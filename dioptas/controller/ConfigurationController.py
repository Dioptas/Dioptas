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
        :type dioptas_model: DioptasModel
        """
        self.widget = configuration_widget
        self.model = dioptas_model
        self.controllers = controllers

        self.update_configuration_widget()

        self.create_signals()

    def create_signals(self):
        self.widget.add_configuration_btn.clicked.connect(self.model.add_configuration)
        self.widget.remove_configuration_btn.clicked.connect(self.model.remove_configuration)

        self.widget.configuration_selected.connect(self.model.select_configuration)

        self.model.configuration_added.connect(self.update_configuration_widget)
        self.model.configuration_removed.connect(self.update_configuration_widget)
        self.model.configuration_selected.connect(self.configuration_selected)

        self.widget.factor_txt.editingFinished.connect(self.factor_txt_changed)

        self.widget.combine_patterns_btn.clicked.connect(self.combine_patterns_btn_clicked)
        self.widget.combine_cakes_btn.clicked.connect(self.combine_cakes_btn_clicked)

    def update_configuration_widget(self):
        self.widget.update_configurations(
            configurations=self.model.configurations,
            cur_ind=self.model.configuration_ind
        )

    def configuration_selected(self):
        self.widget.factor_txt.setText(str(self.model.img_model.factor))

    def combine_patterns_btn_clicked(self):
        self.model.combine_patterns = self.widget.combine_patterns_btn.isChecked()

    def combine_cakes_btn_clicked(self):
        self.model.combine_cakes = self.widget.combine_cakes_btn.isChecked()

    def factor_txt_changed(self):
        self.model.img_model.factor = float(str(self.widget.factor_txt.text()))
