# SPDX-License-Identifier: MIT
from __future__ import annotations

import os.path
import time

import numpy as np
from dioptas.model.util.signal import Signal

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Configuration import Configuration


class MapPointInfo:
    filename: str
    frame_index: int

    def __init__(self, filepath, frame_index=0):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.frame_index = frame_index


class MapModel:
    map_changed = Signal()

    # point_integrated is emitted with the index of the integrated point
    # it will be a fractional number, when the image file contains multiple frames
    point_integrated = Signal(float)

    def __init__(self, configuration: "Configuration"):
        """
        Creates a new map-model. The configuration specified will serve as
        integrator for the processed files.
        :param configuration: Configuration to be used for integration
        """
        super().__init__()
        self.configuration = configuration
        self.filepaths = None
        self.point_infos = []
        self.pattern_intensities = None
        self.pattern_x = None
        self.window = None
        self.window_intensities = None
        self.dimension = None
        self.possible_dimensions = None
        self.map = None

    def load(self, filepaths: list[str], callback_fn=None):
        """Loads a list of files, integrates them and creates a map"""
        if len(filepaths) == 0:
            raise ValueError("No files to load")

        self.filepaths = filepaths

        self.integrate(callback_fn=callback_fn)

        if len(self.pattern_intensities) == 0:
            return

        if self.window is None:
            self.window = get_center_window(self.pattern_x)

        self.window_intensities = get_window_intensities(
            self.pattern_x, self.pattern_intensities, self.window
        )

        self.possible_dimensions = find_possible_dimensions(
            len(self.window_intensities)
        )

        if self.dimension is None or self.dimension not in self.possible_dimensions:
            self.dimension = self.possible_dimensions[0]

        self.map = create_map(self.window_intensities, self.dimension)
        self.map_changed.emit()

    def integrate(self, callback_fn=None):
        """Integrates all files in the filepaths list and stores the results"""
        if not self.configuration.calibration_model.is_calibrated:
            raise ValueError("Detector geometry is not calibrated")

        # initialize data structures
        self.pattern_x = []
        self.pattern_intensities = []
        self.point_infos = []

        # disable trimming trailing zeros for integration, otherwise the
        # integration will result in patterns with different length, which
        # will cause problems when creating the map
        trim_trailing_zeros_backup = self.configuration.trim_trailing_zeros
        self.configuration.trim_trailing_zeros = False

        self.configuration.img_model.img_changed.blocked = True

        try:
            self._integrate(callback_fn=callback_fn)
        except Exception as e:
            self._reset()
            raise e
        finally:
            # reset model to previous state
            self.configuration.trim_trailing_zeros = trim_trailing_zeros_backup
            self.configuration.img_model.img_changed.blocked = False

    def _integrate(self, callback_fn=None):
        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        azi_range = self.configuration.oned_azimuth_range

        if cal.can_use_dioptrin_batch(unit, azi_range):
            self._integrate_dioptrin_batch(callback_fn=callback_fn)
        else:
            self._integrate_pyFAI(callback_fn=callback_fn)

    def _integrate_pyFAI(self, callback_fn=None):
        frame_count = 0
        n_total = None
        last_callback_time = time.monotonic()

        for file_ind, filepath in enumerate(self.filepaths):
            self.configuration.img_model.load(filepath)

            series_max = self.configuration.img_model.series_max
            if n_total is None:
                n_total = len(self.filepaths) * series_max

            for frame_ind in range(series_max):
                self.configuration.img_model.load_series_img(frame_ind + 1)
                x, y = self.configuration.integrate_image_1d(
                    update_pattern_model=False
                )

                if file_ind == 0 and frame_ind == 0:
                    self.pattern_x = x
                else:
                    if len(x) != len(self.pattern_x):
                        raise ValueError(
                            "The integrated patterns have different length, this is not supported"
                        )

                self.point_infos.append(MapPointInfo(filepath, frame_ind))
                self.pattern_intensities.append(y)

                frame_count += 1
                self.point_integrated.emit(
                    file_ind + (frame_ind + 1) / series_max
                )

                now = time.monotonic()
                if callback_fn is not None and now - last_callback_time > 0.1:
                    last_callback_time = now
                    if not callback_fn(frame_count, n_total):
                        self.pattern_intensities = np.array(self.pattern_intensities)
                        return

        # Final callback to ensure progress reaches 100%
        if callback_fn is not None:
            callback_fn(frame_count, n_total)

        self.pattern_intensities = np.array(self.pattern_intensities)

    def _integrate_dioptrin_batch(self, callback_fn=None):
        """Load frames through ImgModel, integrate via batch1d_iter with generator."""
        from dioptas.model.util.integration import iter_frames_sequential, convert_tth_to_d

        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        num_points = self.configuration.integration_rad_points

        if self.configuration.use_mask:
            mask = self.configuration.mask_model.get_mask()
        elif self.configuration.mask_model.roi is not None:
            mask = self.configuration.mask_model.roi_mask
        else:
            mask = None

        # Load first file to get shape and configure integrator
        self.configuration.img_model.load(self.filepaths[0])
        img_shape = self.configuration.img_model.img_data.shape
        first_series_max = self.configuration.img_model.series_max
        num_points = cal.sync_dioptrin_for_batch(mask, unit, num_points, img_shape)

        # Estimate total frames from first file; refined if files differ
        n_total = len(self.filepaths) * first_series_max

        aborted = False
        # Built lazily by frame generator; consumed in result loop
        all_infos = []

        def frame_generator():
            yield from iter_frames_sequential(
                self.configuration.img_model,
                self.filepaths,
                img_shape=img_shape,
                abort_check=lambda: aborted,
                on_frame=lambda fp, fi: all_infos.append(MapPointInfo(fp, fi)),
            )

        result_iter = cal.dioptrin_batch1d_iter(frame_generator(), num_points)

        last_callback_time = time.monotonic()
        frame_count = 0
        for i, result in enumerate(result_iter):
            if aborted:
                # Drain remaining pre-fetched results from dioptrin without
                # processing them. This ensures the iterator is fully
                # consumed so cleanup doesn't crash on worker threads.
                continue

            if not result.is_ok():
                raise RuntimeError(
                    f"Dioptrin batch integration failed: {result.error}"
                )

            x = np.array(result.result.radial)
            y = np.array(result.result.intensity)
            frame_count = i + 1

            if frame_count == 1:
                self.pattern_x = x
            else:
                if len(x) != len(self.pattern_x):
                    raise ValueError(
                        "The integrated patterns have different length, "
                        "this is not supported"
                    )

            self.point_infos.append(all_infos[i])
            self.pattern_intensities.append(y)

            self.point_integrated.emit(frame_count)

            # Throttle callback to avoid GUI overhead dominating throughput
            now = time.monotonic()
            if callback_fn is not None and now - last_callback_time > 0.1:
                last_callback_time = now
                if not callback_fn(frame_count, n_total):
                    aborted = True
                    # Don't break — let the for loop drain remaining
                    # pre-fetched results so dioptrin shuts down cleanly.

        # Final callback to ensure progress reaches 100%
        if callback_fn is not None and not aborted:
            callback_fn(frame_count, n_total)

        self.pattern_intensities = np.array(self.pattern_intensities)

        if unit == "d_A":
            self.pattern_x = convert_tth_to_d(
                self.pattern_x, cal.pattern_geometry.wavelength
            )

    def set_integration_results(
        self,
        pattern_x,
        pattern_intensities,
        point_infos: list[MapPointInfo],
        filepaths: list[str],
    ):
        """Sets pre-computed integration results and rebuilds the map.

        This allows populating the model without re-integrating, e.g. when
        results were computed in a worker thread.
        """
        self.pattern_x = pattern_x
        self.pattern_intensities = pattern_intensities
        self.point_infos = point_infos
        self.filepaths = filepaths

        if self.window is None:
            self.window = get_center_window(self.pattern_x)

        self.window_intensities = get_window_intensities(
            self.pattern_x, self.pattern_intensities, self.window
        )

        self.possible_dimensions = find_possible_dimensions(
            len(self.window_intensities)
        )

        if self.dimension is None or self.dimension not in self.possible_dimensions:
            self.dimension = self.possible_dimensions[0]

        self.map = create_map(self.window_intensities, self.dimension)
        self.map_changed.emit()

    def _reset(self):
        self.filepaths = None
        self.point_infos = []
        self.pattern_intensities = None
        self.pattern_x = None
        self.dimension = None
        self.possible_dimensions = None
        self.map = None
        self.map_changed.emit()

    def set_window(self, window: tuple[float, float]):
        """Sets the window in the pattern for generating the map
        :param window: tuple/list of lower value and upper value of the window
        """
        self.window = window
        if self.pattern_x is None:
            return
        self.window_intensities = get_window_intensities(
            self.pattern_x, self.pattern_intensities, self.window
        )
        self.map = create_map(self.window_intensities, self.dimension)
        self.map_changed.emit()

    def set_dimension(self, dimension: tuple[float, float]):
        """Sets the dimension of the map"""
        if dimension not in self.possible_dimensions:
            return
        self.dimension = dimension
        self.map = create_map(self.window_intensities, self.dimension)
        self.map_changed.emit()

    def get_point_info(self, row_index: int, column_index: int) -> MapPointInfo | None:
        """Returns the point info for the specified row and column index"""
        if self.dimension is None:
            return None
        ind = self.get_point_index(row_index, column_index)
        if ind is None:
            return None
        if ind > len(self.point_infos) - 1:
            return None
        return self.point_infos[ind]

    def get_point_index(self, row_index: int, column_index: int) -> int | None:
        """Returns the point index inside the list of integrated images for the specified row and column index"""
        if self.dimension is None:
            return None
        return int(column_index + self.dimension[1] * row_index)

    def get_point_coordinates(self, index: int) -> tuple[int, int]:
        """Returns the row and column index for the specified point index"""
        if self.dimension is None:
            return None
        return divmod(index, self.dimension[1])

    def get_filenames(self) -> list[str]:
        """Returns a list of filenames for the integrated images, it will add the frame index if it is not 0"""
        filenames = []
        for point_info in self.point_infos:
            if point_info.frame_index == 0:
                filenames.append(point_info.filename)
            else:
                filenames.append(f"{point_info.filename}:{point_info.frame_index}")
        return filenames

    def select_point(self, row_index: int, column_index: int):
        """Selects the point at the specified row and column index, will trigger a load of the image through the
        configuration. Thus the image_changed signal will be sent to all listeners"""
        point_ind = self.get_point_index(row_index, column_index)
        if point_ind is None:
            return
        self.select_point_by_index(point_ind)

    def select_point_by_index(self, index: int):
        """Selects the point at the specified index (considering the list of images), will trigger a load of the
        image through the configuration. Thus the image_changed signal will be sent to all listeners
        """
        if index < 0 or index >= len(self.point_infos):
            return
        point_info = self.point_infos[index]
        self.configuration.img_model.load(
            point_info.filepath,
            point_info.frame_index,
        )


def get_center_window(x, window_range=3) -> list[float, float]:
    """
    Estimates a window of [x_min, x_max] centered in the x value list.
    :param x: a numpy array
    :param window_range: the window will be estimated with +- range * x_step
    :return: windows with [x_min, x_max]
    """
    window_center = x[int(len(x) / 2)]
    x_step = np.mean(np.diff(x))
    return [
        window_center - window_range * x_step,
        window_center + window_range * x_step,
    ]


def ind_in_window(x_array, window: tuple[float, float]) -> np.ndarray:
    """
    Gets the indices of a numpy array which are in the window
    :param x_array: a numpy array
    :param window: tuple/list of lower value and upper value of the window
    :return: list of indices
    """
    return np.where((x_array > window[0]) & (x_array < window[1]))[0]


def get_window_intensities(
    pattern_x, intensities, window: tuple[float, float]
) -> np.ndarray:
    """
    Estimates the intensities inside the specified window
    :param pattern_x: a numpy array of x values from the pattern
    :param intensities: a 2D numpy array holding the intensities of all patterns
    :param window: tuple/list of lower value and upper value of the summing window
    :return: an 1D array containing the sum of  intensities inside the window for each pattern
    """
    indices = ind_in_window(pattern_x, window)
    return np.sum(intensities[:, indices], axis=1)


def find_possible_dimensions(num_points: int) -> list[(int, int)]:
    """
    Finds the possible dimension for a map with a given number of points
    :param num_points: number of points for the map
    :return: list of dimension pairs (x-dimension, y-dimension)
    """
    dimension_pairs = []
    for n in range(1, int(np.floor(np.sqrt(num_points + 1))) + 1):
        if num_points % n == 0:
            dim1 = n
            dim2 = num_points // n
            dimension_pairs.append((dim1, dim2))
            if dim1 != dim2:
                dimension_pairs.append((dim2, dim1))
    dimension_pairs.sort(key=lambda x: ((x[0] + x[1]) / 2 - np.sqrt(num_points)) ** 2)
    return dimension_pairs


def create_map(data: np.ndarray, dimension: tuple[int, int]) -> np.ndarray:
    """
    Creates a new map from the given 1D array and specified dimension. It will
    always create a copy of the data.
    :param data: input data for creating the map
    :param dimension: tuple of integers giving the shape of the map
    :return: numpy array with the reorganized data
    """
    new_data = np.copy(data)
    return np.reshape(new_data, dimension)


