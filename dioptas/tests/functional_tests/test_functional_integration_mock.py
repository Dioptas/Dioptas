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
import pytest
import os
from mock import MagicMock

from qtpy import QtWidgets, QtCore

from dioptas.tests.utility import enter_value_into_text_field, QtTest, click_button
from dioptas.model.util.Pattern import Pattern

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')


@pytest.fixture
def mock_integration(dioptas_model):
    pattern = Pattern().load(os.path.join(data_path, 'CeO2_Pilatus1M.xy'))
    dioptas_model.calibration_model.integrate_1d = MagicMock(return_value=(pattern.x, pattern.y))
    dioptas_model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
    dioptas_model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))


def test_1D_integration_with_azimuth_limits(integration_controller, integration_widget, dioptas_model,
                                            mock_integration):
    # Edith wants to perform 1D integration within a certain range of azimuthal angles. She sees there is an option
    # in the X tab and deselects the Full Range button, enabling the text edits and then manually inputs -100, 80
    assert not integration_widget.oned_azimuth_min_txt.isEnabled()
    assert not integration_widget.oned_azimuth_max_txt.isEnabled()
    integration_widget.oned_full_range_btn.setChecked(False)
    assert integration_widget.oned_azimuth_min_txt.isEnabled()
    assert integration_widget.oned_azimuth_max_txt.isEnabled()

    enter_value_into_text_field(integration_widget.oned_azimuth_min_txt, -100)
    enter_value_into_text_field(integration_widget.oned_azimuth_max_txt, 80)

    dioptas_model.calibration_model.integrate_1d.assert_called_with(mask=None, num_points=None, unit='2th_deg',
                                                                    azi_range=(-100, 80))


def test_changing_number_of_integration_bins(integration_controller, integration_widget, dioptas_model,
                                             mock_integration):
    # Edith wants to change the number of integration bins in order to see the effect of binning onto her line
    # shape. She sees that there is an option in the X tab and deselects automatic and sees that the spinbox
    # becomes editable.
    assert not integration_widget.bin_count_txt.isEnabled()
    integration_widget.automatic_binning_cb.setChecked(False)
    assert integration_widget.bin_count_txt.isEnabled()

    # she sees that the current value and wants to double it and notices that the pattern looks a little bit
    # smoother
    previous_number_of_points = len(dioptas_model.pattern.x)
    enter_value_into_text_field(integration_widget.bin_count_txt, 2 * previous_number_of_points)

    dioptas_model.calibration_model.integrate_1d.assert_called_with(num_points=2 * previous_number_of_points,
                                                                    azi_range=None, mask=None, unit='2th_deg')

    # then she decides that having an automatic estimation may probably be better and changes back to automatic.
    # immediately the number is restored and the image looks like when she started
    integration_widget.automatic_binning_cb.setChecked(True)
    dioptas_model.calibration_model.integrate_1d.assert_called_with(num_points=None, azi_range=None,
                                                                    mask=None, unit='2th_deg')


def test_changing_supersampling_amount_integrating_to_cake_with_mask(integration_controller, integration_widget,
                                                                     dioptas_model, mock_integration):
    # Edith opens the program, calibrates everything and looks in to the options menu. She sees that there is a
    # miraculous parameter called supersampling. It is currently set to 1 which seems to be normal
    assert integration_widget.supersampling_sb.value() == 1

    # then she sets it to two and she sees that the number of pattern bin changes and that the pattern looks
    # smoother

    # values before:
    px1 = dioptas_model.calibration_model.pattern_geometry.pixel1
    px2 = dioptas_model.calibration_model.pattern_geometry.pixel2

    integration_widget.supersampling_sb.setValue(2)
    assert dioptas_model.calibration_model.pattern_geometry.pixel1 == 0.5 * px1
    assert dioptas_model.calibration_model.pattern_geometry.pixel2 == 0.5 * px2
    assert dioptas_model.calibration_model.cake_geometry.pixel1 == 0.5 * px1
    assert dioptas_model.calibration_model.cake_geometry.pixel2 == 0.5 * px2


def test_saving_image(integration_controller, integration_widget, dioptas_model, mock_integration, tmpdir):
    # the widget has to be shown to be able to save the image:
    integration_widget.show()
    # Tests if the image save procedures are working for the different possible file endings
    QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(tmpdir, 'Test_img.png'))
    click_button(integration_widget.qa_save_img_btn)
    QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=os.path.join(tmpdir, 'Test_img.tiff'))
    click_button(integration_widget.qa_save_img_btn)

    assert os.path.exists(os.path.join(tmpdir, 'Test_img.png'))
    assert os.path.exists(os.path.join(tmpdir, 'Test_img.tiff'))


@pytest.mark.parametrize("integration_variable", ["2th", "q", "d"])
def test_saving_pattern(integration_controller, integration_widget, dioptas_model, mock_integration, tmpdir,
                        integration_variable):
    # the widget has to be shown to be able to save the image:
    integration_widget.show()
    pattern_controller = integration_controller.pattern_controller

    if integration_variable == "d":
        click_button(pattern_controller.widget.pattern_d_btn)
    elif integration_variable == "q":
        click_button(pattern_controller.widget.pattern_q_btn)

    def save_pattern(filename):
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filename)
        click_button(integration_widget.qa_save_pattern_btn)

    for file_format in ("xy", "chi", "dat", "png"):  # SVG does not work currently
        filename = os.path.join(tmpdir, "test_pattern." + file_format)
        save_pattern(filename)
        assert os.path.exists(filename)
        assert os.stat(filename).st_size > 1
