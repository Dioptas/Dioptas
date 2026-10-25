# SPDX-License-Identifier: MIT
from pathlib import Path
import numpy as np

from ...model.Configuration import Configuration
from ...model.util.MaskPlugin import MaskPluginBase


class CalibrationProbe(MaskPluginBase):
    name = "Calibration probe"
    needs_geometry = True
    is_dynamic = True

    def compute_mask(self, image, geometry=None, **kwargs):
        mask = np.zeros(image.shape, bool)
        mask[0, 0] = geometry is not None
        return mask


def test_loading_calibration_refreshes_enabled_masks_without_reloading_image(qapp):
    c = Configuration()
    c.auto_integrate_pattern = False
    c.auto_integrate_cake = False
    c.img_model._img_data = np.ones((50, 60))
    c.img_model.img_changed.emit()
    c.mask_plugin_manager.register(CalibrationProbe())
    c.mask_plugin_manager.set_enabled("Calibration probe", True)
    assert not c.mask_plugin_manager.get_combined_mask().any()
    c.calibration_model.load(
        str(Path(__file__).parents[1] / "data/CeO2_Pilatus1M.poni")
    )
    assert c.mask_plugin_manager.get_combined_mask()[0, 0]
    assert c.mask_plugin_manager._geometry.wavelength == c.calibration_model.wavelength


def test_slow_mask_prototypes_are_not_selectable(qapp):
    c = Configuration()
    assert "Diamond Spot Mask (experimental)" not in c.mask_plugin_manager.plugin_names
    schema = c.mask_plugin_manager.get_plugin("Spot Mask").get_settings_schema()
    assert "algorithm" not in schema
    assert not any(key.startswith("broad_") for key in schema)
