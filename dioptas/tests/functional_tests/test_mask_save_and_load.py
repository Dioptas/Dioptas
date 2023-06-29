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

import os.path
from unittest.mock import MagicMock

import fabio
import numpy as np
import pytest
from PIL import Image
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ..utility import click_button, unittest_data_path
from ...controller.MainController import MainController
from ...controller.MaskController import MaskController


@pytest.fixture(scope="session")
def qapp():
    """Fixture ensuring QApplication is instanciated"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    try:
        yield app
    finally:
        if app is not None:
            app.closeAllWindows()


@pytest.fixture
def main_controller(qapp):
    """Fixture providing a MainController instance"""
    controller = MainController(use_settings=False)
    controller.show_window()
    controller.widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    QTest.qWaitForWindowExposed(controller.widget)
    controller.widget.activateWindow()
    controller.widget.raise_()
    try:
        yield controller
    finally:
        controller.widget.close()


def load_image_and_mask(
    main_controller: MainController,
    img_filename: str,
    mask_filename: str,
    dialog_filter: str,
):
    """Sequence: Load image and mask from file and save the mask to file

    dialog_filter is the format option selected in the mask controller load/save dialogs.
    """
    # Load image
    click_button(main_controller.widget.calibration_mode_btn)
    QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=img_filename)
    click_button(main_controller.widget.calibration_widget.load_img_btn)

    # Create mask file
    ref_mask = np.zeros(main_controller.model.mask_model.mask_dimension, dtype=np.int8)
    ref_mask[:100, :200] = 1
    if mask_filename.endswith(".npy"):
        np.save(mask_filename, ref_mask)
    elif mask_filename.endswith(".edf"):
        fabio.edfimage.EdfImage(ref_mask).write(mask_filename)
    else:
        Image.fromarray(ref_mask).save(mask_filename, "tiff")

    # Load mask
    click_button(main_controller.widget.mask_mode_btn)
    QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=(mask_filename, dialog_filter))
    click_button(main_controller.mask_controller.widget.load_mask_btn)

    current_mask = main_controller.model.mask_model.get_mask()
    if dialog_filter == MaskController.FLIPUD_MASK_FILTER:
        assert np.array_equal(np.flipud(ref_mask), current_mask)
    else:
        assert np.array_equal(ref_mask, current_mask)

    # Save mask
    QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=(mask_filename, dialog_filter))
    click_button(main_controller.mask_controller.widget.save_mask_btn)
    assert os.path.isfile(mask_filename)

    if mask_filename.endswith(".npy"):
        saved_mask = np.load(mask_filename)
    elif mask_filename.endswith(".edf"):
        saved_mask = fabio.open(mask_filename).data
    else:
        saved_mask = np.array(Image.open(mask_filename))
    assert np.array_equal(ref_mask, saved_mask)


@pytest.mark.parametrize("img_filename", [
    "lambda/testasapo1_1009_00002_m1_part00000.nxs",
    "spe/CeO2_PI_CCD_Mo.SPE",
    "image_001.tif",
    "karabo_epix.h5",
])
def test_load_save_mask_as_tiff(main_controller, tmp_path, img_filename):
    """Test *.mask mask load/save"""
    load_image_and_mask(
        main_controller,
        os.path.join(unittest_data_path, img_filename),
        str(tmp_path / "ref_mask.mask"),
        dialog_filter=MaskController.DEFAULT_MASK_FILTER,
    )


@pytest.mark.parametrize("mask_ext", [".npy", ".edf"])
@pytest.mark.parametrize("img_filename", [
    "lambda/testasapo1_1009_00002_m1_part00000.nxs",
    "spe/CeO2_PI_CCD_Mo.SPE",
    "image_001.tif",
    "karabo_epix.h5",
])
def test_load_save_flipped_mask(main_controller, tmp_path, img_filename, mask_ext):
    """Test load/save flipped mask"""
    load_image_and_mask(
        main_controller,
        os.path.join(unittest_data_path, img_filename),
        str(tmp_path / f"ref_mask{mask_ext}"),
        dialog_filter=MaskController.FLIPUD_MASK_FILTER
    )
