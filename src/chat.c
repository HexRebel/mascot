/*
    chat.c - line-JSON socket for the chat bubble

    Copyright (C) 2026  HexRebel

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
#include "third_party/json.h/json.h"
#include <errno.h>
#include <fcntl.h>
#include <linux/limits.h>
#include <pthread.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <time.h>
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
// Asleep while "sleep" (e.g. from hypridle) holds, until "wake", or until
// sleep_until ("sleep" with "minutes", which only "wake" with "all" ends early);
// mascots that appear meanwhile fall asleep too
static bool asleep = false;
static bool sleep_held = false;
static time_t sleep_until = 0;
// The newest mascot chat_sleep_all() has seen (ids are not reused)
static int64_t newest_mascot_id = -1;

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

static void chat_send_prototypes(int fd);
static void chat_swap(int fd, const char* line);
static void chat_send_to(int fd, const char* line, size_t len);
static void chat_open(const char* line);
static void chat_open_menu(const char* line);
static bool chat_remark(const char* line);
static bool chat_sleep_all(bool sleep, bool only_new);
static void chat_wake_all(void);
static struct mascot* chat_line_mascot(const char* line);

// Handles one line from a client: {"event":"talking","mascot":N,"active":true|false},
// {"event":"close","mascot":N}, {"event":"list"},
// {"event":"swap","mascot":N,"prototype":"name"}, {"event":"toggle"} and
// {"event":"menu_toggle"} (from `mascot chat`/`mascot menu`, passed on to the
// other clients, i.e. the bubble), {"event":"open","mascot":N} and
// {"event":"menu","mascot":N} (the bubble's answers to them), {"event":"remark"}
// (a random mascot says something now, as CHAT_REMARKS does; with "mascot":N
// that one, if it is still there, e.g. for a reminder), {"event":"sleep"} and
// {"event":"wake"} (from `mascot sleep`/`mascot wake`, e.g. hypridle; with
// "minutes":N they sleep that long, and only "wake" with "all":true ends it
// early, e.g. the sleep_mode tool; with "mascot":N only that one, from the
// menu), {"event":"stay","mascot":N,"active":true|false} (the menu's "Stay"),
// {"event":"answered","mascot":N} (the held mascot's answer waits to be read)
// and {"event":"dismiss","mascot":N} (the menu's "Send away"). Anything
// else is ignored, e.g. the "hiding"/"hidden" events older bubbles still send
static void chat_handle_line(int fd, const char* line)
{
    bool sleep = strstr(line, "\"event\":\"sleep\"") != NULL;
    if ((sleep || strstr(line, "\"event\":\"wake\"")) && strstr(line, "\"mascot\":")) {
        struct mascot* mascot = chat_line_mascot(line);
        if (mascot && mascot_sleep(mascot, sleep, false))
            INFO("<Mascot:%s:%u> %s", mascot->prototype->name, mascot->id, sleep ? "Put to sleep" : "Woken up");
        return;
    }
    if (strstr(line, "\"event\":\"answered\"")) {
        struct mascot* mascot = chat_line_mascot(line);
        if (mascot && (int64_t)mascot->id == held_mascot_id && mascot_chat_answered(mascot))
            INFO("<Mascot:%s:%u> Waits with an answer", mascot->prototype->name, mascot->id);
        return;
    }
    if (strstr(line, "\"event\":\"stay\"")) {
        bool stay = strstr(line, "\"active\":true") != NULL;
        struct mascot* mascot = chat_line_mascot(line);
        if (mascot && mascot_stay(mascot, stay))
            INFO("<Mascot:%s:%u> %s", mascot->prototype->name, mascot->id, stay ? "Stays put" : "Walks again");
        return;
    }
    if (strstr(line, "\"event\":\"dismiss\"")) {
        struct mascot* mascot = chat_line_mascot(line);
        if (!mascot) return;
        if (mascot->id == held_mascot_id) held_mascot_id = -1;
        INFO("<Mascot:%s:%u> Sent away", mascot->prototype->name, mascot->id);
        environment_remove_mascot(mascot->environment, mascot);
        return;
    }
    if (sleep) {
        const char* field = strstr(line, "\"minutes\":");
        double minutes = field ? strtod(field + strlen("\"minutes\":"), NULL) : 0;
        if (minutes > 0) {
            if (minutes > 24 * 60) minutes = 24 * 60;
            sleep_until = time(NULL) + (time_t)(minutes * 60 + 0.5);
            INFO("Mascots fall asleep for %g minutes", minutes);
        } else {
            sleep_held = true;
            INFO("Mascots fall asleep");
        }
        asleep = true;
        chat_sleep_all(true, false);
        return;
    }
    if (strstr(line, "\"event\":\"wake\"")) {
        sleep_held = false;
        if (strstr(line, "\"all\":true")) sleep_until = 0;
        if (sleep_until) {
            INFO("Mascots sleep on until their time is up");
            return;
        }
        if (asleep) chat_wake_all();
        return;
    }
    if (strstr(line, "\"event\":\"remark\"")) {
        chat_remark(line);
        return;
    }
    if (strstr(line, "\"event\":\"toggle\"") || strstr(line, "\"event\":\"menu_toggle\"")) {
        static const char toggle[] = "{\"event\":\"toggle\"}\n";
        static const char menu_toggle[] = "{\"event\":\"menu_toggle\"}\n";
        bool menu = strstr(line, "\"event\":\"menu_toggle\"") != NULL;
        for (int i = 0; i < client_count; i++)
            if (clients[i].fd != fd)
                chat_send_to(clients[i].fd, menu ? menu_toggle : toggle, menu ? sizeof(menu_toggle) - 1 : sizeof(toggle) - 1);
        return;
    }
    if (strstr(line, "\"event\":\"menu\"")) {
        chat_open_menu(line);
        return;
    }
    if (strstr(line, "\"event\":\"open\"")) {
        chat_open(line);
        return;
    }
    if (strstr(line, "\"event\":\"list\"")) {
        chat_send_prototypes(fd);
        return;
    }
    if (strstr(line, "\"event\":\"swap\"")) {
        chat_swap(fd, line);
        return;
    }
    bool talking = strstr(line, "\"event\":\"talking\"");
    bool doing = strstr(line, "\"event\":\"doing\"");
    if (!talking && !doing && !strstr(line, "\"event\":\"close\"")) return;

    const char* field = strstr(line, "\"mascot\":");
    if (!field) return;
    char* end = NULL;
    long id = strtol(field + strlen("\"mascot\":"), &end, 10);
    if (end == field + strlen("\"mascot\":")) return;
    if (id != held_mascot_id) return;

    if (!talking && !doing) {
        chat_release_held();
        return;
    }
    struct mascot* mascot = chat_find_mascot(held_mascot_id);
    if (!mascot) return;
    if (talking) {
        mascot_chat_talk(mascot, strstr(line, "\"active\":true") != NULL);
        return;
    }
    // "tool":"todo" while a tool runs, "tool":"" when it is done
    char tool[32] = "";
    const char* value = strstr(line, "\"tool\":\"");
    if (value) {
        value += strlen("\"tool\":\"");
        size_t len = strcspn(value, "\"");
        if (len < sizeof(tool)) {
            memcpy(tool, value, len);
            tool[len] = 0;
        }
    }
    mascot_chat_doing(mascot, tool);
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
        chat_handle_line(fd, line);
        line = newline + 1;
    }
    client->len = strlen(line);
    memmove(client->buf, line, client->len + 1);

    // A line longer than the buffer can never complete; drop it
    if (client->len == sizeof(client->buf) - 1) client->len = 0;
    return true;
}

void chat_disconnect_all(void)
{
    if (!client_count) return;
    // shutdown(), not close(): the clients go through chat_client_readable() as
    // if they hung up, so mascotd frees their epoll entries as usual
    for (int i = 0; i < client_count; i++) shutdown(clients[i].fd, SHUT_RDWR);
}

void chat_close(void)
{
    while (client_count) chat_remove_client(client_count - 1);
    // The bubble hides and quits once the socket is gone
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

// The mascot being dragged, until the button goes up (chat_mascot_dropped())
static long dragged_mascot_id = -1;

void chat_mascot_dragged(struct mascot* mascot)
{
    if (!mascot) return;
    dragged_mascot_id = mascot->id;
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

void chat_mascot_dropped(void)
{
    if (dragged_mascot_id == -1) return;
    long id = dragged_mascot_id;
    dragged_mascot_id = -1;
    if (!client_count) return;

    char line[64];
    int len = snprintf(line, sizeof(line), "{\"event\":\"dropped\",\"mascot\":%ld}\n", id);
    chat_broadcast(line, len);
}

static const char* chat_prototype_name(const struct mascot_prototype* prototype)
{
    return prototype->display_name ? prototype->display_name : prototype->name;
}

// The prototype's role (CHAT_ROLES, else CHAT_ROLE) as a quoted JSON string, or null
static void chat_role_json(const struct mascot_prototype* prototype, char* dest, size_t size)
{
    char buffer[256], escaped[504];
    const char* role = config_get_chat_role_for(prototype->display_name, prototype->name, buffer, sizeof(buffer));
    if (!role) {
        snprintf(dest, size, "null");
        return;
    }
    json_escape(role, escaped, sizeof(escaped));
    snprintf(dest, size, "\"%s\"", escaped);
}

enum chat_announce_kind { chat_tap, chat_remark_tap, chat_menu };

// The prototype's own system prompt (prompt.md in its directory, e.g. Robo's
// personality) as a quoted JSON string into dest, or null without one
static void chat_prototype_prompt_json(const struct mascot_prototype* prototype, char* dest, size_t size)
{
    snprintf(dest, size, "null");
    if (!prototype || prototype->path_fd < 0) return;
    int fd = openat(prototype->path_fd, "prompt.md", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return;
    char text[4097];
    ssize_t got = read(fd, text, sizeof(text) - 1);
    close(fd);
    if (got <= 0) return;
    text[got] = 0;
    if (got == sizeof(text) - 1)
        WARN("%s's prompt.md is longer than %zu bytes, cut off", prototype->name, sizeof(text) - 1);
    char escaped[12288];
    json_escape(text, escaped, sizeof(escaped));
    snprintf(dest, size, "\"%s\"", escaped);
}

static bool chat_announce(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y,
                          enum chat_announce_kind kind)
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

    // Same for the role: this mascot's from CHAT_ROLES, else CHAT_ROLE
    char role[512];
    chat_role_json(mascot->prototype, role, sizeof(role));

    // And CHAT_TOOLS, the bubble's tools ("time,weather,files,todo,reminders,shell,sleep")
    char tools[300] = "null";
    const char* chat_tools = config_get_chat_tools();
    if (chat_tools) {
        char escaped[290];
        json_escape(chat_tools, escaped, sizeof(escaped));
        snprintf(tools, sizeof(tools), "\"%s\"", escaped);
    }

    // And CHAT_DOTFILES, the hidden files the file tools may see
    char dotfiles[2100] = "null";
    const char* chat_dotfiles = config_get_chat_dotfiles();
    if (chat_dotfiles) {
        char escaped[2090];
        json_escape(chat_dotfiles, escaped, sizeof(escaped));
        snprintf(dotfiles, sizeof(dotfiles), "\"%s\"", escaped);
    }

    // And the prototype's own prompt (prompt.md), if it has one
    char prompt[12300];
    chat_prototype_prompt_json(mascot->prototype, prompt, sizeof(prompt));

    // And CHAT_LANGUAGE, the user's language
    char language[160] = "null";
    const char* chat_language = config_get_chat_language();
    if (chat_language) {
        char escaped[150];
        json_escape(chat_language, escaped, sizeof(escaped));
        snprintf(language, sizeof(language), "\"%s\"", escaped);
    }

    char sprite[128] = "null";
    struct bounding_box box;
    if (environment_subsurface_sprite_geometry(mascot->subsurface, &box)) {
        snprintf(sprite, sizeof(sprite), "{\"x\":%d,\"y\":%d,\"width\":%d,\"height\":%d}",
                 box.x, box.y, box.width, box.height);
    }

    // The menu shows what it can do: wake it or let it sleep, and wake them all
    // after "sleep" (with minutes), and whether it stays put
    char extra[160] = "";
    if (kind == chat_remark_tap)
        snprintf(extra, sizeof(extra), ",\"remark\":true");
    else if (kind == chat_menu)
        snprintf(extra, sizeof(extra), ",\"asleep\":%s,\"all_asleep\":%s,\"staying\":%s",
                 mascot->asleep ? "true" : "false", asleep ? "true" : "false",
                 mascot->stay_behavior ? "true" : "false");

    // Everything is environment-local, logical px, top-referenced
    char line[20480];
    int len = snprintf(line, sizeof(line),
        "{\"event\":\"%s\",\"mascot\":%u,\"prototype\":\"%s\",\"output\":\"%s\","
        "\"pointer\":{\"x\":%d,\"y\":%d},"
        "\"anchor\":{\"x\":%d,\"y\":%d},\"looking_right\":%s,"
        "\"sprite\":%s,"
        "\"surface\":{\"width\":%d,\"height\":%d},"
        "\"command\":%s,\"role\":%s,\"memory\":%d,\"tools\":%s,\"dotfiles\":%s,\"prompt\":%s,\"language\":%s,\"version\":\"" MASCOTD_VERSION "\"%s}\n",
        kind == chat_menu ? "menu" : "tap", mascot->id, prototype, output,
        pointer_x, pointer_y,
        mascot->X->value.i, environment_workarea_height(env) - mascot->Y->value.i,
        mascot->LookingRight->value.i ? "true" : "false",
        sprite,
        environment_workarea_width(env), environment_workarea_height(env),
        command, role, config_get_chat_memory(), tools, dotfiles, prompt, language, extra);
    if (len < 0 || len >= (int)sizeof(line)) {
        WARN("Chat event for mascot %u too long, dropped", mascot->id);
        return false;
    }

    bool delivered = chat_broadcast(line, len);

    // Keep the mascot still while someone is talking to it (or picking from its
    // menu); asleep, it sleeps on under its menu, and sits up only for the bubble
    if (delivered && !(kind == chat_menu && mascot->asleep)) chat_hold(mascot);
    return delivered;
}

bool chat_announce_tap(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y)
{
    return chat_announce(mascot, env, pointer_x, pointer_y, chat_tap);
}

bool chat_announce_menu(struct mascot* mascot, environment_t* env, int32_t pointer_x, int32_t pointer_y)
{
    return chat_announce(mascot, env, pointer_x, pointer_y, chat_menu);
}

static void chat_send_to(int fd, const char* line, size_t len)
{
    ssize_t sent = send(fd, line, len, MSG_NOSIGNAL | MSG_DONTWAIT);
    if (sent == (ssize_t)len) return;
    if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
        WARN("Chat client is not reading, event dropped");
        return;
    }
    shutdown(fd, SHUT_RDWR);
}


// Replies {"event":"prototypes","names":[...]} with every loaded prototype
static void chat_send_prototypes(int fd)
{
    char* line = NULL;
    size_t len = 0;
    FILE* out = open_memstream(&line, &len);
    if (!out) return;

    fputs("{\"event\":\"prototypes\",\"names\":[", out);
    struct protocol_server_state* state = protocol_get_server_state();
    bool first = true;
    pthread_mutex_lock(&state->prototypes_mutex);
    for (int32_t i = 0; i < mascot_prototype_store_count(state->prototypes); i++) {
        struct mascot_prototype* prototype = mascot_prototype_store_get_index(state->prototypes, i);
        if (!prototype) continue;
        char name[1600];
        json_escape(chat_prototype_name(prototype), name, sizeof(name));
        fprintf(out, "%s\"%s\"", first ? "" : ",", name);
        first = false;
    }
    pthread_mutex_unlock(&state->prototypes_mutex);
    fputs("]}\n", out);
    fclose(out);

    chat_send_to(fd, line, len);
    free(line);
}

static void chat_swap_failed(int fd, long mascot_id, const char* reason)
{
    char escaped[1600], line[2048];
    json_escape(reason, escaped, sizeof(escaped));
    int len = snprintf(line, sizeof(line), "{\"event\":\"swap_failed\",\"mascot\":%ld,\"reason\":\"%s\"}\n",
                       mascot_id, escaped);
    if (len > 0 && len < (int)sizeof(line)) chat_send_to(fd, line, len);
}

static void chat_swap_summoned(struct mascot* mascot, void* data)
{
    *(struct mascot**)data = mascot;
}

// Replaces mascot N with a new one of the named prototype (display or internal
// name, any case) at the same spot, facing the same way. The new one takes over
// the chat hold and every client gets {"event":"swapped","mascot":N,"to":M,
// "prototype":"name","role":...} (role as in the tap event); the sender gets {"event":"swap_failed",...} otherwise
static void chat_swap(int fd, const char* line)
{
    struct json_value_s* root = json_parse(line, strlen(line));
    struct json_object_s* object = root ? json_value_as_object(root) : NULL;
    struct json_number_s* id_value = NULL;
    struct json_string_s* name_value = NULL;
    for (struct json_object_element_s* e = object ? object->start : NULL; e; e = e->next) {
        if (!strcmp(e->name->string, "mascot")) id_value = json_value_as_number(e->value);
        if (!strcmp(e->name->string, "prototype")) name_value = json_value_as_string(e->value);
    }
    if (!id_value || !name_value) {
        WARN("Malformed swap request from chat client");
        free(root);
        return;
    }
    long mascot_id = strtol(id_value->number, NULL, 10);

    struct mascot* old = chat_find_mascot(mascot_id);
    if (!old) {
        chat_swap_failed(fd, mascot_id, "That mascot is gone");
        free(root);
        return;
    }

    struct protocol_server_state* state = protocol_get_server_state();
    struct mascot_prototype* prototype = NULL;
    pthread_mutex_lock(&state->prototypes_mutex);
    for (int32_t i = 0; i < mascot_prototype_store_count(state->prototypes) && !prototype; i++) {
        struct mascot_prototype* candidate = mascot_prototype_store_get_index(state->prototypes, i);
        if (!candidate) continue;
        if (!strcasecmp(chat_prototype_name(candidate), name_value->string) ||
            !strcasecmp(candidate->name, name_value->string)) {
            prototype = candidate;
        }
    }
    pthread_mutex_unlock(&state->prototypes_mutex);

    if (!prototype) {
        char reason[512];
        snprintf(reason, sizeof(reason), "No mascot called \"%s\" - try .mascots", name_value->string);
        chat_swap_failed(fd, mascot_id, reason);
        free(root);
        return;
    }
    free(root);

    environment_t* environment = old->environment;
    struct mascot* replacement = NULL;
    environment_summon_mascot(environment, prototype, old->X->value.i, old->Y->value.i,
                              chat_swap_summoned, &replacement);
    if (!replacement) {
        chat_swap_failed(fd, mascot_id, "Could not create the new mascot");
        return;
    }
    pthread_mutex_lock(&replacement->tick_lock);
    replacement->LookingRight->value.i = old->LookingRight->value.i;
    pthread_mutex_unlock(&replacement->tick_lock);
    if (old->stay_behavior) mascot_stay(replacement, true);
    // Asleep one by one (a middle click, the menu's Sleep) too; when all sleep,
    // chat_tick() puts new ones to sleep anyway
    if (old->asleep) mascot_sleep(replacement, true, sleep_until != 0);

    // Hold the new one first: chat_hold() releases the old one
    if (held_mascot_id == old->id) chat_hold(replacement);
    INFO("<Mascot:%s:%u> Swapped for %s from the chat bubble", old->prototype->name, old->id, prototype->name);
    environment_remove_mascot(environment, old);

    char name[1600], role[512], reply[2560];
    json_escape(chat_prototype_name(prototype), name, sizeof(name));
    chat_role_json(prototype, role, sizeof(role));
    int len = snprintf(reply, sizeof(reply),
                       "{\"event\":\"swapped\",\"mascot\":%ld,\"to\":%u,\"prototype\":\"%s\",\"role\":%s}\n",
                       mascot_id, replacement->id, name, role);
    if (len > 0 && len < (int)sizeof(reply)) chat_broadcast(reply, len);
}

// The first mascot on any screen
static struct mascot* chat_first_mascot(void)
{
    struct protocol_server_state* state = protocol_get_server_state();
    struct mascot* mascot = NULL;

    pthread_mutex_lock(&state->environment_mutex);
    for (uint32_t i = 0, c = list_count(state->environments); i < list_size(state->environments) && c && !mascot; i++) {
        environment_t* environment = list_get(state->environments, i);
        if (!environment) continue;
        c--;
        pthread_mutex_t* mutex = NULL;
        struct list* mascots = environment_mascot_list(environment, &mutex);
        if (!mascots) continue;
        pthread_mutex_lock(mutex);
        for (size_t j = 0; j < list_size(mascots) && !mascot; j++) mascot = list_get(mascots, j);
        pthread_mutex_unlock(mutex);
    }
    pthread_mutex_unlock(&state->environment_mutex);
    return mascot;
}

// Opens the bubble at mascot N, or at the first mascot if N is gone or not
// given, as if it had been tapped (pointer at its anchor)
static void chat_open(const char* line)
{
    struct mascot* mascot = NULL;
    const char* field = strstr(line, "\"mascot\":");
    if (field) {
        char* end = NULL;
        long id = strtol(field + strlen("\"mascot\":"), &end, 10);
        if (end != field + strlen("\"mascot\":") && id >= 0) mascot = chat_find_mascot(id);
    }
    if (!mascot) mascot = chat_first_mascot();
    if (!mascot) {
        INFO("Chat bubble asked to open, but there are no mascots");
        return;
    }

    environment_t* env = mascot->environment;
    chat_announce_tap(mascot, env, mascot->X->value.i, environment_workarea_height(env) - mascot->Y->value.i);
}

// The mascot a line names with "mascot":N, if it is still there
static struct mascot* chat_line_mascot(const char* line)
{
    const char* field = strstr(line, "\"mascot\":");
    if (!field) return NULL;
    char* end = NULL;
    long id = strtol(field + strlen("\"mascot\":"), &end, 10);
    if (end == field + strlen("\"mascot\":") || id < 0) return NULL;
    return chat_find_mascot(id);
}

// Opens the menu at mascot N, or at the first mascot if N is gone or not given,
// as if it had been right-clicked (pointer at the top of its sprite)
static void chat_open_menu(const char* line)
{
    struct mascot* mascot = chat_line_mascot(line);
    if (!mascot) mascot = chat_first_mascot();
    if (!mascot) {
        INFO("Menu asked for, but there are no mascots");
        return;
    }
    environment_t* env = mascot->environment;
    int32_t x = mascot->X->value.i, y = environment_workarea_height(env) - mascot->Y->value.i;
    struct bounding_box box;
    if (environment_subsurface_sprite_geometry(mascot->subsurface, &box)) {
        x = box.x + box.width / 2;
        y = box.y;
    }
    chat_announce_menu(mascot, env, x, y);
}

// A random mascot on any screen that is awake
static struct mascot* chat_random_mascot(void)
{
    struct protocol_server_state* state = protocol_get_server_state();
    struct mascot* picked = NULL;
    uint32_t seen = 0;

    pthread_mutex_lock(&state->environment_mutex);
    for (uint32_t i = 0, c = list_count(state->environments); i < list_size(state->environments) && c; i++) {
        environment_t* environment = list_get(state->environments, i);
        if (!environment) continue;
        c--;
        pthread_mutex_t* mutex = NULL;
        struct list* mascots = environment_mascot_list(environment, &mutex);
        if (!mascots) continue;
        pthread_mutex_lock(mutex);
        for (size_t j = 0; j < list_size(mascots); j++) {
            struct mascot* mascot = list_get(mascots, j);
            // Reservoir sampling: each of the n mascots is kept with chance 1/n
            if (mascot && !mascot->asleep && lrand48() % ++seen == 0) picked = mascot;
        }
        pthread_mutex_unlock(mutex);
    }
    pthread_mutex_unlock(&state->environment_mutex);
    return picked;
}

// Lets a mascot say something, the one line names ("mascot":N) or else a random
// one: the bubble opens without taking the keyboard (see "remark" in
// docs/protocol.md). Not while the bubble is open, nor at a mascot off the floor
// or asleep
static bool chat_remark(const char* line)
{
    if (!client_count || held_mascot_id != -1) return false;
    struct mascot* mascot = NULL;
    const char* field = line ? strstr(line, "\"mascot\":") : NULL;
    if (field) {
        char* end = NULL;
        long id = strtol(field + strlen("\"mascot\":"), &end, 10);
        if (end != field + strlen("\"mascot\":") && id >= 0) mascot = chat_find_mascot(id);
    }
    // Asleep means do not disturb: another one says it, or the bubble asks again
    // for a reminder until one wakes up
    if (mascot && mascot->asleep) mascot = NULL;
    if (!mascot) mascot = chat_random_mascot();
    if (!mascot) return false;
    // The bubble stays where it opens: not at a mascot that is falling (e.g.
    // just summoned) or being dragged; the bubble asks again in a moment
    if (mascot->dragged || mascot_get_border_type(mascot) != environment_border_type_floor) return false;
    environment_t* env = mascot->environment;
    INFO("<Mascot:%s:%u> Saying something on its own", mascot->prototype->name, mascot->id);
    return chat_announce(mascot, env, mascot->X->value.i, environment_workarea_height(env) - mascot->Y->value.i,
                         chat_remark_tap);
}

// Puts every mascot (only_new: those that appeared since the last call) to sleep
// or wakes it up. Not the others again, so one woken with a middle click stays
// awake. Returns whether any mascot is asleep now
static bool chat_sleep_all(bool sleep, bool only_new)
{
    struct protocol_server_state* state = protocol_get_server_state();
    uint32_t ids[256];
    size_t count = 0;
    bool any_asleep = false;
    int64_t newest = newest_mascot_id;

    // Only the ids: mascot_sleep() takes the mascot's tick lock, not under these
    pthread_mutex_lock(&state->environment_mutex);
    for (uint32_t i = 0, c = list_count(state->environments); i < list_size(state->environments) && c; i++) {
        environment_t* environment = list_get(state->environments, i);
        if (!environment) continue;
        c--;
        pthread_mutex_t* mutex = NULL;
        struct list* mascots = environment_mascot_list(environment, &mutex);
        if (!mascots) continue;
        pthread_mutex_lock(mutex);
        for (size_t j = 0; j < list_size(mascots) && count < sizeof(ids) / sizeof(*ids); j++) {
            struct mascot* mascot = list_get(mascots, j);
            if (!mascot) continue;
            if (mascot->id > newest_mascot_id) newest_mascot_id = mascot->id;
            if ((!only_new || mascot->id > newest) && mascot->asleep != sleep) {
                ids[count++] = mascot->id;
                any_asleep |= sleep;
            } else {
                any_asleep |= mascot->asleep;
            }
        }
        pthread_mutex_unlock(mutex);
    }
    pthread_mutex_unlock(&state->environment_mutex);

    for (size_t i = 0; i < count; i++) {
        struct mascot* mascot = chat_find_mascot(ids[i]);
        // Asleep for a while (Quiet, the sleep tool): its quiet pose, if it has one
        if (mascot) mascot_sleep(mascot, sleep, sleep && sleep_until);
    }
    return any_asleep;
}

static void chat_wake_all(void)
{
    asleep = false;
    INFO("Mascots wake up");
    chat_sleep_all(false, false);
}

void chat_tick(void)
{
    if (sleep_until && time(NULL) >= sleep_until) {
        sleep_until = 0;
        if (!sleep_held) chat_wake_all();
    }
    // New (summoned, swapped) mascots fall asleep too. Once every mascot has
    // been woken one by one (the menu's "Wake up", a middle click), the quiet
    // is over, so it is not shown as still on, and new ones stay awake
    if (asleep && !chat_sleep_all(true, true)) {
        asleep = false;
        sleep_held = false;
        sleep_until = 0;
        INFO("Every mascot is awake, the quiet is over");
    }

    static time_t next_remark = 0;
    int32_t minutes = config_get_chat_remarks();
    time_t now = time(NULL);
    if (minutes <= 0) {
        next_remark = 0;
        return;
    }
    if (!next_remark) {
        // Every N to 2N minutes, so it does not feel like clockwork
        next_remark = now + minutes * 60 + lrand48() % (minutes * 60 + 1);
        return;
    }
    if (now < next_remark) return;
    // Busy (bubble open), the mascot off the floor or nobody to show it: try again
    // in a couple of minutes
    next_remark = chat_remark(NULL) ? 0 : now + 120;
}
