from magnium import BasePlugin, settings, ui

# (setting key, title, subtitle, TL methods that are not sent while it is on)
SWITCHES = [
    ("hide_read", "Не отмечать прочитанным", "Собеседник не увидит двух галочек",
     ["messages.readHistory", "channels.readHistory", "messages.readEncryptedHistory", "messages.readDiscussion"]),
    ("hide_content_read", "Не отмечать голосовые и кружки", "Остаются «непрослушанными» у отправителя",
     ["messages.readMessageContents", "channels.readMessageContents"]),
    ("hide_typing", "Скрывать «печатает…»", None,
     ["messages.setTyping", "messages.setEncryptedTyping"]),
    ("hide_online", "Не показывать онлайн", "Последний визит перестанет обновляться",
     ["account.updateStatus"]),
    ("hide_story_views", "Смотреть истории незаметно", "Вас не будет в списке просмотревших",
     ["stories.readStories", "stories.incrementStoryViews"]),
    ("hide_mentions_read", "Не сбрасывать упоминания и реакции", "Значки @ и ❤️ останутся на чатах",
     ["messages.readMentions", "messages.readReactions"]),
]


class GhostPlugin(BasePlugin):
    def on_plugin_load(self):
        self._apply()

    def create_settings(self):
        items = [
            settings.Header("Режим призрака"),
            settings.Switch("enabled", "Включён", default=True),
            settings.Header("Что скрывать"),
        ]
        for key, title, subtitle, _ in SWITCHES:
            items.append(settings.Switch(key, title, default=key in ("hide_read", "hide_typing", "hide_story_views"), subtext=subtitle))
        items.append(settings.Text(
            "Отметки, которые не отправились, отправятся после выключения режима и перезапуска Magnium. "
            "Пока режим включён, другие ваши устройства тоже не узнают о прочтении."))
        return items

    def on_setting_changed(self, key, value):
        self._apply()
        if key == "enabled":
            ui.toast("Режим призрака включён 👻" if value else "Режим призрака выключен")

    def _apply(self):
        methods = []
        if self.get_setting("enabled", True):
            for key, _, _, blocked in SWITCHES:
                if self.get_setting(key, key in ("hide_read", "hide_typing", "hide_story_views")):
                    methods.extend(blocked)
        self.block_requests(methods)
