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

import os
import unittest

from qtpy import QtWidgets

from ...model.util import jcpds
from ...widgets.integration.JcpdsEditorWidget import JcpdsEditorWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')

app = QtWidgets.QApplication([])

class JcpdsEditorTest(unittest.TestCase):

    def setUp(self):
        self.jcpds = jcpds()
        self.jcpds.compute_v0()
        self.jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        self.jcpds_editor_widget = JcpdsEditorWidget()
        self.jcpds_editor_widget.show_jcpds(self.jcpds, wavelength=0.31)

    def tearDown(self):
        del self.jcpds
        self.jcpds_editor_widget.close()
        del self.jcpds_editor_widget

    def test_filename_and_comment_are_shown_correctly(self):
        self.assertEqual(self.jcpds_editor_widget.filename_txt.text(),
                         self.jcpds.filename)
        self.assertEqual(self.jcpds_editor_widget.comments_txt.text(),
                         self.jcpds.comments[0])

    def test_all_lattice_parameters_are_shown_correctly(self):
        self.assertEqual(self.jcpds_editor_widget.lattice_a_sb.value(),
                         self.jcpds.a0)
        self.assertEqual(self.jcpds_editor_widget.lattice_b_sb.value(),
                         self.jcpds.b0)
        self.assertEqual(self.jcpds_editor_widget.lattice_c_sb.value(),
                         self.jcpds.c0)
        self.assertAlmostEqual(float(str(self.jcpds_editor_widget.lattice_volume_txt.text())),
                               self.jcpds.v0, delta=0.0001)

        self.assertEqual(float(str(self.jcpds_editor_widget.lattice_eos_a_txt.text())),
                         self.jcpds.a)
        self.assertEqual(float(str(self.jcpds_editor_widget.lattice_eos_b_txt.text())),
                         self.jcpds.b)
        self.assertEqual(float(str(self.jcpds_editor_widget.lattice_eos_c_txt.text())),
                         self.jcpds.c)

        self.assertEqual(self.jcpds_editor_widget.lattice_alpha_sb.value(),
                         self.jcpds.alpha)
        self.assertEqual(self.jcpds_editor_widget.lattice_beta_sb.value(),
                         self.jcpds.beta0)
        self.assertEqual(self.jcpds_editor_widget.lattice_gamma_sb.value(),
                         self.jcpds.gamma0)

        self.assertEqual(self.jcpds_editor_widget.lattice_ab_sb.value(),
                         self.jcpds.a0 / float(self.jcpds.b0))
        self.assertEqual(self.jcpds_editor_widget.lattice_ca_sb.value(),
                         1)
        self.assertEqual(self.jcpds_editor_widget.lattice_cb_sb.value(),
                         1)

    def test_all_eos_parameters_are_shown_correctly(self):
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_K_txt.text())),
                         self.jcpds.k0)
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_Kp_txt.text())),
                         self.jcpds.k0p0)
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_alphaT_txt.text())),
                         self.jcpds.alpha_t0)
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_dalphadT_txt.text())),
                         self.jcpds.d_alpha_dt)
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_dKdT_txt.text())),
                         self.jcpds.dk0dt)
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_dKpdT_txt.text())),
                         self.jcpds.dk0pdt)


if __name__ == '__main__':
    unittest.main()
