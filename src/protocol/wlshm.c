#include "wlshm.h"
#include "third_party/json.h/json.h"

#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

bool wlshm_name_safe(const char* name)
{
    return name && name[0] && name[0] != '.' && !strchr(name, '/');
}

bool wlshm_read_header(const uint8_t header[WLSHM_HEADER_SIZE], char name[256], char version[128])
{
    size_t name_size = header[4];
    if (5 + name_size + 1 > WLSHM_HEADER_SIZE)
        return false;
    size_t version_size = header[5 + name_size];
    if (version_size == 0 || version_size >= 128 || 6 + name_size + version_size > WLSHM_HEADER_SIZE)
        return false;
    memcpy(name, header + 5, name_size);
    name[name_size] = 0;
    memcpy(version, header + 6 + name_size, version_size);
    version[version_size] = 0;
    // A NUL inside would make the name shorter than its length byte says
    if (strlen(name) != name_size || strlen(version) != version_size)
        return false;
    return wlshm_name_safe(name);
}

bool wlshm_member_is_prompt(const char* path)
{
    while (path[0] == '.' && path[1] == '/') {
        path += 2;
        while (*path == '/')
            path++;
    }
    return strcmp(path, "prompt.md") == 0;
}

bool wlshm_member_path_safe(const char* path)
{
    if (!path || !path[0] || path[0] == '/')
        return false;
    for (const char* part = path; *part;) {
        size_t length = strcspn(part, "/");
        if (length == 2 && part[0] == '.' && part[1] == '.')
            return false;
        part += length;
        while (*part == '/')
            part++;
    }
    return true;
}

// json.h parses nesting recursively: a manifest of a million "[" ran it out of
// stack. The loader refuses more than 64 levels too
static bool json_shallow(const char* text, size_t size)
{
    int depth = 0;
    bool in_string = false;
    for (size_t i = 0; i < size; i++) {
        char c = text[i];
        if (in_string) {
            if (c == '\\') i++;
            else if (c == '"') in_string = false;
        } else if (c == '"') {
            in_string = true;
        } else if (c == '[' || c == '{') {
            if (++depth > 64) return false;
        } else if (c == ']' || c == '}') {
            depth--;
        }
    }
    return true;
}

int wlshm_manifest_names(int dirfd, const char* name)
{
    int fd = openat(dirfd, "manifest.json", O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0)
        return WLSHM_MANIFEST_UNREAD;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size > WLSHM_MANIFEST_MAX) {
        close(fd);
        return WLSHM_MANIFEST_UNREAD;
    }
    char* text = calloc(1, (size_t)st.st_size + 1);
    size_t got = 0;
    while (text && got < (size_t)st.st_size) {
        ssize_t n = read(fd, text + got, (size_t)st.st_size - got);
        if (n <= 0)
            break;
        got += (size_t)n;
    }
    close(fd);
    if (!text)
        return WLSHM_MANIFEST_UNREAD;
    // Exactly one name, a string: json.h keeps a second one, and the loader
    // refuses it too, so no name but this one can be loaded
    bool same = false;
    int names = 0;
    struct json_value_s* root = json_shallow(text, got) ? json_parse(text, got) : NULL;
    bool object = root && root->type == json_type_object;
    if (object) {
        for (struct json_object_element_s* e = ((struct json_object_s*)root->payload)->start; e; e = e->next) {
            if (strcmp(e->name->string, "name"))
                continue;
            names++;
            same = e->value->type == json_type_string && !strcmp(((struct json_string_s*)e->value->payload)->string, name);
        }
    }
    same = same && names == 1;
    free(root);
    free(text);
    return !object ? WLSHM_MANIFEST_UNREAD : same ? WLSHM_MANIFEST_NAMES : WLSHM_MANIFEST_OTHER;
}
