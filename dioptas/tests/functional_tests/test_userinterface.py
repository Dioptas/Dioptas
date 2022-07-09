# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

from mock import MagicMock
import os
import gc

import numpy as np

from qtpy import QtCore

from ..utility import QtTest, click_button
from ...controller import MainController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')


class UserInterFaceTest(QtTest):
    @classmethod
    def tearDownClass(cls):
        del cls.app
        gc.collect()

    def setUp(self):
        self.controller = MainController(use_settings=False)
        self.model = self.controller.model
        self.model.calibration_model.integrate_1d = MagicMock(
            return_value=(self.model.calibration_model.tth,
                          self.model.calibration_model.int))
        self.phase_model = self.model.phase_model

        self.calibration_widget = self.controller.widget.calibration_widget
        self.mask_widget = self.controller.widget.mask_widget
        self.integration_widget = self.controller.widget.integration_widget

        self.integration_controller = self.controller.integration_controller
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))

        self.integration_pattern_controller = self.integration_controller.pattern_controller
        self.integration_image_controller = self.integration_controller.image_controller

    def tearDown(self):
        del self.integration_pattern_controller
        self.model.delete_configurations()
        del self.integration_widget
        del self.integration_controller
        del self.model
        gc.collect()

    def test_synchronization_of_view_range(self):
        # calibration and mask view
        self.calibration_widget.img_widget.img_view_box.setRange(QtCore.QRectF(-10, -10, 20, 20))
        click_button(self.controller.widget.mask_mode_btn)

        self.assertAlmostEqual(np.sum(np.array(self.calibration_widget.img_widget.img_view_box.targetRange()) - \
                                      np.array(self.mask_widget.img_widget.img_view_box.targetRange())), 0)

        self.mask_widget.img_widget.img_view_box.setRange(QtCore.QRectF(100, 100, 300, 300))
        click_button(self.controller.widget.calibration_mode_btn)

        self.assertAlmostEqual(np.sum(np.array(self.calibration_widget.img_widget.img_view_box.targetRange()) - \
                                      np.array(self.mask_widget.img_widget.img_view_box.targetRange())), 0)
