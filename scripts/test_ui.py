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
                  f"const lib = new Function(src + '; return {{ localModel, ollamaHere }};')();"
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
        for host in ("192.168.1.20:11434", "http://ollama.example.com", "https://10.0.0.5"):
            self.assertFalse(self.call("ollamaHere", host), host)
            self.assertEqual(self.call("localModel", "model: ollama:gemma4:12b", host), "", host)


if __name__ == "__main__":
    unittest.main()
