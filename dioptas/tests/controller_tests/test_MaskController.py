# SPDX-License-Identifier: MIT

from ..utility import QtTest, click_button, unittest_data_path, click_checkbox, delete_if_exists
import os
import gc
import numpy as np
from mock import MagicMock

from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtTest import QTest

from ...model.DioptasModel import DioptasModel
from ...controller.MaskController import MaskController
from ...widgets.MaskWidget import MaskWidget


class MaskControllerTest(QtTest):
    def setUp(self):

        self.model = DioptasModel()
        self.model.working_directories = {'mask': unittest_data_path}

        self.mask_widget = MaskWidget()
        self.mask_controller = MaskController(self.mask_widget, self.model)

    def tearDown(self):
        delete_if_exists(os.path.join(unittest_data_path, 'dummy.mask'))
        del self.model
        self.mask_widget.close()
        del self.mask_widget
        del self.mask_controller
        gc.collect()

    def get_file_size(self, filename):
        stat_info = os.stat(filename)
        return stat_info.st_size

    def test_loading_and_saving_mask_files(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=(
            os.path.join(unittest_data_path, 'test.mask'),
            MaskController.DEFAULT_MASK_FILTER,
        ))
        click_button(self.mask_widget.load_mask_btn)
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)

        dialog_results = (
            ('.mask', MaskController.DEFAULT_MASK_FILTER),
            ('.npy', f"{MaskController.FLIPUD_MASK_FILTER_PREFIX} (*.npy)"),
            ('.edf', f"{MaskController.FLIPUD_MASK_FILTER_PREFIX} (*.edf)")

        )
        for extension, selected_filter in dialog_results:
            with self.subTest(extension=extension, selected_filter=selected_filter):
                filename = os.path.join(unittest_data_path, f'dummy{extension}')
                QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=(filename, selected_filter))
                click_button(self.mask_widget.save_mask_btn)
                self.assertTrue(os.path.exists(filename))
                delete_if_exists(filename)

    def test_grow_and_shrinking(self):
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        previous_mask = np.copy(self.model.mask_model._mask_data)

        QTest.mouseClick(self.mask_widget.grow_btn, QtCore.Qt.LeftButton)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))

        QTest.mouseClick(self.mask_widget.shrink_btn, QtCore.Qt.LeftButton)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))

    def test_mask_and_unmask(self):
        # test that changing mask mode modifies the model and the color in img_widget
        self.mask_widget.mask_rb.click()
        self.assertEqual(self.model.mask_model.mode, True)
        self.assertEqual(self.mask_widget.img_widget.mask_preview_fill_color, QtGui.QColor(255, 0, 0, 150))
        self.mask_widget.unmask_rb.click()
        self.assertEqual(self.model.mask_model.mode, False)
        self.assertEqual(self.mask_widget.img_widget.mask_preview_fill_color, QtGui.QColor(0, 255, 0, 150))

        # test that masking and unmasking the same area results in the same mask
        previous_mask = np.copy(self.model.mask_model._mask_data)
        self.mask_widget.mask_rb.click()
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        self.assertFalse(np.array_equal(previous_mask, self.model.mask_model._mask_data))
        self.mask_widget.unmask_rb.click()
        self.model.mask_model.mask_ellipse(100, 100, 20, 20)
        self.assertTrue(np.array_equal(previous_mask, self.model.mask_model._mask_data))

    def test_select_configuration_updating_mask(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=(
            os.path.join(unittest_data_path, 'test.mask'),
            MaskController.DEFAULT_MASK_FILTER,
        ))
        click_button(self.mask_widget.load_mask_btn)
        first_mask = self.model.mask_model.get_img()
        self.model.add_configuration()
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        second_mask = self.model.mask_model.get_img()

        self.model.select_configuration(0)
        self.assertEqual(np.sum(self.mask_widget.img_widget.mask_img_item.image-first_mask), 0)
        self.model.select_configuration(1)
        self.assertEqual(np.sum(self.mask_widget.img_widget.mask_img_item.image-second_mask), 0)

    def test_select_configuration_updating_mask_transparency(self):
        QtWidgets.QFileDialog.getOpenFileName = MagicMock(return_value=(
            os.path.join(unittest_data_path, 'test.mask'),
            MaskController.DEFAULT_MASK_FILTER,
        ))
        click_button(self.mask_widget.load_mask_btn)
        self.model.add_configuration()
        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        click_checkbox(self.mask_widget.transparent_rb)
        self.assertTrue(self.mask_widget.transparent_rb.isChecked())

        transparent_color = self.mask_widget.img_widget.create_color_map([255, 0, 0, 100])
        filled_color = self.mask_widget.img_widget.create_color_map([255, 0, 0, 255])

        self.assertTrue(self.model.transparent_mask)
        self.model.select_configuration(0)
        self.assertTrue(self.mask_widget.fill_rb.isChecked())
        self.assertTrue(np.array_equal(self.mask_widget.img_widget.mask_img_item.lut, filled_color))
        self.model.select_configuration(1)
        self.assertTrue(self.mask_widget.transparent_rb.isChecked())
        self.assertTrue(np.array_equal(self.mask_widget.img_widget.mask_img_item.lut, transparent_color))

    def test_apply_cosmic_removal(self):
        click_button(self.mask_widget.cosmic_btn)

    def test_drawing_mask_with_dynamic_plugin_enabled_does_not_recurse(self):
        """Regression: drawing a mask while a dynamic plugin is enabled should
        not cause infinite recursion via mask_changed -> plot_mask cycles."""
        # Load an image so plugins can compute
        self.model.img_model._img_data = np.random.rand(2048, 2048).astype(np.float64) * 1000
        self.model.img_model.img_changed.emit()

        # Enable a dynamic plugin (Cosmic Ray)
        self.model.mask_plugin_manager.set_enabled('Cosmic Ray Mask', True)

        # Draw a rectangle: this used to recurse because plugin recompute
        # emitted mask_changed -> plot_mask -> recompute -> ...
        import sys
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            self.model.mask_model.mask_rect(10, 10, 20, 20)
            self.mask_controller.plot_mask()
            self.model.mask_model.mask_rect(50, 50, 30, 30)
            self.mask_controller.plot_mask()
        finally:
            sys.setrecursionlimit(old_limit)

        # Both rectangles should be in the user mask
        assert self.model.mask_model.get_img().sum() > 0

    def test_imprint_bakes_plugin_mask_into_user_mask(self):
        """The imprint button should OR the plugin's current mask into the
        user-drawn mask and disable the plugin."""
        # Load an image so the plugin can compute
        self.model.img_model._img_data = np.random.rand(100, 100).astype(np.float64) * 1e6
        self.model.img_model.img_changed.emit()

        # Enable cosmic ray plugin via the GUI checkbox (so imprint btn updates)
        row = self.mask_widget.plugin_widget.get_row('Cosmic Ray Mask')
        self.assertIsNotNone(row)
        row.checkbox.setChecked(True)
        self.mask_controller.plot_mask()

        # Get the plugin mask before imprint
        manager = self.model.mask_plugin_manager
        plugin_mask = manager.get_combined_mask()
        if plugin_mask is None or plugin_mask.sum() == 0:
            self.skipTest("Plugin produced no mask on this synthetic data")
        plugin_pixels = plugin_mask.sum()

        # User mask should be empty initially
        self.assertEqual(self.model.mask_model.get_img().sum(), 0)

        # Click imprint
        self.assertTrue(row.imprint_btn.isEnabled())
        QTest.mouseClick(row.imprint_btn, QtCore.Qt.LeftButton)

        # Plugin should be disabled
        self.assertFalse(manager.is_enabled('Cosmic Ray Mask'))
        self.assertFalse(row.checkbox.isChecked())
        self.assertFalse(row.imprint_btn.isEnabled())

        # User mask should now contain the plugin pixels
        self.assertEqual(int(self.model.mask_model.get_img().sum()), int(plugin_pixels))

    def test_drawing_mask_with_geometry_plugin_enabled_does_not_recurse(self):
        """Regression: drawing a mask while a geometry-aware plugin is enabled
        should not recurse. update_geometry emits mask_changed before update_image
        does, so the user mask sum must be updated first."""
        from ...model.util.MaskPlugin import MaskPluginBase, GeometryContext

        class TestGeoPlugin(MaskPluginBase):
            name = "Test Geo Plugin"
            needs_geometry = True
            is_dynamic = True

            def compute_mask(self, img_data, geometry=None, existing_mask=None, **kwargs):
                return np.zeros(img_data.shape, dtype=bool)

        # Provide a fake geometry so update_geometry actually computes
        self.model.mask_plugin_manager._geometry = GeometryContext(
            tth_array=np.zeros((100, 100)), azi_array=np.zeros((100, 100)),
            dist=0.2, wavelength=1e-10, poni1=0.05, poni2=0.05,
            rot1=0, rot2=0, rot3=0, pixel1=75e-6, pixel2=75e-6,
        )
        self.model.mask_plugin_manager.register(TestGeoPlugin())
        self.model.img_model._img_data = np.random.rand(100, 100).astype(np.float64) * 1000
        self.model.img_model.img_changed.emit()
        self.model.mask_plugin_manager.set_enabled('Test Geo Plugin', True)

        import sys
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            self.model.mask_model.mask_rect(10, 10, 20, 20)
            self.mask_controller.plot_mask()
            self.model.mask_model.mask_rect(50, 50, 30, 30)
            self.mask_controller.plot_mask()
        finally:
            sys.setrecursionlimit(old_limit)

        assert self.model.mask_model.get_img().sum() > 0


def test_plugin_settings_dialog_restores_defaults(qapp):
    """The Restore Defaults button sets every field back to the schema
    default and pushes the change through the live-update path."""
    from dioptas.widgets.MaskPluginWidget import MaskPluginSettingsDialog

    schema = {
        "threshold": {"type": "float", "default": 5.0, "min": 0, "max": 100},
        "iterations": {"type": "int", "default": 3, "min": 1, "max": 10},
        "mode": {"type": "choice", "choices": ["fast", "full"], "default": "fast"},
    }
    dialog = MaskPluginSettingsDialog(
        "Test", schema, {"threshold": 42.0, "iterations": 9, "mode": "full"}
    )
    received = []
    dialog.settings_changed.connect(received.append)

    dialog.restore_defaults()

    # exactly one emission: per-field ones would recompute the mask once
    # per field and leave one undo step each
    assert received == [{"threshold": 5.0, "iterations": 3, "mode": "fast"}]
    dialog.close()
