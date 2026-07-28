# SPDX-License-Identifier: MIT

import os
import numpy as np
from qtpy import QtWidgets
from mock import MagicMock
from pytest import approx

from dioptas.controller.MainController import MainController
from dioptas.model.util.calc import convert_units

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


def test_map_panel_moves_into_the_integration_view(main_controller: MainController):
    # Herbert wants to keep exploring his map, but with the large image and all
    # the phase controls of the integration view at hand.
    prepare_map_gui(main_controller)
    map_widget = main_controller.widget.map_widget
    panel = map_widget.map_panel_widget
    map_tab = main_controller.widget.integration_widget.map_control_widget

    # in the map mode the panel sits in the map widget
    assert map_widget.map_panel_host.panel is panel
    assert map_tab.panel is None

    # switching to the integration view brings the map along, into its own tab
    click_button(main_controller.widget.integration_mode_btn)
    assert map_tab.panel is panel
    assert map_widget.map_panel_host.panel is None
    assert panel.map_plot_widget.img_data is not None

    # and going back to the map mode returns it
    click_button(main_controller.widget.map_mode_btn)
    assert map_widget.map_panel_host.panel is panel
    assert map_tab.panel is None


def test_selecting_a_map_point_from_the_integration_view(main_controller: MainController):
    # Herbert clicks around in the map while the integration view is shown, and
    # expects image, pattern and map marker to follow.
    prepare_map_gui(main_controller)
    click_button(main_controller.widget.integration_mode_btn)

    model = main_controller.model
    integration_widget = main_controller.widget.integration_widget
    panel = main_controller.widget.map_widget.map_panel_widget

    panel.map_plot_widget.mouse_left_clicked.emit(2, 2)

    assert model.img_model.filename == map_img_file_paths[2]
    assert np.array_equal(integration_widget.img_widget.img_data, model.img_model.img_data)

    # the pattern comes from a full integration, not from the stored map data,
    # so that it honours the settings of the integration view
    assert model.pattern.name == os.path.basename(map_img_file_paths[2]).split(".")[0]

    # the marker follows the click
    click_x, click_y = panel.map_plot_widget.mouse_click_item.getData()
    assert click_x[0] == approx(2.5)
    assert click_y[0] == approx(2.5)

    # and the map mode file list is up to date when he returns to it
    click_button(main_controller.widget.map_mode_btn)
    assert main_controller.widget.map_widget.control_widget.file_list.currentRow() == 2


def test_map_marker_follows_images_loaded_elsewhere(main_controller: MainController):
    # Stepping through files in the integration view moves the marker, and it
    # disappears for images that are not part of the map.
    prepare_map_gui(main_controller)
    click_button(main_controller.widget.integration_mode_btn)

    model = main_controller.model
    panel = main_controller.widget.map_widget.map_panel_widget

    model.img_model.load(map_img_file_paths[4])
    click_x, click_y = panel.map_plot_widget.mouse_click_item.getData()
    assert click_x[0] == approx(1.5)
    assert click_y[0] == approx(1.5)
    assert panel.map_plot_widget.mouse_click_item.isVisible()

    # an image of the same detector, but not one of the map points
    model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert not panel.map_plot_widget.mouse_click_item.isVisible()

    # back in the map mode the file list agrees with the marker: no map point
    # is shown, so nothing is selected
    click_button(main_controller.widget.map_mode_btn)
    assert main_controller.widget.map_widget.control_widget.file_list.currentRow() == -1


def test_undocked_map_stays_available_in_every_mode(main_controller: MainController):
    # Herbert has two screens and wants the map large on the second one while
    # he works in the integration view on the first.
    prepare_map_gui(main_controller)
    widget = main_controller.widget
    panel = widget.map_widget.map_panel_widget
    window = widget.map_panel_window

    click_button(panel.map_plot_control_widget.undock_btn)

    assert not main_controller.model.view.map_docked
    assert panel.map_plot_control_widget.undock_btn.text() == "Dock"
    assert window.panel is panel
    assert window.isVisible()
    assert widget.map_widget.map_panel_host.panel is None

    # the map keeps working from its own window, whatever mode is shown
    click_button(widget.integration_mode_btn)
    assert window.panel is panel
    assert widget.integration_widget.map_control_widget.panel is None

    panel.map_plot_widget.mouse_left_clicked.emit(1, 1)  # center point of a 3x3 map
    assert main_controller.model.img_model.filename == map_img_file_paths[4]

    # and so does the window region in the integration pattern
    pattern_widget = widget.integration_widget.pattern_widget
    assert pattern_widget.map_interactive_roi in pattern_widget.pattern_plot.items

    # docking it again from the placeholder puts it back where it belongs
    click_button(widget.integration_widget.map_control_widget.dock_btn)
    assert main_controller.model.view.map_docked
    assert widget.integration_widget.map_control_widget.panel is panel
    assert not window.isVisible()


def test_docking_works_from_a_mode_that_has_no_map(main_controller: MainController):
    # Herbert undocks the map, wanders off into the mask mode, and docks it
    # again from there.
    prepare_map_gui(main_controller)
    widget = main_controller.widget
    panel = widget.map_widget.map_panel_widget

    click_button(panel.map_plot_control_widget.undock_btn)
    click_button(widget.mask_mode_btn)

    # the panel's own button is the one on screen in the floating window
    assert panel.map_plot_control_widget.undock_btn.text() == "Dock"
    click_button(panel.map_plot_control_widget.undock_btn)

    assert main_controller.model.view.map_docked
    assert widget.map_panel_window.panel is None
    assert not widget.map_panel_window.isVisible()
    # it went back to the home it was undocked from
    assert widget.map_widget.map_panel_host.panel is panel


def test_removing_a_configuration_updates_the_map_panel(main_controller: MainController):
    # Herbert compares two samples in two configurations and removes the one
    # holding the map.
    prepare_map_gui(main_controller)
    model = main_controller.model
    panel = main_controller.widget.map_widget.map_panel_widget

    assert panel.map_plot_widget.img_data is not None

    model.add_configuration()  # a fresh configuration without a map
    assert panel.map_plot_widget.img_data.size == 0

    model.select_configuration(0)
    assert panel.map_plot_widget.img_data.shape == (3, 3)

    model.remove_configuration()  # removes the one holding the map
    assert model.map_model.map is None
    assert panel.map_plot_widget.img_data.size == 0

    # moving the mouse over the now empty map must not raise
    panel.map_plot_widget.mouse_moved.emit(1, 1)
    panel.map_plot_widget.mouse_left_clicked.emit(1, 1)


def test_closing_the_map_window_docks_it_again(main_controller: MainController):
    prepare_map_gui(main_controller)
    widget = main_controller.widget

    click_button(widget.map_widget.map_panel_widget.map_plot_control_widget.undock_btn)
    assert not main_controller.model.view.map_docked

    widget.map_panel_window.close()

    assert main_controller.model.view.map_docked
    assert (
        widget.map_widget.map_panel_host.panel is widget.map_widget.map_panel_widget
    )


def test_exploring_a_map_from_the_integration_view(main_controller: MainController):
    # Herbert has his map and now wants to work the way he normally does: big
    # image, phases on the pattern, and the map right there to click around in.
    prepare_map_gui(main_controller)
    model = main_controller.model
    widget = main_controller.widget
    panel = widget.map_widget.map_panel_widget

    click_button(widget.integration_mode_btn)
    control_widget = widget.integration_widget.integration_control_widget
    control_widget.tab_widget_1.setCurrentWidget(widget.integration_widget.map_control_widget)

    # the map is in the tab, and the window region shows up in the pattern
    assert widget.integration_widget.map_control_widget.panel is panel
    pattern_widget = widget.integration_widget.pattern_widget
    assert pattern_widget.map_interactive_roi in pattern_widget.pattern_plot.items

    # he picks a point and gets that image, integrated with his settings
    panel.map_plot_widget.mouse_left_clicked.emit(0, 0)
    assert model.img_model.filename == map_img_file_paths[6]
    assert np.array_equal(
        widget.integration_widget.img_widget.img_data, model.img_model.img_data
    )

    # he works in Q, and dragging the region there still picks the right part
    # of the pattern: the map keeps its window in the unit it was integrated in
    model.integration_unit = "q_A^-1"
    assert model.map_model.pattern_unit == "2th_deg"

    wavelength = model.calibration_model.wavelength
    region = sorted(
        convert_units(x, wavelength, "2th_deg", "q_A^-1") for x in (8.0, 9.0)
    )
    old_map = np.copy(model.map_model.map)
    pattern_widget.map_interactive_roi.setRegion(region)

    assert model.map_model.window == approx((8.0, 9.0), rel=1e-6)
    assert not np.array_equal(model.map_model.map, old_map)
    assert np.array_equal(panel.map_plot_widget.img_data, np.flipud(model.map_model.map))

    # finally he puts the map on his second screen and keeps clicking points
    click_button(panel.map_plot_control_widget.undock_btn)
    assert widget.map_panel_window.panel is panel

    panel.map_plot_widget.mouse_left_clicked.emit(2, 0)
    assert model.img_model.filename == map_img_file_paths[8]
    assert pattern_widget.map_interactive_roi in pattern_widget.pattern_plot.items


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
