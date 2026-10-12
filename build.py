"""Builds the bc7e shared library for the current platform into dist/<platform>/, together with bc7e's LICENSE
and a VERSION.txt recording the bc7enc_rdo commit and ISPC version used.

GitHub Actions builds every platform, see .github/workflows/build.yml. A local build needs a bc7enc_rdo checkout and
ISPC, plus MSVC on PATH on Windows (cl and link, with INCLUDE and LIB set).

    python build.py --upstream <bc7enc_rdo checkout> --ispc <ISPC executable>

Outputs per platform:
    win-x64/bc7e.dll
    linux-x64/libbc7e.so
    linux-arm64/libbc7e.so
    osx-arm64/libbc7e.dylib
"""
import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BUILD = ROOT / 'build'
DIST = ROOT / 'dist'
SHIM = ROOT / 'src' / 'bc7e_image.c'

# ISPC emits one copy of the code per instruction set and picks one at run time, so the library also runs on CPUs
# without AVX2
X86_TARGETS = 'sse2-i32x4,sse4-i32x4,avx2-i32x8,avx512skx-x16'
ARM_TARGETS = 'neon-i32x4'


def run(*args: str | Path) -> None:
    print('>', ' '.join(str(arg) for arg in args), flush=True)
    subprocess.run([str(arg) for arg in args], check=True)


def output(*args: str | Path) -> str:
    return subprocess.run([str(arg) for arg in args], check=True, capture_output=True, text=True).stdout.strip()


def compile_ispc(ispc: Path, source: Path, work: Path, *, arch: str, target_os: str) -> list[Path]:
    """Returns the object files: one dispatcher plus one per instruction set. The header bc7e_ispc.h goes into work"""
    work.mkdir(parents=True, exist_ok=True)
    suffix = '.obj' if target_os == 'windows' else '.o'
    targets = X86_TARGETS if arch == 'x86-64' else ARM_TARGETS
    # Upstream calls --opt=fast-math optional; leaving it out keeps the instruction sets' results as close as possible.
    # --pic only matters where shared libraries need position-independent code
    pic = [] if target_os == 'windows' else ['--pic']
    run(ispc, '-O2', '--opt=disable-assertions', '--wno-perf', *pic, f'--arch={arch}', f'--target-os={target_os}',
        f'--target={targets}', source, '-o', work / f'bc7e{suffix}', '-h', work / 'bc7e_ispc.h')
    return sorted(work.glob(f'bc7e*{suffix}'))


def link_windows(work: Path, objects: list[Path], target: Path) -> None:
    # /MT links the C runtime statically, so the DLL depends on KERNEL32 only
    run('cl', '/nologo', '/O2', '/LD', '/MT', f'/I{work}', SHIM, *objects, f'/Fo{work}\\', f'/Fe{target}',
        '/link', f'/IMPLIB:{work / "bc7e.lib"}')


def link_linux(work: Path, objects: list[Path], target: Path) -> None:
    run('cc', '-O2', '-fPIC', '-shared', '-fvisibility=hidden', f'-I{work}', SHIM, *objects, '-o', target, '-lm')


def link_macos(work: Path, objects: list[Path], target: Path) -> None:
    run('cc', '-O2', '-dynamiclib', '-arch', 'arm64', '-mmacosx-version-min=11.0', '-fvisibility=hidden', f'-I{work}',
        SHIM, *objects, '-o', target, '-install_name', '@rpath/libbc7e.dylib')


# (sys.platform prefix, lowercase platform.machine()): (platform name, file name, ISPC --arch, ISPC --target-os, linker)
PLATFORMS = {
    ('win32', 'amd64'): ('win-x64', 'bc7e.dll', 'x86-64', 'windows', link_windows),
    ('linux', 'x86_64'): ('linux-x64', 'libbc7e.so', 'x86-64', 'linux', link_linux),
    ('linux', 'aarch64'): ('linux-arm64', 'libbc7e.so', 'aarch64', 'linux', link_linux),
    ('darwin', 'arm64'): ('osx-arm64', 'libbc7e.dylib', 'aarch64', 'macos', link_macos),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--upstream', type=Path, required=True, help='bc7enc_rdo checkout')
    parser.add_argument('--ispc', type=Path, required=True, help='ISPC executable')
    args = parser.parse_args()
    ispc = args.ispc.resolve()
    machine = platform.machine().lower()
    entry = next((value for (prefix, arch), value in PLATFORMS.items()
                  if sys.platform.startswith(prefix) and arch == machine), None)
    if entry is None:
        print(f'unsupported platform: {sys.platform} {platform.machine()}', file=sys.stderr)
        return 1
    name, file_name, arch, target_os, link = entry

    shutil.rmtree(BUILD, ignore_errors=True)
    work = BUILD / name
    objects = compile_ispc(ispc, args.upstream / 'bc7e.ispc', work, arch=arch, target_os=target_os)
    target_dir = DIST / name
    shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True)
    link(work, objects, target_dir / file_name)

    # bc7e.ispc is Apache 2.0 licensed; the license has to ship with the library
    shutil.copyfile(args.upstream / 'LICENSE', target_dir / 'LICENSE')
    commit = output('git', '-C', args.upstream, 'log', '-1', '--format=%H %cs')
    ispc_version = output(ispc, '--version').splitlines()[0]
    (target_dir / 'VERSION.txt').write_text(f'bc7enc_rdo {commit}\n{ispc_version}\n', encoding='utf-8')
    print(f'built {target_dir / file_name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
