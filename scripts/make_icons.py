#!/usr/bin/env python3
"""Rasterise the team mark (same geometry as logo.svg) onto black tiles for the
home-screen icons and favicon. Run from the repo root:

    python3 scripts/make_icons.py
"""
from PIL import Image, ImageDraw

GOLD = (255, 182, 18)
BLACK = (0, 0, 0)
ART = (385, 100, 1175, 1710)      # x, y, w, h of the mark inside the 1920 box
BOLT = [(745, 465), (1170, 465), (1090, 735), (1290, 735), (565, 1745),
        (525, 1770), (500, 1735), (805, 945), (690, 945)]
TICKS = [(690, 410, 800, 470), (690, 410, 745, 555), (1160, 410, 1235, 555)]


def render(size, pad, ss=4):
    big = size * ss
    im = Image.new("RGB", (big, big), BLACK)
    d = ImageDraw.Draw(im)
    ax, ay, aw, ah = ART
    s = big * (1 - 2 * pad) / ah
    ox = (big - aw * s) / 2 - ax * s
    oy = (big - ah * s) / 2 - ay * s
    P = lambda x, y: (ox + x * s, oy + y * s)
    d.rectangle([P(440, 150), P(1510, 555)], fill=GOLD)
    d.polygon([P(x, y) for x, y in BOLT], fill=GOLD)
    d.rectangle([P(800, 405), P(1160, 470)], fill=GOLD)
    for x0, y0, x1, y1 in TICKS:
        d.rectangle([P(x0, y0), P(x1, y1)], fill=BLACK)
    return im.resize((size, size), Image.LANCZOS)


for name, size, pad in [("icon-512.png", 512, 0.14), ("icon-192.png", 192, 0.14),
                        ("apple-touch-icon.png", 180, 0.14), ("favicon-32.png", 32, 0.06)]:
    render(size, pad).save(name, optimize=True)
    print("wrote", name)
