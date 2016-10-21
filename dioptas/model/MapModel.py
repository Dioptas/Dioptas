import os
import numpy as np


class MapModel(object):
    """
    Model for 2D maps from loading multiple images

    """

    def __init__(self):
        """
        Defines all object variables and creates a dummy image.
        :return:
        """
        super(MapModel, self).__init__()

        self.map_data = {}
        self.map_roi = {}
        self.theta_center = 5.9
        self.theta_range = 0.1
        self.num_hor = 0
        self.num_ver = 0
        self.roi_num = 0
        self.pix_per_hor = 100
        self.pix_per_ver = 100
        self.map_loaded = False
        self.units = '2th_deg'
        self.wavelength = 0.3344
        self.all_positions_exist = True

        # Background for image
        self.bg_image = np.zeros([1920, 1200])

    def reset_map_data(self):
        self.map_data = {}
        self.all_positions_exist = True

    def add_map_data(self, filename, working_directory, motors_info):
        base_filename = os.path.basename(filename)
        self.map_data[filename] = {}
        self.map_data[filename]['image_file_name'] = filename.replace('\\', '/')
        self.map_data[filename]['spectrum_file_name'] = working_directory + '/' + \
                                                        os.path.splitext(base_filename)[0] + '.xy'
        try:
            self.map_data[filename]['pos_hor'] = str(round(float(motors_info['Horizontal']), 3))
            self.map_data[filename]['pos_ver'] = str(round(float(motors_info['Vertical']), 3))
        except KeyError:
            self.all_positions_exist = False

