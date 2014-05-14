__author__ = 'Clemens Prescher'

from pyFAI.peakPicker import Massif
from pyFAI.calibration import Calibration
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.calibrant import Calibrant
from Data.HelperModule import get_base_name
import numpy as np
import pyqtgraph as pg


class CalibrationData(object):
    def __init__(self, img_data=None):
        self.img_data = img_data
        self.points = []
        self.points_index = []
        self.geometry = AzimuthalIntegrator()
        self.calibrant = Calibrant()
        self.start_values = {'dist': 400e-3,
                             'wavelength': 0.4133e-10,
                             'pixel_width': 200e-6,
                             'pixel_height': 200e-6}
        self.fit_wavelength = False
        self.is_calibrated = False
        self.use_mask = False
        self.calibration_name = 'None'
        self._calibrants_working_dir = 'ExampleData/Calibrants'

    def find_peaks_automatic(self, x, y, peak_ind):
        massif = Massif(self.img_data.img_data)
        cur_peak_points = massif.find_peaks([x, y])
        if len(cur_peak_points):
            self.points.append(np.array(cur_peak_points))
            self.points_index.append(peak_ind)
        return np.array(cur_peak_points)

    def find_peak(self, x, y, search_size, peak_ind):
        left_ind = np.round(x - search_size * 0.5)
        top_ind = np.round(y - search_size * 0.5)
        x_ind, y_ind = np.where(self.img_data.img_data[left_ind:(left_ind + search_size),
                                top_ind:(top_ind + search_size)] == \
                                self.img_data.img_data[left_ind:(left_ind + search_size),
                                top_ind:(top_ind + search_size)].max())
        x_ind = x_ind[0] + left_ind
        y_ind = y_ind[0] + top_ind
        self.points.append(np.array([x_ind, y_ind]))
        self.points_index.append(peak_ind)
        return np.array([np.array((x_ind, y_ind))])

    def clear_peaks(self):
        self.points = []
        self.points_index = []

    def set_calibrant(self, filename):
        self.calibrant = Calibrant()
        self.calibrant.load_file(filename)

    def set_start_values(self, start_values):
        self.start_values = start_values

    def refine_geometry(self):
        self.geometry = GeometryRefinement(self.create_point_array(self.points, self.points_index),
                                           dist=self.start_values['dist'],
                                           wavelength=self.start_values['wavelength'],
                                           pixel1=self.start_values['pixel_width'],
                                           pixel2=self.start_values['pixel_height'],
                                           calibrant=self.calibrant)
        self.geometry.refine2()
        if self.fit_wavelength:
            self.geometry.refine2_wavelength(fix=[])
        self.integrate_1d()
        self.integrate_2d()
        self.is_calibrated = True
        self.calibration_name = 'current'

    def integrate_1d(self, num_points=1400, mask=None, polarization_factor=None, filename=None, unit='2th_deg'):
        self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, num_points, method='lut', unit=unit,
                                                       mask=mask, polarization_factor=polarization_factor,
                                                       filename=filename)
        return self.tth, self.int

    def integrate_2d(self, mask=None):
        img = self.geometry.integrate2d(self.img_data.img_data, 2048, 2048, method='lut', mask=None)
        self.cake_img = img[0]
        return self.cake_img

    def create_point_array(self, points, points_ind):
        res = []
        for i, point_list in enumerate(points):
            if len(point_list) == 2:
                res.append([point_list[0], point_list[1], points_ind[i]])
            else:
                for point in point_list:
                    res.append([point[0], point[1], points_ind[i]])
        return np.array(res)

    def get_calibration_parameter(self):
        pyFAI_parameter = self.geometry.getPyFAI()
        try:
            fit2d_parameter = self.geometry.getFit2D()
        except TypeError:
            fit2d_parameter = None
        try:
            pyFAI_parameter['wavelength'] = self.geometry.wavelength
            fit2d_parameter['wavelength'] = self.geometry.wavelength
        except RuntimeWarning:
            pyFAI_parameter['wavelength'] = 0
        return pyFAI_parameter, fit2d_parameter

    def load(self, filename):
        self.geometry.load(filename)
        self.calibration_name = get_base_name(filename)
        self.is_calibrated = True

    def save(self, filename):
        self.geometry.save(filename)
        self.calibration_name = get_base_name(filename)