import datetime
import os
import traceback

from magnium import BasePlugin, HookResult, chat, clear_interval, log, set_interval, settings, ui

from . import finder, shop
from .pet import PetView

CHECK_INTERVAL = 0.5
# How many recent messages count towards a streak (a year of daily chatting fits).
HISTORY_LIMIT = 1500
# A chat's streak is recounted at most this often while it stays open.
STREAK_REFRESH_SECONDS = 60


def _today():
    return datetime.date.today().isoformat()


class StreakPetPlugin(BasePlugin):
    def on_plugin_load(self):
        self._view = None
        self._peer_id = None
        self._streak = 0
        self._at_risk = False
        self._counted_at = 0.0
        self._reported_error = False
        self.add_hook("send_message")
        self._interval = set_interval(self._tick, CHECK_INTERVAL)

    def on_plugin_unload(self):
        clear_interval(self._interval)
        if self._view is not None:
            self._view.remove()
            self._view = None

    # State, kept in the plugin's settings file

    def _coins(self):
        return int(self.get_setting("coins", 20))

    def _level(self):
        return int(self.get_setting("level", 1))

    def _owned(self):
        return set(self.get_setting("owned", ["orange", "none"]))

    def _equipped(self):
        return {slot: self.get_setting("equip_" + slot, "orange" if slot == "color" else "none") for slot in shop.SLOTS}

    def _add_coins(self, amount):
        self.set_setting("coins", self._coins() + amount)

    # Settings page: the pet's stats and the shop

    def create_settings(self):
        level = self._level()
        stage = shop.stage_for_level(level)
        name = self.get_setting("name", "Огонёк")
        items = [
            settings.Header("{} · {}".format(name, shop.STAGE_TITLES[stage])),
            settings.Text("Уровень {} из {} · 🪙 {} монет".format(level, shop.MAX_LEVEL, self._coins())),
            settings.Input("name", "Имя", default="Огонёк", placeholder="Как зовут питомца"),
        ]
        if level < shop.MAX_LEVEL:
            items.append(settings.Button("upgrade", "Улучшить до уровня {} — 🪙 {}".format(level + 1, shop.upgrade_cost(level))))
        else:
            items.append(settings.Text("Максимальный уровень: ваш питомец — легенда ✨"))

        owned = self._owned()
        equipped = self._equipped()
        items.append(settings.Header("Гардероб"))
        for slot, title in (("color", "Цвет"), ("hat", "Шапка"), ("glasses", "Очки"), ("scarf", "Шарф")):
            options = []
            for key, item_title, cost in shop.SLOTS[slot]:
                if key in owned or cost == 0:
                    options.append((key, item_title))
                else:
                    options.append((key, "{} — 🪙 {}".format(item_title, cost)))
            items.append(settings.Selector("equip_" + slot, title, options, equipped[slot]))
        items.append(settings.Text("Одежду видно с уровня 2, когда питомец вылупится из яйца."))

        items.append(settings.Header("Серии"))
        items.append(settings.Switch("visible", "Показывать в чатах", default=True))
        items.append(settings.Text(
            "Серия — сколько дней подряд вы и собеседник оба писали друг другу. За каждое ваше сообщение — "
            "🪙 {} (до {} в день), за продолжение серии — 🪙 {} за каждый её день.".format(
                shop.COINS_PER_MESSAGE, shop.MAX_MESSAGE_COINS_PER_DAY, shop.STREAK_BONUS_PER_DAY)))
        return items

    def on_settings_button(self, key):
        if key == "upgrade":
            self._upgrade()
        if self._view is not None:
            self._view.shown = None

    def on_setting_changed(self, key, value):
        if key.startswith("equip_"):
            self._equip(key[len("equip_"):], value)
        if self._view is not None:
            self._view.shown = None

    def _upgrade(self):
        level = self._level()
        if level >= shop.MAX_LEVEL:
            return
        cost = shop.upgrade_cost(level)
        if self._coins() < cost:
            ui.toast("Не хватает монет: нужно 🪙 {}, есть 🪙 {}".format(cost, self._coins()))
            return
        self._add_coins(-cost)
        self.set_setting("level", level + 1)
        before, after = shop.stage_for_level(level), shop.stage_for_level(level + 1)
        if before != after:
            ui.alert("🎉 {} вырос!".format(self.get_setting("name", "Огонёк")), "Теперь это {}.".format(shop.STAGE_TITLES[after].lower()))
        else:
            ui.toast("Уровень {} ⬆️".format(level + 1))

    def _equip(self, slot, item):
        # The selector already stored the new value; buy it or put the old one back.
        owned = self._owned()
        cost = shop.price(slot, item) or 0
        if item in owned or cost == 0:
            self.set_setting("previous_" + slot, item)
            return
        previous = self.get_setting("previous_" + slot, "orange" if slot == "color" else "none")
        if self._coins() < cost:
            self.set_setting("equip_" + slot, previous)
            ui.toast("«{}» стоит 🪙 {}, у вас 🪙 {}".format(shop.title(slot, item), cost, self._coins()))
            return
        self._add_coins(-cost)
        owned.add(item)
        self.set_setting("owned", sorted(owned))
        self.set_setting("previous_" + slot, item)
        ui.toast("Куплено: {} ✨".format(shop.title(slot, item)))

    # Coins for messages

    def on_hook(self, name, payload):
        if name != "send_message":
            return None
        day = _today()
        earned = int(self.get_setting("earned_" + day, 0))
        if earned < shop.MAX_MESSAGE_COINS_PER_DAY:
            self.set_setting("earned_" + day, earned + shop.COINS_PER_MESSAGE)
            self._add_coins(shop.COINS_PER_MESSAGE)
        # The streak may have just grown.
        self._counted_at = 0.0
        return HookResult()

    # On screen

    def _tick(self):
        try:
            self._update()
        except Exception:
            if not self._reported_error:
                self._reported_error = True
                log("Огонёк: ошибка\n" + traceback.format_exc())

    def _update(self):
        scene, windows = finder.app_windows(excluded=self._view.window if self._view is not None else None)
        if scene is None:
            return
        if self._view is None:
            self._view = PetView(scene, windows[0] if windows else None, os.path.join(self.path, "sprites"))

        peer_id = chat.current_peer_id() if self.get_setting("visible", True) else None
        if peer_id is None:
            self._peer_id = None
            self._view.hide()
            return

        now = datetime.datetime.now().timestamp()
        if peer_id != self._peer_id or now - self._counted_at > STREAK_REFRESH_SECONDS:
            self._peer_id = peer_id
            self._counted_at = now
            messages = chat.recent_messages(peer_id, HISTORY_LIMIT)
            self._streak = shop.streak_days(messages)
            self._at_risk = self._streak > 0 and shop.streak_at_risk(messages)
            self._award_streak_bonus(peer_id)

        equipped = self._equipped()
        stage = shop.stage_for_level(self._level())
        text = "🔥 {}".format(self._streak) if self._streak > 0 else "🔥 0"
        if self._at_risk:
            text += " ⏳"
        self._view.configure(stage, equipped["color"], {slot: equipped[slot] for slot in ("hat", "glasses", "scarf")}, text)
        self._view.place(self._view.window_width() - 12, self._top_offset(windows))

    def _award_streak_bonus(self, peer_id):
        if self._streak <= 0:
            return
        key = "bonus_{}".format(peer_id)
        if self.get_setting(key, "") == _today():
            return
        self.set_setting(key, _today())
        bonus = min(self._streak * shop.STREAK_BONUS_PER_DAY, shop.MAX_STREAK_BONUS)
        self._add_coins(bonus)
        ui.toast("🔥 Серия {} {}! +🪙 {}".format(self._streak, "день" if self._streak % 10 == 1 and self._streak % 100 != 11 else "дней", bonus))

    def _top_offset(self, windows):
        """Just under the chat's navigation bar."""
        views = finder.find(windows[:1], {"bar": ("NavigationBarNode",)})["bar"]
        for view in reversed(views):
            window = finder.window_of(view)
            if window is None or not finder.is_effectively_visible(view):
                continue
            rect = finder.frame_in_window(view, window)
            if rect.size.width > 100:
                return rect.origin.y + rect.size.height + 6
        return 110.0
