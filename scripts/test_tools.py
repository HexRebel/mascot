#!/usr/bin/env python3
"""Tests for the file tools the model gets (tools/mascot-tools), each run like the bubble runs it, in a home of
its own.

Run: python3 -I scripts/test_tools.py
"""

import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "sk-proj-Abc123def456ghi789jkl012mno345pq"


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def tool(self, name, args, dotfiles=""):
        out = subprocess.run([os.path.join(ROOT, "tools", "bin", name), json.dumps(args)],
                             env={"HOME": self.home, "PATH": "/usr/bin:/bin", "MASCOT_TOOLS_LOCAL": "1",
                                  "MASCOT_DOTFILES": dotfiles},
                             capture_output=True, text=True, timeout=30)
        return out.stdout + out.stderr

    def test_allowed_dotfile_keys_are_hidden(self):
        # CHAT_DOTFILES lets the mascot see ~/.zshrc (the help's own example); a key in it is still not shown
        self.write(".zshrc", f"alias ll='ls -l'\nexport OPENAI_API_KEY={KEY}\n")
        out = self.tool("read_file", {"path": "~/.zshrc"}, "~/.zshrc")
        self.assertIn("alias ll='ls -l'", out)
        self.assertIn("OPENAI_API_KEY=[hidden]", out)
        self.assertNotIn(KEY[:12], out)

    def test_search_never_finds_a_key(self):
        # Searching for the key itself must not tell, one letter at a time, what it is
        self.write(".zshrc", f"export OPENAI_API_KEY={KEY}\n")
        out = self.tool("search_file", {"path": "~/.zshrc", "text": KEY[:10]}, "~/.zshrc")
        self.assertIn("is not in", out)
        out = self.tool("search_file", {"path": "~/.zshrc", "text": "OPENAI"}, "~/.zshrc")
        self.assertIn("OPENAI_API_KEY=[hidden]", out)
        self.assertNotIn(KEY[:12], out)

    def test_more_places_with_tokens_are_private(self):
        for rel in (".config/containers/auth.json", ".config/github-copilot/hosts.json", ".config/hub",
                    ".config/gcloud/application_default_credentials.json", ".config/sops/age/keys.txt",
                    ".config/fish/fish_variables", ".config/Code/User/globalStorage/state.vscdb",
                    ".config/doctl/config.yaml", ".terraform.d/credentials.tfrc.json", "docs/auth.json"):
            self.write(rel, f"{{\"token\": \"{KEY}\"}}\n")
            # Even when CHAT_DOTFILES lets the mascot see all of ~/.config and ~/.terraform.d
            out = self.tool("read_file", {"path": "~/" + rel}, "~/.config;~/.terraform.d")
            self.assertIn("private", out, rel)
            self.assertNotIn(KEY[:12], out, rel)

    def test_hard_link_to_a_secret_refused(self):
        # A hard link is the file itself, not a link check_path can follow: one with more names is not read
        secret = self.write(".ssh/id_ed25519", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk\n")
        os.makedirs(os.path.join(self.home, "docs"))
        os.link(secret, os.path.join(self.home, "docs", "hard"))
        self.write("docs/notes.txt", "OPENSSH notes\n")
        out = self.tool("read_file", {"path": "~/docs/hard"})
        self.assertIn("hard link", out)
        self.assertNotIn("b3BlbnNzaC1rZXk", out)
        out = self.tool("search_file", {"path": "~/docs", "text": "OPENSSH"})
        self.assertIn("notes.txt", out)
        self.assertNotIn("b3BlbnNzaC1rZXk", out)
        self.assertNotIn("PRIVATE KEY", out)

    def test_plain_file_unchanged(self):
        self.write("notes.txt", "buy milk\nthe meeting is at 10\n")
        self.assertIn("buy milk\nthe meeting is at 10", self.tool("read_file", {"path": "~/notes.txt"}))


if __name__ == "__main__":
    unittest.main()
