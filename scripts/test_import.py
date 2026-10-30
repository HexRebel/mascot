#!/usr/bin/env python3
"""Tests for importing .wlshm packs from others: the daemon's header and member checks (src/protocol/wlshm.c,
built with a small C driver) and the CLI's own check before it sends a pack (client.py's wlshm_adjusted).

Run: python3 -I scripts/test_import.py
"""

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DRIVER = r"""
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
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

// An unpacked pack with this manifest.json (NULL: none): whether its name is the header's
static void manifest(const char* label, const char* text, const char* name, bool expected) {
    char dir[] = "/tmp/wlshm-test-XXXXXX";
    if (!mkdtemp(dir)) { printf("mkdtemp\n"); failed = 1; return; }
    int fd = open(dir, O_DIRECTORY);
    if (text) {
        int file = openat(fd, "manifest.json", O_WRONLY | O_CREAT, 0600);
        if (write(file, text, strlen(text)) < 0) failed = 1;
        close(file);
    }
    if (wlshm_manifest_names(fd, name) != expected) {
        printf("manifest %s: expected %s\n", label, expected ? "the header's name" : "refused");
        failed = 1;
    }
    unlinkat(fd, "manifest.json", 0);
    close(fd);
    rmdir(dir);
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
    // The header's name chooses what is replaced, the manifest's what is loaded: they must be the same
    manifest("same", "{\"name\": \"Shimeji.Robo\", \"version\": \"0.0.1\"}", "Shimeji.Robo", true);
    manifest("another", "{\"name\": \"Shimeji.Robo\"}", "Innocent", false);
    manifest("prefix", "{\"name\": \"Shimeji.Robo\"}", "Shimeji.Rob", false);
    manifest("none", NULL, "Shimeji.Robo", false);
    manifest("no name", "{\"version\": \"0.0.1\"}", "Shimeji.Robo", false);
    manifest("name not text", "{\"name\": 1}", "1", false);
    manifest("not JSON", "{name: Shimeji.Robo", "Shimeji.Robo", false);
    manifest("not an object", "[\"Shimeji.Robo\"]", "Shimeji.Robo", false);
    // json.h keeps both: the loader took the last, this the first
    manifest("two names", "{\"name\": \"Innocent\", \"name\": \"Shimeji.Robo\"}", "Innocent", false);
    manifest("two names, header the last", "{\"name\": \"Innocent\", \"name\": \"Shimeji.Robo\"}", "Shimeji.Robo", false);
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


ATLAS_DRIVER = r"""
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include "mascot_atlas.h"

// The daemon's log and Wayland buffers, not needed to load sprites
void __error(const char* f, int l, const char* x, ...) { (void)f; (void)l; (void)x; abort(); }
void __warn(const char* f, int l, const char* x, ...) { (void)f; (void)l; va_list a; va_start(a, x); vprintf(x, a); va_end(a); printf("\n"); }
void __info(const char* f, int l, const char* x, ...) { (void)f; (void)l; (void)x; }
void __debug(const char* f, int l, const char* x, ...) { (void)f; (void)l; (void)x; }
static int factory, buffer;
environment_buffer_factory_t* environment_buffer_factory_new() { return (environment_buffer_factory_t*)&factory; }
void environment_buffer_factory_destroy(environment_buffer_factory_t* f) { (void)f; }
bool environment_buffer_factory_write(environment_buffer_factory_t* f, const void* d, size_t s) { (void)f; (void)d; (void)s; return true; }
void environment_buffer_factory_done(environment_buffer_factory_t* f) { (void)f; }
environment_buffer_t* environment_buffer_factory_create_buffer(environment_buffer_factory_t* f, int32_t w, int32_t h, uint32_t s, uint32_t o) { (void)f; (void)w; (void)h; (void)s; (void)o; return (environment_buffer_t*)&buffer; }
void environment_buffer_add_to_input_region(environment_buffer_t* b, int32_t x, int32_t y, int32_t w, int32_t h) { (void)b; (void)x; (void)y; (void)w; (void)h; }
void environment_buffer_destroy(environment_buffer_t* b) { (void)b; }

int main(int argc, char** argv) {
    (void)argc;
    struct mascot_atlas* atlas = mascot_atlas_new(argv[1]);
    if (!atlas) { printf("refused\n"); return 0; }
    printf("sprites %u\n", (unsigned)atlas->sprite_count);
    mascot_atlas_destroy(atlas);
    return 0;
}
"""

# A 1x1 QOI picture: header, one RGBA pixel, end marker
QOI = b"qoif" + (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([4, 0, 0xFE, 1, 2, 3]) + bytes(7) + b"\x01"


def big_qoi(width, height):
    """A QOI picture of one opaque black, small on disk however big: runs of 62 pixels"""
    pixels = width * height
    return (b"qoif" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([4, 0])
            + bytes([0xFD]) * (pixels // 62) + (bytes([0xC0 | (pixels % 62 - 1)]) if pixels % 62 else b"")
            + bytes(7) + b"\x01")


class Atlas(unittest.TestCase):
    def driver(self, tmp):
        driver = os.path.join(tmp, "driver.c")
        with open(driver, "w") as f:
            f.write(ATLAS_DRIVER)
        binary = os.path.join(tmp, "driver")
        built = subprocess.run(["cc", "-std=gnu11", "-Wall", "-fsanitize=address,undefined", "-I",
                                os.path.join(ROOT, "src"), "-I", os.path.join(ROOT, "build"), driver,
                                os.path.join(ROOT, "src", "mascot_atlas.c"), os.path.join(ROOT, "src", "io.c"),
                                "-o", binary], capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stderr)
        return binary

    def atlas(self, binary, sprites):
        out = subprocess.run([binary, sprites], capture_output=True, text=True, timeout=120,
                             env={"ASAN_OPTIONS": "detect_leaks=0", "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 0, out.stdout[-300:] + out.stderr[-1500:])
        return out.stdout.strip().splitlines()[-1]

    def test_picture_size_has_a_ceiling(self):
        # Each picture was read whole and decoded up to 400 million pixels (1.6 GB, twice over for the mirrored
        # copy), and the Wayland pool's size is 32 bits: a pack of a few big pictures took the daemon down
        with tempfile.TemporaryDirectory() as tmp:
            binary = self.driver(tmp)
            for name, pictures, expected in (("fits", [(2048, 2048)], "sprites 1"), ("wide", [(2049, 1)], "refused"),
                                             ("big", [(3000, 3000)], "refused"),
                                             ("many", [(2048, 2048)] * 9, "refused"),
                                             ("lie", [(1, 1, 64 * 1024 * 1024)], "refused")):
                sprites = os.path.join(tmp, name)
                os.mkdir(sprites)
                for i, (width, height, *padding) in enumerate(pictures):
                    with open(os.path.join(sprites, f"{i}.qoi"), "wb") as f:
                        f.write(big_qoi(width, height) + bytes(padding[0] if padding else 0))
                self.assertEqual(self.atlas(binary, sprites), expected, name)

    def test_sprite_count_has_a_ceiling(self):
        # The count was a uint16_t and the loops ran to sprite_count*2 as an int: with more than 32767 sprites
        # they never ended and wrote past the sprites (a pack from the net can hold that many files)
        with tempfile.TemporaryDirectory() as tmp:
            binary = self.driver(tmp)
            for count, expected in ((3, "sprites 3"), (4096, "sprites 4096"), (4097, "refused"), (32768, "refused")):
                sprites = os.path.join(tmp, f"img{count}")
                os.mkdir(sprites)
                for i in range(count):
                    with open(os.path.join(sprites, f"{i}.qoi"), "wb") as f:
                        f.write(QOI)
                try:
                    out = subprocess.run([binary, sprites], capture_output=True, text=True, timeout=60,
                                         env={"ASAN_OPTIONS": "detect_leaks=0", "PATH": "/usr/bin:/bin"})
                except subprocess.TimeoutExpired:
                    self.fail(f"{count} sprites: no end")
                self.assertEqual((out.returncode, out.stdout.strip().splitlines()[-1:]), (0, [expected]),
                                 f"{count}: " + out.stdout[-300:] + out.stderr[-1500:])


PARSER_DRIVER = ATLAS_DRIVER.split("int main(")[0].replace('#include "mascot_atlas.h"', '#include "mascot_config_parser.h"') + r"""
// Each next behavior must be one of the behaviors loaded, not something else in its place
static bool defined(struct mascot_prototype* p, const struct mascot_behavior* b) {
    for (uint16_t i = 0; i < p->behavior_count; i++) if (p->behavior_definitions[i] == b) return true;
    return false;
}

int main(int argc, char** argv) {
    (void)argc;
    struct mascot_prototype* prototype = mascot_prototype_new();
    int result = (int)mascot_prototype_load(prototype, argv[1], argv[2]);
    if (!result) {
        for (uint16_t i = 0; i < prototype->behavior_count; i++) {
            const struct mascot_behavior* b = prototype->behavior_definitions[i];
            for (uint16_t j = 0; j < b->next_behaviors_count; j++)
                if (!defined(prototype, b->next_behavior_list[j].behavior)) { printf("undefined next behavior\n"); abort(); }
        }
    }
    mascot_prototype_unlink(prototype);  // as the daemon does with one it refused
    printf("result %d\n", result);
    return 0;
}
"""

MANIFEST = {"name": "Shimeji.T", "version": "0.0.1", "programs": "programs.json", "actions": "actions.json",
            "behaviors": "behaviors.json", "assets": "assets"}


class Manifest(unittest.TestCase):
    """mascot_prototype_load with a pack's own manifest.json: its file names stay inside the pack, and a file that
    is not a regular file (a FIFO: ftell -1, a read of SIZE_MAX bytes into one) is refused, not read"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        driver = os.path.join(self.root, "driver.c")
        with open(driver, "w") as f:
            f.write(PARSER_DRIVER)
        self.binary = os.path.join(self.root, "driver")
        # Only the loading runs: the rest of the daemon (Wayland, the mascots) is left out, each function it would
        # call a stub that aborts
        stubs = os.path.join(self.root, "stubs.c")
        open(stubs, "w").close()
        build = lambda: subprocess.run(["cc", "-std=gnu11", "-fsanitize=address,undefined", "-I", os.path.join(ROOT, "src"),
                                        "-I", os.path.join(ROOT, "build"), driver, stubs,
                                        *(os.path.join(ROOT, "src", f) for f in ("mascot_config_parser.c",
                                                                                 "mascot_atlas.c", "io.c",
                                                                                 "expressions.c")),
                                        "-lm", "-o", self.binary], capture_output=True, text=True)
        # Except the log and telling clients a refused prototype is gone, which do nothing
        missing = sorted(set(re.findall(r"undefined reference to `(\w+)'", build().stderr))
                         - {"__clog", "protocol_server_prototype_withdraw"})
        with open(stubs, "w") as f:
            f.write("#include <stdlib.h>\nvoid __clog(const char* c, const char* t, const char* f, int l, const char* x, ...) "
                    "{ (void)c; (void)t; (void)f; (void)l; (void)x; }\n"
                    "void protocol_server_prototype_withdraw(const void* p) { (void)p; }\n"
                    + "".join(f"void {name}(void) {{ abort(); }}\n" for name in missing))
        built = build()
        self.assertEqual(built.returncode, 0, built.stderr)
        self.pack("Outside", {})  # another pack, with the files a manifest could point at

    def pack(self, name, manifest_changes, manifest_text=None):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.join(path, "assets"))
        with open(os.path.join(path, "assets", "0.qoi"), "wb") as f:
            f.write(QOI)
        with open(os.path.join(path, "manifest.json"), "w") as f:
            f.write(manifest_text if manifest_text is not None else json.dumps({**MANIFEST, **manifest_changes}))
        return path

    def load(self, name, leaks=False):
        try:
            out = subprocess.run([self.binary, self.root, name], capture_output=True, text=True, timeout=20,
                                 env={"ASAN_OPTIONS": f"detect_leaks={int(leaks)}", "PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired:
            self.fail(f"{name}: no end (a FIFO read?)")
        self.assertEqual(out.returncode, 0, f"{name}: " + out.stdout[-300:] + out.stderr[-1500:])
        return int(out.stdout.strip().splitlines()[-1].split()[1])

    def test_inside_the_pack_gets_to_programs(self):
        # No programs.json: the manifest itself was fine
        self.pack("Plain", {})
        self.assertEqual(self.load("Plain"), 11)  # PROTOTYPE_LOAD_PROGRAMS_NOT_FOUND

    def test_names_outside_the_pack_refused(self):
        outside = os.path.join(self.root, "Outside")
        with open(os.path.join(outside, "programs.json"), "w") as f:
            f.write("{}")
        for i, changes in enumerate(({"assets": os.path.join(outside, "assets")}, {"assets": "../Outside/assets"},
                                     {"programs": "../Outside/programs.json"}, {"programs": "/etc/hostname"},
                                     {"actions": "a/../../Outside/actions.json"}, {"behaviors": "/dev/zero"},
                                     {"assets": ""}, {"programs": "."})):
            self.pack(f"P{i}", changes)
            self.assertEqual(self.load(f"P{i}"), 6, changes)  # PROTOTYPE_LOAD_MANIFEST_INVALID

    def test_only_regular_files_are_read(self):
        fifo = self.pack("Fifo", {})
        os.mkfifo(os.path.join(fifo, "programs.json"))
        self.assertIn(self.load("Fifo"), (11, 12))
        link = self.pack("Link", {})
        with open(os.path.join(self.root, "Outside", "programs.json"), "w") as f:
            f.write("{}")
        os.symlink(os.path.join(self.root, "Outside", "programs.json"), os.path.join(link, "programs.json"))
        self.assertIn(self.load("Link"), (11, 12))
        manifest_fifo = self.pack("ManifestFifo", {})
        os.unlink(os.path.join(manifest_fifo, "manifest.json"))
        os.mkfifo(os.path.join(manifest_fifo, "manifest.json"))
        self.assertIn(self.load("ManifestFifo"), (5, 6))

    def test_one_name_only(self):
        # The import checks the header against one name: a second one must not be the one loaded
        self.pack("Two", {}, manifest_text=json.dumps(MANIFEST)[:-1] + ', "name": "Shimeji.Robo"}')
        self.assertEqual(self.load("Two"), 6)

    def test_broken_manifest_does_not_stop_the_daemon(self):
        # ERROR() ends the daemon: one bad pack must only be left out
        self.pack("Broken", {}, manifest_text="{not json")
        self.assertEqual(self.load("Broken"), 6)


class Pack(Manifest):
    """Robo with one of its files broken the way a pack from the net could be: the daemon loads every pack in the
    prototypes directory at each start, so a crash here stops it for good"""

    def robo(self, name, file, change):
        path = os.path.join(self.root, name)
        shutil.copytree(os.path.join(ROOT, "prototypes", "Shimeji.Robo"), path)
        with open(os.path.join(path, file)) as f:
            data = json.load(f)
        with open(os.path.join(path, file), "w") as f:
            json.dump(change(data), f)
        return path

    def behavior(self, data, **changes):
        data["definitions"][0].update(changes)
        return data

    def test_robo_loads(self):
        self.robo("Robo", "behaviors.json", lambda data: data)
        self.assertEqual(self.load("Robo"), 0)

    def test_empty_programs(self):
        self.robo("Programs", "scripts.json", lambda data: {})
        self.assertEqual(self.load("Programs"), 12)  # PROTOTYPE_LOAD_PROGRAMS_INVALID

    def test_definitions_that_are_not_objects(self):
        for i, bad in enumerate((7, "x", None, True, [7], [None], [{}])):
            self.robo(f"Definition{i}", "behaviors.json", lambda data: {**data, "definitions": [bad] + data["definitions"]})
            self.assertEqual(self.load(f"Definition{i}"), 0, bad)
            self.robo(f"Root{i}", "behaviors.json", lambda data: {**data, "root_behavior_list": [bad]})
            self.assertEqual(self.load(f"Root{i}"), 0, bad)

    def test_count_must_be_the_list(self):
        # The count decided how many of the list were read, past the ones given
        for i, count in enumerate((7, -1, 99999999)):
            self.robo(f"Count{i}", "behaviors.json", lambda data: self.behavior(data, next_behavior_list_count=count))
            self.assertEqual(self.load(f"Count{i}"), 0, count)

    def test_content_count_must_be_the_content(self):
        # An action holds at most 64 pieces of content: the count was read (and freed) past them
        def change(count):
            def apply(data):
                action = next(a for a in data if a["content"])
                action["content_count"] = count
                return data
            return apply
        for i, count in enumerate((9999, 65, 0)):
            self.robo(f"Content{i}", "actions.json", change(count))
            self.load(f"Content{i}", leaks=True)

    def test_frame_count_must_be_the_frames(self):
        def change(count):
            def apply(data):
                animation = next(c for a in data for c in a["content"] if c.get("frames"))
                animation["frame_count"] = count
                return data
            return apply
        for i, count in enumerate((9999, -1)):
            self.robo(f"Frames{i}", "actions.json", change(count))
            self.load(f"Frames{i}", leaks=True)

    def test_long_next_list(self):
        # A behavior holds at most 128 next behaviors: more were written past it
        refs = [{"name": "Look", "frequency": 1}] * 200
        self.robo("Long", "behaviors.json",
                  lambda data: self.behavior(data, next_behavior_list=refs, next_behavior_list_count=200))
        self.assertEqual(self.load("Long"), 0)

    def test_refused_pack_is_freed(self):
        # The daemon reads each pack again at every reload: a refused one must not leave its files behind in memory
        self.robo("Refused", "scripts.json", lambda data: {"programs": {}})
        self.assertEqual(self.load("Refused", leaks=True), 12)
        self.robo("Loaded", "scripts.json", lambda data: data)
        self.assertEqual(self.load("Loaded", leaks=True), 0)

    def test_unknown_next_behavior(self):
        self.robo("Unknown", "behaviors.json", lambda data: self.behavior(
            data, next_behavior_list=[{"name": "Nobody", "frequency": 1}], next_behavior_list_count=1))
        self.assertEqual(self.load("Unknown"), 0)


if __name__ == "__main__":
    unittest.main()
