# SPDX-License-Identifier: MIT

from ..utility import QtTest
import os
import gc

from qtpy import QtWidgets
from mock import MagicMock, patch

from ..utility import enter_value_into_text_field, click_button

from ...controller.integration import OptionsController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class OptionsControllerTest(QtTest):
    def setUp(self):
        # Mocking the function which will block the unittest for some reason...
        # Use patch to ensure proper cleanup
        self.processEvents_patcher = patch.object(QtWidgets.QApplication, 'processEvents', MagicMock())
        self.processEvents_patcher.start()

        self.widget = IntegrationWidget()
        self.options_widget = self.widget.integration_control_widget.integration_options_widget
        self.model = DioptasModel()

        self.options_controller = OptionsController(self.widget, self.model)

    def tearDown(self):
        # Stop the patcher to restore original behavior
        self.processEvents_patcher.stop()

        # Clean up widgets
        self.widget.close()
        self.widget.deleteLater()
        del self.options_controller
        del self.widget
        del self.model
        gc.collect()

    def test_change_azimuth_bins(self):
        enter_value_into_text_field(self.options_widget.cake_azimuth_points_sb.lineEdit(), 100)
        self.assertEqual(self.model.current_configuration.cake_azimuth_points, 100)

    def test_change_azimuth_range(self):
        click_button(self.options_widget.cake_full_toggle_btn)
        enter_value_into_text_field(self.options_widget.cake_azimuth_min_txt, -100)
        self.assertEqual(self.model.current_configuration.cake_azimuth_range[0], -100)

        enter_value_into_text_field(self.options_widget.cake_azimuth_max_txt, 200)
        self.assertEqual(self.model.current_configuration.cake_azimuth_range[1], 200)




    def test_direct_params_write_updates_widgets(self):
        """Writing the params directly (e.g. from a script) renders into the
        GUI through the store-level field events — no refresh needed."""
        self.model.current_configuration.params.cake_azimuth_points = 1234
        self.assertEqual(self.options_widget.cake_azimuth_points_sb.value(), 1234)

        self.model.current_configuration.params.cake_azimuth_range = (-45.0, 45.0)
        self.assertEqual(self.options_widget.cake_azimuth_min_txt.text(), "-45.0")
        self.assertEqual(self.options_widget.cake_azimuth_max_txt.text(), "45.0")
        self.assertFalse(self.options_widget.cake_full_toggle_btn.isChecked())

        self.model.current_configuration.params.cake_azimuth_range = None
        self.assertTrue(self.options_widget.cake_full_toggle_btn.isChecked())
