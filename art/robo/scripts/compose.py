"""complete.png (3x3 sheet) -> <pack>/shime1..94.png (128x128, base at (64,128)) + preview.png

    compose.py complete.png <pack> [bubble|arch|square]   (the chest symbol, see chest.py; bubble by default)

Cells: 1 glide (drawn facing right) · 2 dangle left · 3 dangle right · 4 fall · 5 landed · 6 rest · 7 talk · 8 asleep · 9 NEW
Next to it: robo-cutout.png (looking straight ahead) and experimental.png (3x3; row 2: hologram,
thinking, tinkering; row 3: notepad, -, opening its chest) and experimental3.png (3x3: pondering, nervous,
cheering; grumpy, gears, singing; giggling, globe, meditating), and a few of experimental5.png and
experimental6.png, the "?" of experimental7.png and a few of experimental8.png and experimental9.png (4x4)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from chest import rechest

sheet_path, pack = sys.argv[1], sys.argv[2]
CHEST = sys.argv[3] if len(sys.argv) > 3 else "bubble"  # what is on its chest, see chest.py
os.makedirs(pack, exist_ok=True)
S = 128
TALLEST = 112  # the tallest cell gets this height; every cell uses the same scale


def cut(cell):
    """Background, shadows and glow: everything not dark that can be reached from the edge.
    The dark outline is closed, so the inside stays. Loose cyan parts (the "z") stay too,
    and come back as their own image."""
    rgb = np.asarray(cell.convert("RGB")).astype(int)
    # A light frame around the cell, so the fill gets all the way round even if a corner is dark
    # White body counts as a wall too: something see-through (the hologram cube) breaks the outline
    wall = (rgb.max(axis=2) < 110) | (rgb.min(axis=2) > 200)
    mask = Image.fromarray(np.pad(np.where(wall, 0, 255), 1, constant_values=255).astype(np.uint8)).copy()
    ImageDraw.floodfill(mask, (0, 0), 128, thresh=0)
    outside = np.asarray(mask)[1:-1, 1:-1] == 128
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cyan = (g > 180) & (b > 180) & (r < 150)
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255)]).astype(np.uint8)
    body, loose = rgba.copy(), rgba.copy()
    body[outside] = 0
    # Not the cyan glow under the base: only loose parts above its lowest fifth
    ys = np.nonzero(body[..., 3])[0]
    low = ys.max() - (ys.max() - ys.min()) // 5
    keep = outside & cyan
    keep[low:] = False
    loose[~keep] = 0
    return Image.fromarray(body), Image.fromarray(loose)


def cutout(im):
    body, loose = cut(im)
    whole = Image.alpha_composite(body, loose)
    return whole.crop(whole.getbbox())


def cutout_key(im):
    """For a see-through thing that breaks the outline (the hologram cube), where the fill would
    run into the body: remove the magenta by color instead, then the purple (magenta mixed with
    cyan) inside the cube and in the glow, and everything below the dark base"""
    im = im.crop((8, 8, im.width - 8, im.height - 8))  # not the sheet's faint grid lines
    a = np.asarray(im.convert("RGBA")).copy()
    r, g, b = (a[..., i].astype(int) for i in range(3))
    gone = (g < 140) & (r > 150) & (b > 150)
    purple = ((r - g > 30) & (b > 180)) | ((b - g > 60) & (r > 110))
    h = a.shape[0]
    ys, xs = np.nonzero((g > 200) & (b > 200) & (r < 170))
    low = ys > h * 0.4  # the cube's edges, not the eyes
    cube = np.zeros_like(gone)
    cube[ys[low].min():ys[low].max() + 1, xs[low].min():xs[low].max() + 1] = True
    dark = np.nonzero((np.maximum(np.maximum(r, g), b) < 110).any(axis=1))[0]
    base = np.zeros_like(gone)
    base[dark.max() - h // 8:] = True
    gone |= purple & base
    gone[dark.max() + 1:] = True
    # Inside the cube the magenta shows through as purple (much more blue than green, unlike the
    # lavender body): give it the cube's own cyan, as where it is in front of the body
    tint = cube & ~gone & (b - g > 60) & (np.maximum(np.maximum(r, g), b) > 110)
    a[tint] = (130, 204, 236, 210)
    a[gone] = 0
    out = Image.fromarray(a)
    return out.crop(out.getbbox())


def visor(im):
    """Width of the visor: the biggest navy patch (not grey: a microphone, an open head). Every
    image has the same visor, so this tells how big Gemini drew the robot"""
    a = np.asarray(im.convert("RGBA")).astype(int)
    r, b = a[..., 0], a[..., 2]
    navy = (a[..., :3].max(axis=2) < 110) & (b - r > 20) & (a[..., 3] > 128)
    # Without the thin outlines, which can join the visor to the head's outline
    k = 2 * max(1, a.shape[0] // 160) + 1
    m = Image.fromarray(navy.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(k)).copy()
    best = (0, 0)
    while True:
        ys, xs = np.nonzero(np.asarray(m) == 255)
        if not len(ys):
            return best[1]
        ImageDraw.floodfill(m, (int(xs[0]), int(ys[0])), 100, thresh=0)
        part = np.asarray(m) == 100
        if part.sum() > best[0]:
            px = np.nonzero(part)[1]
            best = (part.sum(), px.max() - px.min() + 1)
        m.paste(0, mask=Image.fromarray(part.astype(np.uint8) * 255))


sheet = Image.open(sheet_path)
cw = sheet.width // 3
cells, extras = {}, {}
for i in range(9):
    body, loose = cut(sheet.crop(((i % 3) * cw, (i // 3) * cw, (i % 3 + 1) * cw, (i // 3 + 1) * cw)))
    whole = Image.alpha_composite(body, loose)
    box = whole.getbbox()
    cells[i + 1] = rechest(whole.crop(box), CHEST)
    if loose.getbbox():
        extras[i + 1] = (rechest(body.crop(box), CHEST), loose.crop(box))

scale = TALLEST / max(c.height for c in cells.values())


def small(im):
    return im.convert("RGBa").resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)


def stand(n, lift=0, im=None):
    """Base on the bottom edge (lifted `lift` px), centered"""
    im = small(im or cells[n])
    if im.width > S or im.height > S - lift:  # drawn a little bigger (singing): fit it
        f = min(S / im.width, (S - lift) / im.height)
        im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
    c = Image.new("RGBa", (S, S))
    c.paste(im, ((S - im.width) // 2, S - im.height - lift))
    return c


def dangle(n, angle=0, im=None):
    """Held by the top of the head; angle < 0 swings the body left"""
    im = small(im or cells[n])
    big = Image.new("RGBa", (S * 3, S * 3))
    px, py = S * 3 // 2, S
    big.paste(im, (px - im.width // 2, py))
    big = big.rotate(angle, resample=Image.BICUBIC, center=(px, py))
    return big.crop((px - S // 2, py - 3, px + S // 2, py - 3 + S))


def z_up(n, dy):
    """The sleeping robot with its "z" moved up `dy` px: breathing"""
    body, loose = extras[n]
    moved = Image.new("RGBA", body.size)
    moved.paste(loose, (0, -round(dy / scale)))
    return stand(n, im=Image.alpha_composite(body, moved))


# Gemini drew the glide facing right; Mascot expects left and mirrors it when going right
cells[1] = cells[1].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
glide = stand(1)
ref = Image.open(os.path.join(os.path.dirname(sheet_path), "robo-cutout.png")).convert("RGBA")
ref = rechest(ref.crop(ref.getbbox()), CHEST)
VISOR = visor(cells[6])  # the sheet's size: every other image is resized to its visor


def matched(im):
    """A robot from another image, resized to the sheet's size"""
    f = VISOR / visor(im)
    return im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)


# Looking straight ahead: the reference itself
front = stand(0, im=matched(ref))


def bubble_down(im, room):
    """The thinking bubble floats above the head: move it down so the frame is at most `room` px high"""
    a = Image.fromarray((np.asarray(im)[..., 3] > 0).astype(np.uint8) * 255).copy()
    ys, xs = np.nonzero(np.asarray(a))
    top = (int(xs[ys.argmin()]), int(ys.min()))
    ImageDraw.floodfill(a, top, 128, thresh=0)  # the bubble: what hangs together with the top pixel
    part = np.asarray(a) == 128
    arr = np.asarray(im).copy()
    bubble = np.where(part[..., None], arr, 0).astype(np.uint8)
    arr[part] = 0
    rest = Image.fromarray(arr)
    dy = max(0, im.height - room)
    out = Image.new("RGBA", im.size)
    out.alpha_composite(Image.fromarray(bubble), (0, dy))
    out.alpha_composite(rest)
    return out.crop(out.getbbox())


here = os.path.dirname(sheet_path)
extra = Image.open(os.path.join(here, "experimental.png"))
ew = extra.width // 3
fun = {(r, c): (cutout_key if (r, c) == (1, 0) else cutout)(extra.crop((c * ew, r * ew, (c + 1) * ew, (r + 1) * ew)))
       for r, c in [(1, 0), (1, 1), (1, 2), (2, 0), (2, 2)]}
# Before resizing: the soft edges of a resized image would join the bubble to the head
fun[1, 1] = bubble_down(fun[1, 1], round((S - 2) / scale * visor(fun[1, 1]) / VISOR))
# Not the hologram cube or the open chest: they are cyan squares of their own
fun = {k: matched(v if k in ((1, 0), (2, 2)) else rechest(v, CHEST)) for k, v in fun.items()}
# experimental3.png (3x3), for the tools and a few more things
more_sheet = Image.open(os.path.join(here, "experimental3.png"))
mw = more_sheet.width // 3
# The globe's glow runs over the arm's outline, like the cube's: cut by colour
more = {(r, c): matched(rechest((cutout_key if (r, c) == (2, 1) else cutout)(
            more_sheet.crop((c * mw, r * mw, (c + 1) * mw, (r + 1) * mw))), CHEST))
        for r in range(3) for c in range(3)}
# front.png: held up and hanging straight down, looking ahead (held still)
hanging = matched(rechest(cutout(Image.open(os.path.join(here, "front.png"))), CHEST))
# Where measuring the visor fails, by eye: the singing one (drawn bigger, its fit to the frame is not
# enough) and the one with its head open (its hand and the lid hide part of the visor)
def resized(im, f):
    return im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)


more[1, 2] = resized(more[1, 2], 0.96)
more[1, 1] = resized(more[1, 1], 1.12)
hanging = resized(hanging, 1.09)  # front.png: drawn smaller than the sheet (by area, against 1-10: 1.04 was too little)

def unpinked(im):
    """The magenta left in a gap the outline closes in (between a handle and the head): see-through"""
    a = np.asarray(im.convert("RGBA")).copy()
    r, g, b = (a[..., i].astype(int) for i in range(3))
    a[(r > 170) & (b > 170) & (g < 100), 3] = 0
    return Image.fromarray(a)


# experimental5.png and experimental6.png (3x3 each): a few each
def cells_of(name, wanted, top=(), grid=3, left=None):
    """The wanted (row, column) cells of a grid x grid sheet, cut out, chest swapped, resized to the sheet;
    the ones in top have a bubble above the head, moved down (see bubble_down()); left: {cell: share of
    its width} to leave out on the left (what pokes in from the cell next to it)"""
    sheet = Image.open(os.path.join(here, name))
    w = sheet.width // grid
    out = {}
    for r, c in wanted:
        x = c * w + round(w * (left or {}).get((r, c), 0))
        im = rechest(cutout(sheet.crop((x, r * w, (c + 1) * w, (r + 1) * w))), CHEST)
        if (r, c) in top:
            im = bubble_down(im, round((S - 2) / scale * visor(im) / VISOR))
        out[r, c] = matched(im)
    return out


five = cells_of("experimental5.png", [(0, 0), (0, 2), (1, 0), (1, 1), (2, 1), (2, 2)], top=[(0, 0)])
six = cells_of("experimental6.png", [(0, 0), (1, 0), (1, 1), (2, 0), (2, 1)])
seven = cells_of("experimental7.png", [(2, 0)])
eight = cells_of("experimental8.png", [(1, 2), (2, 0), (2, 2)], left={(2, 2): 0.06})  # confetti
nine = cells_of("experimental9.png", [(3, 2)], grid=4)
eight[2, 2] = resized(unpinked(eight[2, 2]), 0.87)  # the graph on its visor: measured by its height (100 px, like 60)
still = stand(0, im=hanging)  # front.png: standing still and sitting
frames = {
    # Hovering: the same pose bobbing up and down (Walk/Run/Dash use 1, 2, 3, 2)
    1: glide, 2: stand(1, 2), 3: stand(1, 4),
    4: stand(4),
    # Held up, by how far the pointer is from its feet (Pinched): straight down (front.png, 90) only right
    # under the pointer; 5/6 a little: the swing, turned back towards upright (a small swing); 7/8 further:
    # the swing; 9/10 far: the swing, tilted more
    5: dangle(2, 5), 6: dangle(3, -5), 7: dangle(2), 8: dangle(3),
    9: dangle(2, -6), 10: dangle(3, 6),
    # Sitting (also while it chats) looks straight ahead, like standing still (front.png); the sleepy rest only
    # when lying (21) or getting up (19)
    11: still, 15: stand(7), 16: glide, 17: stand(7),
    # Dizzy only right after landing (Bouncing: 18, 19); lying (21) rests, creeping (20) glides
    18: stand(5), 19: stand(6), 20: glide, 21: stand(6), 22: stand(4),
    26: still, 27: stand(7), 28: glide, 29: stand(7),
    30: still, 31: still, 32: still, 33: still,
    34: glide, 35: stand(1, 2), 36: stand(1, 4), 37: stand(4),
    47: stand(8),       # asleep
    48: stand(9),       # NEW
    56: z_up(8, 4),     # asleep, the "z" a little higher
    57: stand(9, 3),    # NEW, lifted: it bobs while it waits
    58: stand(7),       # talking, mouth open (unused)
    59: stand(7, 2),    # talking, lifted (unused)
    60: still,          # standing still: front.png, looking straight ahead
    # Chatter: thinking, bobbing 2 px, while it answers
    63: stand(0, im=fun[1, 1]), 68: stand(0, 2, fun[1, 1]),
    # Things it does now and then on the floor
    64: stand(0, im=fun[1, 0]),  # hologram cube
    65: stand(0, im=fun[1, 2]),  # tinkering
    66: stand(0, im=fun[2, 0]),  # notepad
    67: stand(0, im=fun[2, 2]),  # opening its chest
    # While a tool runs (see patch.py) and a few more
    69: stand(0, im=more[2, 1]),  # holding the globe: the weather
    70: stand(0, im=more[0, 0]),  # pondering: searching a file
    71: stand(0, im=more[1, 1]),  # its head open, gears turning: your last commands
    72: stand(0, im=more[2, 2]),  # meditating: getting sleepy
    73: stand(0, im=more[1, 2]),  # singing (not used yet: while music plays, MPRIS)
    74: stand(0, im=more[2, 0]),  # giggling
    75: stand(0, im=more[0, 1]),  # nervous (not used yet: an answer that failed)
    76: stand(0, im=more[0, 2]),  # cheering (not used yet: a todo done)
    77: stand(0, im=more[1, 0]),  # grumpy (not used yet: woken up)
    78: stand(0, im=six[0, 0]),   # the magnifying glass (not used yet: kept for something else)
    79: stand(0, im=five[0, 0]),  # thinking, a light bulb in a bubble (Chatter)
    80: stand(0, im=five[2, 2]),  # saluting: a reminder
    81: stand(0, im=five[2, 1]),  # winking
    82: stand(0, im=five[0, 2]),  # laughing, shaking
    83: stand(0, im=six[1, 0]),   # heart eyes (not used yet: a compliment)
    84: stand(0, im=six[1, 1]),   # shrugging (not used yet: an answer that failed, or it does not know)
    85: stand(0, im=six[2, 1]),   # sweating (not used yet)
    86: stand(0, im=five[1, 1]),  # switched off, grey: Quiet
    87: stand(0, im=five[1, 0]),  # a tear (not used yet: sent away)
    88: stand(0, im=six[2, 0]),   # a yellow "!" bulb: a reminder is due (Alarm)
    89: stand(0, im=seven[2, 0]), # a "?" on the visor, hand on the chin: a system tool found nothing (Unsure)
    91: stand(0, im=eight[2, 0]), # laughing, eyes shut tight ("><"): a todo is done (Done)
    92: stand(0, im=eight[2, 2]), # a magnifying glass over a graph on its visor: checking the machine (Machine)
    93: stand(0, im=eight[1, 2]), # worried, a drop of sweat (not used yet: kept for something else)
    94: stand(0, im=nine[3, 2]),  # "ERROR" on its visor, a tear: an answer failed (Failed)
    90: dangle(0, im=hanging),    # held up and still: hanging straight down (Pinched, Resisting)
}
for n in (12, 13, 14, 23, 24, 25, 38, 39, 40, 41, 42, 43, 44, 45, 46, 49, 50, 51, 52, 53, 54, 55):
    frames[n] = glide  # climbing, pulling up, dividing, all fours: not used

preview = Image.new("RGBA", (S * 8, S * ((len(frames) + 7) // 8)), (60, 60, 70, 255))
d = ImageDraw.Draw(preview)
for i, n in enumerate(sorted(frames)):
    im = frames[n].convert("RGBA")
    im.save(f"{pack}/shime{n}.png")
    x, y = (i % 8) * S, (i // 8) * S
    preview.alpha_composite(im, (x, y))
    d.rectangle((x, y, x + S - 1, y + S - 1), outline=(100, 100, 120))
    d.text((x + 3, y + 2), str(n), fill=(255, 255, 0))
preview.save(f"{pack}/../preview.png")
print("scale", round(scale, 4), "frames", len(frames))
