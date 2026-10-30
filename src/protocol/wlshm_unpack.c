#include "wlshm.h"

#include <archive.h>

#include <errno.h>
#include <unistd.h>

bool wlshm_count_member(struct wlshm_budget* budget)
{
    return --budget->members >= 0;
}

int wlshm_copy_member(struct archive* archive, int fd, struct wlshm_budget* budget)
{
    char buffer[16384];
    la_ssize_t got;
    // What libarchive hands out, not the size the tar's header claims (a sparse member reads as its zeros)
    while ((got = archive_read_data(archive, buffer, sizeof(buffer))) > 0) {
        if (got > budget->bytes) return WLSHM_COPY_TOO_BIG;
        budget->bytes -= got;
        for (la_ssize_t at = 0; at < got;) {
            ssize_t written = write(fd, buffer + at, got - at);
            if (written < 0 && errno == EINTR) continue;
            if (written <= 0) return WLSHM_COPY_FAILED;
            at += written;
        }
    }
    return got == 0 ? WLSHM_COPY_OK : WLSHM_COPY_FAILED;
}
