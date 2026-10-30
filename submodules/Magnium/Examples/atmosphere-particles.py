#!/usr/bin/env python3
# Draws the Atmosphere particle images and the plugin icon into atmosphere/ (standard library only).
# Shapes are coverage functions sampled 4x4 per pixel, so edges are antialiased.

import math
import os
import struct
import zlib

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atmosphere")
SAMPLES = 4


def write_png(path, width, height, pixel):
    rows = []
    for y in range(height):
        line = bytearray([0])
        for x in range(width):
            r, g, b, a = pixel(x, y)
            line += bytes((max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))), max(0, min(255, int(a)))))
        rows.append(bytes(line))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    with open(path, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\n")
        file.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        file.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        file.write(chunk(b"IEND", b""))


def shape(name, size, color, inside, height=None):
    """Writes a solid-colour image whose alpha is the antialiased coverage of `inside(u, v)`, u, v in -1...1."""
    height = height or size

    def pixel(x, y):
        covered = 0
        for sy in range(SAMPLES):
            for sx in range(SAMPLES):
                u = ((x + (sx + 0.5) / SAMPLES) / size) * 2 - 1
                v = ((y + (sy + 0.5) / SAMPLES) / height) * 2 - 1
                covered += 1 if inside(u, v) else 0
        return color + (255 * covered / (SAMPLES * SAMPLES),)

    write_png(os.path.join(BASE, "particles", name + ".png"), size, height, pixel)


def glow(name, size, color, sharpness):
    """A soft round glow: alpha falls off with distance from the centre."""
    def pixel(x, y):
        u = (x + 0.5) / size * 2 - 1
        v = (y + 0.5) / size * 2 - 1
        distance = math.sqrt(u * u + v * v)
        return color + (255 * max(0.0, 1 - distance) ** sharpness,)

    write_png(os.path.join(BASE, "particles", name + ".png"), size, size, pixel)


def rotated(inside, angle):
    c, s = math.cos(angle), math.sin(angle)
    return lambda u, v: inside(u * c + v * s, -u * s + v * c)


def leaf(u, v):
    # A pointed oval with a thin stem at the bottom.
    body = (u / 0.55) ** 2 + (v / 0.9) ** 2 <= 1 and abs(u) <= 0.55 * (1 - abs(v) ** 3) ** 0.5
    stem = abs(u) < 0.06 and 0.75 < v < 1.0
    vein = abs(u) < 0.03 and -0.8 < v < 0.8
    return (body or stem) and not vein


def petal(u, v):
    oval = (u / 0.6) ** 2 + (v / 0.95) ** 2 <= 1
    notch = (u / 0.2) ** 2 + ((v + 1.0) / 0.3) ** 2 <= 1
    return oval and not notch


def heart(u, v):
    x, y = u * 1.2, -v * 1.2 + 0.25
    return (x * x + y * y - 1) ** 3 - x * x * y ** 3 <= 0


def sparkle(u, v):
    # Four-pointed star.
    return abs(u) ** 0.5 + abs(v) ** 0.5 <= 1


def bubble(u, v):
    distance = math.sqrt(u * u + v * v)
    ring = 0.82 <= distance <= 1.0
    highlight = ((u + 0.35) / 0.22) ** 2 + ((v + 0.35) / 0.14) ** 2 <= 1
    return ring or highlight


def main():
    os.makedirs(os.path.join(BASE, "particles"), exist_ok=True)
    glow("snow", 32, (255, 255, 255), 1.6)
    shape("rain", 4, (200, 220, 255), lambda u, v: True, height=40)
    for name, color in (("leaf_orange", (232, 128, 46)), ("leaf_red", (204, 62, 44)), ("leaf_yellow", (240, 190, 60))):
        shape(name, 40, color, rotated(leaf, 0.5))
    for name, color in (("petal_pink", (255, 183, 206)), ("petal_white", (255, 228, 236))):
        shape(name, 28, color, petal)
    # Confetti is white and tinted per cell.
    shape("confetti", 10, (255, 255, 255), lambda u, v: True, height=16)
    shape("star", 32, (255, 255, 255), sparkle)
    shape("bubble", 40, (210, 235, 255), bubble)
    glow("firefly", 32, (220, 255, 120), 2.2)
    shape("heart", 32, (255, 90, 120), heart)

    # The icon: a night sky with snow, stars and a falling leaf.
    size = 120
    flakes = [(22, 30, 5), (70, 18, 4), (98, 52, 6), (40, 78, 4), (88, 96, 5), (16, 104, 3), (58, 50, 3)]
    stars = [(34, 16), (106, 24), (12, 62)]

    def icon_pixel(x, y):
        t = y / size
        r, g, b = 40 + 30 * t, 52 + 40 * t, 110 + 50 * t
        for fx, fy, fr in flakes:
            d = math.hypot(x - fx, y - fy)
            if d < fr:
                k = max(0.0, 1 - d / fr) ** 0.6
                r, g, b = r + (255 - r) * k, g + (255 - g) * k, b + (255 - b) * k
        for sx, sy in stars:
            if abs(x - sx) ** 0.5 + abs(y - sy) ** 0.5 <= 2.2:
                r, g, b = 255, 245, 200
        lu, lv = (x - 74) / 16.0, (y - 76) / 16.0
        if rotated(leaf, 0.7)(lu, lv):
            r, g, b = 232, 128, 46
        return r, g, b, 255

    write_png(os.path.join(BASE, "icon.png"), size, size, icon_pixel)
    print("ok")


if __name__ == "__main__":
    main()
