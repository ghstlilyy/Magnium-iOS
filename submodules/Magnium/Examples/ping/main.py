from magnium import BasePlugin, HookResult, HookStrategy, call, log

from . import replies


class PingPlugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("send_message")
        log("Ping loaded in Magnium", call("app.info")["version"])

    def on_hook(self, name, payload):
        text = payload.get("text", "")
        if text == "!cancel":
            return HookResult(HookStrategy.CANCEL)
        reply = replies.reply_for(text)
        if reply is None:
            return None
        payload["text"] = reply
        return HookResult(HookStrategy.MODIFY, payload)
