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

from ..utility import QtTest
import os
import gc

from qtpy import QtWidgets
from mock import MagicMock

from ..utility import enter_value_into_text_field, click_button

from ...controller.integration import OptionsController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')

QtWidgets.QApplication.processEvents = MagicMock()


class OptionsControllerTest(QtTest):
    def setUp(self):
        self.widget = IntegrationWidget()
        self.options_widget = self.widget.integration_control_widget.integration_options_widget
        self.model = DioptasModel()

        self.options_controller = OptionsController(self.widget, self.model)

    def tearDown(self):
        del self.options_controller
        del self.widget
        del self.model
        gc.collect()

    def test_change_azimuth_bins(self):
        enter_value_into_text_field(self.options_widget.cake_azimuth_points_sb.lineEdit(), 100)
        self.assertEqual(self.model.current_configuration.cake_azimuth_points, 100)

    def test_change_azimuth_range(self):
        click_button(self.options_widget.cake_full_toggle_btn)
        enter_value_into_text_field(self.options_widget.cake_azimuth_min_txt, -100)
        self.assertEqual(self.model.current_configuration.cake_azimuth_range[0], -100)

        enter_value_into_text_field(self.options_widget.cake_azimuth_max_txt, 200)
        self.assertEqual(self.model.current_configuration.cake_azimuth_range[1], 200)



