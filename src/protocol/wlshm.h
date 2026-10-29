#ifndef WLSHM_H
#define WLSHM_H

// What mascotd reads from a .wlshm pack (someone else's file) before it unpacks anything:
// the 512-byte header and the path of each member of the tar after it

#include <stdbool.h>
#include <stdint.h>

#define WLSHM_HEADER_SIZE 512

// The pack's name and version from its header ("WLPK", then each as a length byte and the text), always
// NUL-terminated; false if they do not fit in the header or their buffers, or the name is not one safe
// directory name (see wlshm_name_safe)
bool wlshm_read_header(const uint8_t header[WLSHM_HEADER_SIZE], char name[256], char version[128]);

// Whether name can be the pack's directory in the store: not empty, no '/', not hidden (".", "..", and the
// store's own ".unpackingMascot…" directories start with a dot)
bool wlshm_name_safe(const char* name);

// Whether a member's path stays inside the directory it is unpacked into: relative, not empty, no ".."
bool wlshm_member_path_safe(const char* path);

#endif
