# How Robo was made

Robo was generated with Google's Nano Banana 2 (Gemini 3.1 Flash Image, `google/gemini-3.1-flash-image`)
through [OpenRouter](https://openrouter.ai/google/gemini-3.1-flash-image) in October 2026, from **text
prompts only**: no image by anyone else was uploaded as a reference. The prompts below are the ones
Robo started from; the author adjusted their wording until the robot looked right, so the exact
final wording is not recorded. After that, each new image was made from Gemini's own
earlier Robo (`robo-cutout.png`) as the reference.

The cyan square Gemini drew on its chest was replaced afterwards by a speech bubble
(`scripts/chest.py`, a glyph from the Symbols Nerd Font), so the bundled Robo has a mark of its own.

## 1. The robot itself (`robo.png`, 1:1)

```
Character design for a 2D desktop pet: a cute, soft, squishy robot that looks like
a mochi rice cake. Chibi proportions. A big, puffy, rounded white head, slightly
wider than tall and a little squashed, like soft dough, with small rounded ear pods
on each side. A large dark navy visor with very rounded corners covers most of the
face. On the visor: two big glowing cyan oval eyes, a small cyan smile, and a soft
pink blush glow under each eye. Almost no neck: the head sits right on a small,
round, pillowy white body with a little glowing cyan square on the chest. Two short,
chubby, rounded nub arms. No legs and no feet: the body ends in a soft rounded dark
navy base with a faint cyan glow underneath, as if it gently hovers.

Very few panel lines, everything rounded and soft. Simple flat colors with one small
glossy highlight on the head, thick clean dark navy outlines, no gradients, no
texture. One single character, full body, facing left in a three-quarter view,
centered with a small margin around it. Background: solid flat magenta (#FF00FF).
No text, no shadow, no floor, no extra objects.
```

Then, in the same conversation:

```
Same robot, exactly the same design, colors, proportions and outlines, with two
changes: remove the pink blush on the cheeks completely (the visor is plain dark
navy around the eyes and smile), and remove the glow under it completely (nothing
below the dark base, just the flat magenta background #FF00FF). Keep everything
else identical.
```

## 2. The poses (`complete.png`, 1:1, with `robo-cutout.png` attached)

```
A sprite sheet for a 2D desktop pet game, based on the attached robot. Use the
attached robot as the exact reference: same design, same colors, same proportions,
same thick dark navy outlines, same glossy highlights. It must look like the same
character in every cell, at the same size.

Layout: a 3 by 3 grid of equal square cells, one pose per cell, 9 poses in total.
Each robot is centered in its cell with clear empty space around it; nothing
touches or crosses the cell borders, and the robots never overlap. The robot has
no legs: it hovers. Its body never changes shape, only its pose, its arms and the
eyes and smile on its visor change. Every outline is fully closed.

Poses, row by row, left to right:
Row 1:
1. Gliding to the left: the whole robot tilted slightly to the left, arms trailing
   a little behind.
2. Picked up by the top of its head and dangling, body swinging to the left, arms
   hanging loose, eyes as surprised round circles.
3. The same dangling pose, body swinging to the right.
Row 2:
4. Falling: arms raised straight up in surprise, eyes as wide round circles.
5. Landed on the ground after a fall: body squashed a little flatter, eyes as dizzy
   spirals.
6. Resting on the ground: its dark round base sits on the bottom of the cell,
   relaxed, eyes half closed.
Row 3:
7. Talking happily: eyes as happy upside-down arcs, the smile open like a small
   mouth, one arm raised a little as if explaining.
8. Asleep on the ground: slumped slightly forward, eyes as two closed lines, a small
   cyan "z" shown on the visor.
9. Waving one arm up high to get attention, eyes as happy arcs.

Background: solid flat magenta (#FF00FF) everywhere, in every cell and between
cells. No grid lines, no cell borders, no text, no labels, no numbers, no glow, no
shadow, no floor, no extra objects. Full body visible in every cell, never cropped.
```

Then, in the same conversation:

```
Keep this sprite sheet exactly as it is, with only these changes:
- Cell 6 (resting) and cell 8 (asleep): the robot has no legs and no feet. Remove
  them completely. It rests directly on its round dark base, like in the other cells.
- Cell 9 (waving): instead of eyes and smile, the visor shows the word "NEW" in
  big, bold, glowing cyan capital letters, filling most of the visor. Still waving.
- Remove all shadows under the robots.
Everything else stays identical: same robots, same poses, same size, same magenta
background.
```

## 3. More poses (`experimental.png`, `experimental3.png`, `experimental5.png`, `experimental6.png`)

More 3×3 sheets in the same way, written by the author, with `robo-cutout.png` as the
reference. Used: row 2 (holding a hologram cube, thinking, tinkering) and row 3, columns 1 and 3
(a notepad, opening its chest) of the first; all of `experimental3.png`; a few of `experimental5.png` and `experimental6.png`. The other cells are not used.

## 4. Hanging straight down (`front.png`, with `robo-cutout.png` attached)

```
Using the attached robot as the exact reference (same design, colors, proportions,
size, thick dark navy outlines and glossy highlights), draw it picked up by the top
of its head and hanging straight down, perfectly still and upright, not swinging:
body vertical, both arms hanging loose and symmetric at its sides. Front view,
looking straight ahead at the viewer, eyes as surprised round circles in the middle
of the visor. No legs and no feet. Full body visible, centered, solid flat magenta
(#FF00FF) background, no glow, no shadow, no floor, no text.
```
