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
import gc
import shutil
import numpy as np
from mock import MagicMock

from ..utility import QtTest, click_button, click_checkbox

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ...model.util.HelperModule import get_partial_value
from ...widgets.integration import IntegrationWidget
from ...controller.integration.ImageController import ImageController
from ...model.DioptasModel import DioptasModel

unittest_data_path = os.path.join(os.path.dirname(__file__), "../data")


def test_automatic_file_processing(integration_widget, dioptas_model, image_controller):
    # get into a specific folder
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
        return_value=[os.path.join(unittest_data_path, "image_001.tif")]
    )
    click_button(integration_widget.load_img_btn)
    assert str(integration_widget.img_filename_txt.text()) == "image_001.tif"
    assert dioptas_model.working_directories["image"] == unittest_data_path

    click_checkbox(integration_widget.autoprocess_cb)

    assert not dioptas_model.img_model._directory_watcher.signalsBlocked()
    assert integration_widget.autoprocess_cb.isChecked()
    assert dioptas_model.img_model.autoprocess

    shutil.copy2(
        os.path.join(unittest_data_path, "image_001.tif"),
        os.path.join(unittest_data_path, "image_003.tif"),
    )

    dioptas_model.img_model._directory_watcher.file_added.emit(
        os.path.join(unittest_data_path, "image_003.tif")
    )
    assert "image_003.tif" == str(integration_widget.img_filename_txt.text())
    
    # clean up
    os.remove(os.path.join(unittest_data_path, "image_003.tif"))


def test_configuration_selected_changes_mask_mode(
    integration_widget, dioptas_model, image_controller
):
    dioptas_model.add_configuration()
    click_button(integration_widget.img_mask_btn)
    assert dioptas_model.use_mask

    dioptas_model.select_configuration(0)
    assert not dioptas_model.use_mask
    assert not integration_widget.img_mask_btn.isChecked()


def test_configuration_selected_changes_mask_transparency(
    integration_widget, dioptas_model, image_controller
):
    click_button(integration_widget.img_mask_btn)
    dioptas_model.add_configuration()
    click_button(integration_widget.img_mask_btn)
    click_checkbox(integration_widget.mask_transparent_cb)
    assert dioptas_model.transparent_mask

    dioptas_model.select_configuration(0)
    assert not dioptas_model.transparent_mask
    assert not integration_widget.mask_transparent_cb.isChecked()


def test_configuration_selected_changed_autoprocessing_of_images(
    integration_widget, dioptas_model, image_controller
):
    click_checkbox(integration_widget.autoprocess_cb)
    dioptas_model.add_configuration()

    assert not dioptas_model.img_model.autoprocess
    assert not integration_widget.autoprocess_cb.isChecked()

    dioptas_model.select_configuration(0)
    assert dioptas_model.img_model.autoprocess
    assert integration_widget.autoprocess_cb.isChecked()


def test_configuration_selected_changes_calibration_name(
    integration_widget, dioptas_model, image_controller
):
    dioptas_model.calibration_model.calibration_name = "calib1"
    dioptas_model.add_configuration()
    dioptas_model.calibration_model.calibration_name = "calib2"

    dioptas_model.select_configuration(0)
    assert str(integration_widget.calibration_lbl.text()) == "calib1"

    dioptas_model.select_configuration(1)
    assert str(integration_widget.calibration_lbl.text()) == "calib2"


def test_configuration_selected_updates_mask_plot(
    integration_widget, dioptas_model, image_controller
):
    dioptas_model.mask_model.add_mask(os.path.join(unittest_data_path, "test.mask"))
    click_button(integration_widget.img_mask_btn)
    first_mask = dioptas_model.mask_model.get_img()
    dioptas_model.add_configuration()
    assert not integration_widget.img_mask_btn.isChecked()

    dioptas_model.mask_model.mask_below_threshold(dioptas_model.img_data, 1)
    second_mask = dioptas_model.mask_model.get_img()
    click_button(integration_widget.img_mask_btn)

    dioptas_model.select_configuration(0)
    assert np.sum(integration_widget.img_widget.mask_img_item.image - first_mask) == 0
    dioptas_model.select_configuration(1)
    assert np.sum(integration_widget.img_widget.mask_img_item.image - second_mask) == 0


def test_configuration_selected_updates_mask_transparency(
    integration_widget, dioptas_model, image_controller
):
    dioptas_model.mask_model.add_mask(os.path.join(unittest_data_path, "test.mask"))
    click_button(integration_widget.img_mask_btn)
    dioptas_model.add_configuration()

    assert not integration_widget.img_mask_btn.isChecked()
    assert not integration_widget.mask_transparent_cb.isVisible()


def test_configuration_selected_updates_roi_mode(
    integration_widget, dioptas_model, image_controller
):
    click_button(integration_widget.img_roi_btn)
    assert integration_widget.img_roi_btn.isChecked()
    assert (
        integration_widget.img_widget.roi
        in integration_widget.img_widget.img_view_box.addedItems
    )

    dioptas_model.add_configuration()
    assert not integration_widget.img_roi_btn.isChecked()
    assert (
        not integration_widget.img_widget.roi
        in integration_widget.img_widget.img_view_box.addedItems
    )


def test_mask_button_checking_in_image_mode(integration_widget, image_controller):
    click_button(integration_widget.img_mask_btn)
    assert integration_widget.img_mask_btn.isChecked()
    click_button(integration_widget.img_mask_btn)
    assert not integration_widget.img_mask_btn.isChecked()


def test_mask_button_checking_in_cake_mode(
    integration_widget, dioptas_model, image_controller
):
    load_pilatus1M_image_and_calibration(dioptas_model)
    click_button(integration_widget.integration_image_widget.mode_btn)

    click_button(integration_widget.img_mask_btn)
    assert dioptas_model.use_mask
    assert integration_widget.img_mask_btn.isChecked()
    click_button(integration_widget.img_mask_btn)
    assert not dioptas_model.use_mask
    assert not integration_widget.img_mask_btn.isChecked()


def test_adding_images(integration_widget, image_controller):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
        return_value=[os.path.join(unittest_data_path, "image_001.tif")]
    )
    click_button(integration_widget.load_img_btn)
    data1 = np.copy(integration_widget.img_widget.img_data).astype(np.uint32)
    click_checkbox(integration_widget.img_batch_mode_add_rb)
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
        return_value=[
            os.path.join(unittest_data_path, "image_001.tif"),
            os.path.join(unittest_data_path, "image_001.tif"),
        ]
    )
    click_button(integration_widget.load_img_btn)
    assert np.array_equal(2 * data1, integration_widget.img_widget.img_data)


def test_load_image_with_manual_input_file_name(
    integration_widget, dioptas_model, image_controller
):
    file_name = os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.tif")
    integration_widget.img_filename_txt.setText(file_name)
    image_controller.filename_txt_changed()  # need to manually trigger the text change
    old_data = np.copy(dioptas_model.img_data)

    file_name = os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif")
    integration_widget.img_filename_txt.setText(file_name)
    image_controller.filename_txt_changed()
    new_data = dioptas_model.img_data

    assert not np.array_equal(old_data, new_data)


def test_changing_cake_integral_width(
    integration_widget, dioptas_model, image_controller
):
    load_pilatus1M_image_and_calibration(dioptas_model)
    click_button(integration_widget.integration_image_widget.mode_btn)
    image_controller.img_mouse_click(100, 300)

    x = integration_widget.cake_widget.cake_integral_item.xData
    integration_widget.integration_control_widget.integration_options_widget.cake_integral_width_sb.setValue(
        3
    )
    image_controller.img_mouse_click(100, 300)

    assert not np.array_equal(
        x, integration_widget.cake_widget.cake_integral_item.xData
    )


def test_clicking_cake_image(integration_widget, dioptas_model, image_controller):
    load_pilatus1M_image_and_calibration(dioptas_model)
    click_button(integration_widget.integration_image_widget.mode_btn)
    integration_widget.integration_image_widget.cake_view.mouse_left_clicked.emit(
        30, 40
    )


def test_click_image_sends_tth_changed_signal(
    integration_widget, dioptas_model, image_controller
):
    load_pilatus1M_image_and_calibration(dioptas_model)
    dioptas_model.clicked_tth_changed.emit = MagicMock()
    integration_widget.integration_image_widget.img_view.mouse_left_clicked.emit(
        600, 400
    )
    dioptas_model.clicked_tth_changed.emit.assert_called()


def test_click_cake_sends_tth_changed_signal(
    integration_widget, dioptas_model, image_controller
):
    load_pilatus1M_image_and_calibration(dioptas_model)
    dioptas_model.clicked_tth_changed.emit = MagicMock()
    click_button(integration_widget.integration_image_widget.mode_btn)
    integration_widget.integration_image_widget.cake_view.mouse_left_clicked.emit(
        1100, 50
    )
    dioptas_model.clicked_tth_changed.emit.assert_called_once_with(
        get_partial_value(dioptas_model.cake_tth, 1100 - 0.5)
    )


def test_clicked_tth_changed(integration_widget, dioptas_model, image_controller):
    load_pilatus1M_image_and_calibration(dioptas_model)
    integration_widget.integration_image_widget.img_view.mouse_left_clicked.emit(
        600, 400
    )
    before_circle_data = (
        integration_widget.integration_image_widget.img_view.circle_plot_items[
            0
        ].getData()
    )
    dioptas_model.clicked_tth_changed.emit(10)
    after_circle_data = (
        integration_widget.integration_image_widget.img_view.circle_plot_items[
            0
        ].getData()
    )
    assert not np.array_equal(before_circle_data, after_circle_data)


def test_circle_scatter_is_activated_correctly(
    integration_widget, dioptas_model, image_controller
):
    dioptas_model.clicked_tth_changed.emit(10)
    assert not (
        integration_widget.integration_image_widget.img_view.circle_plot_items[0]
        in integration_widget.img_widget.img_view_box.addedItems
    )

    load_pilatus1M_image_and_calibration(dioptas_model)
    dioptas_model.clicked_tth_changed.emit(10)
    assert (
        integration_widget.integration_image_widget.img_view.circle_plot_items[0]
        in integration_widget.img_widget.img_view_box.addedItems
    )


def test_loading_series_karabo_file_shows_correct_gui(
    integration_widget, dioptas_model, image_controller
):
    from dioptas.model.loader.KaraboLoader import karabo_installed

    if not karabo_installed:
        return
    filename = os.path.join(unittest_data_path, "karabo_epix.h5")
    file_widget = (
        integration_widget.integration_control_widget.img_control_widget.file_widget
    )
    integration_widget.show()
    assert not file_widget.step_series_widget.isVisible()
    dioptas_model.img_model.load(filename)
    assert file_widget.step_series_widget.isVisible()


def test_fileinfo_and_move_button_visibility(
    integration_widget, dioptas_model, image_controller
):
    filename = os.path.join(unittest_data_path, "image_001.tif")
    integration_widget.show()
    dioptas_model.img_model.load(filename)
    assert not integration_widget.file_info_btn.isVisible()

    filename = os.path.join(unittest_data_path, "TransferCorrection", "original.tif")
    dioptas_model.img_model.load(filename)
    assert integration_widget.file_info_btn.isVisible()


def test_sources_for_hdf5_files(integration_widget, dioptas_model, image_controller):
    file_widget = (
        integration_widget.integration_control_widget.img_control_widget.file_widget
    )
    integration_widget.show()
    assert not file_widget.sources_widget.isVisible()

    # load file with different sources
    filename = os.path.join(unittest_data_path, "hdf5_dataset", "ma4500_demoh5.h5")
    dioptas_model.img_model.load(filename)
    assert file_widget.sources_widget.isVisible()

    # load file without sources
    filename = os.path.join(unittest_data_path, "image_001.tif")
    dioptas_model.img_model.load(filename)
    assert not file_widget.sources_widget.isVisible()


def test_sources_are_updated_in_sources_combobox(
    integration_widget, dioptas_model, image_controller
):
    file_widget = (
        integration_widget.integration_control_widget.img_control_widget.file_widget
    )
    filename = os.path.join(unittest_data_path, "hdf5_dataset", "ma4500_demoh5.h5")
    dioptas_model.img_model.load(filename)

    assert file_widget.sources_cb.count() > 0
    assert file_widget.sources_cb.count() == len(dioptas_model.img_model.sources)

    file_widget.sources_cb.setCurrentIndex(2)
    assert file_widget.sources_cb.currentText() == dioptas_model.img_model.sources[2]


def load_pilatus1M_image_and_calibration(dioptas_model: DioptasModel):
    file_name = os.path.join(unittest_data_path, "CeO2_Pilatus1M.tif")
    dioptas_model.img_model.load(file_name)
    calibration_file_name = os.path.join(unittest_data_path, "CeO2_Pilatus1M.poni")
    dioptas_model.calibration_model.load(calibration_file_name)
