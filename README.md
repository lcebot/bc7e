# bc7e shared library

Prebuilt shared libraries that encode whole RGBA images to BC7, with a small C API that is easy to call from ctypes or any other FFI.

The encoder is bc7e.ispc from [bc7enc_rdo](https://github.com/richgel999/bc7enc_rdo), compiled with [ISPC](https://github.com/ispc/ispc). ISPC emits code for SSE2, SSE4, AVX2 and AVX-512 on x86-64, or NEON on arm64, and picks the best one for the CPU at run time.

## Platforms

| Platform | Library |
|---|---|
| Windows x64 | `win-x64/bc7e.dll` |
| Linux x64 | `linux-x64/libbc7e.so` |
| Linux arm64 | `linux-arm64/libbc7e.so` |
| macOS Apple Silicon | `osx-arm64/libbc7e.dylib` |

GitHub Actions builds all four on every push, on demand, and once a month. Each run uses the latest commit of bc7enc_rdo and the latest ISPC release.

The `bc7e` artifact of a run holds one directory per platform. Each directory contains:
- the library;
- bc7e's `LICENSE`;
- a `VERSION.txt` recording the bc7enc_rdo commit and ISPC version.

The Windows DLL links the C runtime statically and depends on KERNEL32 only.

## API

```c
void bc7e_image_init(void);
uint32_t bc7e_image_level_count(void);
int bc7e_image_encode(const uint8_t *rgba, uint32_t width, uint32_t height, uint32_t level, int perceptual,
                      uint8_t *blocks);
```

How to use it:
- **Init:** call `bc7e_image_init` once before encoding. After that, any number of threads may encode at the same time.
- **Input and output:** `rgba` holds the pixels row by row. `blocks` receives `ceil(width / 4) * ceil(height / 4) * 16` bytes, block rows in the same order as the pixel rows. When the width or height is not a multiple of 4, the last block row and column repeat the edge pixels.
- **Levels:** `level` goes from 0 (ultrafast) to 6 (slowest).
- **Perceptual:** a nonzero `perceptual` weights the error by luma and chroma instead of RGB.
- **Return value:** 0 on success, -1 for an out-of-range level, and -2 when memory runs out.

`bc7e.py` is a ctypes binding that picks the library for the current platform:

```python
import bc7e
blocks = bc7e.encode(rgba_bytes, (width, height), level='slowest', perceptual=False)
```

### Choosing a level

We tested on illustrations and on UI textures with alpha:
- **`slowest` without `perceptual` was best.** It gave the highest RGB PSNR of all levels, and also beat texconv `-bc x` and etcpak.
- **`perceptual` was worse overall.** It raised luma PSNR on some images, but its CIELAB ΔE was clearly higher.
- **Speed:** `slowest` takes about 0.7 s for a 400x400 image on one thread.

## Building locally

```bash
python build.py --upstream <bc7enc_rdo checkout> --ispc <ISPC executable>
python smoke_test.py
```

On Windows, MSVC must be on PATH, for example in a Developer Command Prompt. The output goes to `dist/<platform>/`. `smoke_test.py` needs numpy and Pillow.

## License

bc7e.ispc is Copyright Binomial LLC and licensed under Apache 2.0. Ship its `LICENSE` with the library.
