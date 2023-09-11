# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import gc
import shutil
import numpy as np
from mock import MagicMock

from ..utility import QtTest, click_button, click_checkbox

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ...model.util.HelperModule import get_partial_value
from ...widgets.integration import IntegrationWidget
from ...controller.integration.ImageController import ImageController
from ...model.DioptasModel import DioptasModel

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')


class ImageControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = ImageController(
            widget=self.widget,
            dioptas_model=self.model)

    def tearDown(self):
        if os.path.exists(os.path.join(unittest_data_path, 'image_003.tif')):
            os.remove(os.path.join(unittest_data_path, 'image_003.tif'))
        del self.widget
        del self.model
        del self.controller
        gc.collect()

    def test_automatic_file_processing(self):
        # get into a specific folder
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(unittest_data_path, 'image_001.tif')])
        click_button(self.widget.load_img_btn)
        self.assertEqual(str(self.widget.img_filename_txt.text()), 'image_001.tif')
        self.assertEqual(self.model.working_directories['image'], unittest_data_path)

        # enable autoprocessing:
        QTest.mouseClick(self.widget.autoprocess_cb, QtCore.Qt.LeftButton,
                         pos=QtCore.QPoint(2, int(self.widget.autoprocess_cb.height() / 2.0)))

        self.assertFalse(self.model.configurations[0].img_model._directory_watcher.signalsBlocked())

        self.assertTrue(self.widget.autoprocess_cb.isChecked())
        self.assertTrue(self.model.img_model.autoprocess)

        shutil.copy2(os.path.join(unittest_data_path, 'image_001.tif'),
                     os.path.join(unittest_data_path, 'image_003.tif'))

        self.model.img_model._directory_watcher.file_added.emit(os.path.join(unittest_data_path, 'image_003.tif'))

        self.assertEqual('image_003.tif', str(self.widget.img_filename_txt.text()))
        QtWidgets.QApplication.instance().processEvents()

    def test_configuration_selected_changes_mask_mode(self):
        self.model.add_configuration()
        click_button(self.widget.img_mask_btn)
        self.assertTrue(self.model.use_mask)

        self.model.select_configuration(0)
        self.assertFalse(self.model.use_mask)
        self.assertFalse(self.widget.img_mask_btn.isChecked())

    def test_configuration_selected_changes_mask_transparency(self):
        click_button(self.widget.img_mask_btn)
        self.model.add_configuration()
        click_button(self.widget.img_mask_btn)
        click_checkbox(self.widget.mask_transparent_cb)
        self.assertTrue(self.model.transparent_mask)

        self.model.select_configuration(0)
        self.assertFalse(self.model.transparent_mask)
        self.assertFalse(self.widget.mask_transparent_cb.isChecked())

    def test_configuration_selected_changed_autoprocessing_of_images(self):
        click_checkbox(self.widget.autoprocess_cb)
        self.model.add_configuration()

        self.assertFalse(self.model.img_model.autoprocess)
        self.assertFalse(self.widget.autoprocess_cb.isChecked())

        self.model.select_configuration(0)
        self.assertTrue(self.model.img_model.autoprocess)
        self.assertTrue(self.widget.autoprocess_cb.isChecked())

    def test_configuration_selected_changes_calibration_name(self):
        self.model.calibration_model.calibration_name = "calib1"
        self.model.add_configuration()
        self.model.calibration_model.calibration_name = "calib2"

        self.model.select_configuration(0)
        self.assertEqual(str(self.widget.calibration_lbl.text()), "calib1")

        self.model.select_configuration(1)
        self.assertEqual(str(self.widget.calibration_lbl.text()), "calib2")

    def test_configuration_selected_updates_mask_plot(self):
        self.model.mask_model.add_mask(os.path.join(unittest_data_path, 'test.mask'))
        click_button(self.widget.img_mask_btn)
        first_mask = self.model.mask_model.get_img()
        self.model.add_configuration()
        self.assertFalse(self.widget.img_mask_btn.isChecked())

        self.model.mask_model.mask_below_threshold(self.model.img_data, 1)
        second_mask = self.model.mask_model.get_img()
        click_button(self.widget.img_mask_btn)

        self.model.select_configuration(0)
        self.assertEqual(np.sum(self.widget.img_widget.mask_img_item.image - first_mask), 0)
        self.model.select_configuration(1)
        self.assertEqual(np.sum(self.widget.img_widget.mask_img_item.image - second_mask), 0)

    def test_configuration_selected_updates_mask_transparency(self):
        self.model.mask_model.add_mask(os.path.join(unittest_data_path, 'test.mask'))
        click_button(self.widget.img_mask_btn)
        self.model.add_configuration()

        self.assertFalse(self.widget.img_mask_btn.isChecked())
        self.assertFalse(self.widget.mask_transparent_cb.isVisible())

    def test_configuration_selected_updates_roi_mode(self):
        click_button(self.widget.img_roi_btn)
        self.assertTrue(self.widget.img_roi_btn.isChecked())
        self.assertTrue(self.widget.img_widget.roi in self.widget.img_widget.img_view_box.addedItems)

        self.model.add_configuration()
        self.assertFalse(self.widget.img_roi_btn.isChecked())
        self.assertFalse(self.widget.img_widget.roi in self.widget.img_widget.img_view_box.addedItems)

    def test_mask_button_checking_in_image_mode(self):
        click_button(self.widget.img_mask_btn)
        self.assertTrue(self.widget.img_mask_btn.isChecked())
        click_button(self.widget.img_mask_btn)
        self.assertFalse(self.widget.img_mask_btn.isChecked())

    def test_mask_button_checking_in_cake_mode(self):
        self.load_pilatus1M_image_and_calibration()
        click_button(self.widget.integration_image_widget.mode_btn)

        click_button(self.widget.img_mask_btn)
        self.assertTrue(self.widget.img_mask_btn.isChecked())
        click_button(self.widget.img_mask_btn)
        self.assertFalse(self.widget.img_mask_btn.isChecked())

    def test_adding_images(self):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(unittest_data_path, 'image_001.tif')])
        click_button(self.widget.load_img_btn)
        data1 = np.copy(self.widget.img_widget.img_data).astype(np.uint32)
        click_checkbox(self.widget.img_batch_mode_add_rb)
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(
            return_value=[os.path.join(unittest_data_path, 'image_001.tif'),
                          os.path.join(unittest_data_path, 'image_001.tif')])
        click_button(self.widget.load_img_btn)
        self.assertTrue(np.array_equal(2 * data1, self.widget.img_widget.img_data))

    def test_load_image_with_manual_input_file_name(self):
        file_name = os.path.join(unittest_data_path, 'LaB6_40keV_MarCCD.tif')
        self.widget.img_filename_txt.setText(file_name)
        self.controller.filename_txt_changed()
        old_data = np.copy(self.model.img_data)
        file_name = os.path.join(unittest_data_path, 'CeO2_Pilatus1M.tif')
        self.widget.img_filename_txt.setText(file_name)
        self.controller.filename_txt_changed()
        new_data = self.model.img_data
        self.assertFalse(np.array_equal(old_data, new_data))

    def test_changing_cake_integral_width(self):
        self.load_pilatus1M_image_and_calibration()
        click_button(self.widget.integration_image_widget.mode_btn)
        self.controller.img_mouse_click(100, 300)

        x = self.widget.cake_widget.cake_integral_item.xData
        self.widget.integration_control_widget.integration_options_widget.cake_integral_width_sb.setValue(3)
        self.controller.img_mouse_click(100, 300)
        self.assertFalse(np.array_equal(x, self.widget.cake_widget.cake_integral_item.xData))

    def test_clicking_cake_image(self):
        self.load_pilatus1M_image_and_calibration()
        click_button(self.widget.integration_image_widget.mode_btn)
        self.widget.integration_image_widget.img_view.mouse_left_clicked.emit(30, 40)

    def test_click_image_sends_tth_changed_signal(self):
        self.load_pilatus1M_image_and_calibration()
        self.model.clicked_tth_changed.emit = MagicMock()
        self.widget.integration_image_widget.img_view.mouse_left_clicked.emit(600, 400)
        self.model.clicked_tth_changed.emit.assert_called()

    def test_click_cake_sends_tth_changed_signal(self):
        self.load_pilatus1M_image_and_calibration()
        self.model.clicked_tth_changed.emit = MagicMock()
        click_button(self.widget.integration_image_widget.mode_btn)
        self.widget.integration_image_widget.cake_view.mouse_left_clicked.emit(1100, 50)
        self.model.clicked_tth_changed.emit.assert_called_once_with(get_partial_value(self.model.cake_tth, 1100 - 0.5))

    def test_clicked_tth_changed(self):
        self.load_pilatus1M_image_and_calibration()
        self.widget.integration_image_widget.img_view.mouse_left_clicked.emit(600, 400)
        before_circle_data = self.widget.integration_image_widget.img_view.circle_plot_items[0].getData()
        self.model.clicked_tth_changed.emit(10)
        after_circle_data = self.widget.integration_image_widget.img_view.circle_plot_items[0].getData()
        self.assertFalse(np.array_equal(before_circle_data, after_circle_data))

    def test_circle_scatter_is_activated_correctly(self):
        self.model.clicked_tth_changed.emit(10)
        self.assertFalse(self.widget.img_widget.circle_plot_items[0] in self.widget.img_widget.img_view_box.addedItems)

        self.load_pilatus1M_image_and_calibration()
        self.model.clicked_tth_changed.emit(10)
        self.assertTrue(self.widget.img_widget.circle_plot_items[0] in self.widget.img_widget.img_view_box.addedItems)

    def test_loading_series_karabo_file_shows_correct_gui(self):
        from dioptas.model.loader.KaraboLoader import karabo_installed
        if not karabo_installed:
            return
        filename = os.path.join(unittest_data_path, 'karabo_epix.h5')
        file_widget = self.widget.integration_control_widget.img_control_widget.file_widget
        self.widget.show()
        self.assertFalse(file_widget.step_series_widget.isVisible())
        self.model.img_model.load(filename)
        self.assertTrue(file_widget.step_series_widget.isVisible())

    def test_fileinfo_and_move_button_visibility(self):
        from dioptas.model.loader.KaraboLoader import karabo_installed
        if not karabo_installed:
            return
        filename = os.path.join(unittest_data_path, 'image_001.tif')
        self.widget.show()
        self.model.img_model.load(filename)
        self.assertFalse(self.widget.file_info_btn.isVisible())
        self.assertFalse(self.widget.file_info_btn.isVisible())

        filename = os.path.join(unittest_data_path, 'TransferCorrection', 'original.tif')
        self.model.img_model.load(filename)
        self.assertTrue(self.widget.file_info_btn.isVisible())
        self.assertTrue(self.widget.file_info_btn.isVisible())

    def test_sources_for_hdf5_files(self):
        file_widget = self.widget.integration_control_widget.img_control_widget.file_widget
        self.widget.show()
        self.assertFalse(file_widget.sources_widget.isVisible())

        # load file with different sources
        filename = os.path.join(unittest_data_path, 'hdf5_dataset', 'ma4500_demoh5.h5')
        self.model.img_model.load(filename)
        self.assertTrue(file_widget.sources_widget.isVisible())

        # load file without sources
        filename = os.path.join(unittest_data_path, 'image_001.tif')
        self.model.img_model.load(filename)
        self.assertFalse(file_widget.sources_widget.isVisible())

    def test_sources_are_updated_in_sources_combobox(self):
        file_widget = self.widget.integration_control_widget.img_control_widget.file_widget
        filename = os.path.join(unittest_data_path, 'hdf5_dataset', 'ma4500_demoh5.h5')
        self.model.img_model.load(filename)

        self.assertGreater(file_widget.sources_cb.count(), 0)
        self.assertEqual(file_widget.sources_cb.count(), len(self.model.img_model.sources))

        file_widget.sources_cb.setCurrentIndex(2)
        self.assertEqual(file_widget.sources_cb.currentText(), self.model.img_model.sources[2])

    # UTILITY functions
    ########################

    def load_pilatus1M_image_and_calibration(self):
        file_name = os.path.join(unittest_data_path, 'CeO2_Pilatus1M.tif')
        self.model.img_model.load(file_name)
        calibration_file_name = os.path.join(unittest_data_path, 'CeO2_Pilatus1M.poni')
        self.model.calibration_model.load(calibration_file_name)
