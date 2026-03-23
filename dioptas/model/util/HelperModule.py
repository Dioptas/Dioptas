# SPDX-License-Identifier: MIT


import logging
import os
import re
import time
from collections.abc import Callable

import numpy as np
from colorsys import hsv_to_rgb

logger = logging.getLogger(__name__)

from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler


class _DirectoryChangeHandler(FileSystemEventHandler):
    """Watchdog handler that calls a callback on any directory change."""

    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback: Callable[[], None] = callback

    def on_any_event(self, event: FileSystemEvent) -> None:
        self._callback()


# Shared observer for all FileNameIterator instances.
# FSEvents on macOS does not allow multiple observers watching the same path,
# so we use a single Observer and schedule/unschedule individual watches.
_shared_observer: Observer = Observer()
_shared_observer.daemon = True
_shared_observer.start()


class FileNameIterator:
    # TODO create an File Index and then just get the next files according to this.
    # Otherwise searching a network is always to slow...

    def __init__(self, filename: str | None = None) -> None:
        self.acceptable_file_endings: list[str] = []
        self._watch: object | None = None
        self._dir_handler: _DirectoryChangeHandler = _DirectoryChangeHandler(
            self.add_new_files_to_list
        )
        self.create_timed_file_list: bool = False

        if filename is None:
            self.complete_path: str | None = None
            self.directory: str | None = None
            self.filename: str | None = None
            self.file_list: list[tuple[float, str]] = []
            self.ordered_file_list: list[tuple[float, str]] = []
            self.filename_list: list[str] = []
        else:
            self.complete_path = os.path.abspath(filename)
            self.directory, self.filename = os.path.split(self.complete_path)
            self.acceptable_file_endings.append(self.filename.split(".")[-1])

    def _get_files_list(self) -> list[tuple[float, str]]:
        t1 = time.time()
        filename_list = os.listdir(self.directory)
        files: list[str] = []
        for file in filename_list:
            if self.is_correct_file_type(file):
                files.append(file)
        paths = [os.path.join(self.directory, file) for file in files]
        file_list = [(os.path.getctime(path), path) for path in paths]
        self.filename_list = paths
        logger.debug("Time needed for getting files: %.3fs", time.time() - t1)
        return file_list

    def is_correct_file_type(self, filename: str) -> bool:
        for ending in self.acceptable_file_endings:
            if filename.endswith(ending):
                return True
        return False

    def _order_file_list(self) -> None:
        t1 = time.time()
        self.ordered_file_list = self.file_list
        self.ordered_file_list.sort(key=lambda x: x[0])

        logger.debug("Time needed for ordering files: %.3fs", time.time() - t1)

    def update_file_list(self) -> None:
        self.file_list = self._get_files_list()
        self._order_file_list()

    def _iterate_file_number(
        self, path: str, step: int, pos: int | None = None
    ) -> str | None:
        directory, file_str = os.path.split(path)
        pattern = re.compile(r"\d+")

        match_iterator = pattern.finditer(file_str)

        for ind, match in enumerate(reversed(list(match_iterator))):
            if (pos is None) or (ind == pos):
                number_span = match.span()
                left_ind = number_span[0]
                right_ind = number_span[1]
                number = int(file_str[left_ind:right_ind]) + step
                new_file_str = "{left_str}{number:0{len}}{right_str}".format(
                    left_str=file_str[:left_ind],
                    number=number,
                    len=right_ind - left_ind,
                    right_str=file_str[right_ind:],
                )
                new_file_str_no_leading_zeros = "{left_str}{number}{right_str}".format(
                    left_str=file_str[:left_ind],
                    number=number,
                    right_str=file_str[right_ind:],
                )
                new_complete_path = os.path.join(directory, new_file_str)
                if os.path.exists(new_complete_path):
                    self.complete_path = new_complete_path
                    return new_complete_path
                new_complete_path = os.path.join(
                    directory, new_file_str_no_leading_zeros
                )
                if os.path.exists(new_complete_path):
                    self.complete_path = new_complete_path
                    return new_complete_path
        return None

    def _iterate_folder_number(
        self, path: str, step: int, mec_mode: bool = False
    ) -> str | None:
        directory_str, file_str = os.path.split(path)
        pattern = re.compile(r"\d+")

        match_iterator = pattern.finditer(directory_str)

        for ind, match in enumerate(reversed(list(match_iterator))):
            number_span = match.span()
            left_ind = number_span[0]
            right_ind = number_span[1]
            number = int(directory_str[left_ind:right_ind]) + step
            new_directory_str = "{left_str}{number:0{len}}{right_str}".format(
                left_str=directory_str[:left_ind],
                number=number,
                len=right_ind - left_ind,
                right_str=directory_str[right_ind:],
            )
            logger.debug("MEC mode: %s", mec_mode)
            if mec_mode:
                match_file_iterator = pattern.finditer(file_str)
                for ind_file, match_file in enumerate(
                    reversed(list(match_file_iterator))
                ):
                    if ind_file != 2:
                        continue
                    number_span = match_file.span()
                    left_ind = number_span[0]
                    right_ind = number_span[1]
                    number = int(file_str[left_ind:right_ind]) + step
                    new_file_str = "{left_str}{number:0{len}}{right_str}".format(
                        left_str=file_str[:left_ind],
                        number=number,
                        len=right_ind - left_ind,
                        right_str=file_str[right_ind:],
                    )
                new_complete_path = os.path.join(new_directory_str, new_file_str)
                logger.debug("New complete path: %s", new_complete_path)
            else:
                new_complete_path = os.path.join(new_directory_str, file_str)
            if os.path.exists(new_complete_path):
                self.complete_path = new_complete_path
                return new_complete_path
        return None

    def get_next_filename(
        self,
        step: int = 1,
        filename: str | None = None,
        mode: str = "number",
        pos: int | None = None,
    ) -> str | None:
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None

        if mode == "time":
            time_stat = os.path.getctime(self.complete_path)
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            try:
                self.complete_path = self.ordered_file_list[cur_ind + step][1]
                return self.complete_path
            except IndexError:
                return None
        elif mode == "number":
            return self._iterate_file_number(self.complete_path, step, pos)
        return None

    def get_previous_filename(
        self,
        step: int = 1,
        filename: str | None = None,
        mode: str = "number",
        pos: int | None = None,
    ) -> str | None:
        """Tries to get the previous filename.

        mode can be either "number" or "time". "number" will decrement the last
        digits of the file name; "time" will get the previous file by creation time.
        """
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None

        if mode == "time":
            time_stat = os.path.getctime(self.complete_path)
            cur_ind = self.ordered_file_list.index((time_stat, self.complete_path))
            if cur_ind > 0:
                try:
                    self.complete_path = self.ordered_file_list[cur_ind - step][1]
                    return self.complete_path
                except IndexError:
                    return None
        elif mode == "number":
            return self._iterate_file_number(self.complete_path, -step, pos)
        return None

    def get_next_folder(
        self, filename: str | None = None, mec_mode: bool = False
    ) -> str | None:
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None
        return self._iterate_folder_number(self.complete_path, 1, mec_mode)

    def get_previous_folder(
        self, filename: str | None = None, mec_mode: bool = False
    ) -> str | None:
        if filename is not None:
            self.complete_path = filename

        if self.complete_path is None:
            return None
        return self._iterate_folder_number(self.complete_path, -1, mec_mode)

    def update_filename(self, new_filename: str) -> None:
        self.complete_path = os.path.abspath(new_filename)
        new_directory, file_str = os.path.split(self.complete_path)
        try:
            self.acceptable_file_endings.append(file_str.split(".")[-1])
        except AttributeError:
            logger.debug("Observer not initialized, skipping stop")
        if self.directory != new_directory:
            self._stop_observing()
            self.directory = new_directory
            self._start_observing()
            if self.create_timed_file_list:
                self.update_file_list()

        if self.create_timed_file_list and self.ordered_file_list == []:
            self.update_file_list()

    def _start_observing(self) -> None:
        if self.directory and os.path.isdir(self.directory):
            self._watch = _shared_observer.schedule(
                self._dir_handler, self.directory, recursive=False
            )

    def _stop_observing(self) -> None:
        if self._watch is not None:
            try:
                _shared_observer.unschedule(self._watch)
            except KeyError:
                logger.debug("Observer watch not found, skipping unwatch")
            self._watch = None

    def __del__(self) -> None:
        self._stop_observing()

    def add_new_files_to_list(self) -> None:
        """Checks for new files in folder and adds them to the sorted file list."""
        cur_filename_list = os.listdir(self.directory)
        cur_filename_list = [
            os.path.join(self.directory, filename)
            for filename in cur_filename_list
            if self.is_correct_file_type(filename)
        ]
        new_filename_list = [
            filename
            for filename in cur_filename_list
            if filename not in list(self.filename_list)
        ]
        self.filename_list = cur_filename_list
        for filename in new_filename_list:
            creation_time = os.path.getctime(filename)
            if len(self.ordered_file_list) > 0:
                if creation_time > self.ordered_file_list[-1][0]:
                    self.ordered_file_list.append((creation_time, filename))
                else:
                    for ind in range(len(self.ordered_file_list)):
                        if creation_time < self.ordered_file_list[ind][0]:
                            self.ordered_file_list.insert(
                                ind, (creation_time, filename)
                            )
                            break
            else:
                self.ordered_file_list.append((creation_time, filename))


def rotate_matrix_m90(matrix: np.ndarray) -> np.ndarray:
    return np.rot90(matrix, -1)


def rotate_matrix_p90(matrix: np.ndarray) -> np.ndarray:
    return np.rot90(matrix)


def get_base_name(filename: str) -> str:
    str = os.path.basename(filename)
    if "." in str:
        str = str.split(".")[:-1][0]
    return str


def calculate_color(ind: int) -> np.ndarray:
    s = 0.8
    v = 0.8
    h = (0.19 * (ind + 2)) % 1
    return np.array(hsv_to_rgb(h, s, v)) * 255


def rgb_to_hex(rgb: tuple[int, int, int] | np.ndarray) -> str:
    return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def convert_d_to_two_theta(
    d: float | np.ndarray, wavelength: float
) -> float | np.ndarray:
    return np.arcsin(wavelength / (2 * d)) / np.pi * 360


def get_partial_index(
    array: list[float] | np.ndarray, value: float
) -> float | None:
    """Calculates the partial index for a value from an array using linear interpolation.

    e.g. with array = [0,1,2,3,4,5] and value = 2.5 it would return 2.5, since it is
    in between the second and third element.
    """
    try:
        upper_ind = np.where(array >= value)[0]
        lower_ind = np.where(array < value)[0]
    except TypeError:
        return None

    try:
        spacing = array[upper_ind[0]] - array[lower_ind[-1]]
        new_pos = lower_ind[-1] + (value - array[lower_ind[-1]]) / spacing
    except IndexError:
        return None

    return new_pos


def get_partial_value(
    array: list[float] | np.ndarray, ind: float
) -> float | None:
    """Calculates the value for a non-integer index from an array using linear interpolation.

    e.g. with array = [0,2,4,6,8,10] and ind = 2.5 it would return 5, since it is
    in between the second and third element.
    """
    ind = np.asarray(ind).item()
    if ind < 0 or ind > len(array) - 1:
        return None

    floor_ind = int(np.floor(ind))
    if floor_ind == len(array) - 1:
        return float(array[floor_ind])
    step = array[floor_ind + 1] - array[floor_ind]
    value = array[floor_ind] + (ind - floor_ind) * step
    return float(value)


def reverse_interpolate_two_array(
    value1: float,
    array1: np.ndarray,
    value2: float,
    array2: np.ndarray,
    delta1: float = 0.1,
    delta2: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """Tries to reverse interpolate two values from two arrays with the same dimensions,
    and finds a common index for value1 and value2 in their respective arrays.
    The deltas define the search radius for a close value match to the arrays.
    """
    tth_ind = np.argwhere(np.abs(array1 - value1) < delta1)
    azi_ind = np.argwhere(np.abs(array2 - value2) < delta2)

    tth_ind_ravel = np.ravel_multi_index(
        (tth_ind[:, 0], tth_ind[:, 1]), dims=array1.shape
    )
    azi_ind_ravel = np.ravel_multi_index(
        (azi_ind[:, 0], azi_ind[:, 1]), dims=array2.shape
    )

    common_ind_ravel = np.intersect1d(tth_ind_ravel, azi_ind_ravel)
    result_ind = np.unravel_index(common_ind_ravel, dims=array1.shape)

    while len(result_ind[0]) > 1:
        if np.max(np.diff(array1)) > 0:
            delta1 = np.max(np.diff(array1[result_ind]))

        if np.max(np.diff(array2)) > 0:
            delta2 = np.max(np.diff(array2[result_ind]))

        tth_ind = np.argwhere(np.abs(array1[result_ind] - value1) < delta1)
        azi_ind = np.argwhere(np.abs(array2[result_ind] - value2) < delta2)

        logger.debug("result_ind: %s", result_ind)

        common_ind = np.intersect1d(tth_ind, azi_ind)
        result_ind = (result_ind[0][common_ind], result_ind[1][common_ind])

    return result_ind[0], result_ind[1]
