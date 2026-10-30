# Magnium

Magnium is an unofficial iOS client built on the [Telegram for iOS](https://github.com/TelegramMessenger/Telegram-iOS)
source (currently app version `13.1.1`). It keeps the full Telegram experience and adds a
Python plugin system that lets you extend the app from inside it, plus a set of built-in
tweaks. It is distributed as a sideloaded `.ipa` (e.g. via [KSign](https://github.com/khcrysalis/Feather)),
not through the App Store.

Official channel: **[t.me/magniumtg](https://t.me/magniumtg)**

> Magnium is not affiliated with or endorsed by Telegram. It is a community fork released
> under the same licence as the upstream project.

## Features

- **Plugins** — Python 3.14 code that runs inside the app with the same rights as the client.
  Install a `.mpp` package by tapping it in any chat, or from Settings ▸ Plugins ▸ *Install from
  file*. Plugins can hook outgoing/incoming actions, add message-menu items, keep deleted and
  self-destructing messages, block TL methods, and ship their own settings pages. See
  [`submodules/Magnium`](submodules/Magnium/README.md) for the full plugin API and
  [`submodules/Magnium/SERVER.md`](submodules/Magnium/SERVER.md) for the plugin server.
- **Magnium settings block** — Magnium's own options live in a dedicated group in Settings,
  separate from Telegram's, alongside the Plugins entry.
- **Hide the Contacts tab** — removes the tab at once; contacts stay reachable from the
  new-message button.

## Repository layout

This is a standard Telegram-iOS checkout. Magnium's own code lives under
[`submodules/Magnium`](submodules/Magnium):

| Module | Purpose |
|---|---|
| `MagniumPlugins` | Plugin runtime and hook core |
| `MagniumPluginsUI` | In-app plugin management UI |
| `MagniumPython` | Embedded Python 3.14 |
| `MagniumServer` | Plugin server |
| `MagniumSettings` | Magnium settings storage |
| `Examples/ping` | A complete example plugin |

Everything else is upstream Telegram-iOS, tracked against the `origin`
(`TelegramMessenger/Telegram-iOS`) remote; Magnium changes live on the `magnium` branch of
`ghstlilyy/Magnium-iOS`.

## Building

Magnium builds with the upstream Bazel/`Make.py` toolchain. See `versions.json` for the exact
Xcode and Bazel versions.

### Requirements

- macOS with the Xcode version pinned in `versions.json`
- A clone **with submodules**:
  ```
  git clone --recursive -j8 https://github.com/ghstlilyy/Magnium-iOS.git
  ```

### Configuration (local only)

You need your own [`api_id`/`api_hash`](https://core.telegram.org/api/obtaining_api_id) and a
code-signing setup. These live in a local configuration JSON and a code-signing directory that
are **not committed** to the repository — keep your credentials out of git.

### IPA

```
python3 build-system/Make/Make.py \
    --cacheDir="$HOME/telegram-bazel-cache" \
    build \
    --configurationPath=path/to/magnium-configuration.json \
    --codesigningInformationPath=path/to/magnium/codesigning \
    --buildNumber=1 \
    --configuration=release_arm64
```

The resulting `.ipa` can be sideloaded onto a device.

## Writing a plugin

Pack a directory into a `.mpp` package:

```
python3 submodules/Magnium/pack-plugin.py <directory>
```

`submodules/Magnium/Examples/ping` is a complete, documented example. Full API reference:
[`submodules/Magnium/README.md`](submodules/Magnium/README.md).

## Licence

Magnium is a fork of Telegram-iOS and is released under the same licence (GPL-2.0-or-later).
As required, the modified source is published here. Please do not use Telegram's name or logo
in a way that implies this is an official Telegram app.
