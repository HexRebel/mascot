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
#include "config.h"
#include "list.h"
#include "mascot.h"
#include "protocol/server.h"
#include <errno.h>
#include <linux/limits.h>
#include <pthread.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define CHAT_MAX_CLIENTS 16
#define CHAT_LINE_MAX 512

struct chat_client {
    int fd;
    size_t len;
    char buf[CHAT_LINE_MAX];
};

static int listen_fd = -1;
static struct chat_client clients[CHAT_MAX_CLIENTS];
static int client_count = 0;
static char listen_path[PATH_MAX] = {0};

// Mascot kept sitting for the open bubble, by id (pointers may be freed)
static int64_t held_mascot_id = -1;

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

static struct mascot* chat_find_mascot(uint32_t id)
{
    struct protocol_server_state* state = protocol_get_server_state();
    struct mascot* mascot = NULL;

    pthread_mutex_lock(&state->environment_mutex);
    for (uint32_t i = 0, c = list_count(state->environments); i < list_size(state->environments) && c; i++) {
        environment_t* environment = list_get(state->environments, i);
        if (!environment) continue;
        c--;
        if ((mascot = environment_mascot_by_id(environment, id))) break;
    }
    pthread_mutex_unlock(&state->environment_mutex);
    return mascot;
}

static void chat_release_held(void)
{
    if (held_mascot_id == -1) return;
    struct mascot* mascot = chat_find_mascot(held_mascot_id);
    if (mascot) mascot_chat_hold(mascot, false);
    held_mascot_id = -1;
}

static void chat_hold(struct mascot* mascot)
{
    if (held_mascot_id != -1 && held_mascot_id != mascot->id) chat_release_held();
    if (mascot_chat_hold(mascot, true)) held_mascot_id = mascot->id;
}

static void chat_remove_client(int index)
{
    close(clients[index].fd);
    clients[index] = clients[--client_count];
    // No bubble left to talk to the held mascot
    if (!client_count) chat_release_held();
}

int chat_accept(void)
{
    int fd = accept4(listen_fd, NULL, NULL, SOCK_NONBLOCK | SOCK_CLOEXEC);
    if (fd < 0) {
        WARN("Cannot accept chat client: %s", strerror(errno));
        return -1;
    }

    if (client_count == CHAT_MAX_CLIENTS) {
        WARN("Too many chat clients, dropping new connection");
        close(fd);
        return -1;
    }
    clients[client_count++] = (struct chat_client){ .fd = fd };
    INFO("Chat client connected (%d total)", client_count);
    return fd;
}

// Handles one line from a client. Only {"event":"close","mascot":N} for now
static void chat_handle_line(const char* line)
{
    if (!strstr(line, "\"event\":\"close\"")) return;

    const char* field = strstr(line, "\"mascot\":");
    if (!field) return;
    char* end = NULL;
    long id = strtol(field + strlen("\"mascot\":"), &end, 10);
    if (end == field + strlen("\"mascot\":")) return;

    if (id == held_mascot_id) chat_release_held();
}

bool chat_client_readable(int fd)
{
    int index = -1;
    for (int i = 0; i < client_count; i++) {
        if (clients[i].fd == fd) index = i;
    }
    if (index == -1) {
        close(fd);
        return false;
    }

    struct chat_client* client = &clients[index];
    ssize_t got = recv(fd, client->buf + client->len, sizeof(client->buf) - client->len - 1, 0);
    if (got < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return true;
    if (got <= 0) {
        chat_remove_client(index);
        INFO("Chat client disconnected (%d left)", client_count);
        return false;
    }
    client->len += got;
    client->buf[client->len] = 0;

    char* line = client->buf;
    char* newline;
    while ((newline = strchr(line, '\n'))) {
        *newline = 0;
        chat_handle_line(line);
        line = newline + 1;
    }
    client->len = strlen(line);
    memmove(client->buf, line, client->len + 1);

    // A line longer than the buffer can never complete; drop it
    if (client->len == sizeof(client->buf) - 1) client->len = 0;
    return true;
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

// Writes one line to every client, returns whether at least one got all of it
static bool chat_broadcast(const char* line, int len)
{
    bool delivered = false;
    for (int i = 0; i < client_count; i++) {
        ssize_t sent = send(clients[i].fd, line, len, MSG_NOSIGNAL | MSG_DONTWAIT);
        if (sent == len) {
            delivered = true;
            continue;
        }
        if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            WARN("Chat client is not reading, event dropped");
            continue;
        }
        // Broken or half-written stream: epoll sees EOF and chat_client_readable() cleans up
        shutdown(clients[i].fd, SHUT_RDWR);
    }
    return delivered;
}

void chat_mascot_dragged(struct mascot* mascot)
{
    if (!mascot) return;
    // Released directly: chat_find_mascot() would take environment_mutex
    // in the middle of a Wayland dispatch
    if (mascot->id == held_mascot_id) {
        mascot_chat_hold(mascot, false);
        held_mascot_id = -1;
    }
    if (!client_count) return;

    char line[64];
    int len = snprintf(line, sizeof(line), "{\"event\":\"dragged\",\"mascot\":%u}\n", mascot->id);
    chat_broadcast(line, len);
}

bool chat_announce_tap(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y)
{
    if (!client_count || !mascot || !env) return false;

    char prototype[256], output[128];
    json_escape(mascot->prototype->display_name ? mascot->prototype->display_name : mascot->prototype->name,
                prototype, sizeof(prototype));
    json_escape(environment_name(env), output, sizeof(output));

    // Quoted JSON string, or null when CHAT_COMMAND is unset
    char command[2048] = "null";
    const char* chat_command = config_get_chat_command();
    if (chat_command) {
        char escaped[2040];
        json_escape(chat_command, escaped, sizeof(escaped));
        snprintf(command, sizeof(command), "\"%s\"", escaped);
    }

    char sprite[128] = "null";
    struct bounding_box box;
    if (environment_subsurface_sprite_geometry(mascot->subsurface, &box)) {
        snprintf(sprite, sizeof(sprite), "{\"x\":%d,\"y\":%d,\"width\":%d,\"height\":%d}",
                 box.x, box.y, box.width, box.height);
    }

    // Everything is environment-local, logical px, top-referenced
    char line[4096];
    int len = snprintf(line, sizeof(line),
        "{\"event\":\"tap\",\"mascot\":%u,\"prototype\":\"%s\",\"output\":\"%s\","
        "\"pointer\":{\"x\":%d,\"y\":%d},"
        "\"anchor\":{\"x\":%d,\"y\":%d},\"looking_right\":%s,"
        "\"sprite\":%s,"
        "\"surface\":{\"width\":%d,\"height\":%d},"
        "\"command\":%s}\n",
        mascot->id, prototype, output,
        pointer_x, pointer_y,
        mascot->X->value.i, environment_workarea_height(env) - mascot->Y->value.i,
        mascot->LookingRight->value.i ? "true" : "false",
        sprite,
        environment_workarea_width(env), environment_workarea_height(env),
        command);
    if (len < 0 || len >= (int)sizeof(line)) {
        WARN("Chat event for mascot %u too long, dropped", mascot->id);
        return false;
    }

    bool delivered = chat_broadcast(line, len);

    // Keep the mascot still while someone is talking to it
    if (delivered) chat_hold(mascot);
    return delivered;
}
