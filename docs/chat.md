# Chat bubble

Left-click (tap) a mascot and a speech bubble opens next to it. Type a message, press Enter, and
the answer from a language model is streamed into the bubble. The mascot sits still while the
bubble is open.

The bubble is a separate [Quickshell](https://quickshell.org/) project in `ui/`; `make install`
puts it in `$(PREFIX)/share/mascot/ui/`. The answers come from [aichat](https://github.com/sigoden/aichat),
so any model aichat supports works, including local ones through Ollama. With a local model, the
bubble asks Ollama (`OLLAMA_HOST`, else `127.0.0.1:11434`, with `curl`) to load it as soon as it
opens and keep it while it is open, and to unload it when it closes, so answers come quicker even
with `OLLAMA_KEEP_ALIVE=0` (and the model frees its memory again; should the bubble never say
so, after 10 minutes).

## Requirements

- Quickshell (`pacman -S quickshell`)
- aichat (`pacman -S aichat`), configured with at least one model
- Optional: pywal (`pacman -S python-pywal`) for colours that follow your theme (see [Colours](#colours))
- Optional: a Nerd Font (e.g. `pacman -S ttf-nerd-fonts-symbols`) for the bubble's icons, in your
  theme's colours; without one it shows emoji
- `curl`, with which the bubble asks Ollama to keep a local model loaded while it is open

## Starting and stopping

You do not start the bubble yourself: `mascotd` starts it (`qs -p $(PREFIX)/share/mascot/ui`) and
stops it again, so it runs exactly as long as Mascot does.

```sh
mascot summon Robo      # starts mascotd, which starts the bubble
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
| `.help` | The commands most people need; `.help all` lists every one |
| `.info` | Show Mascot's version (the running one's: restart Mascot after an update) and aichat's settings |
| `.models`, `.roles`, `.sessions` | List them |
| `.models <search>` | Find models on OpenRouter, newest first, with price, context and whether they can use tools, e.g. `.models gemini flash` |
| `.model <name>` | Switch model, e.g. `.model openrouter:…` |
| `.role <name>` | Switch to one of your aichat roles instead of Mascot's prompt |
| `.session <name>` | Use a named aichat session instead of the mascot's own memory (it is saved, so it outlives Mascot); started with a local model it is private (see *Tools*) |
| `.delete session <name>` | Delete one of aichat's sessions for good (its file in aichat's `sessions_dir`) |
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
for a name found with `.models <search>` in the bubble (e.g. `.models claude haiku`) or on
[openrouter.ai/models](https://openrouter.ai/models). Once it has answered, it is on the Model page from then on (the last
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
(aichat's `--prompt`), so the mascot answers in character, briefly and in your language (set `CHAT_LANGUAGE` if it guesses wrong, e.g. Norwegian for Danish). `{name}` in
the prompt becomes the mascot's name, so Shimeji answers as Shimeji. A mascot can bring its own prompt:
a `prompt.md` in its prototype directory comes first (Robo has one: a small, playful robot, which now
and then mentions its visor or its tools). Your aichat roles and
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
| `system` | `check_system`, `read_log` | Troubleshoot your computer when you ask: "why can't my game find the others on the LAN?", "why is there no sound?", "why does Steam keep crashing?", "why is my computer so loud?", "which governor is my CPU on?". It looks at the network (and firewall), sound, crashes, services, the machine (temperatures and fans, CPU and graphics card, memory, disks, the programs using the most) or power (the CPU's governor, energy preference, speed and boost, and the power profile), and searches the system log; it tells you what it found and the command that fixes it, and never runs it |

`CHAT_TOOLS` is `time,weather` by default; add `files` to let the mascot see your files, `todo`
for the todo list, `reminders` for reminders, `shell` for your last commands, `sleep` to let the
mascots nap and `system` for troubleshooting, e.g. `mascot config set CHAT_TOOLS
time,weather,files,todo,reminders,shell,sleep,system`, or set
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

The file, todo, reminder, shell and system tools keep to what is yours to share:

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
- System: `check_system` and `read_log` only read, as you, without `sudo`: the journal
  (`journalctl`; all of it if you are in the `wheel`, `adm` or `systemd-journal` group, else only your
  own), `coredumpctl`, `systemctl`, `ip`, `pactl`/`wpctl`, `/proc` and `/sys` (the machine's sensors,
  memory and disks) and the firewall's rule files (ufw's in
  `/etc/ufw`; firewalld and nftables need root, so it says it cannot see them). Every answer from them
  says what they could not see, and the mascot is told to say so rather than guess, and to give you
  the command to run yourself (with `sudo` when it needs it), never to say it ran it. Log lines are
  cut to the newest 60 (or what fits the model), and a value after *password*, *token*, *secret*,
  *api_key* and the like is shown as *[hidden]*. When they found nothing to go on, the mascot shows it
  does not know while it answers (Robo's "?").
- Only with a local model, one of aichat's `ollama` client (`ollama:…`), so what they read stays on
  your computer. With any other model (e.g. after `.model openrouter:…`) the mascot has neither, and
  its memory starts over first, so nothing it read goes along (`.todo` and `.remind` still work).
- In a `.session` (it outlives Mascot) only when it is private: a session whose first message went to
  a local model is private, has these tools, and only local models may go on with it - the bubble
  refuses to send a model online what it read, and choosing one switches to a local model (the
  default if it is local, else the local one used last). A session started with another model, or one Mascot
  did not start (made in a terminal), has none of them. Mascot keeps which is which in
  `~/.local/share/mascot/sessions`; aichat itself does not know, so do not open a private session in a
  terminal with a model online. Sessions are files with all that was said; keep them out of git
  (e.g. `.config/aichat/sessions/` in a dotfiles repo's `.gitignore`).

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
| `CHAT_MEMORY` | `8000` | About how many tokens a mascot's memory may hold before it is summed up (counted as 3 characters each, what the tools returned included); `0` never sums up. It is also at most half the model's context, which holds the prompt, a file a tool reads and the reply too: a local model's (Ollama's `num_ctx`, or Ollama's default of 4096 tokens) or one on OpenRouter's (from its list). It never grows past `CHAT_MEMORY`, even for a big model: the whole memory goes with every message, and online every token is paid for (raise it yourself to use more). `.info` in the bubble shows what applies. Not in a `.session`: aichat sums that up itself, past its `compress_threshold`. Takes effect from the next tap. |
| `CHAT_REMARKS` | `0` | A random mascot says something on its own every N to 2N minutes; `0` turns it off. Takes effect without a restart. |
| `CHAT_ROLES` | empty | A role per mascot, `<mascot>=<role>;…`, used instead of `CHAT_ROLE` for those mascots; an empty role means Mascot's prompt. Takes effect from the next tap. |
| `CHAT_TOOLS` | `time,weather` | What the mascot can use: `time`, `weather`, `files`, `todo`, `reminders`, `shell` and/or `sleep`, comma-separated; empty turns the tools off (see *Tools*). Takes effect from the next tap. |
| `CHAT_DOTFILES` | *(empty)* | The hidden files and directories the file tools may see, `;`-separated, e.g. `~/.zshrc;~/.config/hypr`; empty: none (see *Tools*). Takes effect from the next tap. |
| `CHAT_LANGUAGE` | *(empty)* | Your language, e.g. `Danish`: with a mascot's or Mascot's prompt (not your own roles) the model answers in it unless you write in another, and remarks use it. With tools, each tool's answer ends with a note to answer in it (also with your own roles). Empty: the mascot follows your messages, and remarks use your locale's language (e.g. English for `en_DK`). Takes effect from the next tap. |
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

