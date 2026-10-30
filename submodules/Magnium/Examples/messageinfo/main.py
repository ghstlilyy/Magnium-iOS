import datetime

from magnium import BasePlugin, ui


class MessageInfoPlugin(BasePlugin):
    def message_menu_items(self, message):
        return [("info", "Информация"), ("copy_id", "Скопировать ID")]

    def on_message_menu_action(self, item_id, message):
        if item_id == "copy_id":
            ui.copy(str(message["message_id"]))
            ui.toast("ID {} скопирован".format(message["message_id"]))
            return
        sent = datetime.datetime.fromtimestamp(message["timestamp"])
        lines = [
            "Отправлено: {}".format(sent.strftime("%d.%m.%Y %H:%M:%S")),
            "Направление: {}".format("исходящее" if message["outgoing"] else "входящее"),
            "ID сообщения: {}".format(message["message_id"]),
            "ID чата: {}".format(message["peer_id"]),
            "Символов: {}".format(len(message["text"])),
            "Слов: {}".format(len(message["text"].split())),
            "Медиа: {}".format("есть" if message["has_media"] else "нет"),
        ]
        if message["deleted"]:
            lines.append("Удалено собеседником")
        ui.alert("Сообщение", "\n".join(lines))
