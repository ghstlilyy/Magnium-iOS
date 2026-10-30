"""Prices, levels and streaks. Pure logic, no UI."""

import datetime

COLORS = [("orange", "Огненный", 0), ("blue", "Ледяной", 40), ("green", "Лесной", 40), ("purple", "Космический", 80), ("gold", "Золотой", 200)]
HATS = [("none", "Без шапки", 0), ("hat_cap", "Кепка", 25), ("hat_beanie", "Шапка", 25), ("hat_bow", "Бантик", 30), ("hat_party", "Колпак", 45), ("hat_wizard", "Шляпа волшебника", 90), ("hat_crown", "Корона", 150)]
GLASSES = [("none", "Без очков", 0), ("glasses_round", "Круглые очки", 30), ("glasses_sun", "Тёмные очки", 50), ("glasses_hearts", "Очки-сердечки", 70)]
SCARVES = [("none", "Без шарфа", 0), ("scarf_red", "Красный шарф", 20), ("scarf_blue", "Синий шарф", 20), ("scarf_rainbow", "Радужный шарф", 60)]
SLOTS = {"color": COLORS, "hat": HATS, "glasses": GLASSES, "scarf": SCARVES}

MAX_LEVEL = 10
COINS_PER_MESSAGE = 2
MAX_MESSAGE_COINS_PER_DAY = 100
STREAK_BONUS_PER_DAY = 5
MAX_STREAK_BONUS = 100


def price(slot, item):
    for key, _, cost in SLOTS[slot]:
        if key == item:
            return cost
    return None


def title(slot, item):
    for key, name, _ in SLOTS[slot]:
        if key == item:
            return name
    return item


def upgrade_cost(level):
    return 15 * level


def stage_for_level(level):
    if level <= 1:
        return "egg"
    if level <= 3:
        return "baby"
    if level <= 6:
        return "teen"
    if level <= 9:
        return "adult"
    return "legend"


STAGE_TITLES = {"egg": "Яйцо", "baby": "Малыш", "teen": "Подросток", "adult": "Взрослый", "legend": "Легенда"}


def streak_days(messages, today=None):
    """TikTok-style streak: consecutive days on which both sides wrote, ending today or yesterday.

    messages: [{"timestamp", "outgoing"}] in any order.
    """
    today = today or datetime.date.today()
    outgoing_days, incoming_days = set(), set()
    for message in messages:
        day = datetime.date.fromtimestamp(message["timestamp"])
        (outgoing_days if message["outgoing"] else incoming_days).add(day)
    both = outgoing_days & incoming_days
    day = today if today in both else today - datetime.timedelta(days=1)
    streak = 0
    while day in both:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


def streak_at_risk(messages, today=None):
    """Whether today still needs messages from both sides to keep the streak."""
    today = today or datetime.date.today()
    outgoing = any(m["outgoing"] and datetime.date.fromtimestamp(m["timestamp"]) == today for m in messages)
    incoming = any(not m["outgoing"] and datetime.date.fromtimestamp(m["timestamp"]) == today for m in messages)
    return not (outgoing and incoming)
