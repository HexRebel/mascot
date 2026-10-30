#!/usr/bin/env python3
"""Checks on the bubble's QML (ui/) that need no running Quickshell.

Run: python3 -I scripts/test_ui.py
"""

import glob
import json
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blocks(source: str, element: str):
    """(line number, body) of each `element {` block, the body without its nested blocks"""
    for m in re.finditer(rf"^\s*{element}\s*{{", source, re.M):
        depth, i, own = 1, m.end(), []
        while depth:
            c = source[i]
            depth += {"{": 1, "}": -1}.get(c, 0)
            if depth == 1 and c not in "{}":
                own.append(c)
            i += 1
        yield source.count("\n", 0, m.end()) + 1, "".join(own)


class Text(unittest.TestCase):
    def test_every_text_says_its_format(self):
        # Qt's default (AutoText) shows text that looks like HTML as markup, and StyledText fetches <img src>
        # from the net: names from mascot packs, tool arguments and errors must never be read that way
        missing = []
        for path in sorted(glob.glob(os.path.join(ROOT, "ui", "*.qml"))):
            with open(path) as f:
                source = f.read()
            for line, body in blocks(source, "Text"):
                if not re.search(r"^\s*textFormat:", body, re.M):
                    missing.append(f"{os.path.relpath(path, ROOT)}:{line}")
        self.assertEqual(missing, [])


@unittest.skipUnless(shutil.which("node"), "node runs ui/local.js outside Quickshell")
class Local(unittest.TestCase):
    """ui/local.js: which model gets the file, todo and shell tools (what they read must stay on this computer)"""

    def call(self, function, *args):
        script = (f"const src = require('fs').readFileSync({json.dumps(os.path.join(ROOT, 'ui', 'local.js'))}, 'utf8')"
                  ".replace(/^\\.pragma.*$/m, '');"
                  f"const lib = new Function(src + '; return {{ localModel, ollamaHere, configFile }};')();"
                  f"console.log(JSON.stringify(lib.{function}(...{json.dumps(list(args))})));")
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_ollama_on_this_computer_is_local(self):
        self.assertEqual(self.call("localModel", "model: ollama:gemma4:12b\nother: x", ""), "gemma4:12b")
        self.assertEqual(self.call("localModel", "model ollama:gemma4-16k:latest", "127.0.0.1:11434"),
                         "gemma4-16k:latest")
        for host in ("", "localhost:11434", "http://127.0.0.1:11434", "[::1]:11434", "http://localhost", "0.0.0.0:11434"):
            self.assertTrue(self.call("ollamaHere", host), host)

    def test_online_models_are_not(self):
        self.assertEqual(self.call("localModel", "model: openrouter:anthropic/claude-haiku-5.5", ""), "")
        self.assertEqual(self.call("localModel", "", ""), "")

    def test_ollama_cloud_models_are_not(self):
        # They are listed by Ollama but run at ollama.com
        for name in ("gpt-oss:120b-cloud", "glm-4.6:cloud", "qwen3-coder:480b-cloud"):
            self.assertEqual(self.call("localModel", f"model: ollama:{name}", ""), "", name)

    def test_ollama_elsewhere_is_not(self):
        # A user name before @ and names that only start like a loopback address are somewhere else
        for host in ("192.168.1.20:11434", "http://ollama.example.com", "https://10.0.0.5", "127.0.0.1@evil.com:11434",
                     "http://127.0.0.1@evil.com", "http://localhost@evil.com/", "127.attacker.example",
                     "127.0.0.1.evil.com:11434", "http://[::1]@evil.com"):
            self.assertFalse(self.call("ollamaHere", host), host)
            self.assertEqual(self.call("localModel", "model: ollama:gemma4:12b", host), "", host)

    def test_config_file_aichat_reads(self):
        # CHAT_COMMAND may give aichat another config (AICHAT_CONFIG_DIR=… aichat): local_model must read that one
        info = "model                   ollama:x\nconfig_file             /home/me/cloud aichat/config.yaml\nenv_file   /x/.env\n"
        self.assertEqual(self.call("configFile", info), "/home/me/cloud aichat/config.yaml")
        self.assertEqual(self.call("configFile", "model: ollama:x\n"), "")

    def test_local_check_asks_aichats_config_and_remembers_only_local(self):
        # Ollama down for a moment answers "not local": that must not stick for the rest of the bubble
        with open(os.path.join(ROOT, "ui", "Bubble.qml")) as f:
            qml = f.read()
        check = qml[qml.index("function localCheck("):]
        check = check[:check.index("\n    }\n")]
        self.assertIn("AICHAT_CONFIG_FILE: Local.configFile(info)", check)
        # and only for a minute: the config may be changed while the bubble is open
        self.assertRegex(check, r"if \(local && key\)\s*bubble\.localModels\[key\] = Date\.now\(\);")
        self.assertIn("Date.now() - (bubble.localModels[key] ?? 0) < 60000", check)

    def test_local_check_remembered_only_while_the_config_says_the_same(self):
        # The key was [name, path]: an api_base or proxy changed in aichat's config still counted as local for
        # up to a minute (memory and private sessions). What the config says now is part of the key, read
        # again for each check, and with no config named nothing is remembered
        with open(os.path.join(ROOT, "ui", "Bubble.qml")) as f:
            qml = f.read()
        check = qml[qml.index("function localCheck("):]
        check = check[:check.index("\n    }\n")]
        self.assertIn("JSON.stringify([name, config, aichatConfigText(config)])", check)
        self.assertIn("const key = name && config ?", check)
        read = qml[qml.index("function aichatConfigText("):]
        read = read[:read.index("\n    }\n")]
        self.assertIn("aichatConfigView.reload()", read)
        view = qml[qml.rindex("FileView {", 0, qml.index("function aichatConfigText(")):qml.index("function aichatConfigText(")]
        self.assertIn("id: aichatConfigView", view)
        # Read at once, not when the event loop gets to it: the check needs the text now
        self.assertIn("blockLoading: true", view)
        self.assertIn("blockAllReads: true", view)

    def test_ollama_host_is_only_ollama_host(self):
        # ollamaHost was put between dataDir's two lines: without OLLAMA_HOST it was the data directory's path
        # (which the old check took for this computer), and dataDir lost its fallback
        with open(os.path.join(ROOT, "ui", "Bubble.qml")) as f:
            qml = f.read()
        self.assertRegex(qml, r'property string ollamaHost: Quickshell\.env\("OLLAMA_HOST"\) \|\| ""\n')
        self.assertRegex(qml, r'property string dataDir: Quickshell\.env\("MASCOT_DATA_DIR"\)\s*\|\| `\$\{Quickshell\.env\("XDG_DATA_HOME"\)')


class NoRuntimeDir(unittest.TestCase):
    def test_bubble_needs_runtime_dir(self):
        # Without XDG_RUNTIME_DIR the socket and the mascots' memory were null/… where qs was started, and the
        # bubble ran rm -rf on that path: the shell quits, and the memory is only removed when it is a real path
        with open(os.path.join(ROOT, "ui", "shell.qml")) as f:
            shell = f.read()
        self.assertRegex(shell, r'if \(!Quickshell\.env\("XDG_RUNTIME_DIR"\)\) \{[^}]*Qt\.quit\(\)')
        with open(os.path.join(ROOT, "ui", "Bubble.qml")) as f:
            bubble = f.read()
        self.assertRegex(bubble, r'property string memoryDir: Quickshell\.env\("XDG_RUNTIME_DIR"\)\s*\?')
        removals = [line for line in bubble.splitlines() if '"rm", "-rf"' in line]
        self.assertTrue(removals)
        for line in removals:
            self.assertIn("if (bubble.memoryDir)", line)


@unittest.skipUnless(shutil.which("make") and os.path.exists(os.path.join(ROOT, "build", "mascotd"))
                     and os.path.exists(os.path.join(ROOT, "utils", "mascot")), "needs make and a build (make all)")
class Install(unittest.TestCase):
    def test_uninstall_removes_what_install_put_there(self):
        # ui/local.js was installed (ui/*.js) but never removed, so share/mascot/ui and share/mascot stayed
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            make = ["make", "-s", "-C", ROOT, "-o", "all", f"DESTDIR={root}", "PREFIX=/usr"]
            for target in ("install", "uninstall"):
                out = subprocess.run(make + [target], capture_output=True, text=True, timeout=120)
                self.assertEqual(out.returncode, 0, out.stderr)
                if target == "install":
                    self.assertTrue(os.path.exists(os.path.join(root, "usr/share/mascot/ui/local.js")))
            left = sorted(os.path.relpath(os.path.join(d, n), root) for d, ds, fs in os.walk(root) for n in ds + fs)
            self.assertFalse([p for p in left if "mascot" in p], left)


class Network(unittest.TestCase):
    def test_menu_asks_openrouter_only_when_used(self):
        # OpenRouter's list only hides its models that are gone; someone without one is not to ask it at all
        with open(os.path.join(ROOT, "ui", "Menu.qml")) as f:
            calls = [line for line in f if "openRouterRequested()" in line and "signal" not in line]
        self.assertTrue(calls)
        for line in calls:
            self.assertIn('startsWith("openrouter:")', line, line.strip())


if __name__ == "__main__":
    unittest.main()
