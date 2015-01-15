# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import unittest
import sys
import os
import gc

from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from Controller.MainController import MainController


class IntegrationFunctionalTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.main_controller = MainController(use_settings=False)
        self.main_controller.calibration_controller.load_calibration('Data/LaB6_p49_40keV_006.poni', update_all=False)
        self.main_controller.calibration_controller.load_img('Data/LaB6_p49_40keV_006.tif')
        self.main_controller.view.tabWidget.setCurrentIndex(2)
        self.integration_view = self.main_controller.integration_controller.view
        self.calibration_data = self.main_controller.calibration_data
        self.img_data = self.main_controller.img_data
        self.mask_data = self.main_controller.mask_data

        self.integration_spectrum_controller = self.main_controller.integration_controller.spectrum_controller
        self.integration_image_controller = self.main_controller.integration_controller.image_controller

    def tearDown(self):

        del self.integration_spectrum_controller
        del self.integration_spectrum_controller
        del self.mask_data
        del self.img_data
        del self.calibration_data.cake_geometry
        del self.calibration_data.spectrum_geometry
        del self.calibration_data
        del self.integration_view
        del self.main_controller
        del self.app
        gc.collect()

    def enter_value_into_text_field(self, text_field, value):
        text_field.setText('')
        QTest.keyClicks(text_field, str(value))
        QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
        QtGui.QApplication.processEvents()

    def test_changing_number_of_integration_bins(self):
        # Edith wants to change the number of integration bins in order to see the effect of binning onto her line
        # shape. She sees that there is an option in the X tab and deselects automatic and sees that the sbinbox
        # becomes editable.
        self.main_controller.view.integration_widget.tabWidget.setCurrentIndex(4)
        self.assertFalse(self.integration_view.bin_count_txt.isEnabled())
        self.integration_view.automatic_binning_cb.setChecked(False)
        self.assertTrue(self.integration_view.bin_count_txt.isEnabled())

        # she sees that the current value and wants to double it and notices that the spectrum looks a little bit
        # smoother
        self.assertEqual(int(str(self.integration_view.bin_count_txt.text())), 2900)
        previous_number_of_points = len(self.main_controller.spectrum_data.spectrum._x)
        self.enter_value_into_text_field(self.integration_view.bin_count_txt, 2 * 2900)

        self.assertAlmostEqual(len(self.main_controller.spectrum_data.spectrum._x), 2 * previous_number_of_points,
                               delta=1)

        # then she decides that having an automatic estimation may probably be better and changes back to automatic.
        # immediately the number is restored and the image looks like when she started
        self.integration_view.automatic_binning_cb.setChecked(True)
        self.assertEqual(int(str(self.integration_view.bin_count_txt.text())), 2900)
        self.assertEqual(len(self.main_controller.spectrum_data.spectrum._x), previous_number_of_points)

    def test_changing_supersampling_amount_integrating_to_cake_with_mask(self):
        # Edith opens the program, calibrates everything and looks in to the options menu. She sees that there is a
        # miraculous parameter called supersampling. It is currently set to 1 which seems to be normal
        self.main_controller.view.integration_widget.tabWidget.setCurrentIndex(4)
        self.assertEqual(self.integration_view.supersampling_sb.value(), 1)

        # then she sets it to two and she sees that the number of spectrum bin changes and that the spectrum looks
        # smoother

        # values before:
        px1 = self.calibration_data.spectrum_geometry.pixel1
        px2 = self.calibration_data.spectrum_geometry.pixel2

        img_shape = self.img_data.img_data.shape

        self.integration_view.supersampling_sb.setValue(2)
        self.assertEqual(self.calibration_data.spectrum_geometry.pixel1, 0.5 * px1)
        self.assertEqual(self.calibration_data.spectrum_geometry.pixel2, 0.5 * px2)
        self.assertEqual(self.calibration_data.cake_geometry.pixel1, px1)
        self.assertEqual(self.calibration_data.cake_geometry.pixel2, px2)

        self.assertEqual(self.img_data.img_data.shape[0], 2*img_shape[0])
        self.assertEqual(self.img_data.img_data.shape[1], 2*img_shape[0])

        self.mask_data.load_mask('Data/test.mask')
        QTest.mouseClick(self.integration_view.img_mask_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.integration_view.img_mode_btn, QtCore.Qt.LeftButton)

    def test_saving_image(self):
        #Tests if the image save procedures are working for the different possible file endings
        self.main_controller.view.show()
        self.integration_image_controller.save_img('Data/Test_img.png')
        self.integration_image_controller.save_img('Data/Test_img.tiff')

        self.assertTrue(os.path.exists('Data/Test_img.png'))
        self.assertTrue(os.path.exists('Data/Test_img.tiff'))

        os.remove('Data/Test_img.png')
        os.remove('Data/Test_img.tiff')

    def test_saving_spectrum(self):
        self.main_controller.view.show()
        #Tests if the spectrum save procedures is are working for all fileendings
        def save_spectra_test_for_size_and_delete(self):
            self.integration_spectrum_controller.save_spectrum('Data/Test_spec.xy')
            self.integration_spectrum_controller.save_spectrum('Data/Test_spec.chi')
            self.integration_spectrum_controller.save_spectrum('Data/Test_spec.dat')
            self.integration_spectrum_controller.save_spectrum('Data/Test_spec.png')
            self.integration_spectrum_controller.save_spectrum('Data/Test_spec.svg')

            self.assertTrue(os.path.exists('Data/Test_spec.xy'))
            self.assertTrue(os.path.exists('Data/Test_spec.chi'))
            self.assertTrue(os.path.exists('Data/Test_spec.dat'))
            self.assertTrue(os.path.exists('Data/Test_spec.png'))
            self.assertTrue(os.path.exists('Data/Test_spec.svg'))

            self.assertGreater(os.stat('Data/Test_spec.xy').st_size, 1)
            self.assertGreater(os.stat('Data/Test_spec.chi').st_size, 1)
            self.assertGreater(os.stat('Data/Test_spec.dat').st_size, 1)
            self.assertGreater(os.stat('Data/Test_spec.png').st_size, 1)
            self.assertGreater(os.stat('Data/Test_spec.svg').st_size, 1)

            os.remove('Data/Test_spec.xy')
            os.remove('Data/Test_spec.chi')
            os.remove('Data/Test_spec.dat')
            os.remove('Data/Test_spec.png')
            os.remove('Data/Test_spec.svg')

        save_spectra_test_for_size_and_delete(self)
        QTest.mouseClick(self.integration_spectrum_controller.view.spec_q_btn, QtCore.Qt.LeftButton)
        save_spectra_test_for_size_and_delete(self)
        QTest.mouseClick(self.integration_spectrum_controller.view.spec_d_btn, QtCore.Qt.LeftButton)
        save_spectra_test_for_size_and_delete(self)

    def test_undocking_and_docking_img_frame(self):
        QTest.mouseClick(self.integration_view.img_dock_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.integration_view.img_dock_btn, QtCore.Qt.LeftButton)


