# -*- coding: utf8 -*-

import os

import numpy as np
from PyQt4 import QtGui, QtCore

# imports for type hinting in PyCharm -- DO NOT DELETE
from model.ImgConfiguration import ImgConfigurationManager
from widgets.ConfigurationWidget import ConfigurationWidget


class ConfigurationController(object):
    """
    Deals with all the signal handling and model upgrades related to be using multiple configurations.
    """
    def __init__(self, configuration_widget, configuration_manager, controllers=None):
        """

        :param configuration_widget:
        :param configuration_manager:
        :param controllers:
        """
        self.widget = configuration_widget
        self.configuration_manager = configuration_manager
        self.controllers = controllers