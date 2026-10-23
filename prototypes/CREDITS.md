# Bundled prototypes

Everything in `prototypes/` is installed to `$(PREFIX)/share/mascot/prototypes/` and
loaded after the user's own prototype directory, so a user copy with the same name
takes precedence.

Prototype directories are ignored by git: only commit art whose license allows
redistribution, and list it here (`git add -f`).

| Prototype | Artist | Source | License |
|---|---|---|---|
| Shimeji.Robo | HexRebel, made with Google Gemini 3.1 Flash Image (through OpenRouter) from text prompts, 2026 | [`art/robo/`](../art/robo/) (prompts and the scripts that build it; the source images are `robo-sources.zip` on the [releases](https://github.com/HexRebel/mascot/releases)) | CC0 1.0 ([`LICENSE.txt`](Shimeji.Robo/LICENSE.txt)) |
| Shimeji.Shimeji | Yuki Yamada (Group Finity), 2009 | `DefaultMascot/` in [Shijima-Qt](https://github.com/pixelomer/Shijima-Qt); images identical to `img/Shimeji/` in [shimeji-ee](https://github.com/chaoskagami/shimeji-ee) | Original Shimeji license, zlib-style ([`LICENSE.txt`](Shimeji.Shimeji/LICENSE.txt)) |

Changes to Shimeji.Shimeji (as its license requires them to be marked): converted from
Shimeji-ee XML to this format with `mascot convert`, climbing/hanging behaviours disabled with
`scripts/noclimb.py`, `artist`/`description` set in `manifest.json`, and a `Talk` and an
`Answered` behaviour (the existing `SitAndSpinHead` and `SitAndFaceMouse` actions, never picked
at random) added for the chat bubble. Images
are unchanged apart from the conversion to QOI.

Robo is Mascot's own mascot. It was generated from text prompts only (no image by anyone else was given
to the generator; see [`art/robo/PROMPTS.md`](../art/robo/PROMPTS.md)), and the square on its chest
was replaced by a speech bubble afterwards. If you think it looks too much like your work anyway,
please [open an issue](https://github.com/HexRebel/mascot/issues) and we will change or remove it.
