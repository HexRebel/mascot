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

    def tool(self, name, args, dotfiles="", allowed=None, **env):
        out = subprocess.run([os.path.join(ROOT, "tools", "bin", name), json.dumps(args)],
                             env={"HOME": self.home, "PATH": "/usr/bin:/bin", "MASCOT_TOOLS_LOCAL": "1",
                                  "MASCOT_DOTFILES": dotfiles, "MASCOT_TOOLS_ALLOWED": name if allowed is None else allowed,
                                  **env},
                             capture_output=True, text=True, timeout=30)
        return out.stdout + out.stderr

    def test_weather_sends_only_a_place_name(self):
        # The place goes into wttr.in's URL, also for a model that is not local: a file or the shell history as
        # the "city" would leave the computer. Nothing is sent here (the proxy is a closed port)
        weather = lambda location: self.tool("get_current_weather", {"location": location},
                                             https_proxy="http://127.0.0.1:9", MASCOT_TOOLS_LOCAL="0")
        for place in ("København", "Paris, France", "St. Petersburg", "Aix-en-Provence", ""):
            self.assertIn("could not get the weather", weather(place), place)
        for data in ("export OPENAI_API_KEY=sk-abc", "~/.ssh/id_ed25519", "a@b", "line\nbreak", "x" * 65,
                     "%2e%2e", "Paris?format=j1", "Århus/../etc"):
            out = weather(data)
            self.assertNotIn("could not get the weather", out, data)
            self.assertIn("a place name", out, data)

    def test_only_the_chosen_tools_run(self):
        # aichat runs any function in functions.json the model calls, not only those in AICHAT_USE_TOOLS: with
        # only time, weather and todo chosen, a local model could still read files
        self.write("notes.txt", "secret plans\n")
        for allowed in ("get_current_weather,list_todos,add_todo,remove_todo,edit_todo", ""):
            out = self.tool("read_file", {"path": "~/notes.txt"}, allowed=allowed)
            self.assertNotIn("secret plans", out, allowed)
            self.assertIn("not turned on", out, allowed)
        self.assertIn("secret plans", self.tool("read_file", {"path": "~/notes.txt"}, allowed="list_todos,read_file"))

    def test_listing_does_not_start_lines_with_names(self):
        # aichat sends the output as JSON, where a name after a line break reads "\nowl.png": gemma4 wrote
        # nowl.png for owl.png in 11 of 20 answers, and in none of 20 with "- " in front
        self.write("owl.png", "")
        out = self.tool("list_directory", {"path": "~"})
        self.assertIn("\n- owl.png", out)
        self.assertNotIn("\nowl.png", out)

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
