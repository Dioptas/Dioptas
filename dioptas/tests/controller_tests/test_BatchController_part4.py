# SPDX-License-Identifier: MIT

import os
import pytest
from mock import MagicMock
import numpy as np

from qtpy import QtWidgets
from xypattern import Pattern

from ...controller.integration import BatchController


def test_save_xy_without_background_subtraction(
    batch_controller: BatchController, tmp_path
):
    batch_controller.model.batch_model.data = np.ones((22, 1000))
    batch_controller.model.batch_model.binning = np.arange(1000)
    QtWidgets.QFileDialog.getSaveFileName = MagicMock(
        return_value=os.path.join(tmp_path, "test.xy")
    )
    batch_controller.save_data()

    for i in range(len(batch_controller.model.batch_model.data)):
        assert os.path.exists(os.path.join(tmp_path, f"test_{i:03d}.xy"))


def test_save_xy_with_background_subtraction(
    batch_controller: BatchController, tmp_path
):
    batch_controller.model.batch_model.data = np.ones((22, 1001))
    batch_controller.model.batch_model.binning = np.linspace(0, 10, 1001)
    batch_controller.model.pattern_model.set_auto_background_subtraction(
        parameters=[2, 50, 50], roi=[2, 8]
    )

    assert batch_controller.model.pattern_model.pattern.auto_bkg

    QtWidgets.QFileDialog.getSaveFileName = MagicMock(
        return_value=os.path.join(tmp_path, "test.xy")
    )
    batch_controller.save_data()

    # check that normal patterns are saved
    for i in range(len(batch_controller.model.batch_model.data)):
        assert os.path.exists(os.path.join(tmp_path, f"test_{i:03d}.xy"))

    bkg_subtracted_path = os.path.join(tmp_path, "bkg_subtracted")
    assert os.path.exists(bkg_subtracted_path)

    # check that background patterns are saved
    for i in range(len(batch_controller.model.batch_model.data)):
        assert os.path.exists(os.path.join(bkg_subtracted_path, f"test_{i:03d}.xy"))

    # check that background subtracted patterns are saved with the reduced range
    bkg_subtracted_pattern = Pattern()
    bkg_subtracted_pattern.load(os.path.join(bkg_subtracted_path, f"test_011.xy"))
    assert len(bkg_subtracted_pattern.x) == 599
    assert len(bkg_subtracted_pattern.y) == 599
    assert np.sum(bkg_subtracted_pattern.y) == pytest.approx(0, abs=1e-10)

    # check that originalfpytterns are saved with the full range
    pattern = Pattern()
    pattern.load(os.path.join(tmp_path, f"test_011.xy"))
    assert len(pattern.x) == 1001
    assert len(pattern.y) == 1001
