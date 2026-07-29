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
from .Configuration import Configuration
from . import (
    ImgModel,
    CalibrationModel,
    MaskModel,
    PhaseModel,
    PatternModel,
    OverlayModel,
    MapModel,
    BatchModel,
)
from .MapModel import MapModel
from .. import __version__

logger = logging.getLogger(__name__)


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

        File-ending can be chosen as wanted. Usually Dioptas projects are saved as *.dio files.
        """
        logger.info("Saving project to %s", filename)
        # close the file even when saving fails partway — a leaked open
        # handle makes every subsequent save of the same file fail with
        # "unable to truncate a file which is already open"
        f = h5py.File(filename, "w")
        try:
            self._save_into(f)
        finally:
            f.close()

    def _save_into(self, f: h5py.File) -> None:
        # __version__ records which Dioptas wrote the file (informational);
        # format_version is the layout version the loader branches on — see
        # dioptas/model/state/hdf5.py for the versioning policy
        f.attrs["__version__"] = __version__
        f.attrs["format_version"] = PROJECT_FORMAT_VERSION

        save_params(f, self.view, name="view")

        # save configuration
        configurations_group = f.create_group("configurations")
        configurations_group.attrs["selected_configuration"] = self.configuration_ind
        for ind, configuration in enumerate(self.configurations):
            configuration_group = configurations_group.create_group(str(ind))
            configuration.save_in_hdf5(configuration_group)

        # save overlays
        overlay_group = f.create_group("overlays")

        for ind, overlay in enumerate(self.overlay_model.overlays):
            ov = overlay_group.create_group(
                str(ind).zfill(5)
            )  # need to fill the ind string, in order to keep it
            # ordered also for larger numbers of overlays
            save_params(ov, overlay.params)
            ov.attrs["name"] = overlay.name
            x, y = overlay.original_data
            ov.create_dataset("x", x.shape, "f", x)
            ov.create_dataset("y", y.shape, "f", y)
            ov.attrs["scaling"] = overlay.scaling
            ov.attrs["offset"] = overlay.offset
            ov.attrs["color"] = overlay.color
            ov.attrs["visible"] = overlay.visible

        # save phases
        phases_group = f.create_group("phases")
        save_params(phases_group, self.phase_model.params)
        for ind, phase in enumerate(self.phase_model.phases):
            phase_group = phases_group.create_group(str(ind))
            # "item_params": the "params" name is taken by the jcpds params
            save_params(
                phase_group, self.phase_model.item_params[ind], name="item_params"
            )
            phase_group.attrs["name"] = phase._name
            phase_group.attrs["filename"] = phase._filename
            phase_group.attrs["color"] = self.phase_model.phase_colors[ind]
            phase_group.attrs["visible"] = self.phase_model.phase_visible[ind]
            phase_parameter_group = phase_group.create_group("params")
            for key in phase.params:
                if key == "comments":
                    phases_comments_group = phase_group.create_group("comments")
                    for ind, comment in enumerate(phase.params["comments"]):
                        phases_comments_group.attrs[str(ind)] = comment
                else:
                    phase_parameter_group.attrs[key] = phase.params[key]
            phase_reflections_group = phase_group.create_group("reflections")
            for ind, reflection in enumerate(phase.reflections):
                phase_reflection_group = phase_reflections_group.create_group(str(ind))
                phase_reflection_group.attrs["d0"] = reflection.d0
                phase_reflection_group.attrs["d"] = reflection.d
                phase_reflection_group.attrs["intensity"] = reflection.intensity
                phase_reflection_group.attrs["h"] = reflection.h
                phase_reflection_group.attrs["k"] = reflection.k
                phase_reflection_group.attrs["l"] = reflection.l

    def load(self, filename: str) -> None:
        """Loads a previously saved model (see save function) from an h5py file."""
        logger.info("Loading project from %s", filename)
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
        # missing format_version = legacy layout (version 0); newer files
        # load best-effort thanks to the tolerant params layer
        format_version = int(f.attrs.get("format_version", 0))
        if format_version > PROJECT_FORMAT_VERSION:
            logger.warning(
                "Project file %s has format_version %d, newer than supported %d "
                "— loading best-effort, some settings may be missed",
                f.filename,
                format_version,
                PROJECT_FORMAT_VERSION,
            )

        # delete old configurations
        for config in self.configurations:
            del config.img_model
            del config.calibration_model
            del config.mask_model
            import gc

            gc.collect()

        # load_configurations
        self.configurations = []
        for ind, configuration_group in f.get("configurations").items():
            configuration = Configuration()
            configuration.load_from_hdf5(configuration_group)
            configuration.calibration_model.detector_reset.connect(
                self.invalidate_multi_geometry
            )
            configuration.calibration_model.parameters_changed.connect(
                self.invalidate_multi_geometry
            )
            self._combined_cake.add_dependency(configuration.cake_changed)
            self.configurations.append(configuration)
        self.configuration_ind = f.get("configurations").attrs["selected_configuration"]

        self.connect_models()
        self.invalidate_multi_geometry()
        self.configuration_added.emit()
        self.select_configuration(self.configuration_ind)

        # load phase model
        for ind, phase_group in f.get("phases").items():
            if ind == "params":  # the generic params group is not a phase
                continue
            new_jcpds = jcpds()
            new_jcpds.name = phase_group.attrs.get("name")
            new_jcpds.filename = phase_group.attrs.get("filename")
            for p_key, p_value in phase_group.get("params").attrs.items():
                new_jcpds.params[p_key] = p_value
            for c_key, comment in phase_group.get("comments").attrs.items():
                new_jcpds.params["comments"].append(comment)
            for r_key, reflection in phase_group.get("reflections").items():
                new_jcpds.add_reflection(
                    reflection.attrs["h"],
                    reflection.attrs["k"],
                    reflection.attrs["l"],
                    reflection.attrs["intensity"],
                    reflection.attrs["d"],
                )
            new_jcpds.params["modified"] = bool(
                phase_group.get("params").attrs["modified"]
            )
            self.phase_model.phase_files.append(new_jcpds.filename)
            self.phase_model.add_jcpds_object(new_jcpds)
            phase_ind = len(self.phase_model.phases) - 1
            try:
                self.phase_model.set_color(
                    phase_ind, np.array(phase_group.attrs["color"])
                )
                self.phase_model.set_phase_visible(
                    phase_ind, bool(phase_group.attrs["visible"])
                )
            except KeyError:
                logger.debug("Optional phase data not found in project file")

        # load overlay model
        for ind, overlay_group in f.get("overlays").items():
            self.overlay_model.add_overlay(
                overlay_group.get("x")[...],
                overlay_group.get("y")[...],
                overlay_group.attrs["name"],
            )
            index = len(self.overlay_model.overlays) - 1
            self.overlay_model.set_overlay_offset(index, overlay_group.attrs["offset"])
            self.overlay_model.set_overlay_scaling(
                index, overlay_group.attrs["scaling"]
            )
            try:
                self.overlay_model.set_overlay_color(
                    index, overlay_group.attrs["color"]
                )
                self.overlay_model.set_overlay_visible(
                    index, bool(overlay_group.attrs["visible"])
                )
            except KeyError:
                logger.debug("Optional overlay data not found in project file")

        # phase settings absent from the legacy layout
        saved_phase_params = load_params(f.get("phases"), PhaseParams)
        if saved_phase_params is not None:
            self.phase_model.params.same_conditions = (
                saved_phase_params.same_conditions
            )

        # apply saved view state last, field-wise onto the stable instance so
        # subscribed controllers react through the change events
        saved_view = load_params(f, ViewParams, name="view")
        if saved_view is not None:
            apply_params(self.view, saved_view)

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
        self.configuration_params_changed.emit(
            "pattern." + info.signal.name, new, old
        )

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
