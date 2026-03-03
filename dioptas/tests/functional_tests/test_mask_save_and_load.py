# SPDX-License-Identifier: MIT

import os.path
from unittest.mock import MagicMock

import fabio
import numpy as np
import pytest
from PIL import Image
from qtpy import QtWidgets

from ..utility import click_button, unittest_data_path
from ...controller.MainController import MainController
from ...controller.MaskController import MaskController


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
    QtWidgets.QFileDialog.getOpenFileName = MagicMock(
        return_value=(mask_filename, dialog_filter)
    )
    click_button(main_controller.mask_controller.widget.load_mask_btn)

    current_mask = main_controller.model.mask_model.get_mask()
    if dialog_filter.startswith(MaskController.FLIPUD_MASK_FILTER_PREFIX):
        assert np.array_equal(np.flipud(ref_mask), current_mask)
    else:
        assert np.array_equal(ref_mask, current_mask)

    # Save mask
    QtWidgets.QFileDialog.getSaveFileName = MagicMock(
        return_value=(mask_filename, dialog_filter)
    )
    click_button(main_controller.mask_controller.widget.save_mask_btn)
    assert os.path.isfile(mask_filename)

    if mask_filename.endswith(".npy"):
        saved_mask = np.load(mask_filename)
    elif mask_filename.endswith(".edf"):
        saved_mask = fabio.open(mask_filename).data
    else:
        saved_mask = np.array(Image.open(mask_filename))
    assert np.array_equal(ref_mask, saved_mask)


@pytest.mark.parametrize(
    "img_filename",
    [
        "lambda/testasapo1_1009_00002_m1_part00000.nxs",
        "spe/CeO2_PI_CCD_Mo.SPE",
        "image_001.tif",
        "karabo_epix.h5",
    ],
)
def test_load_save_mask_as_tiff(main_controller, tmp_path, img_filename):
    """Test *.mask mask load/save"""
    load_image_and_mask(
        main_controller,
        os.path.join(unittest_data_path, img_filename),
        str(tmp_path / "ref_mask.mask"),
        dialog_filter=MaskController.DEFAULT_MASK_FILTER,
    )


@pytest.mark.parametrize(
    "img_filename",
    [
        "lambda/testasapo1_1009_00002_m1_part00000.nxs",
        "spe/CeO2_PI_CCD_Mo.SPE",
        "image_001.tif",
        "karabo_epix.h5",
    ],
)
def test_load_save_flipped_mask_as_npy(main_controller, tmp_path, img_filename):
    """Test load/save flipped mask as npy"""
    load_image_and_mask(
        main_controller,
        os.path.join(unittest_data_path, img_filename),
        str(tmp_path / "ref_mask.npy"),
        dialog_filter=f"{MaskController.FLIPUD_MASK_FILTER_PREFIX} (*.npy)",
    )


@pytest.mark.parametrize(
    "img_filename",
    [
        "lambda/testasapo1_1009_00002_m1_part00000.nxs",
        "spe/CeO2_PI_CCD_Mo.SPE",
        "image_001.tif",
        "karabo_epix.h5",
    ],
)
def test_load_save_flipped_mask_as_edf(main_controller, tmp_path, img_filename):
    """Test load/save flipped mask as edf"""
    load_image_and_mask(
        main_controller,
        os.path.join(unittest_data_path, img_filename),
        str(tmp_path / "ref_mask.edf"),
        dialog_filter=f"{MaskController.FLIPUD_MASK_FILTER_PREFIX} (*.edf)",
    )
