# -*- coding: utf8 -*-

import os, sys
import gc
from ..utility import QtTest, click_button
from ..exceptionhook import excepthook

import mock
from mock import MagicMock
import numpy as np
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ...controller.integration import IntegrationController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget
from ...controller.integration import MapController
from ...controller.integration import PatternController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class IntegrationControllerTest(QtTest):
    def setUp(self):
        sys.excepthook = excepthook
        self.model = DioptasModel()

        self.widget = IntegrationWidget()
        self.integration_controller = IntegrationController({'spectrum': data_path,
                                                             'image': data_path},
                                                            widget=self.widget,
                                                            dioptas_model=self.model)
        # self.image_controller = self.integration_controller.image_controller
        # self.pattern_controller = PatternController({}, self.widget, self.model)
        # self.map_controller = MapController({}, self.widget, self.model)
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

    def tearDown(self):
        del self.integration_controller
        # del self.image_controller
        del self.model
        del self.widget
        gc.collect()

    def _setup_map_batch_integration(self):
        # setting up filenames and working directories
        map_path = os.path.join(data_path, 'map')
        map_file_names = [f for f in os.listdir(map_path) if os.path.isfile(os.path.join(map_path, f))]
        map_file_paths = []
        for file_name in map_file_names:
            map_file_paths.append(os.path.join(map_path, file_name))
        working_dir = os.path.join(map_path, 'patterns2')
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)
        self.integration_controller.image_controller.working_dir['spectrum'] = os.path.join(working_dir)
        self.widget.spec_autocreate_cb.setChecked(True)
        return map_file_paths, map_file_names, working_dir

    def helper_delete_integrated_map_files_and_working_directory(self, file_names, working_dir):
        for file_name in file_names:
            os.remove(os.path.join(working_dir, file_name.split('.')[0] + '.xy'))
        os.rmdir(working_dir)

    def test_map_batch_integration_of_multiple_files(self, delete_upon_finish=True):
        map_file_paths, map_file_names, working_dir = self._setup_map_batch_integration()
        click_button(self.widget.map_2D_btn)
        self.assertTrue(self.widget.img_batch_mode_map_rb.isChecked())
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=map_file_paths)
        click_button(self.widget.load_img_btn)
        print(self.widget.map_2D_widget.spec_plot)

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




