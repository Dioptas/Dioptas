# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'Clemens Prescher'
import unittest
import os
import gc
import sys

import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest

from model.Helper import jcpds
from model.CalibrationModel import CalibrationModel
from controller.integration import JcpdsEditorController
from controller import MainController



unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')
jcpds_path = os.path.join(data_path, 'jcpds')

def calculate_cubic_d_spacing(h, k, l, a):
    d_squared_inv = (h ** 2 + k ** 2 + l ** 2) / a ** 2
    return np.sqrt(1. / d_squared_inv)


class JcpdsEditorFunctionalTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.calibration_model = CalibrationModel()
        self.jcpds = jcpds()

    def tearDown(self):
        try:
            del self.calibration_model.cake_geometry
        except:
            pass

        try:
            del self.calibration_model.spectrum_geometry
        except:
            pass

        try:
            del self.main_controller.calibration_model.cake_geometry
        except:
            pass

        try:
            del self.main_controller.calibration_model.spectrum_geometry
        except:
            pass
        del self.app
        del self.calibration_model
        del self.jcpds
        gc.collect()

    def enter_value_into_text_field(self, text_field, value):
        text_field.setText('')
        QTest.keyClicks(text_field, str(value))
        QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
        QtGui.QApplication.processEvents()

    def enter_value_into_spinbox(self, spinbox, value):
        spinbox.setValue(value)
        QtGui.QApplication.processEvents()

    def set_symmetry(self, symmetry):
        self.jcpds_view.symmetry_cb.setCurrentIndex(self.jcpds_view.symmetries.index(symmetry))
        QtGui.QApplication.processEvents()

    def get_reflection_table_value(self, row, col):
        item = self.jcpds_view.reflection_table.item(row, col)
        return float(str(item.text()))

    def insert_reflection_table_value(self, row, col, value):
        item = self.jcpds_view.reflection_table.item(row, col)
        item.setText(str(value))

    def get_phase_line_position(self, phase_ind, line_ind):
        return self.main_controller.integration_controller.widget.spectrum_view.phases[phase_ind]. \
            line_items[line_ind].getData()[0][0]

    def compare_line_position(self, prev_line_pos, phase_ind, line_ind):
        new_line_pos = self.get_phase_line_position(phase_ind, line_ind)
        self.assertNotAlmostEqual(prev_line_pos, new_line_pos)
        return new_line_pos

    def convert_d_to_twotheta(self, d, wavelength):
        return np.arcsin(wavelength / (2 * d)) / np.pi * 360

    def test_correctly_displays_parameters_and_can_be_edited(self):
        # Erwin has selected a gold jcpds in the Dioptas interface with cubic symmetry
        # and wants to edit the parameters
        self.jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        self.calibration_model.spectrum_geometry.wavelength = 0.31

        self.jcpds_controller = JcpdsEditorController(jcpds_path, None,  self.calibration_model, self.jcpds)
        self.jcpds_view = self.jcpds_controller.widget

        # Erwin immediately sees the filename in the explorer
        self.assertEqual(str(self.jcpds_view.filename_txt.text()),
                         os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        # and the comment from which paper the data was derived
        self.assertEqual(str(self.jcpds_view.comments_txt.text()),
                         'Gold (04-0784, Anderson et al J Appl Phys 65, 1534, 1989)')

        # Erwin checks the parameters of the phase
        symmetry = str(self.jcpds_view.symmetry_cb.currentText())
        self.assertEqual(symmetry.upper(), 'CUBIC')

        a = float(str(self.jcpds_view.lattice_a_sb.text()))
        b = float(str(self.jcpds_view.lattice_b_sb.text()))
        c = float(str(self.jcpds_view.lattice_c_sb.text()))

        self.assertEqual(a, 4.07860)
        self.assertEqual(b, 4.07860)
        self.assertEqual(c, 4.07860)

        V = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertAlmostEqual(V, a * b * c, delta=0.0001)

        alpha = float(str(self.jcpds_view.lattice_alpha_sb.text()))
        beta = float(str(self.jcpds_view.lattice_beta_sb.text()))
        gamma = float(str(self.jcpds_view.lattice_gamma_sb.text()))

        self.assertEqual(alpha, 90)
        self.assertEqual(beta, 90)
        self.assertEqual(gamma, 90)

        K0 = float(str(self.jcpds_view.eos_K_txt.text()))
        Kp = float(str(self.jcpds_view.eos_Kp_txt.text()))
        alphaT = float(str(self.jcpds_view.eos_alphaT_txt.text()))
        dalpha_dt = float(str(self.jcpds_view.eos_dalphadT_txt.text()))
        dK_dt = float(str(self.jcpds_view.eos_dKdT_txt.text()))
        dKp_dt = float(str(self.jcpds_view.eos_dKpdT_txt.text()))

        self.assertEqual(K0, 166.65)
        self.assertEqual(Kp, 5.4823)
        self.assertEqual(alphaT, 4.26e-5)
        self.assertEqual(dalpha_dt, 0)
        self.assertEqual(dK_dt, 0)
        self.assertEqual(dKp_dt, 0)

        # then he decides to put a new lattice parameter into the a box and realizes that all
        # others are changing too.
        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 4.08)
        QtGui.QApplication.processEvents()
        a = float(str(self.jcpds_view.lattice_a_sb.text()))
        b = float(str(self.jcpds_view.lattice_b_sb.text()))
        c = float(str(self.jcpds_view.lattice_c_sb.text()))
        self.assertEqual(a, 4.08)
        self.assertEqual(b, 4.08)
        self.assertEqual(c, 4.08)

        # then he tries to type something into b even though it is a cubic phase,
        # however he cannot because it is disabled
        self.assertEqual(self.jcpds_view.lattice_b_sb.isEnabled(), False)

        # then he realizes that he needs to change the symmetry first to be able to
        # change additional lattice parameters. This then magically enables to change the lattice parameters but still
        # not the angles
        self.set_symmetry('orthorhombic')

        self.assertEqual(self.jcpds_view.lattice_b_sb.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_c_sb.isEnabled(), True)

        self.assertEqual(self.jcpds_view.lattice_alpha_sb.isEnabled(), False)
        self.assertEqual(self.jcpds_view.lattice_beta_sb.isEnabled(), False)
        self.assertEqual(self.jcpds_view.lattice_gamma_sb.isEnabled(), False)

        # then he changes the different a,b,c values and notices that the volume changes
        self.enter_value_into_spinbox(self.jcpds_view.lattice_b_sb, 5)
        self.enter_value_into_spinbox(self.jcpds_view.lattice_c_sb, 6)

        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_volume_txt.text())), 5 * 6 * 4.08)

        # he notices that the system is a smart editor shows ratios of lattice parameters:

        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_ab_sb.text())), 4.08 / 5)
        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_ca_sb.text())), 6.0 / 4.08, delta=0.0001)
        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_cb_sb.text())), 6.0 / 5, delta=0.0001)

        # he decides to play with the ratios to be better able to fit it to the current spectrum:

        self.enter_value_into_spinbox(self.jcpds_view.lattice_ca_sb, 1.5)
        self.assertEqual(float(str(self.jcpds_view.lattice_a_sb.text())), 4.08)
        self.assertEqual(float(str(self.jcpds_view.lattice_c_sb.text())), 1.5 * 4.08)

        # then he set all values back again and
        #  plays a little bit with the symmetry and accidentally changes it to several different symmetries
        # and sees that the parameters change accordingly...
        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 4.08)
        self.enter_value_into_spinbox(self.jcpds_view.lattice_b_sb, 5)
        self.enter_value_into_spinbox(self.jcpds_view.lattice_c_sb, 6)

        self.set_symmetry("tetragonal")
        self.assertEqual(float(str(self.jcpds_view.lattice_b_sb.text())), 4.08)
        self.assertEqual(float(str(self.jcpds_view.lattice_c_sb.text())), 6)

        self.set_symmetry("hexagonal")
        self.assertEqual(float(str(self.jcpds_view.lattice_gamma_sb.text())), 120)
        self.set_symmetry("monoclinic")
        self.set_symmetry("rhombohedral")
        self.set_symmetry("orthorhombic")

        # now he wants to have full control over the unit cell and sees how the volume changes when he changes the
        # angles

        self.set_symmetry("triclinic")
        self.assertEqual(self.jcpds_view.lattice_a_sb.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_b_sb.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_c_sb.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_alpha_sb.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_beta_sb.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_gamma_sb.isEnabled(), True)

        old_volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.enter_value_into_spinbox(self.jcpds_view.lattice_alpha_sb, 70)
        volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertNotEqual(old_volume, volume)

        old_volume = volume
        self.enter_value_into_spinbox(self.jcpds_view.lattice_beta_sb, 70)
        volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertNotEqual(old_volume, volume)

        old_volume = volume
        self.enter_value_into_spinbox(self.jcpds_view.lattice_gamma_sb, 70)
        volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertNotEqual(old_volume, volume)

        # He sees that the equation of state parameters in the file are not correct and enters new values:
        self.enter_value_into_text_field(self.jcpds_view.eos_K_txt, 200)
        self.enter_value_into_text_field(self.jcpds_view.eos_Kp_txt, 5)
        self.enter_value_into_text_field(self.jcpds_view.eos_alphaT_txt, .23e-5)
        self.enter_value_into_text_field(self.jcpds_view.eos_dalphadT_txt, .1e-6)
        self.enter_value_into_text_field(self.jcpds_view.eos_dKdT_txt, 0.003)
        self.enter_value_into_text_field(self.jcpds_view.eos_dKpdT_txt, 0.1e-5)

        self.assertAlmostEqual(self.jcpds.k0, 200)
        self.assertAlmostEqual(self.jcpds.k0p0, 5)
        self.assertAlmostEqual(self.jcpds.alpha_t0, .23e-5)
        self.assertAlmostEqual(self.jcpds.d_alpha_dt, .1e-6)
        self.assertAlmostEqual(self.jcpds.dk0dt, 0.003)
        self.assertAlmostEqual(self.jcpds.dk0pdt, .1e-5)

    def test_reflection_editing_and_saving_of_files(self):
        # Erwin has selected a gold jcpds in the Dioptas interface with cubic symmetry
        # and wants to look for the reflections entered
        self.jcpds = jcpds()
        self.jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        self.jcpds_controller = JcpdsEditorController(jcpds_path, None, jcpds_phase=self.jcpds)
        self.jcpds_view = self.jcpds_controller.widget

        # he sees that there are 13 reflections predefined in the table

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)

        # he checks if the values are correct:

        self.assertAlmostEqual(self.get_reflection_table_value(0, 4), 2.355, delta=0.001)
        self.assertEqual(self.get_reflection_table_value(1, 1), 0)
        self.assertAlmostEqual(self.get_reflection_table_value(12, 4), 0.6449, delta=0.0001)
        self.assertEqual(self.get_reflection_table_value(12, 3), 10)

        # then he decides to change the lattice parameter and sees that the values in the table are changing:
        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 4)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)
        self.assertEqual(self.get_reflection_table_value(1, 4), 2)

        # After playing with the lattice parameter he sets it back to the original value and looks at the reflections
        # He thinks that he doesn't need the sixth reflection because it any way has to low intensity
        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 4.0786)
        self.jcpds_view.reflection_table.selectRow(5)
        QTest.mouseClick(self.jcpds_view.reflections_delete_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 12)
        self.assertAlmostEqual(self.get_reflection_table_value(5, 4), 0.9358, delta=0.0002)
        self.assertEqual(len(self.jcpds.reflections), 12)

        # then he changed his mind and wants to add the reflection back:

        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()

        self.assertEqual(len(self.jcpds.reflections), 13)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)
        self.assertEqual(self.jcpds_view.get_selected_reflections()[0], 12)

        self.assertEqual(self.get_reflection_table_value(12, 0), 0)  # h
        self.assertEqual(self.get_reflection_table_value(12, 1), 0)  # k
        self.assertEqual(self.get_reflection_table_value(12, 2), 0)  # l
        self.assertEqual(self.get_reflection_table_value(12, 3), 0)  # intensity
        self.assertEqual(self.get_reflection_table_value(12, 4), 0)  # d

        # then he edits he and realizes how the d spacings are magically calculated

        self.insert_reflection_table_value(12, 0, 1)
        self.assertEqual(self.get_reflection_table_value(12, 4), 4.0786)
        self.insert_reflection_table_value(12, 1, 1)
        self.assertAlmostEqual(self.get_reflection_table_value(12, 4),
                               calculate_cubic_d_spacing(1, 1, 0, 4.0786),
                               delta=0.0001)
        self.insert_reflection_table_value(12, 2, 3)
        self.assertAlmostEqual(self.get_reflection_table_value(12, 4),
                               calculate_cubic_d_spacing(1, 1, 3, 4.0786),
                               delta=0.0001)

        # then she decides that everybody should screw with the table and clears it:

        QTest.mouseClick(self.jcpds_view.reflections_clear_btn, QtCore.Qt.LeftButton)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 0)
        self.assertEqual(len(self.jcpds.reflections), 0)
        self.assertEqual(len(self.jcpds_view.get_selected_reflections()), 0)

        # he finds this phase much more promising and wants to give it a new name
        self.enter_value_into_text_field(self.jcpds_view.comments_txt,
                                         'HAHA this is a phase you will never see in your spectrum')
        self.assertEqual(self.jcpds.comments[0], 'HAHA this is a phase you will never see in your spectrum')

        # then he sees the save_as button and is happy to save his non-sense for later users
        filename = os.path.join(jcpds_path,'au_mal_anders.jcpds')
        self.jcpds_controller.save_as_btn_clicked(filename)
        self.assertTrue(os.path.exists(filename))

        # he decides to change the lattice parameter and then reload the file to see if everything is ok
        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 10)

        self.jcpds.load_file(filename)
        self.jcpds_controller = JcpdsEditorController(jcpds_path, None, jcpds_phase=self.jcpds)
        self.jcpds_view = self.jcpds_controller.widget
        self.assertEqual(float(str(self.jcpds_view.lattice_a_sb.text())), 4.0786)
        self.assertEqual(float(str(self.jcpds_view.lattice_b_sb.text())), 4.0786)
        self.assertEqual(float(str(self.jcpds_view.lattice_c_sb.text())), 4.0786)

        # then he decides to make this phase it little bit more useful and adds some peaks and saves this as a different
        # version and trys to load it again...

        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)

        self.insert_reflection_table_value(0, 0, 1)
        self.insert_reflection_table_value(0, 3, 100)
        self.insert_reflection_table_value(1, 1, 1)
        self.insert_reflection_table_value(1, 3, 50)
        self.insert_reflection_table_value(2, 2, 1)
        self.insert_reflection_table_value(2, 3, 20)

        filename = os.path.join(jcpds_path, 'au_mal_anders_vers2.jcpds')
        self.jcpds_controller.save_as_btn_clicked(filename)

        self.jcpds.load_file(filename)
        self.jcpds_controller = JcpdsEditorController(jcpds_path, None, jcpds_phase=self.jcpds)

    def test_connection_between_main_gui_and_jcpds_editor_lattice_and_eos_parameter(self):
        # Erwin opens up the program, loads image and calibration and some phases

        self.main_controller = MainController()
        self.main_controller.calibration_controller.load_calibration(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'),
                                                                     update_all=False)
        self.main_controller.calibration_controller.set_calibrant(7)
        self.main_controller.calibration_controller.load_img(os.path.join(data_path,'LaB6_40keV_MarCCD.tif'))
        self.main_controller.widget.tabWidget.setCurrentIndex(2)
        self.main_controller.widget.integration_widget.tabWidget.setCurrentIndex(3)
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path, 'au_Anderson.jcpds'))
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path, 'mo.jcpds'))
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path, 'ar.jcpds'))
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path, 're.jcpds'))

        self.phase_controller = self.main_controller.integration_controller.phase_controller
        self.jcpds_editor_controller = self.phase_controller.jcpds_editor_controller
        self.jcpds_view = self.jcpds_editor_controller.widget

        self.phase_controller.widget.phase_tw.selectRow(0)
        QTest.mouseClick(self.phase_controller.widget.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()
        self.assertTrue(self.jcpds_view.isActiveWindow())

        # He changes some parameter but then realizes that he screwed it up and presses cancel to revert all his changes

        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 10.4)

        self.assertAlmostEqual(self.phase_controller.phase_model.phases[0].a0, 10.4)
        QTest.mouseClick(self.jcpds_view.cancel_btn, QtCore.Qt.LeftButton)

        self.assertNotAlmostEqual(self.phase_controller.phase_model.phases[0].a0, 10.4)

        # Now he selects one phase in the phase table and starts the JCPDS editor and realizes he wanted to click another
        # phase --  so he just selects it without closing and reopening the editor
        # and magically the new parameters show up

        self.phase_controller.widget.phase_tw.selectRow(1)
        QTest.mouseClick(self.phase_controller.widget.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()

        self.phase_controller.widget.phase_tw.selectRow(2)
        self.assertTrue(float(str(self.jcpds_view.lattice_a_sb.text())), 5.51280)  # Argon lattice parameter

        # Now he changes the lattice parameter and wants to see if there is any change in the line position in the graph

        prev_line_pos = self.get_phase_line_position(2, 0)
        self.enter_value_into_spinbox(self.jcpds_view.lattice_a_sb, 3.4)
        QtGui.QApplication.processEvents()
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        # now he decides to have full control, changes the structure to TRICLINIC and plays with all parameters:

        self.set_symmetry('triclinic')

        self.enter_value_into_spinbox(self.jcpds_view.lattice_b_sb, 3.2)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_c_sb, 3.1)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_ab_sb, 1.6)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_ca_sb, 1.9)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_ab_sb, 0.3)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_alpha_sb, 70)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_beta_sb, 70)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_spinbox(self.jcpds_view.lattice_gamma_sb, 70)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        # then he increases the pressure and sees the line moving, but he realizes that the equation of state may 
        # be wrong so he decides to change the parameters in the jcpds-editor
        self.main_controller.integration_controller.widget.phase_pressure_sb.setValue(10)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_text_field(self.jcpds_view.eos_K_txt, 120)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_text_field(self.jcpds_view.eos_Kp_txt, 6)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        # he decides to change temperature value and play with all equation of state parameters
        self.enter_value_into_text_field(self.jcpds_view.eos_alphaT_txt, 6.234e-5)
        self.assertEqual(self.phase_controller.phase_model.phases[2].alpha_t0, 6.234e-5)

        self.main_controller.integration_controller.widget.phase_temperature_sb.setValue(1300)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_text_field(self.jcpds_view.eos_alphaT_txt, 10.234e-5)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_text_field(self.jcpds_view.eos_dalphadT_txt, 10.234e-6)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_text_field(self.jcpds_view.eos_dKdT_txt, 1.2e-4)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)

        self.enter_value_into_text_field(self.jcpds_view.eos_dKpdT_txt, 1.3e-6)
        prev_line_pos = self.compare_line_position(prev_line_pos, 2, 0)


    def test_connection_between_main_gui_and_jcpds_editor_reflections(self):
        # Erwin loads Dioptas with a previous calibration and image file then he adds several phases and looks into the
        # jcpds editor for the first phase. He sees that everything seems to be correct

        self.main_controller = MainController()
        self.main_controller.calibration_controller.load_calibration(os.path.join(data_path, 'LaB6_40keV_MarCCD.poni'),
                                                                     update_all=False)
        self.main_controller.calibration_controller.set_calibrant(7)
        self.main_controller.calibration_controller.load_img(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.main_controller.widget.tabWidget.setCurrentIndex(2)
        self.main_controller.widget.integration_widget.tabWidget.setCurrentIndex(3)
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path,'au_Anderson.jcpds'))
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path,'mo.jcpds'))
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path,'ar.jcpds'))
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path,'re.jcpds'))

        self.phase_controller = self.main_controller.integration_controller.phase_controller
        self.jcpds_editor_controller = self.phase_controller.jcpds_editor_controller
        self.jcpds_view = self.jcpds_editor_controller.widget
        self.jcpds_phase = self.main_controller.phase_model.phases[0]
        self.jcpds_in_spec = self.main_controller.integration_controller.widget.spectrum_view.phases[0]

        self.phase_controller.widget.phase_tw.selectRow(0)
        QTest.mouseClick(self.phase_controller.widget.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)
        self.assertEqual(len(self.jcpds_phase.reflections), 13)
        self.assertEqual(len(self.jcpds_in_spec.line_items), 13)
        self.assertEqual(len(self.jcpds_in_spec.line_visible), 13)

        # then he decides to add another reflection to the jcpds file and sees that after changing the parameters it is
        # miraculously connected to the view

        #adding the reflection
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 14)
        self.assertEqual(len(self.jcpds_phase.reflections), 14)
        self.assertEqual(len(self.jcpds_in_spec.line_items), 14)
        self.assertEqual(len(self.jcpds_in_spec.line_visible), 14)

        # putting reasonable values into the reflection
        self.insert_reflection_table_value(13, 0, 1)
        self.insert_reflection_table_value(13, 3, 90)
        self.assertAlmostEqual(self.get_phase_line_position(0, 13), self.convert_d_to_twotheta(4.0786, 0.31),
                               delta=0.0005)

        #he looks through the reflection and sees that one is actually forbidden. Who has added this reflection to the
        # file? He decides to delete it

        self.jcpds_view.reflection_table.selectRow(5)

        QTest.mouseClick(self.jcpds_view.reflections_delete_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)
        self.assertEqual(len(self.jcpds_phase.reflections), 13)
        self.assertEqual(len(self.jcpds_in_spec.line_items), 13)
        self.assertEqual(len(self.jcpds_in_spec.line_visible), 13)

        #then he looks again at all reflection and does not like it so he decides to clear all of them and build them
        # up from sketch...

        QTest.mouseClick(self.jcpds_view.reflections_clear_btn, QtCore.Qt.LeftButton)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 0)
        self.assertEqual(len(self.jcpds_phase.reflections), 0)
        self.assertEqual(len(self.jcpds_in_spec.line_items), 0)
        self.assertEqual(len(self.jcpds_in_spec.line_visible), 0)

        # He adds some lines and sees the values change:

        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 4)
        self.assertEqual(len(self.jcpds_phase.reflections), 4)
        self.assertEqual(len(self.jcpds_in_spec.line_items), 4)
        self.assertEqual(len(self.jcpds_in_spec.line_visible), 4)


    def test_phase_name_difference_after_modified(self):
        self.main_controller = MainController(use_settings=False)
        self.main_controller.calibration_controller.load_calibration(os.path.join(data_path,'LaB6_40keV_MarCCD.poni'),
                                                                     update_all=False)
        self.main_controller.calibration_controller.set_calibrant(7)
        self.main_controller.calibration_controller.load_img(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.main_controller.widget.tabWidget.setCurrentIndex(2)
        self.main_controller.widget.integration_widget.tabWidget.setCurrentIndex(3)
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        # Erwin starts the software loads Gold and wants to see what is in the jcpds file, however since he does not
        # change anything the names every are the same...

        self.phase_controller = self.main_controller.integration_controller.phase_controller
        self.jcpds_editor_controller = self.phase_controller.jcpds_editor_controller
        self.jcpds_view = self.jcpds_editor_controller.widget
        self.jcpds_phase = self.main_controller.phase_model.phases[0]
        self.jcpds_in_spec = self.main_controller.integration_controller.widget.spectrum_view.phases[0]

        self.assertEqual('au_Anderson', self.jcpds_phase.name)
        self.assertEqual('au_Anderson', str(self.phase_controller.widget.phase_tw.item(0, 2).text()))
        self.phase_controller.widget.phase_tw.selectRow(0)
        QTest.mouseClick(self.phase_controller.widget.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()
        self.assertEqual('au_Anderson', self.jcpds_phase.name)
        self.assertEqual('au_Anderson', str(self.phase_controller.widget.phase_tw.item(0, 2).text()))


    def test_high_pressure_values_are_shown_in_jcpds_editor(self):
        self.main_controller = MainController(use_settings=False)
        self.main_controller.calibration_controller.load_calibration(os.path.join(data_path,'LaB6_40keV_MarCCD.poni'),
                                                                     update_all=False)
        self.main_controller.calibration_controller.set_calibrant(7)
        self.main_controller.calibration_controller.load_img(os.path.join(data_path, 'LaB6_40keV_MarCCD.tif'))
        self.main_controller.widget.tabWidget.setCurrentIndex(2)
        self.main_controller.widget.integration_widget.tabWidget.setCurrentIndex(3)
        self.main_controller.integration_controller.phase_controller.add_btn_click_callback(
            os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        # Erwin starts the software loads Gold and wants to see what is in the jcpds file, however since he does not

        self.phase_controller = self.main_controller.integration_controller.phase_controller
        self.jcpds_editor_controller = self.phase_controller.jcpds_editor_controller
        self.jcpds_view = self.jcpds_editor_controller.widget
        self.jcpds_phase = self.main_controller.phase_model.phases[0]
        self.jcpds_in_spec = self.main_controller.integration_controller.widget.spectrum_view.phases[0]

        self.phase_controller.widget.phase_tw.selectRow(0)
        QTest.mouseClick(self.phase_controller.widget.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()

        # he looks at the jcpds_editor and sees that there are not only hkl and intensity values for each reflection but
        # also d0, d, two_theta0 and two_theta
        # however, the zero values and non-zero values are all the same

        self.assertEqual(8, self.jcpds_view.reflection_table.columnCount())
        for row_ind in xrange(13):
            self.assertEqual(self.get_reflection_table_value(row_ind, 4), self.get_reflection_table_value(row_ind, 6))
            self.assertAlmostEqual(self.get_reflection_table_value(row_ind, 5),
                                   self.convert_d_to_twotheta(self.jcpds_phase.reflections[row_ind].d0, 0.31),
                                   delta=0.0001)
            self.assertEqual(self.get_reflection_table_value(row_ind, 5), self.get_reflection_table_value(row_ind, 7))

        # he further realizes that there are two sets of lattice parameters in the display, but both still show the same
        # values...

        self.assertEqual(float(self.jcpds_view.lattice_eos_a_txt.text()), self.jcpds_view.lattice_a_sb.value())
        self.assertEqual(float(self.jcpds_view.lattice_eos_b_txt.text()), self.jcpds_view.lattice_b_sb.value())
        self.assertEqual(float(self.jcpds_view.lattice_eos_c_txt.text()), self.jcpds_view.lattice_c_sb.value())
        self.assertEqual(float(self.jcpds_view.lattice_eos_volume_txt.text()),
                         float(self.jcpds_view.lattice_volume_txt.text()))

        #then he decides to increase pressure in the main_view and sees that the non "0" values resemble the high pressure
        # values

        self.phase_controller.widget.phase_pressure_sb.setValue(30)
        for row_ind in xrange(13):
            self.assertNotEqual(self.get_reflection_table_value(row_ind, 4), self.get_reflection_table_value(row_ind, 5))
            self.assertNotAlmostEqual(self.get_reflection_table_value(row_ind, 6),
                                   self.convert_d_to_twotheta(self.jcpds_phase.reflections[row_ind].d0, 0.31),
                                   delta=0.0001)
            self.assertNotEqual(self.get_reflection_table_value(row_ind,6),
                                self.get_reflection_table_value(row_ind,7))

        self.assertNotEqual(float(self.jcpds_view.lattice_eos_a_txt.text()), self.jcpds_view.lattice_a_sb.value())
        self.assertNotEqual(float(self.jcpds_view.lattice_eos_b_txt.text()), self.jcpds_view.lattice_b_sb.value())
        self.assertNotEqual(float(self.jcpds_view.lattice_eos_c_txt.text()), self.jcpds_view.lattice_c_sb.value())
        self.assertNotEqual(float(self.jcpds_view.lattice_eos_volume_txt.text()),
                         float(self.jcpds_view.lattice_volume_txt.text()))


if __name__ == '__main__':
    unittest.main()