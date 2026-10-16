# Bundled prototypes

Everything in `prototypes/` is installed to `$(PREFIX)/share/mascot/prototypes/` and
loaded after the user's own prototype directory, so a user copy with the same name
takes precedence.

Prototype directories are ignored by git: only commit art whose license allows
redistribution, and list it here (`git add -f`).

| Prototype | Artist | Source | License |
|---|---|---|---|
| Shimeji.Shimeji | Yuki Yamada (Group Finity), 2009 | `DefaultMascot/` in [Shijima-Qt](https://github.com/pixelomer/Shijima-Qt); images identical to `img/Shimeji/` in [shimeji-ee](https://github.com/chaoskagami/shimeji-ee) | Original Shimeji license, zlib-style ([`LICENSE.txt`](Shimeji.Shimeji/LICENSE.txt)) |

Changes to Shimeji.Shimeji (as its license requires them to be marked): converted from
Shimeji-ee XML to this format with `mascot convert`, climbing/hanging behaviours disabled with
`scripts/noclimb.py`, `artist`/`description` set in `manifest.json`, and a `Talk` behaviour
(the existing `SitAndSpinHead` action, never picked at random) added for the chat bubble. Images
are unchanged apart from the conversion to QOI.
