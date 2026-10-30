#!/usr/bin/env python3
# Draws the Клодик sprite frames (16x14 pixel art) and the plugin icon into clawd/assets.
# Only the standard library: PNGs are written by hand.

import os
import struct
import zlib

W, H = 16, 14
BODY = (217, 119, 87, 255)
SHADE = (184, 89, 59, 255)
EYE = (31, 31, 31, 255)
CLEAR = (0, 0, 0, 0)


def frame(bob=0, blink=False, legs=(4, 4, 4, 4), wave=False):
    pixels = [[CLEAR] * W for _ in range(H)]

    def put(x, y, color):
        if 0 <= x < W and 0 <= y < H:
            pixels[y][x] = color

    top = 2 + bob
    # Body: 10x8, with a darker bottom row.
    for y in range(top, top + 8):
        for x in range(3, 13):
            put(x, y, SHADE if y == top + 7 else BODY)
    # Arms.
    for x in (1, 2):
        put(x, top + 3, BODY)
        put(x, top + 4, BODY)
    if wave:
        for x in (13, 14):
            put(x, top + 1, BODY)
            put(x, top + 2, BODY)
        put(14, top, BODY)
    else:
        for x in (13, 14):
            put(x, top + 3, BODY)
            put(x, top + 4, BODY)
    # Eyes.
    for x in (5, 10):
        if blink:
            put(x, top + 3, EYE)
        else:
            put(x, top + 2, EYE)
            put(x, top + 3, EYE)
    # Legs hang below the body, down to the bottom of the sprite.
    for x, length in zip((4, 6, 9, 11), legs):
        for y in range(top + 8, min(H, top + 8 + length)):
            put(x, y, SHADE)
    return pixels


def write_png(path, pixels, scale=1):
    height, width = len(pixels) * scale, len(pixels[0]) * scale
    rows = []
    for row in pixels:
        line = bytearray([0])
        for color in row:
            line += bytes(color) * scale
        rows.extend([bytes(line)] * scale)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    with open(path, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\n")
        file.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        file.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        file.write(chunk(b"IEND", b""))


def main():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clawd", "assets")
    os.makedirs(base, exist_ok=True)
    stand = frame()
    frames = [
        stand, stand, frame(bob=1, legs=(3, 3, 3, 3)), frame(bob=1, legs=(3, 3, 3, 3)), stand,
        frame(legs=(4, 3, 4, 3)), frame(legs=(3, 4, 3, 4)), frame(legs=(4, 3, 4, 3)), frame(legs=(3, 4, 3, 4)),
        stand, frame(blink=True), stand, stand,
        frame(wave=True), frame(wave=True, bob=1, legs=(3, 3, 3, 3)), frame(wave=True), stand, stand,
    ]
    for index, pixels in enumerate(frames):
        write_png(os.path.join(base, "frame_{:02d}.png".format(index)), pixels)

    # The icon: the standing frame, scaled up and centred on a warm background.
    size = 24
    background = (250, 240, 230, 255)
    icon = [[background] * size for _ in range(size)]
    for y in range(H):
        for x in range(W):
            if stand[y][x][3]:
                icon[y + 5][x + 4] = stand[y][x]
    write_png(os.path.join(os.path.dirname(base), "icon.png"), icon, scale=5)
    print("{} frames".format(len(frames)))


if __name__ == "__main__":
    main()
