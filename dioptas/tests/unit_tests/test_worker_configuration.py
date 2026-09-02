# SPDX-License-Identifier: MIT

from __future__ import annotations

import numpy as np

from dioptas.model.worker_configuration import (
    build_worker_configuration,
    capture_worker_configuration,
)


def test_worker_configuration_preserves_integration_state(calibrated_config):
    source = calibrated_config
    source.auto_integrate_pattern = False
    source.integration_rad_points = 250
    source.oned_azimuth_range = (0.0, 180.0)
    source.mask_model.mask_rect(10, 10, 20, 20)
    source.use_mask = True

    worker = build_worker_configuration(capture_worker_configuration(source))

    assert worker.integration_scheduler is None
    assert not worker.auto_integrate_pattern
    assert not worker.auto_integrate_cake
    assert not worker.auto_save_integrated_pattern
    assert worker.integration_rad_points == 250
    assert worker.oned_azimuth_range == (0.0, 180.0)
    assert worker.calibration_model.is_calibrated
    np.testing.assert_array_equal(worker.mask_model.get_img(), source.mask_model.get_img())
