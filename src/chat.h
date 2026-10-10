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
#include <stddef.h>
#include <stdint.h>

struct mascot;

// Derives chat socket path from the IPC socket path ("x.sock" -> "x-chat.sock")
size_t chat_socket_path(const char* ipc_socket_path, char* pathbuf, size_t pathbuf_len);

// Creates a listening SOCK_STREAM socket at path, returns fd or -1
int chat_listen(const char* path);

// Accepts a pending connection on the listening socket
void chat_accept(void);

// Closes all sockets and unlinks the socket path
void chat_close(void);

// Writes one line of JSON describing a tap to every connected client.
// pointer_x/pointer_y are environment-local, top-referenced
void chat_announce_tap(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y);

#endif
