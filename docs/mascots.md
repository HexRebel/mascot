# Using mascots

Adding, summoning and steering the mascots themselves. For the chat bubble see [chat.md](chat.md).

## Adding mascots

Shimeji-ee mascots are usually shared as zip files; you can find many on the internet. Import one
straight from the zip (or from its unpacked directory):

```sh
mascot import "Shiba Inu Shimeji.zip"
```

Packs come in many shapes, and the import finds the mascots in them: a Shimeji-ee instance
(`img/<name>/` and `conf/`, also a few directories down, or with `conf/` only inside the mascot's
directory), `img/` with the images right in it, or just the images (`shime1.png` to `shime46.png`),
which use the bundled Shimeji's actions. A mascot without a name of its own is named after the file
(`Testy Shimeji v1.2.zip` gives *Testy*). When it is done, it says what each mascot talks and sleeps
with; anything in the pack that will not work (a missing image, an action that is not defined, and
the behaviors that go with them) is named while converting.

A pack with one mascot is imported as it is. For a pack with several, pick them with `--figure`
(any letter case, more than once), take them all with `--all`, or choose from the list it shows:

```bash
$ mascot import "The Neuroling Collection v0.7.zip"
Prototypes available for conversion:
1. Weuron
2. Vedaling
...
Enter prototypes index or name to convert (can be comma-separated or A to convert all)
>
```

- `--name "Red Shiba"` gives the mascot another name than the pack's (for one mascot), e.g. when
  it is called just `Red`: `mascot import --figure Red --name "Red Shiba" "Shiba Inu Shimeji.zip"`.
- `--no-climb`: the mascot never climbs walls or hangs from the ceiling. Every behavior whose name
  mentions a wall, the ceiling, climbing or hanging is never picked; falling, being thrown and being
  dragged still work.
- While the chat bubble answers, the mascot plays a `Talk` behavior (never picked at random). The
  import picks its action from the mascot's own (one with petting, talking or waving in its name) and
  says which; `--talk <action>` picks another (`mascot prototypes info <name>` lists them; take one
  that looks right on the floor), `--talk none` none, and the mascot just sits.
- Close the bubble while the mascot answers, and it stays sitting and talking until the answer is
  written, then repeats an `Answered` behavior until you click it to read the answer (at most 10
  minutes). The import picks one that stays on the spot (looking at you, waving, watching...) and
  says which; `--answered <action>` picks another, `--answered none` lets it just sit.
- While a tool runs for the answer, a mascot can show what it does: it plays its behavior for that
  tool instead of `Talk`, if it has one, until the answer starts. `Todo` and `Reminder` (the todo list
  and reminders), `Weather`, `Files` (a folder or file), `Search` (in a file), `Image`, `Shell` (your
  last commands), `Sleepy` (the sleep tool), `System` (troubleshooting), `Machine` (checking the machine), `Power` (checking how the CPU runs). Robo writes in its notepad,
  holds up the globe, opens its head while it reads your commands, opens its chest while it checks
  your system... When the system tools found nothing to go on, it plays `Unsure` while it answers
  (Robo's "?"); when it took a todo off the list (or after `.todo done`), `Done` (Robo laughs); when the answer
  failed, `Failed` (Robo's "ERROR" and a tear); when the CPU runs on performance, `FullPower` (Robo's "100% FULL
  POWER"); when the weather feels like 0 °C or colder, `Cold` (Robo wraps himself in a blanket); when your message is nothing but thanks or a compliment ("thanks!", "well done", "tusind tak ❤"),
  `Love` (Robo's heart eyes). One word that is not thanks or praise and it does not: "great, you deleted it all". A
  reminder that is due plays `Alarm` (Robo's yellow "!").
- A figure can hide an easter egg: an `EasterEgg` behavior (frequency 0, so it is never picked) plays
  once when the mascot is clicked quickly many times on the floor. Robo has one; try it.
- Asleep (`mascot sleep`, a middle click), the mascot repeats its own `Sleep` behavior, else
  `LieDown` or `SitDown`. Many packs' `Sleep` gets up again at the end, or rolls along the floor;
  then the import picks a pose that lies still instead (the first part of that `Sleep`, or an action
  named like sleeping or lying) and says which, or says it found none. `--sleep <action>` picks the
  action it sleeps with yourself, e.g. `--sleep SitAndDangleLegs`.
- If you already have a mascot of that name, it is not imported: `-f` replaces it, `--name` keeps
  both. A mascot with the same name in another letter case (*Red* and *red*) is never replaced; give
  the new one another name. `--name` works for `.wlshm` files too.

To see what a mascot's actions look like, `mascot prototypes poses "Red Shiba"` opens a page in
the browser with each of them moving as the mascot plays it, what it talks, waits with an answer
and sleeps with now marked, and buttons that copy the command to change it (the page is written to
`$XDG_RUNTIME_DIR`; `--no-open` only says where).

To change what an installed mascot talks, waits with an answer or sleeps with later, without importing it again:

```
mascot prototypes set "Red Shiba" --sleep SitAndDangleLegs
mascot prototypes set Capoo --talk auto --sleep auto
mascot prototypes set "Brown Bear" --talk BePet --answered Pet
```

An action's name (`mascot prototypes info <name>` lists them), `auto` to pick one as the import
does, or `none` (no `Talk` or `Answered`; for sleep, the mascot's own `Sleep`). It is changed in the mascot's own
directory and reloaded straight away. A bundled mascot is changed in the installed copy, which takes
effect when Mascot starts next and which the next `make install` replaces.

To remove a mascot you imported, with its files: `mascot prototypes remove "Red Shiba"` (it asks
first; `-y` does not). Its mascots on the screen are sent away. The bundled ones come with Mascot
and stay.

Packs made for Windows sometimes name their images in another letter case than their actions do
(`swag1.png` for `Swag1.png`); that is matched.

`scripts/make_test_packs.py <directory>` builds a few packs in these shapes from the bundled
Shimeji's images, to try the import on.

### Converting to .wlshm files

`mascot convert` writes the mascots of a pack to `.wlshm` files instead, e.g. to share them; it
takes the same `--figure`, `--all` and `--name` and does not start Mascot. `mascot import` takes
those files too (as does `mascot prototypes import`).

```sh
mascot convert "Shiba Inu Shimeji.zip" --all -O ~/mascots
mascot import --no-climb ~/mascots/Shimeji.Sesame.wlshm
```

## Listing available prototypes

You can list all available mascot prototypes using the following command:

```sh
mascot prototypes list
```

Mascot ships with two, installed to `$(PREFIX)/share/mascot/prototypes/`: **Robo**, Mascot's own
mascot (a small hovering robot whose visor shows how it feels; CC0, sources and how it was made in
[`art/robo/`](../art/robo/)), and the original **Shimeji** by Yuki Yamada (Group Finity). Prototypes you import yourself go to
`~/.local/share/mascot/shimejis/` and take precedence over a bundled one with the same name.

## Summoning mascots

To summon mascot, you need to know mascot's name, which you can get by using `mascot prototypes list` command. When you found mascot of your choice, you can summon using `mascot summon {name}` command, where `{name}` is the name of the mascot you want to summon.

For example, if you want to summon a mascot named Neuron, you can use the following command:

```sh
mascot summon Neuron
```

If you want to summon mascot at specific location, you can use --select flag or pass your coordinates as -x -y or -position x,y

## Dismissing mascots

To dismiss mascot, you can use `mascot dismiss` command.
mascot will ask you to click on target mascot.
Also we have flags that can be used to dismiss multiple mascots at once.
Use `mascot dismiss --help` to see all available flags.

## Setting mascots behaviors

You can replace mascot's behavior by using `mascot set-behavior {behavior}` command, where `{behavior}` is the name of the behavior you want to set. mascot will ask you to click on target mascot.

You can get all available behaviors by using `mascot prototypes info {prototype_name}` command, where `{prototype_name}` is the name of the mascot prototype you want to get information about.

## Right click

A right click on a mascot opens a small menu next to it (with the chat bubble enabled):
**Settings** (**Change mascot**, like `.mascot`; the mascot's **Model**, **Role** and **Session** to
pick from, as `.model`, `.role` and `.session`, the one in use ticked, a model not listed with
**Other model…** (see *Using it*), a new session with **New session…** (the bubble with `.session`
typed, for its name), a private one marked so, and **Delete session ›** (the bubble with
`.delete session <name>` typed: Enter deletes it); and **Tools** and **Info**, the bubble with `.tools` or `.info`),
**Stay** (it stays where it is, or wherever you drop it, awake: it sits, and in between does whatever
its figure can do on the spot, like lying down or looking around; it still talks and sleeps, until
you pick it again; ticked meanwhile), **Sleep** or **Wake
up** (just this mascot, like a middle click), **Quiet** (all of them sleep for **10 min**, **30 min**
or **1 hour**, like `mascot sleep --minutes 30`, or **Set time…**, the bubble with `.quiet` typed for
a time of your own; **Wake everyone** while they sleep), **Todo list** and **Reminders** (the bubble with
`.todo` or `.reminders`), **Help** (`.help all`) and **Send away** (sending the last one away stops
Mascot). It takes no keyboard and closes when you pick something or
move the pointer off it.

**`mascot menu`** opens the menu at the mascot you last talked to (or the first one) and closes it
again; bind it to a key like `mascot chat`, e.g. in Hyprland `bind = SUPER SHIFT, N, exec, mascot
menu`. Opened this way, it takes the keyboard until it closes: **↑/↓** (or **k/j**) move, **Enter**
or **→** (**l**) picks or opens a page, **←** (**h**) or **Backspace** goes back, **Esc** (or the key
again) closes it. What it opens in the bubble keeps the keyboard too.

## Putting mascots to sleep

`mascot sleep` puts every mascot to sleep until `mascot wake`: each one lies down as soon as it is on
the floor, and mascots summoned meanwhile fall asleep too. A mascot sleeps with the first of these
behaviors its prototype has: `Asleep`, `Sleep`, `LieDown`, `SitDown`; asleep for a while (Quiet, `-m`,
the sleep tool) `Quiet` comes first (Robo switches off). Shimeji-ee's `Sleep` often
ends by getting up again; to choose another pose, add a behavior `Asleep` with `frequency` 0 that
points to it. A sleeping mascot does not disturb: it makes no remarks (`CHAT_REMARKS`), and
reminders wait until one wakes up. A middle click on a mascot puts just that one to sleep, or wakes
it up. A sleeping mascot sleeps on while its right-click menu is open, and sits up while you talk to
it in the bubble; waking the last sleeping one ends a `--minutes` sleep for all. `mascot sleep --minutes 30` (or asking a mascot, with `sleep` in `CHAT_TOOLS`) lets them
sleep for a while instead: a plain `mascot wake` does not end that, so hypridle's does not either,
but `mascot wake --all` and a middle click do. Neither command starts Mascot, so both are safe to
run when it is not running, e.g. from hypridle:

```
listener {
    timeout = 600
    on-timeout = mascot sleep
    on-resume = mascot wake
}
```

## Exporting prototypes

You can export mascot prototype by using `mascot prototypes export` command. It will produce .wlshm file that you can then share with others.

```sh
mascot prototypes export -i {prototype_name} -o {output_file}
```

## Stopping application

You can stop the application by using `mascot stop` command.

## Configuration

You can configure some options of overlay by using `mascot config` command.

```sh
mascot config set "option_name" "value"
```

You also can get option value by using `get` action:

```sh
mascot config get "option_name"
```

Or values of all options by using `list` action:

```sh
mascot config list
```

Config file is usually located at `~/.local/share/mascot/mascotd.conf`

## Advanced usage

### Multihead usage

mascot supports multiple screens. However, some features may be disabled by default. Config provides following options:

- ALLOW_THROWING_MULTIHEAD: Allows throwing mascot between screens
- ALLOW_DRAGGING_MULTIHEAD: Allows dragging mascot between screens
- UNIFIED_OUTPUTS: Treats all outputs as one entity

You may want block one of displays from being used by mascot in runtime, so we have `mascot environment close` to disable one of outputs. mascot will ask you to select one of outputs by clicking on it. After this operation, you can't restore display unless you restart mascot or reconnect display to the system.

### Interpolation

mascot supports movement interpolation of mascots. You can enable it by setting INTERPOLATION_FRAMERATE to value that is not equal to 0. Values > 0 used as interpolation frame rate. -1 Picks output's refresh rate as interpolation frame rate. Values under -1 are not allowed.

### Tablets

mascot recognized pentablets as input method, so you can use it as input device. However, currently subsurfaces bugged under KDE when using them with wp-tablet-v2, so you may want to disable that feature by setting TABLETS_ENABLED to false.

### Mapping mouse buttons

You can map mouse button and tablet events (stylus down, stylus up) to different actions. For example you can remap right button to 0x01, so it will act as left button and etc.

### Using systemd socket

mascot can be activated on-demand through systemd socket. To enable it, use `systemctl --user enable --now mascotd.socket`.
This is optional and has not been tested with Mascot's changes; `mascot summon` starts the daemon by itself.

### Running overlay manually

You can start overlay manually by running `mascotd`. It's not recommended and *useless* in case you don't pass -se flag to it or
if you don't pass unix fd using -cfd flag, unless you implementing another frontend for the overlay. If -se or -cfd not specified
overlay will close immediately after start.

Arguments:

- `-s`, `--socket-path`  - path to the overlay socket file.
- `-cd`, `--configuration-root`  - path to the configuration root of the mascot (`~/.local/share/mascot` by default)
- `-cfd`, `--caller-fd` - paired unix socket fd used for communication. If closed and no other clients connected nor no mascots exists, overlay will close.
- `-c`   - config file path.
- `-pl`  - path to the plugins directory.
- `-pr`  - path to the prototypes directory.
- `-se` - summon everyone. If specified, overlay will summon all known mascots upon start.
- `-v`, `--version`  - version of the overlay.
- `--no-tablets` - disable wp_tablet_v2 wayland protocol support. (broken on kwin right now anyway)
- `--no-viewporter` - disable wp_viewporter wayland protocol support. mascot will use wl_surface.set_buffer_scale() instead.
- `--no-fractional-scale` - disable wp_fractional_scale wayland protocol support. Will use wl_output's scale info instead
- `--no-cursor-shape` - disable wp_cursor_shape wayland protocol support. Will disable cursor shapes for different actions.
- `--no-plugins` - disable plugins

