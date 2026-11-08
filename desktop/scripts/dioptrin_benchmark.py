"""Time cold setup separately from repeated measured-image integrations.

Run from the repository root using .venv/bin/python. Timings cover the model
boundary (including array preparation), excluding file IO, IPC and rendering.
Each engine uses its desktop method: full pixel split for Dioptrin, bbox CSR
for pyFAI. This measures application choices, not identical arithmetic.
"""

import argparse
import gc
from importlib.metadata import version
import json
from pathlib import Path
import platform
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dioptas.desktop.session import DesktopSession


def benchmark(engine, mode, repeats):
    session = DesktopSession(engine=engine)
    for action, payload in (
        ("example", {}),
        ("open_calibration", {"path": str(ROOT / "dioptas/tests/data/CeO2_Pilatus1M.poni"), "defer_integration": True}),
    ):
        response = session.invoke(action, payload)
        assert response["ok"], response.get("error")
    c = session.configuration.calibration_model
    shape = session.configuration.img_model.img_data.shape
    masks = []
    for column in (450, 550):
        mask = np.zeros(shape, dtype=bool)
        mask[350:450, column:column + 60] = True
        masks.append(mask)

    def integrate(index):
        mask = None if mode == "none" else masks[index % 2 if mode == "dynamic" else 0]
        start = time.perf_counter()
        c.integrate_1d(600, mask=mask, trim_zeros=False)
        pattern_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        c.integrate_2d(mask=mask, rad_points=600, azimuth_points=90)
        return {"pattern_ms": pattern_ms, "cake_ms": (time.perf_counter() - start) * 1000}

    cold = integrate(0)
    samples = [integrate(index + 1) for index in range(repeats)]
    assert c.use_dioptrin == (engine == "dioptrin")
    session.close()
    return {
        "engine": engine, "mask": mode, "shape": list(shape),
        "cold": cold, "repeated_median": {
            key: statistics.median(sample[key] for sample in samples) for key in cold
        }, "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--output", type=Path, default=ROOT / "desktop/artifacts/dioptrin-benchmark.json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    results = []
    for mode in ("none", "static", "dynamic"):
        for engine in ("pyfai", "dioptrin"):
            results.append(benchmark(engine, mode, args.repeats))
            gc.collect()  # Native integrators must be released on their owner thread.
    report = {
        "python": platform.python_version(), "platform": platform.platform(),
        "dioptrin": version("dioptrin"), "pyfai": version("pyfai"),
        "radial_bins": 600, "cake_azimuth_bins": 90,
        "scope": "Model calls; no file IO/IPC/rendering. Desktop engine methods differ.",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
