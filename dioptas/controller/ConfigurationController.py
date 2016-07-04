# -*- coding: utf8 -*-
import os

from PyQt4 import QtGui, QtCore

# imports for type hinting in PyCharm -- DO NOT DELETE
from model.ImgConfiguration import ImgConfigurationManager
from widgets.ConfigurationWidget import ConfigurationWidget


class ConfigurationController(object):
    """
    Deals with all the signal handling and model upgrades related to be using multiple configurations.
    """

    def __init__(self, configuration_widget, configuration_manager, controllers=()):
        """
        :type configuration_widget: ConfigurationWidget
        :type configuration_manager: ImgConfigurationManager
        """
        self.widget = configuration_widget
        self.configuration_manager = configuration_manager
        self.controllers = controllers

        self.update_configuration_widget()

        self.create_signals()

    def create_signals(self):
        self.widget.add_configuration_btn.clicked.connect(self.configuration_manager.add_configuration)
        self.widget.remove_configuration_btn.clicked.connect(self.configuration_manager.remove_configuration)

        self.widget.configuration_selected.connect(self.configuration_selected)
        self.widget.configuration_selected.connect(self.update_controller)

        self.configuration_manager.configuration_added.connect(self.update_configuration_widget)
        self.configuration_manager.configuration_added.connect(self.update_controller)

        self.configuration_manager.configuration_removed.connect(self.update_configuration_widget)
        self.configuration_manager.configuration_removed.connect(self.update_controller)

    def update_configuration_widget(self):
        self.widget.update_configurations(
            configurations=self.configuration_manager.configurations,
            cur_ind=self.configuration_manager.current_configuration
        )

    def configuration_selected(self, selected_ind):
        self.configuration_manager.current_configuration = selected_ind

    def update_controller(self):
        # update models
        for controller in self.controllers:
            controller.img_model = self.configuration_manager.img_model
            controller.mask_model = self.configuration_manager.mask_model
            controller.calibration_model = self.configuration_manager.calibration_model

        # fire update events
        self.configuration_manager.img_model.img_changed.emit()
