#!/usr/bin/env python3
# Draws the Огонёк pet: 5 stages x 5 colours x 4 frames on a 24x24 canvas, and the accessories.
# Every stage keeps the eyes on columns 9-10 and 14-15 so accessories fit all of them.

import json
import math
import os
import struct
import zlib

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streak", "sprites")
CANVAS = 24
CLEAR = (0, 0, 0, 0)
EYE = (40, 24, 20, 255)

PALETTES = {
    "orange": ((255, 128, 40), (255, 214, 80)),
    "blue": ((58, 130, 255), (160, 214, 255)),
    "green": ((52, 190, 100), (184, 245, 150)),
    "purple": ((156, 88, 255), (226, 186, 255)),
    "gold": ((222, 170, 30), (255, 244, 160)),
}

# stage: (top row of the flame, half width, eye row, neck row)
STAGES = {
    "baby": (13, 6.0, 18, 21),
    "teen": (9, 6.5, 15, 19),
    "adult": (6, 7.0, 13, 18),
    "legend": (6, 7.0, 13, 18),
}
TIP_OFFSETS = [0.0, 1.2, 0.0, -1.2]
HEIGHT_OFFSETS = [0, -1, 0, 1]


def write_png(path, pixels):
    height, width = len(pixels), len(pixels[0])
    rows = []
    for row in pixels:
        line = bytearray([0])
        for color in row:
            line += bytes(int(max(0, min(255, c))) for c in color)
        rows.append(bytes(line))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    with open(path, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\n")
        file.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        file.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        file.write(chunk(b"IEND", b""))


def flame_inside(x, y, top, half_width, tip):
    """Teardrop: a circle at the bottom, tapering to a tip at `top`."""
    bottom = CANVAS - 1
    cx, cy = 11.5, bottom - half_width
    if y >= cy:
        return (x - cx) ** 2 + (y - cy) ** 2 <= half_width ** 2
    if y < top:
        return False
    t = (y - top) / max(1.0, cy - top)
    width = half_width * t ** 0.75
    return abs(x - (cx + tip * (1 - t))) <= width


def draw_flame(stage, palette, frame):
    outer, inner = PALETTES[palette]
    top, half_width, eye_row, _ = STAGES[stage]
    top += HEIGHT_OFFSETS[frame]
    tip = TIP_OFFSETS[frame]
    pixels = [[CLEAR] * CANVAS for _ in range(CANVAS)]
    for y in range(CANVAS):
        for x in range(CANVAS):
            px, py = x + 0.5, y + 0.5
            if flame_inside(px, py, top, half_width, tip):
                color = outer + (255,)
                if flame_inside(px, py, top + 5, half_width * 0.55, -tip * 0.6):
                    color = inner + (255,)
                pixels[y][x] = color
    if stage == "legend":
        # A golden aura one pixel around the flame.
        aura = (255, 236, 140, 150)
        for y in range(CANVAS):
            for x in range(CANVAS):
                if pixels[y][x][3] == 0 and any(
                        0 <= y + dy < CANVAS and 0 <= x + dx < CANVAS and pixels[y + dy][x + dx][3] == 255
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    pixels[y][x] = aura
        for sx, sy in ((3, 5 + frame % 2), (20, 8 - frame % 2), (2, 17), (21, 15 + frame % 2)):
            pixels[sy][sx] = (255, 255, 220, 255)
    # Eyes, blinking on frame 2.
    for ex in (9, 10, 14, 15):
        pixels[eye_row][ex] = EYE
        if frame != 2:
            pixels[eye_row - 1][ex] = EYE
    # Cheeks.
    for cx in (8, 16):
        pixels[eye_row + 1][cx] = (255, 150, 150, 200)
    return pixels


def draw_egg(frame):
    pixels = [[CLEAR] * CANVAS for _ in range(CANVAS)]
    wobble = [0, 1, 0, -1][frame]
    for y in range(CANVAS):
        for x in range(CANVAS):
            u = (x + 0.5 - 11.5 - wobble * (1 - (y - 9) / 14.0)) / 6.2
            v = (y + 0.5 - 16.5) / 7.5
            if v < 0:
                v *= 1.15
            if u * u + v * v <= 1 and y >= 9:
                color = (255, 244, 225, 255)
                if (x * 7 + y * 3) % 11 == 0:
                    color = (255, 160, 70, 255)
                if u > 0.45:
                    color = (236, 220, 196, 255)
                pixels[y][x] = color
    if frame == 1:
        # A crack: the egg is about to hatch.
        for x, y in ((10, 12), (11, 13), (12, 12), (13, 13)):
            pixels[y][x] = (180, 140, 100, 255)
    return pixels


def blank(width, height):
    return [[CLEAR] * width for _ in range(height)]


def fill(pixels, x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if 0 <= y < len(pixels) and 0 <= x < len(pixels[0]):
                pixels[y][x] = color


# Accessories: (image, x, anchor, y offset). anchor "top" is the flame's top row, "eyes" the
# eye row, "neck" the neck row; the image's row 0 is placed at anchor + offset.
def accessories():
    items = {}

    cap = blank(14, 6)
    fill(cap, 3, 1, 10, 4, (220, 50, 50, 255))
    fill(cap, 3, 4, 13, 5, (180, 30, 30, 255))
    fill(cap, 6, 0, 7, 0, (255, 255, 255, 255))
    items["hat_cap"] = (cap, 5, "top", -4)

    crown = blank(12, 6)
    fill(crown, 1, 3, 10, 5, (240, 190, 40, 255))
    for x in (1, 5, 6, 10):
        fill(crown, x, 0, x, 2, (240, 190, 40, 255))
    crown[4][3] = (220, 40, 60, 255)
    crown[4][8] = (60, 140, 255, 255)
    crown[0][5] = crown[0][6] = (255, 240, 150, 255)
    items["hat_crown"] = (crown, 6, "top", -4)

    party = blank(10, 9)
    for y in range(9):
        half = y * 0.5
        for x in range(10):
            if abs(x + 0.5 - 5) <= half + 0.5:
                party[y][x] = (90, 180, 255, 255) if (y // 2) % 2 == 0 else (255, 120, 190, 255)
    fill(party, 4, 0, 5, 0, (255, 230, 80, 255))
    items["hat_party"] = (party, 7, "top", -7)

    wizard = blank(12, 10)
    for y in range(8):
        half = y * 0.6
        for x in range(12):
            if abs(x + 0.5 - 6) <= half + 0.5:
                wizard[y][x] = (110, 70, 200, 255)
    fill(wizard, 0, 8, 11, 9, (90, 50, 170, 255))
    wizard[4][6] = (255, 230, 90, 255)
    items["hat_wizard"] = (wizard, 6, "top", -8)

    bow = blank(10, 5)
    for y in range(5):
        for x in range(10):
            d = abs(x + 0.5 - 5)
            if d >= 1 and abs(y + 0.5 - 2.5) <= d * 0.6 + 0.5 and d <= 4.5:
                bow[y][x] = (255, 110, 170, 255)
    fill(bow, 4, 1, 5, 3, (220, 60, 130, 255))
    items["hat_bow"] = (bow, 7, "top", -2)

    beanie = blank(14, 6)
    fill(beanie, 2, 1, 11, 4, (60, 110, 220, 255))
    fill(beanie, 1, 4, 12, 5, (40, 80, 180, 255))
    fill(beanie, 6, 0, 7, 0, (255, 255, 255, 255))
    items["hat_beanie"] = (beanie, 5, "top", -4)

    sunglasses = blank(12, 3)
    fill(sunglasses, 0, 0, 11, 0, (20, 20, 20, 255))
    fill(sunglasses, 1, 1, 4, 2, (20, 20, 20, 255))
    fill(sunglasses, 7, 1, 10, 2, (20, 20, 20, 255))
    sunglasses[1][2] = sunglasses[1][8] = (120, 120, 140, 255)
    items["glasses_sun"] = (sunglasses, 6, "eyes", -1)

    rounds = blank(12, 4)
    for ox in (1, 7):
        for x, y in ((0, 0), (1, 0), (2, 0), (3, 1), (3, 2), (2, 3), (1, 3), (0, 3), (-1, 2), (-1, 1)):
            rounds[y][ox + x] = (60, 40, 30, 255)
    fill(rounds, 4, 1, 6, 1, (60, 40, 30, 255))
    items["glasses_round"] = (rounds, 6, "eyes", -2)

    hearts = blank(12, 3)
    for ox in (1, 7):
        for x, y in ((0, 0), (2, 0), (0, 1), (1, 1), (2, 1), (1, 2)):
            hearts[y][ox + x] = (255, 70, 120, 255)
        hearts[0][ox + 1] = (255, 70, 120, 255)
    fill(hearts, 4, 0, 6, 0, (255, 70, 120, 255))
    items["glasses_hearts"] = (hearts, 5, "eyes", -1)

    for name, color, tail in (("scarf_red", (220, 50, 50, 255), (180, 30, 30, 255)),
                              ("scarf_blue", (60, 120, 230, 255), (40, 90, 190, 255))):
        scarf = blank(14, 5)
        fill(scarf, 0, 0, 13, 1, color)
        fill(scarf, 9, 2, 11, 4, tail)
        items[name] = (scarf, 5, "neck", 0)

    rainbow = blank(14, 5)
    colors = [(230, 60, 60, 255), (250, 160, 40, 255), (250, 230, 60, 255), (70, 200, 90, 255), (60, 140, 240, 255), (150, 80, 220, 255)]
    for x in range(14):
        rainbow[0][x] = colors[x % 6]
        rainbow[1][x] = colors[(x + 1) % 6]
    for y in range(2, 5):
        fill(rainbow, 9, y, 11, y, colors[y])
    items["scarf_rainbow"] = (rainbow, 5, "neck", 0)
    return items


def main():
    os.makedirs(BASE, exist_ok=True)
    for frame in range(4):
        write_png(os.path.join(BASE, "egg_{}.png".format(frame)), draw_egg(frame))
    for stage in STAGES:
        for palette in PALETTES:
            for frame in range(4):
                write_png(os.path.join(BASE, "{}_{}_{}.png".format(stage, palette, frame)), draw_flame(stage, palette, frame))
    layout = {"stages": {stage: {"top": top, "eyes": eyes, "neck": neck} for stage, (top, _, eyes, neck) in STAGES.items()}, "accessories": {}}
    for name, (pixels, x, anchor, offset) in accessories().items():
        write_png(os.path.join(BASE, name + ".png"), pixels)
        layout["accessories"][name] = {"x": x, "anchor": anchor, "offset": offset, "width": len(pixels[0]), "height": len(pixels)}
    with open(os.path.join(BASE, "layout.json"), "w") as file:
        json.dump(layout, file, indent=1)
    print(len(os.listdir(BASE)), "files")


if __name__ == "__main__":
    main()
