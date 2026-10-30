from magnium import BasePlugin, chat, settings, ui

from .stats import summarize


class ChatStatsPlugin(BasePlugin):
    def create_settings(self):
        return [
            settings.Selector("depth", "Сколько сообщений учитывать", [("500", "500"), ("2000", "2000"), ("5000", "5000")], "2000"),
            settings.Text("Считается по сообщениям, загруженным на это устройство."),
        ]

    def message_menu_items(self, message):
        return [("stats", "Статистика чата")]

    def on_message_menu_action(self, item_id, message):
        limit = int(self.get_setting("depth", "2000"))
        text = summarize(chat.recent_messages(message["peer_id"], limit))
        ui.alert("Статистика чата 📊", text or "Нет сообщений для подсчёта.")
