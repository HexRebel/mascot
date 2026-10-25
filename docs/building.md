# Building and installing

The short version is in the [README](../README.md#getting-started); this is the full list.

## Requirements

### Build requirements

- libwayland-client:
  - Arch: `pacman -S wayland`
  - Debian: `apt-get install libwayland-dev libwayland-bin`
  - Fedora: `dnf install libwayland-client wayland-devel`
- wayland-protocols:
  - Arch: `pacman -S wayland-protocols`
  - Debian: `apt-get install wayland-protocols` (or clone wayland-protocols and set WAYLAND_PROTOCOLS_DIR to its absolute path)
  - Fedora: `dnf install wayland-protocols-devel`
- libarchive:
  - Arch: `pacman -S libarchive`
  - Debian: `apt-get install libarchive-dev`
  - Fedora: `dnf install libarchive-devel`
- uthash:
  - Arch: `pacman -S uthash`
  - Debian: `apt-get install uthash-dev`
  - Fedora: `dnf install uthash-devel`

### Runtime requirements

Your compositor should *at least* support xdg-shell, wlr-layer-shell protocols, and provide wl_subcompositor interface.

### mascot (CLI) requirements

- python-pillow
  - Arch: `pacman -S python-pillow`
  - Debian: `apt-get install python3-pil`
  - Fedora: `dnf install python3-pillow`
- python >= 3.10

## Installing

### Packages

Mascot is on the AUR as [mascot](https://aur.archlinux.org/packages/mascot) (`yay -S mascot`); elsewhere, build it
from source (below).
The upstream project has packages of its own, which install wl_shimeji, not Mascot:
[wl_shimeji-git](https://aur.archlinux.org/packages/wl_shimeji-git) and
[wl_shimeji-plugin-kwinsupport](https://aur.archlinux.org/packages/wl_shimeji-plugin-kwinsupport) on the AUR,
and a Nix flake (see the [upstream README](https://github.com/CluelessCatBurger/wl_shimeji#readme)).

This repository still contains the upstream Nix flake, updated for the new names, but it has not
been built or tested since the fork.

## Building

From a checkout of this repository, with submodules (`git submodule update --init`):

```sh
make -j$(nproc)
sudo make install                    # to /usr/local
make PREFIX=$HOME/.local install     # or just for you, without sudo
```

`$(PREFIX)/bin` must be in your `PATH`, since `mascot` starts `mascotd` from there.
`make uninstall` removes the files again (pass the same `PREFIX`/`DESTDIR`).

## Plugins

You can also build plugins (everything in src/plugins subdirectories). They come from upstream
and only work on KDE; they build with Mascot but have not been tested with it.
Plugins are optional, but can provide such features as:

- Interactions with other applications' windows
- Get global mouse position

Currently mascots can't move windows as it is not supported by mascot.

Currently we have following plugins:

- src/plugins/kwinsupport - KDE integration using it's scripting API

### Dependencies for plugins

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

### Building plugins

```sh
make build-plugins -j$(nproc)
```

### Installing plugins

```sh
make install-plugins
```

