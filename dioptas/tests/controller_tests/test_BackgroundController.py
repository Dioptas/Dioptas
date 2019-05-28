# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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
from mock import MagicMock

from qtpy import QtWidgets

from ..utility import QtTest, unittest_data_path, click_button, delete_if_exists
from ...widgets.integration import IntegrationWidget
from ...controller.integration.BackgroundController import BackgroundController
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel

data_path = os.path.join(os.path.dirname(__file__), '../data')


class BackgroundControllerTest(QtTest):
    def setUp(self):
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

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "test.xy"))

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

    def test_configuration_selected_changes_auto_background_widgets(self):
        self.model.pattern_model.load_pattern(os.path.join(unittest_data_path, 'pattern_001.chi'))
        click_button(self.widget.qa_bkg_pattern_btn)
        self.assertTrue(self.widget.bkg_pattern_gb.isChecked())
        self.model.add_configuration()
        self.assertFalse(self.model.pattern_model.pattern.auto_background_subtraction)
        self.assertFalse(self.widget.bkg_pattern_gb.isChecked())

        self.model.select_configuration(0)
        self.assertTrue(self.widget.bkg_pattern_gb.isChecked())
        click_button(self.widget.qa_bkg_pattern_inspect_btn)
        self.model.select_configuration(1)
        self.assertFalse(self.widget.qa_bkg_pattern_inspect_btn.isChecked())

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

    def test_save_fit_background_pattern(self):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(data_path, "test_bg.xy"))
        self.model.calibration_model.create_file_header = MagicMock(return_value="None")
        click_button(self.widget.qa_bkg_pattern_btn)
        click_button(self.widget.bkg_pattern_save_btn)

        self.assertTrue(os.path.exists(os.path.join(data_path, "test_bg.xy")))
