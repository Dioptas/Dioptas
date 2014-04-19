__author__ = 'Clemens Prescher'

from pyFAI.peakPicker import Massif
from pyFAI.calibration import Calibration
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.calibrant import Calibrant
import numpy as np
import pyqtgraph as pg


class XrsCalibrationData(object):
    def __init__(self, img_data):
        self.img_data=img_data
        self.points = []
        self.points_index = []
        self.geometry = AzimuthalIntegrator()
        self.calibrant = Calibrant()
        self.start_values =     {'dist':        400e-3,
                                'wavelength':  0.4133e-10,
                                'pixel_width':  200e-6,
                                'pixel_height': 200e-6}

    def find_peaks(self, x,y, peak_ind):
        massif = Massif(self.img_data.img_data)
        cur_peak_points = massif.find_peaks([x,y])
        if len(cur_peak_points):
            self.points.append(np.array(cur_peak_points))
            self.points_index.append(peak_ind)
        return np.array(cur_peak_points)

    def clear_peaks(self):
        self.points=[]

    def set_calibrant(self, filename):
        self.calibrant=Calibrant()
        self.calibrant.load_file(filename)

    def set_start_values(self, start_values):
        self.start_values=start_values

    def refine_geometry(self):
        self.geometry=GeometryRefinement(self.create_point_array(self.points, self.points_index),
                                         dist=self.start_values['dist'],
                                         wavelength=self.start_values['wavelength'],
                                         pixel1 = self.start_values['pixel_width'],
                                         pixel2 = self.start_values['pixel_height'],
                                         calibrant=self.calibrant)
        self.geometry.refine2()
        self.integrate_1d()
        self.integrate_2d()

    def integrate_1d(self):
        self.tth, self.int = self.geometry.integrate1d(self.img_data.img_data, 1400, method='LUT', unit='2th_deg')

    def integrate_2d(self):
        img = self.geometry.integrate2d(self.img_data.img_data, 1000, 1000, method='LUT')
        self.cake_img=img[0]

    def create_point_array(self, points, points_ind):
        res = []
        for i, point_list in enumerate(points):
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

