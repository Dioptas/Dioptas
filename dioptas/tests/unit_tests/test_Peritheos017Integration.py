"""Reference-pressure calculations and persistence with released Peritheos 0.17."""

from copy import deepcopy
import dataclasses

import pytest
from peritheos import get_material_document

from ...model import eos
from ...model.eos.material import Lattice
from ...model.DioptasModel import DioptasModel
from ...model.PhaseModel import PhaseModel
from ...model.util.eos_phase import EosPhase
from ...model.util.jcpds import CrystalState


def reference_phase():
    material = eos.Material.from_dict(get_material_document("coesite_iv"))
    index = next(i for i, record in enumerate(material.eos_records)
                 if record["eos"]["type"] == "BM2Reference")
    # Coesite-IV has no published structure in the library. Synthetic cubic
    # test geometry exercises phase state/persistence, not coesite diffraction.
    a = 375.04 ** (1. / 3.)
    material.symmetry = "CUBIC"
    material.lattice = Lattice(a=a, b=a, c=a, alpha=90., beta=90., gamma=90.)
    material.peaks = [[1, 0, 0, a, 100.]]
    return eos.build_jcpds(material, record_index=index, origin="bundled")


@pytest.mark.parametrize("pressure", [32.7, 45., 60.])
def test_reference_pressure_is_not_treated_as_zero_pressure(pressure):
    engine = EosPhase("BM2Reference", {"V0": 375.04, "K0": 254., "P0": 32.7})
    volume = engine.volume(pressure)
    ratio = 375.04 / volume
    expected = 32.7 + 1.5 * 254. * (ratio ** (7. / 3.) - ratio ** (5. / 3.))
    assert expected == pytest.approx(pressure, abs=1e-8)
    assert engine.volume(32.7) == pytest.approx(375.04, rel=1e-12)
    assert engine.pressure(375.04) == pytest.approx(32.7, abs=1e-10)


@pytest.mark.parametrize("format_version", [3, 4])
def test_material_round_trip_preserves_reference_and_all_record_metadata(tmp_path, format_version):
    phase = reference_phase()
    before = deepcopy(phase.params["eos_records"])
    phase.compute_d(32.7, 300.)
    assert phase.params["v"] == pytest.approx(375.04)
    assert phase.params["p0"] == 32.7
    assert phase.params["k0p0"] == 4.
    output = tmp_path / "reference.eosmat"
    eos.save_material_file(str(output), eos.material_from_jcpds(phase), format_version=format_version)
    restored = eos.load_material_file(str(output))
    assert restored.eos_records == before
    index = phase.params["eos_current_index"]
    loaded = eos.build_jcpds(restored, record_index=index, origin="file")
    loaded.compute_d(32.7, 300.)
    assert loaded.params["p0"] == 32.7
    assert loaded.params["v"] == pytest.approx(375.04)


def test_custom_reference_edit_survives_project_and_undo(tmp_path):
    model = DioptasModel()
    phase = reference_phase()
    model.phase_model.add_jcpds_object(phase)
    custom = model.phase_model.duplicate_eos_record(0, phase.params["eos_current_index"])
    model.phase_model.set_param(0, "p0", 35.)
    assert phase.params["eos_records"][custom]["eos"]["parameters"]["P0"] == 35.
    assert model.phase_model.set_pressure_temperature(0, 35., 300.)
    assert phase.params["v"] == pytest.approx(375.04)
    path = tmp_path / "reference.dio"
    model.save(str(path))
    restored = DioptasModel()
    restored.load(str(path))
    loaded = restored.phase_model.phases[0]
    assert loaded.params["p0"] == 35.
    assert loaded.params["v"] == pytest.approx(375.04)
    restored.history.reset()
    restored.phase_model.set_param(0, "p0", 36.)
    assert loaded.params["v"] != pytest.approx(375.04)
    restored.history.undo()
    loaded = restored.phase_model.phases[0]
    assert loaded.params["p0"] == 35.
    assert loaded.params["eos_records"][custom]["eos"]["parameters"]["P0"] == 35.
    restored.history.redo()
    assert restored.phase_model.phases[0].params["p0"] == 36.


def test_old_snapshot_restores_scalar_reference_pressure_from_record():
    phase = reference_phase()
    state = dataclasses.asdict(phase.state)
    state.pop("p0")
    loaded = CrystalState(**state)
    assert loaded.p0 == 32.7


def test_bundled_reference_cannot_be_edited_and_legacy_export_cannot_lose_it(tmp_path):
    phase = reference_phase()
    model = PhaseModel()
    model.add_jcpds_object(phase)
    with pytest.raises(PermissionError, match="read-only"):
        model.set_param(0, "p0", 0.)
    output = tmp_path / "reference.jcpds"
    output.write_text("Existing file must be preserved")
    with pytest.raises(ValueError, match="reference pressure.*eosmat"):
        phase.save_file(str(output))
    assert output.read_text() == "Existing file must be preserved"
