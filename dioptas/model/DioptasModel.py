# -*- coding: utf8 -*-
import os

import numpy as np

from PyQt4 import QtCore

from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel


class ImgConfiguration(QtCore.QObject):
    cake_img_changed = QtCore.pyqtSignal()

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
        self.cake_data = None

        self.autosave_integrated_pattern = False
        self.integrated_patterns_file_formats = ['.xy']

        self.connect_signals()

    def connect_signals(self):
        self.img_model.img_changed.connect(self.integrate_image_1d)
        self.img_model.img_changed.connect(self.update_mask_dimension)

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

            # if not self.widget.automatic_binning_cb.isChecked():
            #     num_points = int(str(self.widget.bin_count_txt.text()))
            # else:
            #     num_points = None

            x, y = self.calibration_model.integrate_1d(mask=mask, unit=self.integration_unit,
                                                       num_points=self.integration_num_points)

            self.pattern_model.set_pattern(x, y, self.img_model.filename, unit=self.integration_unit)  #

            if self.autosave_integrated_pattern:
                self.save_pattern()

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
        self.cake_img_changed.emit()

    def save_pattern(self):
        filename = self.img_model.filename
        for file_ending in self.integrated_patterns_file_formats:
            if filename is not '':
                filename = os.path.join(
                    self.working_directories['spectrum'],
                    os.path.basename(str(self.img_model.filename)).split('.')[:-1][0] + file_ending)

            if file_ending == '.xy':
                self.pattern_model.save_pattern(filename, header=self._create_xy_header())
            else:
                self.pattern_model.save_pattern(filename)

        if self.pattern_model.pattern.has_background():
            for file_ending in self.integrated_patterns_file_formats:
                directory = os.path.join(self.working_directories['spectrum'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.pattern_model.pattern.name + file_ending)
                if file_ending == '.xy':
                    self.pattern_model.save_pattern(filename, header=self._create_xy_header(),
                                                    subtract_background=True)
                else:
                    self.pattern_model.save_pattern(filename, subtract_background=True)

    def _create_xy_header(self):
        header = self.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header += '\n#\n# ' + self.model.pattern_model.unit + '\t I'
        return header

    def update_mask_dimension(self):
        self.mask_model.set_dimension(self.img_model.img_data.shape)

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
    def integration_unit(self, new_value):
        self._integration_unit = new_value
        self.integrate_image_1d()

    @property
    def integrate_cake(self):
        return self._integrate_cake

    @integrate_cake.setter
    def integrate_cake(self, new_value):
        self._integrate_cake = new_value
        if new_value:
            self.img_model.img_changed.connect(self.integrate_image_2d)
        else:
            self.img_model.img_changed.connect(self.integrate_image_2d)

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


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.pyqtSignal()
    configuration_selected = QtCore.pyqtSignal(int)  # new index
    configuration_removed = QtCore.pyqtSignal(int)  # removed index

    img_changed = QtCore.pyqtSignal()
    pattern_changed = QtCore.pyqtSignal()
    cake_changed = QtCore.pyqtSignal()

    def __init__(self, working_directories=None):
        super(DioptasModel, self).__init__()
        self.working_directories = working_directories
        self.configurations = []
        self.configuration_ind = 0
        self.configurations.append(ImgConfiguration(self.working_directories))

        self._overlay_model = OverlayModel()
        self._phase_model = PhaseModel()

        self.connect_models()

    def add_configuration(self):
        self.configurations.append(ImgConfiguration(self.working_directories))
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
        if ind >= 0 and ind < len(self.configurations):
            self.disconnect_models()
            self.configuration_ind = ind
            self.connect_models()
            self.configuration_selected.emit(ind)
            self.img_changed.emit()
            self.pattern_changed.emit()
            self.cake_changed.emit()

    def disconnect_models(self):
        self.img_model.img_changed.disconnect(self.img_changed)
        self.pattern_model.pattern_changed.disconnect(self.pattern_changed)
        self.current_configuration.cake_img_changed.disconnect(self.cake_changed)

    def connect_models(self):
        self.img_model.img_changed.connect(self.img_changed)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)
        self.current_configuration.cake_img_changed.connect(self.cake_changed)

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

    def clear(self):
        for configuration in self.configurations:
            del configuration.calibration_model.cake_geometry
            del configuration.calibration_model.spectrum_geometry
            del configuration.img_model
            del configuration.mask_model
        del self.configurations


