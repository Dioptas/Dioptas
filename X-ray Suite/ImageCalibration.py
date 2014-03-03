import numpy as np
import matplotlib.pyplot as plt
from utilities import Point


arctan = np.arctan
cos = np.cos
sin = np.sin
sqrt = np.sqrt


def _round(_x, step):
    return np.round(_x / step) * step


def create_meshgrid(width, height):
    x_pixel = np.linspace(1, width, width)
    y_pixel = np.linspace(1, height, height)
    return np.meshgrid(x_pixel, y_pixel)


class ImageCalibration(object):
    def __init__(self, center_in_pixel, tilt_x, tilt_y, detector_distance, pixel_size):
        #PUBLIC variables:
        self.center_in_pixel = center_in_pixel
        self.tilt_x = tilt_x
        self.tilt_y = tilt_y
        self.detector_distance = detector_distance
        self.pixel_size = pixel_size

        self.bin_size = np.tan(pixel_size / self.detector_distance) * 180 / np.pi
        self.two_theta_mesh = []
        self.spectrum_x = []
        self.spectrum_y = []
        self.spectrum_y_norm = []

        #PRIVATE variables:
        self._X = []
        self._Y = []
        self._two_theta_rounded = []
        self._two_theta_indexed = []
        self._bin_vector = []
        self._two_theta_indexed_1d = []

        self._is_not_calibrated = True
        self._calibrated_img_dimension = [0, 0]

    def integrate_image(self, img_data):
        img_size_x = np.size(img_data, 0)
        img_size_y = np.size(img_data, 1)
        if self._is_not_calibrated:
            if self._calibrated_img_dimension[0] is not img_size_x or self._calibrated_img_dimension[
                1] is not img_size_y:
                self._calculate_calibration()
                self._is_not_calibrated = False
                self._calibrated_img_dimension = [img_size_x, img_size_y]
        else:
            self.spectrum_y = self._calculate_spectrum(img_data)
        return self.spectrum_x, self.spectrum_y

    def _calculate_calibration(self):
        [self._X, self._Y] = create_meshgrid(img_size_x, img_size_y)
        self.two_theta_mesh = self.calculate_two_theta(self._X, self._Y)
        self._two_theta_indexed_1d = self._collapse_two_theta()
        self.spectrum_y = self._calculate_spectrum(img_data)
        self.spectrum_x = np.arange(0, len(self.spectrum_y)) * self.bin_size

    def calculate_two_theta(self, x_pixel, y_pixel):
        #create appropriate parameters
        x_distance = (x_pixel - self.center_in_pixel.x) * self.pixel_size
        y_distance = (y_pixel - self.center_in_pixel.y) * self.pixel_size
        phi = self.tilt_y / 180. * np.pi
        beta = self.tilt_x / 180. * np.pi
        d = self.detector_distance

        #conduct the calculation
        first_term = cos(phi) ** 2 * (cos(beta) * x_distance + sin(beta) * y_distance) ** 2
        second_term = (-sin(beta) * x_distance + cos(beta) * y_distance) ** 2
        third_term = (d + sin(phi) * (cos(beta) * x_distance + sin(beta) * y_distance)) ** 2

        two_theta = sqrt(arctan((first_term + second_term) / third_term)) * 180 / np.pi
        return two_theta

    def _collapse_two_theta(self):
        two_theta_rounded = _round(self.two_theta_mesh, self.bin_size)
        two_theta_indexed = two_theta_rounded / self.bin_size
        return np.int64(np.round(two_theta_indexed.ravel()))

    def _calculate_spectrum(self, img_data):
        spectrum_y = np.bincount(self._two_theta_indexed_1d, np.ravel(img_data))
        spectrum_y_norm = spectrum_y / np.bincount(self._two_theta_indexed_1d)
        return spectrum_y_norm


if __name__ == "__main__":
    my_calibration = ImageCalibration(Point(1024, 1024), 14, -0.211, 201.0467e-3, 79e-6)
    img = plt.imread('Data\test_002.tif')

    num_calc = 1
    for i in xrange(num_calc):
        img = plt.imread('Data\test_002.tif')
        x, y = my_calibration.integrate_image(img)

    plt.plot(x, y)
    plt.show()