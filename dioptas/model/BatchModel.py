import logging
import os

import h5py
import numpy as np
from qtpy import QtCore

from .util import extract_background

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
        self.used_calibration = None
        self.raw_available = False

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
        self.raw_available = True
        self.pos_map_all = np.array(pos_map)
        self.file_map = np.array(file_map)

    def load_proc_data(self, filename):
        """
        Load diffraction patterns and metadata from h5 file

        """
        with h5py.File(filename, "r") as data_file:
            self.data = data_file['processed/result/data'][()]
            self.binning = data_file['processed/result/binning'][()]
            self.file_map = data_file['processed/process/file_map'][()]
            self.files = data_file['processed/process/files'][()].astype('U')
            self.pos_map = data_file['processed/process/pos_map'][()]
            self.n_img = self.data.shape[0]
            self.n_img_all = self.data.shape[0]

            self.used_calibration = str(data_file['processed/process/cal_file'][()])
            try:
                self.calibration_model.load(self.used_calibration)
            except:
                pass

            if 'mask' in data_file['processed/process/']:
                mask = data_file['processed/process/mask'][()]
                self.mask_model.set_dimension(mask.shape)
                self.mask_model.set_mask(mask)

            if 'mask_file' in data_file['processed/process/']:
                self.used_mask = str(data_file['processed/process/mask_file'][()])
                self.mask_model.set_dimension(tuple(data_file['processed/process/mask_shape'][()]))
                self.mask_model.load_mask(self.used_mask)

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

            nxprocess['cal_file'] = str(self.used_calibration)
            nxprocess['int_method'] = 'csr'
            nxprocess['int_unit'] = '2th_deg'
            nxprocess['num_points'] = self.binning.shape[0]

            if self.used_mask is not None:
                nxprocess.create_dataset("mask", data=self.used_mask)

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

    def integrate_raw_data(self, num_points, start, stop, step, use_all=False, progress_dialog=None):
        """
        Integrate images from given file

        :param progress_dialog: Progress dialog to show progress
        :param num_points: Numbers of radial bins
        :param start: Start image index fro integration
        :param stop: Stop image index fro integration
        :param step: Step along images to integrate
        :param use_all: Use all images. If False use only images, that were already integrated.
        """
        data = []
        pos_map = []
        image_counter = 0
        current_file = ''
        if self.mask_model.mode:
            self.used_mask = self.mask_model.get_mask()
        else:
            self.used_mask = None

        for index in range(start, stop, step):
            if use_all:
                i_file, pos = self.pos_map_all[index]
            else:
                i_file, pos = self.pos_map[index]
            if i_file != current_file:
                current_file = i_file
                self.calibration_model.img_model.load(self.files[i_file])

            if progress_dialog is not None and progress_dialog.wasCanceled():
                break

            self.calibration_model.img_model.load_series_img(pos)
            binning, intensity = self.calibration_model.integrate_1d(num_points=num_points,
                                                                     mask=self.used_mask)
            image_counter += 1
            if progress_dialog is not None:
                progress_dialog.setValue(image_counter)

            pos_map.append((i_file, pos))
            data.append(intensity)

        self.used_calibration = self.calibration_model.filename
        self.pos_map = np.array(pos_map)
        self.binning = np.array(binning)
        self.data = np.array(data)
        self.n_img = self.data.shape[0]

    def extract_background(self, parameters, progress_dialog=None):
        """
        Subtract background calculated with respect of given parameters
        """

        bkg = np.zeros(self.data.shape)
        for i, y in enumerate(self.data):

            if progress_dialog is not None:
                if progress_dialog.wasCanceled():
                    break
                progress_dialog.setValue(i)

            bkg[i] = extract_background(self.binning, y, *parameters)
        self.bkg = bkg

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
