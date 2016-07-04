# -*- coding: utf8 -*-

from PyQt4 import QtCore

from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel


class ImgConfiguration(QtCore.QObject):
    def __init__(self):
        super(ImgConfiguration, self).__init__()
        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.pyqtSignal()
    configuration_selected = QtCore.pyqtSignal(int)  # new index
    configuration_removed = QtCore.pyqtSignal(int)  # removed index

    img_changed = QtCore.pyqtSignal()
    pattern_changed = QtCore.pyqtSignal()

    def __init__(self):
        super(DioptasModel, self).__init__()
        self.configurations = []
        self.current_configuration = 0
        self.configurations.append(ImgConfiguration())

        self._pattern_model = PatternModel()
        self._phase_model = PhaseModel()

        self.img_model.img_changed.connect(self.img_changed)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)

    def add_configuration(self):
        self.configurations.append(ImgConfiguration())
        self.configuration_added.emit()
        self.select_configuration(len(self.configurations) - 1)

    def remove_configuration(self):
        ind = self.current_configuration
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            ind = len(self.configurations) - 1
        self.configuration_removed.emit(self.current_configuration)
        self.select_configuration(ind)

    def select_configuration(self, ind):
        if ind >= 0 and ind < len(self.configurations):
            self.img_model.img_changed.disconnect(self.img_changed)
            self.pattern_model.pattern_changed.disconnect(self.pattern_changed)

            self.current_configuration = ind
            self.configuration_selected.emit(ind)

            self.img_model.img_changed.connect(self.img_changed)
            self.pattern_model.pattern_changed.connect(self.pattern_changed)

    @property
    def img_model(self):
        """
        :rtype: ImgModel
        """
        return self.configurations[self.current_configuration].img_model

    @property
    def mask_model(self):
        """
        :rtype: MaskModel
        """
        return self.configurations[self.current_configuration].mask_model

    @property
    def calibration_model(self):
        """
        :rtype: CalibrationModel
        """
        return self.configurations[self.current_configuration].calibration_model

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
