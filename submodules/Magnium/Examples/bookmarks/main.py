import datetime

from magnium import BasePlugin, settings, ui

MAX_BOOKMARKS = 200


class BookmarksPlugin(BasePlugin):
    def _bookmarks(self):
        return list(self.get_setting("items", []))

    def message_menu_items(self, message):
        return [("add", "В закладки")]

    def on_message_menu_action(self, item_id, message):
        items = self._bookmarks()
        if any(item["peer_id"] == message["peer_id"] and item["message_id"] == message["message_id"] for item in items):
            ui.toast("Уже в закладках")
            return
        items.insert(0, {
            "peer_id": message["peer_id"],
            "message_id": message["message_id"],
            "text": (message["text"] or "(медиа)")[:500],
            "timestamp": message["timestamp"],
            "saved": int(datetime.datetime.now().timestamp()),
        })
        self.set_setting("items", items[:MAX_BOOKMARKS])
        ui.toast("Добавлено в закладки 🔖")

    def create_settings(self):
        items = self._bookmarks()
        result = [settings.Header("Закладки: {}".format(len(items)))]
        if not items:
            result.append(settings.Text("Пока пусто. Нажмите и удерживайте сообщение → «В закладки»."))
            return result
        for index, item in enumerate(items[:50]):
            when = datetime.datetime.fromtimestamp(item["timestamp"]).strftime("%d.%m.%Y %H:%M")
            result.append(settings.Text("{} · чат {}\n{}".format(when, item["peer_id"], item["text"])))
            result.append(settings.Button("copy_{}".format(index), "Скопировать"))
            result.append(settings.Button("delete_{}".format(index), "Удалить", destructive=True))
        result.append(settings.Header(""))
        result.append(settings.Button("clear", "Очистить все", destructive=True))
        return result

    def on_settings_button(self, key):
        items = self._bookmarks()
        if key == "clear":
            self.set_setting("items", [])
            ui.toast("Закладки очищены")
            return
        action, _, index = key.partition("_")
        index = int(index)
        if index >= len(items):
            return
        if action == "copy":
            ui.copy(items[index]["text"])
            ui.toast("Скопировано")
        elif action == "delete":
            del items[index]
            self.set_setting("items", items)
