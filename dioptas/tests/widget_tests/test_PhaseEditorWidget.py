# SPDX-License-Identifier: MIT

import os
import unittest

from qtpy import QtCore

from ..utility import QtTest, QtWidgets
from ...model.util import jcpds
from ...widgets.integration.PhaseEditorWidget import PhaseEditorWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class PhaseEditorWidgetTest(QtTest):
    def setUp(self):
        self.jcpds = jcpds()
        self.jcpds.compute_v0()
        self.jcpds.load_file(os.path.join(jcpds_path, 'au_Anderson.jcpds'))

        self.jcpds_editor_widget = PhaseEditorWidget()
        self.jcpds_editor_widget.show_jcpds(self.jcpds, wavelength=0.31)

    def tearDown(self):
        del self.jcpds
        self.jcpds_editor_widget.close()
        del self.jcpds_editor_widget

    def test_filename_and_comment_are_shown_correctly(self):
        self.assertEqual(self.jcpds_editor_widget.filename_txt.text(),
                         self.jcpds.filename)
        self.assertEqual(self.jcpds_editor_widget.comments_txt.text(),
                         self.jcpds.params['comments'][0])

    def test_all_lattice_parameters_are_shown_correctly(self):
        self.assertEqual(self.jcpds_editor_widget.lattice_a_sb.value(),
                         self.jcpds.params['a0'])
        self.assertEqual(self.jcpds_editor_widget.lattice_b_sb.value(),
                         self.jcpds.params['b0'])
        self.assertEqual(self.jcpds_editor_widget.lattice_c_sb.value(),
                         self.jcpds.params['c0'])
        self.assertAlmostEqual(float(str(self.jcpds_editor_widget.lattice_volume_txt.text())),
                               self.jcpds.params['v0'], delta=0.0001)

        self.assertEqual(float(str(self.jcpds_editor_widget.lattice_eos_a_txt.text())),
                         self.jcpds.params['a'])
        self.assertEqual(float(str(self.jcpds_editor_widget.lattice_eos_b_txt.text())),
                         self.jcpds.params['b'])
        self.assertEqual(float(str(self.jcpds_editor_widget.lattice_eos_c_txt.text())),
                         self.jcpds.params['c'])

        self.assertEqual(self.jcpds_editor_widget.lattice_alpha_sb.value(),
                         self.jcpds.params['alpha'])
        self.assertEqual(self.jcpds_editor_widget.lattice_beta_sb.value(),
                         self.jcpds.params['beta0'])
        self.assertEqual(self.jcpds_editor_widget.lattice_gamma_sb.value(),
                         self.jcpds.params['gamma0'])

        self.assertEqual(self.jcpds_editor_widget.lattice_ab_sb.value(),
                         self.jcpds.params['a0'] / float(self.jcpds.params['b0']))
        self.assertEqual(self.jcpds_editor_widget.lattice_ca_sb.value(),
                         1)
        self.assertEqual(self.jcpds_editor_widget.lattice_cb_sb.value(),
                         1)

    def test_all_eos_parameters_are_shown_correctly(self):
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_K_txt.text())),
                         self.jcpds.params['k0'])
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_Kp_txt.text())),
                         self.jcpds.params['k0p0'])
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_alphaT_txt.text())),
                         self.jcpds.params['alpha_t0'])
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_dalphadT_txt.text())),
                         self.jcpds.params['d_alpha_dt'])
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_dKdT_txt.text())),
                         self.jcpds.params['dk0dt'])
        self.assertEqual(float(str(self.jcpds_editor_widget.eos_dKpdT_txt.text())),
                         self.jcpds.params['dk0pdt'])

    def test_sokolova_parameters_are_shown_in_scrollable_eos_panel(self):
        parameters = {
            'Tr': 298.15, 'QE1o': 179.5, 'mE1': 1.5,
            'QE2o': 83.0, 'mE2': 1.5, 'delta': 0.134,
            't': 0.087, 'a_0': 0.0, 'm': 0.0, 'g': 0.0,
            'e_0': 0.0,
        }
        self.jcpds.params['thermal_type'] = 'Sokolova2016'
        self.jcpds.params['thermal_parameters'] = parameters
        self.jcpds.params['t_ref'] = parameters['Tr']

        self.jcpds_editor_widget.update_eos_parameters(self.jcpds)

        for name, expected in parameters.items():
            if name == 'Tr':
                field = self.jcpds_editor_widget.eos_tref_txt
            else:
                field = self.jcpds_editor_widget.sokolova_parameter_fields[name]
            self.assertFalse(field.isHidden())
            self.assertAlmostEqual(float(field.text()), expected)
        self.assertTrue(self.jcpds_editor_widget.eos_theta_txt.isHidden())
        self.assertEqual(
            self.jcpds_editor_widget.eos_scroll_area.verticalScrollBarPolicy(),
            QtCore.Qt.ScrollBarAsNeeded)


if __name__ == '__main__':
    unittest.main()
