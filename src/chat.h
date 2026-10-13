/*
    chat.h - line-JSON socket for the chat bubble

    Copyright (C) 2026  Xedoc91

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 2
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <https://www.gnu.org/licenses/>.
*/

#ifndef CHAT_H
#define CHAT_H

#include "master_header.h"
#include "environment.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct mascot;

// Derives chat socket path from the IPC socket path ("x.sock" -> "x-chat.sock")
size_t chat_socket_path(const char* ipc_socket_path, char* pathbuf, size_t pathbuf_len);

// Creates a listening SOCK_STREAM socket at path, returns fd or -1
int chat_listen(const char* path);

// Accepts a pending connection on the listening socket, returns its fd or -1.
// The caller adds it to epoll and calls chat_client_readable() on events
int chat_accept(void);

// Reads from a client; returns false once it is gone (fd already closed)
bool chat_client_readable(int fd);

// Disconnects every client, so a bubble started by mascotd hides and quits by
// itself. The socket keeps listening
void chat_disconnect_all(void);

// Closes all sockets and unlinks the socket path
void chat_close(void);

// Writes one line of JSON describing a tap to every connected client and, if
// any received it, keeps the mascot sitting until the bubble sends
// {"event":"close","mascot":N} or disconnects. Returns whether it was delivered.
// pointer_x/pointer_y are environment-local, top-referenced
bool chat_announce_tap(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y);

// Releases the chat hold on a mascot the user started dragging and tells
// clients with {"event":"dragged","mascot":N}, so its bubble can close
void chat_mascot_dragged(struct mascot* mascot);

#endif
