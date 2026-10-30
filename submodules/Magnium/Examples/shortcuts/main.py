from magnium import BasePlugin, HookResult, HookStrategy, settings

from .commands import COMMANDS, EMOTICONS, transform


class ShortcutsPlugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("send_message")

    def create_settings(self):
        return [
            settings.Header("Быстрые команды"),
            settings.Switch("commands", "Команды", default=True),
            settings.Switch("emoticons", "Смайлики-коды", default=True),
            settings.Text("Команды: " + ", ".join(sorted(COMMANDS))),
            settings.Text("Коды: " + ", ".join(sorted(EMOTICONS))),
        ]

    def on_hook(self, name, payload):
        replacement = transform(payload.get("text", ""), use_emoticons=self.get_setting("emoticons", True), use_commands=self.get_setting("commands", True))
        if replacement is None:
            return None
        payload["text"] = replacement
        return HookResult(HookStrategy.MODIFY, payload)
