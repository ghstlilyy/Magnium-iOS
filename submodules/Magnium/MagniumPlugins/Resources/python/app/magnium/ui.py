"""The app's own UI: toasts, alerts, links."""

from ._host import call


def toast(text):
    """A short notice at the bottom of the screen."""
    call("ui.toast", text=str(text))


def alert(title, text=""):
    call("ui.alert", title=str(title), text=str(text))


def open_url(url):
    """Opens a link the way Telegram does: t.me links in the app, others in the browser."""
    call("app.open_url", url=str(url))


def copy(text):
    """Puts text on the clipboard."""
    call("ui.copy", text=str(text))
