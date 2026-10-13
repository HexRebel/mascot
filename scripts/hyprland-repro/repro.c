// repro.c - Hyprland segfault in CInputManager::refocusLastWindow()
//
// Two overlay layer surfaces:
//   A ("repro-host")    at (300, 300), 200x200, no keyboard interactivity, with a
//                       red wl_subsurface covering it (default, i.e. full, input region)
//   B ("repro-focused") at (0, 0), 240x80, exclusive keyboard interactivity
// After DELAY seconds (default 5), B is destroyed. If the cursor is over the red
// subsurface at that moment, Hyprland crashes in CWLSurface::keyboardFocusable(),
// because a subsurface of a layer surface has no m_hlSurface.
//
// Build: see README.md. Run: ./repro [DELAY]

#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "wlr-layer-shell-unstable-v1-client-protocol.h"

static struct wl_compositor *compositor;
static struct wl_subcompositor *subcompositor;
static struct wl_shm *shm;
static struct zwlr_layer_shell_v1 *layer_shell;

static void registry_global(void *data, struct wl_registry *registry, uint32_t name,
                            const char *interface, uint32_t version) {
    (void)data;
    if (!strcmp(interface, wl_compositor_interface.name))
        compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 4);
    else if (!strcmp(interface, wl_subcompositor_interface.name))
        subcompositor = wl_registry_bind(registry, name, &wl_subcompositor_interface, 1);
    else if (!strcmp(interface, wl_shm_interface.name))
        shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
    else if (!strcmp(interface, zwlr_layer_shell_v1_interface.name))
        layer_shell = wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface,
                                       version < 4 ? version : 4);
}

static void registry_global_remove(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data; (void)registry; (void)name;
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove,
};

// Solid-colour ARGB8888 buffer
static struct wl_buffer *solid_buffer(int width, int height, uint32_t argb) {
    int stride = width * 4, size = stride * height;
    int fd = memfd_create("repro-buffer", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, size) < 0) {
        perror("memfd");
        exit(1);
    }
    uint32_t *pixels = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    for (int i = 0; i < width * height; i++)
        pixels[i] = argb;
    munmap(pixels, size);
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, size);
    struct wl_buffer *buffer = wl_shm_pool_create_buffer(pool, 0, width, height, stride, WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool);
    close(fd);
    return buffer;
}

struct layer {
    struct wl_surface *surface;
    struct zwlr_layer_surface_v1 *layer_surface;
    int width, height;
    uint32_t colour;
    int configured;
};

static void layer_configure(void *data, struct zwlr_layer_surface_v1 *layer_surface,
                            uint32_t serial, uint32_t width, uint32_t height) {
    (void)width; (void)height;
    struct layer *layer = data;
    zwlr_layer_surface_v1_ack_configure(layer_surface, serial);
    if (!layer->configured) {
        wl_surface_attach(layer->surface, solid_buffer(layer->width, layer->height, layer->colour), 0, 0);
        wl_surface_damage(layer->surface, 0, 0, layer->width, layer->height);
    }
    wl_surface_commit(layer->surface);
    layer->configured = 1;
}

static void layer_closed(void *data, struct zwlr_layer_surface_v1 *layer_surface) {
    (void)data; (void)layer_surface;
}

static const struct zwlr_layer_surface_v1_listener layer_listener = {
    .configure = layer_configure,
    .closed = layer_closed,
};

static void layer_create(struct layer *layer, const char *namespace, int x, int y,
                         uint32_t keyboard_interactivity) {
    layer->surface = wl_compositor_create_surface(compositor);
    layer->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        layer_shell, layer->surface, NULL, ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY, namespace);
    zwlr_layer_surface_v1_set_anchor(layer->layer_surface,
        ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT);
    zwlr_layer_surface_v1_set_margin(layer->layer_surface, y, 0, 0, x);
    zwlr_layer_surface_v1_set_size(layer->layer_surface, layer->width, layer->height);
    zwlr_layer_surface_v1_set_exclusive_zone(layer->layer_surface, -1);
    zwlr_layer_surface_v1_set_keyboard_interactivity(layer->layer_surface, keyboard_interactivity);
    zwlr_layer_surface_v1_add_listener(layer->layer_surface, &layer_listener, layer);
    wl_surface_commit(layer->surface);
}

// Dispatches events for the given number of milliseconds
static int run_for(struct wl_display *display, int ms) {
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (;;) {
        clock_gettime(CLOCK_MONOTONIC, &now);
        int left = ms - (int)((now.tv_sec - start.tv_sec) * 1000 + (now.tv_nsec - start.tv_nsec) / 1000000);
        if (left <= 0)
            return 0;
        while (wl_display_prepare_read(display) != 0)
            wl_display_dispatch_pending(display);
        if (wl_display_flush(display) < 0 && errno != EAGAIN) {
            wl_display_cancel_read(display);
            return -1;
        }
        struct pollfd pfd = { .fd = wl_display_get_fd(display), .events = POLLIN };
        if (poll(&pfd, 1, left) > 0) {
            if (wl_display_read_events(display) < 0)
                return -1;
        } else {
            wl_display_cancel_read(display);
        }
        if (wl_display_dispatch_pending(display) < 0)
            return -1;
    }
}

int main(int argc, char **argv) {
    int delay = argc > 1 ? atoi(argv[1]) : 5;

    struct wl_display *display = wl_display_connect(NULL);
    if (!display) {
        fprintf(stderr, "Cannot connect to the Wayland display\n");
        return 1;
    }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);
    if (!compositor || !subcompositor || !shm || !layer_shell) {
        fprintf(stderr, "Missing wl_compositor, wl_subcompositor, wl_shm or zwlr_layer_shell_v1\n");
        return 1;
    }

    // A: layer surface with a subsurface on top of it
    struct layer host = { .width = 200, .height = 200, .colour = 0xff303030 };
    layer_create(&host, "repro-host", 300, 300, ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);
    wl_display_roundtrip(display);

    struct wl_surface *child = wl_compositor_create_surface(compositor);
    struct wl_subsurface *subsurface = wl_subcompositor_get_subsurface(subcompositor, child, host.surface);
    wl_subsurface_set_position(subsurface, 0, 0);
    wl_subsurface_set_desync(subsurface);
    wl_surface_attach(child, solid_buffer(200, 200, 0xffd02020), 0, 0);
    wl_surface_damage(child, 0, 0, 200, 200);
    wl_surface_commit(child);
    wl_surface_commit(host.surface);

    // B: layer surface with exclusive keyboard focus
    struct layer focused = { .width = 240, .height = 80, .colour = 0xff4060a0 };
    layer_create(&focused, "repro-focused", 0, 0, ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_EXCLUSIVE);
    wl_display_roundtrip(display);

    printf("A (grey, red subsurface) at 300,300 200x200; B (blue, exclusive keyboard) at 0,0.\n"
           "Put the cursor on the red square, e.g.: hyprctl dispatch movecursor 400 400\n"
           "Destroying B in %d s...\n", delay);
    fflush(stdout);
    if (run_for(display, delay * 1000) < 0)
        return 1;

    zwlr_layer_surface_v1_destroy(focused.layer_surface);
    wl_surface_destroy(focused.surface);
    wl_display_flush(display);
    printf("B destroyed.\n");
    fflush(stdout);

    if (run_for(display, 3000) < 0) {
        printf("Lost the connection to the compositor (did it crash?)\n");
        return 1;
    }
    printf("Compositor still alive.\n");
    wl_display_disconnect(display);
    return 0;
}
