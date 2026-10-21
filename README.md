# Mascot - Shimeji desktop mascots for Wayland that you can talk to

Mascot puts [Shimeji](https://kilkakon.com/shimeji/)-style characters on your Wayland desktop. They walk
along the bottom of the screen, sit down and can be picked up and thrown. Tap one and a speech bubble
opens next to it: type a message and the answer from a language model is streamed into the bubble,
while the mascot sits still and talks. The answers come from
[aichat](https://github.com/sigoden/aichat), so a local model through Ollama works as well as a hosted one.

Mascot is a fork of [wl_shimeji](https://github.com/CluelessCatBurger/wl_shimeji) by CluelessCatBurger,
licensed under GPL-2.0-or-later like the original. The engine (prototypes, the condition VM, the
Wayland overlay) is theirs; Mascot adds the chat bubble, tap-versus-drag input, a bundled mascot and
the renaming. Source files changed from upstream say so in their header, and the git history shows
exactly what has changed.

<p align="center">
  <img src="./docs/screenshot.png" style="width: 100%;">
</p>

The mascot on the screenshot is the bundled Shimeji by Yuki Yamada (Group Finity), chatting through the bubble.

## Compositor support

Mascot needs a compositor with **wlr-layer-shell** and **wl_subcompositor**, so GNOME (Mutter) and
Gamescope will not work.

- **Hyprland** is what Mascot is developed and tested on (0.56). It works, with two known quirks:
  a mascot that overlaps the right or bottom edge of the screen is squashed instead of clipped
  ([hyprwm/Hyprland#10515](https://github.com/hyprwm/Hyprland/issues/10515)), and Mascot works around
  a Hyprland crash when the bubble closes while the pointer is over a mascot.
- **KDE Plasma, Sway and other wlroots compositors** are supported by upstream but have not been
  tested with Mascot's changes.

## Quick start

```sh
git clone --recurse-submodules https://github.com/Xedoc91/mascot.git
cd mascot
make -j$(nproc)
make PREFIX=$HOME/.local install
mascot summon Shimeji     # starts the daemon and the chat bubble
mascot stop               # stops both again
```

Mascot ships with the original Shimeji; `mascot import <shimeji-ee pack.zip>` adds others (see
[Adding mascots](#adding-mascots)). For the chat bubble you also need Quickshell and a configured
aichat (see [Chat bubble](#chat-bubble)).

# Requirements

## Build requirements

- libwayland-client:
  - Arch: `pacman -S wayland`
  - Debian: `apt-get install libwayland-dev libwayland-bin`
  - Fedora: `dnf install libwayland-client wayland-devel`
- wayland-protocols:
  - Arch: `pacman -S wayland-protocols`
  - Debian: ??? You can manually clone wayland-protocols and then specify it path by setting WAYLAND_PROTOCOLS_DIR to wayland-protocols' absolute path
  - Fedora: `dnf install wayland-protocols-devel`
- libarchive:
  - Arch: `pacman -S libarchive`
  - Debian: `apt-get install libarchive-dev`
  - Fedora: `dnf install libarchive-devel`
- uthash:
  - Arch: `pacman -S uthash`
  - Debian: `apt-get install libuthash-dev`
  - Fedora: `dnf install uthash-devel`

## Runtime requirements

Your compositor should *at least* support xdg-shell, wlr-layer-shell protocols, and provide wl_subcompositor interface.

## mascot (CLI) requirements

- python-pillow
  - Arch: `pacman -S python-pillow`
  - Fedora: `dnf install python3-pillow`
- python >= 3.10

# Installing

## Packages

There are no packages for Mascot yet; build it from source (below).
The upstream project has packages of its own, which install wl_shimeji, not Mascot:
[wl_shimeji-git](https://aur.archlinux.org/packages/wl_shimeji-git) and
[wl_shimeji-plugin-kwinsupport](https://aur.archlinux.org/packages/wl_shimeji-plugin-kwinsupport) on the AUR,
and a Nix flake (see the [upstream README](https://github.com/CluelessCatBurger/wl_shimeji#readme)).

This repository still contains the upstream Nix flake, updated for the new names, but it has not
been built or tested since the fork.

# Building

From a checkout of this repository, with submodules (`git submodule update --init`):

```sh
make -j$(nproc)
sudo make install                    # to /usr/local
make PREFIX=$HOME/.local install     # or just for you, without sudo
```

`$(PREFIX)/bin` must be in your `PATH`, since `mascot` starts `mascotd` from there.
`make uninstall` removes the files again (pass the same `PREFIX`/`DESTDIR`).

# Plugins

You can also build plugins (everything in src/plugins subdirectories). They come from upstream
and only work on KDE; they build with Mascot but have not been tested with it.
Plugins are optional, but can provide such features as:

- Interactions with other applications' windows
- Get global mouse position

Currently mascots can't move windows as it is not supported by mascot.

Currently we have following plugins:

- src/plugins/kwinsupport - KDE integration using it's scripting API

## Dependencies for plugins

- KwinSupport:
  - libsystemd (for dbus):
    - Arch: `pacman -S libsystemd`
    - Debian: `apt-get install libsystemd-dev`
    - Fedora: `dnf install systemd-devel`
  - uthash:
    - Arch: `pacman -S uthash`
    - Debian: `apt-get install libuthash-dev`
    - Fedora: `dnf install uthash-devel`
  - libmascot-plugins (supplied by mascot)
  - mascot should run with XDG_CURRENT_DESKTOP set to "KDE" and org.kde.KWin must be present on session bus

## Building plugins

```sh
make build-plugins -j$(nproc)
```

## Installing plugins

```sh
make install-plugins
```

# How to use

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
- Asleep (`mascot sleep`, a middle click), the mascot repeats its own `Sleep` behavior, else
  `LieDown` or `SitDown`. Some packs' `Sleep` is something else (the Shiba Inu rolls on its back);
  `--sleep <action>` picks the action it sleeps with instead, e.g. `--sleep SitAndDangleLegs`.
- If you already have a mascot of that name, it is not imported: `-f` replaces it, `--name` keeps
  both. A mascot with the same name in another letter case (*Red* and *red*) is never replaced; give
  the new one another name. `--name` works for `.wlshm` files too.

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

# Listing available prototypes

You can list all available mascot prototypes using the following command:

```sh
mascot prototypes list
```

Mascot ships with the original Shimeji by Yuki Yamada (Group Finity), installed to
`$(PREFIX)/share/mascot/prototypes/`. Prototypes you import yourself go to
`~/.local/share/mascot/shimejis/` and take precedence over a bundled one with the same name.

# Summoning mascots

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
**Other model…** (see *Using it*), a new session named with
`.session <name>` in the bubble; and **Tools** and **Info**, the bubble with `.tools` or `.info`), **Sleep** or **Wake
up** (just this mascot, like a middle click), **Quiet** (all of them sleep for **10 min**, **30 min**
or **1 hour**, like `mascot sleep --minutes 30`, or **Set time…**, the bubble with `.quiet` typed for
a time of your own; **Wake everyone** while they sleep), **Todo list** and **Reminders** (the bubble with
`.todo` or `.reminders`), **Help** (`.help`) and **Send away** (sending the last one away stops
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
behaviors its prototype has: `Asleep`, `Sleep`, `LieDown`, `SitDown`. Shimeji-ee's `Sleep` often
ends by getting up again; to choose another pose, add a behavior `Asleep` with `frequency` 0 that
points to it. A sleeping mascot does not disturb: it makes no remarks (`CHAT_REMARKS`), and
reminders wait until one wakes up. A middle click on a mascot puts just that one to sleep, or wakes
it up. `mascot sleep --minutes 30` (or asking a mascot, with `sleep` in `CHAT_TOOLS`) lets them
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

# Exporting prototypes

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

# Chat bubble

Left-click (tap) a mascot and a speech bubble opens next to it. Type a message, press Enter, and
the answer from a language model is streamed into the bubble. The mascot sits still while the
bubble is open.

The bubble is a separate [Quickshell](https://quickshell.org/) project in `ui/`; `make install`
puts it in `$(PREFIX)/share/mascot/ui/`. The answers come from [aichat](https://github.com/sigoden/aichat),
so any model aichat supports works, including local ones through Ollama.

## Requirements

- Quickshell (`pacman -S quickshell`)
- aichat (`pacman -S aichat`), configured with at least one model
- Optional: pywal (`pacman -S python-pywal`) for colours that follow your theme (see [Colours](#colours))

## Starting and stopping

You do not start the bubble yourself: `mascotd` starts it (`qs -p $(PREFIX)/share/mascot/ui`) and
stops it again, so it runs exactly as long as Mascot does.

```sh
mascot summon Shimeji   # starts mascotd, which starts the bubble
mascot stop             # stops mascotd and the bubble, including an aichat that is answering
```

Nothing is left running in the background: the bubble runs in its own process group, which mascotd
stops when it exits (also on SIGTERM, or when the last mascot is dismissed). If mascotd is killed
outright, the kernel stops the bubble (`PR_SET_PDEATHSIG`) and the bubble quits when it loses the
daemon.

To run the bubble by hand instead, e.g. while working on `ui/`, set `BUBBLE_ENABLED` to `false` and
start it next to the daemon (not as part of another Quickshell config):

```sh
qs -p /usr/local/share/mascot/ui
```

Started by hand, it reconnects if the daemon is restarted. It uses the daemon's chat socket,
`$XDG_RUNTIME_DIR/mascotd-chat.sock`, or `MASCOT_CHAT_SOCKET`. The daemon names the chat socket
after its IPC socket, so `-s /run/user/1000/foo.sock` gives `foo-chat.sock`.

## Using it

- **Tap** a mascot to open the bubble. Dragging a mascot does not open it, and dragging the mascot
  away closes it.
- The bubble takes the keyboard when it opens, so you can type straight away. Click another window
  to type there while the bubble stays open; click the bubble (or tap the mascot) to go back.
- **Enter** sends, **Esc** or **×** closes. **↑/↓**, **Ctrl+K/Ctrl+J** and **PageUp/PageDown** scroll
  the conversation.
- Each mascot has its own conversation, kept until Mascot stops: close the bubble, tap the mascot
  again and it carries on where you left it, and the model remembers what was said. `.clear` starts
  it over.
- **`mascot chat`** opens the bubble at the mascot you last talked to (or the first one), and closes
  it again; bind it to a key to chat without the mouse, e.g. in Hyprland
  `bind = SUPER SHIFT, M, exec, mascot chat`. A bubble opened this way keeps the keyboard until it
  closes (Esc, × or the key again), so you can type straight away wherever the pointer is.
- With `CHAT_REMARKS` set, a random mascot now and then says something on its own. Its bubble does
  not take the keyboard and closes 7 seconds after the remark, unless the pointer is on it; click
  into it to answer. `mascot chat --remark` makes one say something now.
- Closing the bubble does not stop a reply: it is written into the conversation in the background,
  ready when you tap the mascot again.
- Reasoning models' `<think>…</think>` is not shown; the bubble says *thinking…* until the answer starts.
- **Copy** part of an answer by selecting it with the mouse and pressing **Ctrl+C** (the input keeps the
  keyboard, so you can type on); `.copy` copies the whole last answer. The mouse wheel scrolls.

Lines starting with `.` are commands, modelled on aichat's REPL:

| Command | Effect |
|---|---|
| `.help` | List the commands |
| `.info` | Show aichat's settings |
| `.models`, `.roles`, `.sessions` | List them |
| `.model <name>` | Switch model, e.g. `.model openrouter:…` |
| `.role <name>` | Switch to one of your aichat roles instead of Mascot's prompt |
| `.session <name>` | Use a named aichat session instead of the mascot's own memory (it is saved, so it outlives Mascot) |
| `.exit model\|session` | Go back to the default |
| `.exit role` | Leave the role, also the one from `CHAT_ROLES`/`CHAT_ROLE` (until `.role` or a restart) |
| `.mascots` | List the mascots you have installed |
| `.mascot <name>` | Swap this mascot for another one, e.g. `.mascot shimeji` |
| `.tools` | List what the mascot can look up (see *Tools*) |
| `.todo` | Show the todo list (see *Tools*) |
| `.todo add <item>` | Add an item to it |
| `.todo done <number or text>` | Remove an item from it, or several, e.g. `.todo done 1, 4` |
| `.todo edit <number> <text>` | Change what an item says |
| `.remind <when> <text>` | Set a reminder or timer, e.g. `.remind 10m tea` or `.remind tomorrow 12:00 water the plants` (see *Tools*) |
| `.reminders` | List the reminders |
| `.remind cancel <number or text>` | Cancel one |
| `.quiet <when>` | All mascots sleep until then (no remarks, reminders wait), e.g. `.quiet 2h` or `.quiet 19:30`; `.quiet now` wakes them |
| `.copy` | Copy the last answer to the clipboard |
| `.clear` | Start this mascot's conversation over |

The model, role and session apply to the mascot whose bubble you typed them in, until changed, and
reset when `qs` restarts; each mascot can have its own.

**Models from OpenRouter.** aichat's own list of OpenRouter's models is old, and OpenRouter removes
models over time (they answer with *No endpoints found*). The menu's **Model** page therefore asks
OpenRouter which models it has now (no key needed) and leaves out the ones that are gone. A model that
is not listed can be used anyway: **Other model…** opens the bubble with `.model openrouter:` typed,
for a name from [openrouter.ai/models](https://openrouter.ai/models) (e.g.
`anthropic/claude-haiku-5.5`). Once it has answered, it is on the Model page from then on (the last
ten are kept in `~/.local/share/mascot/models`). To choose the list yourself, give the client a
`models:` list in aichat's config; aichat then shows only those:

```yaml
clients:
  - type: openai-compatible
    name: openrouter
    api_base: https://openrouter.ai/api/v1
    models:
      - name: anthropic/claude-haiku-5.5
        max_input_tokens: 1000000
        supports_function_calling: true
```

The memory is an aichat session per mascot, kept in `$XDG_RUNTIME_DIR/mascot-memory/` and deleted when
the bubble starts and quits; your own aichat sessions are not touched. The memory is sent with
every message, so once it holds about `CHAT_MEMORY` tokens (8000 by default) the bubble has the
model sum it up and carries on in a fresh memory that starts with the summary; you see *summing up
the memory…* and the text in the bubble stays. `.clear` starts over completely. A session keeps the role or prompt it started with, so changing the role (or swapping to a
mascot with another name) starts the memory over, while the text stays in the bubble.

`.mascot` replaces the mascot by the bubble with a new one of the given type (any letter case) in the
same spot, facing the same way. The bubble stays open and the conversation carries on with the new
mascot; with Mascot's prompt it answers under its new name from the next message.

## The mascot's personality

Unless you pick a role with `.role` or set `CHAT_ROLE`, every message is sent with Mascot's own system prompt
(aichat's `--prompt`), so the mascot answers in character, briefly and in your language. `{name}` in
the prompt becomes the mascot's name, so Shimeji answers as Shimeji. Your aichat roles and
your `cmd_prelude` are left alone; the prompt simply takes their place in the bubble.

The bundled prompt is `$(PREFIX)/share/mascot/ui/prompt.md`. To write your own, put a `prompt.md` in
Mascot's data directory (`~/.local/share/mascot/prompt.md`); it replaces the bundled one, and an
empty file turns the prompt off. Note that aichat skips `cmd_prelude` for a session, and the
bubble's memory is one; to keep your prelude role, set it as `CHAT_ROLE` (below). The bubble reads it when it starts, so run `mascot stop` after
changing it.

To start with one of your aichat roles instead, set `CHAT_ROLE`, e.g. `mascot config set CHAT_ROLE
my-role`. It replaces the prompt from the next tap; `.role` overrides it, and `.exit role` leaves it
until you pick a role again or `qs` restarts.

To give each kind of mascot its own role, set `CHAT_ROLES` to `<mascot>=<role>` pairs separated by
`;`, e.g. `mascot config set CHAT_ROLES 'Shimeji=my-role;Example=other-role'`. Mascot names are the
ones `.mascots` lists (any letter case); a mascot that is not in the list gets `CHAT_ROLE`, and an
empty role (`Shimeji=`) gives that mascot Mascot's prompt instead. Swapping
with `.mascot` switches to the new mascot's role.

## Tools

The mascot can look things up while it answers, with Mascot's own tools (aichat's function calling,
in the [llm-functions](https://github.com/sigoden/llm-functions) layout, installed to
`$(PREFIX)/share/mascot/tools/`). They only read, but for your todo list and reminders; none of them
writes, deletes or runs anything else:

| `CHAT_TOOLS` | Tools | What they do |
|---|---|---|
| `time` | – | The date, weekday and time, put in front of every message (unseen), so it works with any model |
| `weather` | `get_current_weather` | The weather from [wttr.in](https://wttr.in); only the place name is sent (none: wttr.in guesses it from your IP address) |
| `files` | `list_directory`, `read_file`, `search_file`, `look_at_image` | List directories (or draw a tree of one, up to 4 levels), read text files (as much as fits the model, see below), find lines in a file or a directory of files, and look at pictures (PNG, JPEG, WebP) in your home directory |
| `todo` | `list_todos`, `add_todo`, `remove_todo`, `edit_todo` | Keep your todo list: ask the mascot to remember something, to reword an item, or tell it something is done |
| `reminders` | `set_reminder`, `list_reminders`, `cancel_reminder` | Reminders and timers: "remind me to water the plants tomorrow at 12", "set a timer for 10 minutes" |
| `sleep` | `sleep_mode` | "I need to focus, sleep for an hour": all mascots sleep until then (see *Putting mascots to sleep*); "wake up" wakes them early |
| `shell` | `last_commands` | Your last commands in the terminal (5, or up to 10), to explain one: "what did my last command do?", "explain the git command I just ran" |

`CHAT_TOOLS` is `time,weather` by default; add `files` to let the mascot see your files, `todo`
for the todo list, `reminders` for reminders, `shell` for your last commands and `sleep` to let the
mascots nap, e.g. `mascot config set CHAT_TOOLS time,weather,files,todo,reminders,shell,sleep`, or set
it empty to turn the tools off. It takes effect from the
next tap.

The todo list is one list for all mascots, `todo.md` in Mascot's data directory
(`~/.local/share/mascot/todo.md`), with one `- [ ] item` line per item; you can edit it yourself,
and other lines in it are kept. `.todo`, `.todo add <item>`, `.todo done <number or text>` and
`.todo edit <number> <text>` change it straight away, without the model. When the mascot changes it, the bubble shows what really
changed (*✓ todo: added …*), so a reply that only claims it did is easy to spot. Models also like to say *here is your list* without it: when the
mascot looked the todo list up, or drew a tree of a directory, and the reply leaves it out, the bubble
shows it under the reply.

Reminders are kept in `reminders.md` in the data directory, one `- 2026-10-19 12:00 text` line each
(your local time). When one is due, a mascot says it (*⏰ text*): in the open bubble, or else the
bubble opens at a mascot without taking the keyboard and stays until you close it or click it. One
that fell due while Mascot was not running is shown when it starts, with the time it was for. A
shown reminder is taken off the file. `.remind` understands a duration (`10m`, `1h30m`, `2 hours`,
`45s`; a bare number is minutes), a time of day (`12:00`, today or else tomorrow), `tomorrow 9:00`,
or a date and time (`2026-10-19 12:00`, `19.10.26 12:00`). `.remind` works without the tool and with any
model, like `.todo`; the reminders are shown whatever `CHAT_TOOLS` says.

The file, todo, reminder and shell tools keep to what is yours to share:

- Files: only your home directory, and no hidden files or directories (dotfiles, `~/.config`, …)
  unless you list them in `CHAT_DOTFILES`, separated by `;`, e.g. `mascot config set CHAT_DOTFILES
  '~/.zshrc;~/.config/hypr;~/.config/kitty'`. Only what is listed (and what is inside a listed
  directory) can be read; a link may not lead from there to any other hidden place. The directories
  on the way, like `~/.config`, can be listed, but show only what you allowed. `CHAT_DOTFILES` is
  empty by default, so the mascot sees no dotfiles until you choose some.
- Even then, never where keys, logins and history are kept, wherever they are and also not through a
  link: `.ssh`, `.gnupg`, password stores and keyrings, aichat's config, `.env` files, keys and
  certificates, browser profiles and everything that looks like their storage (cookies, local
  storage, databases), mail and chat apps, `.git` directories, `.cache`, flatpak's `.var`, shell
  history, `environment.d` and uwsm's env files (`SECRET_DIRS` and `SECRET_NAMES` in
  `tools/mascot-tools`). That list is a safety net, not a guarantee: it cannot know every app, so
  allow only the dotfiles you would show anyone.
- Big files: `read_file` hands the model about a quarter of its context, so the conversation still
  fits (more silently pushes your question out of it in Ollama): it asks Ollama for the model's
  `num_ctx` (or Ollama's default of 4096 tokens without one), e.g. 12 KB for 16k tokens and 96 KB for
  128k, and 12 KB if Ollama cannot say. A bigger model gets more without any setting. For a bigger
  file the mascot is told to use `search_file`, which finds the lines with what you ask about (e.g.
  *which font does kitty use?*) and a line around each.
- Pictures: a tool can only hand the model text, so `look_at_image` shows the picture to the same
  local model itself, through Ollama's API (`OLLAMA_HOST`, else `127.0.0.1:11434`), and gives the
  model its description. The model must be able to see (Ollama lists `vision` under
  *capabilities* in `ollama show <model>`).
- Shell history: `last_commands` reads the end of the history file written last, whichever shell
  wrote it: zsh (`~/.zsh_history`, `~/.histfile`, `$ZDOTDIR`, or `$HISTFILE` when exported), bash
  (`~/.bash_history`) or fish. Only the commands are there, not their output or whether they failed. A
  command that may hold a password, key or token (words like *token*, *password*, *api_key*, `gpg`,
  `pass`, a long random-looking string, a URL with a password) is shown to the model as *[hidden]*;
  start a command with a space to keep it out of the history altogether (`HIST_IGNORE_SPACE` in zsh,
  `HISTCONTROL=ignorespace` in bash; fish does it by default). zsh needs `INC_APPEND_HISTORY` or
  `SHARE_HISTORY` to write a command as soon as it ran (oh-my-zsh sets `SHARE_HISTORY`), and bash
  `PROMPT_COMMAND="history -a"`; otherwise the mascot sees a terminal's commands only after it closes.
- Only with a local model, one of aichat's `ollama` client (`ollama:…`), so what they read stays on
  your computer. With any other model (e.g. after `.model openrouter:…`) the mascot has neither, and
  its memory starts over first, so nothing it read goes along (`.todo` and `.remind` still work).
- Not in a `.session`, which outlives Mascot and may later go to any model.

The bubble always points aichat at these tools, never at your own llm-functions, and turns function
calling off when `CHAT_TOOLS` is empty, so none of your tools can write or run anything unconfirmed
from the bubble (aichat's tools only ask before they act in a terminal). The model has to support
function calling, and aichat has to know that: mark it in your aichat config, e.g.

```yaml
clients:
  - type: openai-compatible
    name: ollama
    api_base: http://localhost:11434/v1
    models:
      - name: my-model
        supports_function_calling: true
```

`function_calling: false` in the config may stay; the bubble turns it on for its own tools. aichat
lets a role's own `use_tools` override the global ones, so with tools the bubble sends your role as
`--prompt` with its front matter, Mascot's tools as `use_tools` and the role's model as `-m`. A memory
keeps the tools of its first message, so changing `CHAT_TOOLS` or the role starts it over. Some
models call tools more reliably than others; one that does not just answers without looking.

## Configuration

| Option | Default | Description |
|---|---|---|
| `CHAT_ENABLED` | `true` | `false` closes the bubble and stops taps from opening it; `true` starts it again. Takes effect without a restart. |
| `CHAT_COMMAND` | empty | The command that answers a message. |
| `CHAT_ROLE` | empty | The aichat role the bubble starts with (`-r`); empty means Mascot's prompt. Takes effect from the next tap. |
| `CHAT_MEMORY` | `8000` | About how many tokens a mascot's memory may hold before it is summed up (counted as 3 characters each, what the tools returned included); `0` never sums up. With a local model it is at most half the model's context (Ollama's `num_ctx`, or Ollama's default of 4096 tokens), which also holds the prompt, a file a tool reads and the reply; with a bigger model, raise it to use more. Takes effect from the next tap. |
| `CHAT_REMARKS` | `0` | A random mascot says something on its own every N to 2N minutes; `0` turns it off. Takes effect without a restart. |
| `CHAT_ROLES` | empty | A role per mascot, `<mascot>=<role>;…`, used instead of `CHAT_ROLE` for those mascots; an empty role means Mascot's prompt. Takes effect from the next tap. |
| `CHAT_TOOLS` | `time,weather` | What the mascot can use: `time`, `weather`, `files`, `todo`, `reminders`, `shell` and/or `sleep`, comma-separated; empty turns the tools off (see *Tools*). Takes effect from the next tap. |
| `CHAT_DOTFILES` | *(empty)* | The hidden files and directories the file tools may see, `;`-separated, e.g. `~/.zshrc;~/.config/hypr`; empty: none (see *Tools*). Takes effect from the next tap. |
| `BUBBLE_ENABLED` | `true` | Whether mascotd starts the bubble. Read when mascotd starts. |
| `BUBBLE_COMMAND` | empty | The command mascotd starts the bubble with; empty means `qs -p $(PREFIX)/share/mascot/ui`. |

The message is appended to `CHAT_COMMAND` as an argument, never parsed by the shell, and stdin is
closed. An empty `CHAT_COMMAND` means plain `aichat` with your normal config.

The bubble cannot answer aichat's prompts, so give it an aichat config that never waits for one,
e.g. a copy of yours in `~/.config/aichat-mascot/` (the bubble chooses the tools itself, see *Tools*):

```sh
mascot config set CHAT_COMMAND 'AICHAT_CONFIG_DIR="$HOME/.config/aichat-mascot" aichat'
```

## Blur on Hyprland (optional)

The bubble's layer namespace is `mascot-bubble`. With Hyprland 0.53 or newer:

```
layerrule = blur on, match:namespace mascot-bubble
layerrule = ignore_alpha 0.3, match:namespace mascot-bubble
```

## Colours

The bubble takes its colours from pywal (`~/.cache/wal/colors.json`) when it exists, and follows
the file when it changes. What you type is shown in `color4` (also used for the mascot's name and
the outline), the answer in the foreground colour, and the bubble's own messages and command output
in `color8`. Without pywal it uses built-in dark colours.

# Advanced usage

## Multihead usage

mascot supports multiple screens. However, some features may be disabled by default. Config provides following options:

- ALLOW_THROWING_MULTIHEAD: Allows throwing mascot between screens
- ALLOW_DRAGGING_MULTIHEAD: Allows dragging mascot between screens
- UNIFIED_OUTPUTS: Treats all outputs as one entity

You may want block one of displays from being used by mascot in runtime, so we have `mascot environment close` to disable one of outputs. mascot will ask you to select one of outputs by clicking on it. After this operation, you can't restore display unless you restart mascot or reconnect display to the system.

## Interpolation

mascot supports movement interpolation of mascots. You can enable it by setting INTERPOLATION_FRAMERATE to value that is not equal to 0. Values > 0 used as interpolation frame rate. -1 Picks output's refresh rate as interpolation frame rate. Values under -1 are not allowed.

## Tablets

mascot recognized pentablets as input method, so you can use it as input device. However, currently subsurfaces bugged under KDE when using them with wp-tablet-v2, so you may want to disable that feature by setting TABLETS_ENABLED to false.

## Mapping mouse buttons

You can map mouse button and tablet events (stylus down, stylus up) to different actions. For example you can remap right button to 0x01, so it will act as left button and etc.

## Using systemd socket

mascot can be activated on-demand through systemd socket. To enable it, use `systemctl --user enable --now mascotd.socket`.
This is optional and has not been tested with Mascot's changes; `mascot summon` starts the daemon by itself.

## Running overlay manually

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

# Features

These are upstream's features and measurements ("I" and "my implementation" refer to wl_shimeji's author).

1. Less CPU
    - Because of C and Wayland, I was able to make this program as lightweight as possible.
    - When compared to the original Shimeji, my implementation for same configuration uses in ~20 times less CPU.
    (Tested on AMD Ryzen 9 5900HX, 7 mascots. Original Shimeji used ~19% of one CPU core. My implementation used ~0.9% of one CPU core)
    (Do not trust these numbers, they can be different for your configuration)
2. Less RAM
    - Because of prototypes-based method, mascots use as less memory as possible.
    (Tested on AMD Ryzen 9 5900HX, 7 mascots. Original Shimeji ~880MiB. My implementation used ~56MiB)
    (Do not trust these numbers, they can be different for your configuration)
3. Fast VM-based condition evaluation:
    - I implemented simple virtual machine and bytecode compiler for javascript-like conditions used in the original Shimeji.
    - It's not as fast as native code, but it's faster than the original Shimeji.

## Configuration

On first start, the program will create a configuration file in the config directory.
Currently config file allows to:

- Enable/Disable mascot breeding
- Enable/Disable mascot dragging
- Enable/Disable IE interactions (doesn't make sense without plugins)
- Enable/Disable IE throwing (doesn't make sense without plugins)
- Enable/Disable cursor position tracking (doesn't make sense without plugins)
- Set max number of mascots
- Set IE Throw Policy (doesn't make sense without plugins)

All parameters except max number and IE Throw Policy is booleans.
IE Throw Policy and max number is integers.

I will not explain possible values for IE Throw Policy for now.

# Upstream's notes

The rest of this README is by CluelessCatBurger, the author of wl_shimeji, kept as written.
"I" is them, not the Mascot fork.

## TODO LIST

- [ ] Write documentation for plugins API
- [ ] Add more configuration options

## Notes

- About environment interaction: It will be available only through the plugins. Wayland protocol doesn't allow to interact with windows of other applications,
  and will NEVER allow it. It's a security feature. If you think that it makes Wayland bad, ask yourself a question: Why application even should have access to
  the windows of other applications? Try to find at least 5 apps that need this feature and then come back to me.
- About plugins: It will be .so files that will be loaded at runtime. It can implement any functionality to lookup positions of active window, pointer, etc.
  There is no way to make it portable. For example, you theoretically can use kdotool to get and move windows, but it's will work only under kwin.
- X11 support? No, X11 doesn't provide key features that I need for this project. You can try to implement it. For it to work, you need to implement each and every function from
  src/environment.h
- ~~Windows~~/Macos/FreeBSD/InsertYourOS support? If you will able somehow run Wayland on it or reimplement funcs defined in src/environment.h, then yes. I don't have any plans to do it.
- If you want to help me with this project, beware src/mascot_config_parser.c. I warned you. (No, really, even i don't understand what's going on there.)
- Windows support? After searching for a while, I found that there is a similar mechanism to wl_subcompositor in Windows called "DirectComposition".
  I will not implement it by myself, but if you want to try, you can do it.

## Blabbering section

### What is Shimeji?

Shimeji is a program that creates a little character that wanders around your desktop. It can be customized with different skins and can be set to interact with the desktop environment.

### Why did I start this project?

The original Shimeji is written in Java and very unoptimized. It uses a lot of CPU and memory.
For example, from cold start, in some configurations, setup from 7 mascots can eat up 880MiB of RAM and ~19% of one cpu core (AMD Ryzen 9 5900HX)

I think this is unacceptable for such a simple program.
Moreover, original Shimeji is starting lagging when too many mascots on the screen, and because each mascot is a SEPARATE WINDOW, it slow down entire
compositor, with probaility of crashing it.

Even if we close eyes on the graphics, the original Shimeji uses javascript for the conditions, so it's makes everything even slower.

### How my reimplementation is better?

When I started this project, i started with the idea of making it as fast and as lightweight as possible.
So i started to analyze the original Shimeji and found things that can be definitely improved.
For example, when original Shimeji creates a new mascot, it creates instance of the `Mascot` class. What's wrong with it?
Actually nothing, but if we check how instances of `Mascot` are created, we can see that each instance is holds it's own copy of configuration and all sprites.
This is a big problem, as configuration and sprites are not very small, so it's a waste of memory.

What we can do then to improve it? Answer is simple: Prototypes! Instead of copying configuration and sprites for each mascot, we can create a prototype of the mascot
and then reference it in the actual mascot, maintaining the same functionality, but with less memory usage.

So my entire reimplementation is based on this idea. I'm using prototypes for mascots, and only the necessary data is copied for each mascot.

But what about language and graphics? Why I choose C and Wayland from all the possible options?

#### Wayland

This is quite interesting story. When I started this project, i was very interested in the Wayland protocol and how it works.
But this is not enough to choose it as a base for the project, so why Wayland? The answer is subcompositors.
In Wayland, everything that shown on the screen is a surface with it's role. For example, the window is a surface with a role of `xdg_toplevel`.
But what if we want to make complex window with multiple layers? Usually, we need to rerender everything in region that need to be updated.
It's can be difficult, it is developer's responsibility to handle it, and you should be smarter than me to do it.
But in Wayland, we have a concept of subcompositors. Subcompositor is a method to make composite window from multiple surfaces, and it's compositor's
responsibility to handle how window should be rendered. We will return to this later.

Then, if we return to prototypes, we can also find that wayland from box allows us create buffer only from shared memory, but at the same time, we
can reuse same buffer for multiple surfaces. This is exactly what we need for prototypes! We create our buffer only once, and then we reuse for each mascot when we need to.

Then we can start to implement our shimeji project, and...

Oh. oh no. We forgot about nature of Wayland.
Wayland is protocol with security in mind. It's not like X11, where you can do everything you want with the windows.
So what can we do? Or rather, what can’t we do? We can't position our mascots freely on the screen as we don't have access to the window positions (at all).

So, then what we actually can do?
If we open wayland.app, we can see set of protocols that exists in the Wayland. Not each protocol is implemented in each compositor,
but lets see what it can offer us.

So, wlroots created wlr-layer-shell protocol. This protocol allows us to create overlays on the screen. If we can create fullscreen overlay with no input and fully transparent,
we can guarantee that pixel on the overlay is the same as pixel on the screen, so now we can set position of our mascots freely.
But i don't want to render anything, what then I can do?

Now we can return to the subcompositors. We can use subcompositor functionality to avoid manual rendering of mascots. Instead we create subsurface for each mascot
and then attach it to our overlay. Now we can set position of our mascots freely and we don't need to render anything manually, because we use precreated buffers for each possible sprite.

#### C

Now, when we decided to use Wayland, we need to choose language.
Oh, no language currently (Feb 2024) supports Wayland on same level as C (We need low level access to the Wayland protocol). Guess, I had no choice.
Anyway, it will economize memory and CPU usage, so it's not that bad.
That pretty much sums up why I choose C.

#### Conditions and expressions in configuration files

Original Shimeji includes a feature called "Using JavaScript in places where you should not use JavaScript". I not expert in Shimeji-ee, but i think that
one of the reasons why 7 mascots can eat up 880MiB of RAM. I will not test it, but i decided that i will not include javascript in my project. Even if it means
that i will be required to implement compiler of javascript and my own virtual machine for it.
So now we have our own virtual machine instead of javascript. It was great experience.

<!-- !kryeg14 SchizoUUH ✊ !bwaa -->
