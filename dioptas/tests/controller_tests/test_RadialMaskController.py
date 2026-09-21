# SPDX-License-Identifier: MIT

import numpy as np
import pytest
from qtpy import QtWidgets

from dioptas.controller.MaskController import MaskController
from dioptas.model.DioptasModel import DioptasModel
from dioptas.widgets.MaskWidget import MaskWidget


@pytest.fixture
def radial_mask(qapp, qtbot):
    model = DioptasModel()
    model.img_model._img_data = np.zeros((40, 50))
    model.img_model.img_changed.emit()
    widget = MaskWidget()
    qtbot.addWidget(widget)
    controller = MaskController(widget, model)
    assert not widget.range_inside_btn.isEnabled()
    model.calibration_model.set_pyFAI({
        'dist': .02, 'poni1': .01, 'poni2': .015,
        'rot1': 0., 'rot2': 0., 'rot3': 0.,
        'pixel1': .001, 'pixel2': .001, 'wavelength': 1e-10,
        'polarization_factor': .99,
    })
    model.history.reset()
    return model, widget, controller


@pytest.mark.parametrize('unit, lower, upper', [
    ('2th_deg', 20., 40.), ('q_A^-1', 2., 4.), ('d_A', 1.5, 3.),
])
@pytest.mark.parametrize('outside', [False, True])
@pytest.mark.parametrize('supersampling', [1, 3])
def test_radial_mask_uses_calibrated_pixel_centers(
    radial_mask, unit, lower, upper, outside, supersampling,
):
    model, widget, controller = radial_mask
    model.calibration_model.set_supersampling(supersampling)
    widget.range_unit_cb.setCurrentIndex(widget.range_unit_cb.findData(unit))
    widget.range_min_txt.setText(str(lower))
    widget.range_max_txt.setText(str(upper))
    # Independent geometry calculation for this untilted detector.
    rows, columns = np.indices((40, 50))
    radius = np.hypot((rows + .5) * .001 - .01, (columns + .5) * .001 - .015)
    tth = np.arctan2(radius, .02)
    radial = {
        '2th_deg': np.rad2deg(tth),
        'q_A^-1': 4 * np.pi * np.sin(tth / 2),
        'd_A': 1 / (2 * np.sin(tth / 2)),
    }[unit]
    expected = (radial >= lower) & (radial <= upper)
    if outside:
        expected = ~expected
    assert expected.any() and not expected.all()
    model.history.reset()
    button = widget.range_outside_btn if outside else widget.range_inside_btn
    button.click()
    np.testing.assert_array_equal(model.mask_model.get_img(), expected)
    assert model.history.undo()
    assert not model.mask_model.get_img().any()
    assert model.history.redo()
    np.testing.assert_array_equal(model.mask_model.get_img(), expected)
    widget.unmask_rb.click()
    button.click()
    assert not model.mask_model.get_img().any()


def test_radial_mask_single_cutoff(radial_mask):
    model, widget, controller = radial_mask
    widget.range_max_txt.setText('40')
    widget.range_outside_btn.click()
    expected = np.rad2deg(model.calibration_model.tth_array) > 40
    np.testing.assert_array_equal(model.mask_model.get_img(), expected)


def test_radial_mask_requires_current_configuration_calibration(radial_mask):
    model, widget, controller = radial_mask
    assert widget.range_inside_btn.isEnabled()
    model.add_configuration()
    model.select_configuration(0)
    model.configurations[1].calibration_model.is_calibrated = False
    model.select_configuration(1)
    assert not widget.range_inside_btn.isEnabled()
    assert not widget.range_outside_btn.isEnabled()
    model.select_configuration(0)
    assert widget.range_inside_btn.isEnabled()
    model.calibration_model.is_calibrated = False
    assert not widget.range_inside_btn.isEnabled()


@pytest.mark.parametrize('lower, upper', [('', ''), ('40', '20'), ('-1', '20'), ('abc', '20')])
def test_invalid_range_is_reported_without_mask_changes(radial_mask, monkeypatch, lower, upper):
    model, widget, controller = radial_mask
    warnings = []
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', lambda *args: warnings.append(args))
    widget.range_min_txt.setText(lower)
    widget.range_max_txt.setText(upper)
    widget.range_inside_btn.click()
    assert len(warnings) == 1
    assert not model.mask_model.get_img().any()
    assert not model.history.can_undo


def test_unit_change_clears_bounds(radial_mask):
    model, widget, controller = radial_mask
    widget.range_min_txt.setText('20')
    widget.range_max_txt.setText('40')
    widget.range_unit_cb.setCurrentIndex(1)
    assert widget.range_min_txt.text() == widget.range_max_txt.text() == ''


@pytest.mark.parametrize('unit', ['q_A^-1', 'd_A'])
def test_radial_mask_requires_wavelength_for_q_and_d(radial_mask, monkeypatch, unit):
    model, widget, controller = radial_mask
    warnings = []
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', lambda *args: warnings.append(args))
    model.calibration_model.pattern_geometry.wavelength = 0
    widget.range_unit_cb.setCurrentIndex(widget.range_unit_cb.findData(unit))
    widget.range_max_txt.setText('2')
    widget.range_outside_btn.click()
    assert len(warnings) == 1
    assert 'wavelength' in warnings[0][2]
    assert not model.mask_model.get_img().any()
