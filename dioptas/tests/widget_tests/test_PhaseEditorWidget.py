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
        # Legacy comments remain available to old code, but provenance now
        # lives in EoS records and is not duplicated in the phase editor.
        self.assertTrue(self.jcpds_editor_widget.comments_txt.isHidden())
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

    def test_bundled_record_controls_are_read_only(self):
        self.jcpds_editor_widget.update_eos_records(
            ['Published fit'], 0, origins=['bundled'], default_index=0,
            material_origin='bundled')

        self.assertFalse(self.jcpds_editor_widget.eos_K_txt.isEnabled())
        self.assertFalse(self.jcpds_editor_widget.eos_type_cb.isEnabled())
        self.assertFalse(self.jcpds_editor_widget.eos_record_edit_btn.isEnabled())
        self.assertFalse(self.jcpds_editor_widget.eos_record_delete_btn.isEnabled())
        self.assertTrue(
            self.jcpds_editor_widget.eos_record_duplicate_btn.isEnabled())
        self.assertFalse(self.jcpds_editor_widget.lattice_a_sb.isEnabled())
        self.assertFalse(
            self.jcpds_editor_widget.reflection_table_view.isEnabled())
        self.assertFalse(self.jcpds_editor_widget.reload_file_btn.isEnabled())

    def test_custom_record_controls_are_editable(self):
        self.jcpds_editor_widget.update_eos_records(
            ['Custom fit'], 0, origins=['custom'], default_index=0)

        self.assertTrue(self.jcpds_editor_widget.eos_K_txt.isEnabled())
        self.assertTrue(self.jcpds_editor_widget.eos_record_edit_btn.isEnabled())
        self.assertTrue(self.jcpds_editor_widget.eos_record_delete_btn.isEnabled())

    def test_visible_eos_rows_are_compacted(self):
        widget = self.jcpds_editor_widget
        widget.configure_eos_types([
            ('BM3', 'Birch-Murnaghan (3rd order)', ['K0', 'K0_prime'])
        ])
        widget.set_thermal_type('none')
        widget.set_eos_type('BM3')

        def grid_row(control):
            item_index = widget._eos_layout.indexOf(control)
            return widget._eos_layout.getItemPosition(item_index)[0]

        self.assertEqual([
            grid_row(widget.eos_type_cb),
            grid_row(widget.eos_K_txt),
            grid_row(widget.eos_Kp_txt),
            grid_row(widget.thermal_type_cb),
        ], [0, 1, 2, 3])

    def test_cif_and_eosmat_sources_can_be_reloaded(self):
        for material_origin in ('cif', 'file'):
            self.jcpds_editor_widget.update_eos_records(
                [], material_origin=material_origin)
            self.assertTrue(
                self.jcpds_editor_widget.reload_file_btn.isEnabled())


if __name__ == '__main__':
    unittest.main()
