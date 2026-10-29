#include "wlshm.h"

#include <string.h>

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
