"""robo.png -> robo-cutout.png: removes the magenta background and the glow (everything not dark
that can be reached from the edge; the dark outline is closed), cropped to the robot.

    cutout.py robo.png robo-cutout.png
"""
import sys
from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB")
w, h = im.size
px = im.load()
mask = Image.new("L", im.size)
m = mask.load()
for y in range(h):
    for x in range(w):
        r, g, b = px[x, y]
        m[x, y] = 0 if max(r, g, b) < 110 else 255   # 0: the dark outline (or a dark area)
for c in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]:
    ImageDraw.floodfill(mask, c, 128, thresh=0)
rgba = im.convert("RGBA")
a = rgba.load()
for y in range(h):
    for x in range(w):
        if m[x, y] == 128:
            a[x, y] = (0, 0, 0, 0)
bbox = rgba.getbbox()
print("bbox", bbox)
rgba.crop(bbox).save(out)
