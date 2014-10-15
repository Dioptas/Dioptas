# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = 'Clemens Prescher'
from PyQt4 import QtGui, QtCore


class IntegrationBackgroundController(object):
    """
    The IntegrationImageController manages the Image actions in the Integration Window. It connects the file actions, as
    well as interaction with the image_view.
    """

    def __init__(self, working_dir, view, img_data, spectrum_data,):
        self.working_dir = working_dir
        self.view = view
        self.img_data = img_data
        self.spectrum_data = spectrum_data
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.bkg_image_load_btn, self.load_background)
        self.connect_click_function(self.view.bkg_image_delete_btn, self.delete_background)

        self.view.bkg_image_scale_step_txt.editingFinished.connect(self.update_bkg_image_scale_step)
        self.view.bkg_image_offset_step_txt.editingFinished.connect(self.update_bkg_image_offset_step)
        self.view.bkg_image_scale_sb.valueChanged.connect(self.bkg_image_scale_sb_changed)
        self.view.bkg_image_offset_sb.valueChanged.connect(self.bkg_image_offset_sb_changed)

    def connect_click_function(self, emitter, function):
        """
        Small helper function for the button-click connection.
        """
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def load_background(self, filename = None):
        print 'yeha loading file'

    def delete_background(self):
        print 'deleting background'

    def update_bkg_image_scale_step(self):
        pass

    def update_bkg_image_offset_step(self):
        pass

    def bkg_image_scale_sb_changed(self):
        pass

    def bkg_image_offset_sb_changed(self):
        pass

