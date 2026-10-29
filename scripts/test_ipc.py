#!/usr/bin/env python3
"""Tests for how mascotd reads a packet from its IPC socket (src/protocol/connector.c), with a small C driver
built with AddressSanitizer: a client's packet must not make it read past what was received.

Run: python3 -I scripts/test_ipc.py
"""

import os
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


if __name__ == "__main__":
    unittest.main()
