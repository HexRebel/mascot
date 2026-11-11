"""The owl sheets in a directory (art/owl) -> <pack>/shime<N>.png (128x128, feet at (64,128)) + preview.png

    compose.py <images> <pack>

Every image is cut out by colour: the magenta background, the purple shadow under the feet and the pink glow
round the flying owls are all much bluer than green with red about as high as blue, which no part of the owl is
(its browns, cream, yellow feet and white eyes all have blue at or below green). All sheets draw the owl at the
same size for their cell, so one scale per cell size keeps it the same size everywhere.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

here, pack = sys.argv[1], sys.argv[2]
os.makedirs(pack, exist_ok=True)
S = 128
STAND_HEIGHT = 104  # the owl standing still, ears to feet, in px


def cell(name, grid, row, col):
    sheet = Image.open(os.path.join(here, name)).convert("RGB")
    w = sheet.width / grid
    inset = round(w * 0.012)  # not the sheet's faint grid lines
    return sheet.crop((round(col * w) + inset, round(row * w) + inset,
                       round((col + 1) * w) - inset, round((row + 1) * w) - inset)), w


def cut(im, crop=True):
    a = np.asarray(im.convert("RGBA")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    background = (b - g > 25) & (r - g > 25) & (abs(r - b) < 90)
    # The outline's edge mixed with the magenta: see-through as far as it is magenta, and its colour taken back
    edge = ~background & (b - g > 8) & (r - g > 8) & (abs(r - b) < 90)
    out = a.copy()
    out[background, 3] = 0
    out[edge, 3] = 160
    out[edge, 2] = np.minimum(b[edge], g[edge] + 8)
    im = Image.fromarray(out.astype(np.uint8))
    return im.crop(im.getbbox()) if crop else im


ORIGINAL = {}


def owl(name, grid, row, col, flip=False, edit=None):
    im, w = cell(name, grid, row, col)
    if edit:
        im = edit(im)
    im = cut(im)
    if flip:  # drawn flying to the right; Mascot expects left and mirrors it going right
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    ORIGINAL[id(im)] = w
    return im


standing = owl("owl0.png", 3, 0, 0)
UNIT = STAND_HEIGHT / standing.height * ORIGINAL[id(standing)]  # px in a frame per cell width


def small(im):
    f = UNIT / ORIGINAL[id(im)]
    return im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.LANCZOS)


def stand(im, lift=0):
    """Feet on the bottom edge (lifted `lift` px), centred; fitted into the frame if drawn bigger"""
    im = small(im)
    if im.width > S or im.height > S - lift:
        f = min(S / im.width, (S - lift) / im.height)
        im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
    c = Image.new("RGBA", (S, S))
    c.alpha_composite(im, ((S - im.width) // 2, S - im.height - lift))
    return c


def dangle(im, angle=0):
    """Held by the top of the head; angle < 0 swings the body left"""
    im = small(im)
    big = Image.new("RGBA", (S * 3, S * 3))
    px, py = S * 3 // 2, S
    big.alpha_composite(im, (px - im.width // 2, py))
    big = big.rotate(angle, resample=Image.BICUBIC, center=(px, py))
    return big.crop((px - S // 2, py - 3, px + S // 2, py - 3 + S))


def beak(im):
    """Where the beak is (the yellow well above the lowest yellow, the feet), in im's own px"""
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # Yellow to orange, and solid: the outline's edge (alpha 160, see cut()) turns orange-ish where its magenta is taken
    # out, and along a lowered wing it pulled the beak 15 px down (6 Nov)
    ys, xs = np.nonzero((a[..., 3] == 255) & (r > 180) & (b < 100) & (r - b > 100))
    up = ys < ys.max() - im.height * 0.15  # well above the feet (raised wings make the image tall)
    return xs[up].mean(), ys[up].mean()


def head_width(im):
    """How wide the head is, a little above the beak (the run of owl through the beak's column): the size of the owl.
    Measure an image with no wing beside the head there"""
    a = np.asarray(im)[..., 3] > 60
    bx, by = (round(v) for v in beak(im))
    top = np.nonzero(a[:, bx])[0].min()
    row = a[by - round((by - top) * 0.37)]
    left = right = bx
    while left > 0 and row[left - 1]:
        left -= 1
    while right < len(row) - 1 and row[right + 1]:
        right += 1
    return right - left + 1


def background(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (b - g > 25) & (r - g > 25) & (abs(r - b) < 90)


# owl-flap3.png's face (eyes and beak), in a cell's own px (see cell()): Nano Banana drew the beak open in some cells
# and shut in others, and the owl seemed to talk as it flew (the user, 6 Nov)
FACE = (440, 338, 95, 75)  # middle x, y; half width, height


def one_face(cells):
    """Every cell gets the first cell's face. The template put the owl in the same place in all nine, and the face is
    there to the pixel (searched ±10 px: 0 in all), so it goes in where it is; only over the owl (a wing beside the
    head stays)"""
    x, y, rx, ry = FACE
    mask = Image.new("L", cells[0].size)
    ImageDraw.Draw(mask).ellipse((x - rx, y - ry, x + rx, y + ry), fill=255)
    mask = np.asarray(mask.filter(ImageFilter.GaussianBlur(4))).astype(float)
    face = np.asarray(cells[0]).astype(int)
    out = []
    for im in cells:
        a = np.asarray(im).astype(int)
        h, w = min(a.shape[0], face.shape[0]), min(a.shape[1], face.shape[1])
        m = mask[:h, :w] * ~(background(a[:h, :w]) | background(face[:h, :w])) / 255
        a = a.copy()
        a[:h, :w] = np.rint(face[:h, :w] * m[..., None] + a[:h, :w] * (1 - m[..., None]))
        out.append(Image.fromarray(a.astype(np.uint8)))
    return out


def tones(im):
    """Its outline, brown and cream, each the mean colour of its own px (alpha 255)"""
    a = np.asarray(im).astype(float)
    solid = a[..., 3] == 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = (r + g + b) / 3
    parts = (solid & (lum < 60),
             solid & (r > g) & (g > b) & (lum > 60) & (lum < 150) & (r - b > 25) & (g > r * 0.55),  # (not a red scarf)
             solid & (lum > 170) & (r - b < 80))
    return [a[part][:, :3].mean(0) for part in parts]


def recolour(ims, like):
    """owl-flap3.png is a darker, redder brown than the other sheets (brown 142/97/80 against 153/106/74; the user, 6
    Nov): each channel moved by a curve through the three tones of the first cell to those of `like`"""
    have, want = tones(ims[0]), tones(like)
    out = []
    for im in ims:
        a = np.asarray(im).astype(float)
        for ch in range(3):
            xs = [0] + [t[ch] for t in have] + [255]
            ys = [0] + [t[ch] for t in want] + [255]
            a[..., ch] = np.interp(a[..., ch], xs, ys)
        out.append(Image.fromarray(np.rint(a).astype(np.uint8)))
    return out


def as_drawn(name, cells, lift, grow):
    """A sheet whose cells draw the owl in the same place (owl-flap3.png, made from a template): each cell kept just
    as it is, cut out of the same box and scaled by the same factor, so nothing is measured per cell and only what
    the sheet draws moves. The beak (all cells' mean) as far left of the middle as
    standing still once turned (see FACING_RIGHT)"""
    ims = []
    drawn = [cell(name, 3, (n - 1) // 3, (n - 1) % 3) for n in cells]
    for im, w in zip(one_face([im for im, _ in drawn]), (w for _, w in drawn)):
        im = cut(im, crop=False).transpose(Image.Transpose.FLIP_LEFT_RIGHT)  # drawn flying right (see owl())
        f = UNIT / w * grow
        ims.append(im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS))
    ims = recolour(ims, standing)
    boxes = [im.getbbox() for im in ims]
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    ims = [im.crop(box) for im in ims]
    # (5, the wings wrapped round the feet: no beak found, as beak() looks above the feet; the others agree to 2 px)
    # (the beak left of the middle: the floor images are turned to face left, see FACING_RIGHT; it beats its wings
    # where it stood)
    bx = float(np.nanmean([beak(im)[0] for im in ims])) + BEAK_RIGHT
    half = int(np.ceil(max(bx, ims[0].width - bx))) + 1
    out = []
    for im in ims:
        c = Image.new("RGBA", (2 * half, im.height + lift))
        c.alpha_composite(im, (round(half - bx), 0))
        out.append(c)
    return out


owl2 = {n: owl("owl2.png", 6, (n - 1) // 6, (n - 1) % 6) for n in
        (2, 4, 6, 7, 8, 9, 11, 12, 13, 14, 21, 22, 25, 27, 35, 36)}
whistle = owl("owl0.png", 3, 0, 1)
startled = owl("owl0.png", 3, 1, 0)
tilt = owl("owl4.png", 3, 2, 0)
chin = owl("owl4.png", 3, 0, 0)
cheer = owl("owl4.png", 3, 1, 0)
bulb = owl("owl5.png", 3, 0, 2)
sweat = owl("owl5.png", 3, 0, 0)
worried = owl("owl5.png", 3, 1, 1)
glasses = owl("owl5.png", 3, 2, 0)
knocked = owl("owl5.png", 3, 2, 2)
hearts = owl("owl1.png", 3, 1, 2)
cap = owl("owl3.png", 3, 2, 0)
book = owl("owl3.png", 3, 2, 1)
wand = owl("owl3.png", 3, 2, 2)
# Flying: owl-flap3.png (the user's, 6 Nov, "lastowl.png" from Nano Banana, made from skabelon-flyv.png: the same
# owl pasted into all nine cells, and only the wings redrawn). Taken just as drawn (see as_drawn()): the beak stays
# within 3 px and the feet within 5 px in all nine cells (of 682). One flap cycle, a loop: 1 (wings up), 2, 3 (level),
# 4, 5 (down, wrapped round the body), 6, 7 (level), 8, 9 (nearly up again). 3 also glides
FLAP_CELLS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
flap = [owl("owl-flap3.png", 3, (n - 1) // 3, (n - 1) % 3, flip=True) for n in FLAP_CELLS]

SMALL_STANDING = small(standing)
BEAK_RIGHT = beak(SMALL_STANDING)[0] - SMALL_STANDING.width / 2  # the beak, right of the middle, standing still
still = stand(standing)
hop = [still, stand(standing, 5), stand(standing, 10)]
# The wing beat (61-68 and 94, the cells in FLAP_CELLS' order; patch.py loops them), in the air; falling (4, 22, 37): wings
# up, its feet on the canvas's bottom; the glide (69)
# The flying sheet draws the owl another size than owl0.png: one factor for the whole sheet, so its head is as
# wide as standing still, from the wings-down cell (5: no wing beside the head)
FLY_GROW = head_width(SMALL_STANDING) / head_width(small(flap[FLAP_CELLS.index(5)]))
air = as_drawn("owl-flap3.png", FLAP_CELLS, 14, FLY_GROW)
falling = as_drawn("owl-flap3.png", (1,), 0, FLY_GROW)[0]
gliding = air[FLAP_CELLS.index(3)]
print("flying grown", round(FLY_GROW, 3))
def placed(im, grow):
    """A pose drawn another size than owl0 (its own sheet), grown by `grow` and not fitted into 128 (an umbrella, a
    branch): the beak as far right of the middle as standing still, so it does not jump aside"""
    f = UNIT / ORIGINAL[id(im)] * grow  # one resize from the sheet (twice, it was blurry)
    im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    bx = beak(im)[0] - BEAK_RIGHT
    half = int(np.ceil(max(bx, im.width - bx))) + 1
    out = Image.new("RGBA", (2 * half, im.height))
    out.alpha_composite(im, (round(half - bx), 0))
    return out


def grown(im):
    """How much to grow a sheet's owl to owl0's size: by the head's width (an image with no wing beside its head)"""
    return head_width(SMALL_STANDING) / head_width(small(im))



def evened(im, grow=None, lift=0):
    """A pose its sheet drew a few % bigger or smaller than the others (the user, 6 Nov: "lidt forskellige
    størrelser"): grown by its own head like owl6's, or by `grow` where a prop beside the head (a magnifying
    glass, a wand) makes the head look wider than it is; lifted `lift` px"""
    im = placed(im, grow or grown(im))
    if lift:
        c = Image.new("RGBA", (im.width, im.height + lift))
        c.alpha_composite(im, (0, 0))
        im = c
    return im


def landed():
    """owl-landing.png, the user's "landingowl.png" (6 Nov): touching down, a wing out and a puff of dust (it was
    the flying sheet's cell 3). One owl on the sheet: browns moved to owl0's, grown by its head like the others,
    turned to look left like the floor images (so not in FACING_RIGHT). Its beak comes out where standing still's
    is (both 11 px left of the middle), so it does not jump aside when it stands up"""
    im = owl("owl-landing.png", 1, 0, 0)
    w = ORIGINAL[id(im)]
    im = recolour([im], standing)[0]
    ORIGINAL[id(im)] = w
    return placed(im, grown(im)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)


landing = landed()

# owl-branch2.png (6x6), the user's "branch2.png" (6 Nov; owl-branch.png, 3x3, draws a thicker branch: not used): on a branch
# running from the cell's left edge to its right, for chatting, sleeping and the tools while it sits on its branch
# in the screen's side (the *OnWall behaviors, see patch.py). Like 13: the branch's left end is the cut end, in the
# side (the anchor, the canvas's left edge), mirrored on the right side. One factor per sheet, from its plain cell
# (the head as wide as owl0's), browns moved to owl0's, one resize from the sheet; the branch's other end, cut off
# by the cell, fades out
def branch_sheet(name, grid, plain, grow=None):
    def take(n, edit=None):
        im = recolour([owl(name, grid, (n - 1) // grid, (n - 1) % grid, edit=edit)], standing)[0]
        ORIGINAL[id(im)] = 2048 / grid  # the cell's width (recolour() made a new image)
        return im
    # (grow: another sheet's, for a sheet that draws the same branch, so it comes out the same size)
    grow = grow or grown(take(plain))
    def on_branch(n, edit=None):
        # One factor for every cell: the sheet draws the same branch in all of them, so it is the same in every
        # frame (the user, 6 Nov; evened out by the owl, each branch came out a little different)
        im = take(n, edit)
        f = UNIT / ORIGINAL[id(im)] * grow
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
        a = np.asarray(im).copy()
        fade = max(4, im.width // 12)
        a[:, -fade:, 3] = (a[:, -fade:, 3] * np.linspace(1, 0, fade)[None, :]).astype(np.uint8)
        return Image.fromarray(a)
    on_branch.grow = grow
    return on_branch


branch2 = branch_sheet("owl-branch2.png", 6, 1)
# owl-gren.png and owl-gren2.png (3x3), the user's "gren.png" and "gren2.png" from Nano Banana (6 Nov), made from
# skabelon-gren.png (branch2's plain cell nine times): small movements while it just sits on its branch. They draw
# branch2's branch at twice its size, so they take branch2's factor and the branch is the same
gren = branch_sheet("owl-gren.png", 3, 1, branch2.grow)
gren2 = branch_sheet("owl-gren2.png", 3, 1, branch2.grow)
gren3 = branch_sheet("owl-gren3.png", 3, 1, branch2.grow)


def branch_like(im, like):
    """im with nothing under its branch but what like has there: below the branch's bottom edge, every pixel like's.
    gren3.png's looking down draws its tail hanging under the branch, which no other frame has (its branch is the
    same to a px, and its toes over the branch stay as drawn)"""
    w, h = max(im.width, like.width), max(im.height, like.height)
    def padded(i):  # (both on the canvas at its bottom left, see the paste below)
        c = Image.new("RGBA", (w, h))
        c.alpha_composite(i, (0, h - i.height))
        return np.asarray(c)
    a, b = padded(im).copy(), padded(like)
    solid = b[..., 3] > 60
    # The branch's bottom edge where only the branch is (its lowest run, thin), drawn straight on under the owl:
    # where the owl stands on it the run goes up to its head (6 Nov: its top edge there took 101's owl, too)
    xs, tops = [], []
    for x in range(a.shape[1]):
        rows = np.nonzero(solid[:, x])[0]
        if not len(rows):
            continue
        runs = np.split(rows, np.nonzero(np.diff(rows) > 1)[0] + 1)
        if len(runs[-1]) < h // 6:
            xs.append(x)
            tops.append(runs[-1][-1])
    for x in range(a.shape[1]):
        if x < xs[0] or x > xs[-1] or not solid[:, x].any():
            continue
        top = round(np.interp(x, xs, tops)) + 1
        a[top:, x] = b[top:, x]
    return Image.fromarray(a)


def smaller_on_branch(im, f):
    """The owl on im's branch f times as big, its branch as it is (the same in every frame): the owl is what stands
    up from the branch's top edge (the edge drawn straight from where it leaves the cell's left side to the right, the
    owl's own part joined to the middle of it, not the twig), shrunk towards where it sits on the branch"""
    a = np.asarray(im).copy()
    seen = a[..., 3] > 60
    h, w = seen.shape
    def top_at(x):  # the branch's top edge in column x (its lowest run of owl)
        rows = np.nonzero(seen[:, x])[0]
        runs = np.split(rows, np.nonzero(np.diff(rows) > 1)[0] + 1)
        return runs[-1][0]
    x0, x1 = 3, w - w // 12 - 2  # inside the faded end
    y0, y1 = top_at(x0), top_at(x1)
    edge = np.round(y0 + (y1 - y0) * (np.arange(w) - x0) / (x1 - x0)).astype(int)
    above = seen & (np.arange(h)[:, None] < edge[None, :] - 1)
    # The owl: what of it is joined to the middle (a twig at the branch's end is not)
    owl_ = np.zeros_like(above)
    cx = w // 2
    owl_[np.nonzero(above[:, cx])[0], cx] = True
    while True:
        grown_ = owl_.copy()
        grown_[1:] |= owl_[:-1]; grown_[:-1] |= owl_[1:]; grown_[:, 1:] |= owl_[:, :-1]; grown_[:, :-1] |= owl_[:, 1:]
        grown_ &= above
        if (grown_ == owl_).all():
            break
        owl_ = grown_
    # and its soft edge (alpha 60 or less), else a faint ring of the old outline stayed
    soft = (a[..., 3] > 0) & (np.arange(h)[:, None] < edge[None, :] - 1)
    for _ in range(10):
        grown_ = owl_.copy()
        grown_[1:] |= owl_[:-1]; grown_[:-1] |= owl_[1:]; grown_[:, 1:] |= owl_[:, :-1]; grown_[:, :-1] |= owl_[:, 1:]
        owl_ = grown_ & soft
    xs = np.nonzero(owl_.any(0))[0]
    sit_x = (xs.min() + xs.max()) / 2
    sit_y = edge[int(sit_x)]
    layer = np.zeros_like(a)
    layer[owl_] = a[owl_]
    a[owl_] = 0
    small_ = Image.fromarray(layer).resize((round(w * f), round(h * f)), Image.LANCZOS)
    out = Image.fromarray(a)
    out.alpha_composite(small_, (round(sit_x - sit_x * f), round(sit_y - sit_y * f)))
    # A faint dotted ring round the sheet's owl (cell 36's, not the others'): faint pixels over the branch more than
    # 3 px from the owl go
    b = np.asarray(out).copy()
    solid = b[..., 3] > 150
    near = solid.copy()
    for _ in range(3):
        grown_ = near.copy()
        grown_[1:] |= near[:-1]; grown_[:-1] |= near[1:]; grown_[:, 1:] |= near[:, :-1]; grown_[:, :-1] |= near[:, 1:]
        near = grown_
    b[~near & (np.arange(h)[:, None] < edge[None, :] - 1), 3] = 0
    return Image.fromarray(b)
# owl6.png (the user's "sidste.png", 6 Nov, from ugle-reference.png): the owl drawn another size than owl0, and not
# the same in every cell (the head 68 px under the umbrella, 83 in 9), so each grown by its own head. 1 umbrella
# (Weather), 4 scarf, shivering (Cold), 9 shy, blushing (Love)
sheet6 = {n: recolour([owl("owl6.png", 3, (n - 1) // 3, (n - 1) % 3)], standing)[0] for n in (1, 3, 4, 6, 8, 9)}
for im in sheet6.values():
    ORIGINAL[id(im)] = ORIGINAL[id(standing)]
frames = {
    # Walking is hopping (Walk: 1, 2, 3, 2); running and dashing fly (61-64, see patch.py)
    1: still, 2: hop[1], 3: hop[2],
    4: falling, 22: falling,
    # Held up, by how far the pointer is from its feet: startled, wings out, swinging more the further it is
    # (the user's choice, 6 Nov: the other way round than first built)
    5: dangle(startled, -5), 6: dangle(startled, 5), 7: dangle(startled, -9), 8: dangle(startled, 9),
    9: dangle(startled, -14), 10: dangle(startled, 14), 90: dangle(startled),
    # Sitting looks like standing for an owl
    11: still, 15: still, 16: still, 17: still, 20: still, 26: still, 27: still, 28: still, 29: still,
    30: still, 31: still, 32: still, 33: still, 34: still, 35: hop[1], 36: hop[2], 37: falling,
    # Lying is sitting with its legs out
    # Landing (Bouncing: 18, 19): a bird lands well (the user, 6 Nov: not dizzy like Robo): touching down with a puff
    # of dust (owl-landing.png, see landed()), then standing still
    18: landing, 19: still, 21: stand(owl2[9]),
    47: stand(owl2[14]),        # asleep, zzz
    48: evened(owl2[35]),        # an answer waiting: holding up a scroll
    56: stand(owl2[14]),
    57: evened(owl2[35], lift=3),     # the scroll, lifted: it bobs while it waits
    96: placed(sheet6[1], grown(sheet6[1])),  # umbrella: it rains there (Rain)
    134: placed(sheet6[8], grown(sheet6[8])),  # a thermometer: 25 °C or warmer (Warm; the user, 6 Nov: not the sunglasses, 7)
    135: placed(sheet6[6], grown(sheet6[6])),  # a woolly hat, snowflakes: snow or sleet (Snow)
    133: placed(sheet6[3], grown(sheet6[3])),  # holding the globe (Weather; the user, 6 Nov: not the umbrella)
    97: placed(sheet6[6], grown(sheet6[6])),  # a woolly hat, scarf, snowflakes: 0 °C or colder (Cold; the user, 6 Nov: 4
                                                # shivered with teeth, which a bird has not)
    98: placed(sheet6[9], grown(sheet6[9])),  # shy, blushing (Love: thanks or a compliment)
    60: still,  # standing still (owl-front.png was tried, 6 Nov, and taken out again: the user's choice)
    61: air[0], 62: air[1], 63: air[2], 64: air[3], 65: air[4], 66: air[5], 67: air[6], 68: air[7], 94: air[8],
    69: gliding,                # gliding (not used yet)
    # While it answers: head tilted, a wing on its chin, a light bulb
    70: evened(tilt), 71: stand(chin), 72: stand(bulb),
    # Now and then on the floor
    73: stand(whistle), 74: stand(owl2[13]), 75: stand(owl2[4]), 76: stand(owl2[22]), 77: evened(book),
    79: evened(cap), 80: stand(owl2[6]),
    # For the tools and events (see patch.py)
    78: evened(owl2[25]),   # a laurel wreath: tapped quickly many times
    81: stand(glasses),    # reading with its glasses on: checking the system
    82: evened(owl2[36]),   # reading a scroll: the todo list
    83: evened(owl2[21]),   # a pocket watch: a reminder
    84: evened(owl2[27], 0.92),   # a magnifying glass: files, images, searching
    85: stand(hearts),     # hearts: thanks or a compliment
    86: stand(cheer),      # cheering, wings up: a todo done
    87: stand(knocked),    # X eyes, tongue out: an answer failed
    88: stand(worried),    # worried, a wing on its chin: found nothing to go on
    89: stand(sweat),      # startled, sweating: a reminder is due
    90: dangle(startled),
    91: evened(wand, 1.05),       # a magic wand: your last commands
    92: stand(owl2[12]),   # drowsy: getting sleepy
    100: stand(owl2[8]),   # dizzy, spiral eyes: now and then on the floor (Dizzy, like Happy)
    99: stand(owl2[7]),    # startled, wings out: the answer failed (the user's choice, 6 Nov: not the X eyes, 87)
    93: stand(owl2[2]),    # a wink, whistling (not used yet)
    132: stand(owl2[11]),  # a pilot's cap and goggles: the CPU on full power (FullPower; on its branch 131)
}
for n in (12, 13, 14, 23, 24, 25, 38, 39, 40, 41, 42, 43, 44, 45, 46, 49, 50, 51, 52, 53, 54, 55):
    frames[n] = still  # climbing, pulling up, dividing, all fours: not used
# On its branch in the screen's side (GrabWall, thrown against it): owl-branch2.png's plain cell, as 101 (the user,
# 6 Nov: owl-perch.png's branch, the user's "screenlanding.png", was bigger than the others'). As drawn, the branch's
# cut end on the left: the anchor, mirrored on the right side. On a window's edge it sits as the others do, no branch
frames[13] = branch2(1)
# On its branch (see branch_sheet()): sitting while it chats or stays, talking, an answer waiting, asleep, the tools
frames.update({
    101: branch2(1),    # sitting, looking at you (SitDownOnWall)
    102: branch2(10),   # head tilted (TalkOnWall)
    103: branch2(5),    # laughing (TalkOnWall)
    104: branch2(16),   # a star over its head: an idea (TalkOnWall)
    105: branch2(30),   # a satchel: something for you, an answer waiting (AnsweredOnWall; the user's choice, 6 Nov:
                        # not the scroll, 21)
    106: smaller_on_branch(branch2(36), 73 / 82),  # asleep, its head on its chest (AsleepOnWall, QuietOnWall; the
                        # user's choice, 6 Nov: more natural on a branch than the zzz, 6; on the floor it still sleeps
                        # with its zzz). Drawn bigger than the others (its head 82 px to 73), so the owl is made smaller
    107: branch2(27),   # a pencil: the todo list
    108: branch2(19),   # a pocket watch: a reminder
    109: branch2(28),   # a magnifying glass: files, images, searching
    110: branch2(22),   # looking up at the sky: the weather (the user's choice, 6 Nov: not the telescope, 33)
    111: branch2(9),    # a nightcap, yawning: getting sleepy
    112: branch2(14),   # glasses: the system
    114: branch2(12),   # eyes shut, smiling: thanks or a compliment (the flower, 32, is purple: cut out as background)
    115: branch2(35),   # wings up: a todo done
    116: branch2(15),   # eyes shut, a wing to its face: the answer failed
    117: branch2(4),    # worried: found nothing to go on
    118: branch2(18),   # startled, beak open: a reminder is due
    119: branch2(24),   # shivering: cold
    120: branch2(16),   # the star: magic, your last commands
    # Sitting on its branch, now and then a small movement (the Branch* behaviors in patch.py)
    122: gren(3),       # looking aside (every sheet draws it looking the same way: no other way; drowsy, 2, and
                        # a foot lifted, 6, not used, the user, 6 Nov)
    124: gren(5),       # head tilted one way
    125: gren2(5),      # head tilted the other way
    126: branch_like(gren3(6), branch2(1)),  # looking down (owl-gren3.png, the user's "gren3.png"; its tail under
                        # the branch cut off. Its eyes are drawn unlike each other: the user chose it all the same,
                        # 6 Nov, over plain 101 with its eyes moved down)
    127: gren(7),       # fluffed up
    128: gren2(7),      # eyes shut, smiling, content
    129: gren(8),       # wings out, a stretch
    130: gren(9),       # looking up
    131: branch2(7),    # a pilot's cap and goggles: the CPU on full power (FullPowerOnWall; the user, 6 Nov)
})

# Every frame on one canvas, as big as the biggest (the flying ones are wider than 128): mascotd drew a frame of
# another size than the one before it squeezed (6 Nov: the falling owl, 160 px wide, drawn 128 wide). Each keeps its
# anchor, its bottom middle, at the canvas's bottom middle (patch.py sets the anchors from the size)
# Mascot shows an image as it is looking left and mirrors it looking right. The flying owl looks left (owl-flap3.png
# turned, see as_drawn()), but the sheets draw it on the floor looking right: thrown to the right it flew and landed
# looking right and then stood looking left (the user, 6 Nov). So every floor image is turned to look left, but the
# zzz (47, 56: readable, never mirrored) and held up (5-10, 90: the swing the user chose)
FACING_RIGHT = set(frames) - {13} - set(range(101, 132)) - {4, 22, 37, 18, 61, 62, 63, 64, 65, 66, 67, 68, 94, 69} - {47, 56} - {5, 6, 7, 8, 9, 10, 90}
for n in FACING_RIGHT:
    frames[n] = frames[n].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
CW = max(im.width for im in frames.values()) + 1 & ~1
CH = max(im.height for im in frames.values())
for n, im in frames.items():
    c = Image.new("RGBA", (CW, CH))
    # (13: the branch's cut end on the canvas's left edge, its anchor)
    c.alpha_composite(im, (0 if n == 13 or 101 <= n <= 131 else CW // 2 - im.width // 2, CH - im.height))
    frames[n] = c
# 126 (gren3.png's looking down) with the tail of the others: 101's, under its wing to the left of its feet, where
# gren3.png draws only a round stub (the user, 6 Nov). Its own belly and feet stay
a, b = np.asarray(frames[126]).copy(), np.asarray(frames[101])
mean = a[..., :3].astype(int).mean(-1)
own = ((mean > 165) | ((a[..., 0] > 200) & (a[..., 1] > 140) & (a[..., 2] < 90))) & (a[..., 3] > 200)  # belly, feet
tail = np.zeros(own.shape, bool)
tail[CH - 24:CH - 16, 10:52] = True
a[tail & ~own] = b[tail & ~own]
frames[126] = Image.fromarray(a)
print("canvas", CW, CH)
S = max(CW, CH)  # (the preview's cells)
preview = Image.new("RGBA", (S * 8, S * ((len(frames) + 7) // 8)), (60, 60, 70, 255))
d = ImageDraw.Draw(preview)
for i, n in enumerate(sorted(frames)):
    im = frames[n]
    im.save(f"{pack}/shime{n}.png")
    x, y = (i % 8) * S, (i // 8) * S
    preview.alpha_composite(im, (x + (S - CW) // 2, y + S - CH))
    d.rectangle((x, y, x + S - 1, y + S - 1), outline=(100, 100, 120))
    d.text((x + 3, y + 2), str(n), fill=(255, 255, 0))
preview.save(os.path.join(os.path.dirname(os.path.abspath(pack)), "preview.png"))
print("frames", len(frames))
