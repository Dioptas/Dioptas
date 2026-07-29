# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import copy
from collections.abc import Callable
from typing import Any

import numpy as np
from PIL import Image
import h5py

import fabio

from .util import Signal
from .state import ImgParams
from dioptas.model.loader.spe import SpeFile
from .util.NewFileWatcher import NewFileInDirectoryWatcher
from .util.HelperModule import rotate_matrix_p90, rotate_matrix_m90, FileNameIterator
from .util.ImgCorrection import (
    ImgCorrectionManager,
    ImgCorrectionInterface,
    TransferFunctionCorrection,
    FlatFieldCorrection,
)
from dioptas.model.loader.LambdaLoader import LambdaImage
from dioptas.model.loader.KaraboLoader import KaraboFile
from dioptas.model.loader.hdf5Loader import Hdf5Image
from dioptas.model.loader.FabioLoader import FabioLoader

logger = logging.getLogger(__name__)

#: image transformations by name; ImgParams.transformations stores the names,
#: the callable list is derived from this registry
TRANSFORMATION_FUNCTIONS = {
    "flipud": np.flipud,
    "fliplr": np.fliplr,
    "rotate_matrix_m90": rotate_matrix_m90,
    "rotate_matrix_p90": rotate_matrix_p90,
}


class ImgModel:
    """
    Main Image handling class. Supports several features:
        - loading image files in any format using fabio
        - iterating through files either by file number or time of creation
        - image transformations like rotating and flipping
        - setting a background image
        - setting an absorption correction (img_data is divided by this)

    In order to subscribe to changes of the data in the ImgModel, please use the img_changed QtSignal.
    The Signal will be called every time the img_data has changed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.filename: str = ""

        # All user-settable parameters live in the evented params dataclass;
        # the properties below delegate to it and add side effects.
        self.params: ImgParams = ImgParams()

        self.file_name_iterator: FileNameIterator = FileNameIterator()

        self.series_pos: int = 1
        self.series_max: int = 1
        self.selected_source: str | None = None

        self._img_data: np.ndarray | None = None
        self._img_data_background_subtracted: np.ndarray | None = None
        self._img_data_absorption_corrected: np.ndarray | None = None
        self._img_data_background_subtracted_absorption_corrected: np.ndarray | None = None

        self.background_filename: str = ""
        self._background_data: np.ndarray | None = None

        self.transfer_correction: TransferFunctionCorrection = TransferFunctionCorrection()
        self.flat_field_correction: FlatFieldCorrection = FlatFieldCorrection()

        # anything that gets loaded from an image file and needs to be reset if a file without these attributes is
        # loaded 2D array containing the current image
        self.loadable_data: list[dict[str, Any]] = [
            {
                "name": "img_data",
                "default": np.zeros((2048, 2048)),
                "attribute": "_img_data",
            },
            {"name": "file_info", "default": "", "attribute": "file_info"},
            {"name": "motors_info", "default": {}, "attribute": "motors_info"},
            {"name": "img_data_fabio", "default": None, "attribute": "_img_data_fabio"},
            # current position in the loaded series of images, starting at 1
            {"name": "series_pos", "default": 1, "attribute": "series_pos"},
            # maximum position/number of images in the loaded series, starting at 1
            {"name": "series_max", "default": 1, "attribute": "series_max"},
            # function to get an image in the current series. A function assigned to this attribute should take
            # a single parameter pos (position in the series starting at 0) and return a 2d array with the image data
            {
                "name": "series_get_image",
                "default": None,
                "attribute": "series_get_image",
            },
            # list of sources for different image series within 1 file. This is used by an HDF5 file with several
            # datasets
            {"name": "sources", "default": None, "attribute": "sources"},
            # a function to select a source:
            {"name": "select_source", "default": None, "attribute": "_select_source"},
        ]

        # set the loadable attributes to their defaults
        self.set_loadable_attributes({})

        self.file_info: str
        self.motors_info: dict[str, float]
        self._img_data_fabio: Any
        self.series_get_image: Callable[[int], np.ndarray] | None
        self.sources: list[str] | None
        self._select_source: Callable[[str], None] | None
        self.loader: FabioLoader | Hdf5Image | None = None

        self._img_corrections: ImgCorrectionManager = ImgCorrectionManager()
        # TODO: watching a directory should be open to any file type - an extension should  be added when a
        # new file is loaded with a previous non-existing file extension
        self._directory_watcher: NewFileInDirectoryWatcher = NewFileInDirectoryWatcher(
            file_types=[
                "img",
                "sfrm",
                "dm3",
                "edf",
                "xml",
                "cbf",
                "kccd",
                "msk",
                "spr",
                "tif",
                "tiff",
                "mccd",
                "mar3450",
                "pnm",
                "spe",
            ]
        )
        # define the signals
        self.img_changed: Signal = Signal()
        self.autoprocess_changed: Signal = Signal()
        self.transformations_changed: Signal = Signal()
        self.corrections_removed: Signal = Signal()

        self.transformations_changed.connect(self._update_correction_transformations)

        # side effects of settings changes live here (not in the property
        # setters), so a direct params write behaves exactly like the
        # property write
        self.params.events.connect(self._on_params_changed)

    def _on_params_changed(self, info) -> None:
        field = info.signal.name
        if field in ("factor", "background_scaling", "background_offset"):
            # normalize storage to float: an integer factor/scaling would
            # multiply integer-typed image data with wraparound. psygnal
            # updates storage on equal-compare writes without re-emitting.
            value = info.args[0]
            if not isinstance(value, float):
                setattr(self.params, field, float(value))
            if field != "factor":
                self._calculate_img_data()
            self.img_changed.emit()
        elif field == "autoprocess":
            if info.args[0]:
                self._directory_watcher.activate()
            else:
                self._directory_watcher.deactivate()

    def load(self, filename: str, pos: int = 0) -> None:
        """
        Loads an image file in any format known by fabIO, PIL or HDF5. Automatically performs all previous img
        transformations, recalculates background subtracted and absorption corrected image data.
        The img_changed signal will be emitted after the process.
        """
        filename = str(filename)  # since it could also be QString
        logger.info("Loading {0}.".format(filename))
        self.filename = filename

        image_file_data = self.get_image_data(filename, pos)
        self.set_loadable_attributes(image_file_data)

        self.file_name_iterator.update_filename(filename)
        self._directory_watcher.path = os.path.dirname(str(filename))

        self._perform_img_transformations()
        self._calculate_img_data()
        self.series_pos = pos + 1

        self.img_changed.emit()

    def get_image_data(self, filename: str, pos: int = 0) -> dict[str, Any]:
        """
        Tries to load the given file using different image loader libraries and returns a dictionary containing all
        retrieved file data.
        """
        img_loaders = [
            self.load_PIL,
            self.load_spe,
            self.load_fabio,
            self.load_lambda,
            self.load_karabo,
            self.load_hdf5,
        ]

        for loader in img_loaders:
            data = loader(filename, pos)
            if data:
                return data
        else:
            raise IOError("No handler found for given image with filename: " + filename)

    def set_loadable_attributes(self, loaded_data: dict[str, Any]) -> None:
        """
        Sets all attributes that change with the loading of an image to either their defaults or a given value.
        This assures that no leftover data will be kept when it is not overwritten by the new image.
        """
        for attribute in self.loadable_data:
            if attribute["name"] in loaded_data:
                self.__setattr__(attribute["attribute"], loaded_data[attribute["name"]])
            else:
                self.__setattr__(
                    attribute["attribute"], copy.copy(attribute["default"])
                )

    def load_PIL(self, filename: str, *args: Any) -> dict[str, Any] | None:
        """
        Loads an image using the PIL library. Also returns file and motor info if present.
        """
        data = {}
        try:
            im = Image.open(filename)
            if np.prod(im.size) <= 1:
                im.close()
                return False
            data["img_data"] = np.array(im)[::-1]
            try:
                data["file_info"] = self._get_file_info(im)
                data["motors_info"] = self._get_motors_info(im)
            except AttributeError:
                pass
            im.close()
            return data

        except IOError:
            return None

    def load_spe(self, filename: str, *args: Any) -> dict[str, Any] | None:
        """Loads an image using the builtin spe library."""
        if os.path.splitext(filename)[1].lower() == ".spe":
            spe = SpeFile(filename)
            return {"img_data": spe.img}
        else:
            return None

    def load_fabio(self, filename: str, frame_index: int = 0) -> dict[str, Any] | None:
        """Loads an image using the fabio library."""
        try:
            self.loader = FabioLoader(filename)
            return {
                "img_data_fabio": self.loader.fabio_image,
                "img_data": self.loader.get_image(frame_index),
                "series_max": self.loader.series_max,
                "series_get_image": self.loader.get_image,
            }
        except (IOError, fabio.fabioutils.NotGoodReader):
            return None

    def load_lambda(self, filename: str, frame_index: int = 0) -> dict[str, Any] | None:
        """Loads an image made by a lambda detector using the builtin lambda library."""
        try:
            lambda_im = LambdaImage(filename)
        except IOError:
            return None

        if frame_index >= lambda_im.series_max:
            return None
        return {
            "img_data": lambda_im.get_image(frame_index),
            "series_max": lambda_im.series_max,
            "series_get_image": lambda_im.get_image,
        }

    def load_karabo(self, filename: str, frame_index: int = 0) -> dict[str, Any] | None:
        """Loads an Imageseries created from within the karabo-framework at XFEL."""
        try:
            karabo_file = KaraboFile(filename)
        except IOError:
            return None
        if frame_index >= karabo_file.series_max:
            return None
        return {
            "img_data": karabo_file.get_image(frame_index),
            "series_max": karabo_file.series_max,
            "series_get_image": karabo_file.get_image,
        }

    def load_hdf5(self, filename: str, frame_index: int = 0) -> dict[str, Any]:
        """Loads an ESRF hdf5 file."""

        hdf5_image = Hdf5Image(filename)
        self.loader = hdf5_image
        self.selected_source = hdf5_image.image_sources[0]

        return {
            "img_data": hdf5_image.get_image(frame_index),
            "series_max": hdf5_image.series_max,
            "series_get_image": hdf5_image.get_image,
            "sources": hdf5_image.image_sources,
            "select_source": hdf5_image.select_source,
        }

    def select_source(self, source: str) -> None:
        """Selects a source from the available sources and loads updates the current image in the model."""
        self._select_source(source)
        self.selected_source = source
        self.series_max = self.loader.series_max
        self.series_pos = min(self.series_pos, self.series_max)
        self._img_data = self.series_get_image(self.series_pos - 1)

        self._perform_img_transformations()
        self._calculate_img_data()

        self.img_changed.emit()

    def save(self, filename: str) -> None:
        """Saves the current file as another image file, the raw data is used for saving."""
        logger.info("Saving image to %s", filename)
        try:
            self._img_data_fabio.save(filename)
        except AttributeError:
            im_array = np.int32(np.copy(np.flipud(self._img_data)))
            im = Image.fromarray(im_array)
            im.save(filename)

    def load_background(self, filename: str) -> None:
        """
        Loads an image file as background in any format known by fabIO. Automatically performs all previous img
        transformations, recalculates background subtracted and absorption corrected image data.
        The img_changed signal will be emitted after the process.
        """
        logger.info("Loading background image: %s", filename)
        self.background_filename = filename

        self._background_data = self.get_image_data(filename)["img_data"]

        self._perform_background_transformations()

        if self._background_data.shape != self._img_data.shape:
            self._background_data = None
            self._calculate_img_data()
            self.img_changed.emit()
            raise BackgroundDimensionWrongException()

        self._calculate_img_data()
        self.img_changed.emit()

    def add(self, filename: str) -> None:
        """
        Adds an image file in any format known by fabIO. Automatically performs all previous img transformations and
        recalculates background subtracted and absorption corrected image data.
        The img_changed signal will be emitted after the process.
        """
        filename = str(filename)  # since it could also be QString

        img_data = self.get_image_data(filename)["img_data"]

        for transformation in self.img_transformations:
            img_data = transformation(img_data)

        if not self._img_data.shape == img_data.shape:
            return

        logger.info("Adding {0}.".format(filename))

        if (
            self._img_data.dtype == np.uint16
        ):  # if dtype is only uint16 we will convert to 32 bit, so that more
            # additions are possible
            self._img_data = self._img_data.astype(np.uint32)

        self._img_data += img_data

        self._calculate_img_data()
        self.img_changed.emit()

    def _image_and_background_shape_equal(self) -> bool:
        """Tests if the original image and original background image have the same shape."""
        if self._background_data is None:
            return True
        if self._background_data.shape == self._img_data.shape:
            return True
        return False

    def _reset_background(self) -> None:
        """Resets the background data to None."""
        self.background_filename = ""
        self._background_data = None
        self._background_data_fabio = None
        self._calculate_img_data()

    def reset_background(self) -> None:
        logger.debug("Resetting background image")
        self._reset_background()
        self.img_changed.emit()

    def has_background(self) -> bool:
        return self._background_data is not None

    @property
    def background_data(self) -> np.ndarray | None:
        return self._background_data

    @property
    def untransformed_background_data(self) -> np.ndarray:
        self._reset_background_transformations()
        background_data = np.copy(self.background_data)
        self._perform_background_transformations()
        return background_data

    @background_data.setter
    def background_data(self, new_data: np.ndarray | None) -> None:
        self._background_data = new_data
        self._calculate_img_data()
        self.img_changed.emit()

    @property
    def background_scaling(self) -> float:
        return self.params.background_scaling

    @background_scaling.setter
    def background_scaling(self, new_value: float) -> None:
        self.params.background_scaling = new_value

    @property
    def background_offset(self) -> float:
        return self.params.background_offset

    @background_offset.setter
    def background_offset(self, new_value: float) -> None:
        self.params.background_offset = new_value

    @property
    def img_transformations(self) -> list[Callable[[np.ndarray], np.ndarray]]:
        """The applied transformations as callables, derived from the
        canonical name list in the params."""
        return [
            TRANSFORMATION_FUNCTIONS[name] for name in self.params.transformations
        ]

    @img_transformations.setter
    def img_transformations(
        self, transformations: list[Callable[[np.ndarray], np.ndarray]]
    ) -> None:
        self.params.transformations = [t.__name__ for t in transformations]

    def _append_transformation(self, name: str) -> None:
        # reassignment (not in-place append) so the params event fires
        self.params.transformations = self.params.transformations + [name]

    @property
    def file_iteration_mode(self) -> str:
        return self.params.file_iteration_mode

    @file_iteration_mode.setter
    def file_iteration_mode(self, new_mode: str) -> None:
        self.params.file_iteration_mode = new_mode

    def load_series_img(self, pos: int) -> None:
        """
        Takes a position in the series to load, sanitizes it and puts the result from the function assigned to
        series_get_image into _img_data. series_get_image gets called with a position starting from 0, all other series
        pos values start at one as shown to the user.
        """
        logger.debug("Loading series image at position %d", pos)
        pos = min(max(pos, 1), self.series_max)
        if self.series_pos == pos:
            return

        if self.series_get_image is None:
            self._reload_series_file()

        self.series_pos = pos
        self._img_data = self.series_get_image(pos - 1)

        self._perform_img_transformations()
        self._calculate_img_data()

        self.img_changed.emit()

    def _reload_series_file(self) -> None:
        """Re-opens the current file to restore the series_get_image function,
        e.g. after loading a project where only pixel data was saved."""
        if not self.filename or not os.path.exists(self.filename):
            return
        image_file_data = self.get_image_data(self.filename, self.series_pos - 1)
        if image_file_data and "series_get_image" in image_file_data:
            self.series_get_image = image_file_data["series_get_image"]
            self.series_max = image_file_data.get("series_max", self.series_max)
            if "sources" in image_file_data:
                self.sources = image_file_data["sources"]
            if "select_source" in image_file_data:
                self._select_source = image_file_data["select_source"]

    def load_next_file(self, step: int = 1, pos: int | None = None) -> None:
        """Loads the next file based on the current iteration mode and the step you specify."""
        next_file_name = self.file_name_iterator.get_next_filename(
            mode=self.file_iteration_mode, step=step, pos=pos
        )
        if next_file_name is not None:
            self.load(next_file_name)

    def load_previous_file(self, step: int = 1, pos: int | None = None) -> None:
        """Loads the previous file based on the current iteration mode and the step specified."""
        previous_file_name = self.file_name_iterator.get_previous_filename(
            mode=self.file_iteration_mode, step=step, pos=pos
        )
        if previous_file_name is not None:
            self.load(previous_file_name)

    def load_next_folder(self, mec_mode: bool = False) -> None:
        """
        Loads a file with the current filename in the next folder, whereby the folder has to be iteratable by numbers.

        :param mec_mode: enables specific mode for MEC beamline at SLAC, where the folders and the
                         files change during increment.
        """
        next_file_name = self.file_name_iterator.get_next_folder(mec_mode=mec_mode)
        if next_file_name is not None:
            self.load(next_file_name)

    def load_previous_folder(self, mec_mode: bool = False) -> None:
        """
        Loads a file with the current filename in the previous folder, whereby the folder has to be iteratable by
        numbers.

        :param mec_mode: enables specific mode for MEC beamline at SLAC, where the folders and the
                         files change during increment.
        """

        next_previous_name = self.file_name_iterator.get_previous_folder(
            mec_mode=mec_mode
        )
        if next_previous_name is not None:
            self.load(next_previous_name)

    def set_file_iteration_mode(self, mode: str) -> None:
        """
        Sets the file iteration mode for the load_next_file and load_previous_file functions. Possible modes:
            * 'number' will increment or decrement based on numbers in the filename.
            * 'time' will increment or decrement based on creation time for the files.
        """
        if mode == "number":
            self.file_iteration_mode = "number"
            self.file_name_iterator.create_timed_file_list = False
        elif mode == "time":
            self.file_iteration_mode = "time"
            self.file_name_iterator.create_timed_file_list = True
            self.file_name_iterator.update_filename(self.filename)

    def _calculate_img_data(self) -> None:
        """
        Calculates compound img_data based on the state of the object. This function is used internally to not compute
        those img arrays every time somebody requests the image data by get_img_data() and img_data.
        """

        # check that all data has the same dimensions
        if self._background_data is not None:
            if self._img_data.shape != self._background_data.shape:
                self._background_data = None
        if self._img_corrections.has_items():
            if self._img_data.shape != self._img_corrections.shape:
                self._img_corrections.clear()
                self.transfer_correction.reset()
                self.flat_field_correction.reset()
                self.corrections_removed.emit()

        # calculate the current _img_data
        if self._background_data is not None and not self._img_corrections.has_items():
            self._img_data_background_subtracted = self._img_data - (
                self.params.background_scaling * self._background_data
                + self.params.background_offset
            )
        elif self._background_data is None and self._img_corrections.has_items():
            self._img_data_absorption_corrected = (
                self._img_data / self._img_corrections.get_data()
            )

        elif self._background_data is not None and self._img_corrections.has_items():
            self._img_data_background_subtracted_absorption_corrected = (
                self._img_data
                - (
                    self.params.background_scaling * self._background_data
                    + self.params.background_offset
                )
            ) / self._img_corrections.get_data()

    @property
    def img_data(self) -> np.ndarray | None:
        """
        The image based on the current state of the ImgData object. It will apply all image correction as well as
        background subtraction. In case you want the raw data without corrections, please use the
        raw_img_data property.
        """
        # if self._img_data is None:
        #     return None

        if self._background_data is None and not self._img_corrections.has_items():
            return self._img_data * self.factor

        elif (
            self._background_data is not None and not self._img_corrections.has_items()
        ):
            return self._img_data_background_subtracted * self.factor

        elif self._background_data is None and self._img_corrections.has_items():
            return self._img_data_absorption_corrected * self.factor

        elif self._background_data is not None and self._img_corrections.has_items():
            return (
                self._img_data_background_subtracted_absorption_corrected * self.factor
            )

    @property
    def raw_img_data(self) -> np.ndarray | None:
        return self._img_data

    @property
    def untransformed_raw_img_data(self) -> np.ndarray:
        self._reset_img_transformations()
        img_data = np.copy(self.raw_img_data)
        self._perform_img_transformations()
        return img_data

    def rotate_img_p90(self) -> None:
        """
        Rotates the image by 90 degree and updates the background accordingly (does not effect absorption correction).
        The transformation is saved and applied to every new image and background image loaded.
        The img_changed signal will be emitted after the process.
        """
        logger.debug("Rotating image +90°")
        self._img_data = rotate_matrix_p90(self._img_data)

        if self._background_data is not None:
            self._background_data = rotate_matrix_p90(self._background_data)

        self._append_transformation("rotate_matrix_p90")

        self.transformations_changed.emit()
        self._calculate_img_data()
        self.img_changed.emit()

    def rotate_img_m90(self) -> None:
        """
        Rotates the image by -90 degree and updates the background accordingly (does not effect absorption correction).
        The transformation is saved and applied to every new image and background image loaded.
        The img_changed signal will be emitted after the process.
        """
        logger.debug("Rotating image -90°")
        self._img_data = rotate_matrix_m90(self._img_data)
        if self._background_data is not None:
            self._background_data = rotate_matrix_m90(self._background_data)
        self._append_transformation("rotate_matrix_m90")
        self.transformations_changed.emit()

        self._calculate_img_data()
        self.img_changed.emit()

    def flip_img_horizontally(self) -> None:
        """
        Flips image about a horizontal axis and updates the background accordingly (does not effect absorption
        correction). The transformation is saved and applied to every new image and background image loaded.
        The img_changed signal will be emitted after the process.
        """
        logger.debug("Flipping image horizontally")
        self._img_data = np.fliplr(self._img_data)
        if self._background_data is not None:
            self._background_data = np.fliplr(self._background_data)
        self._append_transformation("fliplr")
        self.transformations_changed.emit()

        self._calculate_img_data()
        self.img_changed.emit()

    def flip_img_vertically(self) -> None:
        """
        Flips image about a vertical axis and updates the background accordingly (does not effect absorption
        correction). The transformation is saved and applied to every new image and background image loaded.
        The img_changed signal will be emitted after the process.
        """
        logger.debug("Flipping image vertically")
        self._img_data = np.flipud(self._img_data)
        if self._background_data is not None:
            self._background_data = np.flipud(self._background_data)
        self._append_transformation("flipud")
        self.transformations_changed.emit()

        self._calculate_img_data()
        self.img_changed.emit()

    def reset_transformations(self, img_changed: bool = True) -> None:
        """
        Reverts all image transformations and resets the transformation stack.
        The img_changed signal will be emitted after the process, if set to true.
        """
        logger.debug("Resetting all image transformations")
        self._reset_img_transformations()
        self._reset_background_transformations()

        self.img_transformations = []
        self.transformations_changed.emit()

        self._calculate_img_data()
        if img_changed:
            self.img_changed.emit()

    def set_transformations(self, names: list[str]) -> None:
        """Reconciles the image to exactly the given list of transformations.

        The rotate/flip methods apply their change to the pixels and then
        record the name, so ``params.transformations`` is a log of what was
        done rather than something the image is derived from — assigning to it
        alone leaves the pixels as they were. Undo needs the pixels to follow,
        so this un-applies what is currently recorded and applies the target
        list instead.
        """
        if list(names) == list(self.params.transformations):
            return
        self._reset_img_transformations()
        self._reset_background_transformations()
        self.params.transformations = list(names)
        self._perform_img_transformations()
        self._perform_background_transformations()
        self.transformations_changed.emit()

        self._calculate_img_data()
        self.img_changed.emit()

    def _update_correction_transformations(self) -> None:
        self.transfer_correction.set_img_transformations(self.img_transformations)
        self.flat_field_correction.set_img_transformations(self.img_transformations)

    def _reset_img_transformations(self) -> None:
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                self._img_data = rotate_matrix_m90(self._img_data)
            elif transformation == rotate_matrix_m90:
                self._img_data = rotate_matrix_p90(self._img_data)
            else:
                self._img_data = transformation(self._img_data)

    def _reset_background_transformations(self) -> None:
        if self._background_data is None:
            return

        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                self._background_data = rotate_matrix_m90(self._background_data)
            elif transformation == rotate_matrix_m90:
                self._background_data = rotate_matrix_p90(self._background_data)
            else:
                self._background_data = transformation(self._background_data)

    def _perform_img_transformations(self) -> None:
        """Performs all saved image transformation on original image."""
        for transformation in self.img_transformations:
            self._img_data = transformation(self._img_data)

    def _perform_background_transformations(self) -> None:
        """Performs all saved image transformation on background image."""
        if self._background_data is not None:
            for transformation in self.img_transformations:
                self._background_data = transformation(self._background_data)

    def get_transformations_string_list(self) -> list[str]:
        transformation_list = []
        for transformation in self.img_transformations:
            transformation_list.append(transformation.__name__)
        return transformation_list

    def load_transformations_string_list(self, transformations: list[str]) -> None:
        self._reset_img_transformations()
        self._reset_background_transformations()
        self.img_transformations = []
        for transformation in transformations:
            if transformation == "flipud":
                self._append_transformation("flipud")
            elif transformation == "fliplr":
                self._append_transformation("fliplr")
            elif transformation == "rotate_matrix_m90":
                self._append_transformation("rotate_matrix_m90")
            elif transformation == "rotate_matrix_p90":
                self._append_transformation("rotate_matrix_p90")
        self._perform_img_transformations()
        self._perform_background_transformations()

    def add_img_correction(self, correction: ImgCorrectionInterface, name: str | None = None) -> None:
        """
        Adds a correction to be applied to the image. Corrections are applied multiplicative for each pixel and after
        each other, depending on the order of addition.
        """
        logger.info("Adding image correction: %s", name)
        self._img_corrections.add(correction, name)
        self._calculate_img_data()
        self.img_changed.emit()

    def get_img_correction(self, name: str) -> ImgCorrectionInterface | None:
        """Returns the correction with the specified name."""
        return self._img_corrections.get_correction(name)

    def delete_img_correction(self, name: str | None = None) -> None:
        """Deletes a correction from the correction calculation. If no name is specified, the last added
        correction is deleted."""
        logger.info("Deleting image correction: %s", name)
        self._img_corrections.delete(name)
        self._calculate_img_data()
        self.img_changed.emit()

    def enable_transfer_function(self) -> None:
        if (
            self.transfer_correction.get_data() is not None
            and self.get_img_correction("transfer") is None
        ):
            self.add_img_correction(self.transfer_correction, "transfer")
        if self.get_img_correction("transfer") is not None:
            self._calculate_img_data()
            self.img_changed.emit()

    def disable_transfer_function(self) -> None:
        if self.get_img_correction("transfer") is not None:
            self.delete_img_correction("transfer")

    def enable_flat_field(self) -> None:
        if (
            self.flat_field_correction.get_data() is not None
            and self.get_img_correction("flat_field") is None
        ):
            self.add_img_correction(self.flat_field_correction, "flat_field")
        if self.get_img_correction("flat_field") is not None:
            self._calculate_img_data()
            self.img_changed.emit()

    def disable_flat_field(self) -> None:
        if self.get_img_correction("flat_field") is not None:
            self.delete_img_correction("flat_field")

    @property
    def img_corrections(self) -> ImgCorrectionManager:
        return self._img_corrections

    def has_corrections(self) -> bool:
        """Returns whether the ImgData object has active absorption corrections or not."""
        return self._img_corrections.has_items()

    def _get_file_info(self, image: Image.Image) -> str:
        """Reads the file info from tif_tags and returns a file info."""
        result = ""
        end_result = ""
        tags = image.tag
        useful_keys = []
        for key in tags.keys():
            if key > 300:
                useful_keys.append(key)

        useful_keys.sort()
        for key in useful_keys:
            tag = tags[key][0]
            if isinstance(tag, str):
                new_line = str(tag) + "\n"
                new_line = new_line.replace(":", ":\t", 1)
                if "TIFFImageDescription" in new_line:
                    end_result = new_line
                else:
                    result += new_line
        return result + end_result

    def _get_motors_info(self, image: Image.Image) -> dict[str, float]:
        """Reads the file info from tif_tags and returns positions of vertical, horizontal, focus and omega motors."""
        result = {}
        tags = image.tag

        useful_tags = ["Horizontal:", "Vertical:", "Focus:", "Omega:"]

        try:
            tag_values = tags.itervalues()
        except AttributeError:
            tag_values = tags.values()

        for value in tag_values:
            for key in useful_tags:
                if key in str(value):
                    k, v = str(value[0]).split(":")
                    result[str(k)] = float(v)
        return result

    @property
    def autoprocess(self) -> bool:
        return self.params.autoprocess

    @autoprocess.setter
    def autoprocess(self, new_val: bool) -> None:
        self.params.autoprocess = new_val

    @property
    def factor(self) -> float:
        return self.params.factor

    @factor.setter
    def factor(self, new_value: float) -> None:
        self.params.factor = new_value

    def get_img_data_float64(self) -> np.ndarray:
        """Return current image data as a contiguous float64 array.

        Convenience method used by batch/map integration pipelines.
        """
        return np.ascontiguousarray(self.img_data, dtype=np.float64)

    def _apply_frame_pipeline(self, raw_frame: np.ndarray) -> np.ndarray:
        """Apply transformations and corrections to a raw frame.

        Sets internal state and returns the processed image as contiguous
        float64.  Used by batch processing to bypass the series position
        check and signal emission of :meth:`load_series_img`.
        """
        self._img_data = raw_frame
        self._perform_img_transformations()
        self._calculate_img_data()
        return np.ascontiguousarray(self.img_data, dtype=np.float64)

    def blockSignals(self, block: bool = True) -> None:
        for member in vars(self):
            attr = getattr(self, member)
            if isinstance(attr, Signal):
                attr.blocked = block


class BackgroundDimensionWrongException(Exception):
    pass
