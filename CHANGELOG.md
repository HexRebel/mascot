# Changelog

Mascot's versions (`mascotd --version`). Mascot is a fork of
[wl_shimeji](https://github.com/CluelessCatBurger/wl_shimeji), which was at 0.0.2 when it forked.

## Unreleased

- Security: Robo's tools run only when they are turned on in `CHAT_TOOLS`. aichat runs any of Mascot's tools the
  model asks for, not only the ones the bubble gave it, so with only time, weather and todo on, a local model
  could still read your files, shell history and logs.
- A listed directory has "- " before each name. gemma4 wrote `nowl.png` for `owl.png` in about half its answers,
  and never with the dashes.

## 0.8.0 (2026-10-29)

- `mascot setup`: Robo walks you through setting up the chat in the terminal, right after installing. Local with
  Ollama, online (OpenRouter, Anthropic, OpenAI or Google, with the API key checked before it is saved) or both;
  then your language and Robo's tools. Nothing is written until you say yes, and your own aichat config is never
  read or changed. The AUR package says to run it, and so does the bubble when no model is set up.
- Robo's file tools can no longer read Mascot's own chat config and sessions (where the API key is), also with
  another `MASCOT_DATA_DIR`.
- Security: importing a `.wlshm` pack from someone else could write files anywhere in your home directory (a
  member named `../../.bashrc` or with an absolute path) and overflow a buffer with its header. Mascot now refuses
  such a pack whole, both the CLI and the daemon. Inherited from wl_shimeji.
- Security: `mascot import` leaves a pack's own `prompt.md` out, so a mascot from someone else cannot choose
  what the model is told while it has your tools. Give an imported mascot a personality with a role.
- Security: a mascot pack with a sprite name over 128 characters overflowed a buffer when the daemon loaded it,
  so the daemon could not start while the pack was there. Inherited from wl_shimeji.
- Security: `mascot setup` makes Mascot's own directory private (700) when it is new, as mascotd does; the menu
  asks OpenRouter for its model list only when you have an OpenRouter model.
- Security: without `XDG_RUNTIME_DIR`, Mascot no longer puts its sockets in `/tmp` (where another user could make
  them first); it says so and stops, unless you give one with `-s`. The file tools no longer read a file that is
  also somewhere else under another name (a hard link).
- Security: the daemon no longer trusts the length a packet on its socket claims (it could read past what was
  sent), and reads only the bytes a packet has. Inherited from wl_shimeji.
- Security: names, tool arguments and errors in the bubble and the menu are shown as plain text, so a pack's name
  or text a model was fed can no longer make the bubble load an address from the net.
- Security: Ollama's cloud models (`…-cloud`) and an Ollama on another machine (`OLLAMA_HOST`) no longer count as
  local, so they do not get the tools that read your files, todo list and shell history; `mascot setup` and the
  bubble's guide no longer offer cloud models as "on this computer".
- Security: the file tools hide keys in the dotfiles you let the mascot see (`export OPENAI_API_KEY=...` in
  `~/.zshrc` shows as `[hidden]`, and searching for a key finds nothing), and keep out of more places with logins
  (Copilot, `hub`, gcloud, sops, doctl, Terraform, containers' `auth.json`, VS Code, fish's variables).
- Mascot says where its settings are, so you no longer need the docs to find them. `mascot --help` ends with how to
  start, the chat's settings (`CHAT_TOOLS`, `CHAT_LANGUAGE`, `CHAT_DOTFILES`, `CHAT_REMARKS`, `CHAT_ROLE`) and where
  your roles go. `.tools` shows every tool, on and off, and the command to change them; `.roles` says where to make
  your own, and that a role takes the place of the mascot's own personality.
- The mascot says how to turn a tool on when you ask for something it is turned off for (or that needs a local
  model), instead of only that it cannot. It never turns one on itself.
- Fixed: `.tools` showed nothing for the `system` tool, and the docs left it out of `CHAT_TOOLS`.

## 0.7.1 (2026-10-29)

One fix: the right-click menu lists the bubble's sessions.

- Fixed: the menu's Session page listed aichat's own sessions, not the bubble's
  (`~/.local/share/mascot/aichat-sessions`), and with Mascot's own aichat config the menu found no models,
  roles or sessions at all. The menu now asks aichat the way the bubble does.

## 0.7.0 (2026-10-28)

Mascot sets the chat up for you the first time, and the bubble's sessions move to a folder of Mascot's own.

- New to aichat? Write to the mascot and Mascot's guide sets the chat up: it lists Ollama's models and makes
  Mascot's own aichat config (`~/.local/share/mascot/aichat/config.yaml`) with the one you pick, or says
  what is missing first (aichat, Ollama, a model). Your own aichat config always comes first and is never
  changed. `mascot summon` says when the chat is not set up yet.
- The bubble's sessions (`.session <name>`) are kept in `~/.local/share/mascot/aichat-sessions` instead of
  aichat's own `sessions_dir`, so aichat in a terminal no longer sees them and cannot go on with a private
  one with a model online. Move the ones you made with the bubble there to keep them, e.g.
  `mv ~/.config/aichat/sessions/<name>.yaml ~/.local/share/mascot/aichat-sessions/`.

## 0.6.1 (2026-10-26)

One fix: the menu's Info, Todo list and the rest work the first time.

- Fixed: a menu item that opens the bubble with a command (Info, Todo list, Reminders, Help, Tools, a model,
  role or session) did nothing but open the bubble the first time after Mascot started. The command now waits
  until the bubble has asked aichat about the model.

## 0.6.0 (2026-10-26)

Robo comes back when the screen is turned on again and peeks out of a hole in the floor when he is summoned,
wraps himself in a blanket when it is freezing, blushes when you thank him, and two upstream bugs are fixed.

- Thank or praise Robo and he blushes (`Love`; was heart eyes, which he still makes now and then on the floor).
- Robo no longer takes out his notepad on his own while he walks around; only for the todo list.
- Summon Robo (`mascot summon Robo`, or back after the screen was off) and he peeks out of a hole in the floor
  for a moment instead of dropping from the top (`Appear`, one new image). Other figures can have one too;
  without it they fall as before. `-x`/`-y`/`--position` still put him where you say.
- Ask about the weather when it feels like 0 °C or colder, and Robo wraps himself in a blanket while he
  answers (`Cold`, one new image). Other figures can have one too.
- Turn the screen off and on again (or unplug it), and Robo comes back: when the last screen goes away, mascotd
  keeps running and summons the mascots again on the next screen, instead of sending them away. They come back
  awake, and the bubble starts a new conversation, as after a restart.
- Fixed (upstream bug): a mascot moved to a screen that had just been added, before it was ready, crashed
  mascotd (Hyprland swaps its stand-in screen for the real one when a screen is turned on again).
- Fixed (upstream bug): mascotd kept the screen's description, make and model as pointers into text Wayland
  frees, and sent the freed description to `mascot` at start and whenever a screen changed. Found with
  AddressSanitizer; it never crashed, but could give garbled text or a crash.

## 0.5.0 (2026-10-25)

The mascot can tell how the CPU is set to run, Robo gets heart eyes when you thank him, five new things to do on
the floor and an easter egg, and a few fixes (the jump while walking is really gone now).

- **Power:** a new area for `check_system` (in `system`): how the CPU is set to run, its governor, energy
  preference, speed and boost, and the power profile (platform_profile, power-profiles-daemon, tuned) and battery,
  read from `/sys`. Ask "which governor is my CPU on?". Robo holds up a magnifying glass while it checks, and shows
  "100% FULL POWER" when the governor or the profile is on performance (two new images).
- Thank Robo or praise him ("thanks!", "well done", "tusind tak ❤") and he gets heart eyes (`Love`). Only when
  the message is nothing but that, in the common languages: "thanks, but that was wrong" does not.
- An easter egg: click Robo quickly many times. Other figures can have one too (`EasterEgg`).
- Robo waves, puts on sunglasses, gets heart eyes, wonders and looks through binoculars now and then (five new
  images), and meditates for longer.
- A reminder says the time it was for (*⏰ 20:15 · timer, 10 min*), and the model no longer writes "the timer is
  going off now" into it.
- `.info` (and the menu's Info) starts with Mascot's version: the running one's, so it shows when Mascot wants
  a restart after an update. `mascot --version` shows the installed one's.
- A dot command's output (`.info`, `.help all`, `.todo` ...) is read from the top: the bubble no longer scrolls
  past the command's line. Answers still follow the bottom.
- Robo no longer pulls himself up now and then (a jump aside, a fall and a dizzy landing while he walks): 0.4.0
  meant to switch it off, but mascotd picks by the frequency in the list that names a behaviour.
- A mascot waiting with an answer (NEW) still waits after it is dragged: it is held again when it lands.
- Quiet switches off a mascot that is already asleep, too.
- Robo no longer laughs and shakes now and then on the floor (the image is gone).

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
