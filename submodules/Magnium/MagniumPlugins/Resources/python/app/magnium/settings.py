"""Items a plugin returns from BasePlugin.create_settings(); shown on the plugin's page in the app."""


def Header(text):
    return {"type": "header", "text": text}


def Text(text):
    """A note under the previous items."""
    return {"type": "text", "text": text}


def Switch(key, text, default=False, subtext=None):
    """A switch stored under `key` (see BasePlugin.get_setting); its changes reach on_setting_changed()."""
    item = {"type": "switch", "key": key, "text": text, "default": bool(default)}
    if subtext:
        item["subtext"] = subtext
    return item


def Selector(key, text, options, default):
    """A choice stored under `key`: options are (value, title) pairs, values are strings."""
    return {
        "type": "selector",
        "key": key,
        "text": text,
        "options": [[str(value), str(title)] for value, title in options],
        "default": str(default),
    }


def Input(key, text, default="", placeholder=""):
    """A one-line text field stored under `key`."""
    return {"type": "input", "key": key, "text": text, "default": str(default), "placeholder": str(placeholder)}


def Button(key, text, destructive=False):
    """A button; a tap calls BasePlugin.on_settings_button(key). Nothing is stored."""
    return {"type": "button", "key": key, "text": text, "destructive": bool(destructive)}
