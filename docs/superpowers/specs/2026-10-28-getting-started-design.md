# Mascots guide ("Getting started") — design

Dato: 2026-10-28. Status: udkast, venter på brugerens godkendelse.

## Hvorfor

Testpersonen (CachyOS, `yay -S mascot`, Ollama + `gemma4:latest`) fik Robo på skærmen, men chatten virkede ikke:
aichat havde ingen config. Han vidste ikke, at han skulle lave `~/.config/aichat/config.yaml`, eller hvad der
skulle stå i den. aichats egen opsætningsguide kan boblen ikke svare på (stdin er lukket), og den skriver ikke
`supports_function_calling: true`, så tools er slået fra uden at nogen opdager det.

Målet: en ny bruger kommer fra "mascotten er på skærmen" til "mascotten svarer" uden at læse README'en.

## Mål

- Mascot kan selv lave en aichat-config, når brugeren ikke har nogen, men kun i Mascots egen mappe.
- Boblen fortæller præcist næste skridt, når noget mangler (Ollama, en model, en config).
- Brugere med deres egen aichat-opsætning mærker intet (brugerens beslutning: guiden er til nybegyndere; har man
  aichat, kender man config.yaml og Ollama). Ingen beskeder til dem, heller ikke om tools.

## Ikke-mål

- Mascot installerer ikke Ollama, aichat eller andet (kræver sudo, er distro-specifikt; Mascot er distro-neutral).
- Mascot henter ikke modeller (`ollama pull`): flere GB, og valget afhænger af grafikkortet. Den viser kommandoen.
- Mascot skriver ikke API-nøgler (OpenRouter). Den viser, hvor nøglen skal stå.
- Ingen `.desktop`-fil eller autostart i denne omgang.
- Intet tjek af om Ollama bruger grafikkortet (brugerens beslutning: det er en guide, ikke fejlfinding). Kun
  installationsteksten nævner `ollama-cuda`/`ollama-rocm`, som README'en gør i dag.

## Anti-mål (ville være en fejl, selv hvis det virker)

- Mascot skriver i, overskriver eller "retter" brugerens egen aichat-config (`~/.config/aichat/` eller det,
  `AICHAT_CONFIG_DIR` peger på), eller læser dens `.env`.
- Mascot gør noget i stilhed: når guiden har lavet config'en, siger den det, og hvor filen ligger.
- Guiden lyder som Robo. Den er neutral (Mascots stemme), fordi første figur kan være en hvilken som helst.

## Hvilken config bruges (brugerens beslutning)

I denne rækkefølge, første der gælder:

1. `CHAT_COMMAND` er sat (fx brugerens `AICHAT_CONFIG_DIR="$HOME/.config/aichat-bubble" aichat`): bruges som i
   dag. Guiden skriver intet.
2. Brugeren har sin egen aichat-config: `$AICHAT_CONFIG_DIR/config.yaml` hvis variablen er sat i boblens miljø,
   ellers `~/.config/aichat/config.yaml` (aichats standard; `$XDG_CONFIG_HOME` respekteres hvis aichat gør).
   Bruges som i dag, med almindelig `aichat`.
3. Ellers: Mascots egen, `$MASCOT_DATA_DIR/aichat/config.yaml` (installeret: `~/.local/share/mascot/aichat/`).
   Boblen kører aichat med `AICHAT_CONFIG_DIR` sat til den mappe. Findes den ikke, starter guiden.

Laver brugeren senere sin egen config, vinder den (punkt 2) automatisk; Mascots bliver liggende ubrugt.

Sessions: uændret — `AICHAT_SESSIONS_DIR` er allerede altid Mascots egen (`aichat-sessions/`, 28. okt), også med
Mascots config. Funktioner: boblen sætter allerede `AICHAT_FUNCTIONS_DIR` selv.

## Guiden i boblen

Udløses når brugeren trykker på en mascot og skriver en besked (eller åbner boblen), og ingen config findes (3).
Tekst i boblens systemlinjer, engelsk (der er ingen model til at oversætte), neutral, kort. Hvert trin har den
præcise kommando eller fil.

Guiden kigger kun (læser): `aichat --version`/`which aichat` (findes aichat?), Ollamas `GET /api/tags` på
`http://localhost:11434` (kører den, hvilke modeller). Ikke `pacman -Q`, ikke brugerens config-indhold, ikke `.env`.

Tilstande og hvad boblen siger:

- **aichat mangler:** sig at aichat skal installeres (pakken hedder `aichat` de fleste steder; ellers link til
  GitHub-releases). Eksisterende tekst i `explained()` kan genbruges.
- **Ollama svarer ikke:** Mascot skal bruge en sprogmodel. To veje: lokal og gratis med Ollama (installér, inkl.
  `ollama-cuda`/`ollama-rocm`-hint, `systemctl enable --now ollama`, `ollama pull <model>`), eller OpenRouter
  (betalt, kræver nøgle: vis den config-blok, de selv skal lægge i `~/.local/share/mascot/aichat/config.yaml`,
  med `api_key` som pladsholder).
- **Ollama kører, ingen modeller:** vis `ollama pull <forslag>` og sig: tryk igen bagefter.
- **Ollama kører med modeller:** vis listen i boblen; brugeren vælger én (brugerens beslutning). Guiden skriver
  config'en, siger at den har gjort det og hvor, og sender så den besked, brugeren skrev, videre.

Config'en guiden skriver (Claudes valg: alle Ollama-modeller med, den valgte som standard, så `.model` kan
skifte):

```yaml
model: ollama:<valgt>
clients:
  - type: openai-compatible
    name: ollama
    api_base: http://localhost:11434/v1
    models:
      - name: <model 1>
        supports_function_calling: true
      - name: <model 2>
        supports_function_calling: true
```

Claudes valg (bygger-tjek): listen tager kun modeller der kan chatte, og `supports_function_calling: true` sættes
kun på modeller der kan tools — begge læses fra Ollamas `POST /api/show` (`capabilities`: `completion`, `tools`).
Embedding-modeller vises ikke; en model uden tools kommer med, uden linjen (ellers fejler den med "does not
support tools"). Ollamas adresse: `$OLLAMA_HOST` hvis sat, ellers `localhost:11434`. "Ingen config" afgøres ved
at se om filen findes (`$AICHAT_CONFIG_DIR`, ellers `${XDG_CONFIG_HOME:-~/.config}/aichat/config.yaml`), ikke
ved at køre aichat.

Filen skrives atomisk (temp + rename), mappen oprettes med 700, filen 600. Findes filen allerede, røres den
ikke. Nye modeller hentet senere kommer ikke automatisk med (overlades til bygger: evt. en linje om at slette
filen for at køre guiden igen).

## Terminalen (brugeren: ja, som foreslået)

`mascot summon` (og `mascot` uden argumenter) skriver én linje, når hverken (1), (2) eller (3) findes: "Chat is
not set up yet; tap the mascot to set it up." Ingen interaktion i terminalen.

## Begrænsninger

- Distro-neutral: ingen pakkemanager-kald; tekster nævner Arch-pakker kun som eksempel ved siden af ollama.com.
- Qt 6.8/Quickshell 0.3.0 (Debian): brug aldrig `environment:`-binding i QML; `createObject(…, {environment})`
  eller `env K=V` i kommandoen.
- Kun læsning af systemet; den eneste fil guiden skriver er Mascots egen config.
- Docs: README's "Getting started" trin 2 forkortes (guiden gør det), `docs/chat.md` forklarer rækkefølgen og
  Mascots config-mappe; CHANGELOG *Unreleased*. `explained()`'s henvisninger til README opdateres.

## Overladt til bygger

- Hvordan listen vises og vælges i boblen (genbrug menuens/listens mønster i `Menu.qml`/`Bubble.qml`).
- Hvor tjekket for (1)/(2)/(3) bor: boblen (QML) eller `mascot`-CLI'en; begge skal være enige.
- Præcis ordlyd af teksterne (kort, neutral, engelsk).
- Om `mascot-tools`' SECRET_DIRS skal have `.local/share/mascot/aichat` (ja, sandsynligvis, hvis en OpenRouter-nøgle
  kan ende der).
