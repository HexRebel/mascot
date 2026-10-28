# Mascots guide ("Getting started") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** En ny bruger uden aichat-config kommer fra "mascotten er på skærmen" til "mascotten svarer": boblen
fortæller næste skridt og laver selv Mascots egen aichat-config ud fra en Ollama-model brugeren vælger.

**Architecture:** Al afgørelse og filskrivning ligger i et lille Python-script, `tools/mascot-guide` (`status`,
`write`), der kan testes uden Wayland. Boblen (`ui/Bubble.qml`) kalder det, når `CHAT_COMMAND` er tom, viser
trinnet eller listen, og kører aichat med `AICHAT_CONFIG_DIR` = Mascots mappe, når det er den config der bruges.
CLI'en (`src/mascotctl/client.py`) skriver én linje ved `summon`, når chatten ikke er sat op.

**Tech Stack:** Python 3 (kun standardbiblioteket), QML/Quickshell, aichat 0.30, Ollama HTTP-API.

**Spec:** `docs/superpowers/specs/2026-10-28-getting-started-design.md`

## Global Constraints

- Mascot skriver **aldrig** i brugerens egen aichat-config og læser aldrig `.env` eller config-indholdet.
- Den eneste fil guiden skriver: `$MASCOT_DATA_DIR/aichat/config.yaml` (standard `~/.local/share/mascot/aichat/`),
  mappe 700, fil 600, atomisk (temp + rename), aldrig over en eksisterende fil.
- Rækkefølge: `CHAT_COMMAND` sat → den; ellers brugerens `config.yaml` (`$AICHAT_CONFIG_DIR`, ellers
  `${XDG_CONFIG_HOME:-~/.config}/aichat/`) → den; ellers Mascots → med `AICHAT_CONFIG_DIR`; ellers guiden.
- Tekster: engelsk, neutrale (ikke Robos stemme), korte, hvert trin med den præcise kommando eller fil.
- Distro-neutral: ingen pakkemanager-kald; Arch-pakker kun som eksempel ved siden af ollama.com.
- QML: brug aldrig `environment:`-binding; miljø via `createObject(…, {environment})` (som `run()` gør).
- Ollama: `$OLLAMA_HOST` (med eller uden `http://`), ellers `127.0.0.1:11434` — som `ollama()` i Bubble.qml.
- Ingen beskeder til brugere med egen config, intet grafikkort-tjek (brugerens beslutninger).
- Intet push før brugeren har testet (brugerens krav). Commits er lokale.

## Review Focus

- Ollama kører, men `/api/show` fejler for én model (fx halvt hentet): den model springes over, resten vises.
- Brugeren skriver noget, der ikke er et tal eller et modelnavn, mens listen vises: listen vises igen, intet
  skrives.
- Mascots config findes allerede (guiden har kørt), og Ollama er senere slukket: ingen guide, aichat fejler
  som i dag med `explained()`'s tekst.
- En bemærkning (remark) fyrer, mens chatten ikke er sat op: intet vises, intet aichat-kald.
- `OLLAMA_HOST=0.0.0.0:11434` (uden skema) eller `http://host:port/`: begge virker.

---

### Task 1: `tools/mascot-guide` — afgør tilstanden og skriv config'en

**Files:**
- Create: `tools/mascot-guide` (eksekverbar, `#!/usr/bin/env python3`, samme stil som `tools/mascot-tools`)
- Create: `scripts/test_guide.py` (unittest; falsk Ollama med `http.server` i en tråd; kører scriptet som
  subproces med `HOME`, `XDG_CONFIG_HOME`, `MASCOT_DATA_DIR`, `OLLAMA_HOST`, `PATH` sat til mapper i en tempdir)
- Modify: `Makefile:148-151` (installér `mascot-guide` 755 i `share/mascot/tools/`; fjern i `uninstall`)
- Modify: `tools/mascot-tools:68` (SECRET_DIRS: `.local/share/mascot/aichat`)

**Interfaces:**
- Produces: `mascot-guide status` → én linje JSON på stdout, exit 0:
  `{"state": S, "config": P, "models": [{"name": N, "tools": B}]}` hvor S er
  `"own"` (brugerens config findes; `config` = dens sti) · `"mascot"` (Mascots findes; `config` = dens mappe) ·
  `"no-aichat"` (`aichat` ikke på PATH) · `"no-ollama"` (Ollama svarer ikke inden 3 s) · `"no-models"` (ingen
  model kan chatte) · `"choose"` (`models` = dem der kan chatte, sorteret efter navn). `models` er `[]` undtagen
  ved `"choose"`; `config` er `""` ved de fire sidste.
- Produces: `mascot-guide write <model>` → skriver Mascots config med alle chat-modeller, `<model>` som standard;
  stdout: mappens sti; exit 0. Exit 1 + besked på stderr hvis filen findes, `<model>` ikke er blandt
  chat-modellerne, eller Ollama ikke svarer.
- Models: "kan chatte" = `"completion"` i `POST /api/show` `{"model": N}` → `capabilities`; "tools" = `"tools"`
  i samme liste. Fejler `/api/show` for en model, springes den over.

- [ ] **Step 1: Skriv de fejlende tests i `scripts/test_guide.py`**

  `test_own_config_wins` (fil i `$XDG_CONFIG_HOME/aichat/config.yaml` og en Mascot-config → `state == "own"`),
  `test_aichat_config_dir_env` (`AICHAT_CONFIG_DIR=<d>` med `<d>/config.yaml` → `"own"`, `config ==
  "<d>/config.yaml"`), `test_mascot_config` (kun Mascots → `"mascot"`), `test_no_aichat` (PATH uden `aichat`
  → `"no-aichat"`), `test_no_ollama` (OLLAMA_HOST til en lukket port → `"no-ollama"`), `test_no_models`
  (kun en embedding-model, `capabilities: ["embedding"]` → `"no-models"`), `test_choose` (`gemma4:latest`
  `["completion","tools"]`, `llama2:7b` `["completion"]`, `nomic-embed-text` `["embedding"]`, `broken` hvor
  `/api/show` svarer 500 → `models == [{"name":"gemma4:latest","tools":true},{"name":"llama2:7b","tools":false}]`),
  `test_ollama_host_forms` (`127.0.0.1:P` og `http://127.0.0.1:P/` giver begge `"choose"`),
  `test_write` (efter `write llama2:7b`: filen findes, mode 600, mappe 700, `yaml`-teksten indeholder
  `model: ollama:llama2:7b`, `- name: gemma4:latest` efterfulgt af `supports_function_calling: true`, og
  `- name: llama2:7b` **uden** den linje; `status` giver nu `"mascot"`), `test_write_never_overwrites`
  (eksisterende fil med `x` → exit 1, indhold stadig `x`), `test_write_unknown_model` (exit 1, ingen fil).
  En falsk `aichat` på PATH er bare et `#!/bin/sh`-script i tempdir'en.

- [ ] **Step 2: Kør dem og se dem fejle**

  Run: `python3 -I scripts/test_guide.py -v`
  Expected: FAIL (scriptet findes ikke).

- [ ] **Step 3: Skriv `tools/mascot-guide`**

  `main(argv)` med `status`/`write`. Config'ens tekst er præcis spec'ens blok (`model:`, `clients:`, én
  `openai-compatible` med `name: ollama`, `api_base: <ollama>/v1`, `models:`), med
  `supports_function_calling: true` kun ved `tools`. Atomisk: `tempfile.mkstemp(dir=…)` → `os.fchmod 0o600` →
  skriv → `os.link(tmp, final)` (fejler hvis final findes) → `os.unlink(tmp)`. `urllib.request` med timeout 3 s.

- [ ] **Step 4: Kør testene**

  Run: `python3 -I scripts/test_guide.py -v` — Expected: alle OK.

- [ ] **Step 5: Installér i scratchpad og tjek Makefile**

  Run: `make PREFIX=<scratchpad>/prefix install && ls -l <scratchpad>/prefix/share/mascot/tools/mascot-guide`
  Expected: `-rwxr-xr-x`.

- [ ] **Step 6: Commit** — `git add tools/mascot-guide scripts/test_guide.py Makefile tools/mascot-tools`,
  besked på dansk som de andre ("Guide: mascot-guide afgør om chatten er sat op og skriver Mascots aichat-config").

### Task 2: Boblen bruger guiden

**Files:**
- Modify: `ui/Bubble.qml` — `ask()` (~l. 941), `remark()` (~l. 337), `run()` (~l. 1153), `explained()` (~l. 1701),
  ny `property` og funktioner ved `sessionsDir`.

**Interfaces:**
- Consumes: `mascot-guide status` / `write <model>` (Task 1), kørt via `run([...], false, "", done, c,
  `${bubble.toolsDir}/mascot-guide`)` (som `deleteSession()` kører `rm`).
- Produces (i Bubble.qml): `property string chatSetup` (`""` ukendt, ellers sidste `state`),
  `property var guideModels: []`, `property string guidePending: ""` (beskeden der venter),
  `readonly property string mascotAichatDir: `${bubble.dataDir}/aichat``,
  `function guide(c: QtObject, text: string): void`, `function guideChoice(c: QtObject, text: string): bool`.

- [ ] **Step 1: `run()` sætter `AICHAT_CONFIG_DIR: bubble.mascotAichatDir`**, når `!bubble.event?.command` og
  `bubble.chatSetup === "mascot"` (lagt i samme `Object.assign` som `AICHAT_SESSIONS_DIR`, før `env`).

- [ ] **Step 2: `ask()`**: er `bubble.event?.command` tom og `chatSetup` hverken `"own"` eller `"mascot"`, kald
  `guide(c, text)` i stedet for at spørge aichat. `guide()` kører `status`, sætter `chatSetup`, og:
  `own`/`mascot` → `bubble.lookups = {}` og fortsæt med `ask(text, kind)` som før · `choose` →
  `guidePending = text`, `guideModels = models`, systemlinje med nummereret liste ("Mascot needs a language
  model to chat. Ollama has these - type a number to use one:") · de tre andre → én systemlinje hver med
  trinnet (tekster: spec'ens *Guiden i boblen*; `no-models` nævner ingen bestemt model, men `ollama pull
  <model>` + ollama.com/library; alle tre slutter med "then write again").
  `status` checkes ved hvert `ask()` indtil den giver `own`/`mascot` (så "kør `ollama serve` og skriv igen"
  virker), derefter ikke mere i denne boble.

- [ ] **Step 3: `send()`**: mens `guideModels.length`, går beskeden (der ikke starter med `.`) til
  `guideChoice()`: et tal 1–n eller et præcist modelnavn → `write <navn>`; ok → systemlinje "Made Mascot's
  aichat config with <navn>: <sti>/config.yaml", `chatSetup = "mascot"`, `guideModels = []`, `lookups = {}`,
  og `ask(guidePending, "reply")`. Fejl → linjen fra stderr. Andet input → listen igen.

- [ ] **Step 4: `remark()`**: returnér uden at gøre noget, når `CHAT_COMMAND` er tom og `chatSetup` ikke er
  `"own"`/`"mascot"`.

- [ ] **Step 5: `explained()`**: `"Failed to load config"`- og `"not found"`-teksterne henviser ikke længere til
  README'en, men til at skrive til mascotten igen (guiden tager over); ordlyd kort og neutral.

- [ ] **Step 6: Tjek at boblen loader** — Run: `qs -p ui --no-duplicate` er ikke muligt uden en kørende daemon;
  brug i stedet `qmllint ui/Bubble.qml` hvis det findes, ellers indlæs i den indlejrede test i Task 4.
  Expected: ingen nye fejl.

- [ ] **Step 7: Commit** — "Boblen: guiden laver Mascots aichat-config, når chatten ikke er sat op".

### Task 3: Terminalen og docs

**Files:**
- Modify: `src/mascotctl/client.py` — `mascot_handler` `case "summon"` (~l. 1636), og hvor `parser.print_help()`
  kaldes uden kategori.
- Modify: `README.md` (trin 2, ~l. 72-108), `docs/chat.md` (opsætning og `CHAT_COMMAND`, ~l. 296-304),
  `CHANGELOG.md` (*Unreleased*).

**Interfaces:**
- Produces: `def chat_is_set_up(config_root: str) -> bool` i `client.py`: sand hvis `chat_command` i
  `<config_root>/mascotd.conf` ikke er tom, eller brugerens aichat-`config.yaml` findes (samme sti-regel som
  Task 1), eller `<config_root>/aichat/config.yaml` findes. Bevidst en lille kopi af Task 1's regel (CLI'en kender
  ikke `tools/`-stien); en kommentar siger det.

- [ ] **Step 1: Test** — tilføj `test_cli_chat_is_set_up` i `scripts/test_guide.py`: importér `client.py` via
  `importlib` fra `src/mascotctl/` og tjek de fire tilfælde (intet → False; hver af de tre → True).
- [ ] **Step 2: Kør — FAIL. Step 3: implementér; efter et vellykket `summon` (og over hjælpeteksten uden
  argumenter) skrives `Chat is not set up yet; tap the mascot to set it up.` på stderr, når `False`. Step 4:
  Kør — PASS.**
- [ ] **Step 5: Docs** — README trin 2: "tap the mascot; it lists Ollama's models and sets aichat up for Mascot";
  Ollama-installationen (inkl. `ollama-cuda`/`ollama-rocm`) og OpenRouter-blokken bliver, men OpenRouter-filen
  er nu `~/.local/share/mascot/aichat/config.yaml` *eller* ens egen. `docs/chat.md`: rækkefølgen af config'er og
  at Mascots egen ligger i `~/.local/share/mascot/aichat/`. CHANGELOG *Unreleased*: én linje.
- [ ] **Step 6: Commit** — "Terminalen siger til, når chatten ikke er sat op; README og docs om guiden".

### Task 4: Test som ny bruger (før noget push)

- [ ] **Step 1:** ASan er ikke nødvendigt. Byg og installér i `<scratchpad>/prefix`. Lav en tom `HOME` i
  scratchpad (ingen `~/.config/aichat`, ingen `mascotd.conf`).
- [ ] **Step 2:** **Sig til brugeren, før et indlejret Hyprland-vindue åbner.** Start det med den tomme `HOME`,
  `mascot summon Robo` → terminal-linjen vises. Tryk på Robo og skriv "hej":
  a) Ollama stoppet (`OLLAMA_HOST` til en lukket port) → no-ollama-trinnet;
  b) rigtig Ollama → listen (gemma4-16k, gemma4:12b, ministral…); skriv `1` → "Made Mascot's aichat config…",
  derefter svarer Robo på "hej"; `ls -l` viser 700/600; tools virker (spørg om klokken → `time`-tool);
  c) skriv "abc" mens listen vises → listen igen.
  **Sig til, når vinduet må lukkes.** Slet ikke den tomme `HOME` før brugeren har set resultatet.
- [ ] **Step 3:** Installér i `~/.local` og bekræft, at **intet** ændrer sig for brugeren (`CHAT_COMMAND` er sat →
  ingen guide, `.sessions` viser de 5).
- [ ] **Step 4:** Brugeren tester selv. Først derefter: spørg om push / ny version.
