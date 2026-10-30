"""Magnium plugin API.

A plugin ships as a .mpp file (Magnium plugin package): a zip archive with manifest.json at
its root, any number of Python modules and optional assets::

    manifest.json
    main.py          the entry module (manifest "entry", "main" by default)
    replies.py       other modules, imported with `from . import replies`
    icon.png

The entry module defines one BasePlugin subclass::

    from magnium import BasePlugin, HookResult, HookStrategy

    class PingPlugin(BasePlugin):
        def on_plugin_load(self):
            self.add_hook("send_message")

        def on_hook(self, name, payload):
            if payload.get("text") == "!ping":
                payload["text"] = "pong"
                return HookResult(HookStrategy.MODIFY, payload)
            return None

Plugins run inside the app process with the same rights as the app itself. Besides this
module, ``rubicon.objc`` gives them the whole Objective-C runtime (UIKit included), and
``ctypes`` any exported C function.
"""

from ._host import call, clear_interval, log, run_on_main_thread, set_interval
from . import chat, settings, ui
from ._plugin import BasePlugin, HookResult, HookStrategy

__all__ = [
    "BasePlugin",
    "HookResult",
    "HookStrategy",
    "call",
    "chat",
    "clear_interval",
    "log",
    "run_on_main_thread",
    "set_interval",
    "settings",
    "ui",
]
