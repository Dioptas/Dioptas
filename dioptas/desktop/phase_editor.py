# SPDX-License-Identifier: MIT
"""Phase editor metadata and edits using the same model entry points as Qt.

No Qt imports. Metadata reflects the installed Peritheos constructors; defaults
are displayed as defaults, never silently written into a loaded source record.
"""
from copy import deepcopy
from functools import lru_cache
import inspect

from .thermal_field_labels import thermal_field_display

from dioptas.model.util.eos_phase import (
    RT_EOS_TYPES, THERMAL_EOS_TYPES, NON_MOLAR_THERMAL_TYPES,
    THERMAL_CONFIGURATION_CHOICES, eos_parameter_names,
    thermal_parameter_signature, thermal_parameter_defaults,
    thermal_compatibility_error, THERMAL_MODEL_IDENTIFIERS,
)

EOS_FIELDS = {
    'K0': ('k0', 'K₀', 'GPa', 0, 1e6),
    'K0_prime': ('k0p0', 'K₀′', '', -100, 100),
    'K0_double_prime': ('k0pp0', 'K₀″', 'GPa⁻¹', -100, 100),
    'P0': ('p0', 'P ref', 'GPa', -1e6, 1e6),
    'n': ('n', 'n', 'atoms/formula', 1e-9, 1e6),
    'Z': ('z', 'Z electrons', 'e/formula', 1e-9, 1e6),
    'Zc': ('zc', 'Z cell', 'formula/cell', 1, 1e6),
}
LEGACY_FIELDS = {
    'alpha_t0': ('α(T₀)', 'K⁻¹', -1, 1),
    'd_alpha_dt': ('dα/dT', 'K⁻²', -1, 1),
    'dk0dt': ('dK₀/dT', 'GPa/K', -100, 100),
    'dk0pdt': ('dK₀′/dT', 'K⁻¹', -100, 100),
}
LATTICE_KEYS = {
    'CUBIC': ['a0'], 'TETRAGONAL': ['a0', 'c0'],
    'HEXAGONAL': ['a0', 'c0'], 'TRIGONAL': ['a0', 'c0'],
    'RHOMBOHEDRAL': ['a0', 'alpha0'],
    'ORTHORHOMBIC': ['a0', 'b0', 'c0'],
    'MONOCLINIC': ['a0', 'b0', 'c0', 'beta0'],
    'TRICLINIC': ['a0', 'b0', 'c0', 'alpha0', 'beta0', 'gamma0'],
}


@lru_cache(maxsize=1)
def space_groups():
    from phasesmith.io.space_groups import space_group_by_number
    return [dict(number=n, symbol=space_group_by_number(n).hm_symbol)
            for n in range(1, 231)]


def scalar_fields(params):
    try:
        names = eos_parameter_names(params['eos_type'])
    except ValueError:
        # Other published equation types are inspectable, but not editable here.
        names = [k for k in EOS_FIELDS if k in
                 ((params.get('eos_records') or [{}])[params.get('eos_current_index') or 0]
                  .get('eos', {}).get('parameters', {}))]
    if params['eos_type'] == 'Holzapfel' or (params['thermal_type'] and params['thermal_type'] not in NON_MOLAR_THERMAL_TYPES):
        names = list(dict.fromkeys([*names, 'n', 'Zc']))
    return [dict(key=key, label=label, unit=unit, value=params.get(key),
                 min=low, max=high, integer=key == 'zc')
            for name in names if name in EOS_FIELDS
            for key, label, unit, low, high in [EOS_FIELDS[name]]]


def thermal_fields(params):
    kind = params['thermal_type']
    if not kind:
        return [dict(key=key, label=label, unit=unit, value=params[key],
                     min=low, max=high, required=True)
                for key, (label, unit, low, high) in LEGACY_FIELDS.items()]
    if kind not in THERMAL_EOS_TYPES:
        return []
    values = params.get('thermal_parameters') or {}
    fallback = dict(Tr=params.get('t_ref'), theta0=params.get('theta_t0'),
                    gamma0=params.get('gamma_t0'), q=params.get('q_t0')) if not values else {}
    fields = []
    for name, parameter in thermal_parameter_signature(kind).items():
        if name == 'n':  # shown once, with material normalization data
            continue
        required = parameter.default is inspect.Parameter.empty
        default = None if required else parameter.default
        value = values.get(name, fallback.get(name, default))
        label, unit, description = thermal_field_display(kind, name)
        fields.append(dict(key=name, label=label, description=description,
            unit=unit, value=value, required=required, default=default,
            choices=list(THERMAL_CONFIGURATION_CHOICES.get(name, ())),
            isDefault=name not in values and name not in fallback))
    return fields


def editor_metadata(model, index):
    phase = model.phases[index]
    params = phase.params
    document = params.get('material_document') or {}
    from dioptas.model.eos.structure_composition import assess_structure_composition
    composition = assess_structure_composition(document)
    source = document.get('source') or {}
    from .phase_sites import site_labels, element_choices
    group_number = document.get('space_group_number')
    if document.get('space_group'):
        from dioptas.model.util.phasesmith import _space_group_info
        group_number = _space_group_info(document['space_group'], group_number).number
    thermal_kind = params['thermal_type'] or ('alphakt' if any(
        params[k] for k in LEGACY_FIELDS) else 'none')
    return dict(
        uid=phase_editor_uid(phase),
        copiedFrom=(source.get('copied_from') or {}).get('phase_name') or '',
        materialName=document.get('name') or phase._name,
        canSaveCurrent=bool(model.is_material_editable(index) and phase._filename and phase._filename.lower().endswith('.eosmat')),
        name=phase.name, pressure=params['pressure'], temperature=params['temperature'],
        coldPressure=bool(model.params.dac_thermal_pressure_enabled),
        modified=bool(params.get('modified') or params.get('eos_records_modified')),
        origin=params.get('material_origin') or 'legacy',
        recordOrigin=model.eos_record_origin(index),
        recordLabel=(params['eos_records'][params['eos_current_index']].get('label') or '') if params['eos_records'] else '',
        defaultReference=params.get('eos_default_index', 0),
        eosFields=scalar_fields(params), thermalFields=thermal_fields(params),
        materialFields=[dict(key=key, label=label, unit=unit, value=params.get(key),
            min=low, max=high, integer=key == 'zc')
            for key, label, unit, low, high in (EOS_FIELDS[name] for name in ('n', 'Z', 'Zc'))
            if key not in {f['key'] for f in scalar_fields(params)}],
        recordData=deepcopy(params['eos_records'][params['eos_current_index']]) if params['eos_records'] else None,
        thermalSelection=thermal_kind,
        eosOptions=[dict(value=kind, error=thermal_compatibility_error(
            kind, params['thermal_type'], params.get('thermal_parameters'))) for kind in RT_EOS_TYPES],
        thermalOptions=[dict(value=kind, error=thermal_compatibility_error(
            params['eos_type'], '' if kind in ('none', 'alphakt') else kind))
            for kind in ('none', 'alphakt', *THERMAL_EOS_TYPES)],
        structure=dict(spaceGroup=document.get('space_group') or '',
            spaceGroupNumber=group_number,
            siteWyckoff=site_labels(document), elements=element_choices(),
            groups=space_groups(), sites=deepcopy(document.get('atom_sites') or []),
            formula=document.get('formula') or '', storedZ=params.get('zc'),
            calculatedZ=composition.z, compositionStatus=composition.status,
            compositionDetail=composition.details(),
            modified=bool(source.get('structure_modified')),
            assumption=(source.get('assumed_structure') or {}).get('note') or ''),
    )


def apply_editor_edit(workflow, model, index, operation, changes):
    """Called inside PhaseWorkflow's complete-phase rollback boundary."""
    from .integration import finite
    phase = model.phases[index]
    params = phase.params
    wavelength = workflow.configuration.calibration_model.wavelength * 1e10
    if operation in {'editor_parameter', 'editor_eos_type', 'editor_thermal_type',
                     'editor_thermal_parameter', 'editor_record', 'editor_ranges'}:
        if not model.is_material_editable(index):
            raise PermissionError('Bundled database materials are read-only. Choose Edit a copy before changing EoS records.')
    if operation == 'editor_name':
        model._require_editable_material(index)
        name = str(changes['value']).strip()
        if not name or len(name) > 250 or any(ord(c) < 32 for c in name):
            raise ValueError('A material name needs 1–250 printable characters.')
        document = deepcopy(params.get('material_document') or {})
        if not document:
            from dioptas.model import eos
            document = eos.material_from_jcpds(phase).to_dict()
            if not params.get('chemistry'):
                document['formula'] = ''  # A display/file name is not a declared chemical formula.
        document['name'] = name
        phase._name = name
        params['material_document'] = document
        params['modified'] = True
        model.phase_changed.emit(index)
    elif operation == 'editor_ratio':
        key = changes['parameter']
        allowed = {'a/b': ('a0', 'b0'), 'c/a': ('c0', 'a0'), 'c/b': ('c0', 'b0')}
        if key not in allowed:
            raise ValueError('Unknown lattice ratio.')
        if key == 'a/b' and params['symmetry'].upper() not in ('ORTHORHOMBIC', 'MONOCLINIC', 'TRICLINIC'):
            raise ValueError('This ratio is fixed by lattice symmetry.')
        if key != 'a/b' and 'c0' not in LATTICE_KEYS[params['symmetry'].upper()]:
            raise ValueError('This ratio is fixed by lattice symmetry.')
        target, reference = allowed[key]
        value = finite(changes['value'], 'Lattice ratio', 1e-9, 1e9) * params[reference]
        model.set_param(index, target, finite(value, target, 1e-6, 99999))
    elif operation == 'editor_parameter':
        key = changes['parameter']
        fields = {f['key']: f for f in scalar_fields(params)}
        fields.update({key: dict(key=key, label=label, min=low, max=high, integer=key == 'zc')
            for key, label, unit, low, high in (EOS_FIELDS[name] for name in ('n', 'Z', 'Zc'))})
        if not params['thermal_type']:
            fields.update({f['key']: f for f in thermal_fields(params)})
        if key not in fields:
            raise ValueError('Parameter is not part of the selected model.')
        field = fields[key]
        value = finite(changes['value'], field['label'], field['min'], field['max'], field.get('integer', False))
        model.set_param(index, key, value)
    elif operation == 'editor_eos_type':
        kind = changes['value']
        if kind not in RT_EOS_TYPES:
            raise ValueError('Unsupported editable equation of state.')
        model.set_eos_type(index, kind)
    elif operation == 'editor_thermal_type':
        kind = changes['value']
        if kind in ('none', 'alphakt'):
            model.set_thermal_type(index, '')
            if kind == 'none':
                for key in LEGACY_FIELDS:
                    model.set_param(index, key, 0.)
        elif kind in THERMAL_EOS_TYPES:
            defaults = thermal_parameter_defaults(kind, {'V0': params['v0'], 'K0': params['k0']},
                n=params.get('n'), formula_units_per_cell=params.get('zc'), temperature_ref=params.get('t_ref'))
            if kind not in NON_MOLAR_THERMAL_TYPES:
                if params.get('n') is None:
                    params['n'] = defaults.get('n', 1.)
                if not params.get('zc'):
                    params['zc'] = 1
            # Nullable constructor defaults are represented by absence in EOSMAT.
            # Writing a literal null is rejected by its interchange schema.
            defaults = {key: value for key, value in defaults.items() if value is not None}
            model.set_thermal_type(index, kind, parameters=defaults)
            # AlphaKT without an explicit model marker is the older, different
            # constant-coefficient correction. Retain the selected constructor
            # on v2 records as well as canonical ones when references change.
            current = params['eos_current_index']
            if kind == 'AlphaKT' and params['eos_records'] and not params['eos_records'][current].get('thermal', {}).get('model'):
                model.update_eos_record(index, current, live_record(model, index, params['eos_records'][current]))
        else:
            raise ValueError('Unsupported thermal model.')
    elif operation == 'editor_thermal_parameter':
        kind = params['thermal_type']
        key = changes['parameter']
        if kind not in THERMAL_EOS_TYPES or key not in thermal_parameter_signature(kind) or key == 'n':
            raise ValueError('Unknown thermal parameter.')
        parameter = thermal_parameter_signature(kind)[key]
        value = changes['value']
        values = dict(params.get('thermal_parameters') or {})
        if value is None:
            if parameter.default is inspect.Parameter.empty:
                raise ValueError('This thermal coefficient is required.')
            values.pop(key, None)
        elif key in THERMAL_CONFIGURATION_CHOICES:
            if value not in THERMAL_CONFIGURATION_CHOICES[key]:
                raise ValueError('Unknown thermal configuration.')
            values[key] = value
        else:
            values[key] = finite(value, key, -1e30, 1e30)
        # Keep Qt's familiar scalar aliases and constructor state aligned.
        alias = {'Tr': 't_ref', 'theta0': 'theta_t0', 'gamma0': 'gamma_t0', 'q': 'q_t0'}.get(key)
        if alias and value is not None:
            params[alias] = values[key]
        model.set_param(index, 'thermal_parameters', values)
    elif operation == 'editor_ranges':
        current = params['eos_current_index']
        model._require_editable_eos_record(index, current)
        if not params['eos_records']:
            raise ValueError('Add an EoS record before setting its ranges.')
        ranges = changes['ranges']
        definitions = {
            'experimental_pressure_range_gpa': ('Experimental pressure', -1e9),
            'experimental_temperature_range_k': ('Experimental temperature', 0),
            'pressure_gpa': ('Validity pressure', -1e9),
            'temperature_k': ('Validity temperature', 0),
        }
        if not isinstance(ranges, dict) or set(ranges) != set(definitions):
            raise ValueError('Supply the four experimental and validity ranges.')
        record = live_record(model, index, params['eos_records'][current])
        validity = deepcopy(record.get('validity') or {})
        changed_validity = False
        for key, (label, minimum) in definitions.items():
            values = ranges[key]
            if values is not None:
                if not isinstance(values, list) or len(values) != 2:
                    raise ValueError(f'{label} requires both a minimum and maximum, or neither.')
                values = [finite(value, label, minimum, 1e9) for value in values]
                if values[0] > values[1]:
                    raise ValueError(f'{label} minimum must not exceed its maximum.')
            target = record if key.startswith('experimental_') else validity
            changed = target.get(key) != values
            if changed and target is validity:
                changed_validity = True
            if key == 'experimental_pressure_range_gpa' and changed:
                record.pop('pressure_range_status', None)
            if values is None:
                target.pop(key, None)
            else:
                target[key] = values
        if changed_validity:
            note = 'User-edited validity limits; retained source notes refer to the original record.'
            notes = list(validity.get('notes') or [])
            if note not in notes:
                notes.insert(0, note)
            validity['notes'] = notes
        if validity:
            record['validity'] = validity
        model.update_eos_record(index, current, record)
    elif operation == 'editor_record':
        action = changes['action']
        current = params['eos_current_index']
        if action == 'duplicate':
            model.duplicate_eos_record(index, current)
        elif action == 'add':
            record = live_record(model, index)
            record['label'] = 'Custom EoS'
            model.add_eos_record(index, record, origin='custom')
        elif action == 'delete':
            model.delete_eos_record(index, current)
        elif action == 'clear':
            model.clear_eos_records(index)
        elif action == 'default':
            model.set_eos_default(index, current)
        elif action == 'rename':
            label = str(changes['value']).strip()
            if not label or len(label) > 250:
                raise ValueError('A record label requires 1–250 characters.')
            record = live_record(model, index, params['eos_records'][current])
            record['label'] = label
            model.update_eos_record(index, current, record)
        else:
            raise ValueError('Unknown record action.')
    elif operation == 'editor_space_group':
        model.set_space_group(index, str(changes['value']), wavelength_angstrom=wavelength)
    elif operation == 'editor_site':
        sites = (params.get('material_document') or {}).get('atom_sites') or []
        action = changes['action']
        if action == 'add':
            site = changes['site']
            if set(site) - {'element', 'x', 'y', 'z', 'occupancy'}:
                raise ValueError('Unknown atomic-site property.')
            model.add_atom_site(index, **site, wavelength_angstrom=wavelength)
        elif action == 'remove':
            rows = sorted({finite(row, 'Atomic site', 0, len(sites)-1, True) for row in changes['rows']})
            model.remove_atom_sites(index, rows, wavelength_angstrom=wavelength)
        elif action == 'update':
            row = finite(changes['row'], 'Atomic site', 0, len(sites)-1, True)
            model.set_atom_site_parameter(index, row, changes['parameter'], changes['value'], wavelength_angstrom=wavelength)
        else:
            raise ValueError('Unknown atomic-site action.')
    else:
        raise ValueError('Unknown phase editor operation.')


def export_material(model, index):
    """Include live legacy EoS values even before a named record was created."""
    from dioptas.model import eos
    phase = model.phases[index]
    material = eos.material_from_jcpds(phase)
    document = phase.params.get('material_document') or {}
    if 'formula' in document and document['formula'] == '':
        material.formula = ''
    if not material.eos_records and phase.params['k0']:
        record = live_record(model, index)
        record['label'] = 'Session EoS'
        record['reference'] = '\n'.join(phase.params.get('comments') or [])
        material.eos_records = [record]
    return material


def live_record(model, index, base=None):
    record = model.eos_record_from_phase(index, base)
    if model.phases[index].params['thermal_type'] == 'AlphaKT':
        record['thermal']['model'] = THERMAL_MODEL_IDENTIFIERS['AlphaKT']
    return record


def validate_jcpds_export(phase):
    """Do not silently flatten constructor models or provenance to legacy BM3."""
    params = phase.params
    if (params['eos_type'] != 'BM3' or params['thermal_type']
            or params['eos_records']
            or (params.get('material_document') or {}).get('atom_sites')):
        raise ValueError(
            "JCPDS stores legacy BM3 peak tables and cannot retain this phase's "
            'EoS models, material records or atomic structure. Save as .eosmat instead.')


def phase_editor_uid(phase):
    from uuid import uuid4
    if not getattr(phase, '_desktop_editor_uid', None):
        phase._desktop_editor_uid = uuid4().hex
    return phase._desktop_editor_uid


def resolve_editor_index(model, index=None, editor_uid=None):
    from .integration import finite
    if editor_uid is not None:
        for row, phase in enumerate(model.phases):
            if getattr(phase, '_desktop_editor_uid', None) == editor_uid:
                return row
        raise ValueError('This phase is no longer in the session. Select a phase in the main window.')
    return finite(index, 'Phase index', 0, len(model.phases)-1, True)


def copy_phase_for_editing(model, index):
    """Copy the complete live state, with no file roundtrip or diffraction refit."""
    from uuid import uuid4
    source = model.phases[index]
    phase = deepcopy(source)
    names = {p._name for p in model.phases}
    stem = source._name + ' (custom)'
    name = stem
    number = 2
    while name in names:
        name = source._name + f' (custom {number})'
        number += 1
    phase._name = name
    phase._filename = ''
    phase._desktop_editor_uid = uuid4().hex
    p = phase.params
    document = deepcopy(p.get('material_document') or {})
    provenance = dict(material_identifier=document.get('identifier'),
        phase_name=source._name, filename=source._filename,
        scientific_validation=[deepcopy(record.get('scientific_validation')) for record in p['eos_records']])
    document['name'] = name
    if document.get('identifier'):
        document['identifier'] += '_custom_' + phase._desktop_editor_uid[:8]
    document.setdefault('source', {})['copied_from'] = provenance
    p['material_document'] = document
    p['material_origin'] = 'custom'
    records = deepcopy(p['eos_records'])
    for record in records:
        record['scientific_validation'] = dict(status='deferred', note=
            'Editable material copy; source values are retained, subsequent edits are not primary-source validated.')
    p['eos_records'] = records
    p['eos_record_origins'] = ['custom'] * len(records)
    p['modified'] = True
    same_conditions = model.same_conditions
    try:
        model.same_conditions = False
        model.add_jcpds_object(phase)
    finally:
        model.same_conditions = same_conditions
    model.items[-1].filename = ''
    return len(model.phases)-1


def reflection_rows(phase, wavelength):
    import numpy as np
    def angle(spacing):
        return float(np.degrees(2*np.arcsin(wavelength/(2*spacing)))) if spacing > 0 and wavelength <= 2*spacing else None
    return [dict(h=float(r.h), k=float(r.k), l=float(r.l), intensity=float(r.intensity),
        d0=float(r.d0), d=float(r.d), twoTheta0=angle(r.d0), twoTheta=angle(r.d),
        q0=float(2*np.pi/r.d0) if r.d0 > 0 else None,
        q=float(2*np.pi/r.d) if r.d > 0 else None) for r in phase.reflections]
