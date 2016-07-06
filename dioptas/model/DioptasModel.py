# -*- coding: utf8 -*-

from PyQt4 import QtCore

from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel


class ImgConfiguration(QtCore.QObject):
    def __init__(self):
        super(ImgConfiguration, self).__init__()
        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)

        self.use_mask = False


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.pyqtSignal()
    configuration_selected = QtCore.pyqtSignal(int)  # new index
    configuration_removed = QtCore.pyqtSignal(int)  # removed index

    img_changed = QtCore.pyqtSignal()
    pattern_changed = QtCore.pyqtSignal()

    def __init__(self):
        super(DioptasModel, self).__init__()
        self.configurations = []
        self.configuration_ind = 0
        self.configurations.append(ImgConfiguration())

        self._pattern_model = PatternModel()
        self._phase_model = PhaseModel()

        self.connect_models()

    def add_configuration(self):
        self.configurations.append(ImgConfiguration())
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
        return self._pattern_model

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
        self.configurations[self.configuration_ind].use_mask=new_val

    def clear(self):
        for configuration in self.configurations:
            del configuration.calibration_model.cake_geometry
            del configuration.calibration_model.spectrum_geometry
            del configuration.img_model
            del configuration.mask_model
        del self.configurations
