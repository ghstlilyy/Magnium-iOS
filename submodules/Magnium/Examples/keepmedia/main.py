from magnium import BasePlugin, chat, settings


class KeepMediaPlugin(BasePlugin):
    def on_plugin_load(self):
        self._apply()

    def create_settings(self):
        return [
            settings.Header("Сгорающие медиа"),
            settings.Switch("keep", "Не сжигать после просмотра", default=True,
                            subtext="Открывайте сколько угодно раз"),
            settings.Switch("menu", "«Сохранить в галерею» в меню", default=True),
            settings.Text(
                "Работает для фото и видео с таймером и «просмотр один раз». Если медиа уже было открыто без плагина, "
                "Telegram мог удалить его — тогда сохранить его не получится."),
        ]

    def on_setting_changed(self, key, value):
        self._apply()

    def _apply(self):
        self.set_core_flag("keep_disappearing_media", self.get_setting("keep", True))

    def message_menu_items(self, message):
        if message["has_media"] and self.get_setting("menu", True):
            return [("save", "Сохранить в галерею")]
        return []

    def on_message_menu_action(self, item_id, message):
        if item_id == "save":
            chat.save_media_to_gallery(message["peer_id"], message["message_id"])
