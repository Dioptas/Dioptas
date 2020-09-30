import logging
import os
from past.builtins import basestring
import copy

import h5py
import numpy as np

from PIL import Image
from qtpy import QtCore

from . import ImgModel, CalibrationModel, MaskModel

logger = logging.getLogger(__name__)


class ScanModel(QtCore.QObject):

    def __init__(self, calibration_model, mask_model):
        super(ScanModel, self).__init__()

        self.data = None
        self.binning = None

        self.file_map = []
        self.files = []
        self.pos_map = None

        self.calibration_model = calibration_model
        self.mask_model = mask_model
        self.raw_data_path = ''

    def set_image_files(self, files):
        self.files = files

    def set_raw_data_path(self, raw_data_path):
        self.raw_data_path = raw_data_path

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

            cal_file = data_file.attrs['calibration']
            print(cal_file, str(cal_file))
            self.calibration_model.load(cal_file)
            #mask_file = data_file.attrs['mask']
            #self.mask_model.load_mask(mask_file)

    def save_proc_data(self, filename):

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with h5py.File(filename, mode="w") as f:

            f.attrs['calibration'] = self.calibration_model.filename
            f.attrs['int_method'] = 'Bla'
            f.attrs['num_points'] = len(self.binning)

            f.create_dataset("data", data=self.data)
            f.create_dataset("binning", data=self.binning)
            f.create_dataset("pos_map", data=self.pos_map)
            f.create_dataset("file_map", data=np.array(self.file_map))
            f.create_dataset("files", data=np.array(self.files).astype('S'))


    def integrate_raw_data(self):
        """
        Integrate images from given file

        """
        data = []
        pos_map = []
        for file in self.files:
            self.calibration_model.img_model.load(file)
            self.file_map.append(len(data))

            for i in range(self.calibration_model.img_model.series_max):
                self.calibration_model.img_model.load_series_img(i)
                print(i)

                binning, intensity = self.calibration_model.integrate_1d(num_points=1500,
                                                                         mask=None)#self.mask_model.get_mask())
                pos_map.append(i)
                data.append(intensity)

        self.pos_map = np.array(pos_map)
        self.binning = binning
        self.data = np.array(data)

        print(self.data.shape, self.file_map)

    def save_scan(self, filename):
        """
        Save diffraction patterns to h5 file
        """
        pass

    def get_image_info(self, index):

        f_index = np.where(np.array(self.file_map) <= index)[0][-1]
        filename = self.files[f_index]
        pos = self.pos_map[index]
        return filename, pos

    def load_image(self, index):
        """
        Load image base on index of the image in the scan
        """
        filename, pos = self.get_image_info(index)
        self.calibration_model.img_model.load(filename)
        self.calibration_model.img_model.load_series_img(pos)



