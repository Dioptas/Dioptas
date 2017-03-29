# -*- coding: utf8 -*-

import os
import gc
from ..utility import QtTest, click_button

import mock
from mock import MagicMock
import numpy as np
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest
import time

from ...controller.integration import IntegrationController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


class IntegrationControllerTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()

        # setting up the calibration model but mocking the integration for speed
        self.model.calibration_model.num_points = 1000
        dummy_x = np.linspace(0, 25, 1000)
        dummy_y = np.sin(dummy_x)
        self.model.calibration_model.integrate_1d = mock.Mock(return_value=(dummy_x, dummy_y))

        self.widget = IntegrationWidget()
        self.integration_controller = IntegrationController({'spectrum': data_path,
                                                             'image': data_path},
                                                            widget=self.widget,
                                                            dioptas_model=self.model)
        self.image_controller = self.integration_controller.image_controller
        self.model.calibration_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.poni'))
        self.model.img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))

    def tearDown(self):
        del self.integration_controller
        del self.image_controller
        del self.model
        del self.widget
        gc.collect()

    def _setup_batch_integration(self):
        # setting up filenames and working directories
        filenames = ['image_001.tif', 'image_002.tif']
        input_filenames = [os.path.join(data_path, f) for f in filenames]
        working_dir = os.path.join(data_path, 'out')
        if not os.path.exists(working_dir):
            os.mkdir(working_dir)
        self.image_controller.working_dir['spectrum'] = os.path.join(working_dir)
        self.widget.spec_autocreate_cb.setChecked(True)

        return filenames, input_filenames, working_dir

    def test_batch_integration_of_multiple_files(self):
        filenames, input_filenames, working_dir = self._setup_batch_integration()

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=input_filenames)
        click_button(self.widget.load_img_btn)

        for filename in filenames:
            filename = filename.split('.')[0] + '.xy'
            filepath = os.path.join(working_dir, filename)
            self.assertTrue(os.path.exists(filepath))
            os.remove(filepath)
        # cleaning up
        os.rmdir(working_dir)

    def test_batch_integration_with_automatic_background_subtraction(self):
        filenames, input_filenames, working_dir = self._setup_batch_integration()
        self.widget.bkg_spectrum_gb.setChecked(True)

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=input_filenames)
        click_button(self.widget.load_img_btn)

        self.assertTrue(os.path.exists(os.path.join(working_dir, 'bkg_subtracted')))

        # check if two kind of files have been saved
        for filename in filenames:
            filename = filename.split('.')[0] + '.xy'

            orig_filepath = os.path.join(working_dir, filename)
            self.assertTrue(os.path.exists(orig_filepath))
            os.remove(orig_filepath)

            bkg_subtracted_filepath = os.path.join(working_dir, 'bkg_subtracted', filename)
            self.assertTrue(os.path.exists(bkg_subtracted_filepath))
            os.remove(bkg_subtracted_filepath)

        os.rmdir(os.path.join(working_dir, 'bkg_subtracted'))
        os.rmdir(working_dir)

    def test_switching_to_cake_mode_without_having_clicked_the_image_before(self):
        QTest.mouseClick(self.widget.img_mode_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.widget.img_mode_btn, QtCore.Qt.LeftButton)

    def test_cake_changes_axes(self):
        self.assertEqual(self.widget.integration_image_widget.mode_btn.text(), 'Cake')
        self.assertEqual(self.widget.integration_image_widget.img_view.left_axis_image,
                         self.widget.integration_image_widget.img_view.pg_layout.getItem(1, 0))
        self.widget.integration_image_widget.mode_btn.click()  # change to cake mode
        self.assertEqual(self.widget.integration_image_widget.mode_btn.text(), 'Image')
        self.assertEqual(self.widget.integration_image_widget.img_view.left_axis_cake,
                         self.widget.integration_image_widget.img_view.pg_layout.getItem(1, 0))

    def test_cake_zoom_changes_axes_scale(self):
        self.widget.integration_image_widget.mode_btn.click()
        self.assertEqual(self.widget.integration_image_widget.mode_btn.text(), 'Image')
        print(self.widget.integration_image_widget.img_view.left_axis_cake.range)
        print(self.widget.integration_image_widget.img_view.img_view_box.viewRange())
        rect = QtCore.QRectF(512, 512, 512, 512)
        self.widget.integration_image_widget.img_view.img_view_box.setRange(rect)
        self.widget.integration_image_widget.img_view.img_view_box.setRange(rect)  # for some reason must run twice

        print(self.widget.integration_image_widget.img_view.left_axis_cake.range)
        print(self.widget.integration_image_widget.img_view.img_view_box.viewRange())
        print(self.widget.integration_image_widget.img_view.img_view_box.viewRect())
        self.assertEqual(self.widget.integration_image_widget.img_view.img_view_box.viewRect(), rect)
