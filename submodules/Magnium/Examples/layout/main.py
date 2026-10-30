from magnium import BasePlugin, HookResult, HookStrategy, settings, ui

from .convert import fix, to_english, to_russian


class LayoutPlugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("send_message")

    def create_settings(self):
        return [
            settings.Text("В меню сообщения: «Исправить раскладку» копирует исправленный текст.\nПри отправке: «!ru ghbdtn» → «привет», «!en руддщ» → «hello»."),
        ]

    def message_menu_items(self, message):
        return [("fix", "Исправить раскладку")] if message["text"] else []

    def on_message_menu_action(self, item_id, message):
        fixed = fix(message["text"])
        ui.copy(fixed)
        ui.alert("Исправлено и скопировано", fixed)

    def on_hook(self, name, payload):
        text = payload.get("text", "")
        for command, convert in (("!ru ", to_russian), ("!en ", to_english)):
            if text.startswith(command) and len(text) > len(command):
                payload["text"] = convert(text[len(command):])
                return HookResult(HookStrategy.MODIFY, payload)
        return None
