"""Small, self-contained checks shared by source and frozen-app startup tests."""
from importlib.metadata import version
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


def check_release_runtime():
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator
    from dioptas.model import eos
    from dioptas.pipeline import Pipeline
    from dioptas.model.util.mask_plugins.powder_outlier import _c_compute_binned
    from peritheos import Material as PeritheosMaterial, get_material, load_eosmat

    peritheos_version = version("peritheos")
    if not peritheos_version.startswith("0.16."):
        raise RuntimeError(f"Unsupported bundled Peritheos version: {peritheos_version}")

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

    for identifier in ("palladium", "wadsleyite"):
        if materials[identifier].default_eos_index != -1:
            raise RuntimeError(f"Recommendation hold lost for {identifier}")

    gold = materials["gold"]
    record = gold.eos_records[gold.default_eos_index]
    if (eos.record_reproduction(record)[0] != "Parameter parity"
            or not eos.reconstruction_report_url(record)):
        raise RuntimeError("Scoped EOS reconstruction assessment is missing")

    # Exercise checksum-verified packaged source rows, also in frozen builds.
    pv = get_material("coesite").get_dataset(
        "coesite_levien_1981_table7_pv").as_pressure_volume(pressure_unit="GPa")
    if (not len(pv.volume) or not np.all(np.isfinite(pv.volume))
            or not np.all(np.isfinite(pv.pressure))):
        raise RuntimeError("Packaged Peritheos observation data are unavailable")

    # No user files or settings are needed, and temporary calibration is removed.
    with TemporaryDirectory(prefix="dioptas-smoke-") as directory:
        material_path = Path(directory) / "gold.eosmat"
        eos.save_material_file(str(material_path), gold)
        native = load_eosmat(material_path)
        if native["format_version"] != 4:
            raise RuntimeError("Native EOSMAT v4 export failed")
        imported = eos.build_jcpds(eos.load_material_file(str(material_path)), origin="file")
        imported.compute_d(20., 1000.)
        expected = PeritheosMaterial.from_eosmat(
            native, record_identifiers=[record["identifier"]],
        ).eos_records[0].volume(20., 1000., check_validity=False)
        if not np.isclose(imported.params["v"], expected, rtol=1e-10, atol=0):
            raise RuntimeError("Native EOSMAT thermal calculation changed during import")
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
    logging.getLogger(__name__).info(
        "Peritheos %s: native EOSMAT, thermal calculation, source data and assessments verified",
        peritheos_version)
    return len(materials)
