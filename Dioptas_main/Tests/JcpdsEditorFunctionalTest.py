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
from Data.jcpds import jcpds
from Views.JcpdsEditorWidget import JcpdsEditorWidget
from PyQt4 import QtGui, QtCore
from PyQt4.QtTest import QTest
import sys


class EditCurrentJcpdsTest(unittest.TestCase):

    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)

    def tearDown(self):
        pass

    def test_correctly_displays_parameters_and_can_be_edited(self):
        # Erwin has selected a gold jcpds in the Dioptas interface with cubic symmetry
        # and wants to edit the parameters
        self.jcpds = jcpds()
        self.jcpds.read_file('Data/jcpds/au_Anderson.jcpds')

        self.jcpds_editor = JcpdsEditorWidget(self.jcpds)

        # Erwin immediately sees the filename in the explorer
        self.assertEqual(str(self.jcpds_editor.filename_txt.text()),
                         'Data/jcpds/au_Anderson.jcpds')

        # and the comment from which paper the data was derived
        self.assertEqual(str(self.jcpds_editor.comments_txt.text()),
                         'Gold (04-0784, Anderson et al J Appl Phys 65, 1534, 1989)')

        # Erwin checks the parameters of the phase
        symmetry = str(self.jcpds_editor.symmetry_cb.currentText())
        self.assertEqual(symmetry.upper(), 'CUBIC')

        a = float(str(self.jcpds_editor.lattice_a_txt.text()))
        b = float(str(self.jcpds_editor.lattice_b_txt.text()))
        c = float(str(self.jcpds_editor.lattice_c_txt.text()))
        self.assertEqual(a, 4.07860)
        self.assertEqual(b, 4.07860)
        self.assertEqual(c, 4.07860)

        V = float(str(self.jcpds_editor.lattice_volume_txt.text()))
        self.assertAlmostEqual(V, a * b * c)

        alpha = float(str(self.jcpds_editor.lattice_alpha_txt.text()))
        beta = float(str(self.jcpds_editor.lattice_beta_txt.text()))
        gamma = float(str(self.jcpds_editor.lattice_gamma_txt.text()))

        self.assertEqual(alpha, 90)
        self.assertEqual(beta, 90)
        self.assertEqual(gamma, 90)

        K0 = float(str(self.jcpds_editor.eos_K_txt.text()))
        Kp = float(str(self.jcpds_editor.eos_Kp_txt.text()))
        alphaT = float(str(self.jcpds_editor.eos_alphaT_txt.text()))
        dalpha_dt = float(str(self.jcpds_editor.eos_dalphadT_txt.text()))
        dK_dt = float(str(self.jcpds_editor.eos_dKdT_txt.text()))
        dKp_dt = float(str(self.jcpds_editor.eos_dKpdT_txt.text()))

        self.assertEqual(K0, 166.65)
        self.assertEqual(Kp, 5.4823)
        self.assertEqual(alphaT, 4.26e-5)
        self.assertEqual(dalpha_dt, 0)
        self.assertEqual(dK_dt, 0)
        self.assertEqual(dKp_dt, 0)

        # then she decides to put a new lattice parameter into the a box and realizes that all
        # others are changing too.
        # however in the first try she makes a small typo and it still
        # magically works
        self.jcpds_editor.lattice_a_txt.setText('')
        QTest.keyClicks(self.jcpds_editor.lattice_a_txt, '4.0p8')
        QTest.keyPress(self.jcpds_editor.lattice_a_txt, QtCore.Qt.Key_Enter)
        a = float(str(self.jcpds_editor.lattice_a_txt.text()))
        b = float(str(self.jcpds_editor.lattice_b_txt.text()))
        c = float(str(self.jcpds_editor.lattice_c_txt.text()))
        self.assertEqual(a, 4.08)
        self.assertEqual(b, 4.08)
        self.assertEqual(c, 4.08)









