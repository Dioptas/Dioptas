"""Test-only independent Python references for the Rust input/display boundary.

The production Rust processor is launched with Python and PATH unavailable.
No Python process participates in its numerical or file-reading operations.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import fabio
import h5py
import numpy as np

from dioptas.desktop.display import image_levels
from dioptas.desktop.session import raster

ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = Path(os.environ.get("DIOPTAS_NATIVE_PROCESSOR", str(ROOT / "desktop/backend/target/debug" / ("dioptas-processor.exe" if os.name == "nt" else "dioptas-processor"))))
PROCESSOR_ARGUMENTS = (["--resource-dir", os.environ["DIOPTAS_RESOURCE_DIR"]]
                       if "DIOPTAS_RESOURCE_DIR" in os.environ
                       else ["--source-root", str(ROOT)])


def read_exact(stream, size):
    result = bytearray()
    while len(result) < size:
        chunk = stream.read(size - len(result))
        if not chunk:
            raise RuntimeError("Native processor closed the response pipe")
        result.extend(chunk)
    return result


def main():
    environment = {**os.environ, "PATH": "/nonexistent", "DIOPTAS_PYTHON": "/nonexistent/python"}
    process = subprocess.Popen([str(EXECUTABLE), *PROCESSOR_ARGUMENTS], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
    buffers = {}
    next_id = 0

    def invoke(action, payload):
        nonlocal next_id
        next_id += 1
        process.stdin.write((json.dumps({"id": next_id, "action": action, "payload": payload}) + "\n").encode())
        process.stdin.flush()
        length, = struct.unpack("<I", read_exact(process.stdout, 4))
        header = json.loads(read_exact(process.stdout, length))
        assert header["id"] == next_id
        for buffer in header["buffers"]:
            buffers[buffer["id"]] = read_exact(process.stdout, buffer["length"])
        result = header["result"]
        assert result["ok"], result
        return result

    results = []

    def compare(label, values, payload):
        actual = invoke("open_image", payload)
        expected = np.ascontiguousarray(values[::-1], dtype="<f4").tobytes()
        assert buffers[actual["image"]["bufferId"]] == expected, label
        reference = raster(values[::-1], max_side=None, histogram=True)
        np.testing.assert_array_equal(actual["image"]["histogram"]["counts"], reference["histogram"]["counts"])
        np.testing.assert_allclose(actual["image"]["histogram"]["edges"], reference["histogram"]["edges"], rtol=2e-14, atol=2e-14)
        for mode in ("percentile", "minmax", "mean3std"):
            expected_levels = image_levels(values[::-1], mode=mode)
            native = invoke("image_levels", {"mode": mode})["levels"]
            np.testing.assert_allclose(native, expected_levels, rtol=2e-14, atol=2e-14)
        results.append({"source": label, "shape": list(values.shape), "dtype": str(values.dtype), "displayBytesExact": True, "histogramCountsExact": True})

    try:
        fixture = ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif"
        compare("CeO2_Pilatus1M.tif", fabio.open(str(fixture)).data, {"path": str(fixture)})
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "frames.h5"
            values = np.arange(2 * 17 * 23, dtype=np.uint16).reshape(2, 17, 23)
            with h5py.File(file, "w") as target:
                target.create_dataset("counts", data=values, chunks=(1, 17, 23), compression="gzip")
            for frame in range(2):
                compare(f"gzip HDF5 frame {frame}", values[frame], {"path": str(file), "dataset": "/counts", "frame": frame})
        print(json.dumps(results, indent=2))
    finally:
        process.stdin.close()
        process.wait(timeout=10)
        assert process.returncode == 0, process.stderr.read().decode()


if __name__ == "__main__":
    main()
