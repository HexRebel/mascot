# Changelog

Mascot's versions (`mascotd --version`). Mascot is a fork of
[wl_shimeji](https://github.com/CluelessCatBurger/wl_shimeji), which was at 0.0.2 when it forked.

## Unreleased

- `.info` (and the menu's Info) starts with Mascot's version: the running one's, so it shows when Mascot wants
  a restart after an update. `mascot --version` shows the installed one's.
- A dot command's output (`.info`, `.help all`, `.todo` ...) is read from the top: the bubble no longer scrolls
  past the command's line. Answers still follow the bottom.

## 0.4.0 (2026-10-25)

The mascot can look at the machine itself (temperatures, fans, memory, disks), Robo laughs, meditates and shows
ERROR, and the README is a short front page.

- Robo laughs, eyes shut tight, when a todo is done (`Done`, a new image): when the mascot takes an item off
  the todo list, and after `.todo done`. Other mascots can have a `Done` behaviour of their own.
- **The machine:** a new area for `check_system` (in `system`): temperatures and fans, how busy the CPU and
  graphics card are, memory, disks and the programs using the most, from `/proc` and `/sys` (any distribution;
  NVIDIA through `nvidia-smi`; laptops and ARM boards through their thermal zones; it says when it cannot see
  the CPU's temperature or the fans). `scripts/fake_machines.py` shows what it says on other hardware. Ask "why is my computer so loud?" or "is a disk full?". Robo holds up a
  magnifying glass over a graph while it checks (`Machine`, a new image).
- When an answer fails (no Ollama, no model...), Robo shows "ERROR" and a tear for a few seconds (`Failed`,
  a new image).
- Robo also meditates now and then while it hovers about, to look a bit more alive.
- Robo is the same size standing still and hanging straight as when it hovers and swings (it was about 5%
  smaller), and stays dizzy and grumpy a little longer after landing (about 1.5 seconds).
- Robo no longer jumps aside and shoots off along the floor now and then: it played Shimeji's pulling itself up,
  which it has no images for.
- Robo's "?" and "ERROR" read the right way round when it faces right (they were mirrored).
- With `CHAT_LANGUAGE`, each tool's answer to the model ends with a note to answer in it (gemma4 once drifted
  to Norwegian after a tool's English).
- Robo no longer blinks between gliding and a sleepy face when it creeps along the floor: it hovers, as it walks.
- The "?" (`Unsure`) and the laugh stay a few seconds after the answer, as meant: the end of the answer
  stopped them at once.
- The README is a short front page; the rest moved unchanged to `docs/` (the chat bubble, mascots, building,
  upstream).

## 0.3.0 (2026-10-24)

The mascot can troubleshoot your computer, Mascot installs on Debian 13, and a handful of fixes.

- **Troubleshooting:** a new tool group, `system` in `CHAT_TOOLS` (local models only): ask the mascot why
  something does not work - the network or a game's LAN, sound, a program that crashes, a service - and it
  looks with `check_system` (network and firewall, sound, crashes, services) and `read_log` (the system
  log). It only reads, without `sudo`, says what it could not see, and gives you the command that fixes
  it instead of running it; it is told to say it does not know rather than guess. Robo opens its chest
  while it checks (`System`), and shows a "?" (`Unsure`, a new image) when it found nothing to go on.
- The mascot now offers its tools when one could help, instead of waiting for you to know them.
- With tools, the mascot is told to answer in `CHAT_LANGUAGE` after the tools' English, also with a role of its
  own (gemma4 drifted from Danish to Norwegian), and the "?" stays a few seconds after a short answer.
- **Debian 13:** how to install on Debian in the README's Getting started (Quickshell from `trixie-backports`,
  aichat from its releases), tested in a clean Debian 13 container; the Debian package names under
  Requirements are corrected.
- The menu opened from a key (`mascot menu`) no longer marks its bottom row as well: the pointer resting over
  the mascot, under that row, counted as hovering it. From a key the pointer now counts once it moves, and
  then takes over the keyboard's choice.
- A sleeping mascot swapped for another (`.mascot`, the menu's Change mascot) no longer wakes up: the new one
  sleeps too.
- Reminders work with Quickshell 0.3.0 (Debian's): the bubble could not hand the reminder tool its
  environment there, so the tool refused to run and reminders never showed.
- The memory's summary no longer carries the model's reasoning (`<think>`) into the new conversation, where
  gemma4 answered it with raw template tokens.
- The bubble no longer counts the model's reasoning towards the memory limit (aichat never sends it to the
  model again), so it sums up later.

## 0.2.0 (2026-10-23)

Robo's own personality, and a smoother start for someone new to Mascot.

- **Robo's own personality:** a mascot can bring its own system prompt, a `prompt.md` in its prototype
  directory, used unless a role is chosen (`.role`, `CHAT_ROLES`, `CHAT_ROLE`). Robo has one: warm, curious
  and playful, a little robot now and then, in your language. `.info` shows it as the mascot's own prompt.
- **`CHAT_LANGUAGE`:** tell Mascot your language (e.g. `Danish`); the mascot answers in it unless you write in
  another, and its remarks use it. Without it, remarks now name the locale's language ("English" for `en_DK`)
  instead of its code, which made models guess Norwegian or Swedish.
- **A shorter `.help`:** the commands most people need, and how to reach the menu; `.help all` lists every
  command, as `.help` did, and is what the menu's Help shows.
- **On the AUR:** `yay -S mascot` (the package is in [`packaging/aur/mascot/`](packaging/aur/mascot/)).
- **Getting started** in the README, for someone new: install (AUR or source), give aichat a model (Ollama or
  OpenRouter, with a config to copy), start Robo.
- The bubble explains the errors someone new meets: aichat not set up or not installed, Ollama not running, a
  model that is not downloaded.
- When Mascot cannot start, `mascot` says why instead of `connector.error.initialization`, and on a desktop
  without wlr-layer-shell (GNOME) which desktops it works on.

## 0.1.0 (2026-10-23)

The first version of Mascot as its own program.

### Robo, Mascot's own mascot

- **Robo**, a small hovering robot whose visor shows how it feels, ships next to the original Shimeji
  (CC0; the prompts and the scripts that build it in [`art/robo/`](art/robo/), the source images on the
  releases page).
- While a tool runs for an answer, the mascot shows what it does (Robo's notepad for the todo list, the globe
  for the weather, a hologram cube for your files...): a prototype's `Todo`, `Reminder`,
  `Weather`, `Files`, `Search`, `Image`, `Shell` and `Sleepy` behaviors, and `Alarm` for a reminder that is due.
- Asleep for a while (Quiet, `mascot sleep -m`, the sleep tool), a mascot plays its `Quiet` behavior, if it has
  one (Robo switches off).

### The chat bubble

- Tap a mascot and a speech bubble opens next to it: chat with a language model through
  [aichat](https://github.com/sigoden/aichat), local (Ollama) or hosted (OpenRouter), streamed into the bubble
  while the mascot talks.
- Each mascot has its own memory and role (`CHAT_ROLES`), summed up when it grows too long; private
  sessions for local models.
- Dot commands (`.help`): models, roles, sessions, swapping the mascot, the todo list, reminders, Quiet,
  copying.
- Tools the model can call, read-only except for Mascot's own todo list and reminders: the time, the
  weather, your files and images (local models only), your last shell commands, sleep.
- Remarks: now and then a mascot says something on its own (`CHAT_REMARKS`).
- Closed while it answers, the mascot keeps thinking and then shows that the answer is ready (`Answered`).
- Thinking dots, what a tool is doing, Nerd Font icons, pywal colours, "✓ copied".

### The mascots

- A right-click menu: settings (mascot, model, role, session, tools), Stay, sleep and wake, Quiet, the todo
  list, reminders, Send away. Also from a key: `mascot menu`.
- Sleep: `mascot sleep` / `mascot wake` (e.g. from hypridle), a middle click, Quiet for a while.
- Tap versus drag: a tap opens the bubble, a drag picks the mascot up; dragging works with the bubble open.
- `mascot import` takes Shimeji-ee packs (zip or directory) directly, optionally without climbing
  (`--no-climb`), and picks the talk, answered and sleep poses (`--talk`, `--answered`, `--sleep`);
  `mascot prototypes set`, `poses`, `remove`.
- `mascot config get/set` works without the daemon.

### Fixed (also in upstream wl_shimeji)

- A mascot sent away while being dragged crashed the daemon.
- Three use-after-frees on reload, and a withdraw packet sent to every client (sent upstream as PR #69).
- A Move without a target hung the daemon; a behavior's own first action (Look, Jump, Fall...) crashed it;
  `SelectionCancel` sent the wrong opcode.

### Renamed

- `shimeji-overlayd` → `mascotd`, `shimejictl` → `mascot`, data in `~/.local/share/mascot`.
