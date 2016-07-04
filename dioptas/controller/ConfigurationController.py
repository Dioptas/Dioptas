# -*- coding: utf8 -*-
import os

from PyQt4 import QtGui, QtCore

# imports for type hinting in PyCharm -- DO NOT DELETE
from widgets.ConfigurationWidget import ConfigurationWidget
from model.DioptasModel import DioptasModel


class ConfigurationController(object):
    """
    Deals with all the signal handling and model upgrades related to be using multiple configurations.
    """

    def __init__(self, configuration_widget, dioptas_model, controllers=()):
        """
        :type configuration_widget: ConfigurationWidget
        :type configuration_manager: DioptasModel
        """
        self.widget = configuration_widget
        self.model = dioptas_model
        self.controllers = controllers

        self.update_configuration_widget()

        self.create_signals()

    def create_signals(self):
        self.widget.add_configuration_btn.clicked.connect(self.model.add_configuration)
        self.widget.remove_configuration_btn.clicked.connect(self.model.remove_configuration)

        self.widget.configuration_selected.connect(self.configuration_selected)
        self.widget.configuration_selected.connect(self.update_controller)

        self.model.configuration_added.connect(self.update_configuration_widget)
        self.model.configuration_added.connect(self.update_controller)

        self.model.configuration_removed.connect(self.update_configuration_widget)
        self.model.configuration_removed.connect(self.update_controller)

    def update_configuration_widget(self):
        self.widget.update_configurations(
            configurations=self.model.configurations,
            cur_ind=self.model.current_configuration
        )

    def configuration_selected(self, selected_ind):
        self.model.current_configuration = selected_ind

    def update_controller(self):
        # update models
        for controller in self.controllers:
            controller.img_model = self.model.img_model
            controller.mask_model = self.model.mask_model
            controller.calibration_model = self.model.calibration_model

        # fire update events
        self.model.img_model.img_changed.emit()
