#import <MagniumPython/MagniumPython.h>

#define PY_SSIZE_T_CLEAN
#import <Python/Python.h>

NSErrorDomain const MGPythonErrorDomain = @"MGPythonErrorDomain";

static MGPythonHostHandler _Nullable currentHostHandler = nil;
static MGPythonLogHandler _Nullable currentLogHandler = nil;
static NSLock *hostHandlerLock = nil;

static NSError *makeError(NSString *description) {
    return [NSError errorWithDomain:MGPythonErrorDomain code:1 userInfo:@{ NSLocalizedDescriptionKey: description }];
}

// Takes the raised exception (GIL held) and returns its formatted traceback.
static NSString *consumePythonException(void) {
    PyObject *exception = PyErr_GetRaisedException();
    if (exception == NULL) {
        return @"Unknown Python error";
    }
    NSString *result = nil;
    PyObject *traceback = PyImport_ImportModule("traceback");
    if (traceback != NULL) {
        PyObject *lines = PyObject_CallMethod(traceback, "format_exception", "O", exception);
        if (lines != NULL) {
            PyObject *separator = PyUnicode_FromString("");
            PyObject *joined = separator != NULL ? PyUnicode_Join(separator, lines) : NULL;
            if (joined != NULL) {
                const char *text = PyUnicode_AsUTF8(joined);
                if (text != NULL) {
                    result = [NSString stringWithUTF8String:text];
                }
            }
            Py_XDECREF(joined);
            Py_XDECREF(separator);
            Py_DECREF(lines);
        }
        Py_DECREF(traceback);
    }
    if (result == nil) {
        PyObject *string = PyObject_Str(exception);
        const char *text = string != NULL ? PyUnicode_AsUTF8(string) : NULL;
        result = text != NULL ? [NSString stringWithUTF8String:text] : @"Unprintable Python error";
        Py_XDECREF(string);
    }
    PyErr_Clear();
    Py_DECREF(exception);
    return result;
}

// _magnium_host.call(method: str, arguments_json: str) -> str | None
static PyObject *hostCall(PyObject *module, PyObject *args) {
    const char *method = NULL;
    const char *arguments = NULL;
    if (!PyArg_ParseTuple(args, "ss", &method, &arguments)) {
        return NULL;
    }
    [hostHandlerLock lock];
    MGPythonHostHandler handler = currentHostHandler;
    [hostHandlerLock unlock];
    if (handler == nil) {
        PyErr_SetString(PyExc_RuntimeError, "Magnium host is not available");
        return NULL;
    }

    NSString *methodString = [NSString stringWithUTF8String:method];
    NSString *argumentsString = [NSString stringWithUTF8String:arguments];
    __block NSString *result = nil;
    __block NSError *error = nil;
    // The host may call back into Python, possibly from another thread.
    Py_BEGIN_ALLOW_THREADS
    @autoreleasepool {
        NSError *handlerError = nil;
        result = handler(methodString, argumentsString, &handlerError);
        error = handlerError;
    }
    Py_END_ALLOW_THREADS

    if (error != nil) {
        PyErr_SetString(PyExc_RuntimeError, error.localizedDescription.UTF8String);
        return NULL;
    }
    if (result == nil) {
        Py_RETURN_NONE;
    }
    return PyUnicode_FromString(result.UTF8String);
}

// _magnium_host.log(message: str)
static PyObject *hostLog(PyObject *module, PyObject *args) {
    const char *message = NULL;
    if (!PyArg_ParseTuple(args, "s", &message)) {
        return NULL;
    }
    NSString *line = [NSString stringWithUTF8String:message] ?: @"<invalid UTF-8>";
    [hostHandlerLock lock];
    MGPythonLogHandler handler = currentLogHandler;
    [hostHandlerLock unlock];
    if (handler != nil) {
        handler(line);
    } else {
        NSLog(@"[Magnium] %@", line);
    }
    Py_RETURN_NONE;
}

static PyMethodDef hostMethods[] = {
    { "call", hostCall, METH_VARARGS, "Calls a Magnium host method with JSON arguments." },
    { "log", hostLog, METH_VARARGS, "Writes a line to the Magnium log." },
    { NULL, NULL, 0, NULL }
};

static struct PyModuleDef hostModule = {
    PyModuleDef_HEAD_INIT,
    "_magnium_host",
    NULL,
    -1,
    hostMethods,
    NULL,
    NULL,
    NULL,
    NULL
};

static PyObject *initHostModule(void) {
    return PyModule_Create(&hostModule);
}

@interface MGPythonRuntime () {
    NSLock *_startLock;
}

@property (nonatomic, readwrite) BOOL isStarted;

@end

@implementation MGPythonRuntime

+ (instancetype)shared {
    static MGPythonRuntime *instance = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        hostHandlerLock = [[NSLock alloc] init];
        instance = [[MGPythonRuntime alloc] init];
    });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self != nil) {
        _startLock = [[NSLock alloc] init];
    }
    return self;
}

- (BOOL)startWithHomePath:(NSString *)homePath searchPaths:(NSArray<NSString *> *)searchPaths cachePath:(NSString *)cachePath error:(NSError **)error {
    [_startLock lock];
    if (_isStarted) {
        [_startLock unlock];
        return YES;
    }

    NSString *libPath = [homePath stringByAppendingPathComponent:[NSString stringWithFormat:@"lib/python%d.%d", PY_MAJOR_VERSION, PY_MINOR_VERSION]];
    NSMutableArray<NSString *> *paths = [searchPaths mutableCopy];
    [paths addObject:libPath];
    [paths addObject:[libPath stringByAppendingPathComponent:@"lib-dynload"]];
    [paths addObject:[libPath stringByAppendingPathComponent:@"site-packages"]];

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.install_signal_handlers = 0;
    config.buffered_stdio = 0;
    config.site_import = 1;
    config.write_bytecode = 1;
#if PY_VERSION_HEX >= 0x030E0000
    config.use_system_logger = 1;
#endif

    PyStatus status = PyConfig_SetBytesString(&config, &config.home, homePath.fileSystemRepresentation);
    if (!PyStatus_Exception(status)) {
        // .fwork stubs are resolved against the directory of sys.executable, the app bundle.
        status = PyConfig_SetBytesString(&config, &config.executable, [NSBundle mainBundle].executablePath.fileSystemRepresentation);
    }
    if (!PyStatus_Exception(status)) {
        status = PyConfig_SetBytesString(&config, &config.pycache_prefix, cachePath.fileSystemRepresentation);
    }
    config.module_search_paths_set = 1;
    for (NSString *path in paths) {
        if (PyStatus_Exception(status)) {
            break;
        }
        wchar_t *widePath = Py_DecodeLocale(path.fileSystemRepresentation, NULL);
        if (widePath == NULL) {
            status = PyStatus_NoMemory();
            break;
        }
        status = PyWideStringList_Append(&config.module_search_paths, widePath);
        PyMem_RawFree(widePath);
    }

    if (!PyStatus_Exception(status)) {
        if (PyImport_AppendInittab("_magnium_host", &initHostModule) != 0) {
            status = PyStatus_Error("Could not register _magnium_host");
        }
    }
    if (!PyStatus_Exception(status)) {
        status = Py_InitializeFromConfig(&config);
    }
    PyConfig_Clear(&config);

    if (PyStatus_Exception(status)) {
        if (error != NULL) {
            *error = makeError([NSString stringWithFormat:@"Python failed to start: %s", status.err_msg != NULL ? status.err_msg : "unknown error"]);
        }
        [_startLock unlock];
        return NO;
    }

    // Release the GIL; every entry point takes it with PyGILState_Ensure.
    PyEval_SaveThread();
    self.isStarted = YES;
    [_startLock unlock];
    return YES;
}

- (void)setHostHandler:(MGPythonHostHandler)handler {
    [hostHandlerLock lock];
    currentHostHandler = [handler copy];
    [hostHandlerLock unlock];
}

- (void)setLogHandler:(MGPythonLogHandler)handler {
    [hostHandlerLock lock];
    currentLogHandler = [handler copy];
    [hostHandlerLock unlock];
}

- (NSString *)callFunction:(NSString *)function inModule:(NSString *)module argument:(NSString *)argument error:(NSError **)error {
    if (!_isStarted) {
        if (error != NULL) {
            *error = makeError(@"Python is not started");
        }
        return nil;
    }

    NSString *result = nil;
    NSString *failure = nil;
    PyGILState_STATE gil = PyGILState_Ensure();

    PyObject *moduleObject = PyImport_ImportModule(module.UTF8String);
    PyObject *functionObject = moduleObject != NULL ? PyObject_GetAttrString(moduleObject, function.UTF8String) : NULL;
    PyObject *argumentObject = functionObject != NULL ? PyUnicode_FromString(argument.UTF8String) : NULL;
    PyObject *resultObject = argumentObject != NULL ? PyObject_CallOneArg(functionObject, argumentObject) : NULL;
    if (resultObject == NULL) {
        failure = consumePythonException();
    } else if (resultObject != Py_None) {
        PyObject *string = PyObject_Str(resultObject);
        const char *text = string != NULL ? PyUnicode_AsUTF8(string) : NULL;
        if (text != NULL) {
            result = [NSString stringWithUTF8String:text];
        } else {
            failure = consumePythonException();
        }
        Py_XDECREF(string);
    }
    Py_XDECREF(resultObject);
    Py_XDECREF(argumentObject);
    Py_XDECREF(functionObject);
    Py_XDECREF(moduleObject);

    PyGILState_Release(gil);

    if (failure != nil && error != NULL) {
        *error = makeError(failure);
    }
    return result;
}

- (BOOL)executeSource:(NSString *)source error:(NSError **)error {
    if (!_isStarted) {
        if (error != NULL) {
            *error = makeError(@"Python is not started");
        }
        return NO;
    }

    NSString *failure = nil;
    PyGILState_STATE gil = PyGILState_Ensure();

    PyObject *mainModule = PyImport_AddModuleRef("__main__");
    PyObject *globals = mainModule != NULL ? PyModule_GetDict(mainModule) : NULL;
    PyObject *resultObject = globals != NULL ? PyRun_String(source.UTF8String, Py_file_input, globals, globals) : NULL;
    if (resultObject == NULL) {
        failure = consumePythonException();
    }
    Py_XDECREF(resultObject);
    Py_XDECREF(mainModule);

    PyGILState_Release(gil);

    if (failure != nil && error != NULL) {
        *error = makeError(failure);
    }
    return failure == nil;
}

@end
