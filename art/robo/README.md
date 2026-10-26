# Robo

The sources of Robo, Mascot's bundled mascot (`prototypes/Shimeji.Robo/`): a small hovering robot
whose visor shows how it feels. CC0 (see `prototypes/Shimeji.Robo/LICENSE.txt`); how it was made is
in [PROMPTS.md](PROMPTS.md).

The big source images (28 MB) are not in git: download `robo-sources.zip` from the
[releases](https://github.com/HexRebel/mascot/releases) and unpack it here. The scripts are in git.

| | |
|---|---|
| `robo.png` | The robot alone, 2048×2048 on magenta |
| `robo-cutout.png` | The same, cut out (`scripts/cutout.py`): the reference for the other images, and Robo standing still |
| `front.png` | Straight, looking ahead: Robo standing still and sitting (60, 11, 26, 30–33) and held still, hanging straight down (90) |
| `complete.png` | 3×3: glide · dangle left · dangle right · fall · landed · rest · talk · asleep · NEW |
| `experimental.png` | 3×3; used: row 2 (hologram, thinking, tinkering), row 3 columns 1 and 3 (notepad, open chest) |
| `experimental3.png` | 3×3: pondering, nervous, cheering · grumpy, gears in its open head, singing · giggling, globe, meditating |
| `experimental5.png`, `experimental6.png` | 3×3 each; a few used (see `scripts/compose.py`, frames 78–88) |
| `experimental7.png` | 3×3; used: row 3 column 1, a "?" on its visor, hand on its chin (89, `Unsure`) |
| `experimental8.png` | 3×3; used: row 3 column 1, laughing with its eyes shut tight, "><" (91, `Done`); row 3 column 3, a magnifying glass over a graph (92, `Machine`); row 2 column 3, worried and sweating (93, not used yet) |
| `experimental9.png` | 4×4; used: row 4 column 3, "ERROR" on its visor and a tear (94, `Failed`); row 4 column 1, "100% FULL POWER" (100, `FullPower`) |
| `experimental10.png` | 3×3; used: row 1 column 1, holding an Easter egg (95, `EasterEgg`) |
| `full.png` | 3×3, the first sheet before its legs were taken off; used: row 3 column 3, waving (96) |
| `experimental4.png` | 3×3; used: row 2 column 1, glowing heart eyes (98) |
| `blush.png` | One image: blushing, smiling (83, `Love`) |
| `experimental11.png` | 3×3; used: row 2 column 3, sunglasses (97) |
| `experimental12.png` | 3×3; used: row 2 column 1, a magnifying glass (99, `Power`); row 1 column 1, wondering (101); row 2 column 3, binoculars (102) |
| `experimental13.png` | 3×3; used: row 3 column 1, wrapped in a blanket, freezing (103, `Cold`); row 3 column 3, peeking out of a hole in the floor (104, `Appear`) |
| `scripts/compose.py` | Cuts the images out and makes `shime1.png` … `shime104.png` (128×128, base at (64, 128)) and `preview.png` |
| `scripts/chest.py` | Swaps the square on its chest for a speech bubble (or the Arch logo, for your own copy only: it is Arch Linux's trademark) |
| `scripts/measure.py` | Checks that Robo is the same size in every frame (by its visor); run it after adding images |
| `scripts/cutout.py` | `robo.png` → `robo-cutout.png` |
| `scripts/patch.py` | Adds Robo's own actions and behaviours to the converted pack |

## What it does

- Held up it **dangles**: straight down (`front.png`, 90) only when held still, right under the pointer;
  the further the pointer is from its feet, the more it swings (5/6 a small swing, 7/8 the swing, 9/10 more).
- It **hovers**: walking (and creeping) is the glide image bobbing up and down; standing still, it looks straight
  ahead (`front.png`, also sitting). Dizzy spirals only right after landing.
- While the bubble answers: **thinks** (`Chatter`, three ways of thinking in turn). While a tool runs for the answer it shows what it
  does (see `mascot_chat_doing()`): the **notepad** for the todo list, a **salute** for reminders, the **globe** for the
  weather, the **hologram cube** for files, images and searching a file, its
  **head open, gears turning** over your last commands, **meditating** when it gets sleepy, its **chest open** while it checks your system, a **magnifying glass** over a graph while it checks the machine, a magnifying glass while it checks how the CPU runs, and **"100% FULL POWER"** when it runs on performance. The weather feels like 0 °C or colder: wrapped in a
  **blanket**, freezing (`Cold`). Summoned (or back after the screen was off): it **peeks out of a hole** in the
  floor for about 1.5 s (`Appear`). Thanked or praised: it **blushes** (`Love`). When that found
  nothing to go on, a **"?"** on its visor while it answers (`Unsure`). A todo done:
  **laughing**, eyes shut tight (`Done`). An answer that failed: **"ERROR"** and a tear (`Failed`). A reminder
  that is due: a yellow **"!"** bulb (`Alarm`). Asleep: the "z" on its visor rises and sinks
  (`Snooze`). An answer waiting to be read: **NEW** on its visor (`NewMessage`). Clicked quickly many times:
  it holds up an **Easter egg** (`EasterEgg`).
- Now and then on the floor: a hologram cube, tinkering, opening its chest,
  giggling, winking, meditating (longer than the others), waving, sunglasses, heart eyes, wondering, looking through
  binoculars. Drawn but not used yet (they need events of their own): singing
  (while music plays), nervous,
  cheering, grumpy, shrugging, sweating, worried with a drop of sweat, a tear, the magnifying
  glass (kept for something else).
- **Never used** (the user's choice): laughing and shaking (`experimental5.png` row 1 column 3, frame 82 until
  0.4.0), the two with legs (`experimental7.png` row 3 column 2, heart eyes sitting; `experimental8.png` row 2
  column 2, meditating cross-legged) and standing on a plate (`experimental.png` row 3 column 2).

## Building it

Needs Python with numpy and Pillow, the Symbols Nerd Font (`ttf-nerd-fonts-symbols`) and Mascot.

```sh
mkdir -p build && cd build
python3 ../scripts/compose.py ../complete.png Robo bubble       # or arch, or square
echo 1 | mascot convert -O out --name Robo Robo
python3 ../scripts/patch.py out/Shimeji.Robo.wlshm Robo.wlshm
mascot import -f --no-climb --talk Chatter --sleep Snooze --answered NewMessage Robo.wlshm
```

The bundled copy in `prototypes/Shimeji.Robo/` is what that import installs (from
`~/.local/share/mascot/shimejis/Shimeji.Robo/`). `mascot import -f` does not update a Robo that is
already out; summon a new one with `mascot summon Robo`.
