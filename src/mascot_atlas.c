/*
    mascot_atlas.c - mascot's mascot texture atlas system

    Copyright (C) 2024  CluelessCatBurger <github.com/CluelessCatBurger>
    Modified for Mascot by HexRebel, 2026; see the git history for details.

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


#define _GNU_SOURCE

#include <sys/mman.h>
#include <sys/stat.h>

#include "mascot_atlas.h"
#include <errno.h>
#include <linux/limits.h>
#include <io.h>

#define QOI_IMPLEMENTATION
#include "third_party/qoi/qoi.h"

// A QOI file's header, before it is read whole: no bigger than
// MASCOT_ATLAS_MAX_SIDE a side, and no longer than such a picture can be
static bool qoi_fits(const char* path)
{
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return false;
    struct stat st;
    uint8_t header[QOI_HEADER_SIZE];
    bool read_whole = fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && read(fd, header, sizeof(header)) == (ssize_t)sizeof(header);
    close(fd);
    if (!read_whole || memcmp(header, "qoif", 4)) return false;
    uint64_t width = (uint64_t)header[4] << 24 | header[5] << 16 | header[6] << 8 | header[7];
    uint64_t height = (uint64_t)header[8] << 24 | header[9] << 16 | header[10] << 8 | header[11];
    if (!width || !height || width > MASCOT_ATLAS_MAX_SIDE || height > MASCOT_ATLAS_MAX_SIDE) return false;
    // At most 5 bytes a pixel (QOI_OP_RGBA), then the end marker
    return (uint64_t)st.st_size <= QOI_HEADER_SIZE + width * height * 5 + sizeof(qoi_padding);
}

void _find_ireg(const uint8_t* buffer, uint32_t width, uint32_t height, uint32_t* out_x, uint32_t* out_y, uint32_t* out_width, uint32_t* out_height) {
    uint32_t minX = UINT32_MAX;
    uint32_t minY = UINT32_MAX;
    uint32_t maxX = 0;
    uint32_t maxY = 0;

    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
            // Calculate the index for the alpha component of the current pixel
            uint32_t alphaIndex = (y * width + x) * 4 + 3; // 4 components per pixel, alpha is the 4th
            uint8_t alpha = buffer[alphaIndex];

            if (alpha > 0) { // Pixel is not fully transparent
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }
    }

    // Calculate the output values
    if (minX <= maxX && minY <= maxY) { // Ensure we found at least one non-transparent pixel
        *out_x = minX;
        *out_y = minY;
        *out_width = maxX - minX + 1;
        *out_height = maxY - minY + 1;
    } else { // No non-transparent pixels found, return an empty region
        *out_x = 0;
        *out_y = 0;
        *out_width = 0;
        *out_height = 0;
    }
}

bool _write_buffers(environment_buffer_factory_t* factory, uint64_t* buffer_factory_pos, const uint8_t* buffer, size_t buffer_len, uint32_t width, uint32_t height) {

    if (buffer_len > QOI_PIXELS_MAX) return false;

    uint8_t* buffers = calloc(2, buffer_len);

    if (!buffers) {
        WARN("Failed to write buffers to memfd: Allocation failed for buffer with size %d", buffer_len*2);
        return false;
    }

    // Convert RGBA to ARGB and fill the direct and mirrored buffers
    for (uint32_t y = 0; y < height; y++) {
        for (uint32_t x = 0; x < width; x++) {
            size_t rgbaIndex = (y * width + x) * 4;
            size_t argbIndex = rgbaIndex; // Direct mapping for ARGB buffer
            size_t mirrorIndex = (y * width + (width - 1 - x)) * 4; // Mirrored mapping
            
            // Premultiply aplha
            *(buffers+argbIndex+0) = (buffer[rgbaIndex + 2] * buffer[rgbaIndex+3] + 127) / 255; // Premultiplied B
            *(buffers+argbIndex+1) = (buffer[rgbaIndex + 1] * buffer[rgbaIndex+3] + 127) / 255; // Premultiplied G
            *(buffers+argbIndex+2) = (buffer[rgbaIndex + 0] * buffer[rgbaIndex+3] + 127) / 255; // Premultiplied R
            *(buffers+argbIndex+3) =  buffer[rgbaIndex + 3]; // Just alpha

            *(buffers+buffer_len+mirrorIndex+0) = (buffer[rgbaIndex + 2] * buffer[rgbaIndex+3] + 127) / 255; // Premultiplied B
            *(buffers+buffer_len+mirrorIndex+1) = (buffer[rgbaIndex + 1] * buffer[rgbaIndex+3] + 127) / 255; // Premultiplied G
            *(buffers+buffer_len+mirrorIndex+2) = (buffer[rgbaIndex + 0] * buffer[rgbaIndex+3] + 127) / 255; // Premultiplied R
            *(buffers+buffer_len+mirrorIndex+3) =  buffer[rgbaIndex + 3]; // Just alpha


            // *(buffers+argbIndex) = buffer[rgbaIndex + 3] ? buffer[rgbaIndex + 2] : 0; // B
            // *(buffers+argbIndex+1) = buffer[rgbaIndex + 3] ? buffer[rgbaIndex + 1] : 0; // G
            // *(buffers+argbIndex+2) = buffer[rgbaIndex + 3] ? buffer[rgbaIndex + 0] : 0; // R
            // *(buffers+argbIndex+3) = buffer[rgbaIndex + 3]; // A

            // Fill mirrored ARGB buffer
            // *(buffers+buffer_len+mirrorIndex) = buffer[rgbaIndex + 3] ? buffer[rgbaIndex + 2] : 0; // B
            // *(buffers+buffer_len+mirrorIndex+1) = buffer[rgbaIndex + 3] ? buffer[rgbaIndex + 1] : 0; // G
            // *(buffers+buffer_len+mirrorIndex+2) = buffer[rgbaIndex + 3] ? buffer[rgbaIndex + 0] : 0; // R
            // *(buffers+buffer_len+mirrorIndex+3) = buffer[rgbaIndex + 3]; // A
        }
    }

    // Write the buffers to the factory
    // Not written (the pool could not grow): the sprites would point past its end
    bool written = environment_buffer_factory_write(factory, buffers, buffer_len * 2);
    *buffer_factory_pos += buffer_len * 2;
    free(buffers);
    if (!written) WARN("Failed to write buffers to memfd");
    return written;
}

// Whether a file the walk found is a sprite: its name ends in .qoi (in any case)
static bool is_sprite(const char* name)
{
    size_t length = strlen(name);
    return length >= 5 && !strcasecmp(name + length - 4, ".qoi");
}

struct mascot_atlas* mascot_atlas_new(const char* dirname)
{

    if (!strlen(dirname)) return NULL;

    qoi_desc* qois = NULL;
    uint32_t sprite_count = 0;
    struct mascot_atlas* atlas = NULL;
    char** file_paths = NULL;
    uint32_t file_count = 0;

    DEBUG("Creating mascot atlas from dir \"%s\"", dirname);

    if (io_find(dirname, "*.qoi", IO_RECURSIVE | IO_CASE_INSENSITIVE | IO_FILE_TYPE_REGULAR, &file_paths, (int32_t*)&file_count)) {
        WARN("Could not create atlas from dir \"%s\": Recursive walk failed", dirname);
        return NULL;
    }
    if (!file_count) {
        WARN("Could not create atlas from dir \"%s\": No files found", dirname);
        free(file_paths);
        return NULL;
    }

    // The same test in both loops (the whole name, however long), so the sprites counted here are the ones
    // loaded below, each into its own slot
    for (uint32_t i = 0; i < file_count; i++) {
        if (is_sprite(file_paths[i])) {
            sprite_count ++;
        }
    }

    if (!sprite_count) {
        free(file_paths);
        WARN("Could not create atlas from dir \"%s\": No sprites found", dirname);
        return NULL;
    }
    // A pack from the net can hold any number: the count and the indexes are 16 bits wide
    if (sprite_count > MASCOT_ATLAS_MAX_SPRITES) {
        for (uint32_t i = 0; i < file_count; i++) free(file_paths[i]);
        free(file_paths);
        WARN("Could not create atlas from dir \"%s\": %u sprites, at most %u", dirname, sprite_count, MASCOT_ATLAS_MAX_SPRITES);
        return NULL;
    }

    qois = calloc(sprite_count, sizeof(qoi_desc));
    char ** namelist = calloc(sprite_count, sizeof(char*));
    void ** pixels = calloc(sprite_count, sizeof(void*));

    if (!qois) {
        ERROR("Could not create atlas from dir \"%s\": Allocation failed for png_ctxs", dirname);
    }
    if (!namelist) {
        ERROR("Could not create atlas from dir \"%s\":Allocation failed for namelists", dirname);
    }
    if (!pixels) {
        ERROR("Could not create atlas from dir \"%s\": Allocation failed for filelists", dirname);
    }

    uint32_t local_ecount = 0;
    uint64_t atlas_bytes = 0;
    for (uint32_t i = 0; i < file_count; i++) {
        if (is_sprite(file_paths[i])) {
            if (local_ecount >= sprite_count) break;
            else local_ecount ++;
            char fullpath[PATH_MAX] = {0};
            size_t printed = snprintf(fullpath, sizeof(fullpath), "%s/%s", dirname, file_paths[i]);
            UNUSED(printed);
            if (!qoi_fits(fullpath)) {
                WARN("Could not create atlas from dir \"%s\": \"%s\" is not a QOI picture of at most %d pixels a side", dirname, file_paths[i], MASCOT_ATLAS_MAX_SIDE);
                goto fail_free_qoi_ctxs;
            }
            pixels[local_ecount-1] = qoi_read(fullpath, &qois[local_ecount-1], 4);
            if (!pixels[local_ecount-1])
            {
                WARN("Could not create atlas from dir \"%s\": Failed to read QOI file \"%s\"", dirname, file_paths[i]);
                goto fail_free_qoi_ctxs;
            }
            // Read again after qoi_fits: the file may have changed in between
            if (qois[local_ecount-1].width > MASCOT_ATLAS_MAX_SIDE || qois[local_ecount-1].height > MASCOT_ATLAS_MAX_SIDE) {
                WARN("Could not create atlas from dir \"%s\": \"%s\" is bigger than %d pixels a side", dirname, file_paths[i], MASCOT_ATLAS_MAX_SIDE);
                goto fail_free_qoi_ctxs;
            }
            // Twice: each picture is kept mirrored too
            atlas_bytes += (uint64_t)qois[local_ecount-1].width * qois[local_ecount-1].height * 4 * 2;
            if (atlas_bytes > MASCOT_ATLAS_MAX_BYTES) {
                WARN("Could not create atlas from dir \"%s\": its pictures take more than %u MiB", dirname, MASCOT_ATLAS_MAX_BYTES / 1024 / 1024);
                goto fail_free_qoi_ctxs;
            }
            namelist[local_ecount-1] = strdup(file_paths[i]);
            if (!namelist[local_ecount-1]) {
                ERROR("Could not create atlas from dir \"%s\": Allocation failed for namelist", dirname);
            }
        }
    }

    environment_buffer_factory_t* buffer_factory = environment_buffer_factory_new();
    uint64_t buffer_factory_pos = 0;

    atlas = calloc(1, sizeof(struct mascot_atlas));
    if (!atlas) ERROR("Could not create atlas from dir \"%s\": Allocation failed for atlas struct", dirname);

    atlas->sprites = calloc(2*sprite_count, sizeof(struct mascot_sprite));
    if (!atlas->sprites) ERROR("Could not create atlas from dir \"%s\": Allocation failed for atlas sprites array", dirname);

    for (uint32_t sprite_i = 0; sprite_i < sprite_count; sprite_i ++) {
        uint64_t buffer_factory_offset = buffer_factory_pos;
        uint32_t input_x, input_y, input_width, input_height;

        _find_ireg(pixels[sprite_i], qois[sprite_i].width, qois[sprite_i].height, &input_x, &input_y, &input_width, &input_height);

        atlas->sprites[(sprite_i*2)] = (struct mascot_sprite) {
            .width = qois[sprite_i].width,
            .height = qois[sprite_i].height,
            .offset = buffer_factory_offset,
            .ireg = {
                .x = input_x,
                .y = input_y,
                .w = input_width,
                .h = input_height
            }
        };

        atlas->sprites[(sprite_i*2)+1] = (struct mascot_sprite) {
            .width = qois[sprite_i].width,
            .height = qois[sprite_i].height,
            .offset = buffer_factory_offset + (uint64_t)qois[sprite_i].width*(uint64_t)qois[sprite_i].height*(uint64_t)4,
            .ireg = {
                .x = qois[sprite_i].width - input_x - input_width,
                .y = input_y,
                .w = input_width,
                .h = input_height
            }
        };
        if (!_write_buffers(buffer_factory, &buffer_factory_pos, pixels[sprite_i], (size_t)qois[sprite_i].width*(size_t)qois[sprite_i].height*(size_t)4, qois[sprite_i].width, qois[sprite_i].height)) {
            environment_buffer_factory_destroy(buffer_factory);
            goto fail_free_qoi_ctxs;
        }
    }

    environment_buffer_factory_done(buffer_factory);

    for (uint32_t mascot_sprite = 0; mascot_sprite < sprite_count*2; mascot_sprite ++) {
        atlas->sprites[mascot_sprite].buffer = environment_buffer_factory_create_buffer(buffer_factory, atlas->sprites[mascot_sprite].width, atlas->sprites[mascot_sprite].height, atlas->sprites[mascot_sprite].width*4, atlas->sprites[mascot_sprite].offset);
        environment_buffer_add_to_input_region(atlas->sprites[mascot_sprite].buffer, atlas->sprites[mascot_sprite].ireg.x, atlas->sprites[mascot_sprite].ireg.y, atlas->sprites[mascot_sprite].ireg.w, atlas->sprites[mascot_sprite].ireg.h);
        if (mascot_sprite%2 == 0) DEBUG("Atlas \"%s\": Created sprite \"%s\"", dirname, namelist[mascot_sprite/2]);
        else DEBUG("Atlas \"%s\": Created sprite \"%s\" (Right)", dirname, namelist[mascot_sprite/2]);
    }

    environment_buffer_factory_destroy(buffer_factory);

    atlas->name_order = namelist;
    atlas->sprite_count = sprite_count;

    for (uint32_t i = 0; i < sprite_count; i++) free(pixels[i]);
    for (uint32_t i = 0; i < file_count; i++) free(file_paths[i]);
    free(file_paths);
    free(qois);
    free(pixels);

    DEBUG("Sucessfully created atlas for directory \"%s\", located at %p", dirname, atlas);

    return atlas;

fail_free_qoi_ctxs:
    if (atlas) free(atlas->sprites);
    free(atlas);
    for (uint32_t i = 0; i < sprite_count; i++) free(pixels[i]);
    free(pixels);
    for (uint32_t i = 0; i < sprite_count; i++) free(namelist[i]);
    for (uint32_t i = 0; i < file_count; i++) free(file_paths[i]);
    free(qois);
    free(namelist);
    free(file_paths);
    return NULL;
}

void mascot_atlas_destroy(struct mascot_atlas* atlas)
{
    if (!atlas) return;

    for (uint32_t i = 0; i < (uint32_t)atlas->sprite_count*2; i++) {
        if (i % 2 == 0) free(atlas->name_order[i/2]);
        environment_buffer_destroy(atlas->sprites[i].buffer);
    }

    free(atlas->name_order);
    free(atlas->sprites);
    free(atlas);
}


struct mascot_sprite* mascot_atlas_get(const struct mascot_atlas* atlas, uint16_t index, bool right)
{
    if (!atlas) return NULL;
    if (index >= atlas->sprite_count) return NULL;

    return &atlas->sprites[(index*2)+right];
}

uint16_t mascot_atlas_get_name_index(const struct mascot_atlas* atlas, const char* name)
{
    if (!atlas) return UINT16_MAX;

    for (uint16_t i = 0; i < atlas->sprite_count; i++) {
        if (strcmp(atlas->name_order[i], name) == 0) {
            return i;
        }
    }

    return UINT16_MAX;
}
