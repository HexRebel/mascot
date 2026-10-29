# `mascot setup` — design

Dato: 2026-10-29. Status: udkast, venter på brugerens godkendelse. Mål: Mascot 0.8.0 (efter
sikkerhedsgennemgangen, som også gennemgår dette).

## Hvorfor

Brian (testperson, CachyOS, `yay -S mascot`) ledte i terminalen efter, hvordan man sætter Mascot op: `mascot
--help`, `mascot --help all`. Terminalen siger kun "tap the mascot to set it up"; resten sker i boblen (guiden fra
0.7.0), og kun for Ollama. Han nævnte Astros `npm create astro` som eksempel (`~/hyprshots/eksempel.png`): ét
program spørger trin for trin, viser svarene, slutter med "next" og en lille maskot (Houston).

Målet: lige efter installationen kører man `mascot setup`, svarer på nogle få spørgsmål og har en Robo, der svarer
på ens sprog, med den model og de tools man har valgt — lokalt, online eller begge — uden at læse docs.

## Mål

- Én kommando, `mascot setup`, der i terminalen går gennem: hvor Robo tænker → model(ler) → sprog → tools →
  opsummering og næste skridt.
- Tre valg for hvor Robo tænker (brugerens): **på denne computer (Ollama)**, **online**, **begge** (lokal er
  standard ved begge — brugerens beslutning).
- Online-tjenester (brugerens beslutning, "Mascot handler ikke kun om mig længere"): **OpenRouter** (anbefalet),
  **Anthropic**, **OpenAI**, **Google**, plus **"en anden"**, der henviser til aichats egen opsætning (docs).
- Setup **gemmer API-nøglen** i Mascots egen aichat-config (brugerens beslutning 29. okt; ændrer ikke-målet fra
  2026-10-28-getting-started-design.md "Mascot skriver ikke API-nøgler").
- **Robo er vært** ("Houston"), med et lille ASCII-ansigt til sidst (brugerens beslutning 29. okt; ændrer
  anti-målet fra 28. okt "guiden lyder som Robo" — det gælder fortsat for guiden i boblen, ikke for setup).
- AUR-pakken siger efter installation: kør `mascot setup`. `mascot --help` og CLI'ens "Chat is not set up yet"
  nævner den også.
- Kan køres igen når som helst; viser de nuværende valg som standard.

## Ikke-mål

- Ingen `sudo`, ingen installation af Ollama, aichat eller modeller (`ollama pull`). Mangler noget, viser setup
  kommandoen og stopper ved det trin (distro-neutral: henvis til ollama.com/download, som README'en).
- Intet grafikkort-tjek (beslutning fra 28. okt). Modellisten viser størrelse/parametre, så brugeren selv vælger.
- Ingen andre online-tjenester end de fire (resten: "en anden" → docs).
- Guiden i boblen bliver som den er (for dem der aldrig åbner en terminal); den kan nævne `mascot setup`.
- Ingen grafisk/TUI-ramme (curses o.l.); almindelige spørgsmål i terminalen.

## Anti-mål (en fejl, selv hvis det virker)

- Setup skriver i, overskriver eller læser brugerens egen aichat-config (`$AICHAT_CONFIG_DIR` eller
  `~/.config/aichat`) eller dens `.env`. Har brugeren sin egen (eller `CHAT_COMMAND`), springer setup model-trinene
  over og siger "using your own aichat config" — kun sprog og tools.
- En API-nøgle vises, logges, står i en fejlbesked, i `ps`/argv, i en proces' miljø, der ikke skal bruge den, eller
  sendes andre steder hen end til den tjeneste, den hører til.
- Setup gør noget i stilhed: hver ændring står i opsummeringen med sti eller nøgle.
- Setup ændrer indstillinger, brugeren ikke har bekræftet (fx tools slået til uden at være valgt).

## Hvilken config der bruges

Uændret fra 28. okt: `CHAT_COMMAND` → brugerens egen aichat-config → Mascots egen
(`$MASCOT_DATA_DIR/aichat/config.yaml`, installeret `~/.local/share/mascot/aichat/`). Setup skriver kun den sidste.

## Forløbet

Tekst på engelsk (som resten af CLI'en). Hvert trin har et kort, farvet mærkat i venstre kolonne (som Astro):
`robo`, `where`, `ollama`, `model`, `online`, `key`, `lang`, `tools`, `next`. Farver kun når stdout er en terminal
og `NO_COLOR` ikke er sat. Svaret bliver stående (gråt) under spørgsmålet.

1. **robo** — "Hi! I'm Robo. Let's get me talking - it takes a minute."
2. **Opsætning der allerede findes:** `CHAT_COMMAND` eller brugerens egen config → "Using your own aichat config
   (…)" og videre til trin 6. Mascots egen findes → dens nuværende valg er standard i trin 3-5.
3. **where** — "Where should I think?" 1. On this computer (Ollama) — private, free, needs a good graphics card;
   2. Online — any computer, pay per message; 3. Both — this computer by default, online when you ask for it.
4. **Lokalt** (1 eller 3):
   - `aichat` findes? Ellers: sig hvordan (README's tekst), stop.
   - Ollama svarer (`OLLAMA_HOST`, som guiden)? Ellers: "Start it: `systemctl --user start ollama` (or `ollama
     serve`), then run `mascot setup` again", stop.
   - Modeller der kan chatte (Ollamas `/api/tags` + `/api/show` capabilities, som `tools/mascot-guide`), nummereret
     med parametre (`details.parameter_size`) og om de kan bruge tools. Ingen modeller: vis `ollama pull …` og stop.
5. **Online** (2 eller 3):
   - **online** — "Which service?" 1. OpenRouter — one key for models from every company (recommended);
     2. Anthropic (Claude); 3. OpenAI (GPT); 4. Google (Gemini); 5. Another one — set it up in aichat yourself
     (link til docs, setup fortsætter uden online).
   - **key** — hvor man får en (URL pr. tjeneste), læses skjult (`getpass`). Testes mod tjenesten (se *Nøgler*).
     Forkert: sig det (uden nøglen) og spørg igen; tom linje springer online over. OpenRouter: nævn at man kan sætte
     et forbrugsloft på nøglen.
   - **model** — tjenestens aktuelle modeller (hentet med nøglen, se *Modeller online*), et kort udvalg øverst og
     "type a name". aichats indbyggede liste (0.30.0) er for gammel til at bruges (nyeste Claude: 3.5 Haiku).
6. **lang** — "Which language do you write in?" Standard gættet fra `LANG`/`LC_ALL` (fx `da_DK` → Danish) via en
   lille tabel; ukendt: ingen standard. Tom linje: lad `CHAT_LANGUAGE` være. Gemmes med samme logik som `mascot
   config set CHAT_LANGUAGE`.
7. **tools** — alle 8 med beskrivelse (samme tekster som `.tools`), nummererede, med [x]/[ ]. Brugeren skriver numre
   for at slå til/fra, Enter når færdig. Kun online: de lokale (files, todo, reminders, shell, system) vises som
   "only with a model on this computer" og kan ikke vælges. Gemmes som `CHAT_TOOLS`.
8. **Opsummering** — ✔-linjer for hvert skridt der skrev noget (config med sti, `CHAT_LANGUAGE`, `CHAT_TOOLS`).
9. **next** — `mascot summon Robo`, "click me to talk; .help shows what I can do", ved begge: `.model …` eller
   højreklik → Settings → Model; `mascot setup` igen når som helst. Til sidst Robo-ansigtet med en kort hilsen.

Afbrydes med Ctrl+C eller Ctrl+D: intet er skrevet (alt skrives først i trin 8), og der står "Nothing was changed."
Uden terminal (stdin ikke en tty): "mascot setup asks questions; run it in a terminal", exit 1.

## Configen setup skriver

Én fil, `$MASCOT_DATA_DIR/aichat/config.yaml`, mappe `700`, fil `600`. `model:` er standardmodellen (lokal ved
"begge"). `clients:`:

- Ollama: som `mascot-guide` (`openai-compatible`, navn `ollama`, `api_base` `<OLLAMA_HOST>/v1`, alle chat-modeller,
  `supports_function_calling: true` kun hvor Ollama siger `tools`).
- OpenRouter: `openai-compatible`, navn `openrouter`, `api_base: https://openrouter.ai/api/v1`, `api_key`, de
  valgte/viste modeller med `supports_function_calling` efter OpenRouters `supported_parameters` (`tools`).
- Anthropic / OpenAI / Google: aichats typer `claude` / `openai` / `gemini` med `api_key` og en `models:`-liste med
  den valgte model (+ `supports_function_calling: true`; alle tre tjenesters chatmodeller kan).

Skrives atomisk (midlertidig fil i samme mappe, `600` før indhold, `rename`). Findes filen, gemmes den gamle som
`config.yaml.old` (`600`) — den kan indeholde en nøgle, så aldrig `644`. Brugeren skal have svaret ja på
opsummeringen ("Write this? [Y/n]") før noget skrives.

## Nøgler

- Læses med `getpass` (intet ekko). Aldrig i argv (ikke `aichat … --api-key`), aldrig i miljøet for andre
  processer, aldrig i output. Fejlbeskeder om nøglen siger kun "the key did not work (HTTP 401)".
- Testes med ét kald direkte fra Python (`urllib`, HTTPS) til tjenestens egen adresse:
  OpenRouter `GET https://openrouter.ai/api/v1/key` (Authorization: Bearer); Anthropic `GET
  https://api.anthropic.com/v1/models` (`x-api-key`, `anthropic-version`); OpenAI `GET https://api.openai.com/v1/models`
  (Bearer); Google `GET https://generativelanguage.googleapis.com/v1beta/models` (header `x-goog-api-key`, ikke i
  URL'en). Ingen omdirigeringer følges til andre værter.
- Robo kan ikke læse den: `tools/mascot-tools` har allerede `.local/share/mascot/aichat` i `SECRET_DIRS`. Skal
  stadig gælde, hvis `MASCOT_DATA_DIR` er et andet sted (kendt hul fra 28. okt: "SECRET_DIRS følger ikke en anden
  MASCOT_DATA_DIR") — rettes i samme omgang.

## Modeller online

- OpenRouter: `GET https://openrouter.ai/api/v1/models` (offentlig). Kort udvalg øverst: en lille fast liste i koden
  over billige, hurtige modeller, der findes i svaret (fx `anthropic/claude-haiku-5.5`); kun dem, der er i
  listen, vises. Søg: "type a name or part of one".
- Anthropic / OpenAI / Google: tjenestens models-endpoint (samme kald som nøgletesten), filtreret til chatmodeller
  (OpenAI: `gpt-`/`o`-modeller; Google: `generateContent` i `supportedGenerationMethods`), nyeste først hvor
  svaret har en dato.

## Andre ændringer

- AUR: `packaging/aur/mascot/mascot.install` med `post_install`/`post_upgrade`-tekst ("Run `mascot setup` to get
  started" kun ved install), `install=` i PKGBUILD.
- `mascot --help` (chat_help): første linje under *getting started* bliver `mascot setup`.
- `SETUP_HINT`: "Chat is not set up yet; run mascot setup (or tap the mascot)."
- Guiden i boblen: dens første besked nævner `mascot setup` i terminalen som alternativ.
- README *Getting started* trin 2: `mascot setup` først; de manuelle måder bliver stående under.
- `docs/chat.md`: et afsnit om setup, hvor nøglen ligger, og forbrugsloft.
- CHANGELOG *Unreleased*.

## Test

- Python-tests som `scripts/test_guide.py`: falsk Ollama og falske tjenester (lokal HTTP-server; adresserne kan
  peges om med miljøvariabler kun til test, som `MASCOT_MACHINE_ROOT`), tom HOME + `XDG_CONFIG_HOME` i scratchpad.
  Dækker: hvert valg (1/2/3, hver tjeneste), nøgle forkert → spørg igen, egen config → ingen model-trin, Ctrl+C →
  intet skrevet, genkørsel → `.old`, rettigheder `700`/`600`, nøglen findes ikke i stdout/stderr, configen kan læses
  af rigtig aichat (`aichat --list-models` med `AICHAT_CONFIG_DIR`).
- Mod rigtige tjenester: kun OpenRouter (brugerens egen nøgle, kun med brugerens ok). Anthropic/OpenAI/Google kan
  ikke testes uden nøgler; docs siger det, indtil nogen har prøvet.
- I brugerens rigtige install (~/.local) — uden at røre brugerens egen opsætning (brugeren har `CHAT_COMMAND`, så
  setup skal springe model-trin over der).

## Mine valg (Claude) — tjek dem

- Genkørsel foreslår de nuværende valg; den gamle config gemmes som `config.yaml.old`.
- Tekst på engelsk; kun Pythons standardbibliotek (ingen nye afhængigheder); almindelige spørgsmål, ikke curses.
  Derfor slås tools til/fra med numre, ikke mellemrum (som i mockup'en).
- Standard-tools ved lokal: time, weather, todo, reminders, sleep slået til; files, shell, system fra (de læser
  mest). Ved online: time, weather, sleep.
- Alt skrives først efter "Write this?", så en afbrydelse aldrig efterlader noget halvt.
- Koden ligger i CLI'en (`src/mascotctl/`, nyt modul der inlines af py-compose), ikke i `tools/mascot-guide`
  (som bliver uændret).
- Sprog fra en lille tabel over almindelige sprogkoder; resten skrives af brugeren.
- Genkørsel med en nøgle i Mascots config: "A key for OpenRouter is set. Keep it? [Y/n]" (nøglen vises aldrig,
  heller ikke delvist); nej → spørg efter en ny.
- Kan den valgte standardmodel ikke bruge tools (Ollama siger det), siger tools-trinnet det ("gemma3 cannot use
  tools; pick another model to use them") og gemmer valget alligevel, så de virker ved et senere modelskifte.
- Setup starter ikke Robo selv; *next* viser `mascot summon Robo` (Mascot fortæller, gør ikke).
