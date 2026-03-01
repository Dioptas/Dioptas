# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import logging

import numpy as np
from qtpy.QtCore import QThread, Signal

from dioptas.model.ImgModel import ImgModel
from dioptas.model.MapModel2 import MapPointInfo, _convert_tth_to_d
from dioptas.model.util.ImgCorrection import DummyCorrection

logger = logging.getLogger(__name__)

try:
    from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
except ImportError:
    AzimuthalIntegrator = None


class IntegrationSnapshot:
    """Captures all state needed for integration from the main thread.

    Created on the main thread before the worker starts so that the worker
    never touches the live model objects.
    """

    def __init__(self):
        # pyFAI config (for cloning geometry in worker)
        self.pyfai_config = None

        # dioptrin config (integrator is created fresh on worker thread)
        self.poni_dict = None
        self.dioptrin_num_workers = 10
        self.use_dioptrin = False

        # calibration params
        self.polarization_factor = 0.99
        self.correct_solid_angle = True
        self.supersampling_factor = 1

        # integration params
        self.unit = "2th_deg"
        self.num_points = None
        self.azi_range = None
        self.trim_trailing_zeros = False

        # mask
        self.mask_data = None

        # ImgModel state
        self.img_transformations = []
        self.background_data = None
        self.background_scaling = 1
        self.background_offset = 0
        self.factor = 1
        self.correction_data = None

        # wavelength (for d-spacing conversion)
        self.wavelength = None

    @classmethod
    def from_configuration(cls, configuration):
        """Create a snapshot from a Configuration on the main thread."""
        snap = cls()
        cal = configuration.calibration_model

        # pyFAI geometry config
        snap.pyfai_config = cal.pattern_geometry.get_config()

        # dioptrin (integrator created fresh on worker thread)
        snap.poni_dict = cal._get_poni_dict()
        snap.dioptrin_num_workers = cal.dioptrin_num_workers
        unit = configuration.integration_unit
        azi_range = configuration.oned_azimuth_range
        snap.use_dioptrin = cal.can_use_dioptrin_batch(unit, azi_range)

        # calibration params
        snap.polarization_factor = cal.polarization_factor
        snap.correct_solid_angle = cal.correct_solid_angle
        snap.supersampling_factor = cal.supersampling_factor

        # integration params
        snap.unit = unit
        snap.num_points = configuration.integration_rad_points
        snap.azi_range = azi_range
        snap.trim_trailing_zeros = False  # always False for batch/map

        # mask
        if configuration.use_mask:
            snap.mask_data = np.copy(configuration.mask_model.get_mask())
        elif configuration.mask_model.roi is not None:
            snap.mask_data = np.copy(configuration.mask_model.roi_mask)
        else:
            snap.mask_data = None

        # ImgModel state
        img = configuration.img_model
        snap.img_transformations = list(img.img_transformations)
        if img._background_data is not None:
            snap.background_data = np.copy(img._background_data)
        snap.background_scaling = img._background_scaling
        snap.background_offset = img._background_offset
        snap.factor = img._factor

        # pre-compute combined correction data
        correction_data = img._img_corrections.get_data()
        if correction_data is not None:
            snap.correction_data = np.copy(correction_data)

        # wavelength
        snap.wavelength = cal.pattern_geometry.wavelength

        return snap


class IntegrationWorker(QThread):
    """Runs image loading + integration in a background thread.

    The worker creates its own ImgModel for I/O but reuses the existing
    dioptrin integrator (shared-memory worker pool). For pyFAI, a lightweight
    geometry clone is created.

    Signals:
        progress(int, int): (current_frame, total_frames)
        finished(object): results dict
        error(str): error message
    """

    progress = Signal(int, int)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        snapshot,
        filepaths,
        mode="map",
        batch_start=None,
        batch_stop=None,
        batch_step=None,
        batch_use_all=False,
        batch_pos_map=None,
        batch_files=None,
    ):
        super().__init__()
        self.snapshot = snapshot
        self.filepaths = filepaths
        self.mode = mode

        # batch-specific params
        self.batch_start = batch_start
        self.batch_stop = batch_stop
        self.batch_step = batch_step
        self.batch_use_all = batch_use_all
        self.batch_pos_map = batch_pos_map
        self.batch_files = batch_files

        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self.mode == "map":
                results = self._run_map()
            else:
                results = self._run_batch()
            self.finished.emit(results)
        except Exception as e:
            logger.exception("IntegrationWorker failed")
            self.error.emit(str(e))

    def _run_map(self):
        snap = self.snapshot
        img_model = _create_img_model(snap)

        # Resolve num_points if needed
        if snap.num_points is None:
            img_model.load(self.filepaths[0])
            snap.num_points = _calculate_num_points(snap, img_model.img_data.shape)

        if snap.use_dioptrin:
            return self._run_map_dioptrin(img_model, snap)
        else:
            return self._run_map_pyfai(img_model, snap)

    def _run_map_dioptrin(self, img_model, snap):
        from dioptas.model.loader.hdf5Loader import Hdf5Image

        integrator = _create_dioptrin_integrator(snap)
        all_infos = []
        pattern_x = None
        pattern_intensities = []

        # estimate n_total from first file
        img_model.load(self.filepaths[0])
        n_total = len(self.filepaths) * img_model.series_max

        fast_path = (
            not snap.img_transformations
            and snap.background_data is None
            and snap.correction_data is None
            and snap.factor == 1
        )

        def frame_generator():
            for filepath in self.filepaths:
                if self._cancelled:
                    return
                img_model.load(filepath)
                loader = getattr(img_model, "loader", None)
                if isinstance(loader, Hdf5Image) and loader._is_bitshuffle:
                    for frame_ind, frame in enumerate(loader.gen_frames()):
                        if self._cancelled:
                            return
                        all_infos.append(MapPointInfo(filepath, frame_ind))
                        if fast_path:
                            yield frame
                        else:
                            yield img_model._apply_frame_pipeline(frame)
                else:
                    for frame_ind in range(img_model.series_max):
                        if self._cancelled:
                            return
                        all_infos.append(MapPointInfo(filepath, frame_ind))
                        img_model.load_series_img(frame_ind + 1)
                        yield img_model.get_img_data_float64()

        result_iter = integrator.batch1d_iter(
            frame_generator(),
            snap.num_points,
            num_workers=snap.dioptrin_num_workers,
        )

        for i, result in enumerate(result_iter):
            if not result.is_ok():
                raise RuntimeError(
                    f"Dioptrin batch integration failed: {result.error}"
                )

            x = np.array(result.result.radial)
            y = np.array(result.result.intensity)

            if pattern_x is None:
                pattern_x = x
            else:
                if len(x) != len(pattern_x):
                    raise ValueError(
                        "The integrated patterns have different length, "
                        "this is not supported"
                    )

            pattern_intensities.append(y)
            self.progress.emit(i + 1, n_total)

            if self._cancelled:
                break

        pattern_intensities = np.array(pattern_intensities)

        if snap.unit == "d_A":
            pattern_x = _convert_tth_to_d(pattern_x, snap.wavelength)

        # all_infos may have more entries than pattern_intensities
        # if cancellation happened after yielding but before result processing
        point_infos = all_infos[: len(pattern_intensities)]

        return {
            "pattern_x": pattern_x,
            "pattern_intensities": pattern_intensities,
            "point_infos": point_infos,
            "filepaths": self.filepaths,
        }

    def _run_map_pyfai(self, img_model, snap):
        geometry = _create_pyfai_geometry(snap)
        mask = snap.mask_data
        pattern_x = None
        pattern_intensities = []
        point_infos = []
        frame_count = 0
        n_total = None

        for file_ind, filepath in enumerate(self.filepaths):
            if self._cancelled:
                break
            img_model.load(filepath)
            series_max = img_model.series_max
            if n_total is None:
                n_total = len(self.filepaths) * series_max

            for frame_ind in range(series_max):
                if self._cancelled:
                    break
                img_model.load_series_img(frame_ind + 1)
                img_data = img_model.img_data

                if snap.supersampling_factor > 1:
                    from dioptas.model.CalibrationModel import supersample_image

                    img_data = supersample_image(
                        img_data, snap.supersampling_factor
                    )
                    int_mask = (
                        supersample_image(mask, snap.supersampling_factor)
                        if mask is not None
                        else None
                    )
                else:
                    int_mask = mask

                unit = "2th_deg" if snap.unit == "d_A" else snap.unit
                x, y = geometry.integrate1d(
                    img_data,
                    snap.num_points,
                    unit=unit,
                    mask=int_mask,
                    azimuth_range=snap.azi_range,
                    polarization_factor=snap.polarization_factor,
                    correctSolidAngle=snap.correct_solid_angle,
                )

                if snap.unit == "d_A":
                    x = _convert_tth_to_d(x, snap.wavelength)

                if pattern_x is None:
                    pattern_x = x
                else:
                    if len(x) != len(pattern_x):
                        raise ValueError(
                            "The integrated patterns have different length, "
                            "this is not supported"
                        )

                point_infos.append(MapPointInfo(filepath, frame_ind))
                pattern_intensities.append(y)
                frame_count += 1
                self.progress.emit(frame_count, n_total)

        pattern_intensities = np.array(pattern_intensities)

        return {
            "pattern_x": pattern_x,
            "pattern_intensities": pattern_intensities,
            "point_infos": point_infos,
            "filepaths": self.filepaths,
        }

    def _run_batch(self):
        snap = self.snapshot
        img_model = _create_img_model(snap)

        # Resolve num_points if needed
        if snap.num_points is None:
            indices = list(range(self.batch_start, self.batch_stop, self.batch_step))
            file_index = self.batch_pos_map[indices[0]][0]
            img_model.load(self.batch_files[file_index])
            snap.num_points = _calculate_num_points(snap, img_model.img_data.shape)

        if snap.use_dioptrin:
            return self._run_batch_dioptrin(img_model, snap)
        else:
            return self._run_batch_pyfai(img_model, snap)

    def _run_batch_dioptrin(self, img_model, snap):
        from dioptas.model.loader.hdf5Loader import Hdf5Image

        integrator = _create_dioptrin_integrator(snap)
        indices = list(range(self.batch_start, self.batch_stop, self.batch_step))
        source = self.batch_pos_map
        files = self.batch_files

        intensity_data = []
        pos_map = []
        binning = None
        n_total = len(indices)

        current_file = ""

        fast_path = (
            not snap.img_transformations
            and snap.background_data is None
            and snap.correction_data is None
            and snap.factor == 1
        )

        def frame_generator():
            nonlocal current_file
            frame_iter = None
            next_frame_pos = 0

            for index in indices:
                if self._cancelled:
                    return
                file_index, pos = source[index]
                if file_index != current_file:
                    current_file = file_index
                    img_model.load(files[file_index])
                    # Set up parallel generator for bitshuffle files
                    loader = getattr(img_model, "loader", None)
                    if isinstance(loader, Hdf5Image) and loader._is_bitshuffle:
                        frame_iter = iter(loader.gen_frames())
                        next_frame_pos = 0
                    else:
                        frame_iter = None

                if frame_iter is not None:
                    frame = None
                    while next_frame_pos <= pos:
                        frame = next(frame_iter)
                        next_frame_pos += 1
                    if fast_path:
                        yield frame
                    else:
                        yield img_model._apply_frame_pipeline(frame)
                else:
                    img_model.load_series_img(pos + 1)
                    yield img_model.get_img_data_float64()

        result_iter = integrator.batch1d_iter(
            frame_generator(),
            snap.num_points,
            num_workers=snap.dioptrin_num_workers,
        )

        for i, result in enumerate(result_iter):
            if not result.is_ok():
                raise RuntimeError(
                    f"Dioptrin batch integration failed: {result.error}"
                )

            x = np.array(result.result.radial)
            y = np.array(result.result.intensity)

            if binning is None:
                binning = x
            intensity_data.append(y)
            pos_map.append((source[indices[i]][0], source[indices[i]][1]))

            self.progress.emit(i + 1, n_total)

            if self._cancelled:
                break

        return {
            "intensity_data": intensity_data,
            "binning": binning,
            "pos_map": pos_map,
            "unit": snap.unit,
            "wavelength": snap.wavelength,
        }

    def _run_batch_pyfai(self, img_model, snap):
        geometry = _create_pyfai_geometry(snap)
        mask = snap.mask_data
        indices = list(range(self.batch_start, self.batch_stop, self.batch_step))
        source = self.batch_pos_map
        files = self.batch_files

        intensity_data = []
        binning_data = []
        pos_map = []
        n_total = len(indices)
        current_file = ""

        for count, index in enumerate(indices):
            if self._cancelled:
                break
            file_index, pos = source[index]
            if file_index != current_file:
                current_file = file_index
                img_model.load(files[file_index])

            img_model.load_series_img(pos + 1)
            img_data = img_model.img_data

            if snap.supersampling_factor > 1:
                from dioptas.model.CalibrationModel import supersample_image

                img_data = supersample_image(
                    img_data, snap.supersampling_factor
                )
                int_mask = (
                    supersample_image(mask, snap.supersampling_factor)
                    if mask is not None
                    else None
                )
            else:
                int_mask = mask

            unit = "2th_deg" if snap.unit == "d_A" else snap.unit
            x, y = geometry.integrate1d(
                img_data,
                snap.num_points,
                unit=unit,
                mask=int_mask,
                azimuth_range=snap.azi_range,
                polarization_factor=snap.polarization_factor,
                correctSolidAngle=snap.correct_solid_angle,
            )

            pos_map.append((file_index, pos))
            intensity_data.append(y)
            binning_data.append(x)
            self.progress.emit(count + 1, n_total)

        return {
            "intensity_data": intensity_data,
            "binning_data": binning_data,
            "pos_map": pos_map,
            "unit": snap.unit,
            "wavelength": snap.wavelength,
        }


def _create_img_model(snapshot):
    """Create a fresh ImgModel with copied state from the snapshot."""
    img_model = ImgModel()
    img_model.blockSignals(True)
    img_model.img_transformations = snapshot.img_transformations
    img_model._factor = snapshot.factor
    img_model._background_data = snapshot.background_data
    img_model._background_scaling = snapshot.background_scaling
    img_model._background_offset = snapshot.background_offset

    if snapshot.correction_data is not None:
        dummy = DummyCorrection(snapshot.correction_data.shape)
        dummy._data = snapshot.correction_data
        img_model._img_corrections.add(dummy, name="worker_correction")

    return img_model


def _create_pyfai_geometry(snapshot):
    """Create a cloned pyFAI AzimuthalIntegrator from the snapshot config."""
    geometry = AzimuthalIntegrator()
    geometry.set_config(snapshot.pyfai_config)
    return geometry


def _calculate_num_points(snapshot, img_shape, max_dist_factor=2):
    """Calculate number of integration points from geometry and image shape.

    Replicates CalibrationModel.calculate_number_of_pattern_points logic
    using a cloned pyFAI geometry from the snapshot.
    """
    geometry = _create_pyfai_geometry(snapshot)
    fit2d_parameter = geometry.getFit2D()
    center_x = fit2d_parameter["centerX"]
    center_y = fit2d_parameter["centerY"]
    width, height = img_shape

    if width > center_x > 0:
        side1 = np.max([abs(width - center_x), center_x])
    else:
        side1 = width

    if center_y < height and center_y > 0:
        side2 = np.max([abs(height - center_y), center_y])
    else:
        side2 = height
    max_dist = np.sqrt(side1**2 + side2**2)
    return int(max_dist * max_dist_factor)


def _create_dioptrin_integrator(snapshot):
    """Create a fresh dioptrin integrator on the current thread.

    The dioptrin integrator is thread-pinned (Rust !Send) and cannot be shared
    across threads. A new integrator is created from the poni_dict and
    configured with the same settings that sync_dioptrin_for_batch would apply.
    """
    import dioptrin

    integrator = dioptrin.Integrator.from_poni_dict(
        snapshot.poni_dict,
        method="pixel_split",
        polarization_factor=snapshot.polarization_factor,
        unit="2th_deg",
    )

    # Apply same configuration as CalibrationModel.sync_dioptrin_for_batch
    if snapshot.supersampling_factor > 1:
        integrator.set_method("supersampled", n_ss=snapshot.supersampling_factor)
    else:
        integrator.set_method("pixel_split")

    dioptrin_unit = "2th_deg" if snapshot.unit == "d_A" else snapshot.unit
    integrator.set_unit(dioptrin_unit)

    mask = snapshot.mask_data
    integrator.set_mask(mask.astype(np.uint8) if mask is not None else None)
    integrator.set_polarization_factor(snapshot.polarization_factor)

    return integrator
