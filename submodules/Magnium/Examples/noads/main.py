from magnium import BasePlugin, settings

AD_METHODS = ["messages.getSponsoredMessages", "messages.viewSponsoredMessage"]


class NoAdsPlugin(BasePlugin):
    def on_plugin_load(self):
        self._apply()

    def create_settings(self):
        return [
            settings.Switch("enabled", "Скрывать рекламу в каналах", default=True),
            settings.Text("Magnium не запрашивает спонсорские сообщения, поэтому их просто нет. Уже показанные исчезнут после перезахода в канал."),
        ]

    def on_setting_changed(self, key, value):
        self._apply()

    def _apply(self):
        self.block_requests(AD_METHODS if self.get_setting("enabled", True) else [])
