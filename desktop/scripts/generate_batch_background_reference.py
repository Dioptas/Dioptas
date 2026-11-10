"""Independent Qt-model references; never imported by the native runtime.

Run with this checkout's CPython 3.13 environment from the repository root:
  .venv/bin/python desktop/scripts/generate_batch_background_reference.py
"""
import json
from pathlib import Path

import h5py
import numpy as np
from dioptas.model.BatchModel import BatchModel

cases = []
for unit, axis, parameters in [
    ("2th_deg", np.linspace(0.5, 12.0, 97), (0.37, 31, 8)),
    ("q_A^-1", np.linspace(0.15, 5.0, 97), (0.18, 19, 50)),
    ("d_A", 2 * np.pi / np.linspace(0.25, 5.0, 97), (1.4, 27, 12)),
]:
    t = np.linspace(0, 1, axis.size)
    data = np.array([
        scale * (24 + 11*t + 5*t*t + 0.2*np.cos(t*83) +
                 170*np.exp(-((t-0.29-shift)/0.017)**2) +
                 82*np.exp(-((t-0.67+shift)/0.029)**2))
        for scale, shift in [(1, 0), (2.4, 0.011), (0.43, -0.009)]
    ])
    model = BatchModel(None)
    model.binning = axis
    model.data = data.copy()
    model.extract_background(parameters)
    background = model.bkg.copy()
    model.normalize((4, 70), 1)
    model.extract_background(parameters)
    cases.append(dict(unit=unit, x=axis.tolist(), data=data.ravel().tolist(),
                      background=background.ravel().tolist(),
                      normalized_background=model.bkg.ravel().tolist(),
                      normalized_data=model.data.ravel().tolist(),
                      parameters=dict(zip(("smoothing", "iterations", "order"), parameters))))

target = Path(__file__).parents[1] / "backend/tests/fixtures/batch_background_qt.json"
target.write_text(json.dumps(dict(reference="Qt BatchModel.extract_background; xypattern 1.2.4 Cython SmoothBrucknerBackground; NumPy chebfit/chebval", cases=cases), indent=2) + "\n")
print(target)

# Small, independent input files let headless/transport gates run with no Python.
with h5py.File(target.with_name("batch_background_input.h5"), "w") as f:
    case = cases[0]
    f["data"] = np.array(case["data"]).reshape(3, -1)
    f["binning"] = case["x"]
    f["binning"].attrs["radial_unit"] = case["unit"]
    f["counting_std"] = np.sqrt(f["data"][:])
x = np.linspace(0.5, 12, 4096)
y = 20 + 3*x + 100*np.exp(-((x-4)/0.1)**2)
with h5py.File(target.with_name("batch_background_long.h5"), "w") as f:
    f.create_dataset("data", data=np.array([y, 2.3*y, 0.4*y]), compression="gzip")
    f["binning"] = x
    f["binning"].attrs["radial_unit"] = "2th_deg"
