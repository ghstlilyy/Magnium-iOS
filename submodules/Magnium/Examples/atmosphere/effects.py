"""The effects: CAEmitterCell parameters per particle, before the user's multipliers."""

import datetime
import math

DOWN = math.pi
UP = 0.0


def cell(image, birth, life, velocity=0.0, velocity_range=0.0, y_acceleration=0.0, x_acceleration=0.0,
         longitude=DOWN, emission_range=0.0, scale=1.0, scale_range=0.0, scale_speed=0.0, spin=0.0,
         spin_range=0.0, alpha_range=0.0, alpha_speed=0.0, color=None, color_range=0.0):
    return dict(locals())


CONFETTI_COLORS = [(0.96, 0.33, 0.36), (0.99, 0.75, 0.24), (0.33, 0.78, 0.46), (0.27, 0.58, 0.96), (0.70, 0.42, 0.95), (0.99, 0.55, 0.78)]

# origin: "top" falls from above the screen, "bottom" rises from below it, "area" appears anywhere.
# render: "unordered" draws normally, "additive" makes overlapping particles glow.
EFFECTS = {
    "snow": dict(title="Снег", origin="top", render="unordered", cells=[
        cell("snow", birth=7, life=18, velocity=55, velocity_range=25, y_acceleration=6, emission_range=0.35,
             scale=0.32, scale_range=0.18, alpha_range=0.45, spin_range=0.6),
    ]),
    "rain": dict(title="Дождь", origin="top", render="unordered", cells=[
        cell("rain", birth=55, life=2.2, velocity=650, velocity_range=150, y_acceleration=350, emission_range=0.03,
             scale=0.55, scale_range=0.2, alpha_range=0.4),
    ]),
    "leaves": dict(title="Листопад", origin="top", render="unordered", cells=[
        cell(name, birth=0.5, life=20, velocity=45, velocity_range=20, y_acceleration=5, x_acceleration=3,
             emission_range=0.7, scale=0.5, scale_range=0.18, spin=0.9, spin_range=2.2, alpha_range=0.15)
        for name in ("leaf_orange", "leaf_red", "leaf_yellow")
    ]),
    "sakura": dict(title="Сакура", origin="top", render="unordered", cells=[
        cell(name, birth=1.3, life=18, velocity=40, velocity_range=20, y_acceleration=4, x_acceleration=5,
             emission_range=0.8, scale=0.45, scale_range=0.2, spin=1.2, spin_range=2.5, alpha_range=0.2)
        for name in ("petal_pink", "petal_white")
    ]),
    "confetti": dict(title="Конфетти", origin="top", render="unordered", cells=[
        cell("confetti", birth=2.2, life=10, velocity=150, velocity_range=70, y_acceleration=45, emission_range=0.9,
             scale=0.9, scale_range=0.35, spin=3.0, spin_range=5.0, color=color)
        for color in CONFETTI_COLORS
    ]),
    "stars": dict(title="Звёзды", origin="area", render="additive", cells=[
        cell("star", birth=2.5, life=3.5, scale=0.3, scale_range=0.2, scale_speed=-0.06, spin_range=0.8,
             alpha_speed=-0.28, color=(1.0, 0.95, 0.8), color_range=0.15),
    ]),
    "bubbles": dict(title="Пузыри", origin="bottom", render="unordered", cells=[
        cell("bubble", birth=1.6, life=14, velocity=70, velocity_range=35, y_acceleration=-6, longitude=UP,
             emission_range=0.4, scale=0.45, scale_range=0.3, alpha_range=0.3, alpha_speed=-0.03),
    ]),
    "fireflies": dict(title="Светлячки", origin="area", render="additive", cells=[
        cell("firefly", birth=1.4, life=7, velocity=14, velocity_range=12, longitude=UP, emission_range=2 * math.pi,
             scale=0.32, scale_range=0.16, alpha_speed=-0.14),
    ]),
    "hearts": dict(title="Сердечки", origin="bottom", render="unordered", cells=[
        cell("heart", birth=0.9, life=12, velocity=65, velocity_range=25, y_acceleration=-8, longitude=UP,
             emission_range=0.5, scale=0.42, scale_range=0.2, spin_range=0.6, alpha_speed=-0.07),
    ]),
}

EFFECT_ORDER = ["season", "snow", "rain", "leaves", "sakura", "confetti", "stars", "bubbles", "fireflies", "hearts"]


def effect_for(key, today=None):
    """Resolves "season" to the effect of the current season."""
    if key == "season":
        month = (today or datetime.date.today()).month
        key = {12: "snow", 1: "snow", 2: "snow", 3: "sakura", 4: "sakura", 5: "sakura",
               6: "fireflies", 7: "fireflies", 8: "fireflies"}.get(month, "leaves")
    return EFFECTS.get(key, EFFECTS["snow"])
