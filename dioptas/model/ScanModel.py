import logging
import os

import h5py
import numpy as np
from qtpy import QtCore

from .util import extract_background

logger = logging.getLogger(__name__)


class ScanModel(QtCore.QObject):
    """
    Class describe a model for batch integration
    """

    def __init__(self, calibration_model, mask_model):
        super(ScanModel, self).__init__()

        self.data = None
        self.bkg = None
        self.binning = None
        self.file_map = None
        self.files = None
        self.pos_map = None
        self.n_img = None
        self.n_img_all = None

        self.calibration_model = calibration_model
        self.mask_model = mask_model

    def reset_data(self):
        self.data = None
        self.bkg = None
        self.binning = None
        self.file_map = None
        self.files = None
        self.pos_map = None
        self.n_img = None
        self.n_img_all = None

    def set_image_files(self, files):
        """
        Set internal variables with respect of given list of files.

        Open each file and count number of images inside. Position of each image in the file
        and total number of images are stored in internal variables.

        :param files: List of file names including path
        """
        pos_map = []
        file_map = [0]
        image_counter = 0
        for i, file in enumerate(files):
            self.calibration_model.img_model.load(file)
            n_img = self.calibration_model.img_model.series_max
            image_counter += n_img
            pos_map += list(zip([i] * n_img, range(n_img)))
            file_map.append(image_counter)

        self.files = np.array(files)
        self.n_img_all = image_counter
        if self.pos_map is None:
            self.pos_map = np.array(pos_map)
            self.file_map = np.array(file_map)

    def load_proc_data(self, filename):
        """
        Load diffraction patterns and metadata from h5 file

        """
        with h5py.File(filename, "r") as data_file:
            self.data = data_file['data'][()]
            self.binning = data_file['binning'][()]
            self.file_map = data_file['file_map'][()]
            self.files = data_file['files'][()].astype('U')
            self.pos_map = data_file['pos_map'][()]
            self.n_img = self.data.shape[0]

            cal_file = str(data_file.attrs['calibration'])
            self.calibration_model.load(cal_file)

            if 'mask' in data_file.attrs:
                mask_file = data_file.attrs['mask']
                self.mask_model.load_mask(mask_file)

            if 'bkg' in data_file:
                self.bkg = data_file['bkg'][()]

    def save_proc_data(self, filename):
        """
        Save diffraction patterns to h5 file
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with h5py.File(filename, mode="w") as f:
            f.attrs['calibration'] = self.calibration_model.filename
            f.attrs['int_method'] = 'Bla'  # ToDO
            f.attrs['num_points'] = self.binning.shape[0]
            f.attrs['data_type'] = 'processed'
            if self.mask_model.filename:
                f.attrs['mask'] = self.calibration_model.filename

            if self.bkg is not None:
                f.create_dataset("bkg", data=self.bkg)

            f.create_dataset("data", data=self.data)
            f.create_dataset("binning", data=self.binning)
            f.create_dataset("pos_map", data=self.pos_map)
            f.create_dataset("file_map", data=self.file_map)
            f.create_dataset("files", data=self.files.astype('S'))

    def save_as_csv(self, filename):
        """
        Save diffraction patterns to 3-columns csv file
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        x = self.binning.repeat(self.n_img)
        y = np.arange(self.n_img)[None,:].repeat(self.binning.shape[0], axis=0).flatten()
        np.savetxt(filename, np.array(list(zip(x, y, self.data.T.flatten()))), delimiter=',', fmt='%f')

    def integrate_raw_data(self, progress_dialog, num_points, start, stop, step):
        """
        Integrate images from given file

        :param progress_dialog: Progress dialog to show progress
        :param num_points: Numbers of radial bins
        :param start: Start image index fro integration
        :param stop: Stop image index fro integration
        :param step: Step along images to integrate
        """
        data = []
        pos_map = []
        image_counter = 0
        current_file = ''
        if self.mask_model.mode:
            mask = self.mask_model.get_mask()

        for index in range(start, stop, step):
            i_file, pos = self.pos_map[index]
            if i_file != current_file:
                current_file = i_file
                self.calibration_model.img_model.load(self.files[i_file])
            if progress_dialog.wasCanceled():
                break

            self.calibration_model.img_model.load_series_img(pos)
            binning, intensity = self.calibration_model.integrate_1d(num_points=num_points,
                                                                     mask=mask)
            image_counter += 1
            progress_dialog.setValue(image_counter)

            pos_map.append((i_file, pos))
            data.append(intensity)

        self.pos_map = np.array(pos_map)
        self.binning = np.array(binning)
        self.data = np.array(data)
        self.n_img = self.data.shape[0]

    def extract_background(self, parameters, progress_dialog):
        """
        Subtract background calculated with respect of given parameters
        """

        bkg = np.zeros(self.data.shape)
        for i, y in enumerate(self.data):
            if progress_dialog.wasCanceled():
                break

            progress_dialog.setValue(i)
            bkg[i] = extract_background(self.binning, y, *parameters)
        self.bkg = bkg

    def get_image_info(self, index):
        """
        Get filename and image position in the file

        :param index: Index of image in the batch
        """
        f_index, pos = self.pos_map[index]
        filename = self.files[f_index]
        return filename, pos

    def load_image(self, index):
        """
        Load image in image model

        :param index: Index of image in the batch
        """
        filename, pos = self.get_image_info(index)
        self.calibration_model.img_model.load(filename, pos)
