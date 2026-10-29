#!/usr/bin/env python3
"""Tests for importing .wlshm packs from others: the daemon's header and member checks (src/protocol/wlshm.c,
built with a small C driver) and the CLI's own check before it sends a pack (client.py's wlshm_adjusted).

Run: python3 -I scripts/test_import.py
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "protocol/wlshm.h"

static int failed = 0;

static void prompt(const char* path, bool expected) {
    if (wlshm_member_is_prompt(path) != expected) {
        printf("prompt %s: expected %s\n", path, expected ? "the pack's prompt" : "another file");
        failed = 1;
    }
}

static void member(const char* path, bool expected) {
    if (wlshm_member_path_safe(path) != expected) {
        printf("member %s: expected %s\n", path ? path : "(null)", expected ? "safe" : "refused");
        failed = 1;
    }
}

// A header with the given name and version bytes and length bytes (which may lie)
static void header(const char* label, const char* name, int name_len, const char* version, int version_len,
                   bool expected, const char* expected_name) {
    uint8_t h[WLSHM_HEADER_SIZE] = {'W', 'L', 'P', 'K'};
    size_t at = 4;
    h[at++] = (uint8_t)name_len;
    memcpy(h + at, name, strlen(name) < WLSHM_HEADER_SIZE - at ? strlen(name) : WLSHM_HEADER_SIZE - at);
    at += name_len;
    if (at < WLSHM_HEADER_SIZE) {
        h[at++] = (uint8_t)version_len;
        size_t room = WLSHM_HEADER_SIZE - at;
        memcpy(h + at, version, strlen(version) < room ? strlen(version) : room);
    }
    char got_name[256], got_version[128];
    memset(got_name, 'x', sizeof(got_name));
    memset(got_version, 'x', sizeof(got_version));
    bool ok = wlshm_read_header(h, got_name, got_version);
    if (ok != expected) {
        printf("header %s: expected %s\n", label, expected ? "read" : "refused");
        failed = 1;
    } else if (ok && ((expected_name && strcmp(got_name, expected_name) != 0)
                      || strnlen(got_version, sizeof(got_version)) >= sizeof(got_version))) {
        printf("header %s: read name '%s'\n", label, got_name);
        failed = 1;
    }
}

int main(void) {
    member("manifest.json", true);
    member("assets/shime1.png", true);
    member("assets/", true);
    member("./assets/a.png", true);
    member(NULL, false);
    member("", false);
    member("/home/u/.bashrc", false);
    member("../x", false);
    member("..", false);
    member("assets/../../x", false);
    member("assets/..", false);
    member("a/../b", false);

    // A pack's own prompt.md would become the mascot's personality: it is never unpacked
    prompt("prompt.md", true);
    prompt("./prompt.md", true);
    prompt(".//prompt.md", true);
    prompt("assets/prompt.md", false);
    prompt("prompt.md.txt", false);
    prompt("Prompt.md", false);

    char long_name[300];
    memset(long_name, 'a', sizeof(long_name));
    long_name[299] = 0;
    char long_version[300];
    memset(long_version, '1', sizeof(long_version));
    long_version[299] = 0;

    header("plain", "Shimeji.Robo", 12, "0.0.1", 5, true, "Shimeji.Robo");
    header("version too long for its buffer", "Shimeji.Robo", 12, long_version, 200, false, "");
    header("version past the header", long_name, 255, long_version, 255, false, "");
    header("longest name", long_name, 255, "", 0, false, NULL);  // fits (5 + 255 + 1 <= 512), but no version
    header("empty name", "", 0, "0.0.1", 5, false, "");
    header("dot dot", "..", 2, "0.0.1", 5, false, "");
    header("dot", ".", 1, "0.0.1", 5, false, "");
    header("hidden", ".unpackingMascot1", 17, "0.0.1", 5, false, "");
    header("slash", "../../x", 7, "0.0.1", 5, false, "");
    header("nul inside", "Ro\0bo", 5, "0.0.1", 5, false, "");
    if (!failed)
        printf("ok\n");
    return failed;
}
"""


class Daemon(unittest.TestCase):
    """src/protocol/wlshm.c: what mascotd reads from a pack before it unpacks anything"""

    def test_header_and_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            driver = os.path.join(tmp, "driver.c")
            with open(driver, "w") as f:
                f.write(DRIVER)
            binary = os.path.join(tmp, "driver")
            built = subprocess.run(["cc", "-std=gnu11", "-Wall", "-Werror", "-fsanitize=address,undefined",
                                    "-I", os.path.join(ROOT, "src"), driver,
                                    os.path.join(ROOT, "src", "protocol", "wlshm.c"), "-o", binary],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            out = subprocess.run([binary], capture_output=True, text=True, timeout=30)
            self.assertEqual((out.returncode, out.stdout.strip()), (0, "ok"), out.stdout + out.stderr)


def pack(members: dict, name: str = "Shimeji.Bad") -> str:
    """A .wlshm with the given member names and contents (None: a directory), written to a temp file"""
    sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as tar:
        base = {"manifest.json": json.dumps({"name": name}).encode(), "behaviors.json": b"{}", "actions.json": b"{}"}
        for member_name, content in {**base, **members}.items():
            info = tarfile.TarInfo(member_name)
            if content is None:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            else:
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
    f = tempfile.NamedTemporaryFile(suffix=".wlshm", delete=False)
    f.write(Cli.client.wlshm_header(name, "0.0.1") + data.getvalue())
    f.close()
    return f.name


class Cli(unittest.TestCase):
    """client.py refuses a pack whose members would leave the mascot's directory, before the daemon sees it"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
        spec = importlib.util.spec_from_file_location("client", os.path.join(ROOT, "src", "mascotctl", "client.py"))
        cls.client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.client)

    def adjusted(self, members, name="Shimeji.Bad"):
        path = pack(members, name)
        try:
            return self.client.wlshm_adjusted(path, False, "none", "none")
        finally:
            os.unlink(path)

    def test_plain_pack_passes(self):
        out, manifest, _ = self.adjusted({"assets/": None, "assets/shime1.png": b"png"})
        out.close()
        self.assertEqual(manifest["name"], "Shimeji.Bad")

    def test_traversal_refused(self):
        for bad in ("../../.bashrc", "/home/u/.bashrc", "assets/../../x", ".."):
            with self.assertRaises(ValueError, msg=bad):
                self.adjusted({bad: b"echo owned"})

    def test_links_refused(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as tar:
            for member_name in ("manifest.json", "behaviors.json", "actions.json"):
                info = tarfile.TarInfo(member_name)
                info.size = 2
                tar.addfile(info, io.BytesIO(b"{}"))
            link = tarfile.TarInfo("assets/shime1.png")
            link.type = tarfile.SYMTYPE
            link.linkname = "/home/u/.ssh/id_ed25519"
            tar.addfile(link)
        with tempfile.NamedTemporaryFile(suffix=".wlshm", delete=False) as f:
            f.write(self.client.wlshm_header("Shimeji.Bad", "0.0.1") + data.getvalue())
        try:
            with self.assertRaises(ValueError):
                self.client.wlshm_adjusted(f.name, False, "none", "none")
        finally:
            os.unlink(f.name)

    def test_bad_pack_name_refused(self):
        for bad in ("../../x", "a/b", "..", ".hidden"):
            with self.assertRaises(ValueError, msg=bad):
                self.adjusted({}, name=bad)

    def test_prompt_left_out(self):
        # Someone else's pack does not bring its own personality (prompt.md); a role gives it one
        out, _, changes = self.adjusted({"prompt.md": b"You are evil", "assets/shime1.png": b"png"})
        out.seek(512)
        with tarfile.open(fileobj=io.BytesIO(out.read())) as tar:
            names = tar.getnames()
        out.close()
        self.assertNotIn("prompt.md", names)
        self.assertIn("assets/shime1.png", names)
        self.assertTrue(any("prompt.md" in c for c in changes), changes)

    def test_header_fits_in_512(self):
        self.assertEqual(len(self.client.wlshm_header("a" * 400, "1" * 400)), 512)


if __name__ == "__main__":
    unittest.main()
