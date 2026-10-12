// Whole-image BC7 encoding on top of bc7e, exported as a plain C API for ctypes and similar FFIs.
// bc7e takes pixels grouped by 4x4 block, so the row-major RGBA image is regrouped here. When the width or height is
// not a multiple of 4, the last block row and column repeat the edge pixels.
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "bc7e_ispc.h"

#if defined(_WIN32)
#define BC7E_IMAGE_API __declspec(dllexport)
#else
#define BC7E_IMAGE_API __attribute__((visibility("default")))
#endif

typedef void (*params_init)(struct bc7e_compress_block_params *, bool);

// Encoding levels, from fastest to highest quality
static const params_init LEVELS[] = {
    bc7e_compress_block_params_init_ultrafast,
    bc7e_compress_block_params_init_veryfast,
    bc7e_compress_block_params_init_fast,
    bc7e_compress_block_params_init_basic,
    bc7e_compress_block_params_init_slow,
    bc7e_compress_block_params_init_veryslow,
    bc7e_compress_block_params_init_slowest,
};

// Builds bc7e's lookup tables. Call once before the first encode; afterwards any number of threads may encode at once
BC7E_IMAGE_API void bc7e_image_init(void)
{
    bc7e_compress_block_init();
}

BC7E_IMAGE_API uint32_t bc7e_image_level_count(void)
{
    return sizeof(LEVELS) / sizeof(LEVELS[0]);
}

// Encodes width x height RGBA pixels into blocks, which must hold ceil(width / 4) * ceil(height / 4) * 16 bytes.
// Blocks are written row by row in the same order as the pixel rows. level indexes LEVELS; a nonzero perceptual
// weights the error by luma and chroma instead of RGB.
// Returns 0 on success, -1 for an out-of-range level and -2 when memory runs out
BC7E_IMAGE_API int bc7e_image_encode(const uint8_t *rgba, uint32_t width, uint32_t height, uint32_t level,
                                     int perceptual, uint8_t *blocks)
{
    if (level >= bc7e_image_level_count())
        return -1;
    struct bc7e_compress_block_params params;
    LEVELS[level](&params, perceptual != 0);

    const uint32_t blocks_x = (width + 3) / 4;
    const uint32_t blocks_y = (height + 3) / 4;
    uint32_t *pixels = malloc((size_t)blocks_x * 16 * sizeof(uint32_t));
    // The caller's buffer need not be 8-byte aligned, so each block row goes through an aligned buffer first
    uint64_t *row_blocks = malloc((size_t)blocks_x * 16);
    if (pixels == NULL || row_blocks == NULL)
    {
        free(pixels);
        free(row_blocks);
        return -2;
    }

    for (uint32_t by = 0; by < blocks_y; by++)
    {
        for (uint32_t bx = 0; bx < blocks_x; bx++)
        {
            for (uint32_t i = 0; i < 16; i++)
            {
                uint32_t x = bx * 4 + i % 4;
                uint32_t y = by * 4 + i / 4;
                if (x >= width)
                    x = width - 1;
                if (y >= height)
                    y = height - 1;
                memcpy(&pixels[bx * 16 + i], rgba + ((size_t)y * width + x) * 4, 4);
            }
        }
        bc7e_compress_blocks(blocks_x, row_blocks, pixels, &params);
        memcpy(blocks + (size_t)by * blocks_x * 16, row_blocks, (size_t)blocks_x * 16);
    }

    free(pixels);
    free(row_blocks);
    return 0;
}
