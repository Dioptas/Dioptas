# SPDX-License-Identifier: MIT

import logging

import numpy as np
import numpy.typing as npt
import h5py
import re

logger = logging.getLogger(__name__)


def first(array: npt.NDArray | h5py.Dataset) -> npt.NDArray | np.generic:
    """Get first element if the array has exactly one element, otherwise return full slice."""
    try:
        if isinstance(array, np.ndarray) and len(array) == 1:
            return array[0]
    except Exception:
        logger.debug("Could not extract single element from array, using full slice")
    return array[...]


class LambdaImage:
    def __init__(
        self,
        filename: str | None = None,
        file_list: list[str] | None = None,
    ) -> None:
        """Loads an image produced by a Lambda detector."""
        detector_identifiers: list[list[str | bytes]] = [
            ["/entry/instrument/detector/description", "Lambda"],
            ["/entry/instrument/detector/description", b"Lambda"],
        ]
        filenumber_list: list[int] = [1, 2, 3]
        regex_in: str = r"(.+_m)\d((_part\d+|).nxs)"
        regex_out: str = r"\g<1>{}\g<2>"
        data_path: str = "entry/instrument/detector/data"
        module_positions_path: str = "/entry/instrument/detector/translation/distance"

        if not filename:
            filename = file_list[0]

        try:
            nx_file: h5py.File = h5py.File(filename, "r")
        except OSError:
            raise IOError("not a loadable hdf5 file")

        for identifier in detector_identifiers:
            try:
                if first(nx_file[identifier[0]]) == identifier[1]:
                    break
            except KeyError:
                pass
        else:
            raise IOError("not a lambda image")

        # the image data is spread over multiple files, so we compile a list of them here
        lambda_files: list[h5py.File] = []
        if file_list:
            for f_name in file_list:
                try:
                    lambda_files.append(h5py.File(f_name, "r"))
                except OSError:
                    logger.debug("Could not open Lambda module file: %s", f_name)
        else:
            for moduleIndex in filenumber_list:
                try:
                    lambda_files.append(h5py.File(re.sub(regex_in, regex_out.format(moduleIndex), filename), "r"))
                except OSError:
                    logger.debug("Could not open Lambda module file %d", moduleIndex)

        self.file_list: list[str] | None = file_list
        self.full_img_data: list[h5py.Dataset] = [imageFile[data_path] for imageFile in lambda_files]
        self.shapes: npt.NDArray[np.int_] = np.array([module[0].shape for module in self.full_img_data])
        self._module_pos: npt.NDArray[np.int_] = np.array(
            [np.ravel(nxim[module_positions_path]).astype(int) for nxim in lambda_files]
        )
        self.img_idx: h5py.Dataset = lambda_files[0]['entry/instrument/detector/sequence_number']

        # remove any empty columns/rows to the left or top of the image data or shift any negative rows/columns into the positive
        np.subtract(self._module_pos, self._module_pos[:, 0].min(), self._module_pos, where=[1, 0, 0])
        np.subtract(self._module_pos, self._module_pos[0][1], self._module_pos, where=[0, 1, 0])
        self.series_max: int = lambda_files[0][data_path].shape[0]

    def get_image(self, image_nr: int) -> npt.NDArray[np.float64]:
        """Gets the data for the given image nr and stitches the tiles together."""
        tmp = self.shapes + self._module_pos[:, :2][:, ::-1]
        shape: tuple[int, int] = (np.max(tmp[:, 0]), np.max(tmp[:, 1]))
        image: npt.NDArray[np.float64] = np.zeros(shape)

        for modulenr, moduleImageData in enumerate(self.full_img_data):
            image[self._module_pos[modulenr, 1]:self._module_pos[modulenr, 1] + self.shapes[modulenr][0],
            self._module_pos[modulenr, 0]:self._module_pos[modulenr, 0] + self.shapes[modulenr][1]] = moduleImageData[
                image_nr]

        return image[::-1]
