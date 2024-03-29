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
from pytest import approx

from dioptas.controller.MainController import MainController

from ..utility import click_button

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")
map_img_path = os.path.join(data_path, "map")
map_pattern_path = os.path.join(data_path, "map", "xy")
map_img_file_names = [
    f for f in os.listdir(map_img_path) if os.path.isfile(os.path.join(map_img_path, f))
]
map_img_file_paths = [
    os.path.join(map_img_path, filename) for filename in map_img_file_names
]


def mock_open_filenames(filepaths):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=filepaths)


def prepare_map_gui(main_controller: MainController):
    main_controller.model.current_configuration.img_model.load(map_img_file_paths[0])
    main_controller.model.current_configuration.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    map_widget = main_controller.widget.map_widget
    click_button(main_controller.widget.map_mode_btn)
    mock_open_filenames(map_img_file_paths)
    click_button(map_widget.control_widget.load_btn)


def test_map(main_controller: MainController):
    # Herbert has recently collected a large map of his sample and wants to visualize
    # and explore it in Dioptas.

    # He opens Dioptas loads his calibration file and is curious to see that there
    # is a mode on the left side which is called "Map".
    main_controller.model.current_configuration.img_model.load(map_img_file_paths[0])
    main_controller.model.current_configuration.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )

    # He clicks on the map mode and sees a beautiful gui with 2 image views and one pattern view.

    click_button(main_controller.widget.map_mode_btn)
    assert main_controller.widget.map_widget.isVisible()

    map_widget = main_controller.widget.map_widget

    assert map_widget.map_pg_layout.isVisible()
    assert map_widget.img_pg_layout.isVisible()
    assert map_widget.pattern_pg_layout.isVisible()

    # He realizes that there is also a control widget on the rightside which allows him to load
    # images. He clicks on the load button and load a list of files.

    assert map_widget.control_widget.isVisible()
    mock_open_filenames(map_img_file_paths)

    click_button(map_widget.control_widget.load_btn)
    # The loading of the files generates a list of files in the GUI. Further, it automatically
    # generates a map of something on the left side of the GUI.

    assert map_widget.control_widget.file_list.count() == len(map_img_file_names)
    file_list_strings = [
        map_widget.control_widget.file_list.item(i).text()
        for i in range(map_widget.control_widget.file_list.count())
    ]
    assert map_img_file_names == file_list_strings
    assert map_widget.map_plot_widget.img_data is not None

    # He notices that the first image is loaded in the corresponding image view
    # and the corresponding pattern is shown in the pattern view.

    assert map_widget.img_plot_widget.img_data is not None
    assert map_widget.pattern_plot_widget.plot_item.getData() is not None

    # He clicks on the file list in the control widget, and sees, that the image and pattern
    # is updated in the corresponding views.

    map_widget.control_widget.file_list.setCurrentRow(1)
    loaded_filename = main_controller.model.current_configuration.img_model.filename
    assert loaded_filename == map_img_file_paths[1]

    # Moving his mouse over the map on the right, he sees that the x, y indices of the map
    # are shown on the bottom of the map.

    map_widget.map_plot_widget.mouse_moved.emit(2, 1)
    assert map_widget.map_plot_control_widget.mouse_x_label.text() == "X: 2"
    assert map_widget.map_plot_control_widget.mouse_y_label.text() == "Y: 1"

    # He clicks on individual points of the map and sees that the corresponding image and pattern
    # is shown in the right side of the GUI.
    map_widget.map_plot_widget.mouse_left_clicked.emit(2, 2)
    loaded_filename = main_controller.model.current_configuration.img_model.filename
    assert loaded_filename == map_img_file_paths[2]
    assert map_widget.control_widget.file_list.currentRow() == 2

    # Suddenly he realizes that there is an interactive ROI in the pattern view.
    assert (
        map_widget.pattern_plot_widget.map_interactive_roi
        in map_widget.pattern_plot_widget.pattern_plot.items
    )

    # click anywhere in the pattern view moves the roi and updates the map
    pattern = main_controller.model.current_configuration.pattern_model.pattern
    center_x = np.mean(pattern.x)
    center_y = np.mean(pattern.y)
    map_widget.pattern_plot_widget.mouse_left_clicked.emit(center_x, center_y)

    assert map_widget.pattern_plot_widget.map_interactive_roi.center == approx(center_x)


def test_map_with_different_dimension(main_controller: MainController):
    # Herbert has collected another large map of his sample and wants to visualize
    # and explore it in Dioptas. This time the map is not rectangular but has a
    # different dimension (4x2)

    # He opens Dioptas loads his calibration file and is curious to see that there
    # is a mode on the left side which is called "Map".
    main_controller.model.current_configuration.img_model.load(map_img_file_paths[0])
    main_controller.model.current_configuration.calibration_model.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    map_widget = main_controller.widget.map_widget

    # He clicks on the map mode and loads his images.

    click_button(main_controller.widget.map_mode_btn)
    mock_open_filenames(map_img_file_paths[0:8])

    click_button(map_widget.control_widget.load_btn)

    # He realizes that the resulting map has a 4x2 dimension.

    assert map_widget.map_plot_widget.img_data.shape == (2, 4)

    # however, it is obvious that he actually needs a 4x2 map. He sees, that there are
    # multiple possible dimensions available below the image widget. He clicks on the
    # 2x4 dimension and sees that the map is updated.

    assert map_widget.map_plot_control_widget.map_dimension_cb.currentText() == "2x4"
    dim_cb = map_widget.map_plot_control_widget.map_dimension_cb
    dim_cb_str_list = [dim_cb.itemText(i) for i in range(dim_cb.count())]
    dim_model_str_list = [
        f"{x}x{y}"
        for x, y in main_controller.model.current_configuration.map_model.possible_dimensions
    ]
    assert dim_cb.count() == 4
    assert dim_cb_str_list == dim_model_str_list

    index_4x2 = dim_cb_str_list.index("4x2")
    dim_cb.setCurrentIndex(index_4x2)
    assert map_widget.map_plot_widget.img_data.shape == (4, 2)

    # He is satisfied and can go on exploring his map of the sample.
