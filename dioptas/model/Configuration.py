# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import numpy as np
import json

from copy import deepcopy

from xypattern import Pattern

from .util import Signal
from .state import (
    apply_params,
    CalibrationParams,
    ConfigurationParams,
    ImgParams,
    MaskParams,
    PatternParams,
    save_params,
    load_params,
    Derived,
)
from .util.ImgCorrection import (
    CbnCorrection,
    ObliqueAngleDetectorAbsorptionCorrection,
    SlabAbsorptionCorrection,
    CylinderAbsorptionCorrection,
    SphereAbsorptionCorrection,
    PlateAbsorptionCorrection,
)

from .util.calc import convert_units
from . import ImgModel, CalibrationModel, MaskModel, PatternModel, BatchModel
from .MaskPluginManager import MaskPluginManager
from .util.plugin_discovery import discover_mask_plugins
from .util.mask_plugins import BUILTIN_MASK_PLUGINS
from .MapModel import MapModel
from .CalibrationModel import DetectorModes

import h5py

logger = logging.getLogger(__name__)


def _json_numpy_default(obj: object) -> object:
    """JSON encoder default for numpy scalar and array types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class Configuration:
    """
    The configuration class contains a working combination of an ImgModel, PatternModel, MaskModel and CalibrationModel.
    It does handles the core data manipulation of Dioptas.
    The management of multiple Configurations is done by the DioptasModel.
    """

    def __init__(self, working_directories: dict[str, str] | None = None) -> None:
        super().__init__()

        self.img_model: ImgModel = ImgModel()
        self.mask_model: MaskModel = MaskModel()
        self.mask_plugin_manager: MaskPluginManager = MaskPluginManager()
        self.mask_model.mask_plugin_manager = self.mask_plugin_manager
        self._last_user_mask_sum: int = -1
        self._register_mask_plugins()
        self.calibration_model: CalibrationModel = CalibrationModel(self.img_model)
        self.pattern_model: PatternModel = PatternModel()

        self.batch_model: BatchModel = BatchModel(self)
        self.map_model: MapModel = MapModel(self)

        # All user-settable parameters live in the evented params dataclass;
        # the properties below delegate to it and add side effects
        # (re-integration, signal re-wiring) where needed.
        if working_directories is None:
            self.params: ConfigurationParams = ConfigurationParams()
        else:
            self.params = ConfigurationParams(working_directories=working_directories)

        self.cake_changed: Signal = Signal()
        self._connect_signals()

        # Derived computations: re-run integration when the image changes.
        # `active` mirrors the auto_integrate_* params (the user-facing
        # modes); temporary suppression during bulk operations uses hold().
        # Created after _connect_signals so integration runs after the mask
        # dimension/plugin handlers on img_changed.
        self.pattern_integration: Derived = Derived(
            self.integrate_image_1d,
            dependencies=[self.img_model.img_changed],
            active=self.params.auto_integrate_pattern,
        )
        self.cake_integration: Derived = Derived(
            self.integrate_image_2d,
            dependencies=[self.img_model.img_changed],
            active=self.params.auto_integrate_cake,
        )

        # side effects of settings changes live here (not in the property
        # setters), so a direct params write behaves exactly like the
        # property write — no matter who writes (GUI, script, pipeline).
        # Subscribed before DioptasModel's store forwarding, so reactions
        # run before the GUI is notified.
        self.params.events.connect(self._on_own_params_changed)
        self.calibration_model.params.events.connect(
            self._on_calibration_params_changed
        )

    def _on_own_params_changed(self, info) -> None:
        field = info.signal.name
        if field == "integration_rad_points":
            self.pattern_integration.recompute()
            self.cake_integration.invalidate()
        elif field in ("cake_azimuth_points", "cake_azimuth_range"):
            self.cake_integration.invalidate()
        elif field == "oned_azimuth_range":
            self.pattern_integration.invalidate()
        elif field == "integration_unit":
            new_unit, old_unit = info.args
            self._on_integration_unit_changed(new_unit, old_unit)
        elif field == "auto_integrate_pattern":
            self.pattern_integration.active = info.args[0]
        elif field == "auto_integrate_cake":
            self.cake_integration.active = info.args[0]

    def _on_calibration_params_changed(self, info) -> None:
        if info.signal.name == "correct_solid_angle":
            self.pattern_integration.invalidate()
            self.cake_integration.invalidate()

    def _on_integration_unit_changed(self, new_unit: str, old_unit: str) -> None:
        pattern = self.pattern_model.pattern
        x = getattr(pattern, "x", None)
        valid_units = {"2th_deg", "q_A^-1", "d_A"}
        if old_unit not in valid_units or new_unit not in valid_units:
            return
        if x is not None and len(x) > 1:
            pattern.transform_x(
                lambda x: convert_units(
                    x, self.calibration_model.wavelength, old_unit, new_unit
                )
            )
            self.pattern_integration.recompute()

    def _connect_signals(self) -> None:
        """Connects the img_changed signal to responding functions."""
        self.img_model.img_changed.connect(self.update_mask_dimension)
        self.img_model.img_changed.connect(self._update_plugin_masks)
        self.mask_plugin_manager.mask_changed.connect(
            self.mask_model.mask_changed.emit
        )

    def _update_plugin_masks(self) -> None:
        """Update dynamic mask plugins with the current image data."""
        if self.img_model.img_data is not None:
            # Pass user-drawn mask so plugins can exclude pre-masked pixels
            # (e.g., detector gaps) from their statistics.
            user_mask = self.mask_model.get_img()
            # Update sum FIRST: any signals emitted from update_geometry or
            # update_image will trigger plot_mask -> update_plugin_existing_mask,
            # which must see the current sum to break the recursion cycle.
            self._last_user_mask_sum = int(user_mask.sum())
            self._update_plugin_geometry()
            self.mask_plugin_manager.update_image(
                self.img_model.img_data, existing_mask=user_mask
            )

    def update_plugin_existing_mask(self) -> None:
        """Recompute plugin masks if the user-drawn mask changed.

        Called by the MaskController after mask operations. Only triggers a
        full plugin recomputation if the user mask actually changed, avoiding
        redundant work when called from plugin-triggered mask_changed signals.
        """
        if self.img_model.img_data is None:
            return
        current_sum = int(self.mask_model.get_img().sum())
        if current_sum != self._last_user_mask_sum:
            self._update_plugin_masks()

    def _update_plugin_geometry(self) -> None:
        """Build GeometryContext from calibration and pass to plugin manager."""
        from .util.MaskPlugin import GeometryContext

        if not self.calibration_model.is_calibrated:
            self.mask_plugin_manager.update_geometry(None)
            return

        try:
            geo = self.calibration_model.pattern_geometry
            img_shape = self.img_model.img_data.shape
            geometry = GeometryContext(
                tth_array=geo.center_array(img_shape, unit="2th_rad"),
                azi_array=geo.center_array(img_shape, unit="chi_rad"),
                dist=geo.dist,
                wavelength=geo.wavelength,
                poni1=geo.poni1,
                poni2=geo.poni2,
                rot1=geo.rot1,
                rot2=geo.rot2,
                rot3=geo.rot3,
                pixel1=geo.detector.pixel1,
                pixel2=geo.detector.pixel2,
            )
            self.mask_plugin_manager.update_geometry(geometry)
        except Exception:
            logger.debug(
                "Failed to build geometry context for mask plugins", exc_info=True
            )
            self.mask_plugin_manager.update_geometry(None)

    def _register_mask_plugins(self) -> None:
        """Register built-in and discovered mask plugins."""
        for plugin_cls in BUILTIN_MASK_PLUGINS:
            try:
                self.mask_plugin_manager.register(plugin_cls())
            except Exception:
                logger.exception("Failed to instantiate built-in mask plugin: %s", plugin_cls)

        for plugin_cls in discover_mask_plugins():
            try:
                self.mask_plugin_manager.register(plugin_cls())
            except Exception:
                logger.exception("Failed to instantiate mask plugin: %s", plugin_cls)

    def integrate_image_1d(self, update_pattern_model: bool = True) -> tuple[np.ndarray, np.ndarray] | None:
        """
        Integrates the image in the ImageModel to a Pattern. Will also automatically save the integrated pattern, if
        auto_save_integrated is True.

        :param update_pattern_model: If True, updates pattern_model and emits pattern_changed signal.
            Set to False during batch/map integration to avoid unnecessary GUI updates.
        """
        logger.debug("Integrating image 1D")
        if self.calibration_model.is_calibrated:
            if self.use_mask:
                mask = self.mask_model.get_mask()
            elif self.mask_model.roi is not None:
                mask = self.mask_model.roi_mask
            else:
                mask = None

            x, y = self.calibration_model.integrate_1d(
                azi_range=self.oned_azimuth_range,
                mask=mask,
                unit=self.integration_unit,
                num_points=self.integration_rad_points,
                trim_zeros=self.trim_trailing_zeros,
            )

            if update_pattern_model:
                self.pattern_model.set_pattern(
                    x, y, self.img_model.filename, unit=self.integration_unit
                )

                if self.auto_save_integrated_pattern:
                    self._auto_save_patterns()

            return x, y

    def integrate_image_2d(self) -> None:
        """Integrates the image in the ImageModel to a Cake."""
        logger.debug("Integrating image 2D (cake)")
        if self.use_mask:
            mask = self.mask_model.get_mask()
        elif self.mask_model.roi is not None:
            mask = self.mask_model.roi_mask
        else:
            mask = None

        self.calibration_model.integrate_2d(
            mask=mask,
            rad_points=self.params.integration_rad_points,
            azimuth_points=self.params.cake_azimuth_points,
            azimuth_range=self.params.cake_azimuth_range,
        )

        self.cake_changed.emit()

    def save_pattern(self, filename: str | None = None, subtract_background: bool = False) -> None:
        """
        Saves the current integrated pattern. The format depends on the file ending. Possible file formats:
            [*.xy, *.chi, *.dat, *.fxye]
        """
        logger.info("Saving pattern to %s", filename)
        if filename is None:
            filename = self.img_model.filename

        if filename.endswith(".xy"):
            self.pattern_model.save_pattern(
                filename,
                header=self._create_xy_header(),
                subtract_background=subtract_background,
            )
        elif filename.endswith(".fxye"):
            self.pattern_model.save_pattern(
                filename,
                header=self._create_fxye_header(filename),
                subtract_background=subtract_background,
            )
        else:
            self.pattern_model.save_pattern(
                filename, subtract_background=subtract_background
            )

    def save_background_pattern(self, filename: str | None = None) -> None:
        """
        Saves the current fit background as a pattern. The format depends on the file ending. Possible file formats:
            [*.xy, *.chi, *.dat, *.fxye]
        """
        if filename is None:
            filename = self.img_model.filename

        if filename.endswith(".xy"):
            self.pattern_model.save_auto_background_as_pattern(
                filename, header=self._create_xy_header()
            )
        elif filename.endswith(".fxye"):
            self.pattern_model.save_auto_background_as_pattern(
                filename, header=self._create_fxye_header(filename)
            )
        else:
            self.pattern_model.save_pattern(filename)

    def _create_xy_header(self) -> str:
        """Creates the header for the xy file format (contains information about calibration parameters)."""
        header = self.calibration_model.create_file_header()
        header = header.replace("\r\n", "\n")
        header = header + "\n#\n# " + self.params.integration_unit + "\t I"
        return header

    def _create_fxye_header(self, filename: str) -> str:
        """Creates the header for the fxye file format (used by GSAS and GSAS-II) containing the calibration information."""
        header = "Generated file " + filename + " using DIOPTAS\n"
        header = header + self.calibration_model.create_file_header()
        unit = self.params.integration_unit
        lam = self.calibration_model.wavelength
        if unit == "q_A^-1":
            con = "CONQ"
        else:
            con = "CONS"

        header = (
            header
            + "\nBANK\t1\tNUM_POINTS\tNUM_POINTS "
            + con
            + "\tMIN_X_VAL\tSTEP_X_VAL "
            + "{0:.5g}".format(lam * 1e10)
            + " 0.0 FXYE"
        )
        return header

    def _auto_save_patterns(self) -> None:
        """
        Saves the current pattern in the pattern working directory (specified in self.working_directories['pattern'].
        When background subtraction is enabled in the pattern model the pattern will be saved with background
        subtraction and without in another sub-folder. ('bkg_subtracted')
        """
        for file_ending in self.integrated_patterns_file_formats:
            filename = os.path.join(
                self.working_directories["pattern"],
                os.path.basename(str(self.img_model.filename)).split(".")[:-1][0]
                + file_ending,
            )
            filename = filename.replace("\\", "/")
            self.save_pattern(filename, subtract_background=False)

        pattern = self.pattern_model.pattern

        if pattern.background_pattern is not None or pattern.auto_bkg is not None:
            for file_ending in self.integrated_patterns_file_formats:
                directory = os.path.join(
                    self.working_directories["pattern"], "bkg_subtracted"
                )
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(
                    directory, self.pattern_model.pattern.name + file_ending
                )
                filename = filename.replace("\\", "/")
                self.save_pattern(filename, subtract_background=True)

    def update_mask_dimension(self) -> None:
        """Updates the shape of the mask in the MaskModel to the shape of the image in the ImageModel."""
        self.mask_model.set_dimension(self.img_model._img_data.shape)

    @property
    def working_directories(self) -> dict[str, str]:
        return self.params.working_directories

    @working_directories.setter
    def working_directories(self, new: dict[str, str]) -> None:
        self.params.working_directories = new

    @property
    def use_mask(self) -> bool:
        return self.params.use_mask

    @use_mask.setter
    def use_mask(self, new_value: bool) -> None:
        self.params.use_mask = new_value

    @property
    def transparent_mask(self) -> bool:
        return self.params.transparent_mask

    @transparent_mask.setter
    def transparent_mask(self, new_value: bool) -> None:
        self.params.transparent_mask = new_value

    @property
    def trim_trailing_zeros(self) -> bool:
        return self.params.trim_trailing_zeros

    @trim_trailing_zeros.setter
    def trim_trailing_zeros(self, new_value: bool) -> None:
        self.params.trim_trailing_zeros = new_value

    @property
    def auto_save_integrated_pattern(self) -> bool:
        return self.params.auto_save_integrated_pattern

    @auto_save_integrated_pattern.setter
    def auto_save_integrated_pattern(self, new_value: bool) -> None:
        self.params.auto_save_integrated_pattern = new_value

    @property
    def integrated_patterns_file_formats(self) -> list[str]:
        return self.params.integrated_patterns_file_formats

    @integrated_patterns_file_formats.setter
    def integrated_patterns_file_formats(self, new_value: list[str]) -> None:
        self.params.integrated_patterns_file_formats = new_value

    @property
    def integration_rad_points(self) -> int | None:
        return self.params.integration_rad_points

    @integration_rad_points.setter
    def integration_rad_points(self, new_value: int | None) -> None:
        self.params.integration_rad_points = new_value

    @property
    def cake_azimuth_points(self) -> int:
        return self.params.cake_azimuth_points

    @cake_azimuth_points.setter
    def cake_azimuth_points(self, new_value: int) -> None:
        self.params.cake_azimuth_points = new_value

    @property
    def cake_azimuth_range(self) -> list[float] | None:
        return self.params.cake_azimuth_range

    @cake_azimuth_range.setter
    def cake_azimuth_range(self, new_value: list[float] | None) -> None:
        self.params.cake_azimuth_range = new_value

    @property
    def oned_azimuth_range(self) -> list[float] | None:
        return self.params.oned_azimuth_range

    @oned_azimuth_range.setter
    def oned_azimuth_range(self, new_value: list[float] | None) -> None:
        self.params.oned_azimuth_range = new_value

    @property
    def integration_unit(self) -> str:
        return self.params.integration_unit

    @integration_unit.setter
    def integration_unit(self, new_unit: str) -> None:
        self.params.integration_unit = new_unit

    @property
    def correct_solid_angle(self) -> bool:
        return self.calibration_model.correct_solid_angle

    @correct_solid_angle.setter
    def correct_solid_angle(self, new_val: bool) -> None:
        self.calibration_model.correct_solid_angle = new_val

    @property
    def is_calibrated(self) -> bool:
        return self.calibration_model.is_calibrated

    @property
    def auto_integrate_cake(self) -> bool:
        return self.params.auto_integrate_cake

    @auto_integrate_cake.setter
    def auto_integrate_cake(self, new_value: bool) -> None:
        self.params.auto_integrate_cake = new_value

    @property
    def auto_integrate_pattern(self) -> bool:
        return self.params.auto_integrate_pattern

    @auto_integrate_pattern.setter
    def auto_integrate_pattern(self, new_value: bool) -> None:
        self.params.auto_integrate_pattern = new_value

    @property
    def cake_img(self) -> np.ndarray:
        return self.calibration_model.cake_img

    @property
    def roi(self) -> tuple[int, ...] | None:
        return self.mask_model.roi

    @roi.setter
    def roi(self, new_val: tuple[int, ...] | None) -> None:
        self.mask_model.roi = new_val
        self.pattern_integration.recompute()

    def copy(self) -> Configuration:
        """Creates a copy of the current configuration.

        Every settings tree is copied generically, so settings added in the
        future are included automatically."""
        new_configuration = Configuration()

        # suppressed while copying: the explicit integration below runs once
        with new_configuration.pattern_integration.hold(
            flush=False
        ), new_configuration.cake_integration.hold(flush=False):
            apply_params(new_configuration.params, self.params)
            apply_params(new_configuration.img_model.params, self.img_model.params)
            apply_params(new_configuration.mask_model.params, self.mask_model.params)
            apply_params(
                new_configuration.pattern_model.params, self.pattern_model.params
            )
            apply_params(
                new_configuration.calibration_model.params,
                self.calibration_model.params,
            )

            new_configuration.img_model._img_data = self.img_model._img_data

            new_configuration.calibration_model.set_pyFAI(
                self.calibration_model.get_calibration_parameter()[0]
            )
            # the copied supersampling factor only takes effect on the
            # geometry when applied explicitly
            new_configuration.calibration_model.set_supersampling()

        new_configuration.integrate_image_1d()

        return new_configuration

    def save_in_hdf5(self, hdf5_group: h5py.Group) -> None:
        """Saves the configuration group in the given hdf5_group."""

        f = hdf5_group

        # save the params dataclass generically; the legacy field-by-field
        # attributes below are kept so older Dioptas versions can still read
        # the file
        save_params(f, self.params)

        # save general information
        general_information = f.create_group("general_information")
        # integration parameters:
        general_information.attrs["integration_unit"] = self.integration_unit
        if self.integration_rad_points:
            general_information.attrs["integration_num_points"] = (
                self.integration_rad_points
            )
        else:
            general_information.attrs["integration_num_points"] = 0

        # cake parameters:
        general_information.attrs["auto_integrate_cake"] = self.auto_integrate_cake
        general_information.attrs["cake_azimuth_points"] = self.cake_azimuth_points
        if self.cake_azimuth_range is None:
            general_information.attrs["cake_azimuth_range"] = "None"
        else:
            general_information.attrs["cake_azimuth_range"] = self.cake_azimuth_range

        # mask parameters
        general_information.attrs["use_mask"] = self.use_mask
        general_information.attrs["transparent_mask"] = self.transparent_mask

        # auto save parameters
        general_information.attrs["auto_save_integrated_pattern"] = (
            self.auto_save_integrated_pattern
        )
        dt = h5py.string_dtype()
        general_information.create_dataset(
            "integrated_patterns_file_formats",
            data=self.integrated_patterns_file_formats,
            dtype=dt,
        )

        # save working directories
        working_directories_gp = f.create_group("working_directories")
        try:
            for key in self.working_directories:
                working_directories_gp.attrs[key] = self.working_directories[key]
        except TypeError:
            self.working_directories = {
                "calibration": "",
                "mask": "",
                "image": "",
                "pattern": "",
                "overlay": "",
                "phase": "",
                "batch": "",
            }
            for key in self.working_directories:
                working_directories_gp.attrs[key] = self.working_directories[key]

        # save image model
        image_group = f.create_group("image_model")
        save_params(image_group, self.img_model.params)
        image_group.attrs["auto_process"] = self.img_model.autoprocess
        image_group.attrs["factor"] = self.img_model.factor
        image_group.attrs["has_background"] = self.img_model.has_background()
        image_group.attrs["background_filename"] = self.img_model.background_filename
        image_group.attrs["background_offset"] = self.img_model.background_offset
        image_group.attrs["background_scaling"] = self.img_model.background_scaling
        if self.img_model.has_background():
            background_data = self.img_model.untransformed_background_data
            image_group.create_dataset(
                "background_data", background_data.shape, "f", background_data
            )

        image_group.attrs["series_max"] = self.img_model.series_max
        image_group.attrs["series_pos"] = self.img_model.series_pos

        # image corrections
        corrections_group = image_group.create_group("corrections")
        corrections_group.attrs["has_corrections"] = self.img_model.has_corrections()
        for (
            correction,
            correction_object,
        ) in self.img_model.img_corrections.corrections.items():
            if correction in ["cbn", "oiadac", "slab", "cylinder", "sphere", "plate"]:
                correction_data = correction_object.get_data()
                imcd = corrections_group.create_dataset(
                    correction, correction_data.shape, "f", correction_data
                )
                for param, value in correction_object.get_params().items():
                    imcd.attrs[param] = value
            elif correction == "transfer":
                params = correction_object.get_params()
                transfer_group = corrections_group.create_group("transfer")
                original_data = params["original_data"]
                response_data = params["response_data"]
                original_ds = transfer_group.create_dataset(
                    "original_data", original_data.shape, "f", original_data
                )
                original_ds.attrs["filename"] = params["original_filename"]
                response_ds = transfer_group.create_dataset(
                    "response_data", response_data.shape, "f", response_data
                )
                response_ds.attrs["filename"] = params["response_filename"]
            elif correction == "flat_field":
                params = correction_object.get_params()
                ff_group = corrections_group.create_group("flat_field")
                raw_data = params["raw_data"]
                ff_ds = ff_group.create_dataset(
                    "raw_data", raw_data.shape, "f", raw_data
                )
                ff_ds.attrs["filename"] = params["filename"]

        # the actual image
        image_group.attrs["filename"] = self.img_model.filename
        current_raw_image = self.img_model.untransformed_raw_img_data

        raw_image_data = image_group.create_dataset(
            "raw_image_data", current_raw_image.shape, dtype="f"
        )
        raw_image_data[...] = current_raw_image

        # image transformations
        transformations_group = image_group.create_group("image_transformations")
        for ind, transformation in enumerate(
            self.img_model.get_transformations_string_list()
        ):
            transformations_group.attrs[str(ind)] = transformation

        # save roi data
        if self.roi is not None:
            image_group.attrs["has_roi"] = True
            image_group.create_dataset("roi", (4,), "i8", tuple(self.roi))
        else:
            image_group.attrs["has_roi"] = False

        # save mask model (only user-drawn mask, not plugin-generated masks)
        mask_group = f.create_group("mask")
        save_params(mask_group, self.mask_model.params)
        current_mask = self.mask_model.get_img()
        mask_data = mask_group.create_dataset("data", current_mask.shape, dtype=bool)
        mask_data[...] = current_mask

        # save mask plugin state
        plugin_group = mask_group.create_group("plugins")
        for name in self.mask_plugin_manager.plugin_names:
            entry = self.mask_plugin_manager.plugins[name]
            pg = plugin_group.create_group(name)
            pg.attrs["enabled"] = entry.enabled
            settings = entry.plugin.get_settings()
            if settings:
                pg.attrs["settings"] = json.dumps(settings, default=_json_numpy_default)

        # save detector information
        detector_group = f.create_group("detector")
        detector_mode = self.calibration_model.detector_mode
        detector_group.attrs["detector_mode"] = detector_mode.value
        if detector_mode == DetectorModes.PREDEFINED:
            detector_group.attrs["detector_name"] = self.calibration_model.detector.name
        elif detector_mode == DetectorModes.NEXUS:
            detector_group.attrs["nexus_filename"] = (
                self.calibration_model.detector.filename
            )

        # save calibration model
        calibration_group = f.create_group("calibration_model")
        save_params(calibration_group, self.calibration_model.params)
        # version 2.0 is used to indicate that the pyFAI parameters are stored as a json string
        calibration_group.attrs["version"] = "2.0"

        calibration_filename = self.calibration_model.filename
        if calibration_filename.endswith(".poni"):
            base_filename, ext = self.calibration_model.filename.rsplit(".", 1)
        else:
            base_filename = self.calibration_model.filename
            ext = "poni"
        calibration_group.attrs["calibration_filename"] = base_filename + "." + ext

        pyfai_config = self.calibration_model.pattern_geometry.get_config()
        calibration_group.attrs["pyfai_parameters"] = json.dumps(
            pyfai_config, default=_json_numpy_default
        )
        calibration_group.attrs["polarization_factor"] = (
            self.calibration_model.polarization_factor
        )

        calibration_group.attrs["correct_solid_angle"] = self.correct_solid_angle
        calibration_group.attrs["supersampling_factor"] = (
            self.calibration_model.supersampling_factor
        )
        if self.calibration_model.distortion_spline_filename is not None:
            calibration_group.attrs["distortion_spline_filename"] = (
                self.calibration_model.distortion_spline_filename
            )

        # save background pattern and pattern model
        background_pattern_group = f.create_group("background_pattern")
        try:
            background_pattern_x = self.pattern_model.background_pattern._original_x
            background_pattern_y = self.pattern_model.background_pattern._original_y
        except (TypeError, AttributeError):
            background_pattern_x = None
            background_pattern_y = None
        if background_pattern_x is not None and background_pattern_y is not None:
            background_pattern_group.attrs["has_background_pattern"] = True
            bgx = background_pattern_group.create_dataset(
                "x", background_pattern_x.shape, dtype="f"
            )
            bgy = background_pattern_group.create_dataset(
                "y", background_pattern_y.shape, dtype="f"
            )
            bgx[...] = background_pattern_x
            bgy[...] = background_pattern_y
        else:
            background_pattern_group.attrs["has_background_pattern"] = False

        pattern_group = f.create_group("pattern")
        save_params(pattern_group, self.pattern_model.params)
        try:
            pattern_x = self.pattern_model.pattern._original_x
            pattern_y = self.pattern_model.pattern._original_y
        except (TypeError, AttributeError):
            pattern_x = None
            pattern_y = None
        if pattern_x is not None and pattern_y is not None:
            px = pattern_group.create_dataset("x", pattern_x.shape, dtype="f")
            py = pattern_group.create_dataset("y", pattern_y.shape, dtype="f")
            px[...] = pattern_x
            py[...] = pattern_y
        pattern_group.attrs["pattern_filename"] = self.pattern_model.pattern_filename
        pattern_group.attrs["unit"] = self.pattern_model.unit
        pattern_group.attrs["file_iteration_mode"] = (
            self.pattern_model.file_iteration_mode
        )
        pattern_params = self.pattern_model.params
        if pattern_params.auto_bkg_enabled:
            pattern_group.attrs["auto_background_subtraction"] = True
            auto_background_group = pattern_group.create_group(
                "auto_background_settings"
            )
            auto_background_group.attrs["smoothing"] = pattern_params.auto_bkg_smoothing
            auto_background_group.attrs["iterations"] = (
                pattern_params.auto_bkg_iterations
            )
            auto_background_group.attrs["poly_order"] = (
                pattern_params.auto_bkg_poly_order
            )

            if pattern_params.auto_bkg_roi is not None:
                auto_background_group.attrs["x_start"] = pattern_params.auto_bkg_roi[0]
                auto_background_group.attrs["x_end"] = pattern_params.auto_bkg_roi[1]
        else:
            pattern_group.attrs["auto_background_subtraction"] = False

        # save map model
        self.map_model.save_in_hdf5(f)

    def load_from_hdf5(self, hdf5_group: h5py.Group) -> None:
        """Loads a configuration from the specified hdf5_group."""
        # suppress integrations triggered by the many setter calls during
        # loading — the load path integrates explicitly once at the end
        with self.pattern_integration.hold(flush=False), self.cake_integration.hold(
            flush=False
        ):
            self._load_from_hdf5(hdf5_group)

    @staticmethod
    def _apply_saved_params(target, saved, exclude=None) -> None:
        """Applies a params document loaded from a project file, if present."""
        if saved is not None:
            apply_params(target, saved, exclude=exclude)

    def _load_from_hdf5(self, hdf5_group: h5py.Group) -> None:
        f = hdf5_group

        # do not auto-save patterns for integrations during loading; the
        # saved value is restored further down
        self.auto_save_integrated_pattern = False

        # get working directories
        working_directories: dict[str, str] = {}
        for key, value in f.get("working_directories").attrs.items():
            if os.path.isdir(value):
                working_directories[key] = value
            else:
                working_directories[key] = ""
        self.working_directories = working_directories

        # load pyFAI parameters
        try:
            calibration_schema_version = f.get("calibration_model").attrs["version"]
            if calibration_schema_version == "2.0":
                # pyFAI parameters are stored as a json string
                pyfai_config = json.loads(
                    f.get("calibration_model").attrs["pyfai_parameters"]
                )
                self.calibration_model.set_pyFAI_config(pyfai_config)

                # polarization factor is stored as an attribute (for some reason not in the pyFAI config)
                self.calibration_model.polarization_factor = f.get(
                    "calibration_model"
                ).attrs["polarization_factor"]
        except (KeyError, ValueError):
            # if the version is not set, we assume that the pyFAI parameters are stored in the old way
            # pyFAI parameters are stored as attributes of the group
            # this is the old way of storing pyFAI parameters
            # and is kept for backwards compatibility
            pyfai_parameters: dict[str, object] = {}
            pyfai_parameters_group = f.get("calibration_model").get("pyfai_parameters")
            if pyfai_parameters_group is not None:
                for key, value in pyfai_parameters_group.attrs.items():
                    pyfai_parameters[key] = value

            try:
                if pyfai_parameters:
                    self.calibration_model.set_pyFAI(pyfai_parameters)

            except (KeyError, ValueError):
                logger.warning("Problem with saved pyFAI calibration parameters")

        filename = f.get("calibration_model").attrs["calibration_filename"]
        (_, base_name) = os.path.split(filename)
        self.calibration_model.filename = filename
        self.calibration_model.calibration_name = base_name

        try:
            self.correct_solid_angle = bool(
                f.get("calibration_model").attrs["correct_solid_angle"]
            )
        except KeyError:
            logger.debug("Optional field 'correct_solid_angle' not found in project file")

        try:
            self.calibration_model.set_supersampling(
                int(f.get("calibration_model").attrs["supersampling_factor"])
            )
        except KeyError:
            logger.debug("Optional field 'integration_unit' not found in project file")

        try:
            distortion_spline_filename = f.get("calibration_model").attrs[
                "distortion_spline_filename"
            ]
            self.calibration_model.load_distortion(distortion_spline_filename)
        except KeyError:
            logger.debug("Optional field 'integration_rad_points' not found in project file")

        # load detector definition
        try:
            detector_mode = f.get("detector").attrs["detector_mode"]
            if detector_mode == DetectorModes.PREDEFINED.value:
                detector_name = f.get("detector").attrs["detector_name"]
                self.calibration_model.load_detector(detector_name)
            elif detector_mode == DetectorModes.NEXUS.value:
                nexus_filename = f.get("detector").attrs["nexus_filename"]
                self.calibration_model.load_detector_from_file(nexus_filename)
        except AttributeError:  # to ensure backwards compatibility
            pass

        # load img_model
        self.img_model._img_data = np.copy(
            f.get("image_model").get("raw_image_data")[...]
        )
        filename = f.get("image_model").attrs["filename"]
        self.img_model.filename = filename

        try:
            self.img_model.file_name_iterator.update_filename(filename)
            self.img_model._directory_watcher.path = os.path.dirname(filename)
        except EnvironmentError:
            logger.warning("Could not load mask file from project")

        self.img_model.autoprocess = bool(f.get("image_model").attrs["auto_process"])
        self.img_model.autoprocess_changed.emit()
        self.img_model.factor = f.get("image_model").attrs["factor"]
        # announce the restored image data explicitly (detector shape sync,
        # plugin masks); historically this rode on the factor write above,
        # which no longer emits when the value is unchanged
        self.img_model.img_changed.emit()

        try:
            self.img_model.series_max = f.get("image_model").attrs["series_max"]
            self.img_model.series_pos = f.get("image_model").attrs["series_pos"]
        except KeyError:
            logger.debug("Optional field 'supersampling_factor' not found in project file")

        if f.get("image_model").attrs["has_background"]:
            self.img_model.background_data = np.copy(
                f.get("image_model").get("background_data")[...]
            )
            self.img_model.background_filename = f.get("image_model").attrs[
                "background_filename"
            ]
            self.img_model.background_scaling = f.get("image_model").attrs[
                "background_scaling"
            ]
            self.img_model.background_offset = f.get("image_model").attrs[
                "background_offset"
            ]

        # load image transformations
        transformation_group = f.get("image_model").get("image_transformations")
        transformation_list: list[str] = []
        for key, transformation in transformation_group.attrs.items():
            transformation_list.append(transformation)
        self.calibration_model.load_transformations_string_list(transformation_list)
        self.img_model.load_transformations_string_list(transformation_list)

        # load roi data
        if f.get("image_model").attrs["has_roi"]:
            self.roi = tuple(f.get("image_model").get("roi")[...])

        # load mask model
        self.mask_model.set_mask(np.copy(f.get("mask").get("data")[...]))

        # load mask plugin state
        mask_group = f.get("mask")
        if mask_group is not None and "plugins" in mask_group:
            plugin_group = mask_group["plugins"]
            for name in plugin_group:
                pg = plugin_group[name]
                if name in self.mask_plugin_manager.plugins:
                    enabled = bool(pg.attrs.get("enabled", False))
                    settings_json = pg.attrs.get("settings")
                    if settings_json:
                        settings = json.loads(settings_json)
                        self.mask_plugin_manager.update_plugin_settings(name, settings)
                    self.mask_plugin_manager.set_enabled(name, enabled)

        # load pattern model
        if f.get("pattern").get("x") and f.get("pattern").get("y"):
            self.pattern_model.set_pattern(
                f.get("pattern").get("x")[...],
                f.get("pattern").get("y")[...],
                f.get("pattern").attrs["pattern_filename"],
                f.get("pattern").attrs["unit"],
            )
            self.pattern_model.file_iteration_mode = f.get("pattern").attrs[
                "file_iteration_mode"
            ]
        self.integration_unit = f.get("general_information").attrs["integration_unit"]

        if f.get("background_pattern").attrs["has_background_pattern"]:
            self.pattern_model.background_pattern = Pattern(
                f.get("background_pattern").get("x")[...],
                f.get("background_pattern").get("y")[...],
                "background_pattern",
            )

        if f.get("pattern").attrs["auto_background_subtraction"]:
            auto_background_group = f.get("pattern").get("auto_background_settings")
            pattern_params = self.pattern_model.params
            pattern_params.auto_bkg_smoothing = auto_background_group.attrs["smoothing"]
            pattern_params.auto_bkg_iterations = auto_background_group.attrs[
                "iterations"
            ]
            pattern_params.auto_bkg_poly_order = auto_background_group.attrs[
                "poly_order"
            ]
            if "x_start" in auto_background_group.attrs:
                pattern_params.auto_bkg_roi = [
                    auto_background_group.attrs["x_start"],
                    auto_background_group.attrs["x_end"],
                ]
            pattern_params.auto_bkg_enabled = True

        # load general configuration
        if f.get("general_information").attrs["integration_num_points"]:
            self.integration_rad_points = int(
                f.get("general_information").attrs["integration_num_points"]
            )

        # cake parameters:
        self.auto_integrate_cake = bool(
            f.get("general_information").attrs["auto_integrate_cake"]
        )
        try:
            self.cake_azimuth_points = f.get("general_information").attrs[
                "cake_azimuth_points"
            ]
        except KeyError:
            logger.debug("Optional azimuth range not found in project file")
        try:
            cake_azimuth_range_val = f.get("general_information").attrs["cake_azimuth_range"]
            if isinstance(cake_azimuth_range_val, str) and cake_azimuth_range_val == "None":
                self.cake_azimuth_range = None
            else:
                self.cake_azimuth_range = list(cake_azimuth_range_val)
        except KeyError:
            logger.debug("Optional cake azimuth range not found in project file")

        # mask parameters
        self.use_mask = bool(f.get("general_information").attrs["use_mask"])
        self.transparent_mask = bool(
            f.get("general_information").attrs["transparent_mask"]
        )

        # corrections
        if f.get("image_model").get("corrections").attrs["has_corrections"]:
            for name, correction_group in (
                f.get("image_model").get("corrections").items()
            ):
                params = {}
                for param, val in correction_group.attrs.items():
                    params[param] = val
                if name == "cbn":
                    tth_array = (
                        180.0 / np.pi * self.calibration_model.tth_array
                    )
                    azi_array = (
                        180.0 / np.pi * self.calibration_model.azi_array
                    )
                    cbn_correction = CbnCorrection(
                        tth_array=tth_array, azi_array=azi_array
                    )

                    cbn_correction.set_params(params)
                    cbn_correction.update()
                    self.img_model.add_img_correction(cbn_correction, name)
                elif name == "oiadac":
                    tth_array = (
                        180.0 / np.pi * self.calibration_model.tth_array
                    )
                    azi_array = (
                        180.0 / np.pi * self.calibration_model.azi_array
                    )
                    oiadac = ObliqueAngleDetectorAbsorptionCorrection(
                        tth_array=tth_array, azi_array=azi_array
                    )

                    oiadac.set_params(params)
                    oiadac.update()
                    self.img_model.add_img_correction(oiadac, name)
                elif name in ("slab", "cylinder", "sphere", "plate"):
                    tth_array = (
                        180.0 / np.pi * self.calibration_model.tth_array
                    )
                    azi_array = (
                        180.0 / np.pi * self.calibration_model.azi_array
                    )
                    correction_classes = {
                        "slab": SlabAbsorptionCorrection,
                        "cylinder": CylinderAbsorptionCorrection,
                        "sphere": SphereAbsorptionCorrection,
                        "plate": PlateAbsorptionCorrection,
                    }
                    correction_obj = correction_classes[name](
                        tth_array=tth_array, azi_array=azi_array
                    )
                    correction_obj.set_params(params)
                    correction_obj.update()
                    self.img_model.add_img_correction(correction_obj, name)
                elif name == "transfer":
                    params = {
                        "original_data": correction_group.get("original_data")[...],
                        "original_filename": correction_group.get(
                            "original_data"
                        ).attrs["filename"],
                        "response_data": correction_group.get("response_data")[...],
                        "response_filename": correction_group.get(
                            "response_data"
                        ).attrs["filename"],
                    }

                    self.img_model.transfer_correction.set_params(params)
                    self.img_model.enable_transfer_function()
                elif name == "flat_field":
                    params = {
                        "raw_data": correction_group.get("raw_data")[...],
                        "filename": correction_group.get("raw_data").attrs["filename"],
                    }
                    self.img_model.flat_field_correction.set_params(params)
                    self.img_model.enable_flat_field()

        # autosave parameters
        self.auto_save_integrated_pattern = bool(
            f.get("general_information").attrs["auto_save_integrated_pattern"]
        )
        self.integrated_patterns_file_formats = []
        for file_format in f.get("general_information").get(
            "integrated_patterns_file_formats"
        ):
            # Handle both old ASCII fixed-length (S10) and new variable-length UTF-8 strings
            if isinstance(file_format, np.ndarray):
                val = file_format[0]
            else:
                val = file_format
            if isinstance(val, bytes):
                val = val.decode("utf-8")
            self.integrated_patterns_file_formats.append(str(val))

        # Apply the generic params documents on top of the legacy restore
        # above. Both are written from the same in-memory state by save(),
        # so for every field the legacy layout knows about this is a no-op
        # (equal values emit nothing) — and every field it does NOT know
        # about is restored automatically, with no per-field bookkeeping
        # here. The exclusions below are the fields whose legacy restore is
        # not a plain copy and must win.
        self._apply_saved_params(
            self.params,
            load_params(f, ConfigurationParams),
            # the legacy restore drops working directories that no longer
            # exist on this machine; that validation must not be undone
            exclude={"working_directories"},
        )
        self._apply_saved_params(
            self.img_model.params, load_params(f.get("image_model"), ImgParams)
        )
        self._apply_saved_params(
            self.mask_model.params, load_params(f.get("mask"), MaskParams)
        )
        self._apply_saved_params(
            self.pattern_model.params, load_params(f.get("pattern"), PatternParams)
        )
        self._apply_saved_params(
            self.calibration_model.params,
            load_params(f.get("calibration_model"), CalibrationParams),
            # machine-specific: the effective defaults are computed per
            # machine at construction and must not travel in project files
            exclude={"use_dioptrin", "dioptrin_num_workers"},
        )

        if self.calibration_model.is_calibrated:
            self.integrate_image_1d()
        else:
            self.pattern_model.pattern.recalculate_pattern()

        # load map model
        self.map_model.load_from_hdf5(f)
