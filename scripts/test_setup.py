#!/usr/bin/env python3
"""Tests for mascot setup (src/mascotctl/chatsetup.py and the CLI's setup command), with made-up services.

    python3 -I scripts/test_setup.py -v

Each test gets its own home and data directory in a temporary directory; nothing outside it is read or
written. No real key is ever used: the made-up services accept "good" and refuse anything else.
"""
import importlib.machinery
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
