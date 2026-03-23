from __future__ import annotations

import logging
import os
import re
import pathlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import h5py
import numpy as np
from PIL import Image

from xypattern.auto_background import SmoothBrucknerBackground
from xypattern import Pattern

if TYPE_CHECKING:
    from .Configuration import Configuration

logger = logging.getLogger(__name__)


class BatchModel:
    """Class describing a model for batch integration."""

    def __init__(self, configuration: Configuration) -> None:
        self.data: np.ndarray | None = None
        self.bkg: np.ndarray | None = None
        self.binning: np.ndarray | None = None
        self.file_map: np.ndarray | None = None
        self.files: np.ndarray | None = None
        self.pos_map: np.ndarray | None = None
        self.pos_map_all: np.ndarray | None = None
        self.n_img: int | None = None
        self.n_img_all: int | None = None
        self.raw_available: bool = False

        self.configuration: Configuration = configuration
        self.used_mask: str | None = None
        self.used_mask_shape: tuple[int, ...] | None = None
        self.used_calibration: str | None = None

    def reset_data(self) -> None:
        self.data = None
        self.bkg = None
        self.binning = None
        self.file_map = None
        self.files = None
        self.pos_map = None
        self.pos_map_all = None
        self.n_img = None
        self.n_img_all = None
        self.used_mask = None
        self.used_mask_shape = None
        self.used_calibration = None
        self.raw_available = False

    def set_image_files(self, files: list[str] | None) -> None:
        """Set internal variables with respect of given list of files.

        Open each file and count number of images inside. Position of each image in the file
        and total number of images are stored in internal variables.
        """
        logger.info("Setting %d image files for batch processing", len(files))
        if files is None:
            return
        pos_map = []
        file_map = [0]
        image_counter = 0

        self.configuration.img_model.blockSignals(True)

        for i, file in enumerate(files):
            # Assume tif file contains only one image
            if file[-4:] == ".tif":
                n_img = 1
            else:
                if not os.path.exists(file):
                    return
                self.configuration.img_model.load(file)
                n_img = self.configuration.img_model.series_max
            image_counter += n_img
            pos_map += list(zip([i] * n_img, range(n_img)))
            file_map.append(image_counter)

        self.configuration.img_model.blockSignals(False)

        self.files = np.array(files)
        self.n_img_all = image_counter
        self.raw_available = True
        self.pos_map_all = np.array(pos_map)
        self.file_map = np.array(file_map)

    def try_load_old_format(self, data_file: h5py.File | h5py.Group) -> None:
        self.data = data_file["data"][()]
        self.binning = data_file["binning"][()]
        self.file_map = data_file["file_map"][()]
        raw_files = data_file["files"][()]
        if hasattr(raw_files, 'astype'):
            self.files = np.array([f.decode() if isinstance(f, bytes) else str(f) for f in raw_files.flat])
        else:
            self.files = np.array([str(f) for f in raw_files])
        self.pos_map = data_file["pos_map"][()]
        self.n_img = self.data.shape[0]
        self.n_img_all = self.data.shape[0]
        logger.info("Loading data using deprecated format")

        try:
            cal_file = str(data_file.attrs["calibration"])
            if os.path.isfile(cal_file):
                self.calibration_model.load(cal_file)
        except KeyError:
            logger.info("Calibration info is not found")

        if "mask" in data_file.attrs:
            try:
                mask_file = data_file.attrs["mask"]
                self.mask_model.load_mask(mask_file)
            except FileNotFoundError:
                logger.info("Mask file is not found")

        if "bkg" in data_file:
            self.data = data_file["bkg"][()]

    def load_proc_data(self, filename: str) -> None:
        """Load diffraction patterns and metadata from h5 file."""
        logger.info("Loading processed batch data from %s", filename)
        with h5py.File(filename, "r") as data_file:
            # ToDo To be removed
            if "processed/result" not in data_file:
                self.try_load_old_format(data_file)
                return
            self.data = data_file["processed/result/data"][()]
            self.binning = data_file["processed/result/binning"][()]
            self.n_img = self.data.shape[0]
            self.n_img_all = self.data.shape[0]

            if "process" not in data_file["processed"]:
                logger.info("No matching to raw data")
                return

            self.file_map = data_file["processed/process/file_map"][()]
            raw_files = data_file["processed/process/files"][()]
            self.files = np.array([f.decode() if isinstance(f, bytes) else str(f) for f in raw_files.flat])
            self.pos_map = data_file["processed/process/pos_map"][()]

            if isinstance(data_file["processed/process/cal_file"][()], bytes):
                self.used_calibration = str(
                    data_file["processed/process/cal_file"][()].decode("utf-8")
                )
            else:
                self.used_calibration = str(data_file["processed/process/cal_file"][()])
            if os.path.isfile(self.used_calibration):
                self.configuration.calibration_model.load(self.used_calibration)

            if "mask" in data_file["processed/process/"]:
                mask = data_file["processed/process/mask"][()]
                self.configuration.mask_model.set_dimension(mask.shape)
                self.configuration.mask_model.set_mask(mask)

            if "mask_file" in data_file["processed/process/"]:
                try:
                    self.used_mask = str(data_file["processed/process/mask_file"][()])
                    mask_data = np.array(Image.open(self.used_mask))
                    self.configuration.mask_model.set_dimension(mask_data.shape)
                    self.configuration.mask_model.load_mask(self.used_mask)
                except FileNotFoundError:
                    logger.info(f"Mask file {self.used_mask} is not found")

            if "bkg" in data_file["processed/process/"]:
                self.bkg = data_file["processed/process/bkg"][()]

    def save_proc_data(self, filename: str) -> None:
        """Save diffraction patterns to h5 file."""
        logger.info("Saving processed batch data to %s", filename)
        if os.path.dirname(filename) != "":
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        with h5py.File(filename, mode="w") as f:
            f.attrs["default"] = "processed"

            nxentry = f.create_group("processed")
            nxentry.attrs["NX_class"] = "NXentry"
            nxentry.attrs["default"] = "result"

            nxdata = nxentry.create_group("result")
            nxdata.attrs["NX_class"] = "NXdata"
            nxdata.attrs["signal"] = "data"
            nxdata.attrs["axes"] = [".", "binning"]

            nxprocess = nxentry.create_group("process")
            nxprocess.attrs["NX_class"] = "NXprocess"

            if self.used_calibration is not None:
                nxprocess["cal_file"] = str(self.used_calibration)

            if self.used_mask is not None:
                nxprocess["mask_file"] = str(self.used_mask)
                nxprocess["mask_shape"] = self.used_mask_shape

            nxprocess["int_method"] = "csr"
            nxprocess["int_unit"] = "2th_deg"
            nxprocess["num_points"] = self.binning.shape[0]

            if self.bkg is not None:
                nxprocess.create_dataset("bkg", data=self.bkg)

            nxdata.create_dataset("data", data=self.data)
            tth = nxdata.create_dataset("binning", data=self.binning)
            tth.attrs["unit"] = "deg"
            tth.attrs["long_name"] = "two_theta (degrees)"

            nxprocess.create_dataset("pos_map", data=self.pos_map)
            nxprocess.create_dataset("file_map", data=self.file_map)
            dt = h5py.string_dtype()
            nxprocess.create_dataset("files", data=list(self.files), dtype=dt)

    def save_as_csv(self, filename: str) -> None:
        """Save diffraction patterns to 3-columns csv file."""
        if os.path.dirname(filename) != "":
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        x = self.binning.repeat(self.n_img)
        y = (
            np.arange(self.n_img)[None, :]
            .repeat(self.binning.shape[0], axis=0)
            .flatten()
        )
        np.savetxt(
            filename,
            np.array(list(zip(x, y, self.data.T.flatten()))),
            delimiter=",",
            fmt="%f",
        )

    def integrate_raw_data(
        self,
        start: int,
        stop: int,
        step: int,
        use_all: bool = False,
        callback_fn: Callable[[int], bool] | None = None,
    ) -> None:
        """Integrate images from given file.

        If callback_fn returns False the integration will be aborted.
        """
        logger.info("Batch integrating raw data: frames %d to %d, step %d", start, stop, step)
        if self.configuration.use_mask:
            if self.configuration.mask_model.filename != "":
                self.used_mask = self.configuration.mask_model.filename
            mask = self.configuration.mask_model.get_mask()
            self.used_mask_shape = mask.shape

        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        azi_range = self.configuration.oned_azimuth_range

        if cal.can_use_dioptrin_batch(unit, azi_range):
            self._integrate_raw_data_dioptrin_batch(
                start, stop, step, use_all, callback_fn
            )
        else:
            self._integrate_raw_data_pyFAI(start, stop, step, use_all, callback_fn)

    def _integrate_raw_data_pyFAI(
        self,
        start: int,
        stop: int,
        step: int,
        use_all: bool = False,
        callback_fn: Callable[[int], bool] | None = None,
    ) -> None:
        intensity_data = []
        binning_data = []
        pos_map = []
        image_counter = 0
        current_file = ""

        # Block img_changed to prevent auto-integration and GUI updates
        self.configuration.img_model.img_changed.blocked = True
        last_callback_time = time.monotonic()
        try:
            for index in range(start, stop, step):
                if use_all:
                    file_index, pos = self.pos_map_all[index]
                else:
                    file_index, pos = self.pos_map[index]
                if file_index != current_file:
                    current_file = file_index
                    self.configuration.calibration_model.img_model.load(
                        self.files[file_index]
                    )
                    self.configuration.mask_model.set_dimension(
                        self.configuration.img_model.img_data.shape
                    )

                self.configuration.img_model.load_series_img(pos + 1)

                binning, intensity = self.configuration.integrate_image_1d(
                    update_pattern_model=False
                )
                image_counter += 1
                pos_map.append((file_index, pos))
                intensity_data.append(intensity)
                binning_data.append(binning)

                now = time.monotonic()
                if callback_fn is not None and now - last_callback_time > 0.1:
                    last_callback_time = now
                    if not callback_fn(image_counter):
                        break
        finally:
            self.configuration.img_model.img_changed.blocked = False

        # deal with different x lengths due to trimmed zeros:
        binning_lengths = [len(b) for b in binning_data]
        binning_max_length_ind = np.argmax(binning_lengths)
        binning_max_length = binning_lengths[binning_max_length_ind]
        binning = binning_data[binning_max_length_ind]

        padded_data = np.zeros((len(intensity_data), binning_max_length))
        for ind, intensity in enumerate(intensity_data):
            padded_data[ind, : len(intensity)] = intensity

        # finish and save everything

        if self.configuration.calibration_model.filename != "":
            self.used_calibration = self.configuration.calibration_model.filename
        self.pos_map = np.array(pos_map)
        self.binning = np.array(binning)
        self.data = padded_data
        self.bkg = None
        self.n_img = self.data.shape[0]

    def _integrate_raw_data_dioptrin_batch(
        self,
        start: int,
        stop: int,
        step: int,
        use_all: bool = False,
        callback_fn: Callable[[int], bool] | None = None,
    ) -> None:
        """Load frames through ImgModel, integrate via batch1d_iter with generator."""
        from dioptas.model.util.integration import iter_frames_indexed

        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        num_points = self.configuration.integration_rad_points

        if self.configuration.use_mask:
            mask = self.configuration.mask_model.get_mask()
        elif self.configuration.mask_model.roi is not None:
            mask = self.configuration.mask_model.roi_mask
        else:
            mask = None

        indices = list(range(start, stop, step))
        source = self.pos_map_all if use_all else self.pos_map

        # Configure integrator: load one image to get shape
        first_file_index = source[indices[0]][0]
        self.configuration.img_model.img_changed.blocked = True
        try:
            self.configuration.calibration_model.img_model.load(
                self.files[first_file_index]
            )
            self.configuration.mask_model.set_dimension(
                self.configuration.img_model.img_data.shape
            )
            img_shape = self.configuration.img_model.img_data.shape
            num_points = cal.sync_dioptrin_for_batch(mask, unit, num_points, img_shape)

            # Build pos_map for all indices
            all_pos_map = [(source[i][0], source[i][1]) for i in indices]

            intensity_data: list[np.ndarray] = []
            pos_map: list[tuple[int, int]] = []
            binning: np.ndarray | None = None
            aborted = False

            def frame_generator():
                yield from iter_frames_indexed(
                    self.configuration.img_model,
                    self.files,
                    source,
                    indices,
                    mask_model=self.configuration.mask_model,
                    abort_check=lambda: aborted,
                )

            result_iter = cal.dioptrin_batch1d_iter(frame_generator(), num_points)

            last_callback_time = time.monotonic()
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
                pos_map.append(all_pos_map[i])

                now = time.monotonic()
                if callback_fn is not None and now - last_callback_time > 0.1:
                    last_callback_time = now
                    if not callback_fn(i + 1):
                        aborted = True
                        break
        finally:
            self.configuration.img_model.img_changed.blocked = False

        self._finalize_batch_results(cal, intensity_data, pos_map, binning, unit)

    def set_integration_results(self, results: dict) -> None:
        """Apply pre-computed integration results.

        Accepts both pyFAI-style results (``binning_data`` with variable-length
        arrays) and dioptrin-style results (``binning`` with a single array).
        """
        intensity_data = results["intensity_data"]
        pos_map = results["pos_map"]

        if "binning_data" in results:
            # pyFAI path: variable-length arrays, need padding
            binning_data = results["binning_data"]
            binning_lengths = [len(b) for b in binning_data]
            max_len_ind = int(np.argmax(binning_lengths))
            max_len = binning_lengths[max_len_ind]
            binning = binning_data[max_len_ind]

            padded = np.zeros((len(intensity_data), max_len))
            for i, intensity in enumerate(intensity_data):
                padded[i, : len(intensity)] = intensity
            intensity_data = padded
        else:
            # dioptrin path: uniform-length arrays
            binning = results["binning"]
            intensity_data = np.array(intensity_data)

        self.pos_map = np.array(pos_map)
        self.binning = np.array(binning)
        self.data = intensity_data
        self.bkg = None
        self.n_img = self.data.shape[0]

    def _finalize_batch_results(
        self,
        cal: object,
        intensity_data: list[np.ndarray],
        pos_map: list[tuple[int, int]],
        binning: np.ndarray | None,
        unit: str,
    ) -> None:
        """Store batch integration results."""
        from dioptas.model.util.integration import convert_tth_to_d

        if not intensity_data:
            return

        if unit == "d_A":
            binning = convert_tth_to_d(binning, cal.pattern_geometry.wavelength)

        if self.configuration.calibration_model.filename != "":
            self.used_calibration = self.configuration.calibration_model.filename
        self.pos_map = np.array(pos_map)
        self.binning = np.array(binning)
        self.data = np.array(intensity_data)
        self.bkg = None
        self.n_img = self.data.shape[0]

    def extract_background(
        self,
        parameters: tuple,
        callback_fn: Callable[[int], bool] | None = None,
    ) -> None:
        """Subtract background calculated with respect of given parameters."""
        bkg = np.zeros(self.data.shape)
        auto_bkg = SmoothBrucknerBackground(*parameters)
        for i, y in enumerate(self.data):
            if callback_fn is not None:
                if not callback_fn(i):
                    break
            bkg[i] = auto_bkg.extract_background(Pattern(self.binning, y))
        self.bkg = bkg

    def normalize(self, range_ind: tuple[int, int] = (10, 30)) -> None:
        if self.data is None:
            return
        average_intensities = np.mean(self.data[:, range_ind[0] : range_ind[1]], axis=1)
        factors = average_intensities[0] / average_intensities
        self.data = (self.data.T * factors).T

    def get_image_info(self, index: int, use_all: bool = False) -> tuple[str | None, int | None]:
        """Get filename and image position in the file."""
        if use_all:
            if not self.raw_available:
                return None, None
            f_index, pos = self.pos_map_all[index]
        else:
            if self.pos_map is None:
                return "NA", index
            f_index, pos = self.pos_map[index]
        filename = self.files[f_index]
        return filename, pos

    def load_image(self, index: int, use_all: bool = False) -> None:
        """Load image in image model."""
        if not self.raw_available:
            return
        filename, pos = self.get_image_info(index, use_all)
        self.configuration.calibration_model.img_model.load(filename, pos)

    def get_next_folder_filenames(self) -> list[str]:
        """Loads all files from the next folder with similar file-endings."""
        folder_path, _ = os.path.split(self.files[0])
        next_folder_path = iterate_folder(folder_path, 1)
        files = []
        if next_folder_path is not None and os.path.exists(next_folder_path):
            for file in os.listdir(next_folder_path):
                if file.endswith(pathlib.Path(self.files[0]).suffix):
                    files.append(os.path.join(next_folder_path, file))
        files = sorted(files)
        return files[: self.n_img_all]

    def get_previous_folder_filenames(self) -> list[str]:
        """Loads all files from the previous folder with similar file-endings."""
        folder_path, _ = os.path.split(self.files[0])
        previous_folder_path = iterate_folder(folder_path, -1)
        files = []
        if previous_folder_path is not None and os.path.exists(previous_folder_path):
            for file in os.listdir(previous_folder_path):
                if file.endswith(pathlib.Path(self.files[0]).suffix):
                    files.append(os.path.join(previous_folder_path, file))
        files = sorted(files)
        return files[: self.n_img_all]


def iterate_folder(folder_path: str, step: int) -> str | None:
    pattern = re.compile(r"\d+")
    match_iterator = pattern.finditer(folder_path)
    new_directory_str = None
    for ind, match in enumerate(list(match_iterator)):
        number_span = match.span()
        left_ind = number_span[0]
        right_ind = number_span[1]
        number = int(folder_path[left_ind:right_ind]) + step
        if number < 0:
            number = 0
        new_directory_str = "{left_str}{number:0{len}}{right_str}".format(
            left_str=folder_path[:left_ind],
            number=number,
            len=right_ind - left_ind,
            right_str=folder_path[right_ind:],
        )
    return new_directory_str
