# SPDX-License-Identifier: MIT

"""Tests that mask display updates correctly when switching modes and
configurations. Uses the full MainController to exercise the real
activate/deactivate flow."""

import os
import numpy as np
import pytest

unittest_data_path = os.path.join(os.path.dirname(__file__), "../data")


def _mask_is_visible(img_widget):
    return img_widget.mask_img_item in img_widget.img_view_box.addedItems


def _displayed_mask(img_widget):
    return img_widget.mask_img_item.image


def _switch_to_mode(mc, mode, qapp):
    btn = {
        "calib": mc.widget.calibration_mode_btn,
        "mask": mc.widget.mask_mode_btn,
        "integration": mc.widget.integration_mode_btn,
    }[mode]
    btn.setChecked(True)
    mc.tab_changed()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Mask mode: switching configurations
# ---------------------------------------------------------------------------


def test_mask_mode_config_switch_updates_mask(main_controller, qapp):
    mc = main_controller
    model = mc.model
    mask_widget = mc.widget.mask_widget

    _switch_to_mode(mc, "mask", qapp)

    # draw mask on config 0
    model.mask_model.mask_below_threshold(model.img_data, 1)
    mc.mask_controller.plot_mask()
    mask0 = np.copy(model.mask_model.get_img())

    # add config 1 with a different mask
    model.add_configuration()
    qapp.processEvents()
    model.mask_model.mask_above_threshold(model.img_data, 0)
    mc.mask_controller.plot_mask()
    mask1 = np.copy(model.mask_model.get_img())

    assert not np.array_equal(mask0, mask1)

    # switch to config 0 — mask must update
    model.select_configuration(0)
    qapp.processEvents()
    assert _mask_is_visible(mask_widget.img_widget)
    assert np.array_equal(_displayed_mask(mask_widget.img_widget), mask0)

    # switch to config 1 — mask must update
    model.select_configuration(1)
    qapp.processEvents()
    assert _mask_is_visible(mask_widget.img_widget)
    assert np.array_equal(_displayed_mask(mask_widget.img_widget), mask1)


def test_mask_mode_config_switch_updates_transparency(main_controller, qapp):
    mc = main_controller
    model = mc.model
    mask_widget = mc.widget.mask_widget

    _switch_to_mode(mc, "mask", qapp)

    # config 0: filled mask
    assert not model.transparent_mask

    # add config 1: transparent mask
    model.add_configuration()
    qapp.processEvents()
    model.transparent_mask = True

    # switch back to config 0 — fill radio should be checked
    model.select_configuration(0)
    qapp.processEvents()
    assert mask_widget.fill_rb.isChecked()

    # switch to config 1 — transparent radio should be checked
    model.select_configuration(1)
    qapp.processEvents()
    assert mask_widget.transparent_rb.isChecked()


# ---------------------------------------------------------------------------
# Calibration mode: switching configurations
# ---------------------------------------------------------------------------


def test_calib_mode_config_switch_updates_mask(main_controller, qapp):
    mc = main_controller
    model = mc.model
    calib_widget = mc.widget.calibration_widget

    _switch_to_mode(mc, "calib", qapp)

    # enable mask display via checkbox and model
    model.use_mask = True
    calib_widget.use_mask_cb.setChecked(True)
    qapp.processEvents()

    # draw a mask on config 0
    model.mask_model.mask_below_threshold(model.img_data, 1)
    mask0 = np.copy(model.mask_model.get_img())

    # add config 1 with use_mask=False (default)
    model.add_configuration()
    qapp.processEvents()

    # switch to config 0 — mask checkbox and display should reflect config 0
    model.select_configuration(0)
    qapp.processEvents()
    assert calib_widget.use_mask_cb.isChecked()
    assert _mask_is_visible(calib_widget.img_widget)
    assert np.array_equal(_displayed_mask(calib_widget.img_widget), mask0)


def test_calib_mode_config_switch_no_mask(main_controller, qapp):
    mc = main_controller
    model = mc.model
    calib_widget = mc.widget.calibration_widget

    _switch_to_mode(mc, "calib", qapp)

    # config 0 has no mask enabled
    assert not calib_widget.use_mask_cb.isChecked()

    model.add_configuration()
    qapp.processEvents()

    # enable mask on config 1
    calib_widget.use_mask_cb.setChecked(True)
    model.use_mask = True
    qapp.processEvents()

    # switch to config 0 — mask should be off
    model.select_configuration(0)
    qapp.processEvents()
    assert not calib_widget.use_mask_cb.isChecked()
    assert not _mask_is_visible(calib_widget.img_widget)


# ---------------------------------------------------------------------------
# Integration mode: switching configurations
# ---------------------------------------------------------------------------


def test_integration_mode_config_switch_updates_mask(main_controller, qapp):
    mc = main_controller
    model = mc.model
    int_widget = mc.widget.integration_widget

    _switch_to_mode(mc, "integration", qapp)

    # enable mask on config 0
    model.use_mask = True
    int_widget.img_mask_btn.setChecked(True)
    mc.integration_controller.image_controller.plot_mask()
    qapp.processEvents()

    model.mask_model.mask_below_threshold(model.img_data, 1)
    mask0 = np.copy(model.mask_model.get_img())

    # add config 1 without mask
    model.add_configuration()
    qapp.processEvents()

    # switch to config 0
    model.select_configuration(0)
    qapp.processEvents()
    assert int_widget.img_mask_btn.isChecked()
    assert _mask_is_visible(int_widget.img_widget)

    # switch to config 1
    model.select_configuration(1)
    qapp.processEvents()
    assert not int_widget.img_mask_btn.isChecked()
    assert not _mask_is_visible(int_widget.img_widget)


# ---------------------------------------------------------------------------
# Mode switching: mask persists correctly
# ---------------------------------------------------------------------------


def test_mask_persists_after_mode_switch(main_controller, qapp):
    mc = main_controller
    model = mc.model
    mask_widget = mc.widget.mask_widget

    # draw mask in mask mode
    _switch_to_mode(mc, "mask", qapp)
    model.mask_model.mask_below_threshold(model.img_data, 1)
    mc.mask_controller.plot_mask()
    mask0 = np.copy(model.mask_model.get_img())
    assert np.sum(mask0) > 0

    # switch to calib then back to mask
    _switch_to_mode(mc, "calib", qapp)
    _switch_to_mode(mc, "mask", qapp)

    assert _mask_is_visible(mask_widget.img_widget)
    assert np.array_equal(_displayed_mask(mask_widget.img_widget), mask0)


def test_mask_updates_after_mode_switch_with_config_change(
    main_controller, qapp
):
    mc = main_controller
    model = mc.model
    mask_widget = mc.widget.mask_widget

    _switch_to_mode(mc, "mask", qapp)

    # draw mask on config 0
    model.mask_model.mask_below_threshold(model.img_data, 1)
    mc.mask_controller.plot_mask()
    mask0 = np.copy(model.mask_model.get_img())

    # add config 1 with different mask
    model.add_configuration()
    qapp.processEvents()
    model.mask_model.mask_above_threshold(model.img_data, 0)
    mc.mask_controller.plot_mask()
    mask1 = np.copy(model.mask_model.get_img())

    # switch to calib, change config, come back to mask
    _switch_to_mode(mc, "calib", qapp)
    model.select_configuration(0)
    qapp.processEvents()
    _switch_to_mode(mc, "mask", qapp)

    # should show config 0's mask
    assert _mask_is_visible(mask_widget.img_widget)
    assert np.array_equal(_displayed_mask(mask_widget.img_widget), mask0)


def test_calib_mask_checkbox_syncs_on_mode_switch(main_controller, qapp):
    mc = main_controller
    model = mc.model
    calib_widget = mc.widget.calibration_widget

    # config 0: enable mask
    model.use_mask = True

    # add config 1: no mask
    model.add_configuration()
    qapp.processEvents()

    # switch to integration mode, then config 0, then calib mode
    _switch_to_mode(mc, "integration", qapp)
    model.select_configuration(0)
    qapp.processEvents()
    _switch_to_mode(mc, "calib", qapp)

    assert calib_widget.use_mask_cb.isChecked()

    # switch to config 1
    model.select_configuration(1)
    qapp.processEvents()
    assert not calib_widget.use_mask_cb.isChecked()
