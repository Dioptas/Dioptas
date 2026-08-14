# SPDX-License-Identifier: MIT
import os

import pytest
from pytest import approx

from ...model.util.cif import CifConverter

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
cif_path = os.path.join(data_path, 'cif')


def test_read_cif_without_cell_volume():
    converter = CifConverter(0.31, min_d_spacing=1)
    phase = converter.convert_cif_to_jcpds(
        os.path.join(cif_path, 'ICSD_triclinic_without_cell_volume.cif')
    )
    assert phase.params['v0'] == approx(465.74, 1e-2)


def test_loading_cif_phase_and_calculate_jcpds():
    cif_converter = CifConverter(0.31)
    jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'fcc.cif'))
    assert jcpds_phase.name == 'Ho N (HoN)'
    assert jcpds_phase.reflections[0].intensity == 100
    assert jcpds_phase.reflections[0].d0 == approx(2.814, 1e-5)
    assert jcpds_phase.reflections[1].d0 == approx(2.437, 1e-5)


def test_loading_cif_phase_with_occupancies_specified():
    cif_converter = CifConverter(0.31)
    jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'magnesiowustite.cif'))
    assert jcpds_phase.reflections[0].intensity == approx(27.53, 0.2)
    assert jcpds_phase.reflections[1].intensity == 100
    assert jcpds_phase.reflections[2].intensity == approx(65.02, 0.2)


def test_cif_is_normalized_to_lossless_material():
    converter = CifConverter(0.31)
    filename = os.path.join(cif_path, 'magnesiowustite.cif')

    material = converter.convert_cif_to_material(filename)
    phase = converter.convert_cif_to_jcpds(filename)

    assert material.formula == 'Fe0.3Mg0.7O'
    assert material.formula_units_per_cell == 4
    assert material.space_group == 'F m -3 m'
    assert material.space_group_number == 225
    assert len(material.atom_sites) == 3
    assert material.atom_sites[0]['occupancy'] == pytest.approx(0.7)
    assert material.source['kind'] == 'cif'
    assert 'data_181216-ICSD' in material.source['text']
    assert phase.params['material_origin'] == 'cif'
    assert phase.params['material_document']['formula'] == material.formula
    assert phase.params['zc'] == 4


def test_cif_material_survives_eosmat_round_trip(tmp_path):
    from ...model import eos

    converter = CifConverter(0.31)
    filename = os.path.join(cif_path, 'amcsd.cif')
    phase = converter.convert_cif_to_jcpds(filename)
    output = str(tmp_path / 'CaF2.eosmat')

    eos.save_material_file(output, eos.material_from_jcpds(phase))
    loaded = eos.load_material_file(output)

    assert loaded.formula == 'CaF2'
    assert loaded.space_group == 'F m -3 m'
    assert loaded.source['kind'] == 'cif'
    assert loaded.source['text'] == open(filename, encoding='utf-8').read()


def test_reading_american_mineralogist_db_cif():
    with open(os.path.join(cif_path, 'amcsd.cif'), encoding='utf-8') as stream:
        assert "'F m -3 m'" in stream.read()
    cif_converter = CifConverter(0.31)
    jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'amcsd.cif'))
    assert jcpds_phase.params['a0'] == 5.4631
    assert jcpds_phase.reflections[0].intensity == approx(73.48, 0.5)
    assert jcpds_phase.reflections[1].intensity == 100
    assert jcpds_phase.reflections[2].intensity == approx(33.6, 0.5)
    assert jcpds_phase.reflections[3].intensity == approx(14.65, 0.5)


def test_read_cif_with_errors_in_atomic_positions():
    cif_converter = CifConverter(0.31, min_d_spacing=1.5, min_intensity=10)
    jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'apatite.cif'))
    assert jcpds_phase.params['a0'] == 9.628


def test_read_cif_from_shelx():
    cif_converter = CifConverter(0.31)
    jcpds_phase = cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'Fe2O3_shelx.cif'))
    assert jcpds_phase.params['a0'] == 6.524
    assert jcpds_phase.params['b0'] == 4.702
    assert jcpds_phase.params['c0'] == 4.603


def test_convert_cif_with_triclinic_geometry():
    cif_converter = CifConverter(0.31, min_d_spacing=1, min_intensity=5)
    cif_converter.convert_cif_to_jcpds(os.path.join(cif_path, 'ICSD_triclinic.cif'))


@pytest.mark.parametrize(
    "cif_filename",
    sorted(filename for filename in os.listdir(cif_path) if filename.endswith(".cif")),
)
def test_phasesmith_reads_every_cif_fixture(cif_filename):
    converter = CifConverter(0.31, min_d_spacing=1.5, min_intensity=10)
    phase = converter.convert_cif_to_jcpds(os.path.join(cif_path, cif_filename))
    assert phase.reflections
