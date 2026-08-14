# SPDX-License-Identifier: MIT

"""Headless scripting API for Dioptas.

Provides a Pipeline class that wraps the Dioptas model layer,
enabling integration of XRD images from scripts and Jupyter notebooks
without requiring the GUI.

Example usage::

    from dioptas.pipeline import Pipeline

    # Load full setup from a Dioptas project file
    p = Pipeline.from_project("experiment.dio")

    # Override mask for this run
    p.load_mask("new_beamstop.mask")

    # Integrate a single image
    pattern = p.integrate("sample_001.tiff")
    pattern.save("sample_001.xy")

    # Batch integrate
    patterns = p.integrate_batch("data/*.tiff")
"""

import glob
import os

import numpy as np
from xypattern import Pattern


class Pipeline:
    """Headless API for Dioptas XRD image processing.

    A Pipeline wraps a Dioptas Configuration (calibration, mask,
    corrections, integration parameters) and provides methods to
    integrate images without the GUI.
    """

    def __init__(self):
        """Create an empty pipeline.

        Configure manually via :meth:`load_calibration`,
        :meth:`load_mask`, etc.
        """
        from dioptas.model.Configuration import Configuration

        self._configuration = Configuration()
        self._configuration.auto_integrate_pattern = False
        self._configuration.auto_integrate_cake = False
        self._configuration.auto_save_integrated_pattern = False

    @classmethod
    def from_project(cls, filename: str) -> "Pipeline":
        """Load full setup from a Dioptas project file (.dio).

        This restores calibration, mask, corrections, image orientation,
        integration parameters, and all other settings saved in the project.

        :param filename: path to a .dio project file
        :returns: configured Pipeline instance
        """
        pipeline = cls()

        from dioptas.model.DioptasModel import DioptasModel

        model = DioptasModel()
        model.load(filename)

        # Take the selected configuration from the loaded project
        pipeline._configuration = model.current_configuration

        # Disable auto-integration since we control when integration happens
        pipeline._configuration.auto_integrate_pattern = False
        pipeline._configuration.auto_integrate_cake = False
        pipeline._configuration.auto_save_integrated_pattern = False

        # Keep a reference to the full model for potential future use
        pipeline._model = model

        return pipeline

    # --- Calibration ---

    def load_calibration(self, filename: str) -> None:
        """Load calibration from a .poni file.

        :param filename: path to a pyFAI .poni calibration file
        """
        self._configuration.calibration_model.load(filename)

    @property
    def is_calibrated(self) -> bool:
        """Whether a calibration has been loaded."""
        return self._configuration.calibration_model.is_calibrated

    # --- Mask ---

    def load_mask(self, filename: str) -> None:
        """Load mask from a file (.mask, .tif, .edf, .npy).

        :param filename: path to the mask file
        :raises ValueError: if mask dimensions don't match the current image
        """
        success = self._configuration.mask_model.load_mask(filename)
        if not success:
            raise ValueError(
                f"Mask dimensions from '{filename}' do not match "
                f"current image dimensions {self._configuration.mask_model.mask_dimension}"
            )
        self._configuration.use_mask = True

    def set_mask(self, mask: np.ndarray) -> None:
        """Set mask from a numpy array.

        :param mask: boolean array where True means masked (excluded)
        """
        self._configuration.mask_model.set_mask(mask)
        self._configuration.use_mask = True

    @property
    def use_mask(self) -> bool:
        """Whether masking is enabled for integration."""
        return self._configuration.use_mask

    @use_mask.setter
    def use_mask(self, value: bool) -> None:
        self._configuration.use_mask = value

    # --- Corrections ---

    def add_cbn_correction(
        self,
        diamond_thickness: float = 2.0,
        seat_thickness: float = 5.0,
        small_cbn_seat_radius: float = 0.5,
        large_cbn_seat_radius: float = 2.0,
        tilt: float = 0,
        tilt_rotation: float = 0,
        diamond_abs_length: float = 13.7,
        cbn_abs_length: float = 14.05,
        center_offset: float = 0,
        center_offset_angle: float = 0,
    ) -> None:
        """Add a CbN (cubic boron nitride) seat absorption correction.

        Requires calibration to be loaded first.
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration must be loaded before adding corrections")

        from dioptas.model.util.ImgCorrection import CbnCorrection

        tth_array = 180.0 / np.pi * self._configuration.calibration_model.tth_array
        azi_array = 180.0 / np.pi * self._configuration.calibration_model.azi_array

        correction = CbnCorrection(
            tth_array=tth_array,
            azi_array=azi_array,
            diamond_thickness=diamond_thickness,
            seat_thickness=seat_thickness,
            small_cbn_seat_radius=small_cbn_seat_radius,
            large_cbn_seat_radius=large_cbn_seat_radius,
            tilt=tilt,
            tilt_rotation=tilt_rotation,
            diamond_abs_length=diamond_abs_length,
            cbn_abs_length=cbn_abs_length,
            center_offset=center_offset,
            center_offset_angle=center_offset_angle,
        )
        correction.update()
        self._configuration.img_model.add_img_correction(correction, "cbn")

    def add_oiadac_correction(
        self,
        detector_thickness: float = 0.032,
        absorption_length: float = 0.0076,
    ) -> None:
        """Add oblique incidence angle detector absorption correction.

        Requires calibration to be loaded first.
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration must be loaded before adding corrections")

        from dioptas.model.util.ImgCorrection import (
            ObliqueAngleDetectorAbsorptionCorrection,
        )

        tth_array = 180.0 / np.pi * self._configuration.calibration_model.tth_array
        azi_array = 180.0 / np.pi * self._configuration.calibration_model.azi_array

        correction = ObliqueAngleDetectorAbsorptionCorrection(
            tth_array=tth_array,
            azi_array=azi_array,
            detector_thickness=detector_thickness,
            absorption_length=absorption_length,
        )
        correction.update()
        self._configuration.img_model.add_img_correction(correction, "oiadac")

    def add_slab_absorption_correction(
        self,
        formula: str,
        density: float = None,
        thickness: float = 0.1,
        slab_tilt: float = 0,
        slab_rotation: float = 0,
    ) -> None:
        """Add a flat slab sample absorption correction.

        Calculates the linear absorption coefficient from the chemical
        formula and X-ray energy (from calibration wavelength) using xraydb,
        then applies an absorption correction for a flat sample in
        transmission geometry.

        Requires calibration to be loaded first.

        :param formula: chemical formula (e.g. 'CeO2', 'Au', 'Fe2O3')
        :param density: material density in g/cm³ (None to use xraydb default)
        :param thickness: slab thickness in mm
        :param slab_tilt: tilt of slab normal from beam direction in degrees
        :param slab_rotation: rotation of tilt direction in degrees
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration must be loaded before adding corrections")

        from dioptas.model.util.ImgCorrection import SlabAbsorptionCorrection
        from dioptas.model.util.calc import wavelength_to_energy, calculate_mu

        tth_array = 180.0 / np.pi * self._configuration.calibration_model.tth_array
        azi_array = 180.0 / np.pi * self._configuration.calibration_model.azi_array

        wavelength_m = self._configuration.calibration_model.wavelength
        energy_eV = wavelength_to_energy(wavelength_m)
        mu = calculate_mu(formula, energy_eV, density=density)

        correction = SlabAbsorptionCorrection(
            tth_array=tth_array,
            azi_array=azi_array,
            thickness=thickness,
            absorption_coefficient=mu,
            slab_tilt=slab_tilt,
            slab_rotation=slab_rotation,
        )
        correction.update()
        self._configuration.img_model.add_img_correction(correction, "slab")

    def add_cylinder_absorption_correction(
        self,
        formula: str,
        density: float = None,
        radius: float = 0.15,
        axis_tilt: float = 0,
        axis_rotation: float = 0,
        beam_width: float = 0,
        container_formula: str = None,
        container_density: float = None,
        wall_thickness: float = 0,
    ) -> None:
        """Add a cylindrical sample absorption correction.

        Calculates the absorption correction for a cylindrical sample
        (e.g., a capillary), optionally including a container (e.g.,
        glass capillary wall). The absorption coefficients are calculated
        from the chemical formulas and calibration wavelength.

        Requires calibration to be loaded first.

        :param formula: sample chemical formula (e.g. 'CeO2', 'Au')
        :param density: sample density in g/cm³ (None to use xraydb default)
        :param radius: sample cylinder radius (inner radius) in mm
        :param axis_tilt: tilt of cylinder axis from vertical (degrees).
            0 = vertical (perpendicular to beam), 90 = along beam.
        :param axis_rotation: rotation of tilt around beam axis (degrees)
        :param beam_width: beam diameter in mm. 0 = pencil beam (default),
            >= 2*radius = full illumination.
        :param container_formula: container chemical formula (e.g. 'SiO2'
            for glass). None = no container correction (default).
        :param container_density: container density in g/cm³
        :param wall_thickness: container wall thickness in mm
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration must be loaded before adding corrections")

        from dioptas.model.util.ImgCorrection import CylinderAbsorptionCorrection
        from dioptas.model.util.calc import wavelength_to_energy, calculate_mu

        tth_array = 180.0 / np.pi * self._configuration.calibration_model.tth_array
        azi_array = 180.0 / np.pi * self._configuration.calibration_model.azi_array

        wavelength_m = self._configuration.calibration_model.wavelength
        energy_eV = wavelength_to_energy(wavelength_m)
        mu = calculate_mu(formula, energy_eV, density=density)

        mu_container = 0
        if container_formula is not None and wall_thickness > 0:
            mu_container = calculate_mu(
                container_formula, energy_eV, density=container_density
            )

        correction = CylinderAbsorptionCorrection(
            tth_array=tth_array,
            azi_array=azi_array,
            radius=radius,
            absorption_coefficient=mu,
            axis_tilt=axis_tilt,
            axis_rotation=axis_rotation,
            beam_width=beam_width,
            container_absorption_coefficient=mu_container,
            wall_thickness=wall_thickness,
        )
        correction.update()
        self._configuration.img_model.add_img_correction(correction, "cylinder")

    def add_sphere_absorption_correction(
        self,
        formula: str,
        density: float = None,
        radius: float = 0.1,
        beam_width: float = 0,
    ) -> None:
        """Add a spherical sample absorption correction.

        Calculates the absorption correction for a spherical sample.
        Due to spherical symmetry, the correction depends only on 2θ
        (no orientation parameters needed).

        Requires calibration to be loaded first.

        :param formula: chemical formula (e.g. 'CeO2', 'Au', 'Fe2O3')
        :param density: material density in g/cm³ (None to use xraydb default)
        :param radius: sphere radius in mm
        :param beam_width: beam diameter in mm. 0 = pencil beam (default),
            >= 2*radius = full illumination.
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration must be loaded before adding corrections")

        from dioptas.model.util.ImgCorrection import SphereAbsorptionCorrection
        from dioptas.model.util.calc import wavelength_to_energy, calculate_mu

        tth_array = 180.0 / np.pi * self._configuration.calibration_model.tth_array
        azi_array = 180.0 / np.pi * self._configuration.calibration_model.azi_array

        wavelength_m = self._configuration.calibration_model.wavelength
        energy_eV = wavelength_to_energy(wavelength_m)
        mu = calculate_mu(formula, energy_eV, density=density)

        correction = SphereAbsorptionCorrection(
            tth_array=tth_array,
            azi_array=azi_array,
            radius=radius,
            absorption_coefficient=mu,
            beam_width=beam_width,
        )
        correction.update()
        self._configuration.img_model.add_img_correction(correction, "sphere")

    def add_plate_absorption_correction(
        self,
        formula: str,
        density: float = None,
        thickness: float = 0.1,
    ) -> None:
        """Add a flat plate sample absorption correction.

        Calculates the absorption correction for a flat plate sample
        (e.g., a thin film or pellet) in the Debye-Scherrer geometry.

        Requires calibration to be loaded first.

        :param formula: chemical formula (e.g. 'CeO2', 'Au', 'Fe2O3')
        :param density: material density in g/cm³ (None to use xraydb default)
        :param thickness: plate thickness in mm
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration must be loaded before adding corrections")

        from dioptas.model.util.ImgCorrection import PlateAbsorptionCorrection
        from dioptas.model.util.calc import wavelength_to_energy, calculate_mu

        tth_array = 180.0 / np.pi * self._configuration.calibration_model.tth_array
        azi_array = 180.0 / np.pi * self._configuration.calibration_model.azi_array

        wavelength_m = self._configuration.calibration_model.wavelength
        energy_eV = wavelength_to_energy(wavelength_m)
        mu = calculate_mu(formula, energy_eV, density=density)

        correction = PlateAbsorptionCorrection(
            tth_array=tth_array,
            azi_array=azi_array,
            thickness=thickness,
            absorption_coefficient=mu,
        )
        correction.update()
        self._configuration.img_model.add_img_correction(correction, "plate")

    def clear_corrections(self) -> None:
        """Remove all image corrections."""
        self._configuration.img_model.img_corrections.clear()

    # --- Background subtraction ---

    def load_image_background(self, filename: str) -> None:
        """Load a background image (e.g. dark frame) to subtract from all images.

        The background is subtracted from the raw image before integration.

        :param filename: path to the background image file
        """
        self._configuration.img_model.load_background(filename)

    def reset_image_background(self) -> None:
        """Remove the image background subtraction."""
        self._configuration.img_model.reset_background()

    @property
    def image_background_scaling(self) -> float:
        """Scaling factor for image background subtraction."""
        return self._configuration.img_model.background_scaling

    @image_background_scaling.setter
    def image_background_scaling(self, value: float) -> None:
        self._configuration.img_model.background_scaling = value

    @property
    def image_background_offset(self) -> float:
        """Offset for image background subtraction."""
        return self._configuration.img_model.background_offset

    @image_background_offset.setter
    def image_background_offset(self, value: float) -> None:
        self._configuration.img_model.background_offset = value

    def set_pattern_background_subtraction(
        self,
        smoothing: float = 150,
        iterations: int = 50,
        poly_order: int = 50,
        roi=None,
    ) -> None:
        """Enable automatic background subtraction on integrated patterns.

        Uses the Smooth Bruckner algorithm to estimate and subtract
        the background from the integrated 1D pattern.

        :param smoothing: width of the smoothing window
        :param iterations: number of iterations
        :param poly_order: Chebyshev polynomial order
        :param roi: optional (x_min, x_max) range for background fitting
        """
        self._configuration.pattern_model.set_auto_background_subtraction(
            [smoothing, iterations, poly_order], roi=roi
        )

    def unset_pattern_background_subtraction(self) -> None:
        """Disable automatic pattern background subtraction."""
        self._configuration.pattern_model.unset_auto_background_subtraction()

    # --- Integration parameters ---

    @property
    def integration_unit(self) -> str:
        """Integration unit: '2th_deg', 'q_A^-1', or 'd_A'."""
        return self._configuration.integration_unit

    @integration_unit.setter
    def integration_unit(self, unit: str) -> None:
        # the pipeline integrates explicitly — suppress the write's
        # re-integration reaction
        with self._configuration.pattern_integration.hold(flush=False):
            self._configuration.params.integration_unit = unit

    @property
    def integration_num_points(self):
        """Number of radial points for integration (None for automatic)."""
        return self._configuration.integration_rad_points

    @integration_num_points.setter
    def integration_num_points(self, n) -> None:
        with self._configuration.pattern_integration.hold(flush=False):
            self._configuration.params.integration_rad_points = n

    @property
    def azimuth_range(self):
        """Azimuthal range for integration as (start, end) in degrees, or None."""
        return self._configuration.oned_azimuth_range

    @azimuth_range.setter
    def azimuth_range(self, range) -> None:
        with self._configuration.pattern_integration.hold(flush=False):
            self._configuration.params.oned_azimuth_range = range

    @property
    def correct_solid_angle(self) -> bool:
        """Whether solid angle correction is applied."""
        return self._configuration.calibration_model.correct_solid_angle

    @correct_solid_angle.setter
    def correct_solid_angle(self, value: bool) -> None:
        self._configuration.calibration_model.correct_solid_angle = value

    # --- Integration ---

    def integrate(self, image) -> Pattern:
        """Integrate a single image to a 1D pattern.

        :param image: file path (str) or numpy array
        :returns: integrated Pattern with .x and .y numpy arrays
        :raises RuntimeError: if no calibration is loaded
        """
        if not self.is_calibrated:
            raise RuntimeError(
                "No calibration loaded. Use load_calibration() or from_project() first."
            )

        if isinstance(image, (str, os.PathLike)):
            self._configuration.img_model.load(str(image))
        elif isinstance(image, np.ndarray):
            self._configuration.img_model._img_data = image
            self._configuration.update_mask_dimension()
            self._configuration.img_model._calculate_img_data()
        else:
            raise TypeError(f"Expected file path or numpy array, got {type(image)}")

        result = self._configuration.integrate_image_1d(update_pattern_model=False)
        if result is None:
            raise RuntimeError("Integration failed.")

        x, y = result
        name = ""
        if isinstance(image, (str, os.PathLike)):
            name = os.path.basename(str(image))
        return Pattern(x, y, name)

    def integrate_batch(self, images, progress=True) -> list:
        """Integrate multiple images to 1D patterns.

        :param images: glob pattern (for example, ``data/*.tiff``), or list of
            file paths / numpy arrays
        :param progress: if True and tqdm is available, show a progress bar
        :returns: list of Pattern objects
        """
        if isinstance(images, (str, os.PathLike)):
            images_str = str(images)
            if "*" in images_str or "?" in images_str:
                file_list = sorted(glob.glob(images_str))
                if not file_list:
                    raise FileNotFoundError(f"No files matched pattern: {images_str}")
            else:
                # Single file path
                file_list = [images_str]
        elif isinstance(images, (list, tuple)):
            file_list = images
        else:
            raise TypeError(
                f"Expected file path, glob pattern, or list, got {type(images)}"
            )

        iterator = file_list
        if progress:
            try:
                from tqdm import tqdm

                iterator = tqdm(file_list, desc="Integrating")
            except ImportError:
                pass

        results = []
        for image in iterator:
            results.append(self.integrate(image))
        return results

    # --- Access to underlying models (advanced use) ---

    @property
    def calibration_model(self):
        """Direct access to the CalibrationModel (advanced use)."""
        return self._configuration.calibration_model

    @property
    def mask_model(self):
        """Direct access to the MaskModel (advanced use)."""
        return self._configuration.mask_model

    @property
    def img_model(self):
        """Direct access to the ImgModel (advanced use)."""
        return self._configuration.img_model

    @property
    def configuration(self):
        """Direct access to the underlying Configuration (advanced use)."""
        return self._configuration
