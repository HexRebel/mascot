# Changelog

Mascot's versions (`mascotd --version`). Mascot is a fork of
[wl_shimeji](https://github.com/CluelessCatBurger/wl_shimeji), which was at 0.0.2 when it forked.

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
