import os
import traceback

from rubicon.objc import CGPoint

from magnium import BasePlugin, clear_interval, log, set_interval, settings

from . import finder
from .overlay import Overlay

# (setting key, title, class name parts, where on the element, horizontal position 0...1)
# "top": sits on the element's top edge; "bottom": stands on its bottom edge, inside it.
PLACES = [
    ("chat_input", "Поле ввода в чате", ("ChatTextInputPanelNode",), "top", 0.84),
    ("navigation_bar", "Верхняя панель", ("NavigationBarNode",), "bottom", 0.30),
    ("tab_bar", "Нижние вкладки", ("TabBarNode",), "top", 0.64),
    ("context_menu", "Контекстные меню", ("ContextControllerActionsStackNodeImpl",), "top", 0.80),
    ("alerts", "Всплывающие окна", ("AlertContentNode",), "top", 0.80),
    ("search_bar", "Поиск", ("SearchBarNode",), "top", 0.86),
]

TICK_INTERVAL = 1.0 / 15.0
# Finding elements walks the view tree; following them only converts frames.
RESCAN_EVERY_TICKS = 10


class ClawdPlugin(BasePlugin):
    def on_plugin_load(self):
        self._overlay = None
        self._targets = {}
        self._tick_count = 0
        self._reported_error = False
        # The app runs the interval on the main thread, where UIKit may be used.
        self._interval = set_interval(self._tick, TICK_INTERVAL)
        log("Клодик на месте")

    def on_plugin_unload(self):
        # Called on the main thread, so UIKit can be touched here directly.
        clear_interval(self._interval)
        if self._overlay is not None:
            self._overlay.remove()
            self._overlay = None
        self._targets = {}

    def create_settings(self):
        items = [settings.Header("Где сидит Клодик")]
        for key, title, _, _, _ in PLACES:
            items.append(settings.Switch(key, title, default=True))
        items.append(settings.Header("Клодик"))
        items.append(settings.Switch("animated", "Анимация", default=True, subtext="Покачивается, моргает и машет лапкой"))
        items.append(settings.Text("Клодики не мешают нажатиям: они нарисованы в прозрачном слое поверх приложения."))
        return items

    def on_setting_changed(self, key, value):
        # Applied by the next tick, which rescans right away.
        self._tick_count = 0

    def _tick(self):
        try:
            self._update()
        except Exception:
            if not self._reported_error:
                self._reported_error = True
                log("Клодик споткнулся:\n" + traceback.format_exc())

    def _update(self):
        enabled = [place for place in PLACES if self.get_setting(place[0], True)]
        scene, windows = finder.app_windows(excluded=self._overlay.window if self._overlay is not None else None)
        if scene is None:
            return
        if self._overlay is None:
            self._overlay = Overlay(scene, windows[0] if windows else None, os.path.join(self.path, "assets"))
            log("Клодик: окно поверх приложения создано")
        self._overlay.animated = bool(self.get_setting("animated", True))

        if self._tick_count % RESCAN_EVERY_TICKS == 0:
            found = finder.find(windows, {place[0]: place[2] for place in enabled})
            self._targets = {}
            for key, _, _, anchor, position in enabled:
                target = self._pick(found[key], anchor, position)
                if target is not None:
                    self._targets[key] = target
            if self._tick_count == 0:
                log("Клодик: найдено {}, сидит на {}".format(
                    {key: len(views) for key, views in found.items()}, sorted(self._targets)))
        self._tick_count += 1

        for key, _, _, anchor, position in PLACES:
            target = self._targets.get(key)
            placement = self._placement(target, anchor, position) if target is not None else None
            if placement is None:
                self._overlay.hide(key)
            else:
                self._overlay.place(key, *placement)

    def _pick(self, views, anchor, position):
        """The topmost visible candidate: uncovered if possible, otherwise just not hidden."""
        fallback = None
        for view in reversed(views):
            window = finder.window_of(view)
            if window is None:
                continue
            rect = finder.frame_in_window(view, window)
            if rect.size.width < 40 or rect.size.height < 10:
                continue
            x = rect.origin.x + rect.size.width * position
            y = rect.origin.y + 6 if anchor == "top" else rect.origin.y + rect.size.height - 6
            if finder.is_on_top(view, window, CGPoint(x, y)):
                return view
            if fallback is None and finder.is_effectively_visible(view):
                fallback = view
        return fallback

    def _placement(self, view, anchor, position):
        window = finder.window_of(view)
        if window is None:
            return None
        rect = finder.convert_rect(finder.frame_in_window(view, window), window, self._overlay.window)
        if rect.size.width < 40 or rect.size.height < 10:
            return None
        x = rect.origin.x + rect.size.width * position
        # Legs hang two points over the top edge; standing inside, the feet touch the bottom edge.
        y = rect.origin.y + 2 if anchor == "top" else rect.origin.y + rect.size.height - 1
        return x, y
