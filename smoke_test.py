"""Checks that the built library loads and encodes correctly on this platform: decodes with Pillow to check the
quality, and checks that threads produce the same blocks as a single thread.

    python smoke_test.py [library_root]
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

import bc7e


def sample(width: int, height: int) -> np.ndarray:
    """RGBA gradients, checkers and noise, with a semi-transparent area in the top-left corner"""
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 4), np.uint8)
    image[..., 0] = xx * 255 // max(width - 1, 1)
    image[..., 1] = yy * 255 // max(height - 1, 1)
    image[..., 2] = np.where((xx // 16 + yy // 16) % 2 == 0, 220, 30)
    image[..., :3] = np.clip(image[..., :3] + rng.integers(-8, 9, (height, width, 3)), 0, 255)
    image[..., 3] = 255
    image[: height // 3, : width // 3, 3] = 96
    return image


def decode(blocks: bytes, width: int, height: int) -> np.ndarray:
    padded = ((width + 3) // 4 * 4, (height + 3) // 4 * 4)
    return np.asarray(Image.frombuffer('RGBA', padded, blocks, 'bcn', 7))[:height, :width]


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = np.mean((a.astype(np.float64) - b) ** 2)
    return float('inf') if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else bc7e.DIST
    failures = 0
    # Sizes that are not multiples of 4 exercise the edge padding
    for width, height in ((400, 400), (332, 159)):
        image = sample(width, height)
        for level in ('ultrafast', 'slowest'):
            blocks = bc7e.encode(image.tobytes(), (width, height), level=level, perceptual=False, library_root=root)
            quality = psnr(decode(blocks, width, height), image)
            ok = quality > 35
            failures += not ok
            print(f'{width}x{height} {level:9} PSNR {quality:.2f} dB {"ok" if ok else "FAILED"}')

    image = sample(400, 400).tobytes()
    single = bc7e.encode(image, (400, 400), level='basic', perceptual=True, library_root=root)
    with ThreadPoolExecutor(4) as executor:
        results = list(executor.map(lambda _: bc7e.encode(image, (400, 400), level='basic', perceptual=True,
                                                          library_root=root), range(8)))
    same = all(result == single for result in results)
    failures += not same
    print(f'threads give identical blocks: {same}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
