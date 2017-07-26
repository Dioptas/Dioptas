# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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

import os
import numpy as np

from ..utility import QtTest, unittest_data_path, click_button
from ...widgets.integration import IntegrationWidget
from ...controller.integration.BackgroundController import BackgroundController
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel


class BackgroundControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = BackgroundController(
            widget=self.widget,
            dioptas_model=self.model
        )
        self.pattern_controller = PatternController(
            widget=self.widget,
            dioptas_model=self.model
        )

    def test_configuration_selected_changes_background_image_widgets(self):
        self.model.img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
        self.model.img_model.load_background(os.path.join(unittest_data_path, 'image_001.tif'))

        self.model.add_configuration()
        self.model.img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
        self.model.img_model.load_background(os.path.join(unittest_data_path, 'image_002.tif'))

        self.assertEqual(str(self.widget.bkg_image_filename_lbl.text()), 'image_002.tif')

        self.model.select_configuration(0)
        self.assertEqual(str(self.widget.bkg_image_filename_lbl.text()), 'image_001.tif')

        self.widget.bkg_image_offset_sb.setValue(100)
        self.model.select_configuration(1)
        self.assertEqual(self.widget.bkg_image_offset_sb.value(), 0)

        self.widget.bkg_image_scale_sb.setValue(2)
        self.model.select_configuration(0)
        self.assertEqual(self.widget.bkg_image_scale_sb.value(), 1)

    def test_changing_unit(self):
        # load calibration and image
        self.model.calibration_model.load(os.path.join(unittest_data_path, 'LaB6_40keV_MarCCD.poni'))
        self.model.img_model.load(os.path.join(unittest_data_path, "image_001.tif"))

        x_raw, y_raw = self.model.pattern_model.pattern.data
        click_button(self.widget.qa_bkg_pattern_btn)
        x_2th, y_2th = self.model.pattern_model.pattern.data

        self.assertNotEqual(np.sum(y_raw), np.sum(y_2th))

        click_button(self.widget.pattern_q_btn)
        x_q, y_q = self.model.pattern_model.pattern.data
        x_q_bkg, y_q_bkg = self.model.pattern_model.pattern.auto_background_pattern.data

        self.assertLess(np.max(x_q), np.max(x_2th))
        self.assertEqual(x_q[0], x_q_bkg[0])
        self.assertEqual(x_q[-1], x_q_bkg[-1])

