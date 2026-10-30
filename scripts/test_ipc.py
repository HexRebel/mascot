#!/usr/bin/env python3
"""Tests for how mascotd reads a packet from its IPC socket (src/protocol/connector.c), with a small C driver
built with AddressSanitizer: a client's packet must not make it read past what was received.

Run: python3 -I scripts/test_ipc.py
"""

import os
import re
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DRIVER = r"""
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include "protocol/connector.h"

static int failed = 0;

// A packet as a client would send it: the 8-byte header (type, flags, length, object), then payload
static ipc_packet_t* received(uint16_t claimed_length, const uint8_t* payload, size_t payload_size, int32_t* result) {
    int sv[2];
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    int epfd = epoll_create1(0);
    ipc_connector_t* connector = ipc_initialize_connector(sv[0], epfd, NULL);
    uint8_t data[64] = {1, 0};
    memcpy(data + 2, &claimed_length, 2);
    memcpy(data + 8, payload, payload_size);
    send(sv[1], data, 8 + payload_size, 0);
    ipc_packet_t* packet = NULL;
    *result = ipc_connector_receive(connector, &packet);
    close(sv[1]);
    return *result == 0 ? packet : NULL;
}

int main(void) {
    int32_t result;

    // Honest length; bytes with 2 of data, read into a bigger buffer: only those 2 are copied
    uint8_t honest[] = {2, 0, 'h', 'i', 7};
    ipc_packet_t* packet = received(8 + sizeof(honest), honest, sizeof(honest), &result);
    if (!packet) {
        printf("an honest packet was refused (%d)\n", result);
        return 1;
    }
    char buffer[64];
    memset(buffer, 'x', sizeof(buffer));
    if (ipc_packet_read_bytes(packet, buffer, sizeof(buffer)) != 0 || memcmp(buffer, "hi", 2) != 0
        || buffer[2] != 'x') {
        printf("read_bytes copied more than the data\n");
        failed = 1;
    }
    uint8_t after = 0;
    if (ipc_packet_read_uint8(packet, &after) != 0 || after != 7) {
        printf("read_bytes moved on by the buffer's size, not the data's (next byte %d)\n", after);
        failed = 1;
    }

    // The header says 200 bytes, 13 came: refused, nothing read past them
    uint8_t lying[] = {100, 'a', 'b', 'c', 'd'};
    packet = received(200, lying, sizeof(lying), &result);
    if (packet) {
        char text[256];
        uint8_t length;
        ipc_packet_read_string(packet, text, &length);
        printf("a packet whose header claims more than was sent was taken\n");
        failed = 1;
    }

    // The length is one byte: a longer text (a pack's names) is cut at 255 bytes, before a character that does
    // not fit whole, and what follows it is still read right
    ipc_packet_t* out = ipc_allocate_packet(1024);
    char long_text[301];
    for (int i = 0; i < 300; i += 2) memcpy(long_text + i, "\xc3\xa9", 2);  // é 150 times
    long_text[300] = 0;
    ipc_packet_write_string(out, long_text);
    ipc_packet_write_uint8(out, 7);
    char text[256];
    uint8_t length = 0;
    after = 0;
    if (ipc_packet_read_string(out, text, &length) || length != 254 || memcmp(text, long_text, 254)
        || ipc_packet_read_uint8(out, &after) || after != 7) {
        printf("a long text was written as %u bytes, then %d\n", length, after);
        failed = 1;
    }
    ipc_free_packet(out);

    if (!failed)
        printf("ok\n");
    return failed;
}
"""


class Receive(unittest.TestCase):
    def test_packets_read_only_what_came(self):
        with tempfile.TemporaryDirectory() as tmp:
            driver = os.path.join(tmp, "driver.c")
            with open(driver, "w") as f:
                f.write(DRIVER)
            binary = os.path.join(tmp, "driver")
            src = os.path.join(ROOT, "src")
            built = subprocess.run(["cc", "-std=gnu11", "-g", "-fsanitize=address,undefined", "-I", src,
                                    "-I", os.path.join(src, "protocol"), driver,
                                    os.path.join(src, "protocol", "connector.c"), os.path.join(src, "list.c"),
                                    os.path.join(src, "utils.c"), "-o", binary],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            out = subprocess.run([binary], capture_output=True, text=True, timeout=30,
                                 env={"ASAN_OPTIONS": "detect_leaks=0", "PATH": "/usr/bin:/bin"})
            self.assertEqual((out.returncode, out.stdout.strip().splitlines()[-1:]), (0, ["ok"]),
                             out.stdout + out.stderr[-1500:])


IMPORT_DRIVER = r"""
#include <fcntl.h>
#include <semaphore.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>
#include "protocol/connector.h"
#include "protocol/server.h"
#include "protocol/wlshm.h"

static sem_t reading, go_on;

// The import thread reads the pack's header here: it waits, holding the import, while its client goes away
bool wlshm_read_header(const uint8_t header[WLSHM_HEADER_SIZE], char name[256], char version[128])
{
    (void)header; (void)name; (void)version;
    sem_post(&reading);
    sem_wait(&go_on);
    return false;
}

int main(int argc, char** argv)
{
    (void)argc;
    sem_init(&reading, 0, 0);
    sem_init(&go_on, 0, 0);
    int sv[2];
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    int epfd = epoll_create1(0);
    ipc_connector_t* connector = ipc_initialize_connector(sv[0], epfd, NULL);
    struct protocol_client* client = protocol_accept_connection(connector);
    int pack = open(argv[1], O_RDONLY);
    if (!protocol_server_import(client, pack, (uint32_t)PROTOCOL_OBJECT_IMPORT << 24 | 1, 0)) return 2;
    close(pack);
    sem_wait(&reading);
    // As mascotd does when the client hangs up (mascot import stopped with Ctrl-C)
    protocol_disconnect_client(client);
    ipc_destroy_connector(connector);
    sem_post(&go_on);
    usleep(300000);  // the thread finishes and frees the import
    puts("still running");
    return 0;
}
"""


CANCEL_DRIVER = r"""
#include <dirent.h>
#include <fcntl.h>
#include <semaphore.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include "protocol/connector.h"
#include "protocol/server.h"
#include "protocol/wlshm.h"

static sem_t unpacking, go_on, done;
static int store_fd;

bool wlshm_read_header(const uint8_t header[WLSHM_HEADER_SIZE], char name[256], char version[128])
{
    (void)header;
    strcpy(name, "pack");
    strcpy(version, "0.0.1");
    return true;
}

// The import thread stops at the pack's first member, its temporary directory made, while its client goes away
bool wlshm_member_path_safe(const char* path)
{
    (void)path;
    static int calls = 0;
    if (!calls++) {
        sem_post(&unpacking);
        sem_wait(&go_on);
    }
    return true;
}

bool wlshm_member_is_prompt(const char* path) { (void)path; return false; }
int wlshm_manifest_names(int dirfd, const char* name) { (void)dirfd; (void)name; return WLSHM_MANIFEST_NAMES; }
struct mascot_prototype* mascot_prototype_store_get(mascot_prototype_store* store, const char* name)
{
    (void)store; (void)name;
    return NULL;
}
int32_t mascot_prototype_store_get_fd(mascot_prototype_store* store) { (void)store; return store_fd; }
void mascot_prototype_link(const struct mascot_prototype* prototype) { (void)prototype; }
// The import's last step, installed or not
void mascot_prototype_unlink(const struct mascot_prototype* prototype) { (void)prototype; sem_post(&done); }

int main(int argc, char** argv)
{
    (void)argc;
    static struct protocol_server_state state;
    protocol_set_server_state(&state);
    store_fd = open(argv[2], O_DIRECTORY);
    sem_init(&unpacking, 0, 0);
    sem_init(&go_on, 0, 0);
    sem_init(&done, 0, 0);
    int sv[2];
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    int epfd = epoll_create1(0);
    ipc_connector_t* connector = ipc_initialize_connector(sv[0], epfd, NULL);
    struct protocol_client* client = protocol_accept_connection(connector);
    // Only a regular file is a pack: a socket's mode has the bits of S_IFREG in it as well
    int not_a_file[2];
    socketpair(AF_UNIX, SOCK_STREAM, 0, not_a_file);
    if (protocol_server_import(client, not_a_file[0], (uint32_t)PROTOCOL_OBJECT_IMPORT << 24 | 2, 0)) {
        puts("a socket was taken as a pack");
        return 1;
    }
    close(not_a_file[0]);
    close(not_a_file[1]);
    int pack = open(argv[1], O_RDONLY);
    if (!protocol_server_import(client, pack, (uint32_t)PROTOCOL_OBJECT_IMPORT << 24 | 1, 0)) return 2;
    close(pack);
    sem_wait(&unpacking);
    // mascot import stopped with Ctrl-C while mascotd unpacks
    protocol_disconnect_client(client);
    ipc_destroy_connector(connector);
    sem_post(&go_on);
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 10;
    if (sem_timedwait(&done, &deadline)) {
        puts("the import never finished");
        return 1;
    }
    usleep(200000);  // it frees the import
    DIR* store = fdopendir(store_fd);
    for (struct dirent* entry; (entry = readdir(store));)
        if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) printf("left in the store: %s\n", entry->d_name);
    closedir(store);
    close(sv[1]);
    close(epfd);
    puts("done");
    return 0;
}
"""

EXPORT_DRIVER = r"""
#include <fcntl.h>
#include <semaphore.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include "protocol/connector.h"
#include "protocol/server.h"

static sem_t exported;

// The export's last step
void mascot_prototype_unlink(const struct mascot_prototype* prototype) { (void)prototype; sem_post(&exported); }

int main(int argc, char** argv)
{
    (void)argc;
    // A message to a client that is gone is an error, and mascotd goes on (SIGPIPE is not ignored yet here; on
    // mascotd's SOCK_SEQPACKET Linux gives none, MSG_NOSIGNAL makes sure of it)
    int sv[2];
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    int epfd = epoll_create1(0);
    ipc_connector_t* gone = ipc_initialize_connector(sv[0], epfd, NULL);
    close(sv[1]);
    ipc_packet_t* packet = ipc_allocate_packet(0);
    ipc_packet_set_type(packet, 0x5B);
    if (ipc_connector_send(gone, packet) >= 0) {
        puts("a message to a client that is gone was sent");
        return 1;
    }
    ipc_destroy_connector(gone);
    close(sv[0]);

    signal(SIGPIPE, SIG_IGN);  // as mascotd's main does: an export writes to the client's fd
    sem_init(&exported, 0, 0);
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    ipc_connector_t* connector = ipc_initialize_connector(sv[0], epfd, NULL);
    struct protocol_client* client = protocol_accept_connection(connector);
    struct mascot_prototype prototype = {.name = "pack", .version = 1, .path_fd = open(argv[1], O_DIRECTORY)};
    int pipefd[2];
    if (pipe(pipefd)) return 2;
    if (!protocol_server_export(client, pipefd[1], (uint32_t)PROTOCOL_OBJECT_EXPORT << 24 | 1, &prototype)) return 2;
    close(pipefd[1]);
    char begun[4096];
    if (read(pipefd[0], begun, sizeof(begun)) <= 0) return 3;
    // mascot export stopped with Ctrl-C while mascotd writes the pack to its pipe
    close(pipefd[0]);
    protocol_disconnect_client(client);
    ipc_destroy_connector(connector);
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 10;
    if (sem_timedwait(&exported, &deadline)) {
        puts("the export never finished");
        return 1;
    }
    usleep(200000);  // it frees the export
    close(prototype.path_fd);
    close(sv[1]);
    close(epfd);
    puts("still running");
    return 0;
}
"""


CEILING_DRIVER = r"""
#include <dirent.h>
#include <fcntl.h>
#include <poll.h>
#include <semaphore.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include "protocol/connector.h"
#include "protocol/server.h"
#include "protocol/wlshm.h"

static sem_t done;
static int store_fd;

bool wlshm_read_header(const uint8_t header[WLSHM_HEADER_SIZE], char name[256], char version[128])
{
    (void)header;
    strcpy(name, "pack");
    strcpy(version, "0.0.1");
    return true;
}
bool wlshm_member_path_safe(const char* path) { (void)path; return true; }
bool wlshm_member_is_prompt(const char* path) { (void)path; return false; }
int wlshm_manifest_names(int dirfd, const char* name) { (void)dirfd; (void)name; return WLSHM_MANIFEST_NAMES; }
struct mascot_prototype* mascot_prototype_store_get(mascot_prototype_store* store, const char* name)
{
    (void)store; (void)name;
    return NULL;
}
int32_t mascot_prototype_store_get_fd(mascot_prototype_store* store) { (void)store; return store_fd; }
void mascot_prototype_link(const struct mascot_prototype* prototype) { (void)prototype; }
void mascot_prototype_unlink(const struct mascot_prototype* prototype) { (void)prototype; sem_post(&done); }

// Imports the pack argv[1] into the store argv[2] (built with small ceilings) and prints the code of its
// import.failed, or "finished", and what was left in the store
int main(int argc, char** argv)
{
    (void)argc;
    static struct protocol_server_state state;
    protocol_set_server_state(&state);
    store_fd = open(argv[2], O_DIRECTORY);
    setvbuf(stdout, NULL, _IONBF, 0);
    sem_init(&done, 0, 0);
    int sv[2];
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    int epfd = epoll_create1(0);
    ipc_connector_t* connector = ipc_initialize_connector(sv[0], epfd, NULL);
    struct protocol_client* client = protocol_accept_connection(connector);
    int pack = open(argv[1], O_RDONLY);
    if (!protocol_server_import(client, pack, (uint32_t)PROTOCOL_OBJECT_IMPORT << 24 | 1, 0)) return 2;
    close(pack);
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 10;
    if (sem_timedwait(&done, &deadline)) {
        puts("the import never finished");
        return 1;
    }
    // The import's last packet: import.failed (0x23) with its code, or import.finished (0x25)
    for (struct pollfd ready = {sv[1], POLLIN, 0}; poll(&ready, 1, 2000) == 1;) {
        uint8_t packet[4096];
        ssize_t got = recv(sv[1], packet, sizeof(packet), 0);
        if (got >= 12 && packet[0] == 0x23) {
            uint32_t code;
            memcpy(&code, packet + 8, 4);
            printf("failed %u\n", code);
            break;
        }
        if (got >= 8 && packet[0] == 0x25) {
            puts("finished");
            break;
        }
    }
    usleep(200000);  // it frees the import
    DIR* store = fdopendir(store_fd);
    for (struct dirent* entry; (entry = readdir(store));)
        if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) printf("left in the store: %s\n", entry->d_name);
    closedir(store);
    protocol_disconnect_client(client);
    ipc_destroy_connector(connector);
    close(sv[1]);
    close(epfd);
    return 0;
}
"""


def build_driver(tmp, source, sources, libs=()):
    """Builds source with mascotd's sources under AddressSanitizer: anything else the daemon would call is a stub
    that aborts. Returns the binary, or the compiler's complaint"""
    src = os.path.join(ROOT, "src")
    driver, stubs, binary = (os.path.join(tmp, n) for n in ("driver.c", "stubs.c", "driver"))
    with open(driver, "w") as f:
        f.write(source)
    open(stubs, "w").close()
    build = lambda: subprocess.run(["cc", "-std=gnu11", "-g", "-pthread", "-fsanitize=address,undefined",
                                    "-I", src, "-I", os.path.join(ROOT, "build"), driver, stubs,
                                    *(os.path.join(src, f) for f in sources), *libs, "-o", binary],
                                   capture_output=True, text=True)
    missing = sorted(set(re.findall(r"undefined reference to `(\w+)'", build().stderr)) - {"__clog", "__warn"})
    with open(stubs, "w") as f:
        f.write("#include <stdlib.h>\n"
                "void __clog(const char* c, const char* t, const char* f, int l, const char* x, ...) "
                "{ (void)c; (void)t; (void)f; (void)l; (void)x; }\n"
                "void __warn(const char* f, int l, const char* x, ...) { (void)f; (void)l; (void)x; }\n"
                + "".join(f"void {name}(void) {{ abort(); }}\n" for name in missing))
    built = build()
    return binary if built.returncode == 0 else built.stderr


def run_driver(binary, *args):
    return subprocess.run([binary, *args], capture_output=True, text=True, timeout=30,
                          env={"ASAN_OPTIONS": "detect_leaks=1", "PATH": "/usr/bin:/bin"})


PROTOCOL = ("protocol/server.c", "protocol/connector.c", "protocol/messages.c", "list.c")


class Transfers(unittest.TestCase):
    def test_import_outlives_its_client(self):
        # mascot import stopped with Ctrl-C while mascotd unpacks: mascotd waited for the import with a deadline
        # of 1970 (none), then sent SIGKILL to its thread, which ends the whole process (all mascots gone)
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "pack.wlshm"), "wb") as f:
                f.write(b"WLPK" + bytes(508))
            binary = build_driver(tmp, IMPORT_DRIVER, PROTOCOL)
            self.assertTrue(os.path.isfile(binary), binary)
            out = run_driver(binary, os.path.join(tmp, "pack.wlshm"))
            self.assertEqual((out.returncode, out.stdout), (0, "still running\n"), out.stderr)

    def test_stopped_import_installs_nothing(self):
        # Its thread went on alone after the client was gone, and installed the pack the user had stopped
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store")
            os.mkdir(store)
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                for name, data in (("manifest.json", b'{"name": "pack"}'), ("a.txt", b"a" * 100)):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    tar.addfile(member, io.BytesIO(data))
            with open(os.path.join(tmp, "pack.wlshm"), "wb") as f:
                f.write(b"WLPK" + bytes(508) + archive.getvalue())
            binary = build_driver(tmp, CANCEL_DRIVER, (*PROTOCOL, "io.c", "protocol/wlshm_unpack.c"), ("-larchive",))
            self.assertTrue(os.path.isfile(binary), binary)
            out = run_driver(binary, os.path.join(tmp, "pack.wlshm"), store)
            self.assertEqual((out.returncode, out.stdout), (0, "done\n"), out.stderr[-3000:])

    def test_unpacking_has_a_ceiling(self):
        # A pack of 212 KB unpacked to 210 MB in the store: one over the ceiling (here 1000 bytes and 4 members,
        # mascotd's are 256 MiB and 4096) is refused whole with code 10, and nothing is left behind
        import io
        import tarfile
        cases = {"under": ({"manifest.json": b"{}", "a": bytes(500)}, "finished\nleft in the store: pack\n"),
                 "bytes": ({"manifest.json": b"{}", "a": bytes(600), "b": bytes(600)}, "failed 10\n"),
                 "members": ({"manifest.json": b"{}", "d": None, "d/a": b"a", "d/b": b"b", "d/c": b"c"}, "failed 10\n")}
        with tempfile.TemporaryDirectory() as tmp:
            binary = build_driver(tmp, CEILING_DRIVER, (*PROTOCOL, "io.c", "protocol/wlshm_unpack.c"),
                                  ("-larchive", "-DWLSHM_UNPACKED_MAX=1000", "-DWLSHM_MEMBERS_MAX=4"))
            self.assertTrue(os.path.isfile(binary), binary)
            for case, (members, expected) in cases.items():
                store = os.path.join(tmp, "store-" + case)
                os.mkdir(store)
                archive = io.BytesIO()
                with tarfile.open(fileobj=archive, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                    for name, data in members.items():
                        member = tarfile.TarInfo(name)
                        if data is None:
                            member.type = tarfile.DIRTYPE
                            tar.addfile(member)
                        else:
                            member.size = len(data)
                            tar.addfile(member, io.BytesIO(data))
                pack = os.path.join(tmp, case + ".wlshm")
                with open(pack, "wb") as f:
                    f.write(b"WLPK" + bytes(508) + archive.getvalue())
                out = run_driver(binary, pack, store)
                self.assertEqual((out.returncode, out.stdout), (0, expected), (case, out.stderr[-3000:]))

    def test_export_to_a_pipe_outlives_its_client(self):
        # mascot export stopped with Ctrl-C: mascotd's next write to the pipe gave SIGPIPE, which ends the daemon.
        # The driver ignores it as mascotd's main must (checked below); the export stops, freed, and nothing leaks
        with tempfile.TemporaryDirectory() as tmp:
            pack = os.path.join(tmp, "pack")
            os.mkdir(pack)
            for i in range(4):  # Well over what a pipe holds, and zstd cannot make it smaller
                with open(os.path.join(pack, f"{i}.bin"), "wb") as f:
                    f.write(os.urandom(512 * 1024))
            binary = build_driver(tmp, EXPORT_DRIVER, PROTOCOL, ("-larchive",))
            self.assertTrue(os.path.isfile(binary), binary)
            out = run_driver(binary, pack)
            self.assertEqual((out.returncode, out.stdout), (0, "still running\n"), out.stderr[-3000:])
        with open(os.path.join(ROOT, "src", "mascotd.c")) as f:
            self.assertIn("signal(SIGPIPE, SIG_IGN);", f.read())


CONFIG_DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>
#include "config.h"
#include "protocol/connector.h"
#include "protocol/messages.h"
#include "protocol/server.h"

static int sv[2];

// What mascotd answers: "value <the value's strings joined>" or "notice <message>"
static void answer(void) {
    uint8_t data[4096];
    for (;;) {
        ssize_t got = recv(sv[1], data, sizeof(data), MSG_DONTWAIT);
        if (got < 8) return;
        size_t at = 8;
        if (data[0] == 0x54) {
            at += 1 + data[at];
            printf("value ");
            while (at < (size_t)got) {
                fwrite(data + at + 1, 1, data[at], stdout);
                at += 1 + data[at];
            }
            printf("\n");
        } else if (data[0] == 0x03) {
            at += 2;
            printf("notice %.*s\n", data[at], (char*)data + at + 1);
        }
    }
}

// A request as mascot sends it: the key, then the value in strings of at most `part` bytes
static ipc_packet_t* request(uint8_t type, const char* key, const char* value, size_t part) {
    ipc_packet_t* packet = ipc_allocate_packet(4000);
    ipc_packet_set_type(packet, type);
    ipc_packet_write_string(packet, key);
    for (size_t left = value ? strlen(value) : 0, i = 0; value && (i == 0 || left); ) {
        size_t n = left < part ? left : part;
        ipc_packet_write_uint8(packet, (uint8_t)n);
        if (n) ipc_packet_copy_to(packet, value, (uint16_t)n);
        value += n; left -= n; i++;
    }
    return packet;
}

// argv[1]: mascotd.conf; argv[2]: a value to set as CHAT_ROLES (sent 255 bytes a string), then get
int main(int argc, char** argv) {
    (void)argc;
    config_parse(argv[1]);
    printf("read chat_roles %s, chat_role %s\n", config_get_chat_roles() ? "set" : "(none)",
           config_get_chat_role() ? config_get_chat_role() : "(none)");
    socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv);
    int epfd = epoll_create1(0);
    ipc_connector_t* connector = ipc_initialize_connector(sv[0], epfd, NULL);
    struct protocol_client* client = protocol_accept_connection(connector);
    answer();
    ipc_packet_t* packet = request(0x52, "CHAT_ROLES", argv[2], 255);
    protocol_handler_set_config_key(client, packet);
    ipc_free_packet(packet);
    answer();
    packet = request(0x51, "CHAT_ROLES", NULL, 255);
    protocol_handler_get_config_key(client, packet);
    ipc_free_packet(packet);
    answer();
    protocol_disconnect_client(client);
    ipc_destroy_connector(connector);
    close(sv[1]);
    close(epfd);
    return 0;
}
"""


class Config(unittest.TestCase):
    def test_long_values_go_whole_both_ways(self):
        # mascot sent at most 255 bytes, so CHAT_ROLES with 20 pairs could only be written in mascotd.conf (which
        # takes lines of 1023), and config get cut every value at 254. Now a value goes in strings of 255 to
        # CONFIG_VALUE_MAX (1000) both ways; more is refused, and a line of mascotd.conf over 1023 bytes is left
        # out with a warning instead of being cut (its rest was read as a line of its own)
        roles = ";".join(f"Mascot{i}=rôle-{i}" for i in range(30))  # 30 pairs, with UTF-8 cut between strings
        self.assertGreater(len(roles.encode()), 255)
        with tempfile.TemporaryDirectory() as tmp:
            conf = os.path.join(tmp, "mascotd.conf")
            binary = build_driver(tmp, CONFIG_DRIVER, (*PROTOCOL, "config.c"))
            self.assertTrue(os.path.isfile(binary), binary)

            def run(value):
                with open(conf, "w") as f:
                    f.write("chat_roles=" + "x=y;" * 300 + "\nchat_role=after\n")
                out = run_driver(binary, conf, value)
                self.assertEqual(out.returncode, 0, out.stderr[-3000:])
                return out.stdout
            self.assertEqual(run(roles), f"read chat_roles (none), chat_role after\nvalue {roles}\nvalue {roles}\n")
            with open(conf) as f:
                self.assertIn(f"chat_roles={roles}\n", f.read())  # and mascotd writes it whole in mascotd.conf
            self.assertEqual(run("a" * 1001).splitlines()[1:], ["notice config.warning.long", "value "])
            self.assertEqual(run("a" * 1000).splitlines()[1:], ["value " + "a" * 1000] * 2)


class Client(unittest.TestCase):
    """How the mascot command reads the daemon's texts: a length byte of 128-255 and bytes that are not UTF-8
    (a pack's action and behavior names, its author) are read, not a crash"""

    def test_long_and_odd_texts_are_read(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
        import ipc_protocol
        text = "é".encode() * 100 + b"\xff\xfe"  # 202 bytes, the last two not UTF-8
        one = bytes([len(text)]) + text
        for packet, read in ((ipc_protocol.PrototypeName, "name"), (ipc_protocol.PrototypeDisplayName, "display_name"),
                             (ipc_protocol.PrototypePath, "path"), (ipc_protocol.PrototypeAddAction, "action"),
                             (ipc_protocol.PrototypeAddBehavior, "behavior"), (ipc_protocol.PrototypeAuthor, "author"),
                             (ipc_protocol.ImportFinished, "relative_path")):
            p = packet(0, 0, 1, b"\0" * 8 + one)
            p.decode()
            self.assertTrue(getattr(p, read).startswith("é" * 100), packet.__name__)
        p = ipc_protocol.ConfigKey(0, 0, 1, b"\0" * 8 + one + one)
        p.decode()
        self.assertTrue(p.key.startswith("é") and p.value.startswith("é"))
        p = ipc_protocol.EnvironmentChanged(0, 0, 1, b"\0" * 8 + one + one + bytes(16) + bytes(4))
        p.decode()
        self.assertTrue(p.name.startswith("é") and p.description.startswith("é"))


    def test_texts_sent_are_counted_in_bytes(self):
        # Their length byte was signed and counted letters: 128 letters stopped mascot, and each é cut a byte off
        import sys
        sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
        import ipc_protocol
        value = "Français, réponds brièvement " * 5  # 145 letters, 155 bytes
        data = ipc_protocol.SetConfigKey("CHAT_ROLE", value).serialize()
        self.assertEqual(data[0], 9)
        self.assertEqual(data[10], len(value.encode()))
        self.assertEqual(data[11:].decode(), value)
        for packet in (ipc_protocol.GetConfigKey("CHAT_ROLE" * 20), ipc_protocol.ApplyBehavior(1, "Fall" * 50)):
            data = packet.serialize()
            self.assertEqual(data[0], len(data) - 1, type(packet).__name__)
        # Over 255 bytes in more strings, which mascotd 0.8.1 joins (each whole bytes: é may be cut between them)
        data = ipc_protocol.SetConfigKey("CHAT_ROLE", "é" * 128).serialize()
        self.assertEqual((data[10], data[11 + 255], len(data)), (255, 1, 11 + 255 + 2))
        self.assertEqual((data[11:11 + 255] + data[11 + 256:]).decode(), "é" * 128)
        with self.assertRaises(ValueError):
            ipc_protocol.SetConfigKey("CHAT_ROLE", "x" * 1001).serialize()  # more than a setting may be
        # What mascotd sends back is joined the same way; an older one sent one string
        p = ipc_protocol.ConfigKey(0, 0, 1, b"\0" * 8 + bytes([3]) + b"KEY" + bytes([255]) + b"a" * 255 + bytes([2]) + b"bc")
        p.decode()
        self.assertEqual((p.key, p.value), ("KEY", "a" * 255 + "bc"))
        import client
        # The same with mascotd running or not: mascotd.conf takes the line, and mascot sends it whole
        self.assertIsNone(client.config_value_problem("CHAT_ROLES", "x" * 1000))
        self.assertIn("at most 1000", client.config_value_problem("CHAT_ROLES", "x" * 1001) or "")
        self.assertNotIn("mascotd.conf instead", client.config_value_problem("CHAT_ROLES", "x" * 1001) or "")
        self.assertIsNone(client.config_value_problem("CHAT_ROLES", ";".join(f"Mascot{i}=role-{i}" for i in range(20))))
        self.assertIsNone(client.config_value_problem("CHAT_ROLES", "Robo=robo-role," * 17))
        self.assertIn("UTF-8", client.config_value_problem("CHAT_ROLE", "a\udcff") or "")


    def test_too_long_to_send_is_said_not_a_traceback(self):
        # mascot prototypes reload, config get, summon --behavior and set-behavior with a text over 255 bytes
        # stopped with a ValueError traceback
        import contextlib
        import io
        import socket
        import sys
        sys.path.insert(0, os.path.join(ROOT, "src", "mascotctl"))
        import client
        import ipc_protocol
        packets = (ipc_protocol.ReloadPrototype("/x" * 200), ipc_protocol.GetConfigKey("K" * 256),
                   ipc_protocol.Spawn(1, 1, 0, 0, "Fall" * 64), ipc_protocol.ApplyBehavior(1, "Fall" * 64),
                   ipc_protocol.ReloadPrototype("\ud800"))
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        with a, b:
            c = client.Client.__new__(client.Client)
            c.socket = a
            for packet in packets:
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
                    c.queue_packet(packet)
                self.assertEqual(stop.exception.code, 1, type(packet).__name__)
                self.assertTrue(err.getvalue().startswith("Not sent: "), err.getvalue())
            # A path from the command line that is not UTF-8 is sent as its own bytes
            c.queue_packet(ipc_protocol.ReloadPrototype("/tmp/\udcff"))
            self.assertEqual(b.recv(100)[8:], bytes([6]) + b"/tmp/\xff")


if __name__ == "__main__":
    unittest.main()
