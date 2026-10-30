#!/usr/bin/env python3
"""Where Mascot's sockets go without XDG_RUNTIME_DIR: nowhere. The fallback was /tmp, where another user on the
same computer can put a socket of their own first (and the bubble runs the command a tap event names).

The daemon and the tool run in a namespace with a /tmp of its own (unshare), so the real /tmp is never touched.

Run: python3 -I scripts/test_sockets.py
"""

import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def private_tmp(script: str) -> subprocess.CompletedProcess:
    """script run by sh with an empty /tmp of its own, and no XDG_RUNTIME_DIR or Wayland"""
    return subprocess.run(["unshare", "-rm", "sh", "-c", "mount -t tmpfs tmpfs /tmp && " + script],
                          env={"PATH": "/usr/bin:/bin", "HOME": "/tmp/home"}, capture_output=True, text=True,
                          timeout=60)


def can_unshare() -> bool:
    return bool(shutil.which("unshare")) and private_tmp("true").returncode == 0


class NoRuntimeDir(unittest.TestCase):
    def test_cli_refuses(self):
        out = subprocess.run([shutil.which("python3"), os.path.join(ROOT, "utils", "mascot"), "--do-not-start",
                              "prototypes", "list"],
                             env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}, capture_output=True, text=True,
                             timeout=30)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("XDG_RUNTIME_DIR", out.stderr)

    def test_cli_with_socket_given(self):
        # -s names the socket: then no XDG_RUNTIME_DIR is needed
        out = subprocess.run([shutil.which("python3"), os.path.join(ROOT, "utils", "mascot"), "-s", "/nonexistent.sock",
                              "--do-not-start", "prototypes", "list"],
                             env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}, capture_output=True, text=True,
                             timeout=30)
        self.assertNotIn("XDG_RUNTIME_DIR", out.stderr)

    @unittest.skipUnless(can_unshare(), "unshare cannot give the test a /tmp of its own")
    def test_daemon_refuses(self):
        out = private_tmp(f"mkdir -p /tmp/home/.local/share; {os.path.join(ROOT, 'build', 'mascotd')}; echo rc=$?; ls -A /tmp")
        self.assertIn("XDG_RUNTIME_DIR", out.stdout + out.stderr)
        self.assertNotIn("mascotd.sock", out.stdout, out.stdout + out.stderr)

    @unittest.skipUnless(can_unshare(), "unshare cannot give the test a /tmp of its own")
    def test_tool_does_not_use_tmp(self):
        # Someone else's socket waiting in /tmp: the sleep tool must not send to it
        listen = ("python3 -c 'import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(\"/tmp/mascotd-chat.sock\");"
                  " s.listen(); s.settimeout(5); c,_=s.accept(); print(\"GOT\", c.recv(100)); sys.stdout.flush()' > /tmp/got &"
                  " sleep 1;")
        tool = os.path.join(ROOT, "tools", "bin", "sleep_mode")
        out = private_tmp(f"{listen} MASCOT_TOOLS_ALLOWED=sleep_mode {tool} '{{\"wake_up\": \"now\"}}'; sleep 1; cat /tmp/got")
        self.assertNotIn("GOT", out.stdout, out.stdout + out.stderr)
        self.assertIn("XDG_RUNTIME_DIR", out.stdout + out.stderr)


class PosesPage(unittest.TestCase):
    """mascot prototypes poses writes a page for the browser: in XDG_RUNTIME_DIR, else under a name nobody can
    guess (with -s the CLI runs without XDG_RUNTIME_DIR, and another user could put a link at the old name first)"""

    def setUp(self):
        import importlib.util
        import sys
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
        spec = importlib.util.spec_from_file_location("client", os.path.join(ROOT, "src", "mascotctl", "client.py"))
        self.client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.client)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        saved = os.environ.get("XDG_RUNTIME_DIR"), tempfile.tempdir
        def restore():
            if saved[0] is None:
                os.environ.pop("XDG_RUNTIME_DIR", None)
            else:
                os.environ["XDG_RUNTIME_DIR"] = saved[0]
            tempfile.tempdir = saved[1]
        self.addCleanup(restore)
        tempfile.tempdir = self.tmp  # stands in for /tmp

    def test_in_runtime_dir(self):
        runtime = os.path.join(self.tmp, "run")
        os.mkdir(runtime, 0o700)
        os.environ["XDG_RUNTIME_DIR"] = runtime
        f, path = self.client.poses_file("Robo")
        f.close()
        self.assertEqual(path, os.path.join(runtime, "mascot-poses-Robo.html"))

    def test_without_runtime_dir_not_at_a_known_name(self):
        os.environ.pop("XDG_RUNTIME_DIR", None)
        victim = os.path.join(self.tmp, "victim")
        with open(victim, "w") as f:
            f.write("mine")
        os.symlink(victim, os.path.join(self.tmp, "mascot-poses-Robo.html"))
        f, path = self.client.poses_file("Robo")
        with f:
            f.write("<html>")
        with open(victim) as f:
            self.assertEqual(f.read(), "mine")
        self.assertNotEqual(path, os.path.join(self.tmp, "mascot-poses-Robo.html"))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


class DataDir(unittest.TestCase):
    @unittest.skipUnless(can_unshare(), "unshare cannot give the test a /tmp of its own")
    def test_daemon_makes_data_dir_private(self):
        # make install PREFIX=~/.local makes share/mascot 755 before mascotd runs: the todo list and the sessions
        # in it were readable by others. mascotd stops without XDG_RUNTIME_DIR, but after making it private
        out = private_tmp("mkdir -p /tmp/home/.local/share/mascot && chmod 755 /tmp/home/.local/share/mascot && "
                          f"{os.path.join(ROOT, 'build', 'mascotd')}; stat -c mode=%a /tmp/home/.local/share/mascot")
        self.assertIn("mode=700", out.stdout, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
