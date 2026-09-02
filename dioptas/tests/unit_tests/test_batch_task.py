# SPDX-License-Identifier: MIT

import numpy as np

from dioptas.model.batch_task import BatchBackgroundTask, compute_batch_background


def test_compute_batch_background_is_independent_and_reports_progress():
    binning = np.linspace(1, 10, 100)
    data = np.vstack((np.linspace(5, 15, 100), np.linspace(8, 18, 100)))
    task = BatchBackgroundTask(
        binning=binning,
        data=data,
        parameters=(0.1, 50, 10),
    )
    progress = []

    background = compute_batch_background(
        task, lambda current: progress.append(current) or True
    )

    assert background.shape == data.shape
    assert not np.shares_memory(background, data)
    assert progress == [1, 2]
