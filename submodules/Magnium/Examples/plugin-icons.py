#!/usr/bin/env python3
# Draws the icons of the bundled example plugins: a vertical gradient and a white glyph made of
# coverage functions, antialiased by 4x4 supersampling. Standard library only.

import math
import os
import struct
import zlib

SIZE = 120
SAMPLES = 4
BASE = os.path.dirname(os.path.abspath(__file__))


def write_png(path, pixels):
    rows = []
    for row in pixels:
        line = bytearray([0])
        for r, g, b, a in row:
            line += bytes((int(r), int(g), int(b), int(a)))
        rows.append(bytes(line))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    with open(path, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\n")
        file.write(chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)))
        file.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        file.write(chunk(b"IEND", b""))


def icon(path, top, bottom, glyph):
    pixels = []
    for y in range(SIZE):
        t = y / (SIZE - 1)
        background = tuple(top[i] + (bottom[i] - top[i]) * t for i in range(3))
        row = []
        for x in range(SIZE):
            covered = 0
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    u = (x + (sx + 0.5) / SAMPLES) / SIZE * 2 - 1
                    v = (y + (sy + 0.5) / SAMPLES) / SIZE * 2 - 1
                    covered += 1 if glyph(u, v) else 0
            k = covered / (SAMPLES * SAMPLES)
            row.append(tuple(background[i] + (255 - background[i]) * k for i in range(3)) + (255,))
        pixels.append(row)
    write_png(path, pixels)


def circle(u, v, cx, cy, r):
    return (u - cx) ** 2 + (v - cy) ** 2 <= r * r


def ghost(u, v):
    body = (circle(u, v, 0, -0.12, 0.42) or (abs(u) <= 0.42 and -0.12 <= v <= 0.42))
    # Wavy hem.
    hem = v > 0.42 - 0.1 * (1 + math.cos((u + 0.42) / 0.84 * 3 * 2 * math.pi)) / 2 and v > 0.3
    eyes = circle(u, v, -0.15, -0.12, 0.07) or circle(u, v, 0.15, -0.12, 0.07)
    return body and not hem and not eyes


def trash(u, v):
    lid = abs(u) <= 0.42 and -0.42 <= v <= -0.32
    handle = abs(u) <= 0.13 and -0.52 <= v <= -0.42 and not (abs(u) <= 0.06 and v > -0.47)
    can = abs(u) <= 0.33 - (v + 0.25) * 0.08 and -0.25 <= v <= 0.5
    slots = any(abs(u - x) <= 0.035 and -0.12 <= v <= 0.38 for x in (-0.15, 0.0, 0.15))
    arrow = circle(u, v, 0, 0.13, 0.0)
    return (lid or handle or can) and not slots and not arrow


def flame(u, v):
    # A teardrop flame with an inner cut.
    def drop(x, y, scale):
        x, y = x / scale, y / scale
        if y > 0.15:
            return x * x + (y - 0.15) ** 2 <= 0.4 ** 2
        return abs(x) <= 0.4 * max(0.0, (y + 0.65) / 0.8) ** 1.3
    return drop(u, v - 0.05, 1.0) and not drop(u, v - 0.22, 0.48)


def camera(u, v):
    body = abs(u) <= 0.5 and -0.25 <= v <= 0.38
    bump = abs(u) <= 0.17 and -0.38 <= v <= -0.25
    lens = circle(u, v, 0, 0.06, 0.2) and not circle(u, v, 0, 0.06, 0.12)
    return (body or bump) and not (circle(u, v, 0, 0.06, 0.2) and not lens)


def no_ads(u, v):
    ring = circle(u, v, 0, 0, 0.5) and not circle(u, v, 0, 0, 0.38)
    slash = abs(u - v) <= 0.09 and abs(u) <= 0.4
    return ring or slash


def info(u, v):
    dot = circle(u, v, 0, -0.3, 0.09)
    stem = abs(u) <= 0.08 and -0.12 <= v <= 0.42
    foot = abs(u) <= 0.18 and 0.34 <= v <= 0.42
    return dot or stem or foot


def bolt(u, v):
    # A lightning bolt: two slanted parallelograms.
    upper = -0.5 <= v <= 0.05 and abs((u + 0.05) - (-v * 0.45 - 0.05)) <= 0.16 * (1 if v < 0 else 0.5) + 0.0
    lower = -0.05 <= v <= 0.5 and abs((u - 0.05) - (-v * 0.45 + 0.15)) <= 0.16
    bar = -0.08 <= v <= 0.06 and -0.25 <= u <= 0.3
    return upper or lower or bar


def bookmark(u, v):
    body = abs(u) <= 0.32 and -0.5 <= v <= 0.5
    notch = v > 0.5 - (0.32 - abs(u)) * 0.9
    return body and not notch


def chart(u, v):
    bars = [(-0.35, 0.1), (0.0, -0.25), (0.35, -0.45)]
    return any(abs(u - x) <= 0.12 and top <= v <= 0.45 for x, top in bars)


def keyboard(u, v):
    frame = abs(u) <= 0.55 and abs(v) <= 0.32
    keys = any(abs(u - x) <= 0.07 and abs(v - y) <= 0.06 for x in (-0.36, -0.12, 0.12, 0.36) for y in (-0.14, 0.04))
    space = abs(u) <= 0.3 and abs(v - 0.2) <= 0.05
    return frame and not keys and not space


def main():
    icons = {
        "ghost": ((92, 104, 132), (48, 56, 78), ghost),
        "antidelete": ((240, 104, 96), (190, 58, 72), trash),
        "streak": ((255, 170, 60), (232, 86, 40), flame),
        "keepmedia": ((120, 112, 240), (82, 60, 196), camera),
        "noads": ((70, 190, 120), (34, 140, 90), no_ads),
        "messageinfo": ((80, 160, 250), (40, 110, 210), info),
        "shortcuts": ((250, 200, 70), (226, 150, 30), bolt),
        "bookmarks": ((255, 120, 150), (220, 70, 120), bookmark),
        "chatstats": ((90, 200, 220), (40, 140, 180), chart),
        "layout": ((150, 150, 165), (95, 95, 115), keyboard),
    }
    for name, (top, bottom, glyph) in icons.items():
        directory = os.path.join(BASE, name)
        os.makedirs(directory, exist_ok=True)
        icon(os.path.join(directory, "icon.png"), top, bottom, glyph)
    print("ok")


if __name__ == "__main__":
    main()
