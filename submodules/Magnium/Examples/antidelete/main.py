import datetime

from magnium import BasePlugin, chat, settings, ui

# How far back "Удалённые в этом чате" looks.
SCAN_LIMIT = 1000


class AntiDeletePlugin(BasePlugin):
    def on_plugin_load(self):
        self._apply()

    def create_settings(self):
        return [
            settings.Header("Антиудаление"),
            settings.Switch("enabled", "Сохранять удалённые сообщения", default=True),
            settings.Text(
                "Сохраняются сообщения, которые уже были загружены на это устройство. Удалённые помечаются "
                "словом «удалено» рядом со временем. Ваши собственные удаления работают как обычно."),
        ]

    def on_setting_changed(self, key, value):
        self._apply()

    def _apply(self):
        self.set_core_flag("preserve_deleted", self.get_setting("enabled", True))

    def message_menu_items(self, message):
        items = [("list", "Удалённые в этом чате")]
        if message["deleted"] and message["text"]:
            items.insert(0, ("copy", "Скопировать удалённый текст"))
        return items

    def on_message_menu_action(self, item_id, message):
        if item_id == "copy":
            ui.copy(message["text"])
            ui.toast("Текст скопирован")
            return
        deleted = [entry for entry in chat.recent_messages(message["peer_id"], SCAN_LIMIT) if entry["deleted"]]
        if not deleted:
            ui.alert("Удалённых нет", "Среди последних {} сообщений этого чата удалённых не найдено.".format(SCAN_LIMIT))
            return
        lines = []
        for entry in deleted[:30]:
            when = datetime.datetime.fromtimestamp(entry["timestamp"]).strftime("%d.%m %H:%M")
            who = "Вы" if entry["outgoing"] else "Собеседник"
            text = entry["text"] or "(медиа)"
            lines.append("{} · {}: {}".format(when, who, text[:120]))
        more = "\n\nи ещё {}".format(len(deleted) - 30) if len(deleted) > 30 else ""
        ui.alert("Удалено: {}".format(len(deleted)), "\n\n".join(lines) + more)
