"""Installs, loads and dispatches hooks for plugins. Driven from Swift through handle().

A plugin is a .mpp file (Magnium plugin package): a zip archive with manifest.json at its
root, the plugin's Python modules and optional assets such as the icon. Installed plugins
live unpacked in <plugins>/<id>/ and are imported as the package magnium_plugins.<id>, so
their modules can import each other with relative imports.
"""

import importlib
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import sys
import traceback
import types
import zipfile

from ._host import _clear_intervals_of_package, _run_interval, _run_main_thread_callback, call, install_log_streams, log
from ._plugin import BasePlugin, HookResult, HookStrategy

MANIFEST_NAME = "manifest.json"
PACKAGE_PREFIX = "magnium_plugins"

MAX_PACKAGE_FILES = 2000
MAX_PACKAGE_SIZE = 64 * 1024 * 1024
ICON_EXTENSIONS = (".png", ".jpg", ".jpeg")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
MODULE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

# id -> BasePlugin
_plugins = {}

install_log_streams()


class PluginError(Exception):
    pass


def _string(manifest, key, required=False, limit=4096):
    value = manifest.get(key)
    if value is None:
        if required:
            raise PluginError("manifest.json has no \"{}\"".format(key))
        return None
    if not isinstance(value, str) or not value.strip():
        raise PluginError("\"{}\" in manifest.json must be a non-empty string".format(key))
    return value.strip()[:limit]


def validate_manifest(manifest, file_names):
    """Checks manifest.json and returns it flattened to strings, as Swift reads it."""
    if not isinstance(manifest, dict):
        raise PluginError("manifest.json must be a JSON object")

    plugin_id = _string(manifest, "id", required=True)
    if not ID_PATTERN.match(plugin_id):
        raise PluginError("\"id\" may only contain a-z, 0-9, \".\", \"_\" and \"-\" (2-64 characters)")

    result = {
        "id": plugin_id,
        "name": _string(manifest, "name", required=True, limit=64),
        "version": _string(manifest, "version", required=True, limit=32),
    }
    description = _string(manifest, "description", limit=1024)
    if description:
        result["description"] = description

    author = manifest.get("author")
    if isinstance(author, str):
        author = {"name": author}
    if author is not None:
        if not isinstance(author, dict):
            raise PluginError("\"author\" must be a string or {\"name\", \"url\"}")
        author_name = _string(author, "name", required=True, limit=64)
        result["author_name"] = author_name
        author_url = _string(author, "url", limit=512)
        if author_url:
            if not re.match(r"^(https?://|tg://)", author_url):
                raise PluginError("\"author.url\" must start with https://, http:// or tg://")
            result["author_url"] = author_url

    entry = _string(manifest, "entry") or "main"
    if not MODULE_PATTERN.match(entry):
        raise PluginError("\"entry\" must be a module name such as \"main\"")
    entry_path = entry.replace(".", "/")
    if entry_path + ".py" not in file_names and entry_path + "/__init__.py" not in file_names:
        raise PluginError("The entry module \"{}\" is not in the package".format(entry))
    result["entry"] = entry

    icon = _string(manifest, "icon")
    if icon:
        if not icon.lower().endswith(ICON_EXTENSIONS):
            raise PluginError("\"icon\" must be a .png or .jpg file")
        if icon not in file_names:
            raise PluginError("The icon \"{}\" is not in the package".format(icon))
        result["icon"] = icon

    min_version = _string(manifest, "min_magnium_version", limit=32)
    if min_version:
        result["min_magnium_version"] = min_version
    return result


def _check_member_name(name):
    parts = name.split("/")
    if name.startswith("/") or "\\" in name or any(part in ("", "..") for part in parts[:-1]) or ".." in parts:
        raise PluginError("The package contains an unsafe path: " + name)


def _open_package(path):
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise PluginError("This is not a .mpp package (not a zip archive)")
    members = [info for info in archive.infolist() if not info.is_dir()]
    if len(members) > MAX_PACKAGE_FILES:
        raise PluginError("The package has too many files")
    if sum(info.file_size for info in members) > MAX_PACKAGE_SIZE:
        raise PluginError("The package is too large")
    for info in members:
        _check_member_name(info.filename)
    return archive, {info.filename for info in members}


def inspect_package(path):
    archive, file_names = _open_package(path)
    with archive:
        if MANIFEST_NAME not in file_names:
            raise PluginError("The package has no manifest.json at its root")
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except ValueError as error:
            raise PluginError("manifest.json is not valid JSON: {}".format(error))
        return validate_manifest(manifest, file_names)


def install_package(path, plugins_path):
    """Unpacks the package into <plugins_path>/<id>, replacing an installed version."""
    metadata = inspect_package(path)
    plugin_id = metadata["id"]
    if plugin_id in _plugins:
        unload(plugin_id)

    destination = os.path.join(plugins_path, plugin_id)
    staging = destination + ".installing"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    archive, _ = _open_package(path)
    with archive:
        for info in archive.infolist():
            target = os.path.realpath(os.path.join(staging, info.filename))
            if not target.startswith(os.path.realpath(staging) + os.sep):
                raise PluginError("The package contains an unsafe path: " + info.filename)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as file:
                shutil.copyfileobj(source, file)

    previous = destination + ".previous"
    shutil.rmtree(previous, ignore_errors=True)
    if os.path.exists(destination):
        os.rename(destination, previous)
    os.rename(staging, destination)
    shutil.rmtree(previous, ignore_errors=True)
    return metadata


def _package_name(plugin_id):
    return "{}.{}".format(PACKAGE_PREFIX, re.sub(r"[^A-Za-z0-9_]", "_", plugin_id))


def _forget_modules(package_name):
    for name in list(sys.modules):
        if name == package_name or name.startswith(package_name + "."):
            del sys.modules[name]


def _find_plugin_class(module):
    for value in vars(module).values():
        if isinstance(value, type) and issubclass(value, BasePlugin) and value is not BasePlugin and value.__module__ == module.__name__:
            return value
    raise PluginError("The entry module defines no BasePlugin subclass")


def load(path, data_path):
    """Imports an installed plugin directory and calls on_plugin_load()."""
    with open(os.path.join(path, MANIFEST_NAME), encoding="utf-8") as file:
        manifest = json.load(file)
    file_names = set()
    for directory, _, names in os.walk(path):
        for name in names:
            file_names.add(os.path.relpath(os.path.join(directory, name), path).replace(os.sep, "/"))
    metadata = validate_manifest(manifest, file_names)
    plugin_id = metadata["id"]
    if plugin_id in _plugins:
        unload(plugin_id)

    if PACKAGE_PREFIX not in sys.modules:
        root = types.ModuleType(PACKAGE_PREFIX)
        root.__path__ = []
        sys.modules[PACKAGE_PREFIX] = root

    package_name = _package_name(plugin_id)
    _forget_modules(package_name)
    init_path = os.path.join(path, "__init__.py")
    spec = importlib.util.spec_from_file_location(package_name, init_path if os.path.exists(init_path) else None, submodule_search_locations=[path])
    if spec is None:
        spec = importlib.machinery.ModuleSpec(package_name, None, is_package=True)
        spec.submodule_search_locations = [path]
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    try:
        if spec.loader is not None:
            spec.loader.exec_module(package)
        module = importlib.import_module(package_name + "." + metadata["entry"])
        plugin = _find_plugin_class(module)()
        plugin.id = plugin_id
        plugin.name = metadata["name"]
        plugin.path = path
        plugin.data_path = data_path
        plugin.on_plugin_load()
    except BaseException:
        _forget_modules(package_name)
        raise
    _plugins[plugin_id] = plugin
    log("Loaded plugin", plugin_id)
    return metadata


def unload(plugin_id):
    plugin = _plugins.pop(plugin_id, None)
    if plugin is None:
        return
    try:
        plugin.on_plugin_unload()
    finally:
        _clear_intervals_of_package(_package_name(plugin_id))
        try:
            call("core.release_owner", owner=plugin_id)
        except Exception:
            pass
        _forget_modules(_package_name(plugin_id))
    log("Unloaded plugin", plugin_id)


def run_hook(name, payload):
    """Runs the hook through every subscribed plugin, highest priority first."""
    subscribers = [plugin for plugin in _plugins.values() if name in plugin._hooks]
    subscribers.sort(key=lambda plugin: -plugin._hooks[name])
    strategy = HookStrategy.DEFAULT
    errors = []
    for plugin in subscribers:
        try:
            result = plugin.on_hook(name, payload)
        except Exception:
            # One broken plugin must not break the action for everyone else.
            errors.append({"plugin": plugin.id, "error": traceback.format_exc()})
            continue
        if not isinstance(result, HookResult):
            continue
        if result.strategy == HookStrategy.CANCEL:
            strategy = HookStrategy.CANCEL
            break
        if result.strategy == HookStrategy.MODIFY:
            strategy = HookStrategy.MODIFY
            payload = result.payload
    for error in errors:
        log("Plugin {} failed in hook {}:\n{}".format(error["plugin"], name, error["error"]))
    return {"strategy": strategy, "payload": payload, "errors": errors}


def message_menu(message):
    """Collects the plugins' items for a message's menu: [{"plugin", "id", "title"}]."""
    items = []
    for plugin in _plugins.values():
        try:
            for item_id, title in plugin.message_menu_items(message) or []:
                items.append({"plugin": plugin.id, "id": str(item_id), "title": str(title)})
        except Exception:
            log("Plugin {} failed in message_menu_items:\n{}".format(plugin.id, traceback.format_exc()))
    return items


def message_menu_action(plugin_id, item_id, message):
    plugin = _plugins.get(plugin_id)
    if plugin is None:
        raise PluginError("The plugin is not running")
    plugin.on_message_menu_action(item_id, message)


def settings_items(plugin_id):
    """The plugin's settings page, with each switch's current value filled in."""
    plugin = _plugins.get(plugin_id)
    if plugin is None:
        return []
    items = []
    for item in plugin.create_settings() or []:
        if not isinstance(item, dict) or item.get("type") not in ("header", "text", "switch", "selector", "input", "button"):
            continue
        item = dict(item)
        if item["type"] == "switch":
            item["value"] = bool(plugin.get_setting(item["key"], item.get("default", False)))
        elif item["type"] == "input":
            item["value"] = str(plugin.get_setting(item["key"], item.get("default", "")))
        elif item["type"] == "selector":
            item["value"] = str(plugin.get_setting(item["key"], item.get("default", "")))
        items.append(item)
    return items


def update_setting(plugin_id, key, value):
    plugin = _plugins.get(plugin_id)
    if plugin is None:
        raise PluginError("The plugin is not running")
    plugin.set_setting(key, value)
    plugin.on_setting_changed(key, value)


def press_settings_button(plugin_id, key):
    plugin = _plugins.get(plugin_id)
    if plugin is None:
        raise PluginError("The plugin is not running")
    plugin.on_settings_button(key)


def handle(request_json):
    """The single entry point used by MagniumPluginManager. Never raises."""
    try:
        request = json.loads(request_json)
        command = request["command"]
        if command == "inspect":
            result = inspect_package(request["path"])
        elif command == "install":
            result = install_package(request["path"], request["plugins_path"])
        elif command == "load":
            result = load(request["path"], request["data_path"])
        elif command == "unload":
            unload(request["id"])
            result = None
        elif command == "hook":
            result = run_hook(request["name"], request.get("payload"))
        elif command == "settings":
            result = settings_items(request["id"])
        elif command == "set_setting":
            update_setting(request["id"], request["key"], request["value"])
            result = None
        elif command == "settings_button":
            press_settings_button(request["id"], request["key"])
            result = None
        elif command == "message_menu":
            result = message_menu(request["message"])
        elif command == "message_menu_action":
            message_menu_action(request["plugin"], request["id"], request["message"])
            result = None
        elif command == "interval":
            _run_interval(request["interval_id"])
            result = None
        elif command == "main_thread_callback":
            _run_main_thread_callback(request["callback_id"])
            result = None
        else:
            raise PluginError("Unknown command " + command)
        return json.dumps({"ok": True, "result": result})
    except PluginError as error:
        return json.dumps({"ok": False, "error": str(error)})
    except BaseException as error:
        return json.dumps({"ok": False, "error": str(error), "traceback": traceback.format_exc()})
