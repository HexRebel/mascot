#!/usr/bin/env python3
"""Tests for mascot setup (src/mascotctl/chatsetup.py and the CLI's setup command), with made-up services.

    python3 -I scripts/test_setup.py -v

Each test gets its own home and data directory in a temporary directory; nothing outside it is read or
written. No real key is ever used: the made-up services accept "good" and refuse anything else.
"""
import http.server
import importlib.machinery
import importlib.util
import os
import json
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


# The made-up Ollama's models: name -> (capabilities, parameter size)
OLLAMA = {}
SEEN = []  # (path, headers) of every request to a service


class FakeServices(http.server.BaseHTTPRequestHandler):
    """Ollama and the four services at one address (MASCOT_SETUP_TEST_BASE, OLLAMA_HOST)"""

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
        if self.path == "/api/tags":
            return self.reply(200, {"models": [{"name": n} for n in OLLAMA]})
        if self.path == "/redirect/v1/models":
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/v1/models")
            self.end_headers()
            return
        good = {
            "/api/v1/key": h.get("Authorization") == "Bearer good",
            "/api/v1/models": True,
            "/v1/models": h.get("x-api-key") == "good" or h.get("Authorization") == "Bearer good",
            "/v1beta/models": h.get("x-goog-api-key") == "good",
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
                {"name": "models/text-embedding-9", "supportedGenerationMethods": ["embedContent"]}]})
        if h.get("x-api-key"):
            return self.reply(200, {"data": [{"id": "claude-haiku-5-5", "created_at": "2026-09-01T00:00:00Z"},
                                             {"id": "claude-opus-5-5", "created_at": "2026-10-01T00:00:00Z"}]})
        return self.reply(200, {"data": [{"id": "gpt-5-mini", "created": 2}, {"id": "o3", "created": 1},
                                         {"id": "text-embedding-3", "created": 3}, {"id": "whisper-1", "created": 4}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or "{}")
        model = OLLAMA.get(body.get("model") or body.get("name"))
        if self.path == "/api/show" and model:
            return self.reply(200, {"capabilities": model[0], "details": {"parameter_size": model[1]}})
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
        self.saved = {k: os.environ.get(k) for k in ("MASCOT_SETUP_TEST_BASE", "OLLAMA_HOST")}
        os.environ["MASCOT_SETUP_TEST_BASE"] = self.base
        os.environ["OLLAMA_HOST"] = self.base

    def tearDown(self):
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

    def test_check_key_headers(self):
        for provider, path in (("openrouter", "/api/v1/key"), ("anthropic", "/v1/models"),
                               ("openai", "/v1/models"), ("google", "/v1beta/models")):
            SEEN.clear()
            self.assertEqual(setup.check_key(provider, "good"), 200, provider)
            self.assertEqual(SEEN[-1][0], path)
            self.assertEqual(setup.check_key(provider, "bad"), 401, provider)
        SEEN.clear()
        setup.check_key("anthropic", "good")
        self.assertIn("anthropic-version", {k.lower() for k in SEEN[-1][1]})
        SEEN.clear()
        setup.check_key("google", "good")
        self.assertNotIn("key=", SEEN[-1][0])
        os.environ["MASCOT_SETUP_TEST_BASE"] = f"http://127.0.0.1:{free_port()}"
        self.assertEqual(setup.check_key("openai", "good"), 0)

    def test_no_redirect(self):
        os.environ["MASCOT_SETUP_TEST_BASE"] = self.base + "/redirect"
        self.assertEqual(setup.check_key("openai", "good"), 302)

    def test_online_models(self):
        self.assertEqual(setup.online_models("openrouter", "good"),
                         [{"name": "anthropic/claude-haiku-5.5", "tools": True},
                          {"name": "some/old-model", "tools": False}])
        self.assertEqual([m["name"] for m in setup.online_models("openai", "good")], ["gpt-5-mini", "o3"])
        self.assertEqual(setup.online_models("google", "good"), [{"name": "gemini-3-flash", "tools": True}])
        self.assertEqual([m["name"] for m in setup.online_models("anthropic", "good")],
                         ["claude-opus-5-5", "claude-haiku-5-5"])
        self.assertEqual(setup.online_models("openai", "bad"), [])


if __name__ == "__main__":
    unittest.main()
