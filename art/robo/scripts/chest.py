"""Swaps the cyan square on Robo's chest for a symbol: "bubble" (a speech bubble, the official one) or
"arch" (the Arch Linux logo, only for your own install: it is Arch's trademark). "square" keeps it.

The square is the lowest big, square-ish cyan patch: it is painted over with the body's color around it,
and the symbol is drawn there in the same cyan with a dark outline, from the Symbols Nerd Font."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/TTF/SymbolsNerdFont-Regular.ttf"
GLYPHS = {"bubble": "", "arch": ""}
CYAN, NAVY = (118, 246, 250, 255), (28, 30, 72, 255)


def patches(mask):
    """The connected patches of a boolean mask, as boolean masks"""
    m = Image.fromarray(mask.astype(np.uint8) * 255).copy()
    found = []
    while True:
        ys, xs = np.nonzero(np.asarray(m) == 255)
        if not len(ys):
            return found
        ImageDraw.floodfill(m, (int(xs[0]), int(ys[0])), 100, thresh=0)
        part = np.asarray(m) == 100
        found.append(part)
        m.paste(0, mask=Image.fromarray(part.astype(np.uint8) * 255))


def square(a):
    """The chest square of an RGBA array, or None (covered by an arm, the chest open...)"""
    r, g, b, al = (a[..., i].astype(int) for i in range(4))
    cyan = (g > 190) & (b > 190) & (r < 190) & (al > 128)
    h = a.shape[0]
    best = None
    for p in patches(cyan):
        ys, xs = np.nonzero(p)
        bh, bw = np.ptp(ys) + 1, np.ptp(xs) + 1
        if p.sum() < h * h * 0.002 or not 0.6 < bw / bh < 4 or p.sum() / (bw * bh) < 0.6:
            continue  # small (glints, particles) or not a filled square; flattened when it has landed
        if ys.mean() < h * 0.45:
            continue  # the eyes and the visor are in the upper half
        # On the body, not on the visor (an open mouth): light all around it
        around = np.asarray(Image.fromarray(p.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * max(3, bh // 2) + 1))) > 0
        around &= ~p & (al > 128)
        if around.any() and np.median(a[around][:, :3].min(axis=1)) < 120:
            continue
        if best is None or ys.mean() > best[0]:
            best = (ys.mean(), p)
    return None if best is None else best[1]


def rechest(im, kind):
    if kind == "square":
        return im
    a = np.asarray(im.convert("RGBA")).copy()
    p = square(a)
    if p is None:
        return im
    ys, xs = np.nonzero(p)
    size = max(np.ptp(ys), np.ptp(xs)) + 1
    # The square with its dark outline: grow it until the outline is covered
    grown = Image.fromarray(p.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * round(size * 0.2) + 1))
    cover = np.asarray(grown) > 0
    ring = np.asarray(grown.filter(ImageFilter.MaxFilter(2 * round(size * 0.12) + 1))) > 0
    ring &= ~cover & (a[..., 3] > 200) & (a[..., :3].min(axis=2) > 150)  # the body's light colour around it
    body = np.median(a[ring][:, :3], axis=0).astype(np.uint8) if ring.any() else np.array([225, 222, 245], np.uint8)
    a[cover & (a[..., 3] > 0), :3] = body
    out = Image.fromarray(a)
    # The symbol a little bigger than the square was, centred where it was, and squashed like it
    # (flat when it has landed)
    font = ImageFont.truetype(FONT, 400)
    glyph = GLYPHS[kind]
    stroke = 30
    sym = Image.new("RGBA", (520, 520))
    d = ImageDraw.Draw(sym)
    l, t, rgt, btm = d.textbbox((0, 0), glyph, font=font, stroke_width=stroke)
    d.text((260 - (l + rgt) / 2, 260 - (t + btm) / 2), glyph, font=font, fill=CYAN,
           stroke_width=stroke, stroke_fill=NAVY)
    sym = sym.crop(sym.getbbox())
    w, h = round((np.ptp(xs) + 1) * 1.4), round((np.ptp(ys) + 1) * 1.4)
    sym = sym.resize((w, h), Image.LANCZOS)
    out.alpha_composite(sym, (round(xs.mean() - w / 2), round(ys.mean() - h / 2)))
    return out
