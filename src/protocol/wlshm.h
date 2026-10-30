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

// Whether a member is the pack's own prompt.md (in its root, as src/chat.c reads it), which would become the
// mascot's personality with every tool it has; someone else's pack never brings one
bool wlshm_member_is_prompt(const char* path);

// The most an unpacked pack's manifest.json may hold
#define WLSHM_MANIFEST_MAX (1024 * 1024)

// Whether the manifest.json unpacked in dirfd (a regular file) names the pack as its header does: the header's
// name chooses which prototype is replaced, the manifest's is the one loaded
enum wlshm_manifest {
    WLSHM_MANIFEST_NAMES,  // exactly one name, the header's
    WLSHM_MANIFEST_OTHER,  // a JSON object, but with another name, none or two
    WLSHM_MANIFEST_UNREAD, // missing, not a regular file, over WLSHM_MANIFEST_MAX, not a JSON object, too deep
};
int wlshm_manifest_names(int dirfd, const char* name);

// The most a pack may unpack to: its bytes and its members (files and directories alike). Zeros pack small, so
// a pack of 212 KB unpacked to 210 MB; it is counted as it is unpacked, not as the tar's headers say
// (A test builds with smaller ones)
#ifndef WLSHM_UNPACKED_MAX
#define WLSHM_UNPACKED_MAX (256 * 1024 * 1024)
#endif
#ifndef WLSHM_MEMBERS_MAX
#define WLSHM_MEMBERS_MAX 4096
#endif
struct wlshm_budget {
    int64_t bytes;
    int32_t members;
};
#define WLSHM_BUDGET ((struct wlshm_budget){WLSHM_UNPACKED_MAX, WLSHM_MEMBERS_MAX})

// Counts one more member: false when the pack has more than the budget allows
bool wlshm_count_member(struct wlshm_budget* budget);

// Writes the data of the member archive is at to fd, at most what is left of the budget's bytes; these two are
// in wlshm_unpack.c, the only part that needs libarchive
struct archive;
enum wlshm_copy {
    WLSHM_COPY_OK,
    WLSHM_COPY_TOO_BIG,
    WLSHM_COPY_FAILED,  // not read or not written
};
int wlshm_copy_member(struct archive* archive, int fd, struct wlshm_budget* budget);

#endif
