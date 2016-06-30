# -*- coding: utf8 -*-

from PyQt4 import QtCore

from . import ImgModel, CalibrationModel, MaskModel


class ImgConfiguration(QtCore.QObject):
    def __init__(self):
        super(ImgConfiguration, self).__init__()
        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel()


class ImgConfigurationManager(QtCore.QObject):
    configuration_added = QtCore.pyqtSignal()
    configuration_selected = QtCore.pyqtSignal(int)  # new index
    configuration_removed = QtCore.pyqtSignal()

    def __init__(self):
        super(ImgConfigurationManager, self).__init__()
        self.configurations = []
        self.current_configuration = 0
        self.configurations.append(ImgConfiguration())

    def add_configuration(self):
        self.configurations.append(ImgConfiguration())
        self.current_configuration = len(self.configurations) - 1
        self.configuration_added.emit()

    def remove_configuration(self, ind=-1):
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            self.current_configuration = len(self.configurations)-1
        self.configuration_removed.emit(self.current_configuration)

    def select_configuration(self, ind):
        if ind>=0 and ind<len(self.configurations):
            self.current_configuration = ind
            self.configuration_selected.emit(ind)

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
