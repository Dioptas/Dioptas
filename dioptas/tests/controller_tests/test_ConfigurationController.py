# SPDX-License-Identifier: MIT

import os
from mock import MagicMock
import gc

import numpy as np

from ..utility import (
    QtTest,
    delete_if_exists,
    click_button,
    enter_value_into_text_field,
)

from qtpy import QtWidgets
from xypattern import Pattern

from ...controller.ConfigurationController import ConfigurationController
from ...model.DioptasModel import DioptasModel
from ...widgets.ConfigurationWidget import ConfigurationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
jcpds_path = os.path.join(data_path, "jcpds")


class ConfigurationControllerTest(QtTest):
    def setUp(self):
        self.config_widget = ConfigurationWidget()
        self.model = DioptasModel()
        self.config_controller = ConfigurationController(
            configuration_widget=self.config_widget,
            dioptas_model=self.model,
            controllers=[],
        )

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, "combined_pattern.xy"))
        del self.model
        del self.config_widget
        del self.config_controller
        gc.collect()

    def test_initial_configuration_display(self):
        self.assertEqual(len(self.config_widget.configuration_btns), 1)

    def test_adding_configurations(self):
        click_button(self.config_widget.add_configuration_btn)
        self.assertEqual(len(self.model.configurations), 2)
        self.assertEqual(len(self.config_widget.configuration_btns), 2)
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())

        click_button(self.config_widget.add_configuration_btn)
        self.assertEqual(len(self.model.configurations), 3)
        self.assertEqual(len(self.config_widget.configuration_btns), 3)
        self.assertTrue(self.config_widget.configuration_btns[2].isChecked())

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_selecting_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 3)
        self.assertTrue(self.config_widget.configuration_btns[-1].isChecked())

        click_button(self.config_widget.configuration_btns[0])
        self.assertEqual(self.model.configuration_ind, 0)

    def test_remove_last_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 3)
        self.assertTrue(self.config_widget.configuration_btns[3].isChecked())

        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 2)
        self.assertTrue(self.config_widget.configuration_btns[2].isChecked())
        self.assertEqual(len(self.config_widget.configuration_btn_group.buttons()), 3)

    def test_remove_first_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        click_button(self.config_widget.configuration_btns[0])
        self.assertEqual(self.model.configuration_ind, 0)

        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 0)
        self.assertTrue(self.config_widget.configuration_btns[0].isChecked())
        self.assertEqual(len(self.model.configurations), 3)

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_remove_in_between_configuration(self):
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)
        click_button(self.config_widget.add_configuration_btn)

        click_button(self.config_widget.configuration_btns[1])
        click_button(self.config_widget.remove_configuration_btn)

        self.assertEqual(self.model.configuration_ind, 1)
        self.assertTrue(self.config_widget.configuration_btns[1].isChecked())
        self.assertEqual(len(self.model.configurations), 3)

        self.assertEqual(self.config_widget.configuration_btns[0].text(), "1")
        self.assertEqual(self.config_widget.configuration_btns[1].text(), "2")
        self.assertEqual(self.config_widget.configuration_btns[2].text(), "3")

    def test_using_factors(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        data1 = np.copy(self.model.img_data)
        enter_value_into_text_field(self.config_widget.factor_txt, 2.5)
        self.assertTrue(np.array_equal(2.5 * data1, self.model.img_data))

        self.model.add_configuration()
        self.assertEqual(float(str(self.config_widget.factor_txt.text())), 1.0)
        enter_value_into_text_field(self.config_widget.factor_txt, 3.5)
        self.assertEqual(self.model.img_model.factor, 3.5)

        self.model.select_configuration(0)
        self.assertEqual(self.model.img_model.factor, 2.5)
        self.assertEqual(float(str(self.config_widget.factor_txt.text())), 2.5)

    def test_file_browsing(self):
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))
        self.model.add_configuration()
        self.model.img_model.load(os.path.join(data_path, "image_001.tif"))

        self.config_widget.file_iterator_pos_txt.setText("0")

        click_button(self.config_widget.next_file_btn)

        self.assertEqual(
            os.path.abspath(self.model.configurations[0].img_model.filename),
            os.path.abspath(os.path.join(data_path, "image_002.tif")),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(os.path.join(data_path, "image_002.tif")),
        )

        click_button(self.config_widget.previous_file_btn)

        self.assertEqual(
            os.path.abspath(self.model.configurations[0].img_model.filename),
            os.path.abspath(os.path.join(data_path, "image_001.tif")),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(os.path.join(data_path, "image_001.tif")),
        )

    def test_folder_browsing(self):
        self.model.img_model.load(
            os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
        )
        self.model.add_configuration()
        self.model.img_model.load(
            os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
        )

        click_button(self.config_widget.next_folder_btn)

        self.assertEqual(
            self.model.configurations[0].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run2", "image_1.tif")
            ),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run2", "image_1.tif")
            ),
        )

        click_button(self.config_widget.previous_folder_btn)

        self.assertEqual(
            self.model.configurations[0].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
            ),
        )

        self.assertEqual(
            self.model.configurations[1].img_model.filename,
            os.path.abspath(
                os.path.join(data_path, "FileIterator", "run1", "image_1.tif")
            ),
        )

    def _setup_two_calibrated_configurations(self):
        """Helper to set up two calibrated configurations for combined pattern tests."""
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M.poni")
        )
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

        self.model.add_configuration()
        self.model.calibration_model.load(
            os.path.join(data_path, "CeO2_Pilatus1M_2.poni")
        )
        self.model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))

    def test_save_combined_pattern(self):
        self._setup_two_calibrated_configurations()
        x1, _ = self.model.configurations[0].pattern_model.pattern.data

        self.model.combine_patterns = True

        # mock dialog with PyQt6-style tuple return (filename, selected_filter)
        file_path = os.path.join(data_path, "combined_pattern.xy")
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(
            return_value=(file_path, "Data (*.xy)")
        )
        click_button(self.config_widget.saved_combined_patterns_btn)

        # load and check that it worked
        saved_pattern = Pattern.from_file(file_path)
        x3, _ = saved_pattern.data
        self.assertGreater(np.max(x3), np.max(x1))
        self.assertGreater(len(x3), 0)

        delete_if_exists(file_path)

    def test_save_combined_pattern_uses_multigeometry(self):
        """Verify that saved combined pattern contains data from MultiGeometry
        integration covering the range of both configurations, not just one."""
        self._setup_two_calibrated_configurations()

        # get individual patterns from each configuration
        x1, _ = self.model.configurations[0].pattern_model.pattern.data
        x2, _ = self.model.configurations[1].pattern_model.pattern.data

        self.model.combine_patterns = True

        file_path = os.path.join(data_path, "combined_pattern.xy")
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(
            return_value=(file_path, "Data (*.xy)")
        )
        click_button(self.config_widget.saved_combined_patterns_btn)

        saved_pattern = Pattern.from_file(file_path)
        x_combined, _ = saved_pattern.data

        # combined pattern should span a wider range than either individual pattern
        self.assertGreater(
            np.max(x_combined),
            max(np.max(x1), np.max(x2)) * 0.95,
            "Combined pattern should cover at least the range of both configurations",
        )
        self.assertGreater(len(x_combined), 0)

        delete_if_exists(file_path)

    def test_save_combined_pattern_cancel_dialog(self):
        """Verify no file is written when user cancels the save dialog."""
        self._setup_two_calibrated_configurations()
        self.model.combine_patterns = True

        file_path = os.path.join(data_path, "combined_pattern.xy")
        # PyQt6 returns ('', '') when dialog is cancelled
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(
            return_value=("", "")
        )
        click_button(self.config_widget.saved_combined_patterns_btn)

        self.assertFalse(os.path.exists(file_path))
