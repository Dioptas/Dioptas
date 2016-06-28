# -*- coding: utf8 -*-

from PyQt4 import QtCore

from . import ImgModel, CalibrationModel, MaskModel


class ImgConfiguration(object):
    def __init__(self):
        self.img_model = ImgModel()
        self.mask_model = MaskModel(self.img_model)
        self.calibration_model = CalibrationModel(self.img_model)


class ImgConfigurationManager(QtCore.QObject):
    configuration_added = QtCore.pyqtBoundSignal()
    configuration_selected = QtCore.pyqtBoundSignal(int)  # new index
    configuration_removed = QtCore.pyqtBoundSignal()

    img_changed = QtCore.pyqtBoundSignal()

    def __init__(self):
        super(ImgConfigurationManager, self).__init__()
        self.configurations = []
        self.current_configuration = 0
        self.configurations.append(ImgConfiguration())

        self.configurations[self.current_configuration].img_changed.connect(self.img_changed)

    def add_configuration(self):
        self.configurations.append(ImgConfiguration())
        self.configurations[self.current_configuration].img_changed.disconnect(self.img_changed)
        self.current_configuration = len(self.configurations) - 1
        self.configurations[self.current_configuration].img_changed.connect(self.img_changed)
        self.configuration_added.emit()
        self.img_changed.emit()

    @property
    def img_model(self):
        return self.configurations[self.current_configuration].img_model

    @property
    def mask_model(self):
        return self.configurations[self.current_configuration].mask_model

    @property
    def calibration_model(self):
        return self.configurations[self.current_configuration].calibration_model
