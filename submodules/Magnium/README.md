# Magnium plugins

Plugins are Python 3.14 code that runs inside Magnium with the same rights as the app. They are
installed from inside the app: tap a message with a `.mpp` file in any chat, or use
Settings ▸ Plugins ▸ "Install from file".

## The `.mpp` package

A `.mpp` file is a zip archive with `manifest.json` at its root:

```
manifest.json
main.py        entry module
replies.py     any other modules and packages
icon.png       optional
```

Pack a directory with `python3 submodules/Magnium/pack-plugin.py <directory>`;
`Examples/ping` is a complete example.

### manifest.json

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Unique id: `a-z`, `0-9`, `.`, `_`, `-`, 2–64 characters, e.g. `com.you.ping`. Installing a package with an installed id replaces it. |
| `name` | yes | Name shown in the plugin list (up to 64 characters). |
| `version` | yes | Version string. |
| `description` | no | Shown under the name. |
| `author` | no | `"Name"` or `{"name": "Name", "url": "https://t.me/magniumtg"}`; the url may be `https://`, `http://` or `tg://`. |
| `icon` | no | Path of a `.png` or `.jpg` inside the package, ideally square. |
| `entry` | no | Entry module, `main` by default. |
| `min_magnium_version` | no | Reserved. |

Packages are refused if they contain absolute paths or `..`, more than 2000 files or more
than 64 MB.

## Writing a plugin

The entry module defines one `BasePlugin` subclass. The package is imported as
`magnium_plugins.<id>`, so its modules import each other with relative imports.

```python
from magnium import BasePlugin, HookResult, HookStrategy, call, log
from . import replies

class PingPlugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("send_message")

    def on_hook(self, name, payload):
        reply = replies.reply_for(payload["text"])
        if reply is None:
            return None
        payload["text"] = reply
        return HookResult(HookStrategy.MODIFY, payload)
```

### BasePlugin

- `on_plugin_load()` / `on_plugin_unload()`: lifecycle. Everything the plugin switched on in the
  core (flags, blocked requests, intervals) is switched off when it is unloaded.
- `add_hook(name, priority=0)`, `remove_hook(name)`, `on_hook(name, payload)`: return
  `HookResult(HookStrategy.MODIFY, payload)` to change the payload, `HookResult(HookStrategy.CANCEL)`
  to stop the action, or `None` to leave it alone.
- `create_settings()` → items from `magnium.settings`: `Header(text)`, `Text(text)`,
  `Switch(key, text, default, subtext)`, `Selector(key, text, [(value, title)], default)`,
  `Input(key, text, default, placeholder)`, `Button(key, text, destructive)`.
  Changes arrive in `on_setting_changed(key, value)`, taps in `on_settings_button(key)`.
  The page is rebuilt after every change, so it can show live values (coins, levels…).
- `get_setting(key, default)` / `set_setting(key, value)`: persistent JSON values.
- `message_menu_items(message)` → `[(item_id, title)]` adds items to a message's long-press menu;
  taps arrive in `on_message_menu_action(item_id, message)`. `message` is
  `{"peer_id", "message_id", "text", "outgoing", "has_media", "timestamp", "deleted"}`.
- `set_core_flag(flag, value)`: `"preserve_deleted"` keeps messages the server deletes (marked
  «удалено»); `"keep_disappearing_media"` stops self-destructing media from being consumed.
- `block_requests([methods])`: TL methods that are never sent, e.g. `"messages.readHistory"`.
- `self.path`: the installed package directory; `self.data_path`: the plugin's own directory.

### Module functions

- `magnium.ui`: `toast(text)`, `alert(title, text)`, `copy(text)`, `open_url(url)`.
- `magnium.chat`: `current_peer_id()`, `my_peer_id()`, `recent_messages(peer_id, limit)`,
  `send_message(peer_id, text)`, `save_media_to_gallery(peer_id, message_id)`.
- `magnium.set_interval(function, seconds)` / `clear_interval(id)`: a main-thread timer (UIKit
  is safe there). A failing interval is logged once and stopped.
- `magnium.run_on_main_thread(function)`, `magnium.log(...)`, `magnium.call(method, **arguments)`.
- `print()` and uncaught exceptions (threads included) go to Settings ▸ Plugins ▸ Журнал.
- `rubicon.objc`: the Objective-C runtime, e.g. `ObjCClass("UIDevice").currentDevice`.

### Hooks

| Hook | Payload | Can |
|---|---|---|
| `app_launch` | `{}` | observe; runs before any Telegram UI exists |
| `send_message` | `{"text", "peer_id", "thread_id", "has_media"}` | change `text`, cancel |

### Host methods (`magnium.call`)

`app.info`, `plugins.list`, `ui.toast`, `ui.alert`, `ui.copy`, `app.open_url`, `account.info`,
`chat.current`, `messages.send`, `messages.recent`, `media.save_to_gallery`, `core.set_flag`,
`network.set_blocked`, `runtime.setInterval`, `runtime.clearInterval`, `runtime.runOnMainThread`.

## Bundled examples

`Examples/` holds the plugins shipped with Magnium; regenerate their art with the `*-sprites.py`,
`atmosphere-particles.py` and `plugin-icons.py` scripts next to them.

| Plugin | What it shows |
|---|---|
| Ping | hooks, rubicon-objc |
| Клодик | overlay window, UIKit animation, settings switches |
| Атмосфера | CAEmitterLayer particles, selectors |
| Призрак | `block_requests` (ghost mode) |
| Антиудаление | `set_core_flag("preserve_deleted")`, message menu, alerts |
| Сгорающие медиа | `set_core_flag("keep_disappearing_media")`, saving media |
| Без рекламы | `block_requests` |
| Инфо о сообщении | message menu, clipboard |
| Быстрые команды | `send_message` hook |
| Огонёк | streak pet: chat history, intervals, coins, shop, buttons, inputs |

## Safe mode

If Magnium closes within 15 seconds of launch three times in a row, it starts without plugins;
Settings ▸ Plugins shows "Enable plugins" to turn them back on.
