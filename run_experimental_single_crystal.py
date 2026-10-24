# SPDX-License-Identifier: MIT
"""Development launcher; configure HDF5 before importing the Dioptas package."""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
from pathlib import Path
import sys

_HDF5_HANDLES = []


def disable_external_hdf5_plugins():
    """Disable automatic discovery in the bundled HDF5, for this process only.

    Some desktop installations have incompatible external HDF5 plugins. Load
    the wheel's own HDF5 and use its public C API before h5py initializes LZF.
    hdf5plugin still explicitly registers its bundled compression filters.
    """
    spec = importlib.util.find_spec("h5py")
    if spec is None or spec.origin is None:
        raise RuntimeError("h5py is not installed in this development environment.")
    package = Path(spec.origin).parent
    roots = [package, package.parent / "h5py.libs"]
    candidates = set()
    for root in roots:
        if root.is_dir():
            for pattern in ("libhdf5*.dylib", "libhdf5*.so*", "*hdf5*.dll"):
                for path in root.rglob(pattern):
                    if "hdf5_hl" not in path.name and path.is_file():
                        candidates.add(path.resolve())
    if len(candidates) != 1:
        raise RuntimeError(
            "Could not identify one bundled HDF5 library; omit the isolation flag."
        )
    library = ctypes.CDLL(str(candidates.pop()))
    configure = library.H5PLset_loading_state
    configure.argtypes = [ctypes.c_uint]
    configure.restype = ctypes.c_int
    if configure(0) < 0:
        raise RuntimeError("Could not disable external HDF5 plugin discovery.")
    _HDF5_HANDLES.append(library)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--no-hdf5-plugin-autoload", action="store_true")
    args, remaining = parser.parse_known_args()
    if args.no_hdf5_plugin_autoload:
        disable_external_hdf5_plugins()
    sys.argv = [sys.argv[0], *remaining]
    from dioptas.experimental_single_crystal import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
