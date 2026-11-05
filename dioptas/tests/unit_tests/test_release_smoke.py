"""Release checks must work with core Peritheos without observation tables."""

import pytest
from peritheos import Material

from ...model import eos
from ...model.util.mask_plugins.powder_outlier import _c_compute_binned
from ...model.util.release_smoke import check_release_runtime


@pytest.mark.skipif(_c_compute_binned is None,
                    reason="Release smoke requires the compiled mask extension")
def test_release_smoke_does_not_load_observation_datasets(qapp, monkeypatch):
    def reject_observations(*args, **kwargs):
        raise AssertionError("Dioptas release checks must use core resources only")

    monkeypatch.setattr(Material, "get_dataset", reject_observations)
    assert check_release_runtime() == len(eos.load_materials())
