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
import json
import os
import re
import tempfile
import urllib.error
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
    except (OSError, ValueError):
        return 0, None


def ollama_base() -> str:
    """Ollama's address, from OLLAMA_HOST as tools/mascot-guide reads it"""
    host = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
    return (host if "://" in host else "http://" + host).rstrip("/")


def ollama_models(base: str) -> list | None:
    """Ollama's models that can chat, [{"name", "tools", "size"}]; None if Ollama does not answer"""
    status, tags = get(base + "/api/tags", {})
    if status != 200 or tags is None:
        return None
    models = []
    for name in sorted(m["name"] for m in tags.get("models", [])):
        status, show = get(base + "/api/show", {}, {"model": name})
        if status != 200 or show is None:
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


MODELS_PATH = {"openrouter": "/api/v1/models", "anthropic": "/v1/models", "openai": "/v1/models",
               "google": "/v1beta/models"}


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
        return [{"name": m["name"].removeprefix("models/"), "tools": True} for m in answer.get("models", [])
                if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    models = answer.get("data", [])
    if provider == "openai":
        models = [m for m in models if re.match(r"gpt-|o\d", m["id"])]
    models.sort(key=lambda m: m.get("created_at") or m.get("created") or 0, reverse=True)
    return [{"name": m["id"], "tools": True} for m in models]
