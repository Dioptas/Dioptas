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
from model.Helper import jcpds
from widgets.JcpdsEditorWidget import JcpdsEditorWidget
from PyQt4 import QtGui
import sys
import gc

class JcpdsDisplayTestAuAnderson(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.jcpds = jcpds()
        self.jcpds.compute_v0()
        self.jcpds.load_file('Data/jcpds/au_Anderson.jcpds')

        self.jcpds_editor = JcpdsEditorWidget()
        self.jcpds_editor.show_jcpds(self.jcpds, wavelength=0.31)

    def tearDown(self):
        del self.jcpds
        self.jcpds_editor.close()
        del self.jcpds_editor
        del self.app
        gc.collect()

    def test_filename_and_comment_are_shown_correctly(self):
        self.assertEqual(self.jcpds_editor.filename_txt.text(),
                         self.jcpds.filename)
        self.assertEqual(self.jcpds_editor.comments_txt.text(),
                         self.jcpds.comments[0])

    def test_all_lattice_parameters_are_shown_correctly(self):
        self.assertEqual(self.jcpds_editor.lattice_a_sb.value(),
                         self.jcpds.a0)
        self.assertEqual(self.jcpds_editor.lattice_b_sb.value(),
                         self.jcpds.b0)
        self.assertEqual(self.jcpds_editor.lattice_c_sb.value(),
                         self.jcpds.c0)
        self.assertAlmostEqual(float(str(self.jcpds_editor.lattice_volume_txt.text())),
                         self.jcpds.v0, delta=0.0001)

        self.assertEqual(float(str(self.jcpds_editor.lattice_eos_a_txt.text())),
                         self.jcpds.a)
        self.assertEqual(float(str(self.jcpds_editor.lattice_eos_b_txt.text())),
                         self.jcpds.b)
        self.assertEqual(float(str(self.jcpds_editor.lattice_eos_c_txt.text())),
                         self.jcpds.c)

        self.assertEqual(self.jcpds_editor.lattice_alpha_sb.value(),
                         self.jcpds.alpha)
        self.assertEqual(self.jcpds_editor.lattice_beta_sb.value(),
                         self.jcpds.beta0)
        self.assertEqual(self.jcpds_editor.lattice_gamma_sb.value(),
                         self.jcpds.gamma0)

        self.assertEqual(self.jcpds_editor.lattice_ab_sb.value(),
                         self.jcpds.a0/float(self.jcpds.b0))
        self.assertEqual(self.jcpds_editor.lattice_ca_sb.value(),
                         1)
        self.assertEqual(self.jcpds_editor.lattice_cb_sb.value(),
                         1)

    def test_all_eos_parameters_are_shown_correctly(self):
        self.assertEqual(float(str(self.jcpds_editor.eos_K_txt.text())),
                         self.jcpds.k0)
        self.assertEqual(float(str(self.jcpds_editor.eos_Kp_txt.text())),
                         self.jcpds.k0p0)
        self.assertEqual(float(str(self.jcpds_editor.eos_alphaT_txt.text())),
                         self.jcpds.alpha_t0)
        self.assertEqual(float(str(self.jcpds_editor.eos_dalphadT_txt.text())),
                         self.jcpds.d_alpha_dt)
        self.assertEqual(float(str(self.jcpds_editor.eos_dKdT_txt.text())),
                         self.jcpds.dk0dt)
        self.assertEqual(float(str(self.jcpds_editor.eos_dKpdT_txt.text())),
                         self.jcpds.dk0pdt)


