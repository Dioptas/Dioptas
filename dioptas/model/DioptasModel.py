# -*- coding: utf8 -*-
import os

from scipy.interpolate import interp1d, interp2d
import numpy as np
from qtpy import QtCore
from copy import deepcopy

from .util import Pattern
from .util.calc import convert_units
from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel


class ImgConfiguration(QtCore.QObject):
    cake_changed = QtCore.Signal()

    def __init__(self, working_directories):
        super(ImgConfiguration, self).__init__()

        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.pattern_model = PatternModel()

        if working_directories is not None:
            self.working_directories = working_directories
        else:
            self.working_directories = {}

        self.use_mask = False

        self.transparent_mask = False

        self._integration_num_points = None
        self._integration_azimuth_points = 2048
        self._integration_unit = '2th_deg'

        self._integrate_cake = False

        self.autosave_integrated_pattern = False
        self.integrated_patterns_file_formats = ['.xy']

        self.connect_signals()

    def connect_signals(self):
        self.img_model.img_changed.connect(self.update_mask_dimension)
        self.img_model.img_changed.connect(self.integrate_image_1d)

    def integrate_image_1d(self):
        if self.calibration_model.is_calibrated:
            if self.use_mask:
                if self.mask_model.supersampling_factor != self.img_model.supersampling_factor:
                    self.mask_model.set_supersampling(self.img_model.supersampling_factor)
                mask = self.mask_model.get_mask()
            elif self.mask_model.roi is not None:
                mask = self.mask_model.roi_mask
            else:
                mask = None

            x, y = self.calibration_model.integrate_1d(mask=mask, unit=self.integration_unit,
                                                       num_points=self.integration_num_points)

            self.pattern_model.set_pattern(x, y, self.img_model.filename, unit=self.integration_unit)  #

            if self.autosave_integrated_pattern:
                self._auto_save_patterns()

    def integrate_image_2d(self):
        if self.use_mask:
            if self.mask_model.supersampling_factor != self.img_model.supersampling_factor:
                self.mask_model.set_supersampling(self.img_model.supersampling_factor)
            mask = self.mask_model.get_mask()
        elif self.mask_model.roi is not None:
            mask = self.mask_model.roi_mask
        else:
            mask = None

        self.calibration_model.integrate_2d(mask=mask,
                                            dimensions=(2048, 2048))
        self.cake_changed.emit()

    def save_pattern(self, filename=None, subtract_background=False):
        if filename is None:
            filename = self.img_model.filename

        if filename.endswith('.xy'):
            self.pattern_model.save_pattern(filename, header=self._create_xy_header(),
                                            subtract_background=subtract_background)
        elif filename.endswith('.fxye'):
            self.pattern_model.save_pattern(filename, header=self._create_fxye_header(filename),
                                            subtract_background=subtract_background)
        else:
            self.pattern_model.save_pattern(filename, subtract_background=subtract_background)


    def _create_xy_header(self):
        header = self.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header = header + '\n#\n# ' + self._integration_unit + '\t I'
        return header

    def _create_fxye_header(self, filename):
        header = 'Generated file ' + filename + ' using DIOPTAS\n'
        header = header + self.calibration_model.create_file_header()
        unit = self._integration_unit
        lam = self.calibration_model.wavelength
        if unit == 'q_A^-1':
            con = 'CONQ'
        else:
            con = 'CONS'

        header = header + '\nBANK\t1\tNUM_POINTS\tNUM_POINTS ' + con + '\tMIN_X_VAL\tSTEP_X_VAL ' + \
                 '{0:.5g}'.format(lam * 1e10) + ' 0.0 FXYE'
        return header

    def _auto_save_patterns(self):
        for file_ending in self.integrated_patterns_file_formats:
            filename = os.path.join(
                    self.working_directories['pattern'],
                    os.path.basename(str(self.img_model.filename)).split('.')[:-1][0] + file_ending)
            filename = filename.replace('\\', '/')
            self.save_pattern(filename)

        if self.pattern_model.pattern.has_background():
            for file_ending in self.integrated_patterns_file_formats:
                directory = os.path.join(self.working_directories['pattern'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.pattern_model.pattern.name + file_ending)
                filename = filename.replace('\\', '/')
                self.save_pattern(filename, subtract_background=True)

    def update_mask_dimension(self):
        self.mask_model.set_dimension(self.img_model._img_data.shape)

    @property
    def integration_num_points(self):
        return self._integration_num_points

    @integration_num_points.setter
    def integration_num_points(self, new_value):
        self._integration_num_points = new_value
        self.integrate_image_1d()

    @property
    def integration_unit(self):
        return self._integration_unit

    @integration_unit.setter
    def integration_unit(self, new_unit):
        old_unit = self.integration_unit
        self._integration_unit = new_unit

        auto_bg_subtraction = self.pattern_model.pattern.auto_background_subtraction
        if auto_bg_subtraction:
            self.pattern_model.pattern.auto_background_subtraction = False

        self.integrate_image_1d()

        self.update_auto_background_parameters_unit(old_unit, new_unit)

        if auto_bg_subtraction:
            self.pattern_model.pattern.auto_background_subtraction = True
            self.pattern_model.pattern.recalculate_pattern()
            self.pattern_model.pattern_changed.emit()

    def update_auto_background_parameters_unit(self, old_unit, new_unit):
        self.pattern_model.pattern.auto_background_subtraction_parameters = \
            convert_units(self.pattern_model.pattern.auto_background_subtraction_parameters[0],
                          self.calibration_model.wavelength,
                          old_unit,
                          new_unit), \
            self.pattern_model.pattern.auto_background_subtraction_parameters[1], \
            self.pattern_model.pattern.auto_background_subtraction_parameters[2]

        if self.pattern_model.pattern.auto_background_subtraction_roi is not None:
            self.pattern_model.pattern.auto_background_subtraction_roi = \
                convert_units(self.pattern_model.pattern.auto_background_subtraction_roi[0],
                              self.calibration_model.wavelength,
                              old_unit,
                              new_unit), \
                convert_units(self.pattern_model.pattern.auto_background_subtraction_roi[1],
                              self.calibration_model.wavelength,
                              old_unit,
                              new_unit)

    @property
    def integrate_cake(self):
        return self._integrate_cake

    @integrate_cake.setter
    def integrate_cake(self, new_value):
        self._integrate_cake = new_value
        if new_value:
            self.img_model.img_changed.connect(self.integrate_image_2d)
        else:
            self.img_model.img_changed.disconnect(self.integrate_image_2d)

    @property
    def cake_img(self):
        return self.calibration_model.cake_img

    @property
    def roi(self):
        return self.mask_model.roi

    @roi.setter
    def roi(self, new_val):
        self.mask_model.roi = new_val
        self.integrate_image_1d()

    def copy(self):
        new_configuration = ImgConfiguration(self.working_directories)
        new_configuration.img_model._img_data = self.img_model._img_data
        new_configuration.img_model.img_transformations = deepcopy(self.img_model.img_transformations)

        new_configuration.calibration_model.set_pyFAI(self.calibration_model.get_calibration_parameter()[0])
        new_configuration.integrate_image_1d()

        return new_configuration


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.Signal()
    configuration_selected = QtCore.Signal(int)  # new index
    configuration_removed = QtCore.Signal(int)  # removed index

    img_changed = QtCore.Signal()
    pattern_changed = QtCore.Signal()
    cake_changed = QtCore.Signal()

    def __init__(self, working_directories=None):
        super(DioptasModel, self).__init__()
        self.working_directories = working_directories
        self.configurations = []
        self.configuration_ind = 0
        self.configurations.append(ImgConfiguration(self.working_directories))

        self._overlay_model = OverlayModel()
        self._phase_model = PhaseModel()

        self._combine_patterns = False
        self._combine_cakes = False
        self._cake_data = None

        self.connect_models()

    def add_configuration(self):
        self.configurations.append(ImgConfiguration(self.working_directories))

        if self.current_configuration.calibration_model.is_calibrated:
            dioptas_config_folder = os.path.join(os.path.expanduser("~"), '.Dioptas')
            if not os.path.isdir(dioptas_config_folder):
                os.mkdir(dioptas_config_folder)
            self.current_configuration.calibration_model.save(
                os.path.join(dioptas_config_folder, 'transfer.poni'))
            self.configurations[-1].calibration_model.load(
                os.path.join(dioptas_config_folder, 'transfer.poni'))

        self.configurations[-1].img_model._img_data = self.current_configuration.img_model.img_data

        self.select_configuration(len(self.configurations) - 1)
        self.configuration_added.emit()

    def remove_configuration(self):
        ind = self.configuration_ind
        self.disconnect_models()
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            self.configuration_ind = len(self.configurations) - 1
        self.connect_models()
        self.configuration_removed.emit(self.configuration_ind)

    def select_configuration(self, ind):
        if 0 <= ind < len(self.configurations):
            self.disconnect_models()
            self.configuration_ind = ind
            self.connect_models()
            self.configuration_selected.emit(ind)
            self.img_model.img_changed.disconnect(self.current_configuration.integrate_image_1d)
            if self.combine_cakes:
                self.img_model.img_changed.disconnect(self.current_configuration.integrate_image_2d)
            self.img_changed.emit()
            self.img_model.img_changed.connect(self.current_configuration.integrate_image_1d)
            if self.combine_cakes:
                self.img_model.img_changed.connect(self.current_configuration.integrate_image_2d)
            self.pattern_changed.emit()
            self.cake_changed.emit()

    def disconnect_models(self):
        self.img_model.img_changed.disconnect(self.img_changed)
        self.pattern_model.pattern_changed.disconnect(self.pattern_changed)
        self.current_configuration.cake_changed.disconnect(self.cake_changed)

    def connect_models(self):
        self.img_model.img_changed.connect(self.img_changed)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)
        self.current_configuration.cake_changed.connect(self.cake_changed)

    @property
    def current_configuration(self):
        """
        :rtype: ImgConfiguration
        """
        return self.configurations[self.configuration_ind]

    @property
    def img_model(self):
        """
        :rtype: ImgModel
        """
        return self.configurations[self.configuration_ind].img_model

    @property
    def mask_model(self):
        """
        :rtype: MaskModel
        """
        return self.configurations[self.configuration_ind].mask_model

    @property
    def calibration_model(self):
        """
        :rtype: CalibrationModel
        """
        return self.configurations[self.configuration_ind].calibration_model

    @property
    def pattern_model(self):
        """
        :rtype: PatternModel
        """
        return self.configurations[self.configuration_ind].pattern_model

    @property
    def overlay_model(self):
        """
        :rtype: OverlayModel
        """
        return self._overlay_model

    @property
    def phase_model(self):
        """
        :rtype: PhaseModel
        """
        return self._phase_model

    @property
    def use_mask(self):
        return self.configurations[self.configuration_ind].use_mask

    @use_mask.setter
    def use_mask(self, new_val):
        self.configurations[self.configuration_ind].use_mask = new_val

    @property
    def transparent_mask(self):
        return self.configurations[self.configuration_ind].transparent_mask

    @transparent_mask.setter
    def transparent_mask(self, new_val):
        self.configurations[self.configuration_ind].transparent_mask = new_val

    @property
    def integration_unit(self):
        return self.current_configuration.integration_unit

    @integration_unit.setter
    def integration_unit(self, new_val):
        self.current_configuration.integration_unit = new_val

    @property
    def img_data(self):
        return self.img_model.img_data

    @property
    def cake_data(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_img
        else:
            return self._cake_data

    @cake_data.setter
    def cake_data(self, new_cake_data):
        if not self.combine_cakes:
            self.calibration_model.cake_img = new_cake_data
        else:
            self._cake_data = new_cake_data

    def calculate_combined_cake(self):
        self._activate_cake()
        tth = self._get_combined_cake_tth()
        azi = self._get_combined_cake_azi()
        combined_tth, combined_azi = np.meshgrid(tth, azi)
        combined_intensity = np.zeros(combined_azi.shape)
        for configuration in self.configurations:
            cake_interp2d = interp2d(configuration.calibration_model.cake_tth,
                                     configuration.calibration_model.cake_azi,
                                     configuration.calibration_model.cake_img,
                                     fill_value=0)
            combined_intensity += cake_interp2d(tth, azi)
        self._cake_data = combined_intensity

    def _activate_cake(self):
        for configuration in self.configurations:
            if not configuration.integrate_cake:
                configuration.integrate_cake = True
                configuration.integrate_image_2d()

    def _get_cake_tth_range(self):
        self._activate_cake()
        min_tth = []
        max_tth = []
        for ind in range(len(self.configurations)):
            min_tth.append(np.min(self.configurations[ind].calibration_model.cake_tth))
            max_tth.append(np.max(self.configurations[ind].calibration_model.cake_tth))
        return np.min(min_tth), np.max(max_tth)

    def _get_cake_azi_range(self):
        self._activate_cake()
        min_azi = []
        max_azi = []
        for ind in range(len(self.configurations)):
            min_azi.append(np.min(self.configurations[ind].calibration_model.cake_azi))
            max_azi.append(np.max(self.configurations[ind].calibration_model.cake_azi))
        return np.min(min_azi), np.max(max_azi)

    def _get_combined_cake_tth(self):
        min_tth, max_tth = self._get_cake_tth_range()
        return np.linspace(min_tth, max_tth, 2048)

    def _get_combined_cake_azi(self):
        min_azi, max_azi = self._get_cake_azi_range()
        return np.linspace(min_azi, max_azi, 2048)

    @property
    def cake_tth(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_tth
        else:
            return self._get_combined_cake_tth()

    @property
    def cake_azi(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_azi
        else:
            return self._get_combined_cake_azi()

    @property
    def pattern(self):
        if not self.combine_patterns:
            return self.pattern_model.pattern
        else:
            x_min = []
            for ind in range(0, len(self.configurations)):
                # determine ranges
                x = self.configurations[ind].pattern_model.pattern.x
                x_min.append(np.min(x))

            sorted_pattern_ind = np.argsort(x_min)

            pattern = self.configurations[sorted_pattern_ind[0]].pattern_model.pattern
            for ind in sorted_pattern_ind[1:]:
                x1, y1 = pattern.data
                x2, y2 = self.configurations[ind].pattern_model.pattern.data

                pattern2_interp1d = interp1d(x2, y2, kind='linear')

                overlap_ind_pattern1 = np.where((x1 <= np.max(x2)) & (x1 >= np.min(x2)))[0]
                left_ind_pattern1 = np.where((x1 <= np.min(x2)))[0]
                right_ind_pattern2 = np.where((x2 >= np.max(x1)))[0]

                combined_x1 = x1[left_ind_pattern1]
                combined_y1 = y1[left_ind_pattern1]
                combined_x2 = x1[overlap_ind_pattern1]
                combined_y2 = (y1[overlap_ind_pattern1] + pattern2_interp1d(combined_x2)) / 2
                combined_x3 = x2[right_ind_pattern2]
                combined_y3 = y2[right_ind_pattern2]

                combined_x = np.hstack((combined_x1, combined_x2, combined_x3))
                combined_y = np.hstack((combined_y1, combined_y2, combined_y3))

                pattern = Pattern(combined_x, combined_y)

            pattern.name = "Combined Pattern"
            return pattern

    @property
    def combine_patterns(self):
        return self._combine_patterns

    @combine_patterns.setter
    def combine_patterns(self, new_val):
        self._combine_patterns = new_val
        self.pattern_changed.emit()

    @property
    def combine_cakes(self):
        return self._combine_cakes

    @combine_cakes.setter
    def combine_cakes(self, new_val):
        self._combine_cakes = new_val
        if new_val:
            for configuration in self.configurations:
                configuration.cake_changed.connect(self.calculate_combined_cake)
            self.calculate_combined_cake()
        else:
            for configuration in self.configurations:
                configuration.cake_changed.disconnect(self.calculate_combined_cake)
        self.cake_changed.emit()

    def clear(self):
        for configuration in self.configurations:
            del configuration.calibration_model.cake_geometry
            del configuration.calibration_model.pattern_geometry
            del configuration.img_model
            del configuration.mask_model
        del self.configurations

    def _setup_multiple_file_loading(self):
        if self.combine_cakes:
            for configuration in self.configurations:
                configuration.cake_changed.disconnect(self.calculate_combined_cake)

    def _teardown_multiple_file_loading(self):
        if self.combine_cakes:
            for configuration in self.configurations:
                configuration.cake_changed.connect(self.calculate_combined_cake)
            self.calculate_combined_cake()

    def next_image(self, pos=None):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_next_file(pos=pos)
        self._teardown_multiple_file_loading()

    def previous_image(self, pos=None):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_previous_file(pos=pos)
        self._teardown_multiple_file_loading()

    def next_folder(self, mec_mode=False):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_next_folder(mec_mode=mec_mode)
        self._teardown_multiple_file_loading()

    def previous_folder(self, mec_mode=False):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_previous_folder(mec_mode=mec_mode)
        self._teardown_multiple_file_loading()
