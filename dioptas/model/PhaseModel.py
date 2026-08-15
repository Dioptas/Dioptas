# SPDX-License-Identifier: MIT

import logging
import os
from copy import deepcopy
from math import isclose, pi

import numpy as np
from xypattern import Pattern

from dataclasses import dataclass, field
from typing import Any

from .util import Signal
from .state import PhaseParams, PhaseItemParams
from .util.jcpds import EosCalculationError, jcpds, jcpds_reflection
from .util.cif import CifConverter
from .util.HelperModule import calculate_color

logger = logging.getLogger(__name__)


_EOS_EDIT_PARAMS = frozenset({
    "k0", "k0p0", "k0pp0", "n", "z", "zc", "dk0dt", "dk0pdt",
    "alpha_t0", "d_alpha_dt", "thermal_parameters", "theta_t0",
    "gamma_t0", "q_t0", "t_ref",
})
_STRUCTURE_PARAMS = frozenset({
    "a0", "b0", "c0", "alpha0", "beta0", "gamma0", "symmetry",
})


class PhaseLoadError(Exception):
    def __init__(self, filename: str) -> None:
        super().__init__()
        self.filename: str = filename

    def __repr__(self) -> str:
        return "Could not load {0} as jcpds file".format(self.filename)


@dataclass
class PhaseItem:
    """Everything belonging to one phase, in one record.

    Replaces four parallel lists that had to be mutated in lockstep. The
    jcpds object is the crystallographic data (step 5b dissolves it into
    state and derived values); reflections caches the computed line
    positions/intensities for the current pressure and temperature."""

    jcpds: "jcpds"
    params: PhaseItemParams
    filename: str = ""
    reflections: Any = field(default_factory=list)


class PhaseModel:


    def __init__(self) -> None:
        super().__init__()
        # one record per phase: the four historically parallel lists
        # (phases/reflections/phase_files/item_params) are views over this
        self.items: list[PhaseItem] = []
        #: advances only for genuinely new phases, so each gets a fresh
        #: colour; restoring a phase brings its own colour and must not
        #: consume one (it used to, giving a new colour every undo/redo)
        self._color_counter: int = 0

        # All user-settable parameters live in the evented params dataclass;
        # the property below delegates to it.
        self.params: PhaseParams = PhaseParams()

        self.phase_added: Signal = Signal()
        self.phase_removed: Signal = Signal(int)  # phase ind
        self.phase_changed: Signal = Signal(int)  # phase ind
        self.phase_reloaded: Signal = Signal(int)  # phase ind
        self.condition_rejected: Signal = Signal(int, str, str)

        self.reflection_added: Signal = Signal(int)
        self.reflection_deleted: Signal = Signal(int, int)  # phase index, reflection index

    @property
    def same_conditions(self) -> bool:
        return self.params.same_conditions

    @same_conditions.setter
    def same_conditions(self, new_value: bool) -> None:
        self.params.same_conditions = new_value

    # -- read-only views over the items -----------------------------------
    # The four lists used to be parallel and mutated in lockstep at every
    # site — the same disease the mask's four undo deques had. External code
    # reads them by index; all mutation goes through the item list.

    @property
    def phases(self) -> list[jcpds]:
        return [item.jcpds for item in self.items]

    @property
    def reflections(self) -> list:
        return [item.reflections for item in self.items]

    @property
    def phase_files(self) -> list[str]:
        return [item.filename for item in self.items]

    @property
    def item_params(self) -> list[PhaseItemParams]:
        return [item.params for item in self.items]

    def add_jcpds(self, filename: str) -> None:
        """Adds a jcpds file."""
        logger.info("Adding JCPDS phase: %s", filename)
        try:
            jcpds_object = jcpds()
            jcpds_object.load_file(filename)
            self.add_jcpds_object(jcpds_object, filename=filename)
        except (ZeroDivisionError, UnboundLocalError, ValueError):
            raise PhaseLoadError(filename)

    def add_cif(
        self,
        filename: str,
        intensity_cutoff: float = 0.5,
        minimum_d_spacing: float = 0.5,
        wavelength_angstrom: float = 0.31,
    ) -> None:
        """
        Adds a cif file. Internally it is converted to a jcpds format. It calculates
        the intensities for all of the reflections based on the atomic positions.
        """
        logger.info("Adding CIF phase: %s", filename)
        try:
            cif_converter = CifConverter(
                wavelength_angstrom, minimum_d_spacing, intensity_cutoff
            )
            jcpds_object = cif_converter.convert_cif_to_jcpds(filename)
            self.add_jcpds_object(jcpds_object, filename=filename)
        except (ZeroDivisionError, UnboundLocalError, ValueError) as e:
            logger.warning("Failed to load CIF file %s: %s", filename, e)
            raise PhaseLoadError(filename)

    def add_jcpds_object(
        self,
        jcpds_object: jcpds,
        filename: str = "",
        params: PhaseItemParams | None = None,
    ) -> None:
        """Adds a jcpds object to the phase list.

        *params* supplies the display state for a phase that already has one
        (undo/redo, project loading). It has to be set before the item is
        appended: phase_added is what makes the views build their plot items,
        and they read the colour at that moment — assigning it afterwards left
        the plot in whatever colour the phase happened to be given first.
        """
        if params is None:
            params = PhaseItemParams(
                color=calculate_color(self._color_counter + 9)
            )
            self._color_counter += 1
        self.items.append(
            PhaseItem(
                jcpds=jcpds_object,
                params=params,
                filename=filename or str(jcpds_object.filename or ""),
            )
        )
        if self.same_conditions and len(self.phases) > 2:
            self.phases[-1].compute_d(self.phases[-2].params['pressure'], self.phases[-2].params['temperature'])
        else:
            self.phases[-1].compute_d()
        self.get_lines_d(-1)
        self.phase_added.emit()
        self.phase_changed.emit(len(self.phases) - 1)

    def ensure_structure_reflection_coverage(
        self,
        minimum_d_spacing: float,
        wavelength_angstrom: float,
    ) -> list[int]:
        """Extend structure-backed phases to a required experimental range.

        The supplied d cutoff already includes the experiment's Q margin.
        Existing coverage is retained unless a wavelength change reduces the
        physically accessible scattering sphere. Pressure and temperature do
        not call this method; they only move the cached reflections.
        """

        from .util.phasesmith import calculate_reflection_source

        requested_q_max = 2.0 * pi / minimum_d_spacing
        physical_q_max = np.nextafter(4.0 * pi / wavelength_angstrom, 0.0)
        changed = []
        for ind, phase in enumerate(self.phases):
            source = phase.state.reflection_source
            if not source or phase.state.modified:
                continue

            old_q_max = phase.state.reflection_q_max
            wavelength_changed = not isclose(
                phase.state.reflection_wavelength,
                wavelength_angstrom,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            if requested_q_max <= old_q_max * (1.0 + 1e-12) and not wavelength_changed:
                continue

            target_q_max = min(max(requested_q_max, old_q_max), physical_q_max)
            rows = calculate_reflection_source(
                source,
                minimum_d_spacing=2.0 * pi / target_q_max,
                minimum_intensity=phase.state.reflection_intensity_cutoff,
                wavelength_angstrom=wavelength_angstrom,
            )
            phase.reflections = [
                jcpds_reflection(h=h, k=k, l=l, intensity=intensity, d=d0)
                for h, k, l, d0, intensity in rows
            ]
            phase.state.reflection_q_max = target_q_max
            phase.state.reflection_wavelength = wavelength_angstrom
            phase.compute_d()
            self.get_lines_d(ind)
            self.phase_changed.emit(ind)
            changed.append(ind)
        return changed

    def save_phase_as(self, ind: int, filename: str) -> None:
        """Save the phase specified with ind as a jcpds file."""
        logger.info("Saving phase %d to %s", ind, filename)
        self.phases[ind].save_file(filename)
        self.phase_changed.emit(ind)

    def del_phase(self, ind: int) -> None:
        """Deletes a phase with index ind from the phase list."""
        logger.info("Deleting phase %d", ind)
        del self.items[ind]
        self.phase_removed.emit(ind)

    def reload(self, ind: int) -> None:
        """Reload a JCPDS, CIF, or EoS material from its source file."""
        logger.info("Reloading phase %d", ind)
        source = self.items[ind].filename
        phase = self.phases[ind]
        pressure = phase.params['pressure']
        temperature = phase.params['temperature']

        try:
            extension = os.path.splitext(source)[1].lower()
            if extension == '.cif':
                q_max = phase.state.reflection_q_max
                minimum_d_spacing = 2.0 * pi / q_max if q_max else 0.5
                converter = CifConverter(
                    phase.state.reflection_wavelength or 0.31,
                    minimum_d_spacing,
                    phase.state.reflection_intensity_cutoff,
                )
                reloaded = converter.convert_cif_to_jcpds(source)
                self.items[ind].jcpds = reloaded
            elif extension == '.eosmat':
                from .eos import build_jcpds, load_material_file

                q_max = phase.state.reflection_q_max
                minimum_d_spacing = 2.0 * pi / q_max if q_max else 0.5
                reloaded = build_jcpds(
                    load_material_file(source),
                    minimum_d_spacing=minimum_d_spacing,
                    minimum_intensity=phase.state.reflection_intensity_cutoff,
                    wavelength_angstrom=(
                        phase.state.reflection_wavelength or 0.31),
                    origin='file',
                )
                reloaded._filename = source
                self.items[ind].jcpds = reloaded
            else:
                phase.reload_file()
        except Exception as error:
            logger.warning("Failed to reload phase source %s: %s", source, error)
            raise PhaseLoadError(source) from error

        phase = self.phases[ind]
        phase.params['pressure'] = pressure
        phase.params['temperature'] = temperature
        phase.compute_d()
        self.get_lines_d(ind)
        self.phase_reloaded.emit(ind)
        self.phase_changed.emit(ind)

    def can_reload(self, ind: int) -> bool:
        """Whether a phase has a supported, file-backed source."""
        if not 0 <= ind < len(self.items):
            return False
        extension = os.path.splitext(self.items[ind].filename)[1].lower()
        return extension in ('.jcpds', '.cif', '.eosmat')

    def set_pressure(self, ind: int, pressure: float) -> bool:
        """
        Sets the pressure of a phase with index ind. In case same_conditions is true,
        all phase pressures will be updated.
        """
        logger.debug("Setting pressure for phase %d to %.2f GPa", ind, pressure)
        indices = list(range(len(self.phases))) if self.same_conditions else [ind]
        return self._apply_conditions(
            ind, indices, "pressure", f"{pressure:g} GPa",
            lambda phase: phase.compute_d(pressure=pressure),
        )

    def set_temperature(self, ind: int, temperature: float) -> bool:
        """
        Sets the temperature of a phase with index ind. In case same_conditions is true,
        all phase temperatures will be updated.
        """
        logger.debug("Setting temperature for phase %d to %.1f K", ind, temperature)
        indices = list(range(len(self.phases))) if self.same_conditions else [ind]
        return self._apply_conditions(
            ind, indices, "temperature", f"{temperature:g} K",
            lambda phase: (
                phase.compute_d(temperature=temperature)
                if phase.has_thermal_expansion() else None
            ),
        )

    def set_pressure_temperature(
        self, ind: int, pressure: float, temperature: float
    ) -> bool:
        return self._apply_conditions(
            ind, [ind], "pressure and temperature",
            f"{pressure:g} GPa, {temperature:g} K",
            lambda phase: phase.compute_d(
                temperature=temperature, pressure=pressure),
        )

    @staticmethod
    def _condition_snapshot(phase: jcpds) -> tuple:
        """Capture all state that a failed ``compute_d`` may have changed."""
        return (
            deepcopy(phase.state),
            deepcopy(phase.params._derived),
            [reflection.d for reflection in phase.reflections],
        )

    @staticmethod
    def _restore_condition_snapshot(phase: jcpds, snapshot: tuple) -> None:
        state, derived, reflection_d = snapshot
        phase.state = state
        phase.params._state = state
        phase.params._derived = derived
        for reflection, d_spacing in zip(phase.reflections, reflection_d):
            reflection.d = d_spacing

    def _apply_conditions(self, source_ind: int, indices: list[int],
                          condition: str, requested: str, operation) -> bool:
        """Apply a P/T change atomically, retaining the last valid state."""
        snapshots = {
            index: self._condition_snapshot(self.phases[index])
            for index in indices
        }
        try:
            for index in indices:
                operation(self.phases[index])
        except EosCalculationError as error:
            for index, snapshot in snapshots.items():
                self._restore_condition_snapshot(self.phases[index], snapshot)
                self.phase_changed.emit(index)
            logger.info(
                "Rejected %s %s for phase %d: %s",
                condition, requested, source_ind, error,
            )
            message = (
                f"{requested} was not applied because the selected equation "
                "of state cannot be evaluated there. The last valid "
                "condition was retained."
            )
            self.condition_rejected.emit(source_ind, condition, message)
            return False

        for index in indices:
            self.get_lines_d(index)
            self.phase_changed.emit(index)
        return True

    def set_param(self, ind: int, param: str, value: Any) -> None:
        """
        Sets one of the jcpds parameters for the phase with index ind to a certain value.
        Automatically emits the phase_changed signal.
        """

        phase = self.phases[ind]
        if param in _EOS_EDIT_PARAMS:
            self._require_editable_eos_record(ind)
        if param in _STRUCTURE_PARAMS:
            self._require_editable_material(ind)
        phase.params[param] = value
        if param in _STRUCTURE_PARAMS:
            phase.compute_v0()
            phase.compute_d0()
        if param in _EOS_EDIT_PARAMS or param in _STRUCTURE_PARAMS:
            self._sync_active_eos_record(ind)
        phase.compute_d()
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_eos_type(self, ind: int, eos_type: str) -> None:
        """
        Changes the equation of state used by the phase with index ind
        (a peritheos.eos.rt class name, e.g. 'BM3' or 'Vinet') and
        recomputes its line positions at the current
        pressure/temperature.
        """
        logger.debug("Setting EoS type for phase %d to %s", ind, eos_type)
        self._require_editable_eos_record(ind)
        self.phases[ind].params['eos_type'] = eos_type
        self._sync_active_eos_record(ind)
        self.phases[ind].compute_d()
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def get_eos_type(self, ind: int) -> str:
        """Returns the equation-of-state type of the phase with index ind."""
        return str(self.phases[ind].params.get('eos_type') or 'BM3')

    def set_thermal_type(self, ind: int, thermal_type: str) -> None:
        """
        Changes the thermal model of the phase with index ind: '' for the
        classic constant-coefficient correction, or a peritheos thermal
        class name ('MieGruneisenDebye', 'MieGruneisenEinstein'), and
        recomputes the line positions at the current
        pressure/temperature.
        """
        logger.debug("Setting thermal model for phase %d to '%s'",
                     ind, thermal_type)
        self._require_editable_eos_record(ind)
        self.phases[ind].params['thermal_type'] = thermal_type
        self._sync_active_eos_record(ind)
        self.phases[ind].compute_d()
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def get_thermal_type(self, ind: int) -> str:
        """Returns the thermal model of the phase with index ind."""
        return str(self.phases[ind].params.get('thermal_type') or '')

    def eos_record_origin(self, ind: int, ref_ind: int | None = None) -> str:
        """Runtime ownership of an EoS record."""
        phase = self.phases[ind]
        records = phase.params['eos_records']
        if ref_ind is None:
            ref_ind = phase.params['eos_current_index']
        origins = phase.params.get('eos_record_origins') or []
        if not 0 <= ref_ind < len(records):
            return ""
        if ref_ind < len(origins):
            return str(origins[ref_ind])
        return str(phase.params.get('material_origin') or 'legacy')

    def is_eos_record_editable(self, ind: int,
                               ref_ind: int | None = None) -> bool:
        """A missing/scratch record and every non-bundled record are editable."""
        phase = self.phases[ind]
        if not phase.params['eos_records']:
            return True
        return self.eos_record_origin(ind, ref_ind) != 'bundled'

    def _require_editable_eos_record(self, ind: int,
                                     ref_ind: int | None = None) -> None:
        if not self.is_eos_record_editable(ind, ref_ind):
            raise PermissionError(
                "Bundled EoS records are read-only; duplicate the record "
                "as a custom record before changing it."
            )

    def is_material_editable(self, ind: int) -> bool:
        """Bundled structures are curated application data and read-only."""
        return self.phases[ind].params.get('material_origin') != 'bundled'

    def _require_editable_material(self, ind: int) -> None:
        if not self.is_material_editable(ind):
            raise PermissionError(
                "Bundled materials are read-only; export and reload an "
                ".eosmat file before changing the structure."
            )

    def eos_record_from_phase(self, ind: int, base: dict | None = None) -> dict:
        """Snapshot the live EoS/thermal parameters into one record dict."""
        from .util.eos_phase import eos_parameter_names

        phase = self.phases[ind]
        p = phase.params
        record = deepcopy(base or {})
        eos_type = str(p.get('eos_type') or 'BM3')
        parameter_map = {
            'K0': p.get('k0'),
            'K0_prime': p.get('k0p0'),
            'K0_double_prime': p.get('k0pp0'),
            'n': p.get('n'),
            'Z': p.get('z'),
        }
        names = eos_parameter_names(eos_type)
        parameters = {'V0': p.get('v0')}
        for name in names:
            value = parameter_map.get(name)
            if value is not None:
                parameters[name] = value
        record['eos'] = {'type': eos_type, 'parameters': parameters}

        thermal_type = str(p.get('thermal_type') or '')
        if thermal_type:
            thermal_parameters = deepcopy(p.get('thermal_parameters') or {})
            if (thermal_type in ('MieGruneisenDebye',
                                 'MieGruneisenEinstein')
                    and p.get('n') is not None):
                thermal_parameters.setdefault('n', p['n'])
            record['thermal'] = {
                **deepcopy(record.get('thermal') or {}),
                'type': thermal_type,
                'parameters': thermal_parameters,
            }
        elif any(p.get(key) for key in
                 ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt')):
            record['thermal'] = {
                **deepcopy(record.get('thermal') or {}),
                'type': 'AlphaKT',
                'parameters': {
                    'alpha0': p.get('alpha_t0') or 0.0,
                    'd_alpha_dT': p.get('d_alpha_dt') or 0.0,
                    'dK_dT': p.get('dk0dt') or 0.0,
                    'dK_prime_dT': p.get('dk0pdt') or 0.0,
                },
            }
        else:
            record.pop('thermal', None)
        record['temperature_ref'] = p.get('t_ref') or 298.15
        return record

    def _sync_active_eos_record(self, ind: int) -> None:
        """Keep an editable active record aligned with Phase Editor values."""
        phase = self.phases[ind]
        records = phase.params['eos_records']
        ref_ind = phase.params['eos_current_index']
        if (not 0 <= ref_ind < len(records)
                or not self.is_eos_record_editable(ind, ref_ind)):
            return
        records[ref_ind] = self.eos_record_from_phase(ind, records[ref_ind])
        phase.params['eos_records'] = records
        phase.params['eos_records_modified'] = True

    def add_eos_record(self, ind: int, record: dict, *,
                       origin: str = 'custom', select: bool = True) -> int:
        """Append a user-owned EoS record and optionally make it active."""
        phase = self.phases[ind]
        records = list(phase.params['eos_records'])
        origins = list(phase.params.get('eos_record_origins') or [])
        origins.extend(
            str(phase.params.get('material_origin') or 'legacy')
            for _ in range(len(records) - len(origins))
        )
        records.append(deepcopy(record))
        origins.append(origin)
        new_index = len(records) - 1
        phase.params['eos_records'] = records
        phase.params['eos_record_origins'] = origins
        phase.params['eos_records_modified'] = True
        if len(records) == 1:
            phase.params['eos_default_index'] = 0
        if select:
            phase.params['eos_current_index'] = new_index
            from .eos import apply_eos_record
            apply_eos_record(phase, records[new_index])
            phase.compute_d()
            self.get_lines_d(ind)
        phase.params['modified'] = True
        self.phase_changed.emit(ind)
        return new_index

    def update_eos_record(self, ind: int, ref_ind: int, record: dict) -> None:
        """Replace one user-owned record; bundled records are immutable."""
        self._require_editable_eos_record(ind, ref_ind)
        phase = self.phases[ind]
        records = list(phase.params['eos_records'])
        if not 0 <= ref_ind < len(records):
            raise IndexError(ref_ind)
        records[ref_ind] = deepcopy(record)
        phase.params['eos_records'] = records
        phase.params['eos_records_modified'] = True
        if phase.params['eos_current_index'] == ref_ind:
            from .eos import apply_eos_record
            apply_eos_record(phase, records[ref_ind])
            phase.compute_d()
            self.get_lines_d(ind)
        phase.params['modified'] = True
        self.phase_changed.emit(ind)

    def duplicate_eos_record(self, ind: int, ref_ind: int,
                             record: dict | None = None) -> int:
        """Create an editable custom copy without changing its source record."""
        records = self.phases[ind].params['eos_records']
        if not 0 <= ref_ind < len(records):
            raise IndexError(ref_ind)
        duplicate = deepcopy(record or records[ref_ind])
        duplicate.pop('default', None)
        if record is None:
            label = duplicate.get('label') or 'EoS record'
            duplicate['label'] = f"{label} (custom)"
        return self.add_eos_record(ind, duplicate, origin='custom')

    def delete_eos_record(self, ind: int, ref_ind: int) -> None:
        """Delete a user-owned record and apply a safe remaining selection."""
        self._require_editable_eos_record(ind, ref_ind)
        phase = self.phases[ind]
        records = list(phase.params['eos_records'])
        if not 0 <= ref_ind < len(records):
            raise IndexError(ref_ind)
        origins = list(phase.params.get('eos_record_origins') or [])
        del records[ref_ind]
        if ref_ind < len(origins):
            del origins[ref_ind]
        phase.params['eos_records'] = records
        phase.params['eos_record_origins'] = origins
        phase.params['eos_records_modified'] = True

        default_index = phase.params.get('eos_default_index') or 0
        if default_index > ref_ind:
            default_index -= 1
        phase.params['eos_default_index'] = max(
            0, min(default_index, len(records) - 1)) if records else 0

        if records:
            current = max(0, min(ref_ind, len(records) - 1))
            phase.params['eos_current_index'] = current
            from .eos import apply_eos_record
            apply_eos_record(phase, records[current])
        else:
            phase.params['eos_current_index'] = 0
            phase.params['k0'] = 0.0
            phase.params['k0p0'] = 0.0
            phase.params['k0pp0'] = 0.0
            phase.params['eos_type'] = 'BM3'
            phase.params['thermal_type'] = ''
            phase.params['thermal_parameters'] = {}
            for key in ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'):
                phase.params[key] = 0.0
            phase.compute_v0()
        phase.compute_d()
        phase.params['modified'] = True
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_eos_default(self, ind: int, ref_ind: int) -> None:
        """Choose the default of a user-owned material without source edits."""
        self._require_editable_eos_record(ind, ref_ind)
        records = self.phases[ind].params['eos_records']
        if not 0 <= ref_ind < len(records):
            raise IndexError(ref_ind)
        self.phases[ind].params['eos_default_index'] = ref_ind
        self.phases[ind].params['eos_records_modified'] = True
        self.phases[ind].params['modified'] = True
        self.phase_changed.emit(ind)

    def set_eos_reference(self, ind: int, ref_ind: int) -> bool:
        """
        Switches the phase with index ind to another of its EoS records
        (different literature reference for the same material). Applies
        that record's K0/K0'/V0 etc. — including its equation of state —
        and recomputes the line positions at the current
        pressure/temperature. The phase name stays the chemistry; the
        active reference is visible in the Ref column and the comments.

        The records live on the phase state (set by model.eos.build_jcpds
        for database materials, carried through project files and undo);
        legacy jcpds files have none, so this is a no-op there.
        """
        from .eos import apply_eos_record

        phase = self.phases[ind]
        records = phase.params['eos_records']
        if not 0 <= ref_ind < len(records):
            return False
        record = records[ref_ind]
        from .eos import reference_text
        logger.debug("Switching phase %d to EoS reference '%s'",
                     ind, reference_text(record.get('reference')))

        def apply_reference(candidate: jcpds) -> None:
            candidate.params['eos_current_index'] = ref_ind
            apply_eos_record(candidate, record)
            candidate.compute_d()  # use the phase's current P and T
            candidate.params['modified'] = bool(
                candidate.params.get('eos_records_modified'))

        label = reference_text(record.get('reference')) or "selected reference"
        return self._apply_conditions(
            ind, [ind], "reference", label, apply_reference)

    def get_eos_reference_labels(self, ind: int) -> list:
        """Reference labels available for the phase with index ind."""
        from .eos import record_label
        return [record_label(record)
                for record in self.phases[ind].params['eos_records']]

    def set_color(self, ind: int, color: tuple[int, int, int]) -> None:
        """Changes the color of the phase with index ind."""
        self.item_params[ind].color = color
        self.phase_changed.emit(ind)

    def set_phase_visible(self, ind: int, bool: bool) -> None:
        """Sets the visible flag for phase with index ind."""
        self.item_params[ind].visible = bool
        self.phase_changed.emit(ind)

    @property
    def phase_colors(self) -> list:
        """Per-phase colors (read-only view; write via set_color)."""
        return [item.color for item in self.item_params]

    @property
    def phase_visible(self) -> list[bool]:
        """Per-phase visibility (read-only view; write via set_phase_visible)."""
        return [item.visible for item in self.item_params]

    def get_lines_d(self, ind: int) -> np.ndarray:
        """
        Gets the reflections from the phase with index ind and saves them in a
        two-dimensional array.
        """
        reflections = self.phases[ind].get_reflections()
        res = np.zeros((len(reflections), 5))
        for i, reflection in enumerate(reflections):
            res[i, 0] = reflection.d
            res[i, 1] = reflection.intensity
            res[i, 2] = reflection.h
            res[i, 3] = reflection.k
            res[i, 4] = reflection.l
        self.items[ind].reflections = res
        return res

    def get_phase_line_positions(
        self, ind: int, unit: str, wavelength: float
    ) -> np.ndarray:
        """Gets the line positions of phase with index ind in a specific unit.

        unit can be '2th_deg', 'q_A^-1', or 'd_A'.
        wavelength is in nm.
        """
        positions = self.reflections[ind][:, 0]
        if unit == 'q_A^-1' or unit == '2th_deg':
            positions = 2 * \
                        np.arcsin(wavelength / (2 * positions)) * 180.0 / np.pi
            if unit == 'q_A^-1':
                positions = 4 * np.pi / wavelength * \
                            np.sin(positions / 360 * np.pi)
        return positions

    def get_phase_line_intensities(
        self,
        ind: int,
        positions: np.ndarray,
        pattern: Pattern,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
    ) -> tuple[np.ndarray | list, float]:
        """
        Gets the phase line intensities scaled to each other for a specific x and y
        range and also a maximum intensity based on a specific pattern.

        Returns (array of intensities, baseline representing the start for the lines).
        """
        x, y = pattern.data
        if len(y) != 0:
            y_in_range = y[(x > x_range[0]) & (x < x_range[1])]
            if len(y_in_range) == 0:
                return [], 0
            max_pattern_intensity = np.min([np.max(y_in_range), y_range[1]])
        else:
            max_pattern_intensity = 1

        baseline = y_range[0]
        phase_line_intensities = self.reflections[ind][:, 1]
        # search for reflections within current pattern view range
        phase_line_intensities_in_range = phase_line_intensities[(positions > x_range[0]) & (positions < x_range[1])]

        # rescale intensity based on the lines visible
        if len(phase_line_intensities_in_range):
            scale_factor = (max_pattern_intensity - baseline) / \
                           np.max(phase_line_intensities_in_range)
        else:
            scale_factor = 1
        if scale_factor <= 0:
            scale_factor = 0.01

        phase_line_intensities = scale_factor * self.reflections[ind][:, 1] + baseline
        return phase_line_intensities, baseline

    def get_rescaled_reflections(
        self,
        ind: int,
        pattern: Pattern,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        wavelength: float,
        unit: str = '2th_deg',
    ) -> tuple[np.ndarray, np.ndarray | list, float]:
        """
        Gets the phase line positions and intensities for a phase with index ind scaled
        to each other for a specific x and y range and also a maximum intensity based on
        a specific pattern.

        Returns (positions, intensities, baseline).
        """
        positions = self.get_phase_line_positions(ind, unit, wavelength)

        intensities, baseline = self.get_phase_line_intensities(ind, positions, pattern, x_range, y_range)
        return positions, intensities, baseline

    def add_reflection(self, ind: int) -> None:
        """Adds an empty reflection to the reflection table of a phase with index ind."""
        self._require_editable_material(ind)
        self.phases[ind].add_reflection()
        self.get_lines_d(ind)
        self.reflection_added.emit(ind)

    def delete_reflection(self, phase_ind: int, reflection_ind: int) -> None:
        """Deletes a reflection from a phase with the given phase index."""
        self._require_editable_material(phase_ind)
        self.phases[phase_ind].delete_reflection(reflection_ind)
        self.get_lines_d(phase_ind)
        self.reflection_deleted.emit(phase_ind, reflection_ind)
        self.phase_changed.emit(phase_ind)

    def delete_multiple_reflections(
        self, phase_ind: int, indices: list[int] | np.ndarray
    ) -> None:
        """Deletes multiple reflections from a phase with the given phase index."""
        indices = np.array(sorted(indices))
        for reflection_ind in indices:
            self.delete_reflection(phase_ind, reflection_ind)
            indices -= 1

    def clear_reflections(self, phase_ind: int) -> None:
        """Deletes all reflections from a phase with index phase_ind."""
        for ind in range(len(self.phases[phase_ind].reflections)):
            self.delete_reflection(phase_ind, 0)

    def update_reflection(
        self,
        phase_ind: int,
        reflection_ind: int,
        reflection: jcpds_reflection,
    ) -> None:
        """Updates the reflection of a phase with a new jcpds_reflection."""
        self._require_editable_material(phase_ind)
        self.phases[phase_ind].reflections[reflection_ind] = reflection
        self.phases[phase_ind].params['modified'] = True
        self.phases[phase_ind].compute_d0()
        self.phases[phase_ind].compute_d()
        self.get_lines_d(phase_ind)
        self.phase_changed.emit(phase_ind)

    def reset(self) -> None:
        """Deletes all phases within the phase model."""
        for ind in range(len(self.phases)):
            self.del_phase(0)
