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
import numpy as np
from qtpy import QtWidgets
from mock import MagicMock

from ..utility import click_button

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")


def mock_open_filename(filepath):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[filepath])
    QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=filepath)


def test_map(main_controller):
    # Herbert has recently collected a large map of his sample and wants to visualize
    # and explore it in Dioptas.
    

    # He opens Dioptas loads his calibration file and is curious to see that there
    # is a mode on the left side which is called "Map".
    main_controller.model.current_configuration.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))

    # He clicks on the map mode and sees that there is a button to load his files.

    click_button(main_controller.widget.map_mode_btn)
    assert main_controller.widget.map_widget.isVisible()


    # The loading of the files generates a list of files in the GUI. Further, it automatically
    # generates a map of something on the left side of the GUI.

    # He clicks on individual points of the map and sees that the corresponding image and pattern
    # is shown in the right side of the GUI.

    # He clicks into the Pattern and realizes that the map is updating depending on where he clicks.