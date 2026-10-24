import csv
import json

import numpy as np
import pytest

from dioptas.model.single_crystal import (
    SpotTask,
    backend_available,
    export_spots,
    measure_spots,
)


@pytest.mark.skipif(
    not backend_available(), reason="experimental PhaseSmith build needed"
)
def test_backend_and_export_preserve_all_flags_counts_and_provenance(tmp_path):
    image = np.full((32, 32), 5.0)
    image[12:15, 13:16] += 100
    mask = np.zeros(image.shape, dtype=bool)
    task = SpotTask(image, mask, "unknown.tif", {}, saturation=90)
    result = measure_spots(task)
    assert len(result.table) == 1
    assert result.table.flags[0] & 4
    csv_path, metadata_path = export_spots(result, tmp_path / "spots.csv")
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert float(rows[0]["intensity"]) == 900
    assert "Saturated" in rows[0]["quality"]
    metadata = json.loads(metadata_path.read_text())
    assert metadata["options"]["max_spots"] == 10000
    assert metadata["noise_model"] == "poisson_plus_read_noise_with_variance_floor"
    assert len(metadata["image_sha256"]) == len(metadata["mask_sha256"]) == 64
    assert (
        len(metadata["native_engine_sha256"])
        == len(metadata["python_adapter_sha256"])
        == 64
    )
    assert metadata["records"] == metadata["flagged"] == 1
