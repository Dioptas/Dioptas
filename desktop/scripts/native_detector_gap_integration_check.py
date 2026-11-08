"""Optional real-9M regression: automatic acquisition masks must affect integration."""
import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from native_reference_client import Native, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    folder = args.data
    receipt = {"frames": []}
    with Native() as native, tempfile.TemporaryDirectory() as temporary:
        native.call("integration_settings", bins=2000, cake_bins=90, trim_zeros=False)
        native.call("open_calibration", path=str(folder / "eiger_0000.poni"))
        first = native.call("open_image", path=str(folder / "eiger_0000.h5"))
        auto = native.raster(first, "mask").copy()
        image = native.raster(first, "rawImage")
        marker = image == np.float32(np.iinfo(np.uint32).max)
        assert not np.any(marker & (auto == 0))
        assert int(auto.sum()) == 887556
        assert np.any((image > 1_000_000) & ~marker & (auto == 0))
        reference = np.asarray(first["pattern"]["y"])
        path = Path(temporary) / "explicit-auto.mask"
        with path.open("wb") as output:
            np.save(output, auto.astype(bool))
        explicit = native.call("mask_file", path=str(path))
        np.testing.assert_array_equal(explicit["pattern"]["y"], reference)
        np.testing.assert_array_equal(native.raster(first, "cake"), native.raster(explicit, "cake"))
        native.call("clear_mask")
        disabled = native.call("integration_settings", use_mask=False)
        np.testing.assert_array_equal(disabled["pattern"]["y"], reference)
        native.call("integration_settings", use_mask=True)
        for frame in [0, 1, 7, 250, 624]:
            current = native.call("open_image", path=str(folder / "eiger_0000.h5"), frame=frame)
            mask = native.raster(current, "mask")
            pixels = native.raster(current, "rawImage")
            flagged = pixels == np.float32(np.iinfo(np.uint32).max)
            assert not np.any(flagged & (mask == 0)), frame
            receipt["frames"].append({"frame": frame, "invalidPixels": int(flagged.sum()), "maskedPixels": int(mask.sum())})
            # Bound this test client's retained buffers while traversing images.
            native.buffers.clear()
        native.call("map_load", paths=[str(folder / "eiger_0000.h5")], start=1, stop=4)
        stored = native.call("map_select", index=0, reintegrate=False)
        rebuilt = native.call("map_select", index=0, reintegrate=True)
        for actual in [stored, rebuilt]:
            np.testing.assert_allclose(actual["pattern"]["y"], reference, rtol=2e-12, atol=1e-8)
        receipt.update({"automaticPixels": int(auto.sum()), "medianIntensity": float(np.median(reference)),
                        "maximumIntensity": float(reference.max()), "explicitMaskExactlyMatches": True,
                        "cakeExactlyMatches": True, "userMaskDisabledStillExcludesDetectorInvalids": True,
                        "storedAndReintegratedMapMatch": True})
    with Native() as image_first:
        image_first.call("integration_settings", bins=2000, cake_bins=90, trim_zeros=False)
        image_first.call("open_image", path=str(folder / "eiger_0000.h5"))
        calibrated = image_first.call("open_calibration", path=str(folder / "eiger_0000.poni"))
        np.testing.assert_allclose(calibrated["pattern"]["y"], reference, rtol=2e-12, atol=1e-8)
        receipt["imageBeforeCalibrationMatches"] = True
    output = ROOT / "desktop/artifacts/native-mask/real-eiger-integration.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
