#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

FOUNDATION_EXPORT NSErrorDomain const MGPythonErrorDomain;

// Handles a call from Python (`_magnium_host.call(method, json)`). Returns a JSON string or nil.
typedef NSString * _Nullable (^MGPythonHostHandler)(NSString *method, NSString *argumentsJson, NSError * _Nullable * _Nullable error);

// Receives every line Python logs through `_magnium_host.log`.
typedef void (^MGPythonLogHandler)(NSString *line);

// The embedded CPython interpreter. One per process; every call takes the GIL itself,
// so it may be used from any thread.
@interface MGPythonRuntime : NSObject

+ (instancetype)shared;

@property (nonatomic, readonly) BOOL isStarted;

// `homePath` holds lib/python3.X; `searchPaths` are prepended to sys.path.
// `cachePath` receives compiled bytecode, since the app bundle is read-only.
- (BOOL)startWithHomePath:(NSString *)homePath searchPaths:(NSArray<NSString *> *)searchPaths cachePath:(NSString *)cachePath error:(NSError * _Nullable * _Nullable)error;

- (void)setHostHandler:(MGPythonHostHandler _Nullable)handler;
- (void)setLogHandler:(MGPythonLogHandler _Nullable)handler;

// Calls `module.function(argument)` with a string argument; returns the result's str(), or nil for None.
// A Python exception becomes an NSError whose description holds the traceback.
- (nullable NSString *)callFunction:(NSString *)function inModule:(NSString *)module argument:(NSString *)argument error:(NSError * _Nullable * _Nullable)error;

// Runs source in __main__ (for the plugin console).
- (BOOL)executeSource:(NSString *)source error:(NSError * _Nullable * _Nullable)error;

@end

NS_ASSUME_NONNULL_END
