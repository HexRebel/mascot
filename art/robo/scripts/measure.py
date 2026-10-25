"""Checks that Robo is the same size in every frame: the width of its visor (the biggest navy patch) in each
128x128 frame, against frame 60 (standing still). Gemini draws each image a little bigger or smaller, and
compose.py resizes them by the visor; run this after adding images, and look at the ones it marks.

    measure.py <pack directory> [frame,frame,...]

Frames that hold something navy-ish or hide part of the visor (the open head, the microphone) can measure
wrong: check those by eye.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw


def visor(im):
    """(width, height) of the biggest navy patch"""
    a = np.asarray(im.convert("RGBA")).astype(int)
    navy = (a[..., :3].max(axis=2) < 110) & (a[..., 2] - a[..., 0] > 20) & (a[..., 3] > 128)
    m = Image.fromarray(navy.astype(np.uint8) * 255).copy()
    best = (0, 0, 0)
    while True:
        ys, xs = np.nonzero(np.asarray(m) == 255)
        if not len(ys):
            return best[1], best[2]
        ImageDraw.floodfill(m, (int(xs[0]), int(ys[0])), 100, thresh=0)
        part = np.asarray(m) == 100
        if part.sum() > best[0]:
            py, px = np.nonzero(part)
            best = (part.sum(), int(px.max() - px.min() + 1), int(py.max() - py.min() + 1))
        m.paste(0, mask=Image.fromarray(part.astype(np.uint8) * 255))


pack = sys.argv[1]
frames = [int(n) for n in sys.argv[2].split(",")] if len(sys.argv) > 2 else range(1, 101)
ref = visor(Image.open(f"{pack}/shime60.png"))[0]
print(f"frame 60 (standing still): visor {ref} px wide")
for n in frames:
    try:
        w, h = visor(Image.open(f"{pack}/shime{n}.png"))
    except FileNotFoundError:
        continue
    r = w / ref
    print(f"{n:3}  {w:3}x{h:3}  {r:4.2f}  {'bigger' if r > 1.05 else 'smaller' if r < 0.95 else ''}")
