#!/usr/bin/env python3
"""Connect to mascotd, print handshake result and every mascot.tapped (0x59)."""
import array
import os
import socket
import struct
import sys
import time

sock_path = sys.argv[1]
version = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x200000  # 0.1.0

s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
s.connect(sock_path)
s.send(struct.pack("=bbHIQ", 0x00, 0, 16, 0, version))
print(f"sent client_hello version={version:#x}", flush=True)

names = {0x01: "server_hello", 0x02: "disconnect", 0x03: "notice", 0x04: "start"}
fd_size = array.array("i").itemsize
while True:
    data, anc, _, _ = s.recvmsg(65536, socket.CMSG_SPACE(16 * fd_size))
    for level, kind, payload in anc:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            fds = array.array("i")
            fds.frombytes(payload[: len(payload) - len(payload) % fd_size])
            for fd in fds:
                os.close(fd)
    if not data:
        print("connection closed", flush=True)
        break
    ptype, _, length, obj = struct.unpack("=BBHI", data[:8])
    if ptype == 0x59:
        env, x, y = struct.unpack("=III", data[8:20])
        print(f"{time.strftime('%H:%M:%S')} mascot.tapped mascot={obj & 0xFFFFFF} "
              f"env={env & 0xFFFFFF} x={x} y={y}", flush=True)
    elif ptype in names:
        text = data[8:].decode("utf-8", "replace").replace("\x00", " ").strip()
        print(f"{names[ptype]} {text}", flush=True)
