# SPDX-License-Identifier: MIT

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from ...model.util.MaskPlugin import MaskPluginBase, GeometryContext
from ...model.MaskPluginManager import MaskPluginManager, MaskPluginEntry
from ...model.MaskModel import MaskModel
from ...model.util.plugin_discovery import _discover_from_directory


# -- Test plugins --


class StaticThresholdPlugin(MaskPluginBase):
    name = "Static Threshold"
    is_dynamic = False

    def __init__(self, threshold=100):
        self.threshold = threshold

    def compute_mask(self, img_data, existing_mask=None, **kwargs):
        return img_data > self.threshold

    def get_settings_schema(self):
        return {"threshold": {"type": "float", "default": 100, "label": "Threshold"}}

    def update_settings(self, settings):
        self.threshold = settings.get("threshold", self.threshold)

    def get_settings(self):
        return {"threshold": self.threshold}


class DynamicMeanPlugin(MaskPluginBase):
    name = "Dynamic Mean"
    is_dynamic = True

    def compute_mask(self, img_data, existing_mask=None, **kwargs):
        return img_data > img_data.mean()


class NoSettingsPlugin(MaskPluginBase):
    name = "No Settings"
    is_dynamic = False

    def compute_mask(self, img_data, existing_mask=None, **kwargs):
        mask = np.zeros(img_data.shape, dtype=bool)
        mask[0, :] = True
        return mask


class BrokenPlugin(MaskPluginBase):
    name = "Broken"
    is_dynamic = False

    def compute_mask(self, img_data, existing_mask=None, **kwargs):
        raise ValueError("I am broken")


class WrongShapePlugin(MaskPluginBase):
    name = "Wrong Shape"
    is_dynamic = False

    def compute_mask(self, img_data, existing_mask=None, **kwargs):
        return np.zeros((1, 1), dtype=bool)


class GeometryAwarePlugin(MaskPluginBase):
    name = "Geometry Aware"
    needs_geometry = True
    is_dynamic = True

    def __init__(self, tth_threshold=0.5):
        self.tth_threshold = tth_threshold

    def compute_mask(self, img_data, geometry=None, existing_mask=None, **kwargs):
        if geometry is None:
            return np.zeros(img_data.shape, dtype=bool)
        return geometry.tth_array > self.tth_threshold


class GeometryAwareStaticPlugin(MaskPluginBase):
    name = "Geometry Static"
    needs_geometry = True
    is_dynamic = False

    def compute_mask(self, img_data, geometry=None, existing_mask=None, **kwargs):
        if geometry is None:
            return np.zeros(img_data.shape, dtype=bool)
        return geometry.tth_array > 1.0


def _make_geometry(shape=(100, 100)):
    """Create a simple GeometryContext for testing."""
    tth = np.linspace(0, 1.0, shape[0] * shape[1]).reshape(shape)
    azi = np.linspace(-np.pi, np.pi, shape[0] * shape[1]).reshape(shape)
    return GeometryContext(
        tth_array=tth,
        azi_array=azi,
        dist=0.2,
        wavelength=0.3344e-10,
        poni1=0.05,
        poni2=0.05,
        rot1=0.0,
        rot2=0.0,
        rot3=0.0,
        pixel1=75e-6,
        pixel2=75e-6,
    )


# -- Fixtures --


@pytest.fixture
def manager():
    return MaskPluginManager()


@pytest.fixture
def img_data():
    return np.random.rand(100, 100) * 200


# -- MaskPluginBase tests --


def test_base_class_has_settings():
    plugin = StaticThresholdPlugin()
    assert plugin.has_settings
    assert plugin.get_settings_schema() is not None

    plugin2 = NoSettingsPlugin()
    assert not plugin2.has_settings
    assert plugin2.get_settings_schema() is None


def test_base_class_not_implemented():
    plugin = MaskPluginBase()
    with pytest.raises(NotImplementedError):
        plugin.compute_mask(np.zeros((10, 10)))


# -- MaskPluginManager tests --


def test_register_plugin(manager):
    plugin = StaticThresholdPlugin()
    manager.register(plugin)
    assert "Static Threshold" in manager.plugin_names
    assert manager.get_plugin("Static Threshold") is plugin


def test_register_duplicate_skipped(manager):
    manager.register(StaticThresholdPlugin())
    manager.register(StaticThresholdPlugin())
    assert len(manager.plugin_names) == 1


def test_unregister_plugin(manager):
    manager.register(StaticThresholdPlugin())
    manager.unregister("Static Threshold")
    assert "Static Threshold" not in manager.plugin_names


def test_enable_disable(manager, img_data):
    manager.register(StaticThresholdPlugin(threshold=100))
    manager.update_image(img_data)

    assert not manager.is_enabled("Static Threshold")
    assert manager.get_combined_mask() is None

    manager.set_enabled("Static Threshold", True)
    assert manager.is_enabled("Static Threshold")

    combined = manager.get_combined_mask()
    assert combined is not None
    expected = img_data > 100
    np.testing.assert_array_equal(combined, expected)

    manager.set_enabled("Static Threshold", False)
    assert manager.get_combined_mask() is None


def test_dynamic_plugin_recomputes(manager):
    manager.register(DynamicMeanPlugin())
    manager.set_enabled("Dynamic Mean", True)

    img1 = np.zeros((50, 50))
    img1[0, 0] = 100
    manager.update_image(img1)

    mask1 = manager.get_combined_mask()
    assert mask1 is not None
    assert mask1[0, 0] == True  # 100 > mean
    assert mask1[1, 1] == False

    img2 = np.ones((50, 50)) * 50
    img2[0, 0] = 0
    manager.update_image(img2)

    mask2 = manager.get_combined_mask()
    assert mask2[0, 0] == False  # 0 < mean(~50)


def test_static_plugin_caches(manager):
    plugin = StaticThresholdPlugin(threshold=100)
    manager.register(plugin)
    manager.set_enabled("Static Threshold", True)

    img1 = np.ones((50, 50)) * 200
    manager.update_image(img1)
    mask1 = manager.get_combined_mask().copy()

    # Same shape, different data — static should NOT recompute
    img2 = np.zeros((50, 50))
    manager.update_image(img2)
    mask2 = manager.get_combined_mask()
    np.testing.assert_array_equal(mask1, mask2)


def test_static_plugin_recomputes_on_shape_change(manager):
    plugin = StaticThresholdPlugin(threshold=100)
    manager.register(plugin)
    manager.set_enabled("Static Threshold", True)

    manager.update_image(np.ones((50, 50)) * 200)
    assert manager.get_combined_mask().shape == (50, 50)

    manager.update_image(np.ones((30, 30)) * 200)
    assert manager.get_combined_mask().shape == (30, 30)


def test_combine_multiple_plugins(manager, img_data):
    manager.register(StaticThresholdPlugin(threshold=150))
    manager.register(NoSettingsPlugin())
    manager.set_enabled("Static Threshold", True)
    manager.set_enabled("No Settings", True)
    manager.update_image(img_data)

    combined = manager.get_combined_mask()
    expected = np.logical_or(img_data > 150, np.arange(100) == 0)  # row 0 masked
    # check row 0 is fully masked
    assert np.all(combined[0, :])


def test_broken_plugin_gets_disabled(manager, img_data):
    manager.register(BrokenPlugin())
    manager.set_enabled("Broken", True)
    manager.update_image(img_data)

    assert not manager.is_enabled("Broken")
    assert manager.get_combined_mask() is None


def test_wrong_shape_plugin_ignored(manager):
    manager.register(WrongShapePlugin())
    manager.set_enabled("Wrong Shape", True)
    manager.update_image(np.zeros((50, 50)))

    assert manager.get_combined_mask() is None


def test_update_settings(manager, img_data):
    manager.register(StaticThresholdPlugin(threshold=100))
    manager.set_enabled("Static Threshold", True)
    manager.update_image(img_data)

    mask_before = manager.get_combined_mask().copy()
    manager.update_plugin_settings("Static Threshold", {"threshold": 50})
    mask_after = manager.get_combined_mask()

    # Lower threshold means more pixels masked
    assert mask_after.sum() >= mask_before.sum()


def test_mask_changed_signal(manager, img_data):
    class Listener:
        def __init__(self):
            self.calls = 0

        def on_changed(self):
            self.calls += 1

    listener = Listener()
    manager.mask_changed.connect(listener.on_changed)

    manager.register(StaticThresholdPlugin())
    manager.set_enabled("Static Threshold", True)
    assert listener.calls >= 1

    listener.calls = 0
    manager.update_image(img_data)
    assert listener.calls >= 1


# -- MaskModel integration tests --


def test_mask_model_get_mask_includes_plugins():
    model = MaskModel(mask_dimension=(50, 50))
    manager = MaskPluginManager()
    model.mask_plugin_manager = manager

    manager.register(NoSettingsPlugin())
    manager.set_enabled("No Settings", True)
    manager.update_image(np.zeros((50, 50)))

    mask = model.get_mask()
    assert np.all(mask[0, :])  # row 0 masked by plugin
    assert not np.any(mask[1:, :])  # rest unmasked


def test_mask_model_get_display_mask():
    model = MaskModel(mask_dimension=(50, 50))
    manager = MaskPluginManager()
    model.mask_plugin_manager = manager

    manager.register(NoSettingsPlugin())
    manager.set_enabled("No Settings", True)
    manager.update_image(np.zeros((50, 50)))

    display = model.get_display_mask()
    assert np.all(display[0, :])

    # get_img still returns only user-drawn mask
    assert not np.any(model.get_img())


def test_mask_model_get_mask_combines_user_and_plugin():
    model = MaskModel(mask_dimension=(50, 50))
    manager = MaskPluginManager()
    model.mask_plugin_manager = manager

    # Plugin masks row 0
    manager.register(NoSettingsPlugin())
    manager.set_enabled("No Settings", True)
    manager.update_image(np.zeros((50, 50)))

    # User masks a rectangle at row 1
    model.mask_rect(1, 0, 1, 50)

    mask = model.get_mask()
    assert np.all(mask[0, :])  # plugin
    assert np.all(mask[1, :])  # user


def test_mask_model_without_plugin_manager():
    """Ensure backward compatibility when no plugin manager is set."""
    model = MaskModel(mask_dimension=(50, 50))
    assert model.mask_plugin_manager is None

    mask = model.get_mask()
    assert mask.shape == (50, 50)
    assert not np.any(mask)


# -- Plugin discovery tests --


def test_discover_from_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_file = Path(tmpdir) / "test_plugin.py"
        plugin_file.write_text(
            """
import numpy as np
from dioptas.model.util.MaskPlugin import MaskPluginBase

class TestDiscoveredPlugin(MaskPluginBase):
    name = "Discovered Plugin"
    is_dynamic = False

    def compute_mask(self, img_data):
        return np.zeros(img_data.shape, dtype=bool)
"""
        )

        plugins = _discover_from_directory(Path(tmpdir))
        assert len(plugins) == 1
        assert plugins[0].name == "Discovered Plugin"


def test_discover_from_empty_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins = _discover_from_directory(Path(tmpdir))
        assert len(plugins) == 0


def test_discover_from_nonexistent_directory():
    plugins = _discover_from_directory(Path("/nonexistent/path"))
    assert len(plugins) == 0


def test_discover_skips_broken_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_file = Path(tmpdir) / "broken.py"
        plugin_file.write_text("raise ImportError('broken')")

        plugins = _discover_from_directory(Path(tmpdir))
        assert len(plugins) == 0


# -- Geometry-aware plugin tests --


def test_geometry_aware_plugin_without_geometry(manager, img_data):
    """Geometry-aware plugin returns empty mask when no geometry available."""
    manager.register(GeometryAwarePlugin())
    manager.set_enabled("Geometry Aware", True)
    manager.update_image(img_data)

    mask = manager.get_combined_mask()
    assert mask is not None
    assert not np.any(mask)


def test_geometry_aware_plugin_with_geometry(manager, img_data):
    """Geometry-aware plugin uses geometry context for masking."""
    plugin = GeometryAwarePlugin(tth_threshold=0.5)
    manager.register(plugin)
    manager.set_enabled("Geometry Aware", True)

    geometry = _make_geometry(img_data.shape)
    manager.update_geometry(geometry)
    manager.update_image(img_data)

    mask = manager.get_combined_mask()
    assert mask is not None
    expected = geometry.tth_array > 0.5
    np.testing.assert_array_equal(mask, expected)


def test_geometry_update_recomputes_geometry_plugins(manager, img_data):
    """Updating geometry triggers recomputation of geometry-aware plugins."""
    plugin = GeometryAwarePlugin(tth_threshold=0.5)
    manager.register(plugin)
    manager.set_enabled("Geometry Aware", True)
    manager.update_image(img_data)

    # Initially no geometry — mask is all False
    assert not np.any(manager.get_combined_mask())

    # Provide geometry — mask should now reflect tth > 0.5
    geometry = _make_geometry(img_data.shape)
    manager.update_geometry(geometry)

    mask = manager.get_combined_mask()
    expected = geometry.tth_array > 0.5
    np.testing.assert_array_equal(mask, expected)


def test_geometry_update_does_not_affect_non_geometry_plugins(manager, img_data):
    """Non-geometry plugins are unaffected by geometry updates."""
    manager.register(StaticThresholdPlugin(threshold=100))
    manager.set_enabled("Static Threshold", True)
    manager.update_image(img_data)

    mask_before = manager.get_combined_mask().copy()

    geometry = _make_geometry(img_data.shape)
    manager.update_geometry(geometry)

    mask_after = manager.get_combined_mask()
    np.testing.assert_array_equal(mask_before, mask_after)


def test_geometry_none_clears_geometry(manager, img_data):
    """Setting geometry to None makes geometry plugins return empty mask."""
    plugin = GeometryAwarePlugin(tth_threshold=0.5)
    manager.register(plugin)
    manager.set_enabled("Geometry Aware", True)

    geometry = _make_geometry(img_data.shape)
    manager.update_geometry(geometry)
    manager.update_image(img_data)

    assert np.any(manager.get_combined_mask())

    # Clear geometry
    manager.update_geometry(None)
    manager.update_image(img_data)

    assert not np.any(manager.get_combined_mask())


def test_geometry_context_dataclass():
    """GeometryContext stores all expected fields."""
    geo = _make_geometry((50, 50))
    assert geo.tth_array.shape == (50, 50)
    assert geo.azi_array.shape == (50, 50)
    assert geo.dist == 0.2
    assert geo.wavelength == 0.3344e-10
    assert geo.pixel1 == 75e-6
    assert geo.pixel2 == 75e-6


# -- Plugin imprint tests --


def test_imprint_bakes_mask_and_disables_plugin():
    """imprint_plugin_mask ORs the plugin mask into _mask_data and disables the plugin."""
    model = MaskModel(mask_dimension=(50, 50))
    manager = MaskPluginManager()
    model.mask_plugin_manager = manager

    plugin = NoSettingsPlugin()  # masks row 0
    manager.register(plugin)
    manager.update_image(np.zeros((50, 50)))
    manager.set_enabled("No Settings", True)

    assert model.get_img().sum() == 0
    model.imprint_plugin_mask("No Settings")
    assert model.get_img().sum() == 50  # row 0 baked in
    assert not manager.is_enabled("No Settings")



def test_enabling_after_an_image_change_recomputes_the_mask():
    """Enable on image A, disable, load same-shaped image B, enable again:
    the mask shown used to be image A's."""
    manager = MaskPluginManager()
    plugin = DynamicMeanPlugin()
    manager.register(plugin)

    image_a = np.zeros((4, 4))
    image_a[0, 0] = 100.0  # far above the mean -> masked
    manager.update_image(image_a)
    manager.set_enabled(plugin.name, True)
    mask_a = manager.plugins[plugin.name].cached_mask.copy()
    assert mask_a[0, 0]

    manager.set_enabled(plugin.name, False)
    image_b = np.zeros((4, 4))
    image_b[3, 3] = 100.0  # same shape, different hot pixel
    manager.update_image(image_b)

    manager.set_enabled(plugin.name, True)
    mask_b = manager.plugins[plugin.name].cached_mask
    assert mask_b[3, 3]
    assert not mask_b[0, 0]  # not image A's mask


def test_static_plugin_cache_survives_same_shape_image_changes():
    """A non-dynamic plugin's mask does not depend on the image, so its
    cache stays valid across same-shaped images."""
    manager = MaskPluginManager()
    plugin = StaticThresholdPlugin()
    manager.register(plugin)

    manager.update_image(np.ones((4, 4)))
    manager.set_enabled(plugin.name, True)
    cached = manager.plugins[plugin.name].cached_mask

    manager.set_enabled(plugin.name, False)
    manager.update_image(np.ones((4, 4)) * 2)
    manager.set_enabled(plugin.name, True)
    assert manager.plugins[plugin.name].cached_mask is cached
