"""Crystallographic Z requires the same occupancy-weighted ratio for each element."""

from copy import deepcopy

import pytest
from peritheos import get_material_document

from ...model import eos
from ...model.PhaseModel import PhaseModel
from ...model.eos.structure_composition import assess_structure_composition, formula_composition


def site(element, x=0., y=0., z=0., occupancy=1.):
    return dict(element=element, x=x, y=y, z=z, occupancy=occupancy)


def document(formula, sites, group='P1'):
    return dict(formula=formula, atom_sites=sites, space_group=group)


@pytest.mark.parametrize(('formula', 'expected'), [
    ('CaMgSi2O6', {'Ca': 1., 'Mg': 1., 'Si': 2., 'O': 6.}),
    ('Ca3(PO4)2', {'Ca': 3., 'P': 2., 'O': 8.}),
    ('K4[Fe(CN)6]', {'K': 4., 'Fe': 1., 'C': 6., 'N': 6.}),
    ('Mg₀.₂Fe₀.₈O', {'Mg': .2, 'Fe': .8, 'O': 1.}),
    ('CuSO4·5H2O', {'Cu': 1., 'S': 1., 'O': 9., 'H': 10.}),
    ('Ca1 Mg1 Si2 O6', {'Ca': 1., 'Mg': 1., 'Si': 2., 'O': 6.}),
    ('CH3COOH', {'C': 2., 'H': 4., 'O': 2.}),
    ('D2O', {'H': 2., 'O': 1.}),
    ('Fe0MgO', {'Mg': 1., 'O': 1.}),
])
def test_fixed_formula_syntax(formula, expected):
    assert formula_composition(formula) == expected


@pytest.mark.parametrize('formula', ['', None, 'Mg(1-x)FexO', 'Fe3+', 'Fe³⁺', 'XxO',
                                     'Ca(OH', 'Ca(OH]2', 'Ca()2', 'CaO)', '[57Fe]O',
                                     'H2O·', 'H2O··H2O', 'Fe0', '0H2O'])
def test_unsupported_formula_is_not_partly_parsed(formula):
    with pytest.raises(ValueError):
        formula_composition(formula)


@pytest.mark.parametrize(('identifier', 'z'), [('gold', 4.), ('diamond', 8.),
                                             ('diopside', 4.)])
def test_published_structures_and_special_positions(identifier, z):
    source = get_material_document(identifier)
    before = deepcopy(source)
    result = assess_structure_composition(source)
    assert result.status == 'consistent', result.details()
    assert result.z == pytest.approx(z)
    assert source == before  # This diagnostic cannot rewrite provenance or EoS normalization.
    if identifier == 'diopside':
        assert result.multiplicities == (4, 4, 8, 8, 8, 8)
        assert result.cell_counts == dict(Mg=4., Ca=4., Si=8., O=24.)


def test_current_quartz_inputs_are_checked_against_computed_multiplicity():
    # The current coordinate/setting combination expands Si to six positions,
    # despite the source's 3a label. Report the discrepancy; never force Z = 3.
    source = get_material_document('alpha_quartz')
    result = assess_structure_composition(source)
    assert result.cell_counts == dict(Si=6., O=6.)
    assert result.status == 'mismatch'
    assert result.z is None
    assert source['formula_units_per_cell'] == 3


def test_general_positions_use_operations_not_source_wyckoff_labels():
    doc = document('Au', [site('Au', .123, .234, .345)], 'Fm-3m')
    doc['atom_sites'][0]['wyckoff'] = '4a'  # stale metadata must not determine the answer
    result = assess_structure_composition(doc)
    assert result.z == 192.
    assert result.multiplicities == (192,)


def test_mixed_occupancies_at_symmetry_equivalent_positions_are_additive():
    result = assess_structure_composition(document('Mg0.25Fe0.75O', [
        site('Mg', occupancy=.25), site('Fe', 1., occupancy=.75), site('O', .5, .5, .5),
    ], 'Fm-3m'))
    assert result.z == 4.
    assert result.cell_counts == dict(Mg=1., Fe=3., O=4.)


def test_fractional_z_is_not_rounded_to_an_integer():
    result = assess_structure_composition(document('Fe2O3', [
        site('Fe', occupancy=.4), site('O', .5, occupancy=.6),
    ]))
    assert result.z == pytest.approx(.2)


def test_formula_normalization_changes_z():
    sites = [site('Fe', occupancy=.4), site('O', .5, occupancy=.6)]
    assert assess_structure_composition(document('Fe4O6', sites)).z == pytest.approx(.1)


@pytest.mark.parametrize('sites', [
    [site('Mg'), site('O', .5, occupancy=.5)],  # same elements, incompatible ratios
    [site('Fe'), site('O', .5)],               # extra and missing elements
    [site('Mg')],                             # missing oxygen
])
def test_atom_total_alone_cannot_assign_a_z(sites):
    result = assess_structure_composition(document('MgO', sites))
    assert result.status == 'mismatch'
    assert result.z is None
    assert result.ratios


def test_zero_occupancy_does_not_introduce_an_extra_element():
    result = assess_structure_composition(document('Au', [site('Au'), site('Fe', .5, occupancy=0.)]))
    assert result.z == 1.


def test_isotopes_compare_as_their_element():
    result = assess_structure_composition(document('H2O', [
        site('D'), site('T', .5), site('O', .25),
    ]))
    assert result.z == 1.


@pytest.mark.parametrize('sites', [
    [site('Au'), site('Au', .5, .5, 0.)],  # two full rows describing one F-centred orbit
    [site('Au', occupancy=.6), site('Pt', occupancy=.6)],
])
def test_overoccupied_duplicate_or_mixed_orbits_cannot_assign_z(sites):
    result = assess_structure_composition(document('Au', sites, 'Fm-3m'))
    assert result.z is None
    assert result.status == 'unavailable'
    assert 'total occupancy above one' in result.message


@pytest.mark.parametrize('doc', [
    document('Au', []), document('Au', [site('Au')], ''),
    document('Au', [site('Au', occupancy=-1.)]),
    document('Au', [site('Au', occupancy=float('nan'))]),
    document('Au', [site('Au', occupancy=1.01)]),
    document('Au', [site('Au', occupancy=0.)]),
    document('Au', [site('Au', x=float('inf'))]),
    document('Au', [site('Au')], 'invalid'), document('variable', [site('Au')]),
])
def test_unavailable_inputs_give_an_explanation(doc):
    result = assess_structure_composition(doc)
    assert result.status == 'unavailable'
    assert result.z is None
    assert result.message


def test_formula_rounding_tolerance_does_not_hide_a_composition_change():
    sites = [site('Mg', occupancy=.3333), site('Fe', occupancy=.6667), site('O', .5)]
    result = assess_structure_composition(document('Mg0.333333Fe0.666667O', sites))
    assert result.status == 'consistent'
    sites[0]['occupancy'] = .33
    assert assess_structure_composition(document('Mg0.333333Fe0.666667O', sites)).status == 'mismatch'


def test_structure_edits_recheck_z_without_changing_stored_eos_values(tmp_path):
    model = PhaseModel()
    phase = eos.build_jcpds(eos.Material.from_dict(get_material_document('gold')), origin='file')
    model.add_jcpds_object(phase)
    stored_z = phase.params['zc']
    records = deepcopy(phase.params['eos_records'])
    assert assess_structure_composition(phase.params['material_document']).z == 4.
    model.set_space_group(0, '221')
    assert assess_structure_composition(phase.params['material_document']).z == 1.
    model.set_atom_site_parameter(0, 0, 'occupancy', .5)
    assert assess_structure_composition(phase.params['material_document']).z == .5
    model.set_atom_site_parameter(0, 0, 'element', 'Pt')
    assert assess_structure_composition(phase.params['material_document']).status == 'mismatch'
    assert phase.params['zc'] == stored_z
    assert phase.params['material_document']['formula'] == 'Au'
    assert phase.params['eos_records'] == records
    filename = str(tmp_path / 'edited.eosmat')
    eos.save_material_file(filename, eos.material_from_jcpds(phase))
    loaded = eos.load_material_file(filename).to_dict()
    assert assess_structure_composition(loaded).status == 'mismatch'
    assert loaded['formula_units_per_cell'] == stored_z
