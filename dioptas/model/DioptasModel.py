# -*- coding: utf8 -*-
import os

import numpy as np

from PyQt4 import QtCore

from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel


class ImgConfiguration(QtCore.QObject):
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
        self._roi_mask = None

        self._integration_num_points = None
        self._integration_unit = '2th_deg'

        self.autosave_integrated_pattern = False
        self.integrated_patterns_file_formats = ['.xy']

        self.connect_signals()

    def connect_signals(self):
        self.img_model.img_changed.connect(self.integrate_image)
        self.img_model.img_changed.connect(self.update_mask_dimension)

    def integrate_image(self):
        if self.calibration_model.is_calibrated:
            if self.use_mask:
                if self.mask_model.supersampling_factor != self.img_model.supersampling_factor:
                    self.mask_model.set_supersampling(self.img_model.supersampling_factor)
                mask = self.mask_model.get_mask()
            else:
                mask = None

            if self.roi_mask is not None and mask is None:
                mask = self.roi_mask
            elif self.roi_mask is not None and mask is not None:
                mask = np.logical_or(mask, self.roi_mask)

            # if not self.widget.automatic_binning_cb.isChecked():
            #     num_points = int(str(self.widget.bin_count_txt.text()))
            # else:
            #     num_points = None

            x, y = self.calibration_model.integrate_1d(mask=mask, unit=self.integration_unit,
                                                       num_points=self.integration_num_points)

            self.pattern_model.set_pattern(x, y, self.img_model.filename, unit=self.integration_unit)  #

            if self.autosave_integrated_pattern:
                self.save_pattern()

    def save_pattern(self):
        filename = self.img_model.filename
        for file_ending in self.integrated_patterns_file_formats:
            if filename is not '':
                filename = os.path.join(
                    self.working_directories['spectrum'],
                    os.path.basename(str(self.img_model.filename)).split('.')[:-1][0] + file_ending)
            self.save_pattern(filename)

        if self.pattern_model.pattern.has_background():
            for file_ending in self.integrated_patterns_file_formats:
                directory = os.path.join(self.working_directories['spectrum'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.pattern_model.pattern.name + file_ending)
                self.save_pattern(filename, subtract_background=True)

    def update_mask_dimension(self):
        self.mask_model.set_dimension(self.img_model.img_data.shape)

    @property
    def integration_num_points(self):
        return self._integration_num_points

    @integration_num_points.setter
    def integration_num_points(self, new_value):
        self._integration_num_points = new_value
        self.integrate_image()

    @property
    def integration_unit(self):
        return self._integration_unit

    @integration_unit.setter
    def integration_unit(self, new_value):
        self._integration_unit = new_value
        self.integrate_image()

    @property
    def roi_mask(self):
        return self._roi_mask

    @roi_mask.setter
    def roi_mask(self, new_val):
        self._roi_mask = new_val
        self.integrate_image()


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.pyqtSignal()
    configuration_selected = QtCore.pyqtSignal(int)  # new index
    configuration_removed = QtCore.pyqtSignal(int)  # removed index

    img_changed = QtCore.pyqtSignal()
    pattern_changed = QtCore.pyqtSignal()

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

    def disconnect_models(self):
        self.img_model.img_changed.disconnect(self.img_changed)
        self.pattern_model.pattern_changed.disconnect(self.pattern_changed)

    def connect_models(self):
        self.img_model.img_changed.connect(self.img_changed)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)

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
