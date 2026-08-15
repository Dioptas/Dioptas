# SPDX-License-Identifier: MIT

import os
from math import pi

import numpy as np
import pytest
from xypattern import Pattern

from ...model.PhaseModel import PhaseLoadError, PhaseModel
from ...model.util.jcpds import EosCalculationError, jcpds_reflection

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


@pytest.fixture
def phase_model():
    return PhaseModel()


def load_phase(phase_model, filename):
    phase_model.add_jcpds(os.path.join(jcpds_path, filename))


def test_same_conditions_set_pressure(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    load_phase(phase_model, 'pt.jcpds')

    assert phase_model.phases[0].params['pressure'] == 0
    assert phase_model.phases[1].params['pressure'] == 0
    assert phase_model.same_conditions

    phase_model.set_pressure(0, 10)

    assert phase_model.phases[0].params['pressure'] == 10
    assert phase_model.phases[1].params['pressure'] == 10

    phase_model.same_conditions = False
    phase_model.set_pressure(1, 5)
    assert phase_model.phases[0].params['pressure'] == 10
    assert phase_model.phases[1].params['pressure'] == 5


def test_same_conditions_set_temperature(phase_model: PhaseModel):
    load_phase(phase_model, 'pt.jcpds')
    load_phase(phase_model, 'pt.jcpds')

    assert phase_model.phases[0].params['temperature'] == 298
    assert phase_model.phases[1].params['temperature'] == 298
    assert phase_model.same_conditions

    phase_model.set_temperature(1, 2000)

    assert phase_model.phases[0].params['temperature'] == 2000
    assert phase_model.phases[1].params['temperature'] == 2000

    phase_model.same_conditions = False
    phase_model.set_temperature(1, 1500)
    assert phase_model.phases[0].params['temperature'] == 2000
    assert phase_model.phases[1].params['temperature'] == 1500


def test_set_temperature_with_no_thermal_expansion(phase_model):
    load_phase(phase_model, 'ar.jcpds')

    assert phase_model.phases[0].params['temperature'] == 298
    assert not phase_model.phases[0].has_thermal_expansion()

    phase_model.set_temperature(0, 2000)

    # since there is no thermal expansion defined the temperature should stay at ambient
    assert phase_model.phases[0].params['temperature'] == 298


def test_reload_phase(phase_model: PhaseModel):
    load_phase(phase_model, 'ar.jcpds')
    num_refl = len(phase_model.reflections[0])
    phase_model.delete_reflection(0, 0)
    phase_model.delete_reflection(0, 0)
    phase_model.set_pressure(0, 5)
    old_a0 = phase_model.phases[0].params['a0']
    phase_model.set_param(0, 'a0', 5)

    phase_model.reload(0)

    assert len(phase_model.reflections[0]) == num_refl
    assert phase_model.phases[0].params['a0'] == old_a0
    assert phase_model.phases[0].params['pressure'] == 5


def test_reload_cif_phase_from_source(phase_model: PhaseModel):
    filename = os.path.join(data_path, 'cif', 'hcp.cif')
    phase_model.add_cif(filename, wavelength_angstrom=0.31)
    original_a0 = phase_model.phases[0].params['a0']
    original_name = phase_model.phases[0].name
    phase_model.set_pressure(0, 5)
    phase_model.set_param(0, 'a0', original_a0 + 1)

    assert phase_model.can_reload(0)
    phase_model.reload(0)

    assert phase_model.phases[0].params['a0'] == pytest.approx(original_a0)
    assert phase_model.phases[0].params['pressure'] == 5
    assert phase_model.phases[0].name == original_name
    assert phase_model.phases[0].params['material_origin'] == 'cif'


def test_reload_eosmat_phase_from_source(phase_model: PhaseModel, tmp_path):
    from ...model import eos

    material = eos.Material(
        name='Test mineral', formula='MgO', symmetry='CUBIC',
        lattice=eos.Lattice(a=4.2, b=4.2, c=4.2),
        peaks=[[1, 0, 0, 4.2, 100]],
        eos_records=[{
            'label': 'Test fit',
            'eos': {'type': 'BM3', 'parameters': {
                'V0': 74.088, 'K0': 160.0, 'K0_prime': 4.0,
            }},
        }],
    )
    filename = tmp_path / 'test.eosmat'
    eos.save_material_file(str(filename), material)
    phase = eos.build_jcpds(material, origin='file')
    phase._filename = str(filename)
    phase_model.add_jcpds_object(phase, filename=str(filename))
    phase_model.set_param(0, 'k0', 999.0)

    phase_model.reload(0)

    assert phase_model.phases[0].params['k0'] == pytest.approx(160.0)
    assert phase_model.phases[0].name == 'Test mineral (MgO)'
    assert phase_model.phases[0].params['material_origin'] == 'file'


# --- PhaseLoadError ---

def test_phase_load_error_init():
    err = PhaseLoadError("bad_file.jcpds")
    assert err.filename == "bad_file.jcpds"


def test_phase_load_error_repr():
    err = PhaseLoadError("bad_file.jcpds")
    assert "bad_file.jcpds" in repr(err)


def test_add_jcpds_invalid_file_raises(phase_model):
    # Use a file that exists but is not a valid jcpds (e.g., a cif file)
    with pytest.raises(PhaseLoadError):
        phase_model.add_jcpds(os.path.join(data_path, "test.cif"))


# --- add_cif ---

def test_add_cif(phase_model):
    cif_path = os.path.join(data_path, 'test.cif')
    phase_model.add_cif(cif_path)
    assert len(phase_model.phases) == 1
    assert len(phase_model.reflections) == 1
    assert phase_model.phase_files[0] == cif_path
    assert phase_model.phases[0].state.reflection_source["kind"] == "cif"


def test_structure_reflections_grow_with_pattern_coverage(phase_model):
    from ...model import eos

    gold = next(
        material
        for material in eos.load_materials()
        if material.formula == "Au" and material.atom_sites
    )
    phase = eos.build_jcpds(gold)
    phase_model.add_jcpds_object(phase, filename=phase.filename)
    initial_count = len(phase.reflections)

    changed = phase_model.ensure_structure_reflection_coverage(
        2.0 * pi / 21.0,
        0.31,
    )

    assert changed == [0]
    assert len(phase.reflections) > initial_count
    assert phase.state.reflection_q_max == pytest.approx(21.0)
    assert phase_model.ensure_structure_reflection_coverage(
        2.0 * pi / 20.0,
        0.31,
    ) == []


def test_pressure_and_temperature_keep_cached_reflections(phase_model):
    from ...model import eos

    gold = next(
        material
        for material in eos.load_materials()
        if material.formula == "Au" and material.atom_sites
    )
    phase = eos.build_jcpds(
        gold,
        minimum_d_spacing=2.0 * pi / 21.0,
        wavelength_angstrom=0.31,
    )
    phase_model.add_jcpds_object(phase, filename=phase.filename)
    reflection_identity = [
        (reflection.h, reflection.k, reflection.l, reflection.intensity)
        for reflection in phase.reflections
    ]

    phase_model.set_pressure(0, 50.0)
    phase_model.set_temperature(0, 1000.0)

    assert [
        (reflection.h, reflection.k, reflection.l, reflection.intensity)
        for reflection in phase.reflections
    ] == reflection_identity
    assert phase.state.reflection_q_max == pytest.approx(21.0)


def test_add_cif_invalid_file_raises(phase_model):
    # Use a jcpds file as input to trigger a parse error in the CIF converter
    with pytest.raises(Exception):
        phase_model.add_cif(os.path.join(jcpds_path, "ar.jcpds"))


# --- save_phase_as ---

def test_save_phase_as(phase_model, tmp_path):
    load_phase(phase_model, 'ar.jcpds')
    save_path = str(tmp_path / "saved_ar.jcpds")
    phase_model.save_phase_as(0, save_path)
    assert os.path.exists(save_path)


# --- del_phase ---

def test_del_phase(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    load_phase(phase_model, 'pt.jcpds')
    assert len(phase_model.phases) == 2

    phase_model.del_phase(0)
    assert len(phase_model.phases) == 1
    assert len(phase_model.reflections) == 1
    assert len(phase_model.phase_files) == 1
    assert len(phase_model.phase_colors) == 1
    assert len(phase_model.phase_visible) == 1


# --- set_pressure_temperature ---

def test_set_pressure_temperature(phase_model):
    load_phase(phase_model, 'pt.jcpds')
    phase_model.set_pressure_temperature(0, 10.0, 1500.0)
    assert phase_model.phases[0].params['pressure'] == 10.0
    assert phase_model.phases[0].params['temperature'] == 1500.0


def test_failed_condition_change_restores_all_phases(phase_model, monkeypatch):
    """Apply-to-all must not leave phases at a mixture of old/new states."""
    load_phase(phase_model, 'pt.jcpds')
    load_phase(phase_model, 'pt.jcpds')
    old_temperatures = [phase.params['temperature']
                        for phase in phase_model.phases]
    old_d = [[reflection.d for reflection in phase.reflections]
             for phase in phase_model.phases]
    rejected = []
    phase_model.condition_rejected.connect(
        lambda *args: rejected.append(args))

    def fail_after_mutating(*args, **kwargs):
        phase_model.phases[1].params['temperature'] = 5000.0
        raise EosCalculationError("outside invertible range")

    monkeypatch.setattr(phase_model.phases[1], 'compute_d',
                        fail_after_mutating)

    assert not phase_model.set_temperature(0, 5000.0)
    assert [phase.params['temperature'] for phase in phase_model.phases] \
        == old_temperatures
    assert [[reflection.d for reflection in phase.reflections]
            for phase in phase_model.phases] == old_d
    assert rejected and rejected[0][:2] == (0, "temperature")


# --- set_color ---

def test_set_color(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    new_color = (255, 0, 0)
    phase_model.set_color(0, new_color)
    assert phase_model.phase_colors[0] == new_color


# --- set_phase_visible ---

def test_set_phase_visible(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    assert phase_model.phase_visible[0] is True
    phase_model.set_phase_visible(0, False)
    assert phase_model.phase_visible[0] is False


# --- get_phase_line_positions ---

def test_get_phase_line_positions_d_A(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    positions = phase_model.get_phase_line_positions(0, 'd_A', 0.31e-10)
    # d_A unit should return the d-spacings directly
    assert len(positions) > 0
    np.testing.assert_array_equal(positions, phase_model.reflections[0][:, 0])


def test_get_phase_line_positions_2th_deg(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, '2th_deg', wavelength)
    assert len(positions) > 0
    # 2th values should be positive angles
    assert np.all(positions > 0)


def test_get_phase_line_positions_q(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, 'q_A^-1', wavelength)
    assert len(positions) > 0
    assert np.all(positions > 0)


# --- get_phase_line_intensities ---

def test_get_phase_line_intensities_with_pattern(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, '2th_deg', wavelength)

    x = np.linspace(0, 30, 1000)
    y = np.ones_like(x) * 100
    pattern = Pattern(x, y)

    intensities, baseline = phase_model.get_phase_line_intensities(
        0, positions, pattern, x_range=(0, 30), y_range=(0, 120)
    )
    assert len(intensities) == len(positions)
    assert baseline == 0


def test_get_phase_line_intensities_empty_pattern(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, '2th_deg', wavelength)

    pattern = Pattern(np.array([]), np.array([]))
    intensities, baseline = phase_model.get_phase_line_intensities(
        0, positions, pattern, x_range=(0, 30), y_range=(0, 120)
    )
    assert len(intensities) == len(positions)


def test_get_phase_line_intensities_no_lines_in_range(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, '2th_deg', wavelength)

    # Pattern data covers the x_range, but no phase lines fall in this range
    x = np.linspace(9000, 9999, 1000)
    y = np.ones_like(x) * 100
    pattern = Pattern(x, y)

    intensities, baseline = phase_model.get_phase_line_intensities(
        0, positions, pattern, x_range=(9000, 9999), y_range=(0, 120)
    )
    # scale_factor defaults to 1 when no lines in range
    assert len(intensities) == len(positions)


def test_get_phase_line_intensities_no_y_in_range(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, '2th_deg', wavelength)

    # Pattern x data doesn't overlap with x_range so y_in_range is empty
    x = np.linspace(100, 200, 1000)
    y = np.ones_like(x) * 100
    pattern = Pattern(x, y)

    result = phase_model.get_phase_line_intensities(
        0, positions, pattern, x_range=(0, 30), y_range=(0, 120)
    )
    assert result == ([], 0)


def test_get_phase_line_intensities_negative_scale(phase_model):
    """Test the case where scale_factor <= 0, which gets clamped to 0.01."""
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10
    positions = phase_model.get_phase_line_positions(0, '2th_deg', wavelength)

    # Create a pattern where max_pattern_intensity < baseline (y_range[0])
    x = np.linspace(0, 30, 1000)
    y = np.ones_like(x) * 5  # low pattern intensity
    pattern = Pattern(x, y)

    # y_range[0] (baseline) > max_pattern_intensity -> negative scale_factor
    intensities, baseline = phase_model.get_phase_line_intensities(
        0, positions, pattern, x_range=(0, 30), y_range=(10, 120)
    )
    assert baseline == 10
    assert len(intensities) == len(positions)


# --- get_rescaled_reflections ---

def test_get_rescaled_reflections(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    wavelength = 0.31e-10

    x = np.linspace(0, 30, 1000)
    y = np.ones_like(x) * 100
    pattern = Pattern(x, y)

    positions, intensities, baseline = phase_model.get_rescaled_reflections(
        0, pattern, x_range=(0, 30), y_range=(0, 120), wavelength=wavelength, unit='2th_deg'
    )
    assert len(positions) > 0
    assert len(intensities) == len(positions)


# --- add_reflection ---

def test_add_reflection(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    num_before = len(phase_model.phases[0].reflections)
    phase_model.add_reflection(0)
    assert len(phase_model.phases[0].reflections) == num_before + 1


# --- delete_multiple_reflections ---

def test_delete_multiple_reflections(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    num_before = len(phase_model.phases[0].reflections)
    phase_model.delete_multiple_reflections(0, [0, 1])
    assert len(phase_model.phases[0].reflections) == num_before - 2


# --- update_reflection ---

def test_update_reflection(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    new_refl = jcpds_reflection(h=5, k=5, l=5, intensity=100, d=1.5)
    phase_model.update_reflection(0, 0, new_refl)
    assert phase_model.phases[0].reflections[0].h == 5
    assert phase_model.phases[0].reflections[0].k == 5
    assert phase_model.phases[0].reflections[0].l == 5
    assert phase_model.phases[0].params['modified'] is True


# --- reset ---

def test_reset(phase_model):
    load_phase(phase_model, 'ar.jcpds')
    load_phase(phase_model, 'pt.jcpds')
    assert len(phase_model.phases) == 2

    phase_model.reset()
    assert len(phase_model.phases) == 0
    assert len(phase_model.reflections) == 0
    assert len(phase_model.phase_files) == 0
