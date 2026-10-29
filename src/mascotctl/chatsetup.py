#   chatsetup.py - mascot setup: where the mascot thinks, its model, your language and its tools
#
#   Copyright (C) 2026  HexRebel
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, see <https://www.gnu.org/licenses/>.
"""mascot setup writes one file, Mascot's own aichat config ($MASCOT_DATA_DIR/aichat/config.yaml), and
CHAT_LANGUAGE and CHAT_TOOLS. The user's own aichat config is only looked for, never read or written. An API key
is read without echo, never printed, and only sent to the service it belongs to."""
import http.client
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

# The tool groups, as CHAT_TOOLS names them, and those only a model on this computer gets (ui/Bubble.qml)
TOOLS = ["time", "weather", "files", "todo", "reminders", "shell", "sleep", "system"]
LOCAL_TOOLS = ["files", "todo", "reminders", "shell", "system"]
TOOL_NOTES = {
    "time": "the date and time, sent with every message",
    "weather": "from wttr.in (only the place name is sent)",
    "files": "lists and reads files and looks at images in your home directory, dotfiles only those in "
             "CHAT_DOTFILES, never where keys, logins or history are kept",
    "todo": "shows, adds to, changes and removes from your todo list",
    "reminders": "sets, lists and cancels reminders and timers",
    "shell": "the last commands you ran, hiding those that may hold a password or key",
    "sleep": "the mascots sleep for a while when you ask",
    "system": "looks into why something on your computer does not work and how it is doing; only looks",
}

# The services online: aichat's client type, the prefix of its models' names in aichat, where the key comes
# from, and the service's own address (the key is only ever sent there)
PROVIDERS = {
    "openrouter": {"title": "OpenRouter", "type": "openai-compatible", "prefix": "openrouter",
                   "key_url": "https://openrouter.ai/keys", "base": "https://openrouter.ai"},
    "anthropic": {"title": "Anthropic (Claude)", "type": "claude", "prefix": "claude",
                  "key_url": "https://console.anthropic.com/settings/keys", "base": "https://api.anthropic.com"},
    "openai": {"title": "OpenAI (GPT)", "type": "openai", "prefix": "openai",
               "key_url": "https://platform.openai.com/api-keys", "base": "https://api.openai.com"},
    "google": {"title": "Google (Gemini)", "type": "gemini", "prefix": "gemini",
               "key_url": "https://aistudio.google.com/apikey", "base": "https://generativelanguage.googleapis.com"},
}
OPENROUTER_API = "https://openrouter.ai/api/v1"


@dataclass
class Online:
    provider: str  # a key of PROVIDERS
    key: str
    model: str
    models: list = field(default_factory=list)  # [{"name", "tools"}], model among them


@dataclass
class Choice:
    local_model: str | None  # Ollama's model, None: not on this computer
    local_models: list  # [{"name", "tools"}]
    online: Online | None
    default: str  # "local" or "online": which one answers


def yaml_str(value: str, always: bool = False) -> str:
    """value as a YAML scalar: plain when that is safe, else double-quoted"""
    if not always and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_value(text: str) -> str:
    """A scalar as yaml_str writes it, back to its value"""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return re.sub(r'\\(.)', r'\1', text[1:-1])
    return text


def model_lines(models: list, chosen: str) -> list:
    """The models of one client, the chosen one first: so read_current() finds it when it is not the default"""
    lines = ["    models:"]
    for m in sorted(models, key=lambda m: m["name"] != chosen):
        lines.append(f"      - name: {yaml_str(m['name'])}")
        if m["tools"]:
            lines.append("        supports_function_calling: true")
    return lines


def config_yaml(choice: Choice, ollama_base: str) -> str:
    if choice.default == "online":
        default = f"{PROVIDERS[choice.online.provider]['prefix']}:{choice.online.model}"
    else:
        default = f"ollama:{choice.local_model}"
    lines = [f"model: {yaml_str(default)}", "clients:"]
    if choice.local_model:
        lines += ["  - type: openai-compatible", "    name: ollama", f"    api_base: {yaml_str(ollama_base + '/v1')}"]
        lines += model_lines(choice.local_models, choice.local_model)
    if choice.online:
        provider = PROVIDERS[choice.online.provider]
        lines.append(f"  - type: {provider['type']}")
        if choice.online.provider == "openrouter":
            lines += ["    name: openrouter", f"    api_base: {OPENROUTER_API}"]
        lines.append(f"    api_key: {yaml_str(choice.online.key, always=True)}")
        lines += model_lines(choice.online.models, choice.online.model)
    return "\n".join(lines) + "\n"


def read_current(directory: str) -> Choice | None:
    """The choices in Mascot's own config, as config_yaml() or tools/mascot-guide wrote it; None if it is not
    there or holds anything else (then setup starts from nothing and keeps it as config.yaml.old)"""
    try:
        with open(os.path.join(directory, "config.yaml")) as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    default, clients = None, []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if m := re.fullmatch(r"model: (.+)", line):
            default = yaml_value(m[1])
        elif line == "clients:":
            pass
        elif m := re.fullmatch(r"  - type: (\S+)", line):
            clients.append({"type": m[1], "name": None, "key": None, "models": []})
        elif clients and (m := re.fullmatch(r"    (name|api_base|api_key): (.+)", line)):
            if m[1] != "api_base":
                clients[-1]["name" if m[1] == "name" else "key"] = yaml_value(m[2])
        elif clients and line == "    models:":
            pass
        elif clients and (m := re.fullmatch(r"      - name: (.+)", line)):
            clients[-1]["models"].append({"name": yaml_value(m[1]), "tools": False})
        elif clients and clients[-1]["models"] and line == "        supports_function_calling: true":
            clients[-1]["models"][-1]["tools"] = True
        else:
            return None
    local, online = None, None
    for c in clients:
        if not c["models"]:
            return None
        if c["type"] == "openai-compatible" and c["name"] == "ollama" and not c["key"]:
            local = c
            continue
        provider = next((p for p, v in PROVIDERS.items() if v["type"] == c["type"]
                         and (c["type"] != "openai-compatible" or c["name"] == p)), None)
        if not provider or not c["key"] or online:
            return None
        online = (provider, c)
    if not default or not (local or online):
        return None
    choice = Choice(None, [], None, "local")
    if local:
        choice.local_models = local["models"]
        choice.local_model = local["models"][0]["name"]
    if online:
        provider, c = online
        choice.online = Online(provider, c["key"], c["models"][0]["name"], c["models"])
    prefix, _, name = default.partition(":")
    if prefix == "ollama" and local and any(m["name"] == name for m in local["models"]):
        choice.local_model = name
    elif online and prefix == PROVIDERS[online[0]]["prefix"] and any(m["name"] == name for m in online[1]["models"]):
        choice.online.model = name
        choice.default = "online"
    else:
        return None
    return choice


def write_config(directory: str, text: str) -> str:
    """Writes Mascot's own config (directory 700, file 600, in one step); one that is there is kept as
    config.yaml.old (600: it may hold a key). Returns its path"""
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    path = os.path.join(directory, "config.yaml")

    def replace(target: str, content: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".config.")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp, target)
        except BaseException:
            os.unlink(tmp)
            raise

    if os.path.exists(path):
        with open(path) as f:
            replace(path + ".old", f.read())
    replace(path, text)
    return path


TIMEOUT = 10  # seconds a service or Ollama gets to answer

# Cheap, quick models to show first, when the service has them
RECOMMENDED = {
    "openrouter": ["anthropic/claude-haiku-5.5", "google/gemini-3-flash", "openai/gpt-5-mini"],
    "anthropic": [], "openai": [], "google": [],
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A key goes to the service's own address and nowhere else"""

    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def get(url: str, headers: dict, body: dict | None = None) -> tuple[int, dict | None]:
    """(HTTP status, JSON answer); status 0 when it could not be reached"""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    try:
        with OPENER.open(request, timeout=TIMEOUT) as answer:
            return answer.status, json.load(answer)
    except urllib.error.HTTPError as e:
        e.close()
        return e.code, None
    except (OSError, ValueError, http.client.HTTPException):
        return 0, None


def ollama_base() -> str:
    """Ollama's address, from OLLAMA_HOST as tools/mascot-guide reads it"""
    host = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
    return (host if "://" in host else "http://" + host).rstrip("/")


def ollama_here(base: str) -> bool:
    """Whether Ollama at base is this computer (as ui/local.js decides for the bubble's tools)"""
    host = urllib.parse.urlsplit(base).hostname or ""
    return host in ("", "localhost", "::1", "0.0.0.0") or host.startswith("127.")


def ollama_models(base: str) -> list | None:
    """Ollama's models that can chat, [{"name", "tools", "size"}]; None if Ollama does not answer"""
    status, tags = get(base + "/api/tags", {})
    if status != 200 or tags is None:
        return None
    models = []
    for name in sorted(m["name"] for m in tags.get("models", [])):
        if re.search(r"[-:]cloud$", name):  # Ollama's cloud models run at ollama.com, not here
            continue
        status, show = get(base + "/api/show", {}, {"model": name})
        if status != 200 or show is None or show.get("remote_host") or show.get("remote_model"):
            continue
        caps = show.get("capabilities")
        if caps is None:  # Ollama before 0.6.4 does not say
            caps = ["completion"]
        if "completion" in caps:
            models.append({"name": name, "tools": "tools" in caps,
                           "size": (show.get("details") or {}).get("parameter_size", "")})
    return models


def service(provider: str, key: str, path: str) -> tuple[int, dict | None]:
    """One request to a service, with the key in a header (never in the address)"""
    base = os.environ.get("MASCOT_SETUP_TEST_BASE") or PROVIDERS[provider]["base"]  # only tests set it
    headers = {"anthropic": {"x-api-key": key, "anthropic-version": "2023-06-01"},
               "google": {"x-goog-api-key": key}}.get(provider, {"Authorization": f"Bearer {key}"})
    return get(base + path, headers)


# The whole list: Anthropic gives 20 and Google 50 unless asked for more
MODELS_PATH = {"openrouter": "/api/v1/models", "anthropic": "/v1/models?limit=1000", "openai": "/v1/models",
               "google": "/v1beta/models?pageSize=1000"}
# Models in the lists that aichat cannot chat with (pictures, sound, realtime, search, the Responses API only)
NOT_CHAT = re.compile(r"image|audio|realtime|tts|transcribe|search|embedding|moderation|deep-research|-pro\b|^gemma-")


def check_key(provider: str, key: str) -> int:
    """The service's answer to the key: 200 when it works, 0 when the service could not be reached"""
    return service(provider, key, "/api/v1/key" if provider == "openrouter" else MODELS_PATH[provider])[0]


def online_models(provider: str, key: str) -> list:
    """The service's models to chat with, newest first where it says, [{"name", "tools"}]; [] if it fails"""
    status, answer = service(provider, key, MODELS_PATH[provider])
    if status != 200 or not isinstance(answer, dict):
        return []
    if provider == "openrouter":
        return [{"name": m["id"], "tools": "tools" in (m.get("supported_parameters") or [])}
                for m in answer.get("data", [])]
    if provider == "google":
        return [{"name": name, "tools": True} for m in answer.get("models", [])
                if "generateContent" in (m.get("supportedGenerationMethods") or [])
                and not NOT_CHAT.search(name := m["name"].removeprefix("models/"))]
    models = answer.get("data", [])
    if provider == "openai":
        models = [m for m in models if re.match(r"gpt-|o\d", m["id"]) and not NOT_CHAT.search(m["id"])]
    models.sort(key=lambda m: m.get("created_at") or m.get("created") or 0, reverse=True)
    return [{"name": m["id"], "tools": True} for m in models]


LANGUAGES = {
    "da": "Danish", "de": "German", "en": "English", "es": "Spanish", "fi": "Finnish", "fr": "French",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "nb": "Norwegian", "nl": "Dutch", "nn": "Norwegian",
    "no": "Norwegian", "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "sv": "Swedish", "tr": "Turkish",
    "uk": "Ukrainian", "zh": "Chinese",
}
DEFAULT_TOOLS = {"local": ["time", "weather", "todo", "reminders", "sleep"], "online": ["time", "weather", "sleep"]}
AICHAT_DOCS = "https://github.com/sigoden/aichat/wiki/Configuration-Guide"
ROBO = [" ╭───╮", " │◉ ◉│  Robo: See you on the desktop! Beep.", " ╰───╯"]


def language_from_locale(env: dict) -> str | None:
    """The language the locale names (LC_ALL, LC_MESSAGES, LANG), e.g. da_DK.UTF-8: Danish"""
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if env.get(name):
            return LANGUAGES.get(re.split(r"[_.@]", env[name])[0].lower())
    return None


class SetupStopped(Exception):
    """Setup cannot go on (something missing, or nothing to set up): nothing is written"""


def number(answer: str, most: int) -> bool:
    """Whether answer is one of 1..most, in plain digits (not ² or a thousand-digit number)"""
    return answer.isascii() and answer.isdecimal() and len(answer) < 5 and 1 <= int(answer) <= most


def typed_plain(ask, say, prompt: str) -> str:
    """A written answer without control characters: without line editing, an arrow key adds ESC [ D"""
    while True:
        answer = ask(prompt).strip()
        if not any(ord(c) < 32 or ord(c) == 127 for c in answer):
            return answer
        say("", "That has a control character in it (an arrow key?); write it again.")


def conf_options(path: str) -> dict:
    """CHAT_COMMAND, CHAT_LANGUAGE and CHAT_TOOLS as mascotd.conf sets them (keys in any case, as config.c
    reads them); None when it does not set one, "" when it sets it to nothing"""
    options = {"CHAT_COMMAND": None, "CHAT_LANGUAGE": None, "CHAT_TOOLS": None}
    try:
        with open(path, errors="replace") as f:
            for line in f:
                key, sep, value = line.partition("=")
                if sep and key.strip().upper() in options:
                    options[key.strip().upper()] = value.strip()
    except OSError:
        pass
    return options


def run_setup(config_root: str, ask, ask_secret, out, set_option, current: dict, env: dict) -> int:
    """mascot setup's questions, then (only after "Write this?") Mascot's config and CHAT_LANGUAGE/CHAT_TOOLS.
    ask/ask_secret(prompt) -> answer, out(line), set_option(key, value); current: CHAT_COMMAND, CHAT_LANGUAGE
    and CHAT_TOOLS as set now; env: HOME, XDG_CONFIG_HOME, AICHAT_CONFIG_DIR, PATH and the locale"""
    home = env.get("HOME") or os.path.expanduser("~")

    def shown(path):
        return "~" + path[len(home):] if path.startswith(home + os.sep) else path

    def say(label, text=""):
        out(f"{label:>7}  {text}".rstrip())

    def pick(label, question, options, default=None):
        """1-based number of one of options; Enter takes default"""
        say(label, question)
        for i, option in enumerate(options, 1):
            say("", f"{i}. {option}")
        numbers = ", ".join(str(i) for i in range(1, len(options))) + f" or {len(options)}" if len(options) > 1 else "1"
        while True:
            answer = ask(f"         › {'(Enter: ' + str(default) + ') ' if default else ''}").strip()
            if not answer and default:
                return default
            if number(answer, len(options)):
                return int(answer)
            say("", f"Answer {numbers}.")

    def yes(label, question):
        while True:
            answer = ask(f"{label:>7}  {question} [Y/n] ").strip().lower()
            if answer in ("", "y", "yes"):
                return True
            if answer in ("n", "no"):
                return False

    directory = os.path.join(config_root, "aichat")
    own_dir = env.get("AICHAT_CONFIG_DIR") or os.path.join(env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"), "aichat")
    own = current.get("CHAT_COMMAND") or (os.path.join(own_dir, "config.yaml") if os.path.isfile(os.path.join(own_dir, "config.yaml")) else "")
    say("robo", "Hi! I'm Robo. Let's get me talking - it takes a minute.")
    try:
        choice = None
        if own:
            say("aichat", f"Using your own aichat config ({shown(own)}); Mascot never changes it.")
        else:
            choice = choose_models(directory, ask, ask_secret, say, pick, yes, env)
        language = ask_language(current, env, ask, say)
        tools = ask_tools(current, choice, ask, say)
        out("")
        if choice:
            old = " (the one there now is kept as config.yaml.old)" if os.path.exists(os.path.join(directory, "config.yaml")) else ""
            say("✔", f"Mascot's chat config: {shown(os.path.join(directory, 'config.yaml'))}{old}")
        if language and language != current.get("CHAT_LANGUAGE"):
            say("✔", f"CHAT_LANGUAGE = {language}")
        if ",".join(tools) != current.get("CHAT_TOOLS"):
            say("✔", f"CHAT_TOOLS = {','.join(tools)}")
        if not yes("", "Write this?"):
            raise SetupStopped()
    except (KeyboardInterrupt, EOFError, SetupStopped):
        out("")
        say("", "Nothing was changed.")
        return 1
    if choice:
        write_config(directory, config_yaml(choice, ollama_base()))
    if language and language != current.get("CHAT_LANGUAGE"):
        set_option("CHAT_LANGUAGE", language)
    if ",".join(tools) != current.get("CHAT_TOOLS"):
        set_option("CHAT_TOOLS", ",".join(tools))
    out("")
    say("next", "mascot summon Robo      bring me onto the screen")
    say("", "click me                to talk; .help shows what I can do")
    if choice and choice.local_model and choice.online:
        say("", f".model {PROVIDERS[choice.online.provider]['prefix']}:{choice.online.model}")
        say("", "                        in the bubble asks the one online (or right-click me: Settings, Model)")
    say("", "mascot setup            run this again any time")
    out("")
    for line in ROBO:
        out(line)
    return 0


def choose_models(directory, ask, ask_secret, say, pick, yes, env) -> Choice:
    """Where the mascot thinks and with which model(s); raises SetupStopped when something is missing"""
    if not shutil.which("aichat", path=env.get("PATH")):
        say("aichat", "aichat is not installed: Mascot chats through it. On Arch: pacman -S aichat;")
        say("", "elsewhere: github.com/sigoden/aichat/releases. Then run mascot setup again.")
        raise SetupStopped()
    previous = read_current(directory)
    where_default = None
    if previous:
        where_default = 3 if previous.local_model and previous.online else 1 if previous.local_model else 2
    where = pick("where", "Where should I think?", [
        "On this computer (Ollama) - private, free, needs a good graphics card",
        "Online - any computer, pay per message",
        "Both - this computer by default, online when you ask for it"], where_default)
    choice = Choice(None, [], None, "online" if where == 2 else "local")
    if where in (1, 3):
        base = ollama_base()
        models = ollama_models(base)
        if models is None:
            say("ollama", f"Ollama is not running at {base}. Start it (e.g. sudo systemctl enable --now ollama,")
            say("", "or ollama serve), then run mascot setup again. Installing it: ollama.com/download")
            raise SetupStopped()
        if not models:
            say("ollama", "Ollama has no model to chat with. Download one (ollama pull <model>, see")
            say("", "ollama.com/library), then run mascot setup again.")
            raise SetupStopped()
        if not ollama_here(base):
            say("ollama", f"Ollama is at {base}, not on this computer: what you write goes there, so I only")
            say("", "get the tools that do not read this computer.")
        names = [m["name"] for m in models]
        default = names.index(previous.local_model) + 1 if previous and previous.local_model in names else None
        n = pick("model", "Which model on this computer?", [
            f"{m['name']}  {m['size']}{'' if m['tools'] else ', cannot use tools'}".rstrip() for m in models], default)
        choice.local_model = names[n - 1]
        choice.local_models = [{"name": m["name"], "tools": m["tools"]} for m in models]
    if where in (2, 3):
        choice.online = choose_online(previous, ask, ask_secret, say, pick, yes)
        if not choice.online:
            if where == 2:
                say("", "Nothing to set up online.")
                raise SetupStopped()
            choice.default = "local"
    return choice


def choose_online(previous, ask, ask_secret, say, pick, yes) -> Online | None:
    ids = list(PROVIDERS)
    default = ids.index(previous.online.provider) + 1 if previous and previous.online else None
    n = pick("online", "Which service?", [
        "OpenRouter - one key for models from every company (recommended)",
        "Anthropic (Claude)", "OpenAI (GPT)", "Google (Gemini)",
        "Another one - set it up in aichat yourself"], default)
    if n == 5:
        say("", f"aichat can use many more: {AICHAT_DOCS}")
        say("", "Mascot uses your own aichat config (~/.config/aichat) when there is one.")
        return None
    provider = ids[n - 1]
    info = PROVIDERS[provider]
    key = None
    if previous and previous.online and previous.online.provider == provider:
        if yes("key", f"A key for {info['title']} is set. Keep it?"):
            key = previous.online.key
    while key is None:
        say("key", f"Your {info['title']} key, from {info['key_url']} (shown as dots; Enter skips):")
        typed = ask_secret("         › ").strip()
        if not typed:
            return None
        status = check_key(provider, typed)
        if status == 200:
            say("", "✔ the key works")
            key = typed
        elif status == 0:
            say("", f"Could not reach {info['title']}; check the network and try again.")
        else:
            say("", f"The key did not work (HTTP {status}); try again.")
    if provider == "openrouter":
        say("", "Tip: give the key a credit limit at openrouter.ai/keys, so a lost key costs little.")
    return Online(provider, key, *choose_online_model(provider, key, previous, ask, say, pick))


def choose_online_model(provider, key, previous, ask, say, pick) -> tuple:
    """(model, the models to keep in the config: the one chosen and those shown)"""
    models = online_models(provider, key)
    names = [m["name"] for m in models]
    shown = [m for m in models if m["name"] in RECOMMENDED[provider]] or models[:5]
    old = previous.online.model if previous and previous.online and previous.online.provider == provider else None
    if old in names and old not in [m["name"] for m in shown]:
        shown = [models[names.index(old)]] + shown
    if not models:
        say("", f"Could not get {PROVIDERS[provider]['title']}'s models.")
    while True:
        options = [m["name"] for m in shown] + ["type a name (or part of one)"]
        n = pick("model", "Which model?", options, options.index(old) + 1 if old in options else None)
        if n <= len(shown):
            chosen = shown[n - 1]
            break
        typed = typed_plain(ask, say, "         name › ")
        if not typed:
            continue
        if not models:  # the list could not be read: take it as written
            chosen = {"name": typed, "tools": True}
            break
        exact = [m for m in models if m["name"] == typed]
        matches = exact or [m for m in models if typed.lower() in m["name"].lower()]
        if len(matches) == 1:
            chosen = matches[0]
            break
        if matches:
            shown = matches[:10]
        else:
            say("", f"{PROVIDERS[provider]['title']} has no model called {typed}.")
    return chosen["name"], [chosen] + [m for m in shown if m["name"] != chosen["name"]]


def ask_language(current, env, ask, say) -> str | None:
    """The language for CHAT_LANGUAGE; None leaves it as it is"""
    guess = current.get("CHAT_LANGUAGE") or language_from_locale(env)
    say("lang", f"Which language do you write in? (Enter: {guess or 'I follow yours'})")
    answer = typed_plain(ask, say, "         › ")
    return answer[:1].upper() + answer[1:] if answer else guess


def ask_tools(current, choice, ask, say) -> list:
    """The tools for CHAT_TOOLS, in TOOLS' order. Without a model on this computer, the local ones cannot be
    chosen (the bubble would not give them to a model online); with the user's own config, all can"""
    local = choice is None or (bool(choice.local_model) and ollama_here(ollama_base()))
    # Not set: the defaults; set to nothing: none, as the user chose
    chosen = current.get("CHAT_TOOLS")
    on = list(DEFAULT_TOOLS["local" if local else "online"]) if chosen is None \
        else [t for t in chosen.split(",") if t in TOOLS]
    if not local:
        on = [t for t in on if t not in LOCAL_TOOLS]
    if choice and choice.default == "local":
        model = next(m for m in choice.local_models if m["name"] == choice.local_model)
        if not model["tools"]:
            say("tools", f"{choice.local_model} cannot use tools; they work once you pick a model that can.")
    # Online, only the tools that work there are choices; one line names the others
    choices = TOOLS if local else [t for t in TOOLS if t not in LOCAL_TOOLS]
    others = [t for t in TOOLS if t not in choices]
    while True:
        say("tools", "Which tools may I use?")
        for i, t in enumerate(choices, 1):
            say("", f"{i}. [{'x' if t in on else ' '}] {t:<10} {TOOL_NOTES[t]}")
        if others:
            say("", f"With a model on this computer, I could also use {', '.join(others[:-1])} and {others[-1]}.")
        say("", "Type numbers to turn them on or off (e.g. 1 3), Enter when done.")
        answer = ask("         › ").strip()
        if not answer:
            return [t for t in TOOLS if t in on]
        for token in re.split(r"[\s,]+", answer):
            if not number(token, len(choices)):
                say("", f"There is no tool {token}.")
                continue
            t = choices[int(token) - 1]
            if t in on:
                on.remove(t)
            else:
                on.append(t)
