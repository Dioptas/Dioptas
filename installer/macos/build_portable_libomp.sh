#!/usr/bin/env bash
# Build a pinned OpenMP runtime without raising the wheel's macOS minimum.
set -euo pipefail

prefix="${1:?Provide an installation prefix}"
deployment_target="${2:-14.0}"
source_dir=$(mktemp -d)
trap 'rm -rf "$source_dir"' EXIT

version=23.1.5
release_url="https://github.com/llvm/llvm-project/releases/download/llvmorg-${version}"
archive="$source_dir/llvm.tar.xz"
curl --fail --location --retry 3 "$release_url/llvm-project-${version}.src.tar.xz" -o "$archive"
digest=fb50b1eac93ddeb3aa8dab4cfe324dff74f4a9c2bdee6160c9e36188f8d06a6e
printf '%s  %s\n' "$digest" "$archive" | shasum -a 256 --check
tar -xf "$archive" -C "$source_dir" --strip-components=1

cmake -S "$source_dir/runtimes" -B "$source_dir/build" -G Ninja \
    -DLLVM_ENABLE_RUNTIMES=openmp \
    -DLLVM_INCLUDE_TESTS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET="$deployment_target" \
    -DCMAKE_INSTALL_NAME_DIR="$prefix/lib" \
    -DCMAKE_BUILD_WITH_INSTALL_NAME_DIR=ON \
    -DOPENMP_INSTALL_LIBDIR=lib \
    -DLIBOMP_HEADERS_INSTALL_PATH=include \
    -DOPENMP_ENABLE_LIBOMPTARGET=OFF \
    -DOPENMP_ENABLE_OMPT_TOOLS=OFF
cmake --build "$source_dir/build" --parallel 3
cmake --install "$source_dir/build"

python3 - "$prefix/lib/libomp.dylib" "$deployment_target" <<'PY'
import re
import subprocess
import sys

output = subprocess.check_output(["xcrun", "vtool", "-show-build", sys.argv[1]], text=True)
print(output)
minimum = re.search(r"^\s*minos\s+([\d.]+)", output, re.MULTILINE)
def version(value):
    return tuple((list(map(int, value.split("."))) + [0, 0, 0])[:3])
if minimum is None or version(minimum[1]) > version(sys.argv[2]):
    raise SystemExit("OpenMP runtime exceeds the requested macOS deployment target")
PY

if [[ -n "${GITHUB_ENV:-}" ]]; then
    printf 'DIOPTAS_LIBOMP_PREFIX=%s\n' "$prefix" >> "$GITHUB_ENV"
fi
