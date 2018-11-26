# -*- coding: utf-8 -*-
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
from mock import MagicMock

from ..utility import QtTest, click_button
from ...model.DioptasModel import DioptasModel
from ...widgets.ConfigurationWidget import ConfigurationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class ConfigurationWidgetTest(QtTest):
    def setUp(self):
        self.config_widget = ConfigurationWidget()
        self.model = DioptasModel()

    def test_one_configuration(self):
        self.config_widget.update_configuration_btns(self.model.configurations, 0)
        self.assertEqual(len(self.config_widget.configuration_btns), 1)

    def test_multiple_configurations(self):
        self.model.add_configuration()
        self.model.add_configuration()
        self.model.add_configuration()
        self.config_widget.update_configuration_btns(self.model.configurations, 1)

        self.assertEqual(len(self.config_widget.configuration_btns), 4)
        self.assertFalse(self.config_widget.configuration_btns[0].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[2].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[3].isChecked())
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())

    def test_configuration_selected_signal(self):
        self.config_widget.configuration_selected = MagicMock()
        self.model.add_configuration()
        self.model.add_configuration()
        self.model.add_configuration()
        self.config_widget.update_configuration_btns(self.model.configurations, 0)

        click_button(self.config_widget.configuration_btns[3])
        self.config_widget.configuration_selected.emit.assert_called_once_with(3, True)

        self.assertFalse(self.config_widget.configuration_btns[0].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[1].isChecked())
        self.assertFalse(self.config_widget.configuration_btns[2].isChecked())
        self.assertTrue(self.config_widget.configuration_btns[3].isChecked())
