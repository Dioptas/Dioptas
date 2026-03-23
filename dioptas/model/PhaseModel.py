# SPDX-License-Identifier: MIT

import logging

import numpy as np
from xypattern import Pattern

from .util import Signal
from .util.jcpds import jcpds, jcpds_reflection
from .util.cif import CifConverter
from .util.HelperModule import calculate_color

logger = logging.getLogger(__name__)


class PhaseLoadError(Exception):
    def __init__(self, filename: str) -> None:
        super().__init__()
        self.filename: str = filename

    def __repr__(self) -> str:
        return "Could not load {0} as jcpds file".format(self.filename)


class PhaseModel:

    num_phases: int = 0

    def __init__(self) -> None:
        super().__init__()
        self.phases: list[jcpds] = []
        self.reflections: list[np.ndarray] = []
        self.phase_files: list[str] = []
        self.phase_colors: list[np.ndarray] = []
        self.phase_visible: list[bool] = []

        self.same_conditions: bool = True

        self.phase_added: Signal = Signal()
        self.phase_removed: Signal = Signal(int)  # phase ind
        self.phase_changed: Signal = Signal(int)  # phase ind
        self.phase_reloaded: Signal = Signal(int)  # phase ind

        self.reflection_added: Signal = Signal(int)
        self.reflection_deleted: Signal = Signal(int, int)  # phase index, reflection index

    def add_jcpds(self, filename: str) -> None:
        """Adds a jcpds file."""
        logger.info("Adding JCPDS phase: %s", filename)
        try:
            jcpds_object = jcpds()
            jcpds_object.load_file(filename)
            self.phase_files.append(filename)
            self.add_jcpds_object(jcpds_object)
        except (ZeroDivisionError, UnboundLocalError, ValueError):
            raise PhaseLoadError(filename)

    def add_cif(
        self,
        filename: str,
        intensity_cutoff: float = 0.5,
        minimum_d_spacing: float = 0.5,
    ) -> None:
        """
        Adds a cif file. Internally it is converted to a jcpds format. It calculates
        the intensities for all of the reflections based on the atomic positions.
        """
        logger.info("Adding CIF phase: %s", filename)
        try:
            cif_converter = CifConverter(0.31, minimum_d_spacing, intensity_cutoff)
            jcpds_object = cif_converter.convert_cif_to_jcpds(filename)
            self.phase_files.append(filename)
            self.add_jcpds_object(jcpds_object)
        except (ZeroDivisionError, UnboundLocalError, ValueError) as e:
            logger.warning("Failed to load CIF file %s: %s", filename, e)
            raise PhaseLoadError(filename)

    def add_jcpds_object(self, jcpds_object: jcpds) -> None:
        """Adds a jcpds object to the phase list."""
        self.phases.append(jcpds_object)
        self.reflections.append([])
        self.phase_colors.append(calculate_color(PhaseModel.num_phases + 9))
        self.phase_visible.append(True)
        PhaseModel.num_phases += 1
        if self.same_conditions and len(self.phases) > 2:
            self.phases[-1].compute_d(self.phases[-2].params['pressure'], self.phases[-2].params['temperature'])
        else:
            self.phases[-1].compute_d()
        self.get_lines_d(-1)
        self.phase_added.emit()
        self.phase_changed.emit(len(self.phases) - 1)

    def save_phase_as(self, ind: int, filename: str) -> None:
        """Save the phase specified with ind as a jcpds file."""
        logger.info("Saving phase %d to %s", ind, filename)
        self.phases[ind].save_file(filename)
        self.phase_changed.emit(ind)

    def del_phase(self, ind: int) -> None:
        """Deletes a phase with index ind from the phase list."""
        logger.info("Deleting phase %d", ind)
        del self.phases[ind]
        del self.reflections[ind]
        del self.phase_files[ind]
        del self.phase_colors[ind]
        del self.phase_visible[ind]
        self.phase_removed.emit(ind)

    def reload(self, ind: int) -> None:
        """Reloads a phase specified by index ind from its original source filename."""
        logger.info("Reloading phase %d", ind)
        self.clear_reflections(ind)
        self.phases[ind].reload_file()
        for _ in range(len(self.phases[ind].reflections)):
            self.reflection_added.emit(ind)
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_pressure(self, ind: int, pressure: float) -> None:
        """
        Sets the pressure of a phase with index ind. In case same_conditions is true,
        all phase pressures will be updated.
        """
        logger.debug("Setting pressure for phase %d to %.2f GPa", ind, pressure)
        if self.same_conditions:
            for j in range(len(self.phases)):
                self._set_pressure(j, pressure)
                self.phase_changed.emit(j)
        else:
            self._set_pressure(ind, pressure)
            self.phase_changed.emit(ind)

    def _set_pressure(self, ind: int, pressure: float) -> None:
        self.phases[ind].compute_d(pressure=pressure)
        self.get_lines_d(ind)

    def set_temperature(self, ind: int, temperature: float) -> None:
        """
        Sets the temperature of a phase with index ind. In case same_conditions is true,
        all phase temperatures will be updated.
        """
        logger.debug("Setting temperature for phase %d to %.1f K", ind, temperature)
        if self.same_conditions:
            for j in range(len(self.phases)):
                self._set_temperature(j, temperature)
                self.phase_changed.emit(j)
        else:
            self._set_temperature(ind, temperature)
            self.phase_changed.emit(ind)

    def _set_temperature(self, ind: int, temperature: float) -> None:
        if self.phases[ind].has_thermal_expansion():
            self.phases[ind].compute_d(temperature=temperature)
            self.get_lines_d(ind)

    def set_pressure_temperature(
        self, ind: int, pressure: float, temperature: float
    ) -> None:
        self.phases[ind].compute_d(temperature=temperature, pressure=pressure)
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_param(self, ind: int, param: str, value: float) -> None:
        """
        Sets one of the jcpds parameters for the phase with index ind to a certain value.
        Automatically emits the phase_changed signal.
        """

        self.phases[ind].params[param] = value
        self.phases[ind].compute_v0()
        self.phases[ind].compute_d0()
        self.phases[ind].compute_d()
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_color(self, ind: int, color: tuple[int, int, int]) -> None:
        """Changes the color of the phase with index ind."""
        self.phase_colors[ind] = color
        self.phase_changed.emit(ind)

    def set_phase_visible(self, ind: int, bool: bool) -> None:
        """Sets the visible flag for phase with index ind."""
        self.phase_visible[ind] = bool
        self.phase_changed.emit(ind)

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
        self.reflections[ind] = res
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
        self.phases[ind].add_reflection()
        self.get_lines_d(ind)
        self.reflection_added.emit(ind)

    def delete_reflection(self, phase_ind: int, reflection_ind: int) -> None:
        """Deletes a reflection from a phase with the given phase index."""
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
