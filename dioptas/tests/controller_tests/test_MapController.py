# -*- coding: utf8 -*-

import os
import gc
from ..utility import QtTest, click_button, unittest_data_path

from mock import MagicMock
from qtpy import QtWidgets

from ...controller.integration import IntegrationController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

jcpds_path = os.path.join(unittest_data_path, 'jcpds')


class MapControllerTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()
        self.model.working_directories['image'] = unittest_data_path
        self.model.working_directories['pattern'] = unittest_data_path
        self.model.working_directories['phase'] = unittest_data_path
        self.widget = IntegrationWidget()

        self.widget.map_2D_widget.show = MagicMock()

        self.integration_controller = IntegrationController(widget=self.widget, dioptas_model=self.model)

        self.model.calibration_model.load(os.path.join(unittest_data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(unittest_data_path, 'CeO2_Pilatus1M.tif'))

    def tearDown(self):
        del self.integration_controller
        del self.model
        del self.widget
        gc.collect()

    def _setup_map_batch_integration(self):
        # setting up filenames and working directories
        map_path = os.path.join(unittest_data_path, 'map')
        map_img_file_names = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        map_img_file_paths = [os.path.join(map_path, filename) for filename in map_img_file_names]
        working_dir = os.path.join(map_path, 'patterns')
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)
        self.model.working_directories['pattern'] = os.path.join(working_dir)
        self.widget.pattern_autocreate_cb.setChecked(True)
        return map_img_file_paths, map_img_file_names, working_dir

    @staticmethod
    def helper_delete_integrated_map_files_and_working_directory(file_names, working_dir):
        for file_name in file_names:
            os.remove(os.path.join(working_dir, file_name.split('.')[0] + '.xy'))
        os.rmdir(working_dir)

    def test_map_batch_integration_of_multiple_files(self, delete_upon_finish=True):
        map_file_paths, map_file_names, working_dir = self._setup_map_batch_integration()
        click_button(self.widget.map_2D_btn)
        self.assertTrue(self.widget.img_batch_mode_map_rb.isChecked())
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=map_file_paths)
        click_button(self.widget.load_img_btn)

        for filename in map_file_names:
            filename = filename.split('.')[0] + '.xy'
            file_path = os.path.join(working_dir, filename)
            self.assertTrue(os.path.exists(file_path))
        if delete_upon_finish:
            self.helper_delete_integrated_map_files_and_working_directory(map_file_names, working_dir)

    def test_adding_map_and_range_enables_map_functionality(self):
        self.assertFalse(self.widget.map_2D_widget.update_map_btn.isEnabled())
        self.test_map_batch_integration_of_multiple_files(delete_upon_finish=False)
        self.assertFalse(self.widget.map_2D_widget.update_map_btn.isEnabled())
        click_button(self.widget.map_2D_widget.roi_add_btn)
        self.assertTrue(self.widget.map_2D_widget.update_map_btn.isEnabled())

    def helper_add_range_at_pos(self, pos):
        current_count = self.widget.map_2D_widget.roi_list.count()
        self.integration_controller.pattern_controller.pattern_left_click(pos, 50.0)
        click_button(self.widget.map_2D_widget.roi_add_btn)
        self.assertEqual(self.widget.map_2D_widget.roi_list.count(), current_count + 1)

    def test_add_range_btn_adds_roi_in_correct_place(self):
        click_button(self.widget.map_2D_btn)
        click_position_x = 10.2
        self.helper_add_range_at_pos(click_position_x)
        roi_range = self.widget.map_2D_widget.roi_list.item(0).text().rsplit('_', 1)[-1]
        roi_center = (float(roi_range.split('-')[0]) + float(roi_range.split('-')[1]))/2.0
        self.assertAlmostEqual(roi_center, click_position_x, 5)

    def test_remove_roi_range_btn(self):
        click_button(self.widget.map_2D_btn)
        click_position_x = 10.2
        self.helper_add_range_at_pos(click_position_x)
        click_button(self.widget.map_2D_widget.roi_del_btn)
        self.assertEqual(self.widget.map_2D_widget.roi_list.count(), 0)

    def test_clear_roi_ranges_btn(self):
        click_button(self.widget.map_2D_btn)
        click_position_x = 10.2
        self.helper_add_range_at_pos(click_position_x)
        click_position_x = 11.8
        self.helper_add_range_at_pos(click_position_x)
        click_button(self.widget.map_2D_widget.roi_clear_btn)
        self.assertEqual(self.widget.map_2D_widget.roi_list.count(), 0)

    def test_select_all_btn(self):
        click_button(self.widget.map_2D_btn)
        click_position_x = 10.2
        self.helper_add_range_at_pos(click_position_x)
        click_position_x = 11.8
        self.helper_add_range_at_pos(click_position_x)
        selected_items = self.widget.map_2D_widget.roi_list.selectedItems()
        self.assertEqual(len(selected_items), 2)
        self.widget.map_2D_widget.roi_list.clearSelection()
        self.widget.map_2D_widget.roi_list.setCurrentItem(selected_items[1])
        self.assertEqual(len(self.widget.map_2D_widget.roi_list.selectedItems()), 1)
        click_button(self.widget.map_2D_widget.roi_select_all_btn)
        self.assertEqual(len(self.widget.map_2D_widget.roi_list.selectedItems()), 2)
        click_button(self.widget.map_2D_widget.roi_del_btn)
        self.assertEqual(len(self.widget.map_2D_widget.roi_list.selectedItems()), 0)

    def test_deleting_roi_renames_other_rois(self):
        click_button(self.widget.map_2D_btn)
        click_position_x = 10.2
        self.helper_add_range_at_pos(click_position_x)
        click_position_x = 11.8
        self.helper_add_range_at_pos(click_position_x)
        click_position_x = 14.5
        self.helper_add_range_at_pos(click_position_x)
        selected_items = self.widget.map_2D_widget.roi_list.selectedItems()
        self.widget.map_2D_widget.roi_list.clearSelection()
        self.widget.map_2D_widget.roi_list.setCurrentItem(selected_items[1])
        click_button(self.widget.map_2D_widget.roi_del_btn)
        self.assertEqual(self.widget.map_2D_widget.roi_list.count(), 2)
        roi_range = self.widget.map_2D_widget.roi_list.item(1).text().rsplit('_', 1)[-1]
        roi_center = (float(roi_range.split('-')[0]) + float(roi_range.split('-')[1])) / 2.0
        self.assertEqual(self.widget.map_2D_widget.roi_list.item(1).text().split('_')[0], 'B')
        self.assertAlmostEqual(roi_center, click_position_x, 5)

    def test_roi_add_phase_btn(self):
        click_button(self.widget.map_2D_btn)
        self.helper_load_phase('ar.jcpds')
        self.assertEqual(self.widget.phase_tw.rowCount(), 1)
        click_button(self.widget.map_2D_widget.roi_add_phase_btn)
        self.assertEqual(self.widget.map_2D_widget.roi_list.count(), 5)

        current_phase_ind = self.widget.phase_widget.get_selected_phase_row()
        phase_lines = self.model.phase_model.get_lines_d(current_phase_ind)
        xcenter = []
        for line in phase_lines[0:5]:
            xcenter.append(self.model.map_model.convert_units(line[0], 'd_A', self.model.map_model.units,
                                                              self.model.map_model.wavelength))

        for roi_item, xcen in zip(self.widget.map_2D_widget.roi_list.selectedItems(), xcenter):

            roi_range = roi_item.text().rsplit('_', 1)[-1]
            roi_center = (float(roi_range.split('-')[0]) + float(roi_range.split('-')[1])) / 2.0
            self.assertAlmostEqual(roi_center, xcen, 3)

    def helper_load_phase(self, filename):
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[os.path.join(jcpds_path, filename)])
        click_button(self.widget.phase_add_btn)

    def test_create_map_from_xy_files(self):
        map_path = os.path.join(unittest_data_path, 'map', 'xy')
        map_file_names = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        map_file_paths = []
        for file_name in map_file_names:
            map_file_paths.append(os.path.join(map_path, file_name))
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=map_file_paths)
        QtWidgets.QMessageBox = MagicMock()
        click_button(self.widget.map_2D_widget.load_ascii_files_btn)
        QtWidgets.QMessageBox.assert_called_once()
        self.assertTrue(len(self.model.map_model.map_data) > 0)
