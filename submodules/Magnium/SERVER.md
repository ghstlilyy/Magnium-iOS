# Magnium server API (draft)

The app talks to a Magnium server once its address is set in Settings ▸ Magnium ▸ Сервер. Until
then the plugin catalog shows how to set one up and badges come only from this device. The client
is `submodules/Magnium/MagniumServer`.

All responses are JSON over HTTPS. Times are Unix seconds. Telegram user ids are decimal strings
in object keys and numbers elsewhere.

## Plugin catalog

`GET /v1/plugins`

```json
{
  "plugins": [
    {
      "id": "magnium.ghost",
      "name": "Призрак",
      "version": "1.0",
      "description": "Читайте, не отправляя отметок о прочтении…",
      "author": {"name": "Magnium", "url": "https://t.me/magniumtg"},
      "icon_url": "https://example.org/plugins/magnium.ghost/icon.png",
      "download_url": "https://example.org/plugins/magnium.ghost/1.0.mpp",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  ]
}
```

The app downloads `download_url`, refuses the file unless its SHA-256 equals `sha256`, then
installs it like any `.mpp` (with the same full-access confirmation). `id` must equal the
package's `manifest.json` id.

## Badges

`GET /v1/badges`

```json
{
  "badges": {
    "123456789": [
      {"id": "founder", "emoji": "👑", "title": "Основатель Magnium"}
    ]
  }
}
```

Fetched on launch and when the server address changes. Badges show on user profiles as
"значки Magnium". The preset ids the app offers when issuing are `founder`, `developer`,
`plugin_author`, `tester`, `supporter`, `early`, `moderator`, `artist`
(`magniumBadgePresets` in `MagniumServer.swift`).

`POST /v1/badges` — issue a badge; owner only.

```
Authorization: Bearer <owner token>
{"user_id": 123456789, "badge_id": "tester"}
```

`204` on success, `401`/`403` for a wrong token. The app stores issued badges locally first, so
they show on the issuing device even without a server.

`DELETE /v1/badges/<user id>/<badge id>` — revoke; owner only. (The app revokes locally today.)

## Badges from other clients

Other clients' badges can be added with a `MagniumBadgeProvider` (`MagniumServer.swift`):
implement `fetchBadges()` returning badges by user id and register it with
`MagniumBadges.shared.register(provider:)`. Only use a client's **public** badge list, with its
author's permission; nothing in Magnium reads private APIs of other clients.

## Plugins that use the server

A plugin can reach any HTTPS endpoint with Python's `urllib.request` (run it off the main thread
with `threading` and report back with `magnium.run_on_main_thread`). A server-backed plugin should
keep its base URL in a `settings.Input`, so it works with any server.
