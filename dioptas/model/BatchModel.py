import logging
import os
import pathlib

import h5py
import numpy as np
from qtpy import QtCore
from PIL import Image

from .util import extract_background
from .util.HelperModule import FileNameIterator

logger = logging.getLogger(__name__)


class BatchModel(QtCore.QObject):
    """
    Class describe a model for batch integration
    """

    def __init__(self, calibration_model, mask_model):
        super(BatchModel, self).__init__()

        self.data = None
        self.bkg = None
        self.binning = None
        self.file_map = None
        self.files = None
        self.pos_map = None
        self.pos_map_all = None
        self.n_img = None
        self.n_img_all = None
        self.raw_available = False

        self.calibration_model = calibration_model
        self.mask_model = mask_model
        self.used_mask = None
        self.used_mask_shape = None
        self.used_calibration = None

    def reset_data(self):
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

    def set_image_files(self, files):
        """
        Set internal variables with respect of given list of files.

        Open each file and count number of images inside. Position of each image in the file
        and total number of images are stored in internal variables.

        :param files: List of file names including path
        """
        if files is None:
            return
        pos_map = []
        file_map = [0]
        image_counter = 0
        for i, file in enumerate(files):
            # Assume tif file contains only one image
            if file[-4:] == '.tif':
                n_img = 1
            else:
                if not os.path.exists(file):
                    return
                self.calibration_model.img_model.load(file)
                n_img = self.calibration_model.img_model.series_max
            image_counter += n_img
            pos_map += list(zip([i] * n_img, range(n_img)))
            file_map.append(image_counter)

        self.files = np.array(files)
        self.n_img_all = image_counter
        self.raw_available = True
        self.pos_map_all = np.array(pos_map)
        self.file_map = np.array(file_map)

    def try_load_old_format(self, data_file):
        self.data = data_file['data'][()]
        self.binning = data_file['binning'][()]
        self.file_map = data_file['file_map'][()]
        self.files = data_file['files'][()].astype('U')
        self.pos_map = data_file['pos_map'][()]
        self.n_img = self.data.shape[0]
        self.n_img_all = self.data.shape[0]
        logger.info("Loading data using deprecated format")

        try:
            cal_file = str(data_file.attrs['calibration'])
            if os.path.isfile(cal_file):
                self.calibration_model.load(cal_file)
        except KeyError:
            logger.info("Calibration info is not found")

        if 'mask' in data_file.attrs:
            try:
                mask_file = data_file.attrs['mask']
                self.mask_model.load_mask(mask_file)
            except FileNotFoundError:
                logger.info("Mask file is not found")

        if 'bkg' in data_file:
            self.data = data_file['bkg'][()]

    def load_proc_data(self, filename):
        """
        Load diffraction patterns and metadata from h5 file

        """
        with h5py.File(filename, "r") as data_file:
            # ToDo To be removed
            if 'processed/result' not in data_file:
                self.try_load_old_format(data_file)
                return
            self.data = data_file['processed/result/data'][()]
            self.binning = data_file['processed/result/binning'][()]
            self.n_img = self.data.shape[0]
            self.n_img_all = self.data.shape[0]

            if 'process' not in data_file['processed']:
                logger.info("No matching to raw data")
                return

            self.file_map = data_file['processed/process/file_map'][()]
            self.files = data_file['processed/process/files'][()].astype('U')
            self.pos_map = data_file['processed/process/pos_map'][()]

            if isinstance(data_file['processed/process/cal_file'][()], bytes):
                self.used_calibration = str(data_file['processed/process/cal_file'][()].decode("utf-8"))
            else:
                self.used_calibration = str(data_file['processed/process/cal_file'][()])
            if os.path.isfile(self.used_calibration):
                self.calibration_model.load(self.used_calibration)

            if 'mask' in data_file['processed/process/']:
                mask = data_file['processed/process/mask'][()]
                self.mask_model.set_dimension(mask.shape)
                self.mask_model.set_mask(mask)

            if 'mask_file' in data_file['processed/process/']:
                try:
                    self.used_mask = str(data_file['processed/process/mask_file'][()])
                    mask_data = np.array(Image.open(self.used_mask))
                    self.mask_model.set_dimension(mask_data.shape)
                    self.mask_model.load_mask(self.used_mask)
                except FileNotFoundError:
                    logger.info(f"Mask file {self.used_mask} is not found")

            if 'bkg' in data_file['processed/process/']:
                self.bkg = data_file['processed/process/bkg'][()]

    def save_proc_data(self, filename):
        """
        Save diffraction patterns to h5 file
        """
        if os.path.dirname(filename) != '':
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        with h5py.File(filename, mode="w") as f:
            f.attrs['default'] = 'processed'

            nxentry = f.create_group('processed')
            nxentry.attrs["NX_class"] = 'NXentry'
            nxentry.attrs['default'] = 'result'

            nxdata = nxentry.create_group('result')
            nxdata.attrs["NX_class"] = 'NXdata'
            nxdata.attrs["signal"] = 'data'
            nxdata.attrs["axes"] = ['.', 'binning']

            nxprocess = nxentry.create_group('process')
            nxprocess.attrs["NX_class"] = 'NXprocess'

            if self.used_calibration is not None:
                nxprocess['cal_file'] = str(self.used_calibration)

            if self.used_mask is not None:
                nxprocess["mask_file"] = str(self.used_mask)
                nxprocess['mask_shape'] = self.used_mask_shape

            nxprocess['int_method'] = 'csr'
            nxprocess['int_unit'] = '2th_deg'
            nxprocess['num_points'] = self.binning.shape[0]

            if self.bkg is not None:
                nxprocess.create_dataset("bkg", data=self.bkg)

            nxdata.create_dataset("data", data=self.data)
            tth = nxdata.create_dataset("binning", data=self.binning)
            tth.attrs["unit"] = 'deg'
            tth.attrs['long_name'] = 'two_theta (degrees)'

            nxprocess.create_dataset("pos_map", data=self.pos_map)
            nxprocess.create_dataset("file_map", data=self.file_map)
            nxprocess.create_dataset("files", data=self.files.astype('S'))

    def save_as_csv(self, filename):
        """
        Save diffraction patterns to 3-columns csv file
        """
        if os.path.dirname(filename) != '':
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        x = self.binning.repeat(self.n_img)
        y = np.arange(self.n_img)[None, :].repeat(self.binning.shape[0], axis=0).flatten()
        np.savetxt(filename, np.array(list(zip(x, y, self.data.T.flatten()))), delimiter=',', fmt='%f')

    def integrate_raw_data(self, num_points, start, stop, step, use_all=False, callback_fn=None,
                           use_mask=False):
        """
        Integrate images from given file

        :param num_points: Numbers of radial bins
        :param start: Start image index from integration
        :param stop: Stop image index from integration
        :param step: Step along images to integrate
        :param use_all: Use all images. If False use only images, that were already integrated.
        :param callback_fn: callback function which is called each iteration with the current image number as parameter,
                            if it returns False the integration will be aborted.
        :param use_mask: use mask if True
        """
        intensity_data = []
        binning_data = []
        pos_map = []
        image_counter = 0
        current_file = ''
        if use_mask:
            if self.mask_model.filename != '':
                self.used_mask = self.mask_model.filename
            mask = self.mask_model.get_mask()
            self.used_mask_shape = mask.shape
        else:
            mask = None

        for index in range(start, stop, step):
            if use_all:
                file_index, pos = self.pos_map_all[index]
            else:
                file_index, pos = self.pos_map[index]
            if file_index != current_file:
                current_file = file_index
                self.calibration_model.img_model.load(self.files[file_index])

            self.calibration_model.img_model.load_series_img(pos+1)
            binning, intensity = self.calibration_model.integrate_1d(num_points=num_points,
                                                                     mask=mask)
            image_counter += 1
            pos_map.append((file_index, pos))
            intensity_data.append(intensity)
            binning_data.append(binning)

            if callback_fn is not None:
                if not callback_fn(image_counter):
                    break

        # deal with different x lengths due to trimmed zeros:
        binning_lengths = [len(binning) for binning in binning_data]
        binning_max_length_ind = np.argmax(binning_lengths)
        binning_max_length = binning_lengths[binning_max_length_ind]
        binning = binning_data[binning_max_length_ind]

        for ind in range(len(intensity_data)):
            intensity_data[ind] = np.append(intensity_data[ind],
                                            np.zeros((binning_max_length - binning_lengths[ind], 1)))

        # finish and save everything

        if self.calibration_model.filename != '':
            self.used_calibration = self.calibration_model.filename
        self.pos_map = np.array(pos_map)
        self.binning = np.array(binning)
        self.data = np.array(intensity_data)
        self.bkg = None
        self.n_img = self.data.shape[0]

    def extract_background(self, parameters, callback_fn=None):
        """
        Subtract background calculated with respect of given parameters
        """

        bkg = np.zeros(self.data.shape)
        for i, y in enumerate(self.data):

            if callback_fn is not None:
                if not callback_fn(i):
                    break
            bkg[i] = extract_background(self.binning, y, *parameters)
        self.bkg = bkg

    def normalize(self, range_ind=(10, 30)):
        if self.data is None:
            return
        average_intensities = np.mean(self.data[:, range_ind[0]:range_ind[1]], axis=1)
        factors = average_intensities[0] / average_intensities
        self.data = (self.data.T * factors).T

    def get_image_info(self, index, use_all=False):
        """
        Get filename and image position in the file

        :param index: Index of image in the batch
        :param use_all: Indexing with respect to all images. If False count only images, that were integrated.
        """
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

    def load_image(self, index, use_all=False):
        """
        Load image in image model

        :param index: Index of image in the batch
        :param use_all: Indexing with respect to all images. If False count only images, that were integrated.
        """
        if not self.raw_available:
            return
        filename, pos = self.get_image_info(index, use_all)
        self.calibration_model.img_model.load(filename, pos)

    def get_next_folder_filenames(self):
        """
        Loads all files from the next folder with similar file-endings.
        """
        iterator = FileNameIterator(self.files[0])
        files = []
        next_file_path = iterator.get_next_folder()
        if next_file_path is not None:
            next_folder_path = pathlib.Path(next_file_path).parent
            for file in os.listdir(next_folder_path):
                if file.endswith(pathlib.Path(self.files[0]).suffix):
                    files.append(os.path.join(next_folder_path, file))
        return files

    def get_previous_folder_filenames(self):
        """
        Loads all files from the previous folder with similar file-endings.
        """
        iterator = FileNameIterator(self.files[0])
        files = []
        previous_file_path = iterator.get_previous_folder()
        if previous_file_path is not None:
            previous_folder_path = pathlib.Path(previous_file_path).parent
            for file in os.listdir(previous_folder_path):
                if file.endswith(pathlib.Path(self.files[0]).suffix):
                    files.append(os.path.join(previous_folder_path, file))
        return files
