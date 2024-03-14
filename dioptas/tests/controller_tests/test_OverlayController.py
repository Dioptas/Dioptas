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

from ..utility import QtTest, click_button, click_checkbox
import pytest
import os
import gc
from mock import MagicMock

import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtTest import QTest

from ...controller.integration import OverlayController
from ...model.DioptasModel import DioptasModel
from ...model.OverlayModel import OverlayModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


@pytest.fixture
def overlay_controller(
    integration_widget: IntegrationWidget, dioptas_model: DioptasModel
) -> OverlayController:
    return OverlayController(integration_widget, dioptas_model)


def load_overlays(overlay_model: OverlayModel):
    for i in range(6):
        overlay_model.add_overlay(np.arange(10), np.arange(10), "Overlay {}".format(i))


def test_add_overlays(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    load_overlays(dioptas_model.overlay_model)

    overlay_tw = integration_widget.overlay_widget.overlay_tw

    assert overlay_tw.rowCount() == 6
    assert len(dioptas_model.overlay_model.overlays) == 6
    assert overlay_tw.currentRow() == 5


def test_delete_overlays(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    load_overlays(dioptas_model.overlay_model)

    overlay_tw = integration_widget.overlay_widget.overlay_tw
    overlay_widget = integration_widget.overlay_widget

    overlay_controller.delete_btn_click_callback()

    assert overlay_tw.rowCount() == 5
    assert len(dioptas_model.overlay_model.overlays) == 5
    assert overlay_tw.currentRow() == 4

    overlay_widget.select_overlay(1)
    overlay_controller.delete_btn_click_callback()

    assert overlay_tw.rowCount() == 4
    assert len(dioptas_model.overlay_model.overlays) == 4
    assert overlay_tw.currentRow() == 1

    tw_filenames = [overlay_tw.item(i, 2).text() for i in range(4)]
    assert tw_filenames[1] == "Overlay 2"

    for _ in range(4):
        click_button(overlay_widget.delete_btn)

    assert overlay_tw.rowCount() == 0
    assert len(dioptas_model.overlay_model.overlays) == 0
    assert overlay_tw.currentRow() == -1

    click_button(overlay_widget.delete_btn)
    assert overlay_tw.rowCount() == 0
    assert len(dioptas_model.overlay_model.overlays) == 0
    assert overlay_tw.currentRow() == -1


def test_clear_overlays(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    load_overlays(dioptas_model.overlay_model)

    overlay_tw = integration_widget.overlay_widget.overlay_tw
    overlay_widget = integration_widget.overlay_widget

    click_button(overlay_widget.clear_btn)

    assert overlay_tw.rowCount() == 0
    assert len(dioptas_model.overlay_model.overlays) == 0
    assert overlay_tw.currentRow() == -1


def test_change_scaling_in_view(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    load_overlays(dioptas_model.overlay_model)
    overlay_widget = integration_widget.overlay_widget
    for ind in [0, 3, 4]:
        overlay_widget.scale_sbs[ind].setValue(2.0)
        assert dioptas_model.overlay_model.get_overlay_scaling(ind) == 2


def test_change_offset_in_view(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    load_overlays(dioptas_model.overlay_model)
    overlay_widget = integration_widget.overlay_widget
    for ind in [0, 3, 4]:
        overlay_widget.offset_sbs[ind].setValue(100)
        assert dioptas_model.overlay_model.get_overlay_offset(ind) == 100


def test_scaling_auto_step_change(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    load_overlays(dioptas_model.overlay_model)
    overlay_widget = integration_widget.overlay_widget

    overlay_widget.scale_step_msb.setValue(0.5)
    overlay_widget.scale_step_msb.stepUp()

    new_scale_step = overlay_widget.scale_step_msb.value()
    assert new_scale_step == pytest.approx(1.0)

    overlay_widget.scale_step_msb.stepDown()
    overlay_widget.scale_step_msb.stepDown()
    new_scale_step = overlay_widget.scale_step_msb.value()
    assert new_scale_step == pytest.approx(0.2)


def test_scalestep_spinbox_changes_scale_spinboxes(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    for ind in range(6):
        assert integration_widget.overlay_widget.scale_sbs[ind].singleStep() == 0.01

    new_step = 5
    overlay_widget.scale_step_msb.setValue(new_step)
    for ind in range(6):
        assert integration_widget.overlay_widget.scale_sbs[ind].singleStep() == new_step


def test_offset_spinbox_changes_offset_spinboxes(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    for ind in range(6):
        assert overlay_widget.offset_sbs[ind].singleStep() == 100

    new_step = 5
    overlay_widget.offset_step_msb.setValue(new_step)
    for ind in range(6):
        assert overlay_widget.offset_sbs[ind].singleStep() == new_step


def test_offset_auto_step_change(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    overlay_widget.offset_step_msb.setValue(10.0)
    overlay_widget.offset_step_msb.stepUp()

    new_offset_step = overlay_widget.offset_step_msb.value()
    assert new_offset_step == pytest.approx(20.0)

    overlay_widget.offset_step_msb.stepDown()
    overlay_widget.offset_step_msb.stepDown()
    new_offset_step = overlay_widget.offset_step_msb.value()
    assert new_offset_step == pytest.approx(5.0)


def test_setting_overlay_as_bkg(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    dioptas_model.pattern_model.set_pattern(np.arange(10), np.arange(10))
    overlay_widget.select_overlay(0)

    click_button(integration_widget.overlay_set_as_bkg_btn)

    assert integration_widget.overlay_set_as_bkg_btn.isChecked()
    assert np.array_equal(
        dioptas_model.pattern_model.background_pattern,
        dioptas_model.overlay_model.overlays[0],
    )
    _, y = dioptas_model.pattern.data
    assert np.sum(y) == 0


def test_setting_overlay_as_bkg_and_changing_scale(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    dioptas_model.pattern_model.set_pattern(np.arange(10), np.arange(10))
    overlay_widget.select_overlay(0)

    click_button(integration_widget.overlay_set_as_bkg_btn)

    overlay_widget.scale_sbs[0].setValue(2)

    _, y = dioptas_model.pattern.data
    assert np.array_equal(y, -np.arange(10))


def test_setting_overlay_as_bkg_and_changing_offset(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)

    dioptas_model.pattern_model.set_pattern(np.arange(10), np.arange(10))
    overlay_widget.select_overlay(0)

    click_button(integration_widget.overlay_set_as_bkg_btn)

    overlay_widget.offset_sbs[0].setValue(100)
    _, y = dioptas_model.pattern.data
    assert np.sum(y) == -100 * y.size


def test_setting_overlay_as_bkg_and_then_change_to_new_overlay_as_bkg(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    dioptas_model.pattern_model.set_pattern(np.arange(10), np.arange(10))
    overlay_widget.select_overlay(0)

    click_button(integration_widget.overlay_set_as_bkg_btn)

    assert integration_widget.overlay_set_as_bkg_btn.isChecked()
    assert (
        dioptas_model.pattern.background_pattern is
        dioptas_model.overlay_model.overlays[0]
    )
    _, y = dioptas_model.pattern.data
    assert np.sum(y) == 0

    overlay_widget.select_overlay(1)
    assert not integration_widget.overlay_set_as_bkg_btn.isChecked()
    overlay_widget.scale_sbs[1].setValue(2)
    click_button(integration_widget.overlay_set_as_bkg_btn)

    assert (
        dioptas_model.pattern.background_pattern is
        dioptas_model.overlay_model.overlays[1]
    )
    _, y = dioptas_model.pattern.data
    assert np.array_equal(y, -np.arange(10))


def test_setting_pattern_as_bkg(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    dioptas_model.pattern_model.set_pattern(np.arange(10), np.arange(10))
    click_button(integration_widget.qa_set_as_background_btn)

    assert integration_widget.overlay_set_as_bkg_btn.isChecked()
    assert len(dioptas_model.overlay_model.overlays) == 1

    _, y = dioptas_model.pattern.data
    assert np.sum(y) == 0


def test_having_overlay_as_bkg_and_deleting_it(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    dioptas_model.pattern_model.set_pattern(np.arange(10), np.arange(10))
    click_button(integration_widget.qa_set_as_background_btn)

    assert dioptas_model.pattern_model.background_pattern is not None
    assert len(dioptas_model.overlay_model.overlays) == 1

    click_button(integration_widget.overlay_del_btn)

    assert not integration_widget.overlay_set_as_bkg_btn.isChecked()
    assert integration_widget.overlay_tw.rowCount() == 0
    assert len(dioptas_model.overlay_model.overlays) == 0

    _, y = dioptas_model.pattern.data
    assert np.sum(y) != 0


def test_overlay_waterfall(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    overlay_widget.waterfall_separation_msb.setValue(10)
    click_button(overlay_widget.waterfall_btn)

    assert dioptas_model.overlay_model.overlays[5].offset == -10
    assert dioptas_model.overlay_model.overlays[4].offset == -20

    click_button(integration_widget.reset_waterfall_btn)

    assert dioptas_model.overlay_model.overlays[5].offset == 0
    assert dioptas_model.overlay_model.overlays[5].offset == 0


def test_move_single_overlay_one_step_up(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_model = dioptas_model.overlay_model
    load_overlays(dioptas_model.overlay_model)
    integration_widget.overlay_tw.selectRow(3)

    assert integration_widget.overlay_tw.item(3, 2).text() == "Overlay 3"
    assert overlay_model.overlays[2].name == "Overlay 2"

    new_name = "special"
    overlay_model.set_overlay_name(3, new_name)
    assert overlay_model.overlays[3].name == new_name
    assert integration_widget.overlay_tw.item(3, 2).text() == new_name

    click_button(integration_widget.overlay_move_up_btn)

    assert dioptas_model.overlay_model.overlays[2].name == new_name
    assert integration_widget.overlay_tw.item(2, 2).text() == new_name
    assert dioptas_model.overlay_model.overlays[3].name == "Overlay 2"
    assert integration_widget.overlay_tw.item(3, 2).text() == "Overlay 2"

    # selected row should also move
    assert integration_widget.overlay_tw.currentRow() == 2


def test_move_single_overlay_one_step_down(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_model = dioptas_model.overlay_model
    load_overlays(dioptas_model.overlay_model)
    integration_widget.overlay_tw.selectRow(3)

    assert integration_widget.overlay_tw.item(3, 2).text() == "Overlay 3"
    assert overlay_model.overlays[2].name == "Overlay 2"

    new_name = "special"
    overlay_model.set_overlay_name(3, new_name)
    assert overlay_model.overlays[3].name == new_name
    assert integration_widget.overlay_tw.item(3, 2).text() == new_name

    click_button(integration_widget.overlay_move_down_btn)

    assert dioptas_model.overlay_model.overlays[4].name == new_name
    assert integration_widget.overlay_tw.item(4, 2).text() == new_name
    assert dioptas_model.overlay_model.overlays[3].name == "Overlay 4"
    assert integration_widget.overlay_tw.item(3, 2).text() == "Overlay 4"

    # selected row should also move
    assert integration_widget.overlay_tw.currentRow() == 4


def test_bulk_change_visibility_of_overlays(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    for cb in overlay_widget.show_cbs:
        assert cb.isChecked()

    overlay_controller.overlay_tw_header_section_clicked(0)
    for cb in overlay_widget.show_cbs:
        assert not cb.isChecked()

    for overlay in dioptas_model.overlay_model.overlays:
        assert not overlay.visible

    click_checkbox(overlay_widget.show_cbs[1])
    overlay_controller.overlay_tw_header_section_clicked(0)
    for cb in overlay_widget.show_cbs:
        assert not cb.isChecked()

    overlay_controller.overlay_tw_header_section_clicked(0)
    for cb in overlay_widget.show_cbs:
        assert cb.isChecked()

    for overlay in dioptas_model.overlay_model.overlays:
        assert overlay.visible


def test_change_overlay_color(
    overlay_controller: OverlayController,
    integration_widget: IntegrationWidget,
    dioptas_model: DioptasModel,
):
    overlay_widget = integration_widget.overlay_widget
    load_overlays(dioptas_model.overlay_model)
    color1 = overlay_widget.color_btns[1].palette().color(QtGui.QPalette.Button)
    QtWidgets.QColorDialog.getColor = MagicMock(return_value=color1)

    click_button(overlay_widget.color_btns[3])

    assert dioptas_model.overlay_model.overlays[3].color == color1.name()
    assert overlay_widget.color_btns[3].palette().color(QtGui.QPalette.Button) == color1
