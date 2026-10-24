"""Experimental mode remains isolated, uses raw pixels and rejects stale jobs."""

import importlib
import threading

import numpy as np
import pytest
from qtpy import QtCore

from dioptas.controller.MainController import MainController
from dioptas.model.single_crystal import backend_available
from dioptas.widgets.MainWidget import MainWidget

native = pytest.mark.skipif(
    not backend_available(), reason="experimental PhaseSmith build needed"
)


def load_scene(controller, tmp_path):
    from fabio.tifimage import TifImage

    image = np.full((64, 80), 5, dtype=np.uint16)
    image[12:15, 17:20] += 100
    path = tmp_path / "unknown-sample.tif"
    TifImage(data=image).write(str(path))
    controller.model.img_model.load(str(path))
    return path


@pytest.fixture
def experimental_controller(qapp):
    controller = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    controller.widget.show()
    yield controller
    controller.widget.close()


def test_default_mode_is_absent(qapp, monkeypatch):
    monkeypatch.delenv("DIOPTAS_EXPERIMENTAL_SINGLE_CRYSTAL", raising=False)
    widget = MainWidget()
    assert widget.single_crystal_mode_btn is None
    assert widget.single_crystal_widget is None
    widget.close()


def test_opt_in_environment_is_explicit(qapp, monkeypatch):
    monkeypatch.setenv("DIOPTAS_EXPERIMENTAL_SINGLE_CRYSTAL", "0")
    normal = MainWidget()
    assert normal.single_crystal_widget is None
    normal.close()
    monkeypatch.setenv("DIOPTAS_EXPERIMENTAL_SINGLE_CRYSTAL", "1")
    experimental = MainWidget()
    assert experimental.single_crystal_widget is not None
    experimental.close()


def test_missing_backend_disables_measurement(qapp, monkeypatch):
    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    monkeypatch.setattr(module, "backend_available", lambda: False)
    controller = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    widget = controller.widget.single_crystal_widget
    assert not widget.detect_button.isEnabled()
    assert "not included" in widget.status_label.text()
    controller.widget.close()


@native
def test_mode_switching_and_real_backend(experimental_controller, tmp_path):
    c = experimental_controller
    load_scene(c, tmp_path)
    c.widget.single_crystal_mode_btn.click()
    assert c.current_tab_index == 4
    assert c.single_crystal_controller._active
    np.testing.assert_array_equal(
        c.widget.single_crystal_widget.img_widget.img_data,
        c.model.img_model.raw_img_data,
    )
    c.widget.single_crystal_widget.detect_button.click()
    result = c.single_crystal_controller.result
    assert result is not None and len(result.table) == 1
    np.testing.assert_allclose(
        result.table.column("intensity"), 900, atol=1e-12, rtol=0
    )
    overlay = c.widget.single_crystal_widget.spot_overlay
    np.testing.assert_allclose(overlay.getData()[0], result.table.column("x") + 0.5)
    assert c.widget.single_crystal_widget.table_model.rowCount() == 1
    c.widget.integration_mode_btn.click()
    assert not c.single_crystal_controller._active
    assert c.current_tab_index == 2
    c.widget.single_crystal_mode_btn.click()
    assert c.single_crystal_controller.result is result


@native
def test_intensity_uses_raw_counts_and_respects_mask(experimental_controller, tmp_path):
    c = experimental_controller
    load_scene(c, tmp_path)
    c.model.img_model.factor = 7
    c.single_crystal_controller.detect()
    np.testing.assert_allclose(
        c.single_crystal_controller.result.table.column("intensity"), 900
    )
    mask = np.zeros(c.model.img_model.raw_img_data.shape, dtype=bool)
    peak = np.unravel_index(np.argmax(c.model.img_model.raw_img_data), mask.shape)
    mask[peak] = True
    c.model.use_mask = True
    c.model.mask_model.set_mask_data(mask)
    c.model.mask_changed.emit()
    assert c.single_crystal_controller.result is None
    c.single_crystal_controller.detect()
    result = c.single_crystal_controller.result
    assert result.table.flags[0] & 2
    np.testing.assert_allclose(result.table.column("intensity"), 800)
    assert result.metadata["masked_pixels"] == 1


@native
def test_image_parameters_and_configuration_invalidate_results(
    experimental_controller, tmp_path
):
    c = experimental_controller
    load_scene(c, tmp_path)
    sc = c.single_crystal_controller
    sc.detect()
    c.widget.single_crystal_widget.threshold.setValue(6)
    assert sc.result is None
    assert not c.widget.single_crystal_widget.export_button.isEnabled()
    sc.detect()
    c.model.img_changed.emit()
    assert sc.result is None
    sc.detect()
    c.model.add_configuration()
    assert sc.result is None


@native
def test_stale_background_result_is_discarded(qapp, qtbot, tmp_path, monkeypatch):
    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    original = module.measure_spots
    started, release = threading.Event(), threading.Event()

    def delayed(task):
        started.set()
        assert release.wait(10)
        return original(task)

    monkeypatch.setattr(module, "measure_spots", delayed)
    c = MainController(
        use_settings=False, run_async_processing=True, experimental_single_crystal=True
    )
    try:
        load_scene(c, tmp_path)
        sc = c.single_crystal_controller
        sc.detect()
        qtbot.waitUntil(started.is_set, timeout=5000)
        assert not c.widget.single_crystal_widget.detect_button.isEnabled()
        c.model.img_changed.emit()
        release.set()
        qtbot.waitUntil(lambda: not sc._runner.is_busy, timeout=5000)
        assert sc.result is None
        assert c.widget.single_crystal_widget.table_model.rowCount() == 0
    finally:
        release.set()
        c.widget.close()


@native
def test_table_shows_quality_and_nonfinite_values(experimental_controller, tmp_path):
    c = experimental_controller
    load_scene(c, tmp_path)
    widget = c.widget.single_crystal_widget
    widget.saturation_enabled.setChecked(True)
    widget.saturation.setValue(90)
    c.single_crystal_controller.detect()
    model = widget.table_model
    assert "Saturated" in model.data(model.index(0, 7))
    assert model.data(model.index(0, 0)) == 1
    assert model.headerData(3, QtCore.Qt.Horizontal) == "Counts"


@native
def test_zero_padding_mask_is_opt_in_and_exported(experimental_controller, tmp_path):
    c = experimental_controller
    load_scene(c, tmp_path)
    c.model.img_model.raw_img_data[:4, :] = 0
    widget = c.widget.single_crystal_widget
    assert not widget.zero_padding.isChecked()
    c.single_crystal_controller.detect()
    assert c.single_crystal_controller.result.metadata["masked_pixels"] == 0
    widget.zero_padding.setChecked(True)
    assert c.single_crystal_controller.result is None
    c.single_crystal_controller.detect()
    result = c.single_crystal_controller.result
    assert result.metadata["masked_pixels"] == 4 * 80
    assert result.metadata["mask_policy"]["exclude_zero_padding"]
