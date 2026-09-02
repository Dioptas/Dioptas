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


def test_mask_controls_are_below_every_detector_image(main_controller):
    widgets = main_controller.widget
    calibration_display = (
        widgets.calibration_widget.calibration_display_widget
    )

    assert (
        calibration_display._status_layout.indexOf(
            calibration_display.show_calibrant_numbers_cb
        )
        < calibration_display._status_layout.indexOf(
            calibration_display.mask_controls_separator
        )
        < calibration_display._status_layout.indexOf(
            calibration_display.mask_controls
        )
    )
    assert (
        calibration_display._status_layout.indexOf(
            calibration_display.mask_controls
        )
        >= 0
    )
    assert (
        widgets.mask_widget._status_layout.indexOf(
            widgets.mask_widget.mask_controls
        )
        >= 0
    )
    assert (
        widgets.integration_widget.integration_image_widget
        ._control_layout.indexOf(
            widgets.integration_widget.integration_image_widget.mask_controls
        )
        >= 0
    )
    assert (
        widgets.map_widget._img_layout.indexOf(
            widgets.map_widget.mask_controls
        )
        >= 0
    )


def test_mask_controls_in_every_mode_share_configuration_state(
    main_controller, qapp
):
    widgets = main_controller.widget
    model = main_controller.model
    mask_controls = [
        widgets.calibration_widget.calibration_display_widget.mask_controls,
        widgets.mask_widget.mask_controls,
        widgets.integration_widget.integration_image_widget.mask_controls,
        widgets.map_widget.mask_controls,
    ]

    for controls in mask_controls:
        assert controls.use_mask_cb.text() == "mask"
        assert controls.transparent_mask_cb.text() == "transparent"
        assert not controls.transparent_mask_cb.isEnabled()

    for controls in mask_controls:
        controls.use_mask_cb.click()
        qapp.processEvents()
        assert model.use_mask
        assert all(item.use_mask_cb.isChecked() for item in mask_controls)
        assert all(
            item.transparent_mask_cb.isEnabled() for item in mask_controls
        )

        controls.transparent_mask_cb.click()
        qapp.processEvents()
        assert model.transparent_mask
        assert all(
            item.transparent_mask_cb.isChecked() for item in mask_controls
        )

        controls.transparent_mask_cb.click()
        qapp.processEvents()
        assert not model.transparent_mask
        assert not any(
            item.transparent_mask_cb.isChecked() for item in mask_controls
        )

        controls.use_mask_cb.click()
        qapp.processEvents()
        assert not model.use_mask
        assert not any(item.use_mask_cb.isChecked() for item in mask_controls)
        assert not any(
            item.transparent_mask_cb.isEnabled() for item in mask_controls
        )


def test_project_reload_restores_file_browsing_and_mask_drawing_modes(
    main_controller, qapp, tmp_path
):
    mc = main_controller
    model = mc.model
    integration = mc.widget.integration_widget

    integration.img_step_file_widget.browse_by_time_rb.click()
    integration.pattern_browse_by_time_rb.click()
    _switch_to_mode(mc, "mask", qapp)
    mc.widget.mask_widget.unmask_rb.click()

    filename = tmp_path / "navigation-state.dio"
    model.save(filename)
    model.reset()
    qapp.processEvents()

    assert integration.img_step_file_widget.browse_by_name_rb.isChecked()
    assert integration.pattern_browse_by_name_rb.isChecked()
    assert mc.widget.mask_widget.mask_rb.isChecked()

    model.load(filename)
    qapp.processEvents()

    assert integration.img_step_file_widget.browse_by_time_rb.isChecked()
    assert integration.pattern_browse_by_time_rb.isChecked()
    assert mc.widget.mask_widget.unmask_rb.isChecked()
    assert model.img_model.file_name_iterator.create_timed_file_list
    assert model.pattern_model.file_name_iterator.create_timed_file_list


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

    # switch back to config 0 — transparency should be off
    model.select_configuration(0)
    qapp.processEvents()
    assert not mask_widget.mask_transparent_cb.isChecked()

    # switch to config 1 — transparent radio should be checked
    model.select_configuration(1)
    qapp.processEvents()
    assert mask_widget.mask_transparent_cb.isChecked()


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
