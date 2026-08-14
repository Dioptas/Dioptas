# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import numpy as np

from .util import Signal
from .state import apply_params, ConfigurationParams, Derived
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

logger = logging.getLogger(__name__)


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
        # the corrections reconcile lives here rather than in ImgModel:
        # rebuilding a correction needs the calibration's tth/azi arrays,
        # and Configuration is what owns both models
        self._reconciling_corrections = False
        self.img_model.params.events.connect(self._on_img_params_changed)

    def _on_img_params_changed(self, info) -> None:
        if info.signal.name == "corrections" and not self._reconciling_corrections:
            self._reconcile_corrections()

    def _reconcile_corrections(self) -> None:
        """Makes the active corrections follow ImgParams.corrections.

        Interactive adds/removes sync the params at their end, which this
        recognizes as already reconciled (per-name scalar comparison). A
        correction that cannot be rebuilt — a reference image that has moved,
        or no calibration for the tth/azi grids — is logged and dropped from
        the params, so the state never claims a correction that is not
        applied."""
        from .ImgModel import scalar_correction_params

        # delete/add below sync the params mid-way through; reacting to those
        # intermediate writes would restart the reconcile against a target
        # that is no longer the one being applied
        self._reconciling_corrections = True
        try:
            wanted = dict(self.img_model.params.corrections)
            live = self.img_model.img_corrections.corrections

            for name in [n for n in live if n not in wanted]:
                self.img_model.delete_img_correction(name)

            for name, params in wanted.items():
                existing = live.get(name)
                if existing is not None and (
                    scalar_correction_params(existing) == params
                ):
                    continue
                try:
                    correction = self._build_correction(name, dict(params))
                except Exception:
                    logger.exception("Failed to rebuild the %s correction", name)
                    correction = None
                if correction is not None:
                    self.img_model.add_img_correction(correction, name)

            # one settled sync at the end: params mirror what is actually
            # applied, including anything that could not be rebuilt
            self.img_model._sync_correction_params()
        finally:
            self._reconciling_corrections = False

    def _build_correction(self, name: str, params: dict):
        """Constructs a correction object from its scalar parameters — the
        one recipe shared by the params reconcile and the project loader.
        Returns None when the inputs for the rebuild are not available."""
        if name in ("cbn", "oiadac", "slab", "cylinder", "sphere", "plate"):
            if self.calibration_model.tth_array is None:
                return None
            tth_array = 180.0 / np.pi * self.calibration_model.tth_array
            azi_array = 180.0 / np.pi * self.calibration_model.azi_array
            correction_classes = {
                "cbn": CbnCorrection,
                "oiadac": ObliqueAngleDetectorAbsorptionCorrection,
                "slab": SlabAbsorptionCorrection,
                "cylinder": CylinderAbsorptionCorrection,
                "sphere": SphereAbsorptionCorrection,
                "plate": PlateAbsorptionCorrection,
            }
            correction = correction_classes[name](
                tth_array=tth_array, azi_array=azi_array
            )
            correction.set_params(params)
            correction.update()
            return correction
        if name == "transfer":
            correction = self.img_model.transfer_correction
            if params.get("original_data") is not None:
                # legacy loader path: the arrays travel in the project file
                correction.set_params(params)
                return correction
            current = correction.get_params()
            if (
                current.get("original_data") is None
                or current.get("original_filename") != params["original_filename"]
                or current.get("response_filename") != params["response_filename"]
            ):
                # scalar-only params (undo, params doc): re-read the files
                correction.load_original_image(params["original_filename"])
                correction.load_response_image(params["response_filename"])
            return correction
        if name == "flat_field":
            correction = self.img_model.flat_field_correction
            if params.get("raw_data") is not None:
                correction.set_params(params)
            else:
                correction.load(params["filename"])
            return correction
        logger.warning("Unknown image correction type: %s", name)
        return None

    def _on_own_params_changed(self, info) -> None:
        field = info.signal.name
        if field == "integration_rad_points":
            self.pattern_integration.recompute()
            self.cake_integration.invalidate()
        elif field in ("cake_azimuth_points", "cake_azimuth_range"):
            self.cake_integration.invalidate()
        elif field == "oned_azimuth_range":
            self.pattern_integration.invalidate()
        elif field == "calculate_poisson_errors":
            # Enabling needs a new integration to produce sigma. Disabling
            # only affects future integrations; the current pattern can keep
            # the errors already calculated for it.
            if info.args[0]:
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

            integration_kwargs = dict(
                azi_range=self.oned_azimuth_range,
                mask=mask,
                unit=self.integration_unit,
                num_points=self.integration_rad_points,
                trim_zeros=self.trim_trailing_zeros,
            )
            if self.calculate_poisson_errors:
                integration_kwargs["calculate_errors"] = True
            x, y = self.calibration_model.integrate_1d(**integration_kwargs)

            if update_pattern_model:
                self.pattern_model.set_pattern(
                    x,
                    y,
                    self.img_model.filename,
                    unit=self.integration_unit,
                    errors=(
                        self.calibration_model.sigma
                        if self.calculate_poisson_errors
                        else None
                    ),
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
        """Save the current integrated pattern.

        The output format is selected from the filename suffix. Supported
        suffixes are ``.xy``, ``.xye``, ``.chi``, ``.dat``, and ``.fxye``.
        """
        logger.info("Saving pattern to %s", filename)
        if filename is None:
            filename = self.img_model.filename

        if filename.endswith((".xy", ".xye")):
            header = self._create_xy_header()
            if filename.endswith(".xye"):
                header += "\t sigma"
            self.pattern_model.save_pattern(
                filename,
                header=header,
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
        """Save the current fitted background as a pattern.

        The output format is selected from the filename suffix. Supported
        suffixes are ``.xy``, ``.chi``, ``.dat``, and ``.fxye``.
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
    def calculate_poisson_errors(self) -> bool:
        return self.params.calculate_poisson_errors

    @calculate_poisson_errors.setter
    def calculate_poisson_errors(self, new_value: bool) -> None:
        self.params.calculate_poisson_errors = new_value

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
