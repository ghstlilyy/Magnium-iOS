import os
import traceback

from rubicon.objc import CGPoint

from magnium import BasePlugin, clear_interval, log, set_interval, settings

from . import finder
from .effects import EFFECT_ORDER, EFFECTS, effect_for
from .sky import Sky, low_power_mode

INTENSITY = [("light", "Слабо", 0.5), ("normal", "Средне", 1.0), ("heavy", "Сильно", 2.0), ("storm", "Буря", 4.0)]
SPEED = [("slow", "Медленно", 0.6), ("normal", "Обычно", 1.0), ("fast", "Быстро", 1.7)]
SIZE = [("small", "Мелкие", 0.7), ("normal", "Обычные", 1.0), ("large", "Крупные", 1.5)]
WIND = [("none", "Без ветра", 0.0), ("left", "Влево", -1.0), ("right", "Вправо", 1.0), ("storm_left", "Сильный влево", -2.5), ("storm_right", "Сильный вправо", 2.5)]
OPACITY = [("100", "Полная", 1.0), ("70", "70%", 0.7), ("40", "40%", 0.4)]
WHERE = [("everywhere", "Везде"), ("chats", "Только в чатах"), ("chat_list", "Только в списке чатов")]

# How often the plugin checks the screen size, where the user is and Low Power Mode.
CHECK_INTERVAL = 1.0


def _value(table, key):
    for entry in table:
        if entry[0] == key:
            return entry[2]
    return 1.0


class AtmospherePlugin(BasePlugin):
    def on_plugin_load(self):
        self._sky = None
        self._shown_key = None
        self._reported_error = False
        self._interval = set_interval(self._check, CHECK_INTERVAL)
        self._check()

    def on_plugin_unload(self):
        clear_interval(self._interval)
        if self._sky is not None:
            self._sky.remove()
            self._sky = None

    def create_settings(self):
        effect_options = [("season", "По сезону")] + [(key, EFFECTS[key]["title"]) for key in EFFECT_ORDER if key != "season"]
        return [
            settings.Header("Эффект"),
            settings.Selector("effect", "Что идёт", effect_options, "season"),
            settings.Selector("intensity", "Сколько", [(key, title) for key, title, _ in INTENSITY], "normal"),
            settings.Selector("speed", "Скорость", [(key, title) for key, title, _ in SPEED], "normal"),
            settings.Selector("size", "Размер", [(key, title) for key, title, _ in SIZE], "normal"),
            settings.Selector("wind", "Ветер", [(key, title) for key, title, _ in WIND], "none"),
            settings.Selector("opacity", "Прозрачность", [(key, title) for key, title, _ in OPACITY], "100"),
            settings.Header("Где"),
            settings.Selector("where", "Показывать", WHERE, "everywhere"),
            settings.Switch("low_power", "Пауза в режиме энергосбережения", default=True),
            settings.Text("«По сезону»: зимой снег, весной сакура, летом светлячки, осенью листопад. Частицы не мешают нажатиям."),
        ]

    def on_setting_changed(self, key, value):
        self._shown_key = None
        self._check()

    def _settings_key(self):
        return tuple(str(self.get_setting(key, default)) for key, default in (
            ("effect", "season"), ("intensity", "normal"), ("speed", "normal"), ("size", "normal"), ("wind", "none"), ("opacity", "100")))

    def _check(self):
        try:
            self._update()
        except Exception:
            if not self._reported_error:
                self._reported_error = True
                log("Атмосфера: ошибка\n" + traceback.format_exc())

    def _update(self):
        scene, windows = finder.app_windows(excluded=self._sky.window if self._sky is not None else None)
        if scene is None:
            return
        if self._sky is None:
            self._sky = Sky(scene, windows[0] if windows else None, os.path.join(self.path, "particles"))
            log("Атмосфера: слой создан")

        key = self._settings_key()
        if key != self._shown_key:
            effect_key, intensity, speed, size, wind, opacity = key
            self._sky.show(effect_for(effect_key), _value(INTENSITY, intensity), _value(SPEED, speed), _value(SIZE, size),
                           _value(WIND, wind), _value(OPACITY, opacity))
            self._shown_key = key
            log("Атмосфера: {}".format(effect_for(effect_key)["title"]))
        elif self._sky.bounds_size() != self._sky.size:
            self._sky.layout()

        self._sky.set_visible(self._should_show(windows))

    def _should_show(self, windows):
        if self.get_setting("low_power", True) and low_power_mode():
            return False
        where = self.get_setting("where", "everywhere")
        if where == "everywhere":
            return True
        target = "ChatControllerNode" if where == "chats" else "ChatListControllerNode"
        views = finder.find(windows, {"target": (target,)})["target"]
        for view in reversed(views):
            window = finder.window_of(view)
            if window is None:
                continue
            rect = finder.frame_in_window(view, window)
            centre = CGPoint(rect.origin.x + rect.size.width / 2.0, rect.origin.y + rect.size.height / 2.0)
            if finder.is_on_top(view, window, centre):
                return True
        return False
