import numpy as np
import matplotlib.pyplot as plt

from utilities import Point


arctan = np.arctan
arccos = np.arccos
arcsin = np.arcsin
cos = np.cos
sin = np.sin
sqrt = np.sqrt
tan = np.tan


def _round_to(_x, step):
    return np.round(_x / np.float32(step)) * step


def distance(point1, point2):
    return sqrt((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2)


def _create_meshgrid(width, height):
    x_pixel = np.linspace(.5, width - .5, width)
    y_pixel = np.linspace(.5, height - .5, height)
    return np.meshgrid(x_pixel, y_pixel)


class ImageCalibration(object):
    def __init__(self, center_in_pixel, tilt_x, tilt_y, detector_distance, pixel_size, method=1):
        #PUBLIC variables:
        self.center_in_pixel = center_in_pixel
        self.tilt_x = tilt_x
        self.tilt_y = tilt_y
        self.detector_distance = detector_distance
        self.pixel_size = pixel_size

        self.bin_size = tan(pixel_size / detector_distance) * 180 / np.pi
        self.bin_size = 2.0842087E-02
        self.two_theta_mesh = []
        self.spectrum_x = []
        self.spectrum_y = []
        self.spectrum_y_norm = []
        self.method = method

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
        img_data = np.array(img_data)[::-1, :]
        img_size_x = np.size(img_data, 0)
        img_size_y = np.size(img_data, 1)
        if self._is_not_calibrated:
            if self._calibrated_img_dimension[0] is not img_size_x or \
                            self._calibrated_img_dimension[1] is not img_size_y:
                self._calibrated_img_dimension = [img_size_x, img_size_y]
                self._calculate_calibration(img_data)
                self._is_not_calibrated = False
        else:
            self.spectrum_y = self._calculate_spectrum(img_data)
        return self.spectrum_x, self.spectrum_y

    def get_two_theta(self, x_pixel, y_pixel):
        return self.two_theta_mesh[x_pixel - 1, y_pixel - 1]

    def _calculate_calibration(self, img_data):
        [self._X, self._Y] = _create_meshgrid(self._calibrated_img_dimension[0],
                                              self._calibrated_img_dimension[1])
        self.two_theta_mesh = self._calculate_two_theta(self._X, self._Y)
        self.spectrum_y = self._calculate_spectrum(img_data)
        self.spectrum_x = np.arange(0, len(self.spectrum_y)) * self.bin_size
        self.spectrum_y = self.spectrum_y / (1 + cos(self.spectrum_x / 180. * np.pi) ** 2) * 2


    def _calculate_two_theta(self, x_pixel, y_pixel):
        d = self.detector_distance
        if self.method == 1:
            #conduct the calculation
            #following fit2d paper:

            #create appropriate parameters
            x_distance = (x_pixel - self.center_in_pixel.x) * self.pixel_size
            y_distance = (y_pixel - self.center_in_pixel.y) * self.pixel_size
            phi = self.tilt_y / 180. * np.pi
            beta = self.tilt_x / 180. * np.pi
            first_term = cos(phi) ** 2 * (cos(beta) * x_distance + sin(beta) * y_distance) ** 2
            second_term = (-sin(beta) * x_distance + cos(beta) * y_distance) ** 2
            third_term = (d + sin(phi) * (cos(beta) * x_distance + sin(beta) * y_distance)) ** 2

            two_theta = arctan(sqrt((first_term + second_term) / third_term)) * 180 / np.pi

        elif self.method == 2:
            #follwoing the Bob B. He:
            x_distance = (x_pixel - 1024) * self.pixel_size
            y_distance = (y_pixel - 1024) * self.pixel_size
            alpha = arcsin(distance(Point(1024, 1024), self.center_in_pixel) * self.pixel_size / d)
            two_theta = arccos(
                (x_distance * sin(alpha) + d * cos(alpha)) / np.sqrt(d ** 2 + x_distance ** 2 + y_distance ** 2)) \
                        * 180 / np.pi
        return two_theta

    def _calculate_spectrum(self, img_data):
        two_theta_indexed_1d = self._collapse_two_theta()
        #spatial_factor=
        spectrum_y = np.bincount(two_theta_indexed_1d, np.ravel(img_data))  #img_data*4*
        #sin(self.two_theta_mesh/360*np.pi)**2*cos(self.two_theta_mesh/360*np.pi)))
        spectrum_y_norm = np.double(spectrum_y) / np.bincount(two_theta_indexed_1d)
        return spectrum_y_norm


    def _collapse_two_theta(self):
        two_theta_rounded = _round_to(self.two_theta_mesh.ravel(), self.bin_size)
        two_theta_indexed = two_theta_rounded / self.bin_size
        return np.int64(np.round(two_theta_indexed, decimals=1))


if __name__ == "__main__":
    my_calibration = ImageCalibration(Point(1024, 1024), 14, -0.211, 201.0467e-3, 79e-6)
    img = plt.imread('Data/test_002.tif')

    num_calc = 1
    for i in xrange(num_calc):
        img = plt.imread('Data/test_002.tif')
        x, y = my_calibration.integrate_image(img)

    print my_calibration.get_two_theta(1024, 1024)

    #plt.plot(x, y)
    #plt.show()