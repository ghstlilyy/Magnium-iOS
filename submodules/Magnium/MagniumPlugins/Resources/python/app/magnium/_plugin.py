"""The base class every plugin subclasses."""

import json
import os

from ._host import call


class HookStrategy:
    # Leave the payload as it is and let the next plugin see it.
    DEFAULT = "default"
    # Replace the payload with HookResult.payload.
    MODIFY = "modify"
    # Stop the action; later plugins are not called.
    CANCEL = "cancel"


class HookResult:
    def __init__(self, strategy=HookStrategy.DEFAULT, payload=None):
        self.strategy = strategy
        self.payload = payload


class BasePlugin:
    # Filled in by the plugin manager before on_plugin_load().
    id = None
    # The installed package directory, for reading bundled assets.
    path = None
    name = None
    data_path = None

    def __init__(self):
        self._hooks = {}
        self._settings = None

    # Lifecycle

    def on_plugin_load(self):
        pass

    def on_plugin_unload(self):
        pass

    # Hooks

    def add_hook(self, name, priority=0):
        """Subscribes to a hook or event; higher priority runs first."""
        self._hooks[name] = priority

    def remove_hook(self, name):
        self._hooks.pop(name, None)

    def on_hook(self, name, payload):
        """Called for every hook added with add_hook(). Returns a HookResult or None."""
        return None

    # Core switches. Everything a plugin switches on is switched off when it is unloaded.

    def set_core_flag(self, flag, value):
        """flag: "preserve_deleted" (keep messages the server deletes, marked "удалено") or
        "keep_disappearing_media" (opening self-destructing media does not consume it)."""
        call("core.set_flag", owner=self.id, flag=flag, value=bool(value))

    def block_requests(self, methods):
        """Never sends the given TL methods, e.g. ["messages.readHistory"]. An empty list unblocks."""
        call("network.set_blocked", owner=self.id, methods=sorted(set(methods)))

    # Message menu (long press on a message)

    def message_menu_items(self, message):
        """Returns [(item_id, title), ...] to add to the menu of `message`:
        {"peer_id", "message_id", "text", "outgoing", "has_media", "timestamp", "deleted"}."""
        return []

    def on_message_menu_action(self, item_id, message):
        pass

    # Settings page

    def create_settings(self):
        """Returns the items of the plugin's settings page, built with magnium.settings."""
        return []

    def on_setting_changed(self, key, value):
        """Called after a switch, selector or input on the settings page changed `key`."""
        pass

    def on_settings_button(self, key):
        """Called when a settings.Button is tapped."""
        pass

    # Settings, stored as JSON in the plugin's data directory

    def get_setting(self, key, default=None):
        return self._load_settings().get(key, default)

    def set_setting(self, key, value):
        settings = self._load_settings()
        settings[key] = value
        os.makedirs(self.data_path, exist_ok=True)
        temporary_path = os.path.join(self.data_path, "settings.json.tmp")
        with open(temporary_path, "w") as file:
            json.dump(settings, file)
        os.replace(temporary_path, os.path.join(self.data_path, "settings.json"))

    def _load_settings(self):
        if self._settings is None:
            try:
                with open(os.path.join(self.data_path, "settings.json")) as file:
                    self._settings = json.load(file)
            except (OSError, ValueError):
                self._settings = {}
        return self._settings
