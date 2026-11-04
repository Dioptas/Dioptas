# SPDX-License-Identifier: MIT
"""Qt Phase controls backed by PhaseModel; no Qt widgets or scientific server."""
from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path

import numpy as np

from .phase_database import catalog_payload, database_material, open_documentation

from dioptas.model import eos
from dioptas.model.eos.material import record_is_explicit_candidate
from dioptas.model.util.phasesmith import (
    material_has_diffraction_data, minimum_d_spacing_for_pattern,
)


def reference_details(phase):
    origins = phase.params.get('eos_record_origins') or []
    return [
        {
            'label': label,
            'assessment': eos.record_reproduction(record, origin=origins[i] if i < len(origins) else None)[0],
            'detail': eos.reference_text(record.get('reference')) + ' — ' +
                      (record.get('eos') or {}).get('type', 'BM3') + '\n\n' +
                      eos.record_reproduction(record, origin=origins[i] if i < len(origins) else None)[1],
        }
        for i, (record, label) in enumerate(zip(phase.params['eos_records'],
            [eos.record_label(r) for r in phase.params['eos_records']]))
    ]


def load_error(material, reference):
    if not material_has_diffraction_data(material):
        return 'No crystal structure or reference peak table is available for diffraction phase lines.'
    if material.eos_records:
        if reference is None or not 0 <= reference < len(material.eos_records):
            return material.recommendation_hold or 'Select an EoS record explicitly; no automatic default is recommended.'
        record = material.eos_records[reference]
        status = (record.get('scientific_validation') or {}).get('status')
        if material.format == 'peritheos.material' and status != 'primary_source_validated' and not record_is_explicit_candidate(record):
            return f'This record is {status or "unvalidated"} and is retained as source data only.'
    return ''


class PhaseWorkflow:
    def _phase_calculation_parameters(self):
        wavelength = self.configuration.calibration_model.wavelength * 1e10
        spacing = minimum_d_spacing_for_pattern(
            self._model.pattern.data[0],
            self.configuration.pattern_model.unit or self._model.integration_unit, wavelength)
        return spacing, wavelength

    def _phase_legend_name(self, phase):
        pressure = phase.params['pressure']
        temperature = phase.params['temperature']
        label = ''
        if self._model.phase_model.params.dac_thermal_pressure_enabled:
            label += f'P₀={pressure:.2f} GPa '
        elif pressure != 0:
            label += f'{pressure:.2f} GPa '
        if temperature not in (0, 298, None):
            label += f'{temperature:.2f} K '
        return label + phase.name

    def _phase_state(self):
        model = self._model.phase_model
        from .phase_editor import phase_editor_uid
        return [dict(
            uid=phase_editor_uid(phase),
            name=phase.name, pressure=phase.params['pressure'],
            temperature=phase.params['temperature'],
            thermal=bool(phase.has_thermal_expansion()),
            fileBacked=Path(model.phase_files[i]).is_file(),
            visible=model.phase_visible[i],
            color='#%02x%02x%02x' % tuple(int(v) for v in model.phase_colors[i]),
            references=model.get_eos_reference_labels(i), reference=phase.params['eos_current_index'],
            referenceDetails=reference_details(phase),
        ) for i, phase in enumerate(model.phases)]

    def _integration_phase_files(self, paths=None, path=None):
        if paths is None:
            path = self._path(path, 'phase')
            if path is None:
                return {'cancelled': True}
            paths = [path]
        paths = [self._path(p, 'phase') for p in paths]
        spacing, _ = self._phase_calculation_parameters()
        return {'phaseImport': {'paths': paths, 'minimumDSpacing': spacing}}

    def _phase_load(self, path, minimum_d_spacing=None, intensity_cutoff=0.5):
        from .integration import finite
        model = self._model.phase_model
        spacing, wavelength = self._phase_calculation_parameters()
        if minimum_d_spacing is not None:
            spacing = finite(minimum_d_spacing, 'Minimum d-spacing', 0.01, 100)
        cutoff = finite(intensity_cutoff, 'Intensity cutoff', 0, 100)
        suffix = Path(path).suffix.lower()
        if suffix == '.cif':
            model.add_cif(path, cutoff, spacing, wavelength)
        elif suffix in {'.eosmat', '.json'}:
            obj = eos.build_jcpds(eos.load_material_file(path), minimum_d_spacing=spacing,
                                 wavelength_angstrom=wavelength, origin='file')
            obj._filename = path
            model.add_jcpds_object(obj, filename=path)
        elif suffix == '.jcpds':
            model.add_jcpds(path)
        else:
            raise ValueError('Choose a JCPDS, CIF or EOSMAT phase file.')

    def _integration_phase_catalog(self, query=''):
        return catalog_payload(query, load_error)

    def _integration_phase_documentation(self, material_id, reference, kind):
        return open_documentation(self._phase_material(material_id), reference, kind)

    def _phase_material(self, identifier):
        material = next((m for m in eos.load_materials() if m.identifier == identifier), None)
        if material is None:
            raise ValueError('Unknown database material.')
        return material

    def _integration_phase_list(self, save=False, path=None):
        from .integration import boolean, finite
        save = boolean(save, 'Save phase list')
        model = self._model.phase_model
        path = self._path(path, 'phase_list', save=save)
        if path is None:
            return {'cancelled': True}
        if save:
            if any(not Path(filename).is_file() for filename in model.phase_files):
                raise ValueError('Phase lists reference files on disk. Save a project to retain database or unsaved phases.')
            # Same six columns as the Qt controller. CSV quoting also preserves commas in filenames/names.
            with open(path, 'w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                for i, phase in enumerate(model.phases):
                    writer.writerow([model.phase_files[i], model.phase_visible[i],
                        '#%02x%02x%02x' % tuple(int(v) for v in model.phase_colors[i]),
                        phase.name, phase.params['pressure'], phase.params['temperature']])
            return {'savedPath': path}
        original_items = list(model.items)
        original_counter = model._color_counter
        same = model.same_conditions
        try:
            model.same_conditions = False
            with open(path, newline='', encoding='utf-8-sig') as stream:
                for row in csv.reader(stream):
                    if not row:
                        continue
                    if len(row) != 6:
                        raise ValueError('Phase list needs file, visibility, color, name, pressure and temperature.')
                    filename, visible, color, name, pressure, temperature = row
                    if visible not in {'True', 'False', '1', '0'}:
                        raise ValueError('Phase visibility must be True or False.')
                    source = Path(filename).expanduser()
                    if not source.is_absolute():
                        source = Path(path).parent / source
                    self._phase_load(self._path(str(source), 'phase'))
                    i = len(model.phases) - 1
                    phase = model.phases[i]
                    phase._name = name
                    if not model.set_pressure_temperature(i, finite(pressure, 'Pressure', -9999999, 9999999),
                            finite(temperature, 'Temperature', 0, 9999999)):
                        raise ValueError('Phase model rejected conditions in the phase list.')
                    color = self._integration_color(color)
                    model.set_color(i, tuple(int(color[k:k+2], 16) for k in (1, 3, 5)))
                    model.set_phase_visible(i, visible in {'True', '1'})
        except Exception:
            model.items = original_items
            model._color_counter = original_counter
            raise
        finally:
            model.same_conditions = same
        self._refresh_integration_pattern()
        self._revision += 1
        return self._snapshot()

    def _integration_phase_state(self):
        # Phase edits change table rows and reference lines, never detector pixels.
        return {**self._state(), 'pattern': self._pattern,
                'patternOnly': True, 'phaseOnly': True}

    def _integration_phase_editor(self, index=None, editor_uid=None):
        from .integration import finite
        model = self._model.phase_model
        from .phase_editor import resolve_editor_index
        index = resolve_editor_index(model, index, editor_uid)
        phase = model.phases[index]
        params = phase.params
        wavelength = self.configuration.calibration_model.wavelength * 1e10
        from dioptas.model.util.eos_phase import eos_parameter_names
        try:
            names = eos_parameter_names(params['eos_type'])
        except ValueError:
            names = ['K0', 'K0_prime']
        eos_keys = [key for key, name in [('k0', 'K0'), ('k0p0', 'K0_prime'), ('k0pp0', 'K0_double_prime')]
                    if name in names]
        if not params['thermal_type']:
            eos_keys += ['alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt']
        lattice_keys = {
            'CUBIC': ['a0'], 'TETRAGONAL': ['a0','c0'], 'HEXAGONAL': ['a0','c0'],
            'TRIGONAL': ['a0','c0'], 'RHOMBOHEDRAL': ['a0','alpha0'],
            'ORTHORHOMBIC': ['a0','b0','c0'], 'MONOCLINIC': ['a0','b0','c0','beta0'],
            'TRICLINIC': ['a0','b0','c0','alpha0','beta0','gamma0'],
        }
        from .phase_editor import editor_metadata, reflection_rows
        return {'phaseRevision': self._revision, 'phaseEditor': dict(
            **editor_metadata(model, index),
            index=index, filename=str(phase._filename),
            editable=model.is_material_editable(index),
            eosEditable=model.is_material_editable(index) and model.is_eos_record_editable(index),
            canReload=model.can_reload(index), symmetry=params['symmetry'].lower(),
            lattice={k: float(params[k]) for k in ('a0', 'b0', 'c0', 'alpha0', 'beta0', 'gamma0', 'v0', 'a', 'b', 'c', 'v')},
            latticeEditable=lattice_keys.get(params['symmetry'].upper(), []),
            eosType=params['eos_type'], thermalType=params['thermal_type'],
            eosParameters={k: float(params[k]) for k in eos_keys},
            references=reference_details(phase), reference=params['eos_current_index'],
            reflections=reflection_rows(phase, wavelength),
        )}

    def _integration_phase_export(self, index=None, material_id=None, path=None, format=None, editor_only=False, editor_uid=None, save_current=False, suggested_name=None, assume_structure=False):
        if editor_uid is not None:
            from .phase_editor import resolve_editor_index
            index = resolve_editor_index(self._model.phase_model, editor_uid=editor_uid)
        if save_current:
            if material_id is not None or index is None:
                raise ValueError('Select an editable material to save.')
            model = self._model.phase_model
            from .integration import finite
            index = finite(index, 'Phase index', 0, len(model.phases)-1, True)
            phase = model.phases[index]
            if not model.is_material_editable(index) or not (phase._filename or '').lower().endswith('.eosmat'):
                raise ValueError('Use Save As to choose an EOSMAT file for this material.')
            path = phase._filename
        if format not in (None, 'txt', 'eosmat'):
            raise ValueError('Unknown phase export format.')
        path = self._path(path, 'phase_reflections' if format == 'txt' else 'phase_export', save=True)
        if path is None:
            return {'cancelled': True}
        suffix = Path(path).suffix.lower()
        if not suffix:
            path += '.txt' if format == 'txt' else '.eosmat'
            suffix = Path(path).suffix.lower()
        if format == 'eosmat' and suffix != '.eosmat':
            raise ValueError('Choose an .eosmat material file.')
        if format == 'txt' and suffix != '.txt':
            raise ValueError('Choose a .txt file for the reflection table.')
        if suffix not in ({'.eosmat'} if material_id is not None else {'.eosmat', '.jcpds', '.txt'}):
            raise ValueError('Choose an EOSMAT material, JCPDS phase or TXT reflection table.')
        if material_id is not None:
            eos.save_material_file(path, database_material(self._phase_material(material_id), assume_structure))
        else:
            from .integration import finite
            model = self._model.phase_model
            index = finite(index, 'Phase index', 0, len(model.phases) - 1, True)
            if Path(path).suffix.lower() == '.jcpds':
                from .phase_editor import validate_jcpds_export
                validate_jcpds_export(model.phases[index])
                model.save_phase_as(index, path)
            elif Path(path).suffix.lower() == '.txt':
                with open(path, 'w', encoding='utf-8') as stream:
                    stream.write('h\tk\tl\tIntensity\td0 (Å)\td (Å)\t2θ0 (°)\t2θ (°)\tQ0 (Å⁻¹)\tQ (Å⁻¹)\n')
                    for row in self._integration_phase_editor(index)['phaseEditor']['reflections']:
                        stream.write('\t'.join('' if row[k] is None else f'{row[k]:.17g}' for k in
                            ('h', 'k', 'l', 'intensity', 'd0', 'd', 'twoTheta0', 'twoTheta', 'q0', 'q')) + '\n')
            else:
                from .phase_editor import export_material
                # A failed save must leave an existing material file intact.
                import os
                import tempfile
                target = Path(path)
                with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.eosmat', delete=False) as temporary:
                    temporary_path = temporary.name
                try:
                    eos.save_material_file(temporary_path, export_material(model, index))
                    os.replace(temporary_path, path)
                finally:
                    if os.path.exists(temporary_path):
                        os.unlink(temporary_path)
                if model.is_material_editable(index):
                    phase = model.phases[index]
                    phase._filename = path
                    model.items[index].filename = path
                    phase.params['modified'] = False
                    phase.params['eos_records_modified'] = False
                    self._refresh_integration_pattern()
        self._revision += 1
        if editor_only:
            return {**self._integration_phase_editor(index), 'savedPath': path}
        result = {**self._snapshot(), 'savedPath': path}
        if index is not None:
            result.update(self._integration_phase_editor(index))
        return result

    def _integration_phase(self, **arguments):
        editor_only = arguments.pop('editor_only', False)
        editor_uid = arguments.pop('editor_uid', None)
        from .phase_editor import resolve_editor_index
        if editor_uid is not None:
            arguments['index'] = resolve_editor_index(self._model.phase_model, editor_uid=editor_uid)
        model = self._model.phase_model
        original = deepcopy(model.items)
        original_counter = model._color_counter
        try:
            result = self._phase_command(**arguments, editor_only=editor_only)
            return result
        except Exception as error:
            model.items = original
            model._color_counter = original_counter
            if arguments.get('operation') == 'editor_transaction':
                # Inline rejection feedback belongs inside the modal. Return the
                # restored authoritative editor, with an explicit rejected-edit
                # message; ordinary command clients retain normal error responses.
                self._refresh_integration_pattern()
                result = {**({} if editor_only else self._integration_phase_state()),
                          **self._integration_phase_editor(arguments['index'])}
                result['phaseEditor']['editError'] = str(error)
                return result
            raise

    def _phase_command(self, operation, index=None, path=None, paths=None, editor=False, editor_only=False, **changes):
        from .integration import finite, boolean
        model = self._model.phase_model
        if operation == 'editor_transaction':
            operation = changes.pop('edit_operation')
            if operation not in {'parameter', 'reflection', 'update', 'reload'} and not operation.startswith('editor_'):
                raise ValueError('Unknown editor edit.')
            if operation == 'editor_transaction':
                raise ValueError('Nested editor transactions are not supported.')
        if operation == 'load':
            if paths is None:
                path = self._path(path, 'phase')
                if path is None:
                    return {'cancelled': True}
                paths = [path]
            original_items = list(model.items)
            try:
                for filename in paths:
                    self._phase_load(self._path(filename, 'phase'), **changes)
            except Exception:
                model.items = original_items
                raise
        elif operation == 'load_database':
            material = database_material(self._phase_material(changes['material_id']),
                                         changes.get('assume_structure', False))
            reference = finite(changes['reference'], 'Reference', 0, len(material.eos_records)-1, True) if material.eos_records else None
            reason = load_error(material, reference)
            if reason:
                raise ValueError(reason)
            spacing, wavelength = self._phase_calculation_parameters()
            phase = eos.build_jcpds(material, reference, minimum_d_spacing=spacing,
                                    wavelength_angstrom=wavelength, origin='bundled')
            model.add_jcpds_object(phase, filename=phase.filename)
        elif operation == 'same_conditions':
            model.same_conditions = boolean(changes['enabled'], 'Same conditions')
        elif operation == 'clear':
            model.reset()
        elif operation == 'visibility_all':
            enabled = boolean(changes['visible'], 'Visibility')
            for i in range(len(model.phases)):
                model.set_phase_visible(i, enabled)
        else:
            index = finite(index, 'Phase index', 0, len(model.phases)-1, True)
            if operation == 'remove':
                model.del_phase(index)
            elif operation.startswith('editor_'):
                from .phase_editor import apply_editor_edit
                if operation == 'editor_copy':
                    from .phase_editor import copy_phase_for_editing
                    index = copy_phase_for_editing(model, index)
                else:
                    apply_editor_edit(self, model, index, operation, changes)
            elif operation == 'reload':
                model.reload(index)
            elif operation == 'parameter':
                key = changes['parameter']
                limits = dict(a0=(1e-6, 99999), b0=(1e-6, 99999), c0=(1e-6, 99999),
                    alpha0=(0.001,179.999), beta0=(0.001,179.999), gamma0=(0.001,179.999),
                    k0=(0,1e6), k0p0=(-100,100), k0pp0=(-100,100),
                    alpha_t0=(-1,1), d_alpha_dt=(-1,1), dk0dt=(-100,100), dk0pdt=(-100,100))
                if key == 'symmetry':
                    value = str(changes['value']).lower()
                    if value not in {'cubic','tetragonal','hexagonal','trigonal','rhombohedral','orthorhombic','monoclinic','triclinic'}:
                        raise ValueError('Unknown lattice symmetry.')
                    value = value.upper()
                elif key in limits:
                    value = finite(changes['value'], key, *limits[key])
                else:
                    raise ValueError('Unknown phase parameter.')
                # _integration_phase owns the complete rollback boundary.
                model.set_param(index, key, value)
            elif operation == 'reflection':
                action = changes['action']
                if action == 'add':
                    model.add_reflection(index)
                elif action == 'clear':
                    model.clear_reflections(index)
                elif action == 'remove':
                    rows = sorted({finite(v, 'Reflection', 0, len(model.phases[index].reflections)-1, True) for v in changes['rows']})
                    model.delete_multiple_reflections(index, rows)
                elif action == 'update':
                    row = finite(changes['row'], 'Reflection', 0, len(model.phases[index].reflections)-1, True)
                    key = changes['parameter']
                    if key not in {'h','k','l','intensity'}:
                        raise ValueError('Only h, k, l and intensity are editable.')
                    reflection = deepcopy(model.phases[index].reflections[row])
                    setattr(reflection, key, finite(changes['value'], key, 0 if key == 'intensity' else -10000, 1e9 if key == 'intensity' else 10000))
                    if reflection.h == reflection.k == reflection.l == 0:
                        raise ValueError('A reflection requires a nonzero Miller index.')
                    model.update_reflection(index, row, reflection)
                else:
                    raise ValueError('Unknown reflection action.')
            elif operation == 'update':
                for key, value in changes.items():
                    if key in {'pressure', 'temperature'}:
                        value = finite(value, key, -9999999 if key == 'pressure' else 0, 9999999)
                        if not getattr(model, 'set_' + key)(index, value):
                            raise ValueError(f'Phase model rejected {key} {value:g}.')
                    elif key == 'reference':
                        value = finite(value, key, 0, len(model.get_eos_reference_labels(index))-1, True)
                        if not model.set_eos_reference(index, value):
                            raise ValueError('Phase model rejected this reference.')
                    elif key == 'visible':
                        model.set_phase_visible(index, boolean(value, key))
                    elif key == 'color':
                        color = self._integration_color(value)
                        model.set_color(index, tuple(int(color[k:k+2],16) for k in (1,3,5)))
                    else:
                        raise ValueError('Unknown phase option.')
            else:
                raise ValueError('Unknown phase operation.')
        if index is not None and index < len(model.phases) and (operation in {'parameter', 'reflection'} or operation.startswith('editor_')):
            model.phases[index].params['modified'] = True
        self._refresh_integration_pattern()
        self._revision += 1
        result = {} if editor_only else self._integration_phase_state()
        if editor and index is not None and index < len(model.phases):
            result.update(self._integration_phase_editor(index))
        return result
