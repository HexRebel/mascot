# Owl

The sources of Owl, one of Mascot's bundled mascots (`prototypes/Shimeji.Owl/`): a small brown owl that hops on
the floor, flies when it hurries and sits on a branch in the screen's side. CC0 (see
`prototypes/Shimeji.Owl/LICENSE.txt`). Made in 2026 with Google Gemini (Nano Banana): sprite sheets from text
prompts on magenta, later ones with the owl's own earlier images as references (`ugle-reference.png`) or as
templates where only the part that moves is redrawn (`skabelon-flyv.png`: the same owl in nine cells, only the
wings redrawn; `skabelon-gren.png` likewise on its branch). A template with the body locked worked far better
than describing it.

The big source images (93 MB) are not in git: download `owl-sources.zip` from the
[releases](https://github.com/HexRebel/mascot/releases) and unpack it here. The scripts are in git.

| | |
|---|---|
| `owl0.png` | 3×3; row 1 column 1: standing still (1, 60, sitting); row 1 column 2: whistling, side-eye (73, `Whistle`, now and then); row 2 column 1: startled, wings out (held up, 5–10, 90) |
| `owl-front.png` | Like Robo's `front.png`: looking straight ahead, standing still and sitting (60, 11, 26, 30–33). As tall as owl0 standing, its browns moved to owl0's |
| `owl-perch.png` | Not used any more (its branch was bigger than the others'; 13, landing on its branch, is now owl-branch2.png's plain cell, as 101) |
| `owl-branch2.png` | 6×6: on a branch from the cell's left edge to its right, for its branch in the screen's side: landing there (13) and chatting there (101-120, the `*OnWall` behaviors in patch.py: sitting, talking, an answer waiting, asleep with its head on its chest (36: drawn bigger, so only the owl is made smaller, its branch kept), a satchel for an answer waiting (30), looking up at the sky for the weather (22), the tools; 7, a pilot's cap and goggles, is FullPowerOnWall, 131). The left end is the cut end in the side (anchor at the canvas's left), the other end fades out. One factor for every cell: the sheet draws the same branch in all, so it is the same in every frame (the owls as drawn, a few % apart). Browns moved to owl0's. On the floor it still sleeps with its zzz (47) |
| `owl-gren.png`, `owl-gren2.png` | From Nano Banana (3x3), made from `skabelon-gren.png`: small movements while it just sits on its branch (122, 124-130: looking aside, looking down (126, from `owl-gren3.png`: its tail under the branch cut off: below the branch only what 101 has there, and 101's tail under its wing), head tilted both ways, fluffed, eyes shut and content, a stretch, looking up; drowsy and a foot lifted left out, and no sheet draws it looking the other way), the `Branch*` behaviors in patch.py, picked on a wall (not named `*Wall*`: `--no-climb` turns those off). `FallFromWall` is off: it stays on its branch until you take it down. They draw branch2's branch, so they take branch2's factor. Of `owl-gren3.png` only the looking down (its other beaks are open, as if it talks) |
| `owl-branch.png` | 3×3: not used (its branch is thicker than branch2's). The flower (branch2 32) is not used either: its purple petals are cut out as background |
| `owl6.png` | 3×3, made from `ugle-reference.png`: 3 holding the globe (133, Weather), 1 umbrella (96, Rain), 6 a woolly hat and snow (135, Snow, and 97, Cold),  8 a thermometer (134, Warm), 9 shy, blushing (98, Love: thanks or a compliment; the hearts, 85, not used now). Not used: 2 shading its eyes, 4 scarf, shivering (its teeth: a bird has none), 5 hugging itself, 7 sunglasses and a fan. Each grown by its own head (the sheet draws it at different sizes) |
| `owl-landing.png` | Touching down with a wing out and a puff of dust (18, landing, then standing 19). Grown by its head like the others, turned to look left, its beak where standing still's is |
| `owl-flap3.png` | 3×3 from Nano Banana, made from `skabelon-flyv.png`: the same owl in all nine cells, only the wings redrawn. One flap cycle, all nine cells (61–68, 94, a loop, down quickly and up slower); 1 is also falling (4/22/37), 3 gliding (69, not used yet; it was also landing, 18, until owl-landing.png). Every cell gets cell 1's face (eyes and beak: the beak was open in some, so it seemed to talk), is recoloured to owl0's brown (it was darker and redder), then is taken just as drawn: cut from the same box and scaled by one factor (the head as wide as owl0), nothing measured per cell |
| `skabelon-flyv.png`, `skabelon-gren.png` | The template: cell 3 of owl-flap2.png pasted into nine cells, for Nano Banana to redraw only the wings |
| `owl-flap2.png` | Not used any more (the body changed a little between cells). 3×3 from Nano Banana, one flap cycle with the same calm face and body in every cell: the wing beat is cells 1, 2, 3, 5, 6, 7, 8, 9 (61–68, a loop, down quickly and up slower); 1 is also falling (4/22/37), 3 gliding (69, not used yet) and landing on its feet (18, then standing 19), 4 (like 2) not used. Grown by the head's width to owl0's size (×1.07), and each cell evened out by its face disc (the cells differ by up to 5 %, and the owl zoomed in and out) and the beak where it is standing still, so it neither changes size nor jumps aside when it takes off |
| `owl-flap.png` | The first try at a wing beat: not used any more (the face changed between cells) |
| `owl-flying.png` | 3×3 flying poses (not a wing beat: one wing is up in all, the body changes): only 9, gliding (66, not used yet) |
| `owl2.png` | 6×6 (cells 341 px, enough for 128 px): 11 pilot's cap and goggles (132, FullPower: the CPU on full power), 8 dizzy (not used: it lands well), 12 drowsy (92), 7 startled, wings out (99, Failed), 9 sitting legs out (21), 14 asleep (47), 35 scroll (48/57, an answer waiting), 13 wave, 4 gem, 22 stones, 6 happy, 25 laurel (EasterEgg), 36 scroll (Todo), 21 pocket watch (Reminder), 27 magnifying glass (Files/Search/Image), 2 wink (93, not used yet). The sheet draws some a few % bigger or smaller (seen 6 Nov): 35, 36, 25, 21 and 27 are grown by their own head (`evened`, 27 by hand, 0.92: its lens is beside the head) |
| `owl3.png` | row 3: graduation cap (79), reading with glasses (77, `Read`), magic wand (91, Shell). Each grown by its own head (`evened`; the wand by hand, 1.05) |
| `owl4.png` | row 3 column 1: head tilted (70, Chatter, grown by its head: it was drawn smaller); row 1 column 1: a wing on its chin (71, Chatter); row 2 column 1: cheering (86, Done) |
| `owl5.png` | row 1: sweating (89, Alarm), –, light bulb (72, Chatter); row 2 column 2: worried (88, Unsure); row 3: glasses and a book (81, System/Machine/Power), –, X eyes (87, not used now) |
| `owl1.png` | row 2 column 3: hearts (85, Love) |
| `scripts/compose.py` | Cuts the cells out by colour and makes `shime<N>.png` and `preview.png`: every frame on one canvas (246×174 now, anchor at its bottom middle), as big as the flying owl, since mascotd drew a frame of another size than the one before it squeezed |
| `scripts/patch.py` | Flying whenever it moves (walk, creep, run, dash, carrying a window, stumbling: never on its feet), Chatter/Snooze/NewMessage, the things it does on the floor and the tool poses |

## Talking

`prompt.md` in `prototypes/Shimeji.Owl/` is its own system prompt (like Robo's), for anyone without a role for
it: a calm, kind owl with a dry sense of humour, now and then its books, scroll, pocket watch, magnifying glass
or umbrella.

## Building it

Needs Python with numpy and Pillow, and Mascot.

```sh
cd art/owl && mkdir -p build && cd build
python3 ../scripts/compose.py .. Owl
rm -rf out && echo 1 | mascot convert -O out --name Owl Owl
python3 ../scripts/patch.py out/Shimeji.Owl.wlshm Owl.wlshm
mascot import -f --no-climb --talk Chatter --sleep Snooze --answered NewMessage Owl.wlshm
cp ../../../prototypes/Shimeji.Owl/prompt.md ~/.local/share/mascot/shimejis/Shimeji.Owl/   # import leaves a pack's prompt.md out
mascot summon Owl
```

To update the bundled one, copy `~/.local/share/mascot/shimejis/Shimeji.Owl/` over `prototypes/Shimeji.Owl/`,
keeping `LICENSE.txt`. `import -f` does not update an owl that is already out: dismiss it and summon a new one.
To swap an image, change its line in `compose.py` (the frame numbers are the comments) and build again.
