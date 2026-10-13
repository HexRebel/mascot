# Reproducer: segfault in `CInputManager::refocusLastWindow()`

Hyprland crashes when a layer surface with keyboard focus goes away while the cursor
is over a `wl_subsurface` of **another** layer surface.

`repro.c` is a self-contained Wayland client (about 200 lines, only `libwayland-client`)
that creates two overlay layer surfaces:

| | Where | What |
|---|---|---|
| A | (300, 300), 200×200 | grey layer surface, no keyboard interactivity, covered by a red **subsurface** |
| B | (0, 0), 240×80 | blue layer surface with **exclusive** keyboard interactivity |

After 5 seconds it destroys B. If the cursor is on the red square at that moment, Hyprland
segfaults. With the cursor anywhere else, nothing happens.

## Build

You need a C compiler, `wayland-scanner`, `libwayland-client` and the `wayland-protocols`
package (for `xdg-shell.xml`, which the layer-shell protocol refers to).

```sh
curl -LO https://gitlab.freedesktop.org/wlroots/wlr-protocols/-/raw/master/unstable/wlr-layer-shell-unstable-v1.xml
P=$(pkg-config --variable=pkgdatadir wayland-protocols)

wayland-scanner client-header wlr-layer-shell-unstable-v1.xml wlr-layer-shell-unstable-v1-client-protocol.h
wayland-scanner private-code  wlr-layer-shell-unstable-v1.xml wlr-layer-shell-unstable-v1-protocol.c
wayland-scanner private-code  $P/stable/xdg-shell/xdg-shell.xml xdg-shell-protocol.c

cc -I. repro.c wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c -lwayland-client -o repro
```

## Run

It is safest in a nested Hyprland, because the compositor crashes. `hyprland.conf` in this
directory is a minimal config for that.

1. In your Hyprland session, start a nested one:
   ```sh
   Hyprland -c hyprland.conf
   ```
   A new window opens. Note its Wayland socket (usually `wayland-2`, see `ls $XDG_RUNTIME_DIR`)
   and its instance signature (the newest directory in `$XDG_RUNTIME_DIR/hypr/`).
2. In a terminal outside the nested Hyprland:
   ```sh
   export WAYLAND_DISPLAY=wayland-2
   export HYPRLAND_INSTANCE_SIGNATURE=<signature of the nested instance>
   ./repro &
   sleep 1
   hyprctl dispatch movecursor 400 400   # onto the red square
   ```
3. When `repro` prints `B destroyed.`, the nested Hyprland segfaults and `repro` prints
   `Lost the connection to the compositor`.

As a control, run step 2 with `hyprctl dispatch movecursor 1000 600` instead: B goes away,
`repro` prints `Compositor still alive.` and nothing happens.

Do not run `./repro` in your real session with the cursor on the red square: the same code
path crashed a real session three times before it was narrowed down to this.

## Result

Hyprland v0.56.2 (`efb50993`), Arch Linux: crashes on every attempt with the cursor on the
subsurface, never with the cursor elsewhere. `hyprlandCrashReport.txt` is Hyprland's own crash
report from one run:

```
#4 | Desktop::View::CWLSurface::keyboardFocusable() const +0x19
#5 | CInputManager::refocusLastWindow(...) +0x240
#6 | Desktop::View::CLayerSurface::onUnmap() +0xde4
#7 | Desktop::View::CLayerSurface::onDestroy() +0x178
```

On `main`, PR #16311 (`f33e6a0`, after v0.56.2) gives subsurfaces of layer surfaces their own
view, which probably avoids the crash. This has not been tested against a build that contains it.
