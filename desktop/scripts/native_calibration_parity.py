"""Test-only pyFAI forward-model and peak-file compatibility checks.

The Rust process runs with Python/PATH unavailable. The independent reference
receives exported scientific data only after each native operation completes.
"""
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from dioptas.desktop.session import DesktopSession
from native_backend_parity import EXECUTABLE, read_exact


def main():
    process = subprocess.Popen([str(EXECUTABLE)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={**os.environ, "PATH": "/nonexistent", "DIOPTAS_PYTHON": "/nonexistent/python"})
    identifier = 0

    def invoke(action, **payload):
        nonlocal identifier
        identifier += 1
        process.stdin.write((json.dumps({"id": identifier, "action": action, "payload": payload}) + "\n").encode())
        process.stdin.flush()
        length, = struct.unpack("<I", read_exact(process.stdout, 4))
        header = json.loads(read_exact(process.stdout, length))
        assert header["id"] == identifier
        for buffer in header["buffers"]:
            read_exact(process.stdout, buffer["length"])
        result = header["result"]
        assert result["ok"], result
        return result

    reference = DesktopSession()
    receipts = []
    try:
        invoke("example")
        for x, y, ring in [(637, 564, 1), (671, 511, 2), (668, 703, 3), (350.5, 592.8, 1), (554.3, 367.9, 1)]:
            invoke("pick_peak", x=x, y=y, ring=ring)
        invoke("workflow_settings", numberOfRings=4)
        with tempfile.TemporaryDirectory() as directory:
            for automatic in (False, True):
                fitted = invoke("calibrate", automatic=automatic)
                peak_file = Path(directory) / "native-peaks.json"
                poni_file = Path(directory) / "native.poni"
                invoke("save_peaks", path=str(peak_file))
                invoke("save_calibration", path=str(poni_file))
                assert reference.invoke("example")["ok"]
                imported = reference.invoke("load_peaks", {"path": str(peak_file)})
                assert imported["ok"], imported
                assert imported["state"]["calibration"]["picks"] == fitted["state"]["calibration"]["picks"]
                points = reference.configuration.calibration_model.get_point_array().copy()
                loaded = reference.invoke("open_calibration", {"path": str(poni_file)})
                assert loaded["ok"], loaded
                model = reference.configuration.calibration_model
                geometry = model.pattern_geometry
                model.calibrant.setWavelength_change2th(geometry.wavelength)
                targets = np.array(model.calibrant.get_2th())[points[:, 2].astype(int)]
                angles = geometry.tth(points[:, 0], points[:, 1])
                rms = np.rad2deg(np.sqrt(np.mean((angles - targets) ** 2)))
                native_rms = fitted["state"]["calibration"]["rmsDegrees"]
                np.testing.assert_allclose(rms, native_rms, rtol=1e-8, atol=1e-9)
                assert rms < 0.05
                receipts.append({"automatic": automatic, "groups": len(fitted["state"]["calibration"]["picks"]),
                                 "points": len(points), "nativeRmsDegrees": native_rms,
                                 "independentPyfaiRmsDegrees": float(rms), "peakFileExact": True})
        print(json.dumps(receipts, indent=2))
    finally:
        try:
            close = getattr(reference, "close", None)
            if close is not None:
                close()
        finally:
            process.stdin.close()
            process.wait(timeout=10)
            assert process.returncode == 0, process.stderr.read().decode()


if __name__ == "__main__":
    main()
