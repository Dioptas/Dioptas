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
from pytest import approx

from qtpy import QtCore, QtWidgets
from mock import MagicMock
from ..utility import click_button

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")


def mock_open_filename(filepath):
    QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[filepath])
    QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=filepath)


def test_synchronization_of_view_range(main_controller):
    # Herbert opens the loads an image and zooms into a certain area,
    # then he switches to mask mode and sees the same area in the mask view.
    mock_open_filename(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    click_button(main_controller.widget.calibration_mode_btn)
    click_button(main_controller.widget.calibration_widget.load_img_btn)

    calibration_img_vb = (
        main_controller.widget.calibration_widget.img_widget.img_view_box
    )
    mask_img_vb = main_controller.widget.mask_widget.img_widget.img_view_box
    integration_img_vb = (
        main_controller.widget.integration_widget.img_widget.img_view_box
    )
    map_img_vb = main_controller.widget.map_widget.img_plot_widget.img_view_box

    calibration_img_vb.setRange(QtCore.QRectF(-10, -10, 20, 20))
    click_button(main_controller.widget.mask_mode_btn)

    range_diff = np.sum(
        np.array(calibration_img_vb.targetRange()) - np.array(mask_img_vb.targetRange())
    )

    assert range_diff == approx(0)

    # Herbert zooms into a different area in the mask view and sees the same area in the calibration view.

    mask_img_vb.setRange(QtCore.QRectF(100, 100, 300, 300))
    click_button(main_controller.widget.calibration_mode_btn)

    range_diff = np.sum(
        np.array(calibration_img_vb.targetRange()) - np.array(mask_img_vb.targetRange())
    )

    assert range_diff == approx(0)

    # HE also goes to the integration view and observes the same a similar range there.
    click_button(main_controller.widget.integration_mode_btn)

    range_diff = np.sum(
        np.array(calibration_img_vb.targetRange())
        - np.array(integration_img_vb.targetRange())
    )

    assert range_diff == approx(0)

    # then he checks the map view and see that the range is also the same there.
    click_button(main_controller.widget.map_mode_btn)
    range_diff = np.sum(
        np.array(calibration_img_vb.targetRange()) - np.array(map_img_vb.targetRange())
    )

    assert range_diff == approx(0)

    # He zooms out of the image in the map view and sees that the range is also the same in the other views.
    map_img_vb.setRange(QtCore.QRectF(-10, -10, 20, 20))

    click_button(main_controller.widget.calibration_mode_btn)
    range_diff = np.sum(
        np.array(calibration_img_vb.targetRange()) - np.array(map_img_vb.targetRange())
    )

    assert range_diff == approx(0)


def test_remove_img_background_in_view(main_controller):
    # Herbert opens an image in the integration view and wants to remove the background signal.
    mock_open_filename(os.path.join(data_path, "image_001.tif"))
    click_button(main_controller.widget.integration_mode_btn)
    click_button(main_controller.widget.integration_widget.load_img_btn)

    integration_widget = main_controller.widget.integration_widget
    image_widget = integration_widget.img_widget

    data_before_bg = image_widget.data_img_item.image.copy()

    # He clicks the background subtraction button and sees that the image does not change and wonders why.
    integration_widget.integration_control_widget.tab_widget_1.setCurrentIndex(5)
    mock_open_filename(os.path.join(data_path, "image_002.tif"))
    click_button(
        integration_widget.integration_control_widget.background_control_widget.load_image_btn
    )
    assert (
        integration_widget.integration_control_widget.background_control_widget.filename_lbl.text()
        == "image_002.tif"
    )

    data_after_bg = image_widget.data_img_item.image.copy()
    assert np.array_equal(data_before_bg, data_after_bg)

    # He realizes that there is s a show background subtraction button and clicks it.
    # With satisfaction he sees the background subtracted image
    click_button(
        integration_widget.integration_image_widget.show_background_subtracted_img_btn
    )
    assert (
        integration_widget.integration_image_widget.show_background_subtracted_img_btn.isChecked()
    )
    data_before_bg = image_widget.data_img_item.image.copy()
    assert not np.array_equal(data_before_bg, data_after_bg)
