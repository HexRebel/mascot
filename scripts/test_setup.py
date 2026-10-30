#!/usr/bin/env python3
"""Tests for mascot setup (src/mascotctl/chatsetup.py and the CLI's setup command), with made-up services.

    python3 -I scripts/test_setup.py -v

Each test gets its own home and data directory in a temporary directory; nothing outside it is read or
written. No real key is ever used: the made-up services accept "sk-good-key" and refuse anything else.
"""
import http.server
import importlib.machinery
import importlib.util
import json
import os
import pty
import select
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


setup = load("chatsetup", os.path.join(ROOT, "src", "mascotctl", "chatsetup.py"))
guide = load("mascot_guide", os.path.join(ROOT, "tools", "mascot-guide"))

LOCAL = [{"name": "gemma4:12b", "tools": True}, {"name": "tiny", "tools": False}]


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.data = os.path.join(self.home, ".local", "share", "mascot")
        os.makedirs(self.home)
        self.aichat_dir = os.path.join(self.data, "aichat")

    def tearDown(self):
        self.tmp.cleanup()

    def mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)


class Config(Home):
    def test_yaml_local(self):
        text = setup.config_yaml(setup.Choice("gemma4:12b", LOCAL, None, "local"), "http://127.0.0.1:11434")
        self.assertIn("model: ollama:gemma4:12b", text)
        self.assertIn("name: ollama", text)
        self.assertIn("api_base: http://127.0.0.1:11434/v1", text)
        after = text.split("gemma4:12b")[-1]
        self.assertIn("supports_function_calling: true", after.split("tiny")[0])
        self.assertNotIn("supports_function_calling", text.split("tiny")[-1])

    def test_yaml_both_online_and_default(self):
        online = setup.Online("anthropic", "k", "claude-haiku-5-5", [{"name": "claude-haiku-5-5", "tools": True}])
        text = setup.config_yaml(setup.Choice("gemma4:12b", LOCAL, online, "local"), "http://127.0.0.1:11434")
        self.assertIn("model: ollama:gemma4:12b", text)
        self.assertIn("type: claude", text)
        self.assertIn('api_key: "k"', text)
        text = setup.config_yaml(setup.Choice("gemma4:12b", LOCAL, online, "online"), "http://127.0.0.1:11434")
        self.assertIn("model: claude:claude-haiku-5-5", text)

    def test_yaml_openrouter(self):
        online = setup.Online("openrouter", "k", "anthropic/claude-haiku-5.5",
                              [{"name": "anthropic/claude-haiku-5.5", "tools": True}])
        text = setup.config_yaml(setup.Choice(None, [], online, "online"), "http://127.0.0.1:11434")
        self.assertIn("type: openai-compatible", text)
        self.assertIn("name: openrouter", text)
        self.assertIn("api_base: https://openrouter.ai/api/v1", text)
        self.assertIn("model: openrouter:anthropic/claude-haiku-5.5", text)
        self.assertNotIn("name: ollama", text)

    def test_yaml_key_quoted(self):
        key = 'sk-or-a#b: "c"\\d'
        online = setup.Online("openrouter", key, "m", [{"name": "m", "tools": True}])
        setup.write_config(self.aichat_dir, setup.config_yaml(setup.Choice(None, [], online, "online"), "http://x"))
        self.assertEqual(setup.read_current(self.aichat_dir).online.key, key)

    def test_read_back(self):
        online = setup.Online("openai", "k", "gpt-5-mini", [{"name": "gpt-5-mini", "tools": True}])
        for choice in (setup.Choice("gemma4:12b", LOCAL, None, "local"),
                       setup.Choice(None, [], online, "online"),
                       setup.Choice("gemma4:12b", LOCAL, online, "local"),
                       setup.Choice("gemma4:12b", LOCAL, online, "online")):
            setup.write_config(self.aichat_dir, setup.config_yaml(choice, "http://127.0.0.1:11434"))
            self.assertEqual(setup.read_current(self.aichat_dir), choice)

    def test_read_guide_config(self):
        os.makedirs(self.aichat_dir)
        with open(os.path.join(self.aichat_dir, "config.yaml"), "w") as f:
            f.write(guide.config_text("gemma4:12b", LOCAL))
        self.assertEqual(setup.read_current(self.aichat_dir), setup.Choice("gemma4:12b", LOCAL, None, "local"))

    def test_read_missing_or_foreign(self):
        self.assertIsNone(setup.read_current(self.aichat_dir))
        os.makedirs(self.aichat_dir)
        with open(os.path.join(self.aichat_dir, "config.yaml"), "w") as f:
            f.write("model: something\nkeybindings: vi\n")
        self.assertIsNone(setup.read_current(self.aichat_dir))

    def test_online_repr_hides_key(self):
        # A debug print, a log line or a failing test's diff must not show the key
        online = setup.Online("openrouter", "sk-good-key", "anthropic/claude-haiku-5.5", [])
        self.assertNotIn("sk-good-key", repr(online))
        self.assertNotIn("sk-good-key", repr(setup.Choice(None, [], online, "online")))

    def test_shipped_mascot_has_no_test_address(self):
        # Where a key is sent is not something the environment can change in the command people install
        with open(os.path.join(ROOT, "utils", "mascot")) as f:
            text = f.read()
        self.assertNotIn("MASCOT_SETUP_TEST_BASE", text)
        self.assertIn("\nTEST_BASE = None", text)

    def test_data_dir_private_when_new(self):
        # Right after installing there is no ~/.local/share: Mascot's own directory is made 700, not 755
        setup.write_config(self.aichat_dir, "model: ollama:a\n")
        self.assertEqual(self.mode(self.data), 0o700)

    def test_data_dir_made_private(self):
        # make install PREFIX=~/.local makes share/mascot 755 before Mascot runs: the todo list and the sessions
        # in it were readable by others
        os.makedirs(self.data, mode=0o755)
        os.chmod(self.data, 0o755)
        setup.write_config(self.aichat_dir, "model: ollama:a\n")
        self.assertEqual(self.mode(self.data), 0o700)

    def test_write_perms_and_old(self):
        path = setup.write_config(self.aichat_dir, "model: ollama:a\n")
        self.assertEqual(path, os.path.join(self.aichat_dir, "config.yaml"))
        self.assertEqual(self.mode(self.aichat_dir), 0o700)
        self.assertEqual(self.mode(path), 0o600)
        setup.write_config(self.aichat_dir, "model: ollama:b\n")
        old = os.path.join(self.aichat_dir, "config.yaml.old")
        with open(old) as f:
            self.assertEqual(f.read(), "model: ollama:a\n")
        self.assertEqual(self.mode(old), 0o600)
        with open(path) as f:
            self.assertEqual(f.read(), "model: ollama:b\n")
        self.assertEqual(sorted(os.listdir(self.aichat_dir)), ["config.yaml", "config.yaml.old"])

    @unittest.skipUnless(shutil.which("aichat"), "aichat is not installed")
    def test_aichat_reads_it(self):
        online = setup.Online("openrouter", "not-a-key", "anthropic/claude-haiku-5.5",
                              [{"name": "anthropic/claude-haiku-5.5", "tools": True}])
        setup.write_config(self.aichat_dir, setup.config_yaml(setup.Choice("gemma4:12b", LOCAL, online, "local"),
                                                              "http://127.0.0.1:11434"))
        env = {"HOME": self.home, "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
               "AICHAT_CONFIG_DIR": self.aichat_dir, "PATH": os.environ["PATH"]}
        out = subprocess.run(["aichat", "--list-models"], env=env, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("ollama:gemma4:12b", out.stdout)
        self.assertIn("openrouter:anthropic/claude-haiku-5.5", out.stdout)
        for provider, model in (("anthropic", "claude-haiku-5-5"), ("openai", "gpt-5-mini"), ("google", "gemini-3-flash")):
            online = setup.Online(provider, "not-a-key", model, [{"name": model, "tools": True}])
            setup.write_config(self.aichat_dir, setup.config_yaml(setup.Choice(None, [], online, "online"), ""))
            out = subprocess.run(["aichat", "--list-models"], env=env, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, timeout=30)
            self.assertEqual(out.returncode, 0, provider + ": " + out.stderr)
            self.assertIn(f"{setup.PROVIDERS[provider]['prefix']}:{model}", out.stdout)


# The made-up Ollama's models: name -> (capabilities, parameter size)
OLLAMA = {}
SEEN = []  # (path, headers) of every request to a service


class FakeServices(http.server.BaseHTTPRequestHandler):
    """Ollama and the four services at one address (chatsetup.TEST_BASE, OLLAMA_HOST)"""

    def log_message(self, *args):
        pass

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        SEEN.append((self.path, dict(self.headers)))
        h = self.headers
        self.path = self.path.split("?")[0]
        if self.path == "/api/tags":
            return self.reply(200, {"models": [{"name": n} for n in OLLAMA]})
        if self.path == "/redirect/v1/models":
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/v1/models")
            self.end_headers()
            return
        good = {
            "/api/v1/key": h.get("Authorization") == "Bearer sk-good-key",
            "/api/v1/models": True,
            "/v1/models": h.get("x-api-key") == "sk-good-key" or h.get("Authorization") == "Bearer sk-good-key",
            "/v1beta/models": h.get("x-goog-api-key") == "sk-good-key",
        }.get(self.path)
        if good is None:
            return self.reply(404, {})
        if not good:
            return self.reply(401, {"error": "no"})
        if self.path == "/api/v1/key":
            return self.reply(200, {"data": {"label": "test"}})
        if self.path == "/api/v1/models":
            return self.reply(200, {"data": [
                {"id": "anthropic/claude-haiku-5.5", "supported_parameters": ["tools", "temperature"]},
                {"id": "some/old-model", "supported_parameters": ["temperature"]}]})
        if self.path == "/v1beta/models":
            return self.reply(200, {"models": [
                {"name": "models/gemini-3-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-9", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemma-3-27b-it", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]}]})
        if h.get("x-api-key"):
            return self.reply(200, {"data": [{"id": "claude-haiku-5-5", "created_at": "2026-09-01T00:00:00Z"},
                                             {"id": "claude-opus-5-5", "created_at": "2026-10-01T00:00:00Z"}]})
        return self.reply(200, {"data": [{"id": "gpt-5-mini", "created": 2}, {"id": "o3", "created": 1},
                                         {"id": "text-embedding-3", "created": 3}, {"id": "whisper-1", "created": 4}]
                               + [{"id": i, "created": 9} for i in (
                                   "gpt-image-1", "gpt-realtime", "gpt-4o-transcribe", "gpt-4o-mini-tts", "gpt-audio",
                                   "gpt-4o-search-preview", "o3-pro", "o3-deep-research", "omni-moderation-latest")]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or "{}")
        model = OLLAMA.get(body.get("model") or body.get("name"))
        if self.path == "/api/show" and model:
            return self.reply(200, {"capabilities": model[0], "details": {"parameter_size": model[1]},
                                    **(model[2] if len(model) > 2 else {})})
        self.reply(500, {"error": "no"})


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Served(Home):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeServices)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        super().setUp()
        OLLAMA.clear()
        SEEN.clear()
        self.saved = {k: os.environ.get(k) for k in ("OLLAMA_HOST",)}
        os.environ["OLLAMA_HOST"] = self.base
        setup.TEST_BASE = self.base

    def tearDown(self):
        setup.TEST_BASE = None
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()


class Net(Served):
    def test_ollama_models(self):
        OLLAMA["gemma4:12b"] = (["completion", "tools"], "11.9B")
        OLLAMA["embed"] = (["embedding"], "0.1B")
        OLLAMA["tiny"] = (["completion"], "1B")
        self.assertEqual(setup.ollama_base(), self.base)
        self.assertEqual(setup.ollama_models(self.base), [{"name": "gemma4:12b", "tools": True, "size": "11.9B"},
                                                          {"name": "tiny", "tools": False, "size": "1B"}])
        self.assertIsNone(setup.ollama_models(f"http://127.0.0.1:{free_port()}"))

    def test_ollama_cloud_models_are_not_local(self):
        # Ollama lists its cloud models too, but they run at ollama.com
        OLLAMA["gemma4:12b"] = (["completion", "tools"], "11.9B")
        OLLAMA["gpt-oss:120b-cloud"] = (["completion", "tools"], "116.8B")
        OLLAMA["glm-4.6:cloud"] = (["completion", "tools"], "")
        OLLAMA["renamed"] = (["completion", "tools"], "", {"remote_host": "https://ollama.com:443"})
        self.assertEqual([m["name"] for m in setup.ollama_models(self.base)], ["gemma4:12b"])

    def test_ollama_here(self):
        for base in ("http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434", "http://0.0.0.0:11434"):
            self.assertTrue(setup.ollama_here(base), base)
        for base in ("http://192.168.1.20:11434", "https://ollama.example.com", "http://127.attacker.example:11434",
                     "http://127.0.0.1.evil.com", "http://127.0.0.1@evil.com:11434"):
            self.assertFalse(setup.ollama_here(base), base)

    def test_check_key_headers(self):
        for provider, path in (("openrouter", "/api/v1/key"), ("anthropic", "/v1/models"),
                               ("openai", "/v1/models"), ("google", "/v1beta/models")):
            SEEN.clear()
            self.assertEqual(setup.check_key(provider, "sk-good-key"), 200, provider)
            self.assertEqual(SEEN[-1][0].split("?")[0], path)
            self.assertEqual(setup.check_key(provider, "bad"), 401, provider)
        SEEN.clear()
        setup.check_key("anthropic", "sk-good-key")
        self.assertIn("anthropic-version", {k.lower() for k in SEEN[-1][1]})
        SEEN.clear()
        setup.check_key("google", "sk-good-key")
        self.assertNotIn("key=", SEEN[-1][0])
        setup.TEST_BASE = f"http://127.0.0.1:{free_port()}"
        self.assertEqual(setup.check_key("openai", "sk-good-key"), 0)

    def test_no_redirect(self):
        setup.TEST_BASE = self.base + "/redirect"
        self.assertEqual(setup.check_key("openai", "sk-good-key"), 302)

    def test_online_models(self):
        self.assertEqual(setup.online_models("openrouter", "sk-good-key"),
                         [{"name": "anthropic/claude-haiku-5.5", "tools": True},
                          {"name": "some/old-model", "tools": False}])
        self.assertEqual([m["name"] for m in setup.online_models("openai", "sk-good-key")], ["gpt-5-mini", "o3"])
        self.assertEqual(setup.online_models("google", "sk-good-key"), [{"name": "gemini-3-flash", "tools": True}])
        self.assertEqual([m["name"] for m in setup.online_models("anthropic", "sk-good-key")],
                         ["claude-opus-5-5", "claude-haiku-5-5"])
        self.assertEqual(setup.online_models("openai", "bad"), [])

    def test_online_models_whole_list(self):
        # Anthropic gives 20 and Google 50 unless asked for more, and a typed name must be found in the list
        SEEN.clear()
        setup.online_models("anthropic", "sk-good-key")
        setup.online_models("google", "sk-good-key")
        self.assertIn("/v1/models?limit=1000", [path for path, _ in SEEN])
        self.assertIn("/v1beta/models?pageSize=1000", [path for path, _ in SEEN])

    def test_get_survives_broken_http(self):
        # Something that is not HTTP at OLLAMA_HOST (or a cut-off answer): could not reach, no traceback
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()

            def answer():
                conn, _ = server.accept()
                conn.recv(1024)
                conn.sendall(b"SSH-2.0-OpenSSH\r\n\r\n")
                conn.close()
            threading.Thread(target=answer, daemon=True).start()
            self.assertEqual(setup.get(f"http://127.0.0.1:{server.getsockname()[1]}/api/tags", {}), (0, None))


class Script:
    """Answers to setup's questions in order (an exception class is raised instead), and what it says"""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.secret_asked = 0
        self.lines = []
        self.options = []

    def next(self):
        if not self.answers:
            raise AssertionError("setup asked more than the script answers:\n" + self.text())
        a = self.answers.pop(0)
        if isinstance(a, type) and issubclass(a, BaseException):
            raise a()
        return a

    def ask(self, prompt):
        return self.next()

    def ask_secret(self, prompt):
        self.secret_asked += 1
        return self.next()

    def out(self, line):
        self.lines.append(line)

    def set_option(self, key, value):
        self.options.append((key, value))

    def text(self):
        return "\n".join(self.lines)


class Flow(Served):
    def setUp(self):
        super().setUp()
        OLLAMA["gemma4:12b"] = (["completion", "tools"], "11.9B")
        OLLAMA["tiny"] = (["completion"], "1B")
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.bin)
        with open(os.path.join(self.bin, "aichat"), "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(os.path.join(self.bin, "aichat"), 0o755)
        self.env = {"HOME": self.home, "XDG_CONFIG_HOME": os.path.join(self.home, ".config"), "PATH": self.bin}
        self.current = {"CHAT_COMMAND": "", "CHAT_LANGUAGE": "", "CHAT_TOOLS": None}

    def run_setup(self, script, **current):
        code = setup.run_setup(self.data, script.ask, script.ask_secret, script.out, script.set_option,
                               {**self.current, **current}, self.env)
        return code

    def config(self):
        with open(os.path.join(self.aichat_dir, "config.yaml")) as f:
            return f.read()

    def written(self):
        return os.path.exists(os.path.join(self.aichat_dir, "config.yaml"))

    def test_local(self):
        s = Script("1", "1", "Danish", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("model: ollama:gemma4:12b", self.config())
        self.assertIn(("CHAT_LANGUAGE", "Danish"), s.options)
        self.assertIn(("CHAT_TOOLS", "time,weather,todo,reminders,sleep"), s.options)
        self.assertIn("mascot summon Robo", s.text())
        self.assertIn("Robo", s.lines[0])

    def test_online_openrouter(self):
        s = Script("2", "1", " sk-good-key\n", "1", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("model: openrouter:anthropic/claude-haiku-5.5", self.config())
        self.assertNotIn("name: ollama", self.config())
        self.assertIn(("CHAT_TOOLS", "time,weather,sleep"), s.options)
        self.assertFalse([o for o in s.options if o[0] == "CHAT_LANGUAGE"])
        self.assertIn("limit", s.text())
        self.assertNotIn("sk-good-key", s.text())

    def test_bad_key_then_good(self):
        s = Script("2", "1", "bad-key-123", "sk-good-key", "1", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("did not work (HTTP 401)", s.text())
        self.assertNotIn("bad-key-123", s.text())
        self.assertEqual(s.secret_asked, 2)

    def test_both(self):
        s = Script("3", "1", "2", "sk-good-key", "1", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        text = self.config()
        self.assertIn("model: ollama:gemma4:12b", text)
        self.assertIn("type: claude", text)
        self.assertIn(".model claude:", s.text())

    def test_invalid_answers(self):
        s = Script("x", "0", "9", "", "1", "1", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertEqual(s.text().count("Where should I think?"), 1)
        self.assertGreaterEqual(s.text().count("1, 2 or 3"), 4)

    def test_tools_toggle(self):
        s = Script("1", "1", "", "3 7", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn(("CHAT_TOOLS", "time,weather,files,todo,reminders"), s.options)

    def test_tools_online_lists_only_online_ones(self):
        # Online, the local-only tools are not choices: one line names them, the rest are numbered 1-3
        s = Script("2", "1", "sk-good-key", "1", "", "4", "3", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("With a model on this computer, I could also use files, todo, reminders, shell and system.",
                      s.text())
        self.assertIn("3. [x] sleep", s.text())
        self.assertNotIn("files      ", s.text())
        self.assertIn("There is no tool 4.", s.text())
        self.assertIn(("CHAT_TOOLS", "time,weather"), s.options)

    def test_tools_question_is_honest(self):
        # todo and reminders change things, so the question must not say the tools never do
        s = Script("1", "1", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertNotIn("never change", s.text())

    def test_tools_none_stays_none(self):
        # CHAT_TOOLS set to nothing on purpose: a rerun starts with none ticked, and Enter keeps it so
        s = Script("1", "1", "", "", "y")
        self.assertEqual(self.run_setup(s, CHAT_TOOLS=""), 0, s.text())
        self.assertNotIn("[x]", s.text())
        self.assertNotIn("CHAT_TOOLS", [k for k, _ in s.options])

    def test_odd_digits_ask_again(self):
        s = Script("²", "1", "1", "", "³", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("There is no tool ³.", s.text())

    def test_control_characters_ask_again(self):
        # Without line editing, an arrow key puts ESC [ D in the answer; it must not reach the config
        s = Script("1", "1", "Dan\x1b[Dish", "Danish", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn(("CHAT_LANGUAGE", "Danish"), s.options)
        self.assertIn("arrow key", s.text())

    def test_ollama_elsewhere(self):
        # Ollama on another machine: setup says so, and the tools that read this computer are not offered
        saved = setup.ollama_here
        setup.ollama_here = lambda base: False
        try:
            s = Script("1", "1", "", "", "y")
            self.assertEqual(self.run_setup(s), 0, s.text())
        finally:
            setup.ollama_here = saved
        self.assertIn("not on this computer", s.text())
        self.assertIn(("CHAT_TOOLS", "time,weather,sleep"), s.options)

    def test_own_config_skips_models(self):
        own = os.path.join(self.home, ".config", "aichat", "config.yaml")
        os.makedirs(os.path.dirname(own))
        with open(own, "w") as f:
            f.write("model: x\n")
        s = Script("Danish", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("Using your own aichat config", s.text())
        self.assertFalse(self.written())
        s = Script("Danish", "", "y")
        os.unlink(own)
        self.assertEqual(self.run_setup(s, CHAT_COMMAND="my-aichat"), 0, s.text())
        self.assertIn("Using your own aichat config", s.text())
        self.assertFalse(self.written())

    def test_ctrl_c_writes_nothing(self):
        for stop in (KeyboardInterrupt, EOFError):
            s = Script("1", "1", "Danish", stop)
            self.assertEqual(self.run_setup(s), 1)
            self.assertIn("Nothing was changed.", s.text())
            self.assertFalse(self.written())
            self.assertEqual(s.options, [])

    def test_no_at_confirm(self):
        s = Script("1", "1", "", "", "n")
        self.assertEqual(self.run_setup(s), 1)
        self.assertIn("Nothing was changed.", s.text())
        self.assertFalse(self.written())
        self.assertEqual(s.options, [])

    def test_rerun_keeps_key(self):
        online = setup.Online("openrouter", "sk-good-key", "anthropic/claude-haiku-5.5",
                              [{"name": "anthropic/claude-haiku-5.5", "tools": True}])
        setup.write_config(self.aichat_dir, setup.config_yaml(setup.Choice(None, [], online, "online"), self.base))
        s = Script("2", "1", "y", "1", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertEqual(s.secret_asked, 0)
        self.assertEqual(setup.read_current(self.aichat_dir).online.key, "sk-good-key")
        self.assertTrue(os.path.exists(os.path.join(self.aichat_dir, "config.yaml.old")))
        self.assertNotIn("sk-good-key", s.text())

    def test_rerun_defaults(self):
        setup.write_config(self.aichat_dir, setup.config_yaml(
            setup.Choice("tiny", [{"name": "gemma4:12b", "tools": True}, {"name": "tiny", "tools": False}],
                         None, "local"), self.base))
        s = Script("", "", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("model: ollama:tiny", self.config())

    def test_another_service(self):
        s = Script("2", "5")
        self.assertEqual(self.run_setup(s), 1)
        self.assertIn("aichat", s.text())
        self.assertIn("Nothing to set up online", s.text())
        self.assertEqual(s.secret_asked, 0)
        s = Script("3", "1", "5", "", "", "y")
        self.assertEqual(self.run_setup(s), 0, s.text())
        self.assertIn("model: ollama:gemma4:12b", self.config())

    def test_no_ollama_stops(self):
        os.environ["OLLAMA_HOST"] = f"127.0.0.1:{free_port()}"
        s = Script("1")
        self.assertEqual(self.run_setup(s), 1)
        self.assertIn("ollama serve", s.text())
        self.assertFalse(self.written())

    def test_no_aichat_stops(self):
        os.unlink(os.path.join(self.bin, "aichat"))
        s = Script()
        self.assertEqual(self.run_setup(s), 1)
        self.assertIn("aichat is not installed", s.text())

    def test_conf_options(self):
        conf = os.path.join(self.home, "mascotd.conf")
        with open(conf, "w") as f:
            f.write("CHAT_COMMAND=aichat -m x\nchat_tools=\nsomething=else\n")
        self.assertEqual(setup.conf_options(conf), {"CHAT_COMMAND": "aichat -m x", "CHAT_LANGUAGE": None,
                                                    "CHAT_TOOLS": ""})
        self.assertEqual(setup.conf_options(os.path.join(self.home, "none")),
                         {"CHAT_COMMAND": None, "CHAT_LANGUAGE": None, "CHAT_TOOLS": None})

    def test_language_from_locale(self):
        self.assertEqual(setup.language_from_locale({"LANG": "da_DK.UTF-8"}), "Danish")
        self.assertEqual(setup.language_from_locale({"LC_ALL": "nb_NO.UTF-8", "LANG": "en_US"}), "Norwegian")
        self.assertIsNone(setup.language_from_locale({"LANG": "C"}))
        self.assertIsNone(setup.language_from_locale({}))


class Cli(Served):
    """The composed mascot command, run like a user would (its own copy, with a home and runtime dir of its own)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.build = tempfile.TemporaryDirectory()
        cls.composed = os.path.join(cls.build.name, "mascot")
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "py-compose.py"), "-s",
                        os.path.join(ROOT, "src", "mascotctl", "client.py"), "-o", cls.composed], check=True)
        # Only this copy sends the services' requests to the made-up services
        with open(cls.composed) as f:
            text = f.read()
        assert text.count("\nTEST_BASE = None") == 1
        with open(cls.composed, "w") as f:
            f.write(text.replace("\nTEST_BASE = None", f"\nTEST_BASE = {cls.base!r}"))

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        OLLAMA["gemma4:12b"] = (["completion", "tools"], "11.9B")
        self.bin = os.path.join(self.tmp.name, "bin")
        self.run_dir = os.path.join(self.tmp.name, "run")
        os.makedirs(self.bin)
        os.makedirs(self.run_dir, mode=0o700)
        with open(os.path.join(self.bin, "aichat"), "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(os.path.join(self.bin, "aichat"), 0o755)
        self.env = {"HOME": self.home, "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
                    "XDG_RUNTIME_DIR": self.run_dir, "PATH": self.bin + os.pathsep + "/usr/bin" + os.pathsep + "/bin",
                    "OLLAMA_HOST": self.base, "LANG": "C"}

    def mascot(self, *args, stdin=subprocess.DEVNULL):
        return subprocess.run([sys.executable, self.mascot_path(), "-cr", self.data, *args], env=self.env,
                              stdin=stdin, capture_output=True, text=True, timeout=60)

    def mascot_path(self):
        return type(self).composed

    def test_cli_needs_tty(self):
        out = self.mascot("setup")
        self.assertEqual(out.returncode, 1)
        self.assertIn("run it in a terminal", out.stderr)
        self.assertEqual(os.listdir(self.run_dir), [])

    def test_cli_help_mentions_setup(self):
        out = self.mascot("--help")
        self.assertIn("mascot setup", out.stdout)
        out = self.mascot()
        self.assertIn("run mascot setup", out.stderr)

    def test_cli_setup_via_pty(self):
        text, code = self.setup_via_pty(["1", "1", "Danish", "", "y"])
        self.assertEqual(code, 0, text)
        self.assertEqual(self.mode(self.data), 0o700)
        self.assertTrue(os.path.exists(os.path.join(self.aichat_dir, "config.yaml")), text)
        with open(os.path.join(self.data, "mascotd.conf")) as f:
            conf = f.read()
        self.assertIn("chat_language=Danish", conf)
        self.assertIn("chat_tools=time,weather,todo,reminders,sleep", conf)

    def test_cli_setup_no_writes_nothing(self):
        # The composed mascot is one namespace: a name in chatsetup must not be another module's
        text, code = self.setup_via_pty(["1", "1", "Danish", "", "n"])
        self.assertEqual(code, 1, text)
        self.assertIn("Nothing was changed.", text)
        self.assertNotIn("Traceback", text)
        self.assertFalse(os.path.exists(os.path.join(self.aichat_dir, "config.yaml")), text)

    def test_cli_key_shows_dots(self):
        # One dot per character, so a paste is seen to land; backspace takes one back; the key itself never shows
        text, code = self.setup_via_pty(["2", "1", "sk-good-keyX\x7f", "1", "", "", "y"])
        self.assertEqual(code, 0, text)
        self.assertIn("•" * 11, text)
        self.assertNotIn("•" * 13, text)
        self.assertNotIn("sk-good-key", text)
        self.assertIn("the key works", text)

    def test_cli_chatsetup_names_are_its_own(self):
        import ast
        with open(type(self).composed) as f:
            composed = ast.parse(f.read()).body
        with open(os.path.join(ROOT, "src", "mascotctl", "chatsetup.py")) as f:
            own = ast.parse(f.read()).body

        def names(body):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    yield node.name
                elif isinstance(node, ast.Assign):
                    yield from (t.id for t in node.targets if isinstance(t, ast.Name))

        everywhere = list(names(composed))
        self.assertEqual([n for n in set(names(own)) if everywhere.count(n) > 1], [])

    def setup_via_pty(self, answers):
        # openpty + Popen, not pty.fork: forking a process with the fake server's thread can deadlock
        fd, tty = pty.openpty()
        child = subprocess.Popen([sys.executable, self.mascot_path(), "-cr", self.data, "setup"], env=self.env,
                                 stdin=tty, stdout=tty, stderr=tty, start_new_session=True)
        os.close(tty)
        seen = b""
        while True:
            ready, _, _ = select.select([fd], [], [], 30)
            if not ready:
                child.kill()
                self.fail("setup did not answer:\n" + seen.decode(errors="replace"))
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
            if (seen.rstrip().endswith(b"\xe2\x80\xba") or seen.rstrip().endswith(b"[Y/n]")) and answers:
                os.write(fd, (answers.pop(0) + "\n").encode())
        os.close(fd)
        return seen.decode(errors="replace"), child.wait(30)


class ToolsPrivacy(Home):
    """Robo's file tools never read Mascot's chat config or sessions, wherever MASCOT_DATA_DIR is"""

    def read(self, path, **env):
        return subprocess.run([os.path.join(ROOT, "tools", "bin", "read_file"), json.dumps({"path": path})],
                              env={"HOME": self.home, "PATH": "/usr/bin:/bin", "MASCOT_TOOLS_LOCAL": "1",
                                   "MASCOT_TOOLS_ALLOWED": "read_file", **env},
                              capture_output=True, text=True, timeout=30)

    def test_tools_block_data_dir_aichat(self):
        elsewhere = os.path.join(self.home, "elsewhere")
        for sub in ("aichat", "aichat-sessions"):
            os.makedirs(os.path.join(elsewhere, sub))
            with open(os.path.join(elsewhere, sub, "config.yaml"), "w") as f:
                f.write('api_key: "sk-good-key"\n')
        os.symlink(os.path.join(elsewhere, "aichat"), os.path.join(self.home, "link"))
        for path in (os.path.join(elsewhere, "aichat", "config.yaml"),
                     os.path.join(elsewhere, "aichat-sessions", "config.yaml"),
                     os.path.join(self.home, "link", "config.yaml")):
            out = self.read(path, MASCOT_DATA_DIR=elsewhere)
            self.assertIn("private", out.stdout + out.stderr, path)
            self.assertNotIn("sk-good-key", out.stdout + out.stderr, path)
        with open(os.path.join(elsewhere, "notes.txt"), "w") as f:
            f.write("just notes\n")
        self.assertIn("just notes", self.read(os.path.join(elsewhere, "notes.txt"), MASCOT_DATA_DIR=elsewhere).stdout)


class OldPython(unittest.TestCase):
    """docs/building.md promises Python 3.10: nothing in Mascot's Python may need a newer grammar. Only 3.12 reads a
    string with the f-string's own quote inside its braces (f"{x.decode("utf-8")}"): before, the file does not load"""

    def test_no_quotes_reused_inside_f_strings(self):
        import io
        import tokenize
        files = [os.path.join(ROOT, "utils", "mascot"), os.path.join(ROOT, "tools", "mascot-tools"),
                 os.path.join(ROOT, "tools", "mascot-guide")]
        files += [os.path.join(ROOT, "src", "mascotctl", f) for f in os.listdir(os.path.join(ROOT, "src", "mascotctl"))
                  if f.endswith(".py")]
        for path in files:
            with open(path, encoding="utf-8") as f:
                tokens = list(tokenize.generate_tokens(io.StringIO(f.read()).readline))
            quotes = []  # the quote of each f-string we are inside
            for token in tokens:
                if token.type == tokenize.FSTRING_START:
                    quote = token.string.lstrip("rRfFbB")
                    self.assertFalse(quotes and quote[0] == quotes[-1][0],
                                     f"{os.path.basename(path)}:{token.start[0]}: f-string inside one with the same quote")
                    quotes.append(quote)
                elif token.type == tokenize.FSTRING_END:
                    quotes.pop()
                elif token.type == tokenize.STRING and quotes:
                    quote = token.string.lstrip("rRbBuU")[0]
                    self.assertNotEqual(quote, quotes[-1][0],
                                        f"{os.path.basename(path)}:{token.start[0]}: {token.string} inside an f-string")


if __name__ == "__main__":
    unittest.main()
