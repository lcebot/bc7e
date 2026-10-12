"""ctypes binding for the bc7e shared library. Libraries sit under library_root in the layout build.py produces"""
import ctypes
import functools
import platform
import sys
from pathlib import Path

DIST = Path(__file__).parent / 'dist'
# (sys.platform prefix, lowercase platform.machine()): library path
_LIBRARIES = {('win32', 'amd64'): 'win-x64/bc7e.dll',
              ('linux', 'x86_64'): 'linux-x64/libbc7e.so',
              ('linux', 'aarch64'): 'linux-arm64/libbc7e.so',
              ('darwin', 'arm64'): 'osx-arm64/libbc7e.dylib'}
# Level names, in the order of LEVELS in bc7e_image.c
LEVELS = ('ultrafast', 'veryfast', 'fast', 'basic', 'slow', 'veryslow', 'slowest')


@functools.cache
def _library(library_root: Path) -> ctypes.CDLL:
    machine = platform.machine().lower()
    name = next(name for (prefix, arch), name in _LIBRARIES.items()
                if sys.platform.startswith(prefix) and arch == machine)
    library = ctypes.CDLL(str(library_root / name))
    library.bc7e_image_encode.argtypes = (ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_int, ctypes.c_void_p)
    library.bc7e_image_encode.restype = ctypes.c_int
    library.bc7e_image_level_count.restype = ctypes.c_uint32
    assert library.bc7e_image_level_count() == len(LEVELS)
    library.bc7e_image_init()
    return library


def encode(pixels: bytes, dimensions: tuple[int, int], *, level: str, perceptual: bool,
           library_root: Path = DIST) -> bytes:
    """Encodes RGBA pixels of dimensions (width, height) to BC7. The GIL is released during the call, so several
    threads can encode at once"""
    width, height = dimensions
    blocks = ctypes.create_string_buffer(((width + 3) // 4) * ((height + 3) // 4) * 16)
    result = _library(library_root).bc7e_image_encode(pixels, width, height, LEVELS.index(level), perceptual, blocks)
    if result != 0:
        raise RuntimeError(f'bc7e_image_encode returned {result}')
    return blocks.raw
