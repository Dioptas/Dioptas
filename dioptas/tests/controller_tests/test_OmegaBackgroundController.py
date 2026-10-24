# SPDX-License-Identifier: MIT
"""Experimental-mode GUI runs off-thread and exports/reopens a complete series."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from PIL import Image
from qtpy import QtCore

from dioptas.controller.OmegaBackgroundController import OmegaBackgroundController
from dioptas.model.rotation_series import RotationSeries
from dioptas.widgets.SingleCrystalWidget import SingleCrystalWidget


def make_owner(tmp_path, dioptas_model, qtbot):
    widget = SingleCrystalWidget()
    qtbot.addWidget(widget)
    files = []
    for i in range(12):
        data = np.random.default_rng(i).normal(100, 1, (24, 30)).astype(np.float32)
        data[10, 12] += 100 if i == 5 else 0
        path = tmp_path / f"source_{i:03d}.tif"
        Image.fromarray(data).save(path)
        files.append(str(path))
    bounds = np.column_stack([np.arange(12) * 0.5, np.arange(12) * 0.5 + 0.5])
    series = RotationSeries(
        tuple(files),
        tuple(range(12)),
        bounds,
        "explicit test angles",
        tuple({} for _ in files),
    )
    dioptas_model.img_model.load(files[0])
    return SimpleNamespace(
        widget=widget, model=dioptas_model, series=series, load_series=Mock()
    )


def test_real_async_export_keeps_source_until_explicit_open(
    tmp_path, qtbot, dioptas_model
):
    owner = make_owner(tmp_path, dioptas_model, qtbot)
    controller = OmegaBackgroundController(owner)
    controller.show()
    assert "12 frames" in controller.dialog.source_label.text()
    source_series = owner.series
    mask = np.zeros((24, 30), bool)
    mask[3, 7] = True
    owner.model.mask_model.set_mask_data(mask)
    controller.dialog.workers.setValue(2)
    controller.run()
    assert not controller.dialog.run_button.isEnabled()
    ticks = []
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(1)
    qtbot.waitUntil(lambda: controller._result is not None, timeout=10000)
    timer.stop()
    assert ticks  # event loop remained available during processing
    assert owner.series is source_series
    owner.load_series.assert_not_called()
    assert controller.dialog.open_result_button.isEnabled()
    assert "processing" in controller.dialog.status_label.text()
    controller.open_result()
    exported = owner.load_series.call_args.args[0]
    assert exported.files != source_series.files
    assert all(Path(p).exists() for p in exported.files)
    np.testing.assert_array_equal(exported.omega_bounds, source_series.omega_bounds)
    assert len(exported.source_records) == 12
    np.testing.assert_array_equal(owner.model.mask_model.get_mask(), mask)
    assert owner.model.use_mask


def test_cancel_during_job_removes_incomplete_output(tmp_path, qtbot, dioptas_model):
    owner = make_owner(tmp_path, dioptas_model, qtbot)
    controller = OmegaBackgroundController(owner)
    controller.show()
    controller.run()
    controller.cancel()
    qtbot.waitUntil(lambda: not controller._runner.is_busy, timeout=10000)
    assert controller._result is None
    assert "Cancelled" in controller.dialog.status_label.text()
    assert controller.dialog.run_button.isEnabled()
    assert not list(tmp_path.glob("omega_background_*"))
    assert not list(tmp_path.glob(".omega-background-*"))


def test_no_series_and_invalid_output_are_explained(tmp_path, qtbot, dioptas_model):
    owner = make_owner(tmp_path, dioptas_model, qtbot)
    controller = OmegaBackgroundController(owner)
    controller.show()
    controller.dialog.output_parent.setText(str(tmp_path / "absent"))
    controller.run()
    assert not controller._runner.is_busy
    assert "existing output" in controller.dialog.status_label.text()
    owner.series = None
    controller.show()
    assert "Open a rotation series" in owner.widget.status_label.text()


def test_new_single_crystal_mode_wires_background_tool(qtbot, dioptas_model):
    from dioptas.controller.SingleCrystalController import SingleCrystalController

    widget = SingleCrystalWidget()
    qtbot.addWidget(widget)
    controller = SingleCrystalController(widget, dioptas_model, run_async=False)
    widget.omega_background_button.click()
    assert "Open a rotation series" in widget.status_label.text()
    controller.shutdown()
