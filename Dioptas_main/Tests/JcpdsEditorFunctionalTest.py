# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
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
import numpy as np
import os
import time

from Data.jcpds import jcpds
from Controller.JcpdsEditorController import JcpdsEditorController
from Controller.MainController import MainController
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest
import sys


def calculate_cubic_d_spacing(h,k,l,a):
    d_squared_inv=(h ** 2 + k ** 2 + l ** 2) / a ** 2
    return np.sqrt(1./d_squared_inv)

class EditCurrentJcpdsTest(unittest.TestCase):

    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)

    def tearDown(self):
        del self.app

    def enter_value_into_text_field(self, text_field, value):
        text_field.setText('')
        QTest.keyClicks(text_field, str(value))
        QTest.keyPress(text_field, QtCore.Qt.Key_Enter)
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

    def test_correctly_displays_parameters_and_can_be_edited(self):
        # Erwin has selected a gold jcpds in the Dioptas interface with cubic symmetry
        # and wants to edit the parameters
        self.jcpds = jcpds()
        self.jcpds.read_file('Data/jcpds/au_Anderson.jcpds')

        self.jcpds_controller = JcpdsEditorController('Data/jcpds',self.jcpds)
        self.jcpds_view = self.jcpds_controller.view

        # Erwin immediately sees the filename in the explorer
        self.assertEqual(str(self.jcpds_view.filename_txt.text()),
                         'Data/jcpds/au_Anderson.jcpds')

        # and the comment from which paper the data was derived
        self.assertEqual(str(self.jcpds_view.comments_txt.text()),
                         'Gold (04-0784, Anderson et al J Appl Phys 65, 1534, 1989)')

        # Erwin checks the parameters of the phase
        symmetry = str(self.jcpds_view.symmetry_cb.currentText())
        self.assertEqual(symmetry.upper(), 'CUBIC')

        a = float(str(self.jcpds_view.lattice_a_txt.text()))
        b = float(str(self.jcpds_view.lattice_b_txt.text()))
        c = float(str(self.jcpds_view.lattice_c_txt.text()))

        self.assertEqual(a, 4.07860)
        self.assertEqual(b, 4.07860)
        self.assertEqual(c, 4.07860)

        V = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertAlmostEqual(V, a * b * c, delta=0.0001)

        alpha = float(str(self.jcpds_view.lattice_alpha_txt.text()))
        beta = float(str(self.jcpds_view.lattice_beta_txt.text()))
        gamma = float(str(self.jcpds_view.lattice_gamma_txt.text()))

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
        # however in the first try she makes a small typo and it still
        # magically works
        self.enter_value_into_text_field(self.jcpds_view.lattice_a_txt, '4.asd08')
        a = float(str(self.jcpds_view.lattice_a_txt.text()))
        b = float(str(self.jcpds_view.lattice_b_txt.text()))
        c = float(str(self.jcpds_view.lattice_c_txt.text()))
        self.assertEqual(a, 4.08)
        self.assertEqual(b, 4.08)
        self.assertEqual(c, 4.08)

        # then he tries to type something into b even though it is a cubic phase, however he cannot because it is disabled
        self.assertEqual(self.jcpds_view.lattice_b_txt.isEnabled(), False)

        # then he realizes that he needs to change the symmetry first to be able to
        # change additional lattice parameters. This then magically enables to change the lattice parameters but still
        # not the angles
        self.set_symmetry('orthorhombic')

        self.assertEqual(self.jcpds_view.lattice_b_txt.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_c_txt.isEnabled(), True)

        self.assertEqual(self.jcpds_view.lattice_alpha_txt.isEnabled(), False)
        self.assertEqual(self.jcpds_view.lattice_beta_txt.isEnabled(), False)
        self.assertEqual(self.jcpds_view.lattice_gamma_txt.isEnabled(), False)

        # then he changes the different a,b,c values and notices that the volume changes
        self.enter_value_into_text_field(self.jcpds_view.lattice_b_txt, '5')
        self.enter_value_into_text_field(self.jcpds_view.lattice_c_txt, '6')

        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_volume_txt.text())), 5*6*4.08)

        # he notices that the system is a smart editor shows ratios of lattice parameters:

        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_ab_txt.text())), 4.08/5)
        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_ca_txt.text())), 6.0/4.08, delta=0.0001)
        self.assertAlmostEqual(float(str(self.jcpds_view.lattice_cb_txt.text())), 6.0/5, delta = 0.0001)

        # he decides to play with the ratios to be better able to fit it to the current spectrum:

        self.enter_value_into_text_field(self.jcpds_view.lattice_ca_txt, 1.5)
        self.assertEqual(float(str(self.jcpds_view.lattice_a_txt.text())), 4.08)
        self.assertEqual(float(str(self.jcpds_view.lattice_c_txt.text())), 1.5*4.08)


        # then he set all values back again and
        #  plays a little bit with the symmetry and accidentally changes it to several different symmetries
        # and sees that the parameters change accordingly...

        self.enter_value_into_text_field(self.jcpds_view.lattice_a_txt, 4.08)
        self.enter_value_into_text_field(self.jcpds_view.lattice_b_txt, '5')
        self.enter_value_into_text_field(self.jcpds_view.lattice_c_txt, '6')

        self.set_symmetry("tetragonal")
        self.assertEqual(float(str(self.jcpds_view.lattice_b_txt.text())), 4.08)
        self.assertEqual(float(str(self.jcpds_view.lattice_c_txt.text())), 6)

        self.set_symmetry("hexagonal")
        self.assertEqual(float(str(self.jcpds_view.lattice_gamma_txt.text())), 120)
        self.set_symmetry("monoclinic")
        self.set_symmetry("rhombohedral")
        self.set_symmetry("orthorhombic")

        # now he wants to have full control over the unit cell and sees how the volume changes when he changes the
        # angles

        self.set_symmetry("triclinic")
        self.assertEqual(self.jcpds_view.lattice_a_txt.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_b_txt.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_c_txt.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_alpha_txt.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_beta_txt.isEnabled(), True)
        self.assertEqual(self.jcpds_view.lattice_gamma_txt.isEnabled(), True)

        old_volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.enter_value_into_text_field(self.jcpds_view.lattice_alpha_txt, 70)
        volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertNotEqual(old_volume, volume)

        old_volume = volume
        self.enter_value_into_text_field(self.jcpds_view.lattice_beta_txt, 70)
        volume = float(str(self.jcpds_view.lattice_volume_txt.text()))
        self.assertNotEqual(old_volume, volume)

        old_volume = volume
        self.enter_value_into_text_field(self.jcpds_view.lattice_gamma_txt, 70)
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
        self.assertAlmostEqual(self.jcpds.alpha0, .23e-5)
        self.assertAlmostEqual(self.jcpds.d_alpha_dt, .1e-6)
        self.assertAlmostEqual(self.jcpds.dk0dt, 0.003)
        self.assertAlmostEqual(self.jcpds.dk0pdt, .1e-5)

    def test_reflection_editing_and_saving_of_files(self):
        # Erwin has selected a gold jcpds in the Dioptas interface with cubic symmetry
        # and wants to look for the reflections entered
        self.jcpds = jcpds()
        self.jcpds.read_file('Data/jcpds/au_Anderson.jcpds')

        self.jcpds_controller = JcpdsEditorController('Data/jcpds/',self.jcpds)
        self.jcpds_view = self.jcpds_controller.view

        #he sees that there are 13 reflections predefined in the table

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)

        #he checks if the values are correct:

        self.assertAlmostEqual(self.get_reflection_table_value(0,4), 2.355, delta = 0.001)
        self.assertEqual(self.get_reflection_table_value(1,1), 0)
        self.assertAlmostEqual(self.get_reflection_table_value(12,4), 0.6449,delta = 0.0001)
        self.assertEqual(self.get_reflection_table_value(12,3), 10)

        #then he decides to change the lattice parameter and sees that the values in the table are changing:
        self.enter_value_into_text_field(self.jcpds_view.lattice_a_txt, 4)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)
        self.assertEqual(self.get_reflection_table_value(1,4),2)

        #After playing with the lattice parameter he sets it back to the original value and looks at the reflections
        # He thinks that he doesn't need the sixth reflection because it any way has to low intensity
        self.enter_value_into_text_field(self.jcpds_view.lattice_a_txt, 4.0786)
        self.jcpds_view.reflection_table.selectRow(5)
        QTest.mouseClick(self.jcpds_view.reflections_delete_btn, QtCore.Qt.LeftButton)

        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 12)
        self.assertAlmostEqual(self.get_reflection_table_value(5,4), 0.9358, delta = 0.0002)
        self.assertEqual(len(self.jcpds.reflections), 12)

        #then he changed his mind and wants to add the reflection back:

        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()

        self.assertEqual(len(self.jcpds.reflections), 13)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 13)
        self.assertEqual(self.jcpds_view.get_selected_reflections()[0], 12)

        self.assertEqual(self.get_reflection_table_value(12,0),0)#h
        self.assertEqual(self.get_reflection_table_value(12,1),0)#k
        self.assertEqual(self.get_reflection_table_value(12,2),0)#l
        self.assertEqual(self.get_reflection_table_value(12,3),0)#intensity
        self.assertEqual(self.get_reflection_table_value(12,4),0)#d

        # then he edits he and realizes how the d spacings are magically calculated

        self.insert_reflection_table_value(12,0,1)
        self.assertEqual(self.get_reflection_table_value(12,4), 4.0786)
        self.insert_reflection_table_value(12,1,1)
        self.assertAlmostEqual(self.get_reflection_table_value(12,4),
                               calculate_cubic_d_spacing(1,1,0,4.0786),
                               delta = 0.0001)
        self.insert_reflection_table_value(12,2,3)
        self.assertAlmostEqual(self.get_reflection_table_value(12,4),
                               calculate_cubic_d_spacing(1,1,3,4.0786),
                               delta = 0.0001)

        #then she decides that everybody should screw with the table and clears it:

        QTest.mouseClick(self.jcpds_view.reflections_clear_btn, QtCore.Qt.LeftButton)
        self.assertEqual(self.jcpds_view.reflection_table.rowCount(), 0)
        self.assertEqual(len(self.jcpds.reflections), 0)
        self.assertEqual(len(self.jcpds_view.get_selected_reflections()), 0)

        # he finds this phase much more promising and wants to give it a new name
        self.enter_value_into_text_field(self.jcpds_view.comments_txt,
                                         'HAHA this is a phase you will never see in your spectrum')
        self.assertEqual(self.jcpds.comments[0], 'HAHA this is a phase you will never see in your spectrum')

        # then he sees the save_as button and is happy to save his non-sense for later users
        filename='Data/jcpds/au_mal_anders.jcpds'
        self.jcpds_controller.save_as_btn_click(filename)
        self.assertTrue(os.path.exists(filename))

        # he decides to change the lattice parameter and then reload the file to see if everything is ok
        self.enter_value_into_text_field(self.jcpds_view.lattice_a_txt, 10)

        self.jcpds.read_file('Data/jcpds/au_mal_anders.jcpds')
        self.jcpds_controller = JcpdsEditorController('Data/jcpds/', self.jcpds)
        self.jcpds_view = self.jcpds_controller.view
        self.assertEqual(float(str(self.jcpds_view.lattice_a_txt.text())), 4.0786)
        self.assertEqual(float(str(self.jcpds_view.lattice_b_txt.text())), 4.0786)
        self.assertEqual(float(str(self.jcpds_view.lattice_c_txt.text())), 4.0786)

        # then he decides to make this phase it little bit more useful and adds some peaks and saves this as a different
        # version and trys to load it again...

        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)
        QTest.mouseClick(self.jcpds_view.reflections_add_btn, QtCore.Qt.LeftButton)

        self.insert_reflection_table_value(0,0, 1)
        self.insert_reflection_table_value(0,3, 100)
        self.insert_reflection_table_value(1,1, 1)
        self.insert_reflection_table_value(1,3, 50)
        self.insert_reflection_table_value(2,2,1)
        self.insert_reflection_table_value(2,3, 20)

        filename='Data/jcpds/au_mal_anders_vers2.jcpds'
        self.jcpds_controller.save_as_btn_click(filename)

        self.jcpds.read_file(filename)
        self.jcpds_controller = JcpdsEditorController('Data/jcpds/', self.jcpds)

    def test_connection_between_main_gui_and_jcpds_editor(self):
        #Erwin opens up the program, loads image and calibration and some phases
        self.main_controller = MainController(self.app)
        self.main_controller.calibration_controller.load_calibration('Data/LaB6_p49_40keV_006.poni', update_all=False)
        self.main_controller.calibration_controller.set_calibrant(7)
        self.main_controller.calibration_controller.load_img('Data/LaB6_p49_40keV_006.tif')
        self.main_controller.view.tabWidget.setCurrentIndex(2)
        self.main_controller.view.integration_widget.tabWidget.setCurrentIndex(3)
        self.main_controller.integration_controller.phase_controller.add_phase('Data/jcpds/au_Anderson.jcpds')
        self.main_controller.integration_controller.phase_controller.add_phase('Data/jcpds/mo.jcpds')
        self.main_controller.integration_controller.phase_controller.add_phase('Data/jcpds/ar.jcpds')
        self.main_controller.integration_controller.phase_controller.add_phase('Data/jcpds/re.jcpds')

        self.phase_controller = self.main_controller.integration_controller.phase_controller
        self.jcpds_editor_controller = self.phase_controller.jcpds_editor_controller
        self.jcpds_view = self.jcpds_editor_controller.view

        self.phase_controller.view.phase_tw.selectRow(0)
        QTest.mouseClick(self.phase_controller.view.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()
        self.assertTrue(self.jcpds_view.isActiveWindow())

        # He changes some parameter but then realizes that he screwed it up and presses cancel to revert all his changes

        self.enter_value_into_text_field(self.jcpds_view.lattice_a_txt, 10.4)

        self.assertAlmostEqual(self.phase_controller.phase_data.phases[0].a0, 10.4)
        QTest.mouseClick(self.jcpds_view.cancel_btn, QtCore.Qt.LeftButton)

        self.assertNotAlmostEqual(self.phase_controller.phase_data.phases[0].a0, 10.4)

        # Now he selects one phase in the phase table and starts the JCPDS editor and realizes he wanted to click another
        # phase --  so he just selects it without closing and reopening the editor and magically the new parameters show up

        self.phase_controller.view.phase_tw.selectRow(1)
        QTest.mouseClick(self.phase_controller.view.phase_edit_btn, QtCore.Qt.LeftButton)
        QtGui.QApplication.processEvents()

        self.phase_controller.view.phase_tw.selectRow(2)
        self.assertTrue(float(str(self.jcpds_view.lattice_a_txt.text())), 5.51280) #Argon lattice parameter















