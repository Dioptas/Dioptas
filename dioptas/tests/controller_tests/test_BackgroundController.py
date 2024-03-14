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
import pytest
from mock import MagicMock

from qtpy import QtWidgets

from ..utility import unittest_data_path, click_button


def test_configuration_selected_changes_background_image_widgets(
    background_controller, integration_widget, dioptas_model, qtbot
):
    widget = integration_widget
    model = dioptas_model

    model.img_model.load(os.path.join(unittest_data_path, "image_001.tif"))
    model.img_model.load_background(os.path.join(unittest_data_path, "image_001.tif"))

    model.add_configuration()
    model.img_model.load(os.path.join(unittest_data_path, "image_001.tif"))
    model.img_model.load_background(os.path.join(unittest_data_path, "image_002.tif"))

    assert str(widget.bkg_image_filename_lbl.text()) == "image_002.tif"

    model.select_configuration(0)
    assert str(widget.bkg_image_filename_lbl.text()) == "image_001.tif"

    widget.bkg_image_offset_sb.setValue(100)
    model.select_configuration(1)
    assert widget.bkg_image_offset_sb.value() == 0

    widget.bkg_image_scale_sb.setValue(2)
    model.select_configuration(0)
    assert widget.bkg_image_scale_sb.value() == 1


def test_configuration_selected_changes_auto_background_widgets(
    background_controller, pattern_controller, integration_widget, dioptas_model, qtbot
):
    widget = integration_widget
    model = dioptas_model

    model.pattern_model.load_pattern(
        os.path.join(unittest_data_path, "pattern_001.chi")
    )
    click_button(widget.qa_bkg_pattern_btn)
    assert widget.bkg_pattern_gb.isChecked()

    model.add_configuration()
    assert model.pattern_model.pattern.auto_bkg is None
    assert not widget.bkg_pattern_gb.isChecked()

    model.select_configuration(0)
    assert widget.bkg_pattern_gb.isChecked()
    click_button(widget.qa_bkg_pattern_inspect_btn)

    model.select_configuration(1)
    assert not widget.bkg_pattern_gb.isChecked()


def test_changing_unit(
    background_controller, pattern_controller, integration_widget, dioptas_model, qtbot
):
    widget = integration_widget
    model = dioptas_model

    model.calibration_model.load(
        os.path.join(unittest_data_path, "LaB6_40keV_MarCCD.poni")
    )
    model.img_model.load(os.path.join(unittest_data_path, "image_001.tif"))

    x_raw, y_raw = model.pattern_model.pattern.data
    click_button(widget.qa_bkg_pattern_btn)
    x_2th, y_2th = model.pattern_model.pattern.data

    assert np.sum(y_raw) != np.sum(y_2th)

    click_button(widget.pattern_q_btn)
    x_q, y_q = model.pattern_model.pattern.data
    x_q_bkg, y_q_bkg = model.pattern_model.pattern.auto_background_pattern.data

    assert np.max(x_q) < np.max(x_2th)
    assert x_q[0] == x_q_bkg[0]
    assert x_q[-1] == x_q_bkg[-1]


def test_save_fit_background_pattern(
    background_controller,
    pattern_controller,
    integration_widget,
    dioptas_model,
    qtbot,
    tmpdir,
):
    widget = integration_widget
    model = dioptas_model

    QtWidgets.QFileDialog.getSaveFileName = MagicMock(
        return_value=os.path.join(tmpdir, "test_bg.xy")
    )
    model.calibration_model.create_file_header = MagicMock(return_value="None")
    click_button(widget.qa_bkg_pattern_btn)
    click_button(widget.bkg_pattern_save_btn)
    assert os.path.exists(os.path.join(tmpdir, "test_bg.xy"))
