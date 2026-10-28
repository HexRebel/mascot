#!/usr/bin/env python3
"""Tests for tools/mascot-guide (and the CLI's chat_is_set_up), with a made-up Ollama.

    python3 -I scripts/test_guide.py -v

Each test gets its own home, data directory and PATH in a temporary directory; nothing outside it is read
or written. The made-up Ollama answers /api/tags and /api/show from MODELS.
"""
import http.server
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GUIDE = os.path.join(ROOT, "tools", "mascot-guide")

# name -> capabilities, or None: /api/show fails for it
MODELS = {}


class FakeOllama(http.server.BaseHTTPRequestHandler):
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
        if self.path == "/api/tags":
            self.reply(200, {"models": [{"name": n} for n in MODELS]})
        else:
            self.reply(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or "{}")
        caps = MODELS.get(body.get("model") or body.get("name"))
        if self.path == "/api/show" and caps is not None:
            self.reply(200, {"capabilities": caps})
        else:
            self.reply(500, {"error": "no"})


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Guide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        MODELS.clear()
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.home = os.path.join(t, "home")
        self.data = os.path.join(self.home, ".local", "share", "mascot")
        self.bin = os.path.join(t, "bin")
        os.makedirs(self.data)
        os.makedirs(self.bin)
        aichat = os.path.join(self.bin, "aichat")
        with open(aichat, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(aichat, 0o755)
        self.env = {"HOME": self.home, "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
                    "MASCOT_DATA_DIR": self.data, "OLLAMA_HOST": f"127.0.0.1:{self.port}",
                    "PATH": self.bin + os.pathsep + "/usr/bin" + os.pathsep + "/bin"}

    def tearDown(self):
        self.tmp.cleanup()

    def guide(self, *args, **env):
        return subprocess.run([sys.executable, GUIDE, *args], env={**self.env, **env}, capture_output=True, text=True, timeout=30)

    def status(self, **env):
        out = self.guide("status", **env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def touch(self, path, text="model: x\n"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def mascot_config(self):
        return os.path.join(self.data, "aichat", "config.yaml")

    def test_own_config_wins(self):
        own = os.path.join(self.home, ".config", "aichat", "config.yaml")
        self.touch(own)
        self.touch(self.mascot_config())
        s = self.status()
        self.assertEqual(s["state"], "own")
        self.assertEqual(s["config"], own)

    def test_aichat_config_dir_env(self):
        d = os.path.join(self.home, "elsewhere")
        self.touch(os.path.join(d, "config.yaml"))
        s = self.status(AICHAT_CONFIG_DIR=d)
        self.assertEqual(s["state"], "own")
        self.assertEqual(s["config"], os.path.join(d, "config.yaml"))

    def test_mascot_config(self):
        self.touch(self.mascot_config())
        s = self.status()
        self.assertEqual(s["state"], "mascot")
        self.assertEqual(s["config"], os.path.join(self.data, "aichat"))

    def test_no_aichat(self):
        os.unlink(os.path.join(self.bin, "aichat"))
        self.assertEqual(self.status(PATH=self.bin)["state"], "no-aichat")

    def test_no_ollama(self):
        s = self.status(OLLAMA_HOST=f"127.0.0.1:{free_port()}")
        self.assertEqual(s, {"state": "no-ollama", "config": "", "models": []})

    def test_no_models(self):
        MODELS["nomic-embed-text"] = ["embedding"]
        self.assertEqual(self.status()["state"], "no-models")

    def choose_models(self):
        MODELS.update({"llama2:7b": ["completion"], "gemma4:latest": ["completion", "tools"],
                       "nomic-embed-text": ["embedding"], "broken": None})

    def test_choose(self):
        self.choose_models()
        s = self.status()
        self.assertEqual(s["state"], "choose")
        self.assertEqual(s["models"], [{"name": "gemma4:latest", "tools": True}, {"name": "llama2:7b", "tools": False}])

    def test_ollama_host_forms(self):
        self.choose_models()
        for host in (f"127.0.0.1:{self.port}", f"http://127.0.0.1:{self.port}/"):
            self.assertEqual(self.status(OLLAMA_HOST=host)["state"], "choose", host)

    def test_write(self):
        self.choose_models()
        out = self.guide("write", "llama2:7b")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), os.path.join(self.data, "aichat"))
        path = self.mascot_config()
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode), 0o700)
        with open(path) as f:
            text = f.read()
        self.assertIn("model: ollama:llama2:7b\n", text)
        self.assertIn(f"api_base: http://127.0.0.1:{self.port}/v1\n", text)
        self.assertIn("- name: gemma4:latest\n          supports_function_calling: true\n", text)
        self.assertRegex(text, r"- name: llama2:7b\n(?!\s*supports_function_calling)")
        self.assertNotIn("nomic", text)
        self.assertEqual(os.listdir(os.path.dirname(path)), ["config.yaml"])  # no temporary file left
        self.assertEqual(self.status()["state"], "mascot")

    def test_write_never_overwrites(self):
        self.choose_models()
        self.touch(self.mascot_config(), "x")
        out = self.guide("write", "llama2:7b")
        self.assertEqual(out.returncode, 1)
        with open(self.mascot_config()) as f:
            self.assertEqual(f.read(), "x")

    def test_write_unknown_model(self):
        self.choose_models()
        out = self.guide("write", "nomic-embed-text")
        self.assertEqual(out.returncode, 1)
        self.assertFalse(os.path.exists(self.mascot_config()))


class Cli(unittest.TestCase):
    """client.py's chat_is_set_up: the same rule as mascot-guide's status, for the line `mascot summon` writes"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
        spec = importlib.util.spec_from_file_location("client", os.path.join(ROOT, "src", "mascotctl", "client.py"))
        cls.client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.client)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.root = os.path.join(self.home, ".local", "share", "mascot")
        os.makedirs(self.root)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "XDG_CONFIG_HOME", "AICHAT_CONFIG_DIR")}
        os.environ["HOME"] = self.home
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("AICHAT_CONFIG_DIR", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def test_cli_chat_is_set_up(self):
        conf = os.path.join(self.root, "mascotd.conf")
        self.write(conf, "chat_command=\nbreeding=true\n")
        self.assertFalse(self.client.chat_is_set_up(self.root))
        self.write(conf, "chat_command=aichat -r x\n")
        self.assertTrue(self.client.chat_is_set_up(self.root))
        os.unlink(conf)
        self.write(os.path.join(self.root, "aichat", "config.yaml"), "model: x\n")
        self.assertTrue(self.client.chat_is_set_up(self.root))
        os.unlink(os.path.join(self.root, "aichat", "config.yaml"))
        self.write(os.path.join(self.home, ".config", "aichat", "config.yaml"), "model: x\n")
        self.assertTrue(self.client.chat_is_set_up(self.root))


if __name__ == "__main__":
    unittest.main()
