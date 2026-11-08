"""Independent Python/C comparisons of all bundled native mask plugins.

Only this test driver imports Python. The worker has neither Python nor PATH.
Spot statistics use the existing C accelerator and SciPy smoothing route.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import fabio
import numpy as np
from pyFAI.geometry import Geometry

from dioptas.model.util.MaskPlugin import GeometryContext
from dioptas.model.util.mask_plugins import (
    ThresholdMaskPlugin, CosmicRayMaskPlugin, PowderDiffSpotMaskPlugin,
)
from dioptas.model.util.mask_plugins import powder_outlier
from native_backend_parity import PROCESSOR_ARGUMENTS, EXECUTABLE, ROOT, read_exact


def main():
    assert powder_outlier._c_compute_binned is not None, "Build/install the reference C accelerator for this comparison"
    # Qualify the deterministic SciPy route used by the Rust implementation.
    powder_outlier._cv2 = None
    child = subprocess.Popen([str(EXECUTABLE), *PROCESSOR_ARGUMENTS], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env={**os.environ, "PATH": "/nonexistent", "DIOPTAS_PYTHON": "/nonexistent/python"})
    identifier = 0
    buffers = {}

    def invoke(action, **payload):
        nonlocal identifier
        identifier += 1
        child.stdin.write((json.dumps(dict(id=identifier, action=action, payload=payload)) + "\n").encode())
        child.stdin.flush()
        size, = struct.unpack("<I", read_exact(child.stdout, 4))
        header = json.loads(read_exact(child.stdout, size))
        assert header["id"] == identifier
        for item in header["buffers"]:
            buffers[item["id"]] = read_exact(child.stdout, item["length"])
        result = header["result"]
        assert result["ok"], result
        return result

    def native_mask(result):
        m = result["mask"]
        return np.frombuffer(buffers[m["bufferId"]], np.uint8).reshape(m["height"], m["width"]).astype(bool)

    receipts = []
    try:
        assert invoke("__host__")["runtime"] == "rust"
        rng = np.random.default_rng(715)
        synthetic = rng.normal(40, 4, (96, 113))
        synthetic[0, 0] = 90000
        synthetic[95, 112] = 80000
        synthetic[50:54, 44:48] = 4000
        synthetic[51, 49] = 900
        synthetic[:, 65] = -1
        synthetic[14:16, 12:15] = 5000
        synthetic[43:47, 60:65] = 10000
        # A narrow detector gap next to a bright cluster exercises reach limits.
        image_path = ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif"
        measured = fabio.open(str(image_path)).data[::-1].astype(np.float64)
        with tempfile.TemporaryDirectory() as directory:
            for label, image in [("synthetic", synthetic), ("measured-CeO2", measured)]:
                file = Path(directory) / "image.npy"
                np.save(file, image[::-1])
                # Each independently generated detector fixture is a new setup.
                loaded = invoke("open_image", path=str(file), defer_integration=True)
                if loaded.get("imageChange"):
                    invoke("open_image", path=str(file), defer_integration=True, reset_calibration=True)
                shape = image.shape
                values = dict(dist=0.14, poni1=shape[0]*0.000172*0.49,
                              poni2=shape[1]*0.000172*0.52, rot1=0.012,
                              rot2=-0.018, rot3=0.025, pixel1=0.000172,
                              pixel2=0.000172, wavelength=0.406626e-10)
                invoke("manual_geometry", convention="pyfai", values={**values, "polarization_factor": 0.99}, defer_integration=True)
                geometry = Geometry(**values)
                context = GeometryContext(tth_array=geometry.center_array(shape, unit="2th_rad"),
                    azi_array=geometry.center_array(shape, unit="chi_rad"), **values)
                existing = np.zeros(shape, bool)
                stroke = invoke("mask_stroke", points=[[65, row] for row in range(shape[0])], radius=1, defer_integration=True)
                existing[:] = native_mask(stroke)
                classes = [ThresholdMaskPlugin, CosmicRayMaskPlugin, PowderDiffSpotMaskPlugin]
                cases = [
                    (0, dict(above_value=1500, below_enabled=True, below_value=0)),
                    (0, dict(above_enabled=False, below_enabled=False)),
                    (1, dict(sigma=3, window_size=3, iterations=1, min_intensity=100)),
                    (1, dict(sigma=5, window_size=6, iterations=3, min_intensity=60)),
                    (1, dict(sigma=7, window_size=11, iterations=2, min_intensity=200)),
                    (2, dict(method="median", num_bins=128, smooth_sigma=0)),
                    (2, dict(method="mean", num_bins=128, smooth_sigma=0, iterations=5)),
                    (2, dict(method="median", num_bins=445, smooth_sigma=1, smooth_threshold=0.3)),
                    (2, dict(method="mean", num_bins=128, smooth_sigma=1.6, smooth_threshold=0.12)),
                    (2, dict(method="median", num_bins=128, smooth_sigma=2.5, smooth_threshold=0.3)),
                ]
                for index, settings in cases:
                    plugin = classes[index]()
                    plugin.update_settings(settings)
                    result = invoke("mask_plugin", name=plugin.name, enabled=True,
                                    settings=plugin.get_settings(), defer_integration=True)
                    kwargs = dict(existing_mask=existing)
                    if index == 2:
                        kwargs["geometry"] = context
                    expected_plugin = plugin.compute_mask(image, **kwargs)
                    expected = expected_plugin | existing
                    actual = native_mask(result)
                    count = np.count_nonzero(actual != expected)
                    assert count == 0, (label, plugin.name, settings, count,
                                        np.argwhere(actual != expected)[:10].tolist())
                    details = result["state"]["maskDetails"]["plugins"][index]
                    assert details["settings"] == plugin.get_settings()
                    assert details["schema"] == plugin.get_settings_schema()
                    assert details["maskedPixels"] == np.count_nonzero(expected_plugin)
                    receipts.append(dict(source=label, plugin=plugin.name, settings=settings,
                                         maskedPixels=int(np.count_nonzero(expected_plugin)), differentPixels=int(count)))
                    invoke("mask_plugin", name=plugin.name, enabled=False, defer_integration=True)
                invoke("clear_mask", defer_integration=True)
                plugin = PowderDiffSpotMaskPlugin()
                empty_result = invoke("mask_plugin", name=plugin.name, enabled=True, settings=plugin.get_settings(), defer_integration=True)
                np.testing.assert_array_equal(native_mask(empty_result), plugin.compute_mask(image, geometry=context, existing_mask=np.zeros(shape,bool)))
                receipts.append(dict(source=label, plugin=plugin.name, existingMask="empty", maskedPixels=int(np.count_nonzero(native_mask(empty_result))), differentPixels=0))
                invoke("mask_plugin", name=plugin.name, enabled=False, defer_integration=True)
                # Recompute an enabled Spot mask after geometry changes, then
                # undo that geometry and recover the former output exactly.
                enabled = invoke("mask_plugin", name=plugin.name, enabled=True, defer_integration=True)
                changed = {**values, "poni2": values["poni2"]+0.001}
                moved = invoke("manual_geometry", convention="pyfai", values={**changed, "polarization_factor":0.99}, defer_integration=True)
                changed_geo = Geometry(**changed)
                changed_context = GeometryContext(tth_array=changed_geo.center_array(shape,unit="2th_rad"),azi_array=changed_geo.center_array(shape,unit="chi_rad"),**changed)
                np.testing.assert_array_equal(native_mask(moved),plugin.compute_mask(image,geometry=changed_context,existing_mask=np.zeros(shape,bool)))
                restored = invoke("undo_calibration",defer_integration=True)
                np.testing.assert_array_equal(native_mask(restored),native_mask(enabled))
                receipts.append(dict(source=label, plugin=plugin.name, geometryChangeAndUndo=True, differentPixels=0))
                invoke("mask_plugin", name=plugin.name, enabled=False, defer_integration=True)
            # Cosmic treats NaNs and negative values as excluded neighbors;
            # threshold comparisons preserve IEEE behavior, including infinities.
            nonfinite = synthetic.copy()
            nonfinite[3, 3] = np.nan
            nonfinite[4, 4] = -np.inf
            np.save(file, nonfinite[::-1])
            loaded = invoke("open_image", path=str(file), defer_integration=True)
            if loaded.get("imageChange"):
                invoke("open_image", path=str(file), defer_integration=True, reset_calibration=True)
            for cls in [ThresholdMaskPlugin, CosmicRayMaskPlugin]:
                plugin = cls()
                result = invoke("mask_plugin", name=plugin.name, enabled=True, settings=plugin.get_settings(), defer_integration=True)
                np.testing.assert_array_equal(native_mask(result), plugin.compute_mask(nonfinite))
                invoke("mask_plugin", name=plugin.name, enabled=False, defer_integration=True)
        artifact = ROOT / "desktop/artifacts/native-mask"
        artifact.mkdir(parents=True, exist_ok=True)
        (artifact / "parity-results.json").write_text(json.dumps(receipts, indent=2) + "\n")
        print(json.dumps(dict(comparisons=len(receipts)+2, differentPixels=0,
                             reference="bundled Python Threshold/Cosmic; Spot C accelerator and SciPy Gaussian",
                             receipts=str(artifact / "parity-results.json")), indent=2))
    finally:
        child.stdin.close()
        child.wait(timeout=10)
        assert child.returncode == 0, child.stderr.read().decode()


if __name__ == "__main__":
    main()
