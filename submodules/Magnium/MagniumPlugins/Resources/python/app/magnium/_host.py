"""Calls into the Swift side of Magnium."""

import json
import sys
import threading

import _magnium_host

_main_thread_callbacks = {}
_main_thread_callbacks_lock = threading.Lock()
_next_callback_id = 0


def call(method, **arguments):
    """Calls a host method registered by the app (MagniumPluginManager.registerHostMethod)."""
    result = _magnium_host.call(method, json.dumps(arguments))
    return None if result is None else json.loads(result)


def log(*values):
    _magnium_host.log(" ".join(str(value) for value in values))


class _LogStream:
    """Sends print() and stderr output to the Magnium log, one line at a time."""

    def __init__(self, prefix):
        self._prefix = prefix
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text):
        with self._lock:
            self._buffer += text
            lines = self._buffer.split("\n")
            self._buffer = lines.pop()
        for line in lines:
            _magnium_host.log(self._prefix + line)
        return len(text)

    def flush(self):
        with self._lock:
            line, self._buffer = self._buffer, ""
        if line:
            _magnium_host.log(self._prefix + line)

    def isatty(self):
        return False


def _log_thread_exception(arguments):
    import traceback
    log("Unhandled exception in thread {}:\n{}".format(
        arguments.thread.name if arguments.thread is not None else "?",
        "".join(traceback.format_exception(arguments.exc_type, arguments.exc_value, arguments.exc_traceback))))


def install_log_streams():
    sys.stdout = _LogStream("")
    sys.stderr = _LogStream("stderr: ")
    threading.excepthook = _log_thread_exception


def run_on_main_thread(function):
    """Schedules function() on the main thread; UIKit must only be touched there."""
    global _next_callback_id
    with _main_thread_callbacks_lock:
        _next_callback_id += 1
        callback_id = _next_callback_id
        _main_thread_callbacks[callback_id] = function
    call("runtime.runOnMainThread", callback_id=callback_id)


# interval id -> (function, module of the function, for cancelling a plugin's intervals on unload)
_intervals = {}
_next_interval_id = 0


def set_interval(function, seconds):
    """Calls function() on the main thread every `seconds` until clear_interval(); returns its id.

    Intervals of a plugin stop by themselves when the plugin is unloaded.
    """
    global _next_interval_id
    _next_interval_id += 1
    interval_id = _next_interval_id
    _intervals[interval_id] = (function, getattr(function, "__module__", None) or "")
    call("runtime.setInterval", interval_id=interval_id, seconds=float(seconds))
    return interval_id


def clear_interval(interval_id):
    if _intervals.pop(interval_id, None) is not None:
        call("runtime.clearInterval", interval_id=interval_id)


def _clear_intervals_of_package(package_name):
    for interval_id, (_, module) in list(_intervals.items()):
        if module == package_name or module.startswith(package_name + "."):
            clear_interval(interval_id)


def _run_interval(interval_id):
    entry = _intervals.get(interval_id)
    if entry is None:
        return
    try:
        entry[0]()
    except Exception:
        # A failing interval would fail on every tick: report it once and stop it.
        import traceback
        log("Interval {} of {} failed and was stopped:\n{}".format(interval_id, entry[1], traceback.format_exc()))
        clear_interval(interval_id)


def _run_main_thread_callback(callback_id):
    with _main_thread_callbacks_lock:
        function = _main_thread_callbacks.pop(callback_id, None)
    if function is not None:
        function()
