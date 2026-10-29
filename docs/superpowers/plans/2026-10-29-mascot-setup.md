# `mascot setup` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `mascot setup` går i terminalen gennem hvor Robo tænker (lokalt/online/begge), model(ler), nøgle, sprog og
tools, skriver Mascots egen aichat-config og `CHAT_LANGUAGE`/`CHAT_TOOLS`, og slutter med næste skridt og Robo.

**Architecture:** Al logik ligger i et nyt modul, `src/mascotctl/chatsetup.py` (py-compose lægger det ind i
`utils/mascot`), opdelt i rene funktioner (config-tekst, sprog, læsning af den nuværende config), netværk (Ollama og
fire tjenester, med en test-adresse) og ét interaktivt forløb, `run_setup()`, der får sine input/output-funktioner
udefra, så det kan testes uden terminal. `client.py` tilføjer underkommandoen og kalder det, før daemonen startes.

**Tech Stack:** Python 3 (kun standardbiblioteket: `urllib`, `getpass`, `json`, `tempfile`), aichat 0.30, Ollama
HTTP-API, OpenRouter/Anthropic/OpenAI/Google HTTP-API'er.

**Spec:** `docs/superpowers/specs/2026-10-29-mascot-setup-design.md`

## Global Constraints

- Setup skriver **aldrig** i og læser **aldrig** brugerens egen aichat-config (`$AICHAT_CONFIG_DIR`, ellers
  `${XDG_CONFIG_HOME:-~/.config}/aichat/`) eller `.env`. Med `CHAT_COMMAND` eller egen config: ingen model-trin.
- Den eneste fil setup skriver: `$MASCOT_DATA_DIR/aichat/config.yaml` (standard `<config root>/aichat/`), mappe
  `700`, fil `600`, atomisk (temp i samme mappe, `600` før indhold, `os.replace`); en eksisterende flyttes til
  `config.yaml.old` (`600`). Plus `CHAT_LANGUAGE` og `CHAT_TOOLS` via `mascot config set`.
- Intet skrives før brugeren har svaret ja til "Write this? [Y/n]". Ctrl+C/Ctrl+D → "Nothing was changed.", exit 1.
- En nøgle: læses med `getpass`, `.strip()`'es, står aldrig i stdout/stderr, argv eller andre processers miljø;
  sendes kun til tjenestens egen vært over HTTPS; omdirigeringer følges ikke.
- Ingen `sudo`, ingen installation, ingen `ollama pull`. Tekst på engelsk. Robo er vært.
- Tools: `time, weather, files, todo, reminders, shell, sleep, system`; lokale (kun lokal model):
  `files, todo, reminders, shell, system`. Standard lokal: `time,weather,todo,reminders,sleep`; kun online:
  `time,weather,sleep`.
- Tjenester (id → aichat-type, model-præfiks): `openrouter` → `openai-compatible` navn `openrouter`
  (`https://openrouter.ai/api/v1`); `anthropic` → `claude`; `openai` → `openai`; `google` → `gemini`.
- Lokal er standardmodel ved "both".

## Review Focus

- En nøgle indsat med mellemrum eller linjeskift → den virker (strip), og fejlbeskeden viser den aldrig.
- Ugyldigt svar (bogstaver, 0, et for stort nummer, tom linje hvor et valg kræves) → spørg igen, ingen traceback.
- Mascots config lavet af boblens guide (kun Ollama) og setup køres med "online" → gammel gemt som `.old`, ny
  har kun online, og aichat kan læse den.
- `~/.local/share` findes ikke → mapperne laves (`700`), intet crash.
- Ollama svarer, men en tjeneste kan ikke nås (intet net) → "could not reach …", spørg igen eller spring over,
  ingen traceback.

---

### Task 1: Configen — tekst, læsning og skrivning

**Files:**
- Create: `src/mascotctl/chatsetup.py`
- Test: `scripts/test_setup.py`

**Interfaces:**
- Produces:
  - `TOOLS: list[str]` (de 8 i rækkefølgen ovenfor), `LOCAL_TOOLS: list[str]`, `TOOL_NOTES: dict[str, str]`
    (samme tekster som `.tools` i `ui/Bubble.qml`, uden "only with …"), `PROVIDERS: dict[str, dict]` med nøglerne
    `title`, `key_url`, `type` (aichat), `prefix` (model-præfiks, fx `openrouter`, `claude`, `openai`, `gemini`).
  - `@dataclass Online: provider: str; key: str; model: str; models: list[dict]` (`{"name": str, "tools": bool}`)
  - `@dataclass Choice: local_model: str | None; local_models: list[dict]; online: Online | None; default: str`
    (`"local"`/`"online"`)
  - `config_yaml(choice: Choice, ollama_base: str) -> str`
  - `read_current(directory: str) -> Choice | None` (kun Mascots egen fil; `None` hvis den mangler eller ikke kan
    læses)
  - `write_config(directory: str, text: str) -> str` (stien skrevet)

- [ ] **Step 1: Skriv de fejlende tests** i `scripts/test_setup.py` (samme opbygning som `scripts/test_guide.py`:
  `importlib` af `src/mascotctl/chatsetup.py`, tom HOME i `tempfile`):
  - `test_yaml_local`: `Choice("gemma4:12b", [{"name":"gemma4:12b","tools":True},{"name":"tiny","tools":False}], None, "local")`
    → indeholder `model: ollama:gemma4:12b`, `name: ollama`, `api_base: http://127.0.0.1:11434/v1`, og
    `supports_function_calling: true` kun under `gemma4:12b`.
  - `test_yaml_both_online_and_default`: med `Online("anthropic","k","claude-haiku-5-5",[...])` og `default="local"`
    → `model: ollama:…`, en `type: claude`-klient med `api_key: k`; med `default="online"` → `model: claude:claude-haiku-5-5`.
  - `test_yaml_openrouter`: `type: openai-compatible`, `name: openrouter`, `api_base: https://openrouter.ai/api/v1`,
    model `openrouter:anthropic/claude-haiku-5.5`.
  - `test_yaml_key_quoted`: en nøgle med `#` og `:` skrives som YAML-streng i dobbelte anførselstegn, og
    `read_current` læser den tilbage uændret.
  - `test_read_back`: `read_current` på en fil skrevet af `config_yaml` giver samme `Choice` (for local, online,
    both); på en fil skrevet af `tools/mascot-guide`s `config_text` giver den en lokal `Choice`.
  - `test_write_perms_and_old`: `write_config` i en mappe der ikke findes → mappe `0o700`, fil `0o600`; anden gang
    → `config.yaml.old` med det gamle indhold, `0o600`; ingen `.config.*`-temp-filer tilbage.
  - `test_aichat_reads_it` (spring over hvis `aichat` mangler): skriv local+online config, kør
    `aichat --list-models` med `AICHAT_CONFIG_DIR`, tom HOME og `XDG_CONFIG_HOME`, stdin `/dev/null` → begge
    modeller står i output, exit 0.

- [ ] **Step 2: Kør og se dem fejle**
  Run: `python3 -I scripts/test_setup.py -v`  Expected: FAIL (modulet findes ikke).

- [ ] **Step 3: Implementér** funktionerne ovenfor i `chatsetup.py`. YAML skrives som tekst (ingen PyYAML), alle
  strenge-værdier fra brugeren i dobbelte anførselstegn med `\\` og `"` escaped. `read_current` læser kun den form,
  `config_yaml` og `mascot-guide` skriver (linjebaseret), og giver `None` ved alt andet. `write_config`: `makedirs`
  `0o700` + `chmod`, `mkstemp(dir=…, prefix=".config.")`, `fchmod 0o600`, skriv, `os.replace` den gamle til `.old`
  (efter `chmod 0o600`) og så temp → `config.yaml`.

- [ ] **Step 4: Kør testene**  Run: `python3 -I scripts/test_setup.py -v`  Expected: alle PASS.

- [ ] **Step 5: Commit**  `git add src/mascotctl/chatsetup.py scripts/test_setup.py` —
  "Setup: Mascots aichat-config som tekst, læst og skrevet (700/600, .old)"

### Task 2: Netværk — Ollama og de fire tjenester

**Files:**
- Modify: `src/mascotctl/chatsetup.py`
- Test: `scripts/test_setup.py`

**Interfaces:**
- Consumes: `PROVIDERS` (Task 1).
- Produces:
  - `ollama_base() -> str` (fra `OLLAMA_HOST` som `mascot-guide`)
  - `ollama_models(base: str) -> list[dict] | None` (`{"name","tools","size"}`, `size` fra
    `details.parameter_size`, fx `"11.9B"` eller `""`; `None` hvis Ollama ikke svarer; kun `completion`-modeller,
    gammel Ollama uden `capabilities` som i `mascot-guide`)
  - `check_key(provider: str, key: str) -> int` (HTTP-status; `0` = kunne ikke nås)
  - `online_models(provider: str, key: str) -> list[dict]` (`{"name","tools"}`; `[]` ved fejl)
  - `RECOMMENDED: dict[str, list[str]]` — fx `openrouter: ["anthropic/claude-haiku-5.5", "google/gemini-3-flash",
    "openai/gpt-5-mini"]`; kun dem, der findes i svaret, vises øverst.

- [ ] **Step 1: Skriv de fejlende tests** med en falsk server (`ThreadingHTTPServer`), som både er Ollama og de
  fire tjenester. Tjenesternes adresse peges om med `MASCOT_SETUP_TEST_BASE=http://127.0.0.1:<port>` (kun til
  test: alle tjenesters vært erstattes af den; ellers bruges de rigtige HTTPS-adresser fra spec'en).
  - `test_ollama_models`: to modeller, én med `tools` → `[{"name":…,"tools":True,"size":"11.9B"}, …]`; ingen
    server → `None`.
  - `test_check_key_headers`: serveren noterer headers pr. sti; `openrouter` → `GET /api/v1/key` med
    `Authorization: Bearer good`; `anthropic` → `GET /v1/models` med `x-api-key` og `anthropic-version`; `openai`
    → `GET /v1/models` Bearer; `google` → `GET /v1beta/models` med `x-goog-api-key` og **ingen** `key=` i stien.
    Rigtig nøgle → 200, forkert → 401, ingen server → 0.
  - `test_no_redirect`: serveren svarer 302 til en anden vært → `check_key` giver 302 (følger ikke).
  - `test_online_models`: OpenRouter-svar med `supported_parameters` (`tools` eller ej) → `tools` sat derefter;
    OpenAI-liste med `gpt-…`, `o3`, `text-embedding-…`, `whisper-1` → kun de to første; Google med og uden
    `generateContent` → kun den første, navn uden `models/`-præfiks.

- [ ] **Step 2: Kør og se dem fejle**  Run: `python3 -I scripts/test_setup.py -v`  Expected: de nye FAIL.

- [ ] **Step 3: Implementér.** Én `urllib`-opener med en `HTTPRedirectHandler`, hvis `redirect_request` returnerer
  `None`, timeout 10 s. `HTTPError` → dens kode; `URLError`/`OSError`/`ValueError` → 0. Nøglen kun i headers.

- [ ] **Step 4: Kør testene**  Expected: alle PASS.

- [ ] **Step 5: Commit** — "Setup: Ollamas modeller, nøgletest og modeller hos fire tjenester"

### Task 3: Forløbet — `run_setup()`

**Files:**
- Modify: `src/mascotctl/chatsetup.py`
- Test: `scripts/test_setup.py`

**Interfaces:**
- Consumes: alt fra Task 1-2.
- Produces:
  - `language_from_locale(env: dict) -> str | None` (`LC_ALL` → `LC_MESSAGES` → `LANG`; tabel over mindst
    `da, de, en, es, fi, fr, it, ja, ko, nb, nl, nn, no, pl, pt, ru, sv, tr, uk, zh`; `nb/nn/no` → `Norwegian`)
  - `run_setup(config_root: str, ask: Callable[[str], str], ask_secret: Callable[[str], str],
    out: Callable[[str], None], set_option: Callable[[str, str], None], current: dict[str, str],
    env: dict) -> int` — `current` er de nuværende `CHAT_COMMAND`, `CHAT_LANGUAGE`, `CHAT_TOOLS` fra
    `mascotd.conf` (tom streng når ikke sat); returnerer exit-kode.

Forløbet og teksterne følger spec'ens *Forløbet* trin 1-9 og *Mine valg*. Mærkaterne (`robo`, `where`, `ollama`,
`model`, `online`, `key`, `lang`, `tools`, `next`) farves kun når `out` skriver til en tty og `NO_COLOR` ikke er sat
(farvelægningen sker i Task 4; her er `out` ren tekst). Hvert valg-spørgsmål gentages ved ugyldigt svar.

- [ ] **Step 1: Skriv de fejlende tests** med en `Script`-hjælper: en liste af svar, der gives til `ask` og
  `ask_secret` i rækkefølge (raiser `AssertionError` hvis der mangler et svar), alt `out` samlet i en streng, og
  `set_option`-kald noteret. Falsk Ollama/tjeneste fra Task 2.
  - `test_local`: svar `1`, `1` (model), `Danish`, `` (tools: standard), `y` → config med `ollama:` som standard,
    `set_option` kaldt med `("CHAT_LANGUAGE","Danish")` og `("CHAT_TOOLS","time,weather,todo,reminders,sleep")`,
    exit 0, output indeholder `mascot summon Robo`.
  - `test_online_openrouter`: `2`, `1` (OpenRouter), nøgle `" good\n"`, `1` (model), `` (sprog), `` , `y` →
    config med `openrouter:`, `CHAT_TOOLS` `time,weather,sleep`, ingen `CHAT_LANGUAGE`-kald; output nævner
    forbrugsloft; strengen `good` findes ikke i output.
  - `test_bad_key_then_good`: forkert nøgle → "did not work (HTTP 401)" og spørg igen; output indeholder ikke
    nøglen.
  - `test_both`: `3` → begge trin; config har standard `ollama:` og en online-klient; *next* nævner `.model`.
  - `test_invalid_answers`: `x`, `0`, `9`, `` før `1` ved "Where" → spurgt fire gange, ingen exception.
  - `test_tools_toggle`: lokal, tools-svar `3 7` → `files` slået til, `sleep` fra; kun online: et lokalt nummer →
    "only with a model on this computer", ikke slået til.
  - `test_own_config_skips_models`: egen `~/.config/aichat/config.yaml` → output "Using your own aichat config",
    første spørgsmål er sproget, ingen config skrevet; samme med `current["CHAT_COMMAND"]` sat.
  - `test_ctrl_c_writes_nothing`: `ask` raiser `KeyboardInterrupt` ved tools-trinnet (og en anden test: `EOFError`)
    → "Nothing was changed.", exit 1, ingen fil, ingen `set_option`.
  - `test_no_at_confirm`: `n` ved "Write this?" → intet skrevet, exit 1.
  - `test_rerun_keeps_key`: eksisterende config med OpenRouter-nøgle; svar `2`, `1`, `y` (keep), … → samme nøgle i
    den nye fil, `.old` findes, `ask_secret` aldrig kaldt; output indeholder ikke nøglen.
  - `test_another_service`: `2`, `5` → output nævner aichats docs, ingen nøgle spurgt; "only online" uden tjeneste
    → "Nothing to set up online"; med `3` fortsætter den med kun lokal.
  - `test_rerun_defaults`: eksisterende lokal config med `gemma4:12b` → Enter ved "Where" og model vælger det
    samme som før.
  - `test_no_ollama_stops`: lokal, ingen Ollama → "systemctl --user start ollama", exit 1, intet skrevet.
  - `test_language_from_locale`: `{"LANG":"da_DK.UTF-8"}` → `Danish`; `{"LC_ALL":"nb_NO.UTF-8","LANG":"en_US"}`
    → `Norwegian`; `{"LANG":"C"}` → `None`.

- [ ] **Step 2: Kør og se dem fejle**  Expected: de nye FAIL.

- [ ] **Step 3: Implementér `language_from_locale` og `run_setup`.** Al skrivning (`write_config`, `set_option`)
  sker først efter bekræftelsen; `KeyboardInterrupt`/`EOFError` fanges ét sted omkring hele forløbet.

- [ ] **Step 4: Kør testene**  Expected: alle PASS (også Task 1-2's og `python3 -I scripts/test_guide.py`).

- [ ] **Step 5: Commit** — "Setup: forløbet (hvor, model, nøgle, sprog, tools, next) med Robo som vært"

### Task 4: CLI'en — `mascot setup`, hjælp og hint

**Files:**
- Modify: `src/mascotctl/client.py` (import, subparser ved de andre `category.add_parser`, dispatch før `Client`
  ved `convert`-blokken ~l. 2525, `chat_help()`, `SETUP_HINT`)
- Generated: `utils/mascot` (`make`)
- Test: `scripts/test_setup.py`

**Interfaces:**
- Consumes: `run_setup`, `language_from_locale` (Task 3).
- Produces: `setup_handler(arguments: argparse.Namespace) -> int`.

- [ ] **Step 1: Skriv de fejlende tests** (kører `utils/mascot` som subprocess med tom HOME,
  `MASCOT_SETUP_TEST_BASE`, `-cr <tmp>`):
  - `test_cli_needs_tty`: `mascot -cr … setup` med stdin fra `/dev/null` → exit 1, stderr "run it in a terminal",
    ingen daemon startet (ingen socket i `XDG_RUNTIME_DIR`=tmp).
  - `test_cli_help_mentions_setup`: `mascot --help` → `mascot setup` står under *getting started*; uden config står
    `SETUP_HINT` med "mascot setup".
  - `test_cli_setup_via_pty` (med `pty.fork`): lokal, Enter-standarder, `y` → `<tmp>/aichat/config.yaml` findes og
    `mascotd.conf` har `chat_language=` og `chat_tools=…` (med daemonen ikke kørende).

- [ ] **Step 2: Kør og se dem fejle.**

- [ ] **Step 3: Implementér.** `from chatsetup import *` (py-compose inliner). Subparser `setup` (help: "Set up the
  chat: where the mascot thinks, the model, your language and its tools"). `setup_handler`: kræver
  `sys.stdin.isatty()`; `ask=input`, `ask_secret=getpass.getpass`, `out` = `print` med ANSI-mærkater når
  `sys.stdout.isatty()` og ikke `NO_COLOR`; `current` læst fra `mascotd.conf`; `set_option` kører
  `[sys.executable, os.path.realpath(sys.argv[0])] + <-s/-c/-cr som givet> + ["config", "set", key, value]`
  (virker med og uden daemon). Dispatches før `Client(...)`. `chat_help()`: første linje
  `mascot setup              set up the chat (model, language, tools)`. `SETUP_HINT`: "Chat is not set up yet; run
  mascot setup (or tap the mascot)." Kør `make`.

- [ ] **Step 4: Kør testene**  Expected: alle PASS.

- [ ] **Step 5: Commit** (`client.py`, `utils/mascot`, test) — "mascot setup i CLI'en; --help og hint nævner den"

### Task 5: Robo kan ikke læse nøglen — også med en anden `MASCOT_DATA_DIR`

**Files:**
- Modify: `tools/mascot-tools` (`check_path`, ~l. 143)
- Test: `scripts/test_setup.py`

- [ ] **Step 1: Skriv den fejlende test** `test_tools_block_data_dir_aichat`: `MASCOT_DATA_DIR=<home>/elsewhere`,
  `MASCOT_TOOLS_LOCAL=1`, kør `tools/bin/read_file` med `{"path": "<home>/elsewhere/aichat/config.yaml"}` → svaret
  siger "private", nøglen står ikke i stdout. Det samme for `aichat-sessions/` og for et symlink i home, der peger
  derind.

- [ ] **Step 2: Kør og se den fejle.**

- [ ] **Step 3: Implementér:** i `check_path` afvises også (som written og realpath) alt under
  `$MASCOT_DATA_DIR/aichat` og `$MASCOT_DATA_DIR/aichat-sessions`, når `MASCOT_DATA_DIR` er sat (samme besked som
  `is_secret`).

- [ ] **Step 4: Kør testene**  Expected: PASS.

- [ ] **Step 5: Commit** — "Tools: Mascots aichat-mapper er private, også med en anden MASCOT_DATA_DIR"

### Task 6: Pakke, boble, docs — og test i rigtig brug

**Files:**
- Create: `packaging/aur/mascot/mascot.install`
- Modify: `packaging/aur/mascot/PKGBUILD` (`install=mascot.install`), `.SRCINFO` (`makepkg --printsrcinfo`),
  `ui/Bubble.qml` (`guide()` ~l. 1082, `showModels()` ~l. 1096), `README.md` (*Getting started* trin 2),
  `docs/chat.md` (nyt afsnit *Setting up*), `CHANGELOG.md` (*Unreleased*)

- [ ] **Step 1:** `mascot.install`: `post_install() { echo "==> Run  mascot setup  to get started."; }` (intet ved
  upgrade). PKGBUILD + `.SRCINFO`.
- [ ] **Step 2:** Boblen: `no-ollama`-teksten's "For a hosted one instead: …" → "For a hosted one (OpenRouter,
  Anthropic, OpenAI, Google), or to choose step by step: run mascot setup in a terminal." `showModels()` får
  linjen "(mascot setup in a terminal has more choices)". `qmllint` uden fejl.
- [ ] **Step 3:** README trin 2 starter med `mascot setup` (de manuelle måder bliver stående under "or by hand");
  `docs/chat.md` *Setting up*: forløbet, hvor nøglen ligger (`~/.local/share/mascot/aichat/config.yaml`, `600`),
  at Robo ikke kan læse den, forbrugsloft hos OpenRouter, at Anthropic/OpenAI/Google ikke er testet med rigtige
  nøgler endnu; CHANGELOG.
- [ ] **Step 4: Rigtig test** (sig til brugeren først): `make PREFIX=$HOME/.local install`; i en terminal med tom
  `HOME`/`XDG_CONFIG_HOME` i scratchpad og `-cr`: lokal med rigtig Ollama → `mascot summon`-svar i boblen
  (indlejret Hyprland, varsl vinduet); OpenRouter kun med brugerens ok og nøgle (brugeren skriver den selv).
  I brugerens egen opsætning: `mascot setup` siger "Using your own aichat config", og hans `mascotd.conf` ændres
  kun ved hans ja. `bash -c '. packaging/aur/mascot/mascot.install; post_install'` viser beskeden (`makepkg` bygger
  fra tagget, så den rigtige pakke testes først ved 0.8.0).
- [ ] **Step 5: Commit** — "Setup: AUR-besked, boblen og docs nævner mascot setup"
