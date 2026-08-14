# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import numpy as np
import h5py

from pyFAI.multi_geometry import MultiGeometry

from xypattern import Pattern

from .util import Signal
from .util import jcpds
from .state import (
    apply_params,
    Derived,
    PhaseParams,
    ViewParams,
    save_params,
    load_params,
    PROJECT_FORMAT_VERSION,
)
from .state import PayloadStore
from .state.snapshot import StateRecorder
from .state.project import save_project, load_project
from .Configuration import Configuration
from . import (
    ImgModel,
    CalibrationModel,
    MaskModel,
    PhaseModel,
    PatternModel,
    OverlayModel,
    BatchModel,
)
from .MapModel import MapModel
from .. import __version__

logger = logging.getLogger(__name__)


class UnsupportedProjectFileError(Exception):
    """A .dio file this version cannot read (written before format 2)."""


class DioptasModel:
    """Handles all the data used in Dioptas.

    Image, Calibration and Mask are handled by so called configurations.
    Patterns and overlays are global and always the same, no matter which configuration is selected.
    """

    def __init__(self) -> None:
        super().__init__()
        self.configurations: list[Configuration] = []
        self.configuration_ind: int = 0
        self.configurations.append(Configuration())

        self._overlay_model: OverlayModel = OverlayModel()
        self._phase_model: PhaseModel = PhaseModel()

        # GUI view state (see ViewParams). A single stable instance for the
        # model's lifetime — load() applies fields onto it, so controllers'
        # event subscriptions stay valid.
        self.view: ViewParams = ViewParams()

        self._combine_patterns: bool = False
        self._combine_cakes: bool = False
        self._cake_data: np.ndarray | None = None
        self._cake_tth: np.ndarray | None = None
        self._cake_azi: np.ndarray | None = None

        self._multi_geometry: MultiGeometry | None = None
        self._multi_geometry_unit: str | None = None

        self.configurations[0].calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )
        self.configurations[0].calibration_model.parameters_changed.connect(
            self.invalidate_multi_geometry
        )

        self.configuration_added: Signal = Signal()
        self.configuration_selected: Signal = Signal(int)  # new index
        self.configuration_removed: Signal = Signal(int)  # removed index

        self.img_changed: Signal = Signal()
        self.mask_changed: Signal = Signal()
        self.pattern_changed: Signal = Signal()
        self.cake_changed: Signal = Signal()
        self.enabled_phases_in_cake: Signal = Signal()

        # the store-level settings-change surface: forwards every params
        # field change of the CURRENT configuration as (field, new, old);
        # stable across configuration switches (rewired in connect_models).
        # Sub-model params are namespaced by prefix: e.g. the ImgModel's
        # factor arrives as "img.factor"; Configuration fields are unprefixed.
        self.configuration_params_changed: Signal = Signal(str, object, object)

        # convenience signal for the most-consumed field, emitting
        # (new_unit, previous_unit); derived from the forwarding above
        self.integration_unit_changed: Signal = Signal(str, str)

        self.clicked_tth: float = 0
        self.clicked_azi: float = 0

        self.clicked_tth_changed: Signal = Signal()
        self.clicked_azi_changed: Signal = Signal()
        self.clicked_tth_changed.connect(self.update_clicked_tth)
        self.clicked_azi_changed.connect(self.update_clicked_azi)

        # Combined cake across all configurations: recomputed when any
        # configuration's cake changes, gated by combine_cakes. Registered
        # before connect_models so the recompute runs before the cake_changed
        # forwarding to the GUI.
        self._combined_cake: Derived = Derived(
            self.calculate_combined_cake, active=False
        )
        self._combined_cake.add_dependency(self.configurations[0].cake_changed)

        self.connect_models()

        # the phase model is global (not per-configuration), so its params
        # events are forwarded once and never rewired
        self._phase_model.params.events.connect(self._on_phase_params_event)
        # map windows can subtract an overlay; an edited overlay has to reach
        # every configuration's map, not only the current one
        self._overlay_model.overlay_added.connect(self._on_overlays_changed_for_maps)
        self._overlay_model.overlay_removed.connect(
            self._on_overlays_changed_for_maps
        )
        self._overlay_model.overlay_changed.connect(
            self._on_overlays_changed_for_maps
        )

        # Owned binary payloads (mask pixels; overlay data in later steps),
        # content-addressed so snapshots and configurations share them by id.
        self.payloads: PayloadStore = PayloadStore()

        # Undo/redo. Constructed last: it subscribes to the signals above and
        # captures a baseline snapshot, so everything it snapshots must exist.
        self._recorder: StateRecorder = StateRecorder(self)

    def add_configuration(self) -> None:
        """Adds a new configuration to the list of configurations.

        The new configuration will have the same working directories as the currently selected.
        """
        logger.info("Adding new configuration")
        self.configurations.append(Configuration(self.working_directories))

        source_calibration = self.current_configuration.calibration_model
        if source_calibration.is_calibrated:
            dioptas_config_folder = os.path.join(os.path.expanduser("~"), ".Dioptas")
            if not os.path.isdir(dioptas_config_folder):
                os.mkdir(dioptas_config_folder)
            # the calibration is transferred through a temporary poni file;
            # save()/load() overwrite the calibration name and filename, so
            # they are restored afterwards for both configurations
            calibration_name = source_calibration.calibration_name
            calibration_filename = source_calibration.filename
            transfer_path = os.path.join(dioptas_config_folder, "transfer.poni")
            source_calibration.save(transfer_path)
            self.configurations[-1].calibration_model.load(transfer_path)
            for calibration_model in (
                source_calibration,
                self.configurations[-1].calibration_model,
            ):
                calibration_model.calibration_name = calibration_name
                calibration_model.filename = calibration_filename

        self.configurations[-1].img_model._img_data = (
            self.current_configuration.img_model.img_data
        )
        self.configurations[-1].calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )
        self.configurations[-1].calibration_model.parameters_changed.connect(
            self.invalidate_multi_geometry
        )
        self._combined_cake.add_dependency(self.configurations[-1].cake_changed)

        self.select_configuration(len(self.configurations) - 1)
        self.invalidate_multi_geometry()
        self.configuration_added.emit()

    def remove_configuration(self) -> None:
        """Removes the currently selected configuration."""
        logger.info("Removing configuration")
        if len(self.configurations) == 1:
            return
        ind = self.configuration_ind
        self.configurations[ind].calibration_model.detector_reset.disconnect(
            self.invalidate_multi_geometry
        )
        self.configurations[ind].calibration_model.parameters_changed.disconnect(
            self.invalidate_multi_geometry
        )
        self.disconnect_models()
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            self.configuration_ind = len(self.configurations) - 1
        self.connect_models()
        self.invalidate_multi_geometry()
        self.configuration_removed.emit(self.configuration_ind)

    def save(self, filename: str) -> None:
        """Saves the current state of the model in a h5py file.

        The file ending can be chosen freely. Dioptas projects normally use
        the ``.dio`` suffix.
        """
        logger.info("Saving project to %s", filename)
        # Write into a sibling temp file and swap it in atomically: a save
        # that fails partway (or a crash mid-write) can then never destroy
        # the previous project file, and the "unable to truncate a file
        # which is already open" failure mode cannot reach the real file.
        temp_filename = f"{filename}.tmp-{os.getpid()}"
        try:
            f = h5py.File(temp_filename, "w")
            try:
                self._save_into(f)
            finally:
                f.close()
            os.replace(temp_filename, filename)
        finally:
            if os.path.isfile(temp_filename):
                os.remove(temp_filename)

    def _save_into(self, f: h5py.File) -> None:
        # __version__ records which Dioptas wrote the file (informational);
        # format_version is the layout version the loader branches on — see
        # dioptas/model/state/hdf5.py for the versioning policy
        f.attrs["__version__"] = __version__
        f.attrs["format_version"] = PROJECT_FORMAT_VERSION
        save_project(self, f)

    def load(self, filename: str) -> None:
        """Loads a previously saved model (see save function) from an h5py file."""
        logger.info("Loading project from %s", filename)

        # refuse old files before touching the current session, so a refusal
        # never leaves a half-loaded state behind
        with h5py.File(filename, "r") as probe:
            format_version = int(probe.attrs.get("format_version", 0))
        if format_version < PROJECT_FORMAT_VERSION:
            raise UnsupportedProjectFileError(
                f"{os.path.basename(filename)} was written by Dioptas 0.8.7 "
                "or earlier. The project layout changed with the state "
                "migration; please open the file with the Dioptas version "
                "that wrote it (older releases stay available on PyPI and "
                "GitHub) and re-export what you need."
            )

        self.disconnect_models()

        # close the file even when loading fails partway — a leaked open
        # handle blocks any later save of the same file
        f = h5py.File(filename, "r")
        try:
            # a loaded project is a starting point, not an edit: undoing back
            # into the previous session's state would be surprising
            with self.history.suspended():
                self._load_from(f)
        finally:
            f.close()
        self.history.reset()

    def _load_from(self, f: h5py.File) -> None:
        format_version = int(f.attrs.get("format_version", 0))
        if format_version > PROJECT_FORMAT_VERSION:
            logger.warning(
                "Project file %s has format_version %d, newer than supported %d "
                "— loading best-effort, some settings may be missed",
                f.filename,
                format_version,
                PROJECT_FORMAT_VERSION,
            )

        self.delete_configurations()
        load_project(self, f, Configuration)

    def attach_configuration(self, configuration: Configuration) -> None:
        """Adds an already-built configuration and wires its signals.

        Used by project loading, which constructs configurations from the
        file rather than through add_configuration (that one copies the
        current calibration and selects the new configuration).
        """
        configuration.calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )
        configuration.calibration_model.parameters_changed.connect(
            self.invalidate_multi_geometry
        )
        self._combined_cake.add_dependency(configuration.cake_changed)
        self.configurations.append(configuration)

    def select_configuration(self, ind: int) -> None:
        """Selects a configuration specified by the index as current model.

        This will reemit all needed signals, so that the GUI can update accordingly.
        """
        if 0 <= ind < len(self.configurations):
            self.disconnect_models()
            self.configuration_ind = ind
            self.connect_models()
            self.configuration_selected.emit(ind)
            # suppress integrations indirectly triggered by GUI handlers of
            # the re-emitted signals — nothing changed, we only re-render
            with self.current_configuration.pattern_integration.hold(
                flush=False
            ), self.current_configuration.cake_integration.hold(flush=False):
                self.img_changed.emit()
                self.mask_changed.emit()
            self.pattern_changed.emit()
            self.cake_changed.emit()

    def disconnect_models(self) -> None:
        """Disconnects signals of the currently selected configuration."""
        self.img_model.img_changed.disconnect(self.img_changed)
        self.mask_model.mask_changed.disconnect(self.mask_changed)
        self.pattern_model.pattern_changed.disconnect(self.pattern_changed)
        self.current_configuration.cake_changed.disconnect(self.cake_changed)
        self.current_configuration.params.events.disconnect(
            self._on_configuration_params_event, missing_ok=True
        )
        self.img_model.params.events.disconnect(
            self._on_img_params_event, missing_ok=True
        )
        self.pattern_model.params.events.disconnect(
            self._on_pattern_params_event, missing_ok=True
        )
        self.mask_model.params.events.disconnect(
            self._on_mask_params_event, missing_ok=True
        )
        self.calibration_model.params.events.disconnect(
            self._on_calibration_params_event, missing_ok=True
        )
        self.map_model.params.events.disconnect(
            self._on_map_params_event, missing_ok=True
        )
        self.map_model.roi_params_changed.disconnect(self._on_map_roi_params_changed)

    def connect_models(self) -> None:
        """Connects signals of the currently selected configuration."""
        self.img_model.img_changed.connect(self.img_changed, priority=True)
        self.mask_model.mask_changed.connect(self.mask_changed)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)
        self.current_configuration.cake_changed.connect(self.cake_changed)
        self.current_configuration.params.events.connect(
            self._on_configuration_params_event
        )
        self.img_model.params.events.connect(self._on_img_params_event)
        self.pattern_model.params.events.connect(self._on_pattern_params_event)
        self.mask_model.params.events.connect(self._on_mask_params_event)
        self.calibration_model.params.events.connect(
            self._on_calibration_params_event
        )
        self.map_model.params.events.connect(self._on_map_params_event)
        # a map ROI carries its own evented params, which are not part of the
        # MapParams group the line above follows
        self.map_model.roi_params_changed.connect(self._on_map_roi_params_changed)
        # overlays live here, not in the configuration, so the map model gets
        # a resolver instead of a reference
        self.map_model.overlay_lookup = self._map_overlay_lookup

    def _map_overlay_lookup(self, name: str):
        for overlay in self._overlay_model.overlays:
            if overlay.name == name:
                return overlay.x, overlay.y
        return None

    def _on_overlays_changed_for_maps(self, *_args) -> None:
        # reset() deletes the configurations attribute outright and clears
        # the overlays while it is gone — those maps are being discarded,
        # so there is nothing to recompute
        for configuration in getattr(self, "configurations", []):
            configuration.map_model.overlays_changed()

    def _on_map_roi_params_changed(self, field, new, old) -> None:
        self.configuration_params_changed.emit("map.roi." + field, new, old)

    def _on_configuration_params_event(self, info) -> None:
        """Forwards a psygnal EmissionInfo from the current configuration's
        params event group to the store-level signals."""
        field = info.signal.name
        new, old = info.args
        self.configuration_params_changed.emit(field, new, old)
        if field == "integration_unit":
            self.integration_unit_changed.emit(new, old)

    def _on_img_params_event(self, info) -> None:
        new, old = info.args
        self.configuration_params_changed.emit("img." + info.signal.name, new, old)

    def _on_pattern_params_event(self, info) -> None:
        new, old = info.args
        if info.signal.name == "background_overlay_uid":
            # the uid is the state; the Pattern object it names lives in the
            # (global) overlay model, so the resolution happens here
            self._resolve_background_overlay(self.current_configuration)
        self.configuration_params_changed.emit(
            "pattern." + info.signal.name, new, old
        )

    def _resolve_background_overlay(self, configuration) -> None:
        pattern_model = configuration.pattern_model
        uid = pattern_model.params.background_overlay_uid
        if uid is None:
            # not tracked by reference (e.g. an anonymous background restored
            # from an old project file) — leave whatever is set alone
            return
        overlay = self.overlay_model.get_overlay_by_uid(uid) if uid else None
        if pattern_model.background_pattern is not overlay:
            pattern_model.background_pattern = overlay

    def resolve_background_overlays(self) -> None:
        """Re-points every configuration's pattern background at the overlay
        its uid names. Called after bulk state changes (undo restore, project
        load), where the uid may be applied before the overlay exists."""
        for configuration in self.configurations:
            self._resolve_background_overlay(configuration)

    def _on_mask_params_event(self, info) -> None:
        new, old = info.args
        self.configuration_params_changed.emit("mask." + info.signal.name, new, old)

    def _on_calibration_params_event(self, info) -> None:
        new, old = info.args
        self.configuration_params_changed.emit(
            "calibration." + info.signal.name, new, old
        )

    def _on_map_params_event(self, info) -> None:
        new, old = info.args
        self.configuration_params_changed.emit("map." + info.signal.name, new, old)

    def _on_phase_params_event(self, info) -> None:
        new, old = info.args
        self.configuration_params_changed.emit("phase." + info.signal.name, new, old)

    @property
    def history(self):
        """Undo/redo over the settings and masks (see state/snapshot.py)."""
        return self._recorder.history

    @property
    def working_directories(self) -> dict[str, str]:
        return self.current_configuration.working_directories

    @working_directories.setter
    def working_directories(self, new: dict[str, str]) -> None:
        self.current_configuration.working_directories = new

    @property
    def current_configuration(self) -> Configuration:
        return self.configurations[self.configuration_ind]

    @property
    def img_model(self) -> ImgModel:
        return self.configurations[self.configuration_ind].img_model

    @property
    def mask_model(self) -> MaskModel:
        return self.configurations[self.configuration_ind].mask_model

    @property
    def mask_plugin_manager(self):
        return self.configurations[self.configuration_ind].mask_plugin_manager

    @property
    def calibration_model(self) -> CalibrationModel:
        return self.configurations[self.configuration_ind].calibration_model

    @property
    def pattern_model(self) -> PatternModel:
        return self.configurations[self.configuration_ind].pattern_model

    @property
    def overlay_model(self) -> OverlayModel:
        return self._overlay_model

    @property
    def phase_model(self) -> PhaseModel:
        return self._phase_model

    @property
    def batch_model(self) -> BatchModel:
        return self.configurations[self.configuration_ind].batch_model

    @property
    def map_model(self) -> MapModel:
        return self.configurations[self.configuration_ind].map_model

    @property
    def use_mask(self) -> bool:
        return self.configurations[self.configuration_ind].use_mask

    @use_mask.setter
    def use_mask(self, new_val: bool) -> None:
        self.configurations[self.configuration_ind].use_mask = new_val

    @property
    def transparent_mask(self) -> bool:
        return self.configurations[self.configuration_ind].transparent_mask

    @transparent_mask.setter
    def transparent_mask(self, new_val: bool) -> None:
        self.configurations[self.configuration_ind].transparent_mask = new_val

    @property
    def integration_unit(self) -> str:
        return self.current_configuration.integration_unit

    @integration_unit.setter
    def integration_unit(self, new_val: str) -> None:
        self.current_configuration.integration_unit = new_val

    @property
    def img_data(self) -> np.ndarray:
        return self.img_model.img_data

    @property
    def cake_data(self) -> np.ndarray:
        if not self.combine_cakes:
            return self.calibration_model.cake_img
        else:
            return self._cake_data

    @property
    def pattern(self) -> Pattern:
        if not self.combine_patterns:
            return self.pattern_model.pattern
        else:
            return self._integrate_combined_1d()

    @property
    def combine_patterns(self) -> bool:
        return self._combine_patterns

    @combine_patterns.setter
    def combine_patterns(self, new_val: bool) -> None:
        self._combine_patterns = new_val
        self.pattern_changed.emit()

    def save_combined_pattern(self, filename: str) -> None:
        """Saves the current integrated pattern."""
        self.pattern.save(filename, unit=self.integration_unit)

    @property
    def combine_cakes(self) -> bool:
        return self._combine_cakes

    @combine_cakes.setter
    def combine_cakes(self, new_val: bool) -> None:
        self._combine_cakes = new_val
        self._combined_cake.active = new_val
        if new_val:
            self._combined_cake.recompute()
        self.cake_changed.emit()

    def _get_multi_geometry(self, unit: str = "2th_deg") -> MultiGeometry:
        """Returns a cached pyFAI MultiGeometry from all configurations' geometries.

        The MultiGeometry is recreated only when the unit changes or when invalidated.
        """
        if self._multi_geometry is None or self._multi_geometry_unit != unit:
            ais = [
                config.calibration_model.pattern_geometry
                for config in self.configurations
            ]
            self._multi_geometry = MultiGeometry(ais, unit=unit)
            self._multi_geometry_unit = unit
        return self._multi_geometry

    def invalidate_multi_geometry(self) -> None:
        """Invalidates the cached MultiGeometry so it is recreated on next use."""
        self._multi_geometry = None
        self._multi_geometry_unit = None

    def _get_lst_data_and_masks(self) -> tuple[list[np.ndarray], list[np.ndarray | None]]:
        """Collects image data and masks from all configurations."""
        lst_data: list[np.ndarray] = []
        lst_mask: list[np.ndarray | None] = []
        for configuration in self.configurations:
            lst_data.append(configuration.img_model.img_data)
            if configuration.use_mask:
                lst_mask.append(configuration.mask_model.get_mask())
            elif configuration.mask_model.roi is not None:
                lst_mask.append(configuration.mask_model.roi_mask)
            else:
                lst_mask.append(None)
        return lst_data, lst_mask

    def _integrate_combined_1d(self) -> Pattern:
        """Uses pyFAI MultiGeometry to integrate all configurations into a single 1D pattern."""
        unit = self.integration_unit
        mg_unit = "2th_deg" if unit == "d_A" else unit

        mg = self._get_multi_geometry(unit=mg_unit)
        # Reset cached ranges so they're recalculated if geometry changed
        mg.radial_range = None
        mg.azimuth_range = None

        lst_data, lst_mask = self._get_lst_data_and_masks()

        num_points = self.current_configuration.integration_rad_points
        if num_points is None:
            num_points = self.calibration_model.calculate_number_of_pattern_points(
                self.img_model.img_data.shape, 2
            )

        polarization_factor = self.calibration_model.polarization_factor
        correct_solid_angle = self.calibration_model.correct_solid_angle

        result = mg.integrate1d(
            lst_data,
            npt=num_points,
            correctSolidAngle=correct_solid_angle,
            polarization_factor=polarization_factor,
            lst_mask=lst_mask,
        )

        x = result.radial
        y = result.intensity

        if unit == "d_A":
            wavelength = self.calibration_model.pattern_geometry.wavelength
            x = wavelength / (2 * np.sin(x / 360 * np.pi)) * 1e10

        return Pattern(x, y)

    def calculate_combined_cake(self) -> None:
        """Uses pyFAI MultiGeometry to combine cakes from all configurations."""
        self._activate_cake()

        unit = self.integration_unit
        mg_unit = "2th_deg" if unit == "d_A" else unit

        mg = self._get_multi_geometry(unit=mg_unit)
        # Reset cached ranges so they're recalculated if geometry changed
        mg.radial_range = None
        mg.azimuth_range = None

        lst_data, lst_mask = self._get_lst_data_and_masks()

        num_points = self.current_configuration.integration_rad_points
        if num_points is None:
            num_points = self.calibration_model.calculate_number_of_pattern_points(
                self.img_model.img_data.shape, 2
            )

        azimuth_points = self.current_configuration.cake_azimuth_points
        polarization_factor = self.calibration_model.polarization_factor
        correct_solid_angle = self.calibration_model.correct_solid_angle

        result = mg.integrate2d(
            lst_data,
            npt_rad=num_points,
            npt_azim=azimuth_points,
            correctSolidAngle=correct_solid_angle,
            polarization_factor=polarization_factor,
            lst_mask=lst_mask,
        )

        self._cake_data = result.intensity
        self._cake_tth = result.radial
        self._cake_azi = result.azimuthal

    def _activate_cake(self) -> None:
        """Activates cake integration in all configurations."""
        for configuration in self.configurations:
            if not configuration.auto_integrate_cake:
                configuration.auto_integrate_cake = True
                configuration.integrate_image_2d()

    @property
    def cake_tth(self) -> np.ndarray | None:
        if not self.combine_cakes:
            return self.calibration_model.cake_tth
        else:
            return self._cake_tth

    @property
    def cake_azi(self) -> np.ndarray | None:
        if not self.combine_cakes:
            return self.calibration_model.cake_azi
        else:
            return self._cake_azi

    def reset(self) -> None:
        """Resets the state of the model.

        It only remembers the current working directories of the currently selected
        configuration. Everything else including all configurations is deleted.
        """
        working_directories = self.working_directories
        self.disconnect_models()
        self.delete_configurations()
        self.configurations = [Configuration()]
        self.configurations[0].calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )
        self.configurations[0].calibration_model.parameters_changed.connect(
            self.invalidate_multi_geometry
        )
        self._combined_cake.add_dependency(self.configurations[0].cake_changed)
        self.configuration_ind = 0
        self.overlay_model.reset()
        self.phase_model.reset()
        self.invalidate_multi_geometry()
        self.connect_models()
        self.working_directories = working_directories
        self.configuration_removed.emit(0)
        self.configuration_selected.emit(0)
        self.img_model.img_changed.emit()
        # without this the mask views keep showing the deleted mask
        self.mask_changed.emit()
        self.pattern_model.pattern_changed.emit()

    def delete_configurations(self) -> None:
        """Deletes all configurations currently present in the model."""
        for configuration in self.configurations:
            configuration.calibration_model.pattern_geometry.reset()
            if configuration.calibration_model.cake_geometry is not None:
                configuration.calibration_model.cake_geometry.reset()
            del configuration.calibration_model.cake_geometry
            del configuration.calibration_model.pattern_geometry
            del configuration.img_model
            del configuration.mask_model
        del self.configurations

    def next_image(self, pos: int | None = None) -> None:
        """Loads the next image for each configuration if it exists.

        The pos parameter is the position of the number in terms of numbers present
        in the filename string (not string position).
        """
        with self._combined_cake.hold():
            for configuration in self.configurations:
                configuration.img_model.load_next_file(pos=pos)

    def previous_image(self, pos: int | None = None) -> None:
        """Loads the previous image for each configuration if it exists.

        The pos parameter is the position of the number in terms of numbers present
        in the filename string (not string position).
        """
        with self._combined_cake.hold():
            for configuration in self.configurations:
                configuration.img_model.load_previous_file(pos=pos)

    def next_folder(self, mec_mode: bool = False) -> None:
        """Loads an image in the next folder with the same filename.

        This assumes that the folders are sorted with run numbers, e.g. run101, run102, etc.
        If mec_mode is True, accounts for the MEC beamline at LCLS-SLAC where filenames
        also include the run number.
        """
        with self._combined_cake.hold():
            for configuration in self.configurations:
                configuration.img_model.load_next_folder(mec_mode=mec_mode)

    def previous_folder(self, mec_mode: bool = False) -> None:
        """Loads an image in the previous folder with the same filename.

        This assumes that the folders are sorted with run numbers, e.g. run101, run102, etc.
        If mec_mode is True, accounts for the MEC beamline at LCLS-SLAC where filenames
        also include the run number.
        """
        with self._combined_cake.hold():
            for configuration in self.configurations:
                configuration.img_model.load_previous_folder(mec_mode=mec_mode)

    def blockSignals(self, block: bool = True) -> None:
        for member in vars(self):
            attr = getattr(self, member)
            if isinstance(attr, Signal):
                attr.blocked = block

    def update_clicked_tth(self, tth: float) -> None:
        self.clicked_tth = tth

    def update_clicked_azi(self, azi: float) -> None:
        self.clicked_azi = azi
