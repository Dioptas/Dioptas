# SPDX-License-Identifier: MIT
from pathlib import Path
import numpy as np

from ...model.Configuration import Configuration
from ...model.util.MaskPlugin import MaskPluginBase


class CalibrationProbe(MaskPluginBase):
    name = "Calibration probe"
    needs_geometry = True
    is_dynamic = True

    def __init__(self):
        self.calls = []

    def compute_mask(self, image, geometry=None, **kwargs):
        self.calls.append((image.copy(), geometry))
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


def test_new_frame_is_computed_once_with_current_geometry(qapp):
    c = Configuration()
    c.auto_integrate_pattern = c.auto_integrate_cake = False
    c.img_model._img_data = np.ones((50, 60))
    c.img_model.img_changed.emit()
    c.calibration_model.load(str(Path(__file__).parents[1] / "data/CeO2_Pilatus1M.poni"))
    probe = CalibrationProbe()
    c.mask_plugin_manager.register(probe)
    c.mask_plugin_manager.set_enabled(probe.name, True)
    probe.calls.clear()
    c.img_model._img_data = np.full((50, 60), 2.0)
    c._update_plugin_masks()
    assert len(probe.calls) == 1
    image, geometry = probe.calls[0]
    assert np.all(image == 2)
    assert geometry is c.mask_plugin_manager._geometry
    refreshed = c._get_plugin_geometry(image.shape)
    assert refreshed.tth_array is geometry.tth_array
    assert refreshed.azi_array is geometry.azi_array
    np.testing.assert_array_equal(
        geometry.tth_array,
        c.calibration_model.pattern_geometry.center_array(image.shape, unit="2th_rad"),
    )


def test_slow_mask_prototypes_are_not_selectable(qapp):
    c = Configuration()
    assert "Diamond Spot Mask (experimental)" not in c.mask_plugin_manager.plugin_names
    schema = c.mask_plugin_manager.get_plugin("Spot Mask").get_settings_schema()
    assert "algorithm" not in schema
    assert not any(key.startswith("broad_") for key in schema)
