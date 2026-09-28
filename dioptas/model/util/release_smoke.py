"""Small, self-contained checks shared by source and frozen-app startup tests."""
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


def check_release_runtime():
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator
    from dioptas.model import eos
    from dioptas.pipeline import Pipeline
    from dioptas.model.util.mask_plugins.powder_outlier import _c_compute_binned

    if _c_compute_binned is None:
        raise RuntimeError("Dioptas powder-outlier C extension is missing")
    materials = {material.identifier: material for material in eos.load_materials()}
    for identifier in ("gold", "argon_fcc"):
        phase = eos.build_jcpds(materials[identifier], origin="bundled")
        phase.compute_d(10.0, 300.0)
        if not phase.reflections or not all(
            np.isfinite(reflection.d) and reflection.d > 0
            for reflection in phase.reflections
        ):
            raise RuntimeError(f"Invalid bundled diffraction phase: {identifier}")

    # No user files or settings are needed, and temporary calibration is removed.
    with TemporaryDirectory(prefix="dioptas-smoke-") as directory:
        calibration = Path(directory) / "smoke.poni"
        AzimuthalIntegrator(
            dist=0.1, poni1=0.0032, poni2=0.0032,
            pixel1=0.0001, pixel2=0.0001, wavelength=1e-10,
        ).save(str(calibration))
        pipeline = Pipeline()
        pipeline.load_calibration(str(calibration))
        pattern = pipeline.integrate(np.full((64, 64), 100.0))
        if not len(pattern.x) or not np.all(np.isfinite(pattern.y)):
            raise RuntimeError("Synthetic image integration failed")
    return len(materials)
