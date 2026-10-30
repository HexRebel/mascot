#!/usr/bin/env python3
"""Tests for the file tools the model gets (tools/mascot-tools), each run like the bubble runs it, in a home of
its own.

Run: python3 -I scripts/test_tools.py
"""

import http.server
import json
import os
import subprocess
import tempfile
import threading
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

    def test_todo_list_is_private(self):
        todo = os.path.join(self.home, "todo.md")
        self.tool("add_todo", {"item": "secret plans"}, MASCOT_TODO_FILE=todo)
        self.assertEqual(os.stat(todo).st_mode & 0o777, 0o600)

    def fake_ollama(self, shows):
        """An Ollama answering /api/show with shows[model] ({} for others); its address"""
        class Ollama(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                model = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["model"]
                body = json.dumps(shows.get(model, {})).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Ollama)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def aichat_config(self, api_base, name="config.yaml", client="ollama"):
        """An aichat config dir (or file) whose client reaches Ollama at api_base (none: no api_base line)"""
        os.makedirs(os.path.join(self.home, "aichat"), exist_ok=True)
        path = os.path.join(self.home, "aichat", name)
        with open(path, "w") as f:
            f.write("model: ollama:gemma4:12b\nclients:\n  - type: openai-compatible\n"
                    f"    name: {client}\n" + (f"    api_base: {api_base}\n" if api_base else "")
                    + "    models:\n      - name: gemma4:12b\n")
        return path

    def read_as(self, model, **env):
        return self.tool("read_file", {"path": "~/notes.txt"}, MASCOT_VISION_MODEL=model, **env)

    def test_copy_of_a_cloud_model_is_not_local(self):
        # ollama cp gpt-oss:120b-cloud mine: a local name, but Ollama sends it to ollama.com (its /api/show has
        # remote_host); the files must not go there. Ollama not answering: not local either
        self.write("notes.txt", "secret plans\n")
        base = self.fake_ollama({"mine": {"remote_host": "https://ollama.com:443", "remote_model": "gpt-oss:120b"},
                                 "gemma4:12b": {"parameters": "num_ctx 16384"}})
        self.aichat_config(base + "/v1")
        cfg = os.path.join(self.home, "aichat")
        self.assertIn("secret plans", self.read_as("gemma4:12b", AICHAT_CONFIG_DIR=cfg))
        out = self.read_as("mine", AICHAT_CONFIG_DIR=cfg)
        self.assertNotIn("secret plans", out)
        self.assertIn("local model", out)
        self.aichat_config("http://127.0.0.1:9/v1")
        self.assertNotIn("secret plans", self.read_as("gemma4:12b", AICHAT_CONFIG_DIR=cfg))

    def test_bubble_asks_the_same(self):
        # The bubble's memory and private sessions go on only with a model the tools count as local
        base = self.fake_ollama({"mine": {"remote_host": "https://ollama.com:443", "remote_model": "gpt-oss:120b"},
                                 "gemma4:12b": {}})
        self.aichat_config(base + "/v1")
        cfg = os.path.join(self.home, "aichat")
        ask = lambda model: self.tool("local_model", {}, MASCOT_VISION_MODEL=model, AICHAT_CONFIG_DIR=cfg).split("\n")[0]
        self.assertEqual(ask("gemma4:12b"), "1")
        self.assertEqual(ask("mine"), "0")
        self.assertEqual(ask(""), "0")
        self.aichat_config("http://127.0.0.1:9/v1")
        self.assertEqual(ask("gemma4:12b"), "0")

    def test_local_means_where_aichat_sends_it(self):
        # aichat sends an ollama: model to its client's api_base (else OLLAMA_API_BASE), not to OLLAMA_HOST
        self.write("notes.txt", "secret plans\n")
        base = self.fake_ollama({})
        cfg = os.path.join(self.home, "aichat")
        mine = lambda **env: self.read_as("gemma4:12b", OLLAMA_HOST=base, **env)
        for elsewhere in ("http://192.168.1.20:11434/v1", "https://ollama.example.com/v1",
                          "http://127.0.0.1@evil.com:11434/v1", "http://127.attacker.example/v1"):
            self.aichat_config(elsewhere)
            self.assertNotIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg), elsewhere)
        self.aichat_config(f'"{base}/v1"')  # quoted, as YAML allows
        self.assertIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg))
        # The config's api_base wins over OLLAMA_API_BASE; without it, OLLAMA_API_BASE is used
        self.assertIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg, OLLAMA_API_BASE="http://192.168.1.20:11434/v1"))
        self.aichat_config(None)
        self.assertNotIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg, OLLAMA_API_BASE="http://192.168.1.20:11434/v1"))
        self.assertIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg, OLLAMA_API_BASE=base + "/v1"))
        self.assertNotIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg))  # no address at all
        # AICHAT_CONFIG_FILE wins over the directory; without either, ~/.config/aichat (XDG_CONFIG_HOME)
        self.aichat_config(base + "/v1")
        other = self.aichat_config("http://192.168.1.20:11434/v1", name="other.yaml")
        self.assertNotIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg, AICHAT_CONFIG_FILE=other))
        self.assertIn("secret plans", mine(XDG_CONFIG_HOME=self.home))
        # Another client with the right address does not count: ollama: models go to the one named ollama
        self.aichat_config(base + "/v1", client="local")
        self.assertNotIn("secret plans", mine(AICHAT_CONFIG_DIR=cfg))

    def test_weather_sends_only_a_place_name(self):
        # The place goes into wttr.in's URL, also for a model that is not local: a file or the shell history as
        # the "city" would leave the computer. Nothing is sent here (the proxy is a closed port)
        weather = lambda location: self.tool("get_current_weather", {"location": location},
                                             https_proxy="http://127.0.0.1:9", MASCOT_TOOLS_LOCAL="0")
        for place in ("København", "Paris, France", "St. Petersburg", "Aix-en-Provence", "L'Aquila", "L’Aquila",
                      "Frankfurt (Oder)", ""):
            self.assertIn("could not get the weather", weather(place), place)
        for data in ("export OPENAI_API_KEY=sk-abc", "~/.ssh/id_ed25519", "a@b", "line\nbreak", "x" * 65,
                     "%2e%2e", "Paris?format=j1", "Århus/../etc"):
            out = weather(data)
            self.assertNotIn("could not get the weather", out, data)
            self.assertIn("a place name", out, data)

    def test_weather_once_an_answer_with_local_tools(self):
        # With the local tools a model can read a file: the weather must not carry it away 64 letters at a time
        runtime = os.path.join(self.home, "run")
        os.mkdir(runtime, 0o700)
        weather = lambda answer, local="1": self.tool(
            "get_current_weather", {"location": "Paris"}, https_proxy="http://127.0.0.1:9", MASCOT_TOOLS_LOCAL=local,
            MASCOT_ANSWER=answer, XDG_RUNTIME_DIR=runtime)
        self.assertIn("could not get the weather", weather("a1"))
        self.assertIn("once", weather("a1"))
        self.assertIn("could not get the weather", weather("a2"))
        for _ in range(2):  # without the local tools, as often as it likes
            self.assertIn("could not get the weather", weather("b1", local="0"))

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

    def test_keys_by_their_name_are_hidden(self):
        # The name tells it is secret even when the word is not right before "=" (AWS_SECRET_ACCESS_KEY), the value
        # has a "/" or a space, or netrc writes "password word"; words that only contain "key" or "pass" are not
        secrets = {"AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY": "K7MDENG",
                   "machine example.com login me password s3cr3tWord": "s3cr3tWord",
                   "export GITHUB_TOKEN='ghp abc def'": "ghp abc",
                   "  apiKey: abcdefabcdef": "abcdefabcdef",
                   'db.password = "open sesame"': "sesame",
                   "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9": "eyJhbG",
                   "STRIPE_KEY: pk/live/abc": "pk/live",
                   "client_secret=hunter2": "hunter2",
                   # Run together (as the old rule hid them), and inside a setting or a log line that is not secret
                   "export PGPASSWORD=pgpw4": "pgpw4", "ACCESSTOKEN=acc5": "acc5", "adminpass=adm6": "adm6",
                   "OAUTHTOKEN: oau7": "oau7", "authkey=auk8": "auk8",
                   "alias db='PGPASSWORD=alpw9 psql'": "alpw9",
                   "systemd[1]: Environment=DB_PASSWORD=envpw1": "envpw1",
                   "Oct 30 host kernel: password=kpw2": "kpw2", "level=info msg=password=mpw3": "mpw3",
                   "env: TOKEN=etk4": "etk4",
                   # Never hidden before either
                   '{"password": "jpw5", "api_key": "jak6"}': "jpw5", "mysqldump --password ddpw7 shop": "ddpw7",
                   "Authorization: Basic YWxhZGRpbjpvcGVu": "YWxhZGRp",
                   # Over lines (YAML, INI, JSON): a name with nothing after it must not take the next line's
                   "database:\n  password: ymlpw1\nsmtp:\n  token: ymltk2": "ymlpw1",
                   "environment:\n  POSTGRES_PASSWORD: dcpw3": "dcpw3", "[db]\nuser =\npassword = inipw4": "inipw4",
                   '{"db":\n {"password": "jsnpw5"}}': "jsnpw5", "# Example:\nAPI_TOKEN: extk6": "extk6",
                   # A name with ": " that is not secret before one that is, on one line
                   "myapp[12]: config: password: cfpw7": "cfpw7", "x: token: xtk8": "xtk8", "note: secret: nsc9": "nsc9",
                   # Names starting with a digit, passwords in URLs, other languages, escaped quotes
                   "1password=opw1": "opw1", "2FA_TOKEN=fat2": "fat2", "DATABASE_URL=postgres://bob:urlpw3@db/x": "urlpw3",
                   "url: https://bob:urlpw4@h.dk": "urlpw4", "'password' => 'phppw5'": "phppw5",
                   "<password>xmlpw6</password>": "xmlpw6", 'password := "gopw7"': "gopw7",
                   "Authorization: authpw8": "authpw8", 'password="a\\"b escpw9"': "escpw9"}
        plain = ["keyboard=us", "kb_layout = dk", "bypass = no", "monkey: banana", "passthrough=yes",
                 "tokenizer = bert", "compass=north", "Environment=LANG=C", "url: https://github.com/me/x",
                 "<title>Mascot</title>", "database:", "user ="]
        self.write("notes.txt", "\n".join(list(secrets) + plain) + "\n")
        out = self.tool("read_file", {"path": "~/notes.txt"})
        for line, value in secrets.items():
            self.assertNotIn(value, out, line)
        for line in plain:
            self.assertIn(line, out)
        self.assertIn("AWS_SECRET_ACCESS_KEY=[hidden]", out)
        self.assertIn("ymltk2", "".join(secrets))  # (the second secret in that file: hidden too)
        self.assertNotIn("ymltk2", out)
        # Each on its own too, as search_file and the logs see one line at a time
        for line, value in secrets.items():
            self.write("one.txt", line + "\n")
            self.assertNotIn(value, self.tool("read_file", {"path": "~/one.txt"}), line)

    def test_a_long_json_line_is_read(self):
        # Minified JSON (an app's settings): masking it made a RecursionError, and read_file gave nothing
        self.write("state.json", "{" + ",".join(f'"k{i}":{i}' for i in range(3000)) + ',"token":"tk9z"}\n')
        for tool, args in (("read_file", {"path": "~/state.json"}), ("search_file", {"path": "~/state.json", "text": "k2999"})):
            out = self.tool(tool, args)
            self.assertNotIn("Traceback", out, tool)
            self.assertNotIn("tk9z", out, tool)
        self.assertIn('"k1":1', self.tool("read_file", {"path": "~/state.json"}))

    def history(self, commands):
        with open(os.path.join(self.home, ".zsh_history"), "w") as f:
            f.write("".join(f": {1700000000 + i}:0;{c}\n" for i, c in enumerate(commands)))
        return self.tool("last_commands", {"count": len(commands)})

    def test_shell_history(self):
        out = self.history(["ls -la", "git status"])
        self.assertIn("git status  <- the last command", out)
        self.assertIn("ls -la", out)

    def test_shell_history_hides_passwords(self):
        # A short password has no key-like look and no word that gives it away: the command it is given to does
        secret = ["mysql -u root -phunter2 shop", "sshpass -p hunter2 ssh pi", "curl -u me:hunter2 https://x.dk",
                  "git clone https://me:hunter2@github.com/me/x", "echo hunter2 | sudo -S pacman -Syu",
                  "mariadb --user=root -phunter2", "echo hunter2 | sudo -k -S true",
                  "curl -ume:hunter2 https://x.dk", "lftp -u me,hunter2 ftp.x.dk", "redis-cli -a hunter2 ping",
                  "redis-cli --pass hunter2", "docker login -u me -p hunter2 ghcr.io", "podman login -phunter2 x.io",
                  "docker login --password hunter2", "smbclient //nas/share -U me%hunter2",
                  "smbclient -U=me%hunter2 //nas/x", "zip -P hunter2 a.zip f", "unzip -Phunter2 a.zip",
                  "7z a -phunter2 a.7z f", "wpa_passphrase wifi hunter2", "ssh-keygen -N hunter2 -f k",
                  "ssh-keygen -p -P old -N hunter2", "openssl enc -k hunter2 -in f", "htpasswd -b f me hunter2",
                  "mosquitto_pub -u me -P hunter2 -t x"]
        plain = ["mkdir -p src/x", "ssh -p 2222 pi", "curl -u me https://x.dk", "git clone https://github.com/me/x",
                 "ls -p", "sudo pacman -Syu", "sudo pacman -S firefox", "sudo -E pacman -S --needed git",
                 "socat -u UNIX-CONNECT:/run/x.sock -", "docker login ghcr.io", "docker ps -a", "redis-cli ping",
                 "zip -r a.zip f", "unzip a.zip", "ssh-keygen -t ed25519", "smbclient -L nas -U me", "7z x a.7z",
                 "lftp -u me ftp.x.dk", "redis-cli -h db -p 6379 get x"]
        # last_commands shows at most 10
        for chunk in (secret[i:i + 10] for i in range(0, len(secret), 10)):
            out = self.history(chunk)
            self.assertNotIn("hunter2", out)
            self.assertEqual(out.count("[hidden"), len(chunk), out)
        for chunk in (plain[i:i + 10] for i in range(0, len(plain), 10)):
            out = self.history(chunk)
            self.assertNotIn("[hidden", out)
            for command in chunk:
                self.assertIn(command, out)

    def test_search_never_finds_a_key(self):
        # Searching for the key itself must not tell, one letter at a time, what it is
        self.write(".zshrc", f"export OPENAI_API_KEY={KEY}\n")
        out = self.tool("search_file", {"path": "~/.zshrc", "text": KEY[:10]}, "~/.zshrc")
        self.assertIn("is not in", out)
        out = self.tool("search_file", {"path": "~/.zshrc", "text": "OPENAI"}, "~/.zshrc")
        self.assertIn("OPENAI_API_KEY=[hidden]", out)
        self.assertNotIn(KEY[:12], out)

    def test_log_search_never_finds_a_key(self):
        # A journalctl that, like the real one, only gives the lines matching --grep
        bin_dir = os.path.join(self.home, "bin")
        self.write("bin/journalctl", "#!/usr/bin/python3\nimport re, sys\n"
                   "lines = ['2026-10-30T10:00:00+0100 pc app[1]: login password=hunter2 ok',\n"
                   "         '2026-10-30T10:00:01+0100 pc app[1]: started']\n"
                   "grep = sys.argv[sys.argv.index('--grep') + 1] if '--grep' in sys.argv else ''\n"
                   "print('\\n'.join(l for l in lines if re.search(grep, l, re.I)))\n")
        os.chmod(os.path.join(bin_dir, "journalctl"), 0o755)
        path = bin_dir + ":/usr/bin:/bin"
        found = self.tool("read_log", {"search": "password=h"}, PATH=path)
        missed = self.tool("read_log", {"search": "password=x"}, PATH=path)
        self.assertEqual(found.replace("password=h", "password=x"), missed)
        out = self.tool("read_log", {"search": "login"}, PATH=path)
        self.assertIn("login password=[hidden] ok", out)
        self.assertNotIn("started", out)

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
