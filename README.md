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

On the screenshot is Robo, Mascot's own mascot: you type, it answers; close the bubble while it answers and it
keeps thinking, then shows *NEW* until you click it to read the answer.

## Compositor support

Mascot needs a compositor with **wlr-layer-shell** and **wl_subcompositor**, so GNOME (Mutter) and
Gamescope will not work.

- **Hyprland** is what Mascot is developed and tested on (0.56). It works, with two known quirks:
  a mascot that overlaps the right or bottom edge of the screen is squashed instead of clipped
  ([hyprwm/Hyprland#10515](https://github.com/hyprwm/Hyprland/issues/10515)), and Mascot works around
  a Hyprland crash when the bubble closes while the pointer is over a mascot.
- **KDE Plasma, Sway and other wlroots compositors** are supported by upstream but have not been
  tested with Mascot's changes.

## Getting started

Mascot needs a Wayland compositor with layer-shell: Hyprland, Sway or another wlroots compositor, or KDE
Plasma (not GNOME). Three steps:

**1. Install it.** On Arch, from the AUR (with an AUR helper such as `yay` or `paru`):

```sh
yay -S mascot
```

Or from source (any distribution; on Arch the packages are named as below):

```sh
sudo pacman -S --needed base-devel git wayland wayland-protocols libarchive uthash python python-pillow quickshell aichat
git clone --recurse-submodules https://github.com/HexRebel/mascot.git
cd mascot
make -j$(nproc)
make PREFIX=$HOME/.local install    # then ~/.local/bin must be in your PATH
```

On **Debian 13 (trixie)**, Quickshell comes from `trixie-backports` and aichat from its GitHub releases (it is not
packaged in Debian):

```sh
echo "deb http://deb.debian.org/debian trixie-backports main" | sudo tee /etc/apt/sources.list.d/backports.list
sudo apt update
sudo apt install build-essential pkg-config git curl libwayland-dev libwayland-bin wayland-protocols \
    libarchive-dev uthash-dev python3 python3-pil
sudo apt install -t trixie-backports quickshell
curl -LO https://github.com/sigoden/aichat/releases/download/v0.30.0/aichat-v0.30.0-x86_64-unknown-linux-musl.tar.gz
tar xzf aichat-v0.30.0-x86_64-unknown-linux-musl.tar.gz
mkdir -p ~/.local/bin && install -m755 aichat ~/.local/bin/
```

then clone and build as above. Debian adds `~/.local/bin` to your PATH at login once it exists, so log out and in
again after the first install.

**2. Give it a language model to talk with.** The chat bubble talks through
[aichat](https://github.com/sigoden/aichat). The easiest way is to let Robo walk you through it:

```sh
mascot setup
```

It asks where the mascot should think (on this computer with Ollama, online, or both), which model, your language
and which tools Robo may use, shows what it will write, and writes nothing until you say yes. Online it knows
OpenRouter, Anthropic, OpenAI and Google, and checks your API key before saving it. If you already use aichat,
Mascot uses your config as it is and setup only asks about language and tools
(see [Setting up](docs/chat.md#setting-up)).

Or by hand, pick one:

- **Free and local, with Ollama** (runs on your own computer; a graphics card helps):

  ```sh
  sudo pacman -S ollama            # or ollama-rocm (AMD) / ollama-cuda (NVIDIA); elsewhere see ollama.com/download
  sudo systemctl enable --now ollama
  ollama pull llama3.2             # about 2 GB
  ```

  That is all: the first time you write to the mascot (step 3), it lists Ollama's models, and the one you
  pick becomes Mascot's own aichat config, `~/.local/share/mascot/aichat/config.yaml` (your own aichat
  config, if you make one later, comes first; Mascot never changes it).

- **Hosted, with [OpenRouter](https://openrouter.ai)** (needs an account and an API key from
  [openrouter.ai/keys](https://openrouter.ai/keys); you pay per message): put this in
  `~/.local/share/mascot/aichat/config.yaml`:

  ```yaml
  model: openrouter:anthropic/claude-haiku-5.5
  clients:
    - type: openai-compatible
      name: openrouter
      api_base: https://openrouter.ai/api/v1
      api_key: sk-or-your-key-here
      models:
        - name: anthropic/claude-haiku-5.5
          supports_function_calling: true
  ```

**3. Start Robo**, Mascot's own mascot:

```sh
mascot summon Robo        # starts Mascot and the chat bubble
```

Click Robo and write to it; `.help` in the bubble lists what you can do, and right-clicking Robo opens its
menu. `mascot stop` stops Mascot again. If Robo answers in a language you did not write in, tell it yours:
`mascot config set CHAT_LANGUAGE Danish` (see [the chat bubble's configuration](docs/chat.md#configuration)).

Mascot also ships with the original Shimeji; `mascot import <shimeji-ee pack.zip>` adds others (see
[Adding mascots](docs/mascots.md#adding-mascots)).

## Everyday use

```sh
mascot summon Robo          # one more Robo (or another mascot by name)
mascot prototypes list      # the mascots you have
mascot dismiss              # click a mascot to send it away (--all: every one)
mascot stop                 # stop Mascot and the bubble
```

In the bubble, Robo can look things up for you with tools: files in your home directory, the weather, the
computer itself (disks, memory, temperatures, why something does not work), a todo list and more. Type `.help` to
see the commands, and `.tools` to see which tools are on.

## More

- [The chat bubble](docs/chat.md): commands, the mascot's personality, tools, configuration, blur and colours
- [Using mascots](docs/mascots.md): adding and converting mascots, the right-click menu, sleep, multiple screens
- [Building and installing](docs/building.md): every requirement, packages and plugins
- [Robo](art/robo/README.md): how Mascot's own mascot is made
- [The protocol](docs/protocol.md) between `mascot`, the daemon and the bubble
- [Upstream](docs/upstream.md): wl_shimeji's features and its author's notes
- [Changelog](CHANGELOG.md)
