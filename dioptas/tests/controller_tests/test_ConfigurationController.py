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

import os
import unittest
from mock import MagicMock
import gc

import numpy as np

from ..utility import (
    QtTest,
    delete_if_exists,
    click_button,
    enter_value_into_text_field,
)

from qtpy import QtWidgets

from ...controller.ConfigurationController import ConfigurationController
from ...model.DioptasModel import DioptasModel, Pattern
from ...widgets.ConfigurationWidget import ConfigurationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
jcpds_path = os.path.join(data_path, "jcpds")


class ConfigurationControllerTest(QtTest):
    def setUp(self):
        self.config_widget = ConfigurationWidget()
        self.model = DioptasModel()
        self.config_controller = ConfigurationController(
            configuration_widget=self.config_widget,
            dioptas_model=self.model,
            controllers=[],
        )

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "combined_pattern.xy"))
        del self.model
        del self.config_widget
        del self.config_controller
        gc.collect()

    def test_initial_configuration_display(self):
        self.assertEqual(len(self.config_widget.configuration_btns), 1)

    def test_adding_configurations(self):
        click_button(self.config_widget.add_configuration_btn)
        self.assertEqual(len(self.model.configurations), 2)
        self.assertEqual(len(self.config_widget.configuration_btns), 2)
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())

        click_button(self.config_widget.add_configuration_btn)
        self.assertEqual(len(self.model.configurations), 3)
        self.assertEqual(len(self.config_widget.configuration_btns), 3)
        self.assertTrue(self.config_widget.configuration_btns[2].isChecked())

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_selecting_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 3)
        self.assertTrue(self.config_widget.configuration_btns[-1].isChecked())

        click_button(self.config_widget.configuration_btns[0])
        self.assertEqual(self.model.configuration_ind, 0)

    def test_remove_last_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 3)
        self.assertTrue(self.config_widget.configuration_btns[3].isChecked())

        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 2)
        self.assertTrue(self.config_widget.configuration_btns[2].isChecked())
        self.assertEqual(len(self.config_widget.configuration_btn_group.buttons()), 3)

    def test_remove_first_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        click_button(self.config_widget.configuration_btns[0])
        self.assertEqual(self.model.configuration_ind, 0)

        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 0)
        self.assertTrue(self.config_widget.configuration_btns[0].isChecked())
        self.assertEqual(len(self.model.configurations), 3)

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_remove_in_between_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        click_button(self.config_widget.configuration_btns[1])
        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 1)
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())
        self.assertEqual(len(self.model.configurations), 3)

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_using_factors(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        data1 = np.copy(self.model.img_data)
        enter_value_into_text_field(self.config_widget.factor_txt, 2.5)
        self.assertTrue(np.array_equal(2.5 * data1, self.model.img_data))

        self.model.add_configuration()
        self.assertEqual(float(str(self.config_widget.factor_txt.text())), 1.0)
        enter_value_into_text_field(self.config_widget.factor_txt, 3.5)
        self.assertEqual(self.model.img_model.factor, 3.5)

        self.model.select_configuration(0)
        self.assertEqual(self.model.img_model.factor, 2.5)
        self.assertEqual(float(str(self.config_widget.factor_txt.text())), 2.5)

    def test_file_browsing(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        self.config_widget.file_iterator_pos_txt.setText("0")

        click_button(self.config_widget.next_file_btn)

        self.assertEqual(
            os.path.abspath(self.model.configurations[0].img_model.filename),
            os.path.abspath(os.path.join(data_path, "image_002.tif")),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(os.path.join(data_path, "image_002.tif")),
        )

        click_button(self.config_widget.previous_file_btn)

        self.assertEqual(
            os.path.abspath(self.model.configurations[0].img_model.filename),
            os.path.abspath(os.path.join(data_path, "image_001.tif")),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(os.path.join(data_path, "image_001.tif")),
        )

    def test_folder_browsing(self):
        self.model.img_model.load(
            os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
        )
        self.model.add_configuration()
        self.model.img_model.load(
            os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
        )

        click_button(self.config_widget.next_folder_btn)

        self.assertEqual(
            self.model.configurations[0].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run2", "image_1.tif")
            ),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run2", "image_1.tif")
            ),
        )

        click_button(self.config_widget.previous_folder_btn)

        self.assertEqual(
            self.model.configurations[0].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
            ),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
            ),
        )

    def test_save_combined_pattern(self):
        # prepare two patterns
        x1 = np.linspace(0, 10)
        y1 = np.ones(x1.shape)
        pattern1 = Pattern(x1, y1)

        x2 = np.linspace(7, 15)
        y2 = np.ones(x2.shape) * 2
        pattern2 = Pattern(x2, y2)

        self.model.pattern_model.pattern = pattern1
        self.model.add_configuration()
        self.model.pattern_model.pattern = pattern2

        self.model.combine_patterns = True

        # click the button
        file_path = os.path.join(data_path, "combined_pattern.xy")
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=file_path)
        click_button(self.config_widget.saved_combined_patterns_btn)

        # load and check that it worked
        saved_pattern = Pattern.from_file(file_path)
        x3, _ = saved_pattern.data
        self.assertLess(np.min(x3), 7)
        self.assertGreater(np.max(x3), 10)
