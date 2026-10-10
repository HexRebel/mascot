/*
    chat.c - line-JSON socket for the chat bubble

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

// Plain SOCK_STREAM socket that Quickshell's Socket (QLocalSocket) can read
// without speaking the binary IPC protocol. Every event is one JSON object
// followed by '\n'. All functions run on the main epoll thread.

#define _GNU_SOURCE
#include "chat.h"
#include "mascot.h"
#include <errno.h>
#include <linux/limits.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define CHAT_MAX_CLIENTS 16

static int listen_fd = -1;
static int clients[CHAT_MAX_CLIENTS];
static int client_count = 0;
static char listen_path[PATH_MAX] = {0};

size_t chat_socket_path(const char* ipc_socket_path, char* pathbuf, size_t pathbuf_len)
{
    size_t len = strlen(ipc_socket_path);
    if (len > 5 && !strcmp(ipc_socket_path + len - 5, ".sock")) {
        return snprintf(pathbuf, pathbuf_len, "%.*s-chat.sock", (int)(len - 5), ipc_socket_path);
    }
    return snprintf(pathbuf, pathbuf_len, "%s-chat", ipc_socket_path);
}

int chat_listen(const char* path)
{
    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    if (strlen(path) >= sizeof(addr.sun_path)) {
        WARN("Chat socket path too long: %s", path);
        return -1;
    }
    strcpy(addr.sun_path, path);

    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (fd < 0) {
        WARN("Failed to create chat socket: %s", strerror(errno));
        return -1;
    }

    // Only called once the IPC socket is ours, so a leftover file is stale
    unlink(path);
    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0 || listen(fd, 4) < 0) {
        WARN("Failed to listen on chat socket %s: %s", path, strerror(errno));
        close(fd);
        return -1;
    }

    strncpy(listen_path, path, sizeof(listen_path) - 1);
    listen_fd = fd;
    INFO("Chat socket listening on %s", path);
    return fd;
}

static void chat_remove_client(int index)
{
    close(clients[index]);
    clients[index] = clients[--client_count];
}

// Drops clients that have hung up, so reconnecting bubbles do not leak fds
static void chat_prune_clients(void)
{
    for (int i = client_count - 1; i >= 0; i--) {
        struct pollfd pfd = { .fd = clients[i], .events = POLLRDHUP };
        if (poll(&pfd, 1, 0) > 0 && (pfd.revents & (POLLRDHUP | POLLHUP | POLLERR | POLLNVAL))) {
            chat_remove_client(i);
        }
    }
}

void chat_accept(void)
{
    int fd = accept4(listen_fd, NULL, NULL, SOCK_NONBLOCK | SOCK_CLOEXEC);
    if (fd < 0) {
        WARN("Cannot accept chat client: %s", strerror(errno));
        return;
    }

    chat_prune_clients();
    if (client_count == CHAT_MAX_CLIENTS) {
        WARN("Too many chat clients, dropping new connection");
        close(fd);
        return;
    }
    clients[client_count++] = fd;
    INFO("Chat client connected (%d total)", client_count);
}

void chat_close(void)
{
    while (client_count) chat_remove_client(client_count - 1);
    if (listen_fd != -1) close(listen_fd);
    listen_fd = -1;
    if (listen_path[0]) unlink(listen_path);
    listen_path[0] = 0;
}

static void json_escape(const char* in, char* out, size_t out_len)
{
    size_t pos = 0;
    for (; in && *in && pos + 7 < out_len; in++) {
        unsigned char c = *in;
        if (c == '"' || c == '\\') {
            out[pos++] = '\\';
            out[pos++] = c;
        } else if (c < 0x20) {
            pos += snprintf(out + pos, out_len - pos, "\\u%04x", c);
        } else {
            out[pos++] = c;
        }
    }
    out[pos] = 0;
}

void chat_announce_tap(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y)
{
    if (!client_count || !mascot || !env) return;

    char prototype[256], output[128];
    json_escape(mascot->prototype->display_name ? mascot->prototype->display_name : mascot->prototype->name,
                prototype, sizeof(prototype));
    json_escape(environment_name(env), output, sizeof(output));

    char sprite[128] = "null";
    struct bounding_box box;
    if (environment_subsurface_sprite_geometry(mascot->subsurface, &box)) {
        snprintf(sprite, sizeof(sprite), "{\"x\":%d,\"y\":%d,\"width\":%d,\"height\":%d}",
                 box.x, box.y, box.width, box.height);
    }

    // Everything is environment-local, logical px, top-referenced
    char line[1024];
    int len = snprintf(line, sizeof(line),
        "{\"event\":\"tap\",\"mascot\":%u,\"prototype\":\"%s\",\"output\":\"%s\","
        "\"pointer\":{\"x\":%d,\"y\":%d},"
        "\"anchor\":{\"x\":%d,\"y\":%d},\"looking_right\":%s,"
        "\"sprite\":%s,"
        "\"surface\":{\"width\":%d,\"height\":%d}}\n",
        mascot->id, prototype, output,
        pointer_x, pointer_y,
        mascot->X->value.i, environment_workarea_height(env) - mascot->Y->value.i,
        mascot->LookingRight->value.i ? "true" : "false",
        sprite,
        environment_workarea_width(env), environment_workarea_height(env));
    if (len < 0 || len >= (int)sizeof(line)) {
        WARN("Chat event for mascot %u too long, dropped", mascot->id);
        return;
    }

    for (int i = client_count - 1; i >= 0; i--) {
        ssize_t sent = send(clients[i], line, len, MSG_NOSIGNAL | MSG_DONTWAIT);
        if (sent == len) continue;
        if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            WARN("Chat client is not reading, event dropped");
            continue;
        }
        chat_remove_client(i);
    }
}
