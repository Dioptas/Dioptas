# SPDX-License-Identifier: MIT

import unittest
from ..utility import QtTest
from qtpy.QtTest import QTest
from qtpy import QtCore, QtGui
import os
import gc
from qtpy import QtWidgets

from mock import MagicMock, patch
import numpy as np

from ..utility import click_button, enter_value_into_text_field, delete_if_exists
from ...controller.integration import PhaseEditorController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
jcpds_path = os.path.join(data_path, 'jcpds')


class PhaseEditorControllerTest(QtTest):
    # SETUP
    #######################
    def setUp(self) -> None:
        self.model = DioptasModel()
        self.model.calibration_model.is_calibrated = True
        self.model.calibration_model.pattern_geometry.wavelength = 0.31E-10
        self.model.calibration_model.integrate_1d = MagicMock(return_value=(self.model.calibration_model.tth,
                                                                            self.model.calibration_model.int))

        self.phase_model = self.model.phase_model

        self.widget = IntegrationWidget()

        self.controller = PhaseEditorController(self.widget, self.model)
        self.model.pattern_model.load_pattern(os.path.join(data_path, 'pattern_001.xy'))

        self.jcpds_widget = self.controller.jcpds_widget
        self.phase_widget = self.widget.phase_widget

        self.load_phases()
        self.controller.active = True
        self.controller.show_view()

        self.setup_selected_row(5)
        click_button(self.phase_widget.edit_btn)

    def tearDown(self) -> None:
        del self.controller
        del self.widget
        self.model.delete_configurations()
        del self.model
        delete_if_exists(os.path.join(jcpds_path, 'dummy.jcpds'))
        delete_if_exists(os.path.join(jcpds_path, 'dummy.eosmat'))
        delete_if_exists(os.path.join(data_path, 'reflection_table.txt'))
        gc.collect()

    # Utility Functions
    #######################
    def load_phase(self, filename):
        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, filename))

    def load_phases(self):
        self.load_phase('ar.jcpds')
        self.load_phase('ag.jcpds')
        self.load_phase('au_Anderson.jcpds')
        self.load_phase('mo.jcpds')
        self.load_phase('pt.jcpds')
        self.load_phase('re.jcpds')

    def setup_selected_row(self, ind):
        self.phase_widget.get_selected_phase_row = MagicMock(return_value=ind)

    def send_phase_tw_select_signal(self, ind):
        self.phase_widget.phase_tw.currentCellChanged.emit(ind, 0, 0, 0)

    def set_symmetry(self, symmetry):
        self.jcpds_widget.symmetry_cb.setCurrentIndex(self.jcpds_widget.symmetries.index(symmetry))
        QtWidgets.QApplication.processEvents()

    # Tests
    #######################
    def test_edit_button_shows_correct_phase(self):
        self.assertEqual(self.jcpds_widget.filename_txt.text(), self.phase_model.phases[5].filename)

    def test_selection_changed_shows_correct_phase(self):
        self.send_phase_tw_select_signal(3)
        self.assertEqual(self.jcpds_widget.filename_txt.text(), self.phase_model.phases[3].filename)

    def test_updating_the_gui_after_external_change(self):
        previous_a = self.jcpds_widget.lattice_eos_a_txt.text()
        self.phase_model.set_pressure(5, 20)
        self.assertNotEqual(previous_a, self.jcpds_widget.lattice_eos_a_txt.text())

    def test_updating_volume_after_changing_a(self):
        previous_volume = self.jcpds_widget.lattice_volume_txt.text()
        self.jcpds_widget.lattice_a_sb.setValue(3)
        self.assertNotEqual(previous_volume, self.jcpds_widget.lattice_volume_txt.text())

    def test_updating_volume_after_changing_c(self):
        previous_volume = self.jcpds_widget.lattice_volume_txt.text()
        self.jcpds_widget.lattice_c_sb.setValue(3)
        self.assertNotEqual(previous_volume, self.jcpds_widget.lattice_volume_txt.text())

    def test_updating_volume_after_changing_ca_ratio(self):
        previous_volume = self.jcpds_widget.lattice_volume_txt.text()
        self.jcpds_widget.lattice_c_sb.setValue(3)
        self.assertNotEqual(previous_volume, self.jcpds_widget.lattice_volume_txt.text())

    def test_updating_k0_parameter(self):
        self.phase_model.set_pressure(5, 30)
        previous_volume = self.jcpds_widget.lattice_eos_volume_txt.text()
        enter_value_into_text_field(self.jcpds_widget.eos_K_txt, 300)
        self.assertNotEqual(previous_volume, self.jcpds_widget.lattice_eos_volume_txt.text())

    def test_updating_kp_parameter(self):
        self.phase_model.set_pressure(5, 30)
        previous_volume = self.jcpds_widget.lattice_eos_volume_txt.text()
        enter_value_into_text_field(self.jcpds_widget.eos_Kp_txt, 5)
        self.assertNotEqual(previous_volume, self.jcpds_widget.lattice_eos_volume_txt.text())

    def test_adding_a_reflection(self):
        num_phase_reflections = len(self.phase_model.phases[5].reflections)
        num_table_reflections = self.jcpds_widget.reflection_table_model.rowCount()
        self.assertEqual(num_phase_reflections, num_table_reflections)

        click_button(self.jcpds_widget.reflections_add_btn)

        self.assertEqual(len(self.phase_model.phases[5].reflections),
                         num_phase_reflections + 1)
        self.assertEqual(self.jcpds_widget.reflection_table_model.rowCount(),
                         num_table_reflections + 1)

    def test_adding_two_reflections(self):
        num_phase_reflections = len(self.phase_model.phases[5].reflections)
        num_table_reflections = self.jcpds_widget.reflection_table_model.rowCount()
        self.assertEqual(num_phase_reflections, num_table_reflections)

        click_button(self.jcpds_widget.reflections_add_btn)
        click_button(self.jcpds_widget.reflections_add_btn)

        self.assertEqual(len(self.phase_model.phases[5].reflections),
                         num_phase_reflections + 2)
        self.assertEqual(self.jcpds_widget.reflection_table_model.rowCount(),
                         num_table_reflections + 2)

    def test_removing_one_reflection(self):
        num_phase_reflections = len(self.phase_model.phases[5].reflections)
        num_table_reflections = self.jcpds_widget.reflection_table_model.rowCount()
        self.assertEqual(num_phase_reflections, num_table_reflections)

        self.jcpds_widget.get_selected_reflections = MagicMock(return_value=[3])

        click_button(self.jcpds_widget.reflections_delete_btn)

        self.assertEqual(self.jcpds_widget.reflection_table_model.rowCount(),
                         num_table_reflections - 1)
        self.assertEqual(len(self.phase_model.phases[5].reflections),
                         num_phase_reflections - 1)

    def test_removing_multiple_reflections(self):
        num_phase_reflections = len(self.phase_model.phases[5].reflections)
        num_table_reflections = self.jcpds_widget.reflection_table_model.rowCount()
        self.assertEqual(num_phase_reflections, num_table_reflections)

        self.jcpds_widget.reflection_table_view.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        for ind in [3, 1, 5, 11]:
            self.jcpds_widget.reflection_table_view.selectRow(ind)

        click_button(self.jcpds_widget.reflections_delete_btn)

        self.assertEqual(len(self.phase_model.phases[5].reflections),
                         num_phase_reflections - 4)
        self.assertEqual(self.jcpds_widget.reflection_table_model.rowCount(),
                         num_table_reflections - 4)

    def test_clear_reflections(self):
        self.assertGreater(self.jcpds_widget.reflection_table_model.rowCount(), 0)
        click_button(self.jcpds_widget.reflections_clear_btn)
        self.assertEqual(len(self.phase_model.phases[5].reflections), 0)
        self.assertEqual(self.jcpds_widget.reflection_table_model.rowCount(), 0)


    @unittest.skip('Does currently not work with pytest running a full suite - needs to be added later again')
    def test_edit_reflection(self):
        col = 0
        row = 1

        previous_d0 = self.phase_model.phases[5].reflections[1].d

        # get x,y position for the cell
        x_pos = self.jcpds_widget.reflection_table_view.columnViewportPosition(col) + 3
        y_pos = self.jcpds_widget.reflection_table_view.rowViewportPosition(row) + 10

        # click then doubleclick  the cell
        self.assertTrue(self.jcpds_widget.reflection_table_view.isVisible())
        viewport = self.jcpds_widget.reflection_table_view.viewport()
        QTest.mouseClick(viewport, QtCore.Qt.LeftButton, pos=QtCore.QPoint(x_pos, y_pos))
        QTest.mouseDClick(viewport, QtCore.Qt.LeftButton, pos=QtCore.QPoint(x_pos, y_pos))

        # type in the new number
        QTest.keyClicks(viewport.focusWidget(), "3")
        QTest.keyPress(viewport.focusWidget(), QtCore.Qt.Key_Enter)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.phase_model.phases[5].reflections[1].h, 3)
        print(self.phase_model.phases[5].reflections[1].d)
        self.assertNotEqual(self.phase_model.phases[5].reflections[1].d,
                            previous_d0)

    def test_reload_phase(self):
        num_phase_reflections = len(self.phase_model.phases[5].reflections)
        self.phase_model.delete_reflection(5, 0)
        self.phase_model.delete_reflection(5, 0)
        self.assertEqual(len(self.phase_model.reflections[5]), num_phase_reflections - 2)

        previous_a = self.jcpds_widget.lattice_a_sb.value()
        self.jcpds_widget.lattice_a_sb.setValue(3)

        click_button(self.jcpds_widget.reload_file_btn)

        self.assertEqual(self.jcpds_widget.reflection_table_model.rowCount(), num_phase_reflections)
        self.assertEqual(self.jcpds_widget.lattice_a_sb.value(), previous_a)

    def test_save_as(self):
        filename = os.path.join(jcpds_path, 'dummy.jcpds')
        QtWidgets.QFileDialog.getSaveFileName = MagicMock(return_value=filename)
        click_button(self.jcpds_widget.save_as_btn)
        self.assertEqual(self.jcpds_widget.filename_txt.text(), filename)

    def test_changing_symmetry(self):
        print(self.controller.jcpds_phase.params['symmetry'])
        self.assertTrue(self.jcpds_widget.lattice_a_sb.isEnabled())
        self.assertFalse(self.jcpds_widget.lattice_b_sb.isEnabled())
        self.assertTrue(self.jcpds_widget.lattice_c_sb.isEnabled())

        self.set_symmetry('orthorhombic')
        self.assertEqual(self.controller.jcpds_phase.params['symmetry'], 'ORTHORHOMBIC')
        self.assertTrue(self.jcpds_widget.lattice_a_sb.isEnabled())
        self.assertTrue(self.jcpds_widget.lattice_b_sb.isEnabled())
        self.assertTrue(self.jcpds_widget.lattice_c_sb.isEnabled())

    def test_select_row_in_phase_widget(self):
        self.controller.phase_widget.phase_tw.setRowCount(6)
        self.controller.phase_widget.phase_tw.selectRow(2)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(self.controller.phase_ind, 2)

    def test_editing_the_comments(self):
        enter_value_into_text_field(self.jcpds_widget.comments_txt,
                                    'HAHA this is a phase you will never see in your pattern')
        self.assertEqual(self.controller.jcpds_phase.params['comments'][0],
                         'HAHA this is a phase you will never see in your pattern')

    def test_export_reflection_table(self):
        path = os.path.join(data_path, 'reflection_table.txt')
        self.controller.export_table_data(path)
        with open(path, 'r') as f:
            self.assertEqual(len(f.readlines()), 21)

    def test_copy_complete_reflection_table(self):
        self.controller.reflection_table_key_pressed(QtGui.QKeySequence.SelectAll)
        self.controller.reflection_table_key_pressed(QtGui.QKeySequence.Copy)

        self.assertEqual(QtWidgets.QApplication.clipboard().text().split('\n')[3],
                         '1	0	1	100.00	2.1065	2.1065	8.4396	8.4396	2.9828	2.9828')

        self.jcpds_widget.reflection_table_model.wavelength = None
        self.controller.reflection_table_key_pressed(QtGui.QKeySequence.Copy)
        self.assertEqual(QtWidgets.QApplication.clipboard().text().split('\n')[3],
                         '1	0	1	100.00	2.1065	2.1065')



    # EoS selection
    #######################

    def test_eos_combobox_offers_all_peritheos_equations(self):
        from dioptas.model.util.eos_phase import RT_EOS_TYPES
        cb = self.jcpds_widget.eos_type_cb
        keys = [cb.itemData(i) for i in range(cb.count())]
        self.assertEqual(keys, list(RT_EOS_TYPES))
        # a plain jcpds phase starts as 3rd-order Birch-Murnaghan
        self.assertEqual(self.jcpds_widget.get_eos_type(), 'BM3')

    def test_editing_atomic_position_updates_material_and_hkl_table(self):
        from ...model import eos
        from peritheos import get_material_document

        phase = eos.build_jcpds(eos.Material.from_dict(get_material_document('diopside')),
                                origin='file')
        self.phase_model.add_jcpds_object(phase)
        self.controller.show_phase(phase)
        widget = self.jcpds_widget
        widget.parameter_tabs.setCurrentIndex(0)
        table = widget.structure_sites_table
        column = next(col for col in range(table.columnCount())
                      if table.item(3, col).data(QtCore.Qt.UserRole) == 'x')
        before = widget.reflection_table_model.reflection_data.copy()
        table.item(3, column).setText('0.13')

        self.assertEqual(phase.params['material_document']['atom_sites'][3]['x'], .13)
        self.assertEqual(widget.structure_composition_lbl.text(),
                         'Calculated Z = 4 · formula matches')
        data = widget.reflection_table_model.reflection_data
        self.assertTrue(before.shape != data.shape or not np.allclose(before, data))
        np.testing.assert_allclose(data[:, 3], [r.intensity for r in phase.reflections])
        self.assertTrue(widget.structure_edit_status_lbl.isHidden())

        lines = data.copy()
        depth = self.model.history.depth
        table.item(3, column).setText('nan')
        self.assertEqual(phase.params['material_document']['atom_sites'][3]['x'], .13)
        self.assertEqual(table.item(3, column).text(), '0.13')
        np.testing.assert_array_equal(widget.reflection_table_model.reflection_data, lines)
        self.assertFalse(widget.structure_edit_status_lbl.isHidden())
        self.assertIn('finite', widget.structure_edit_status_lbl.text())
        self.assertEqual(self.model.history.depth, depth)

    def test_element_picker_and_site_buttons_recalculate_user_material(self):
        from ...model import eos
        from peritheos import get_material_document

        phase = eos.build_jcpds(eos.Material.from_dict(get_material_document('diopside')),
                                origin='file')
        self.phase_model.add_jcpds_object(phase)
        self.controller.show_phase(phase)
        widget = self.jcpds_widget
        table = widget.structure_sites_table
        count = table.rowCount()
        column = next(col for col in range(table.columnCount())
                      if table.item(0, col).data(QtCore.Qt.UserRole) == 'element')
        module = 'dioptas.controller.integration.phase.PhaseEditorController'
        with patch(module + '.ElementPickerDialog') as picker:
            picker.return_value.exec_.return_value = QtWidgets.QDialog.Accepted
            picker.return_value.element = 'Fe'
            table.cellDoubleClicked.emit(0, column)
        self.assertEqual(phase.params['material_document']['atom_sites'][0]['element'], 'Fe')
        self.assertEqual(widget.structure_composition_lbl.text(), 'Formula mismatch · no common Z')
        with patch(module + '.AtomicSiteDialog') as form:
            form.return_value.exec_.return_value = QtWidgets.QDialog.Accepted
            form.return_value.site.return_value = {
                'element': 'O', 'x': .12, 'y': .23, 'z': .34, 'occupancy': .5}
            widget.structure_site_add_btn.click()
        self.assertEqual(table.rowCount(), count + 1)
        self.assertTrue(widget.structure_site_remove_btn.isEnabled())
        widget.structure_site_remove_btn.click()
        self.assertEqual(table.rowCount(), count)
        np.testing.assert_allclose(widget.reflection_table_model.reflection_data[:, 3],
                                   [r.intensity for r in phase.reflections])
        before = self.phase_model._condition_snapshot(phase)
        with patch(module + '.ElementPickerDialog') as picker:
            picker.return_value.exec_.return_value = QtWidgets.QDialog.Rejected
            self.controller.choose_atomic_element(0)
        self.assertEqual(self.phase_model._condition_snapshot(phase), before)

    def test_space_group_apply_and_invalid_entry_update_the_editor(self):
        from ...model import eos
        from peritheos import get_material_document

        phase = eos.build_jcpds(eos.Material.from_dict(get_material_document('gold')),
                                origin='file')
        self.phase_model.add_jcpds_object(phase)
        self.controller.show_phase(phase)
        widget = self.jcpds_widget
        widget.space_group_cb.setCurrentIndex(220)
        widget.space_group_cb.activated.emit(220)
        self.assertEqual(phase.params['material_document']['space_group_number'], 221)
        self.assertEqual(widget.space_group_cb.currentText(), '221 — Pm-3m')
        self.assertIn((1, 0, 0), {(r.h, r.k, r.l) for r in phase.reflections})
        self.assertEqual(widget.structure_composition_lbl.text(),
                         'Calculated Z = 1 · differs from stored Z')
        self.assertEqual(phase.params['zc'], 4)
        np.testing.assert_allclose(widget.reflection_table_model.reflection_data[:, 3],
                                   [r.intensity for r in phase.reflections])
        before = self.phase_model._condition_snapshot(phase)
        depth = self.model.history.depth
        widget.space_group_apply_btn.click()
        self.assertEqual(widget.space_group_cb.currentText(), '221 — Pm-3m')
        self.assertEqual(self.model.history.depth, depth)
        widget.space_group_txt.setText('invalid group')
        QTest.keyClick(widget.space_group_txt, QtCore.Qt.Key_Return)
        self.assertEqual(self.phase_model._condition_snapshot(phase), before)
        self.assertEqual(widget.space_group_cb.value(), phase.params['material_document']['space_group'])
        self.assertEqual(widget.space_group_cb.currentText(), '221 — Pm-3m')
        self.assertFalse(widget.structure_edit_status_lbl.isHidden())
        self.assertEqual(self.model.history.depth, depth)

    def test_selecting_eos_updates_model_and_parameter_rows(self):
        self.jcpds_widget.parameter_tabs.setCurrentWidget(self.jcpds_widget.eos_gb)
        cb = self.jcpds_widget.eos_type_cb
        cb.setCurrentIndex(cb.findData('BM4'))
        self.assertEqual(self.phase_model.get_eos_type(5), 'BM4')
        # BM4 shows the K0'' row, BM3 does not
        self.assertTrue(self.jcpds_widget.eos_Kpp_txt.isVisibleTo(
            self.jcpds_widget))
        cb.setCurrentIndex(cb.findData('BM3'))
        self.assertEqual(self.phase_model.get_eos_type(5), 'BM3')
        self.assertFalse(self.jcpds_widget.eos_Kpp_txt.isVisibleTo(
            self.jcpds_widget))

    def test_reference_pressure_field_updates_the_live_equation(self):
        from ...model.util.eos_phase import EosPhase

        cb = self.jcpds_widget.eos_type_cb
        cb.setCurrentIndex(cb.findData('BM2Reference'))
        field = self.jcpds_widget.eos_P0_txt
        self.assertFalse(field.isHidden())
        field.setText('32.7')
        field.editingFinished.emit()
        phase = self.phase_model.phases[5]
        self.assertEqual(phase.params['p0'], 32.7)
        self.assertAlmostEqual(EosPhase.from_jcpds(phase).pressure(phase.params['v0']), 32.7)
        cb.setCurrentIndex(cb.findData('BM3'))
        self.assertTrue(field.isHidden())

    def test_reference_pressure_legacy_export_shows_an_explanation(self):
        from tempfile import TemporaryDirectory

        cb = self.jcpds_widget.eos_type_cb
        cb.setCurrentIndex(cb.findData('BM2Reference'))
        self.jcpds_widget.eos_P0_txt.setText('32.7')
        self.jcpds_widget.eos_P0_txt.editingFinished.emit()
        with TemporaryDirectory() as directory, patch.object(self.widget, 'show_error_msg') as error:
            path = os.path.join(directory, 'reference.jcpds')
            self.controller.save_as_btn_clicked(path)
            self.assertFalse(os.path.exists(path))
        self.assertIn('.eosmat', error.call_args.args[0])

    def test_holzapfel_shows_material_data_rows(self):
        self.jcpds_widget.parameter_tabs.setCurrentWidget(self.jcpds_widget.eos_gb)
        cb = self.jcpds_widget.eos_type_cb
        cb.setCurrentIndex(cb.findData('Holzapfel'))
        for field in (self.jcpds_widget.eos_n_txt,
                      self.jcpds_widget.eos_z_txt,
                      self.jcpds_widget.eos_zc_txt):
            self.assertTrue(field.isVisibleTo(self.jcpds_widget))
        # legacy phase has no n/Z/Zc — the fields are empty, not '0'
        self.assertEqual(self.jcpds_widget.eos_n_txt.text(), '')

    def test_editing_k0pp_writes_state(self):
        cb = self.jcpds_widget.eos_type_cb
        cb.setCurrentIndex(cb.findData('BM4'))
        self.jcpds_widget.eos_Kpp_txt.setText('-0.04')
        self.jcpds_widget.eos_Kpp_txt.editingFinished.emit()
        self.assertAlmostEqual(
            self.phase_model.phases[5].params['k0pp0'], -0.04)

    def test_thermal_selector_derived_from_values(self):
        self.jcpds_widget.parameter_tabs.setCurrentWidget(self.jcpds_widget.eos_gb)
        # au_Anderson.jcpds carries thermal expansion -> AlphaKT selected
        self.setup_selected_row(2)
        click_button(self.phase_widget.edit_btn)
        self.assertEqual(self.jcpds_widget.get_thermal_type(), 'alphakt')
        self.assertTrue(self.jcpds_widget.eos_alphaT_txt.isVisibleTo(
            self.jcpds_widget))
        # a BM3 phase shows only its own parameters otherwise
        self.assertFalse(self.jcpds_widget.eos_Kpp_txt.isVisibleTo(
            self.jcpds_widget))

    def test_selecting_no_thermal_model_zeroes_coefficients(self):
        self.jcpds_widget.parameter_tabs.setCurrentWidget(self.jcpds_widget.eos_gb)
        self.setup_selected_row(2)
        click_button(self.phase_widget.edit_btn)
        cb = self.jcpds_widget.thermal_type_cb
        self.assertNotEqual(
            self.phase_model.phases[2].params['alpha_t0'], 0.0)
        cb.setCurrentIndex(cb.findData('none'))
        for param in ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'):
            self.assertEqual(self.phase_model.phases[2].params[param], 0.0)
        self.assertFalse(self.jcpds_widget.eos_alphaT_txt.isVisibleTo(
            self.jcpds_widget))

    def test_thermal_dropdown_offers_peritheos_models(self):
        cb = self.jcpds_widget.thermal_type_cb
        keys = [cb.itemData(i) for i in range(cb.count())]
        from ...model.util.eos_phase import THERMAL_EOS_TYPES
        self.assertEqual(set(keys), {'none', 'alphakt', *THERMAL_EOS_TYPES})

    def test_canonical_alphakt_is_editable_and_rejects_incompatible_switch(self):
        self.jcpds_widget.parameter_tabs.setCurrentWidget(self.jcpds_widget.eos_gb)
        from ...model import eos
        from peritheos import get_material_document
        material = eos.Material.from_dict(get_material_document('gold'))
        index = next(i for i, r in enumerate(material.eos_records)
                     if r['identifier'] == 'gold_hirose_2008_bm3_fit2')
        phase = eos.build_jcpds(material, record_index=index, origin='bundled')
        self.phase_model.add_jcpds_object(phase, filename=phase.filename)
        self.phase_model.duplicate_eos_record(6, index)
        self.controller.show_phase(phase, wavelength=0.31)
        widget = self.jcpds_widget
        self.assertEqual(widget.get_thermal_type(), 'AlphaKT')
        field = widget.thermal_parameter_fields['AlphaKT', 'kprime_log_coefficient']
        self.assertTrue(field.isVisibleTo(widget))
        self.assertTrue(field.isEnabled())
        bm2_index = widget.eos_type_cb.findData('BM2')
        self.assertFalse(widget.eos_type_cb.model().item(bm2_index).isEnabled())
        self.assertIn('K′', widget.eos_type_cb.itemData(bm2_index, QtCore.Qt.ToolTipRole))
        # Programmatic changes must be safe too, even if they bypass a disabled item.
        widget.eos_type_cb.setCurrentIndex(bm2_index)
        self.assertEqual(phase.params['eos_type'], 'BM3')
        self.assertEqual(widget.get_eos_type(), 'BM3')
        field.setText('0')
        field.editingFinished.emit()
        self.assertTrue(widget.eos_type_cb.model().item(bm2_index).isEnabled())
        widget.eos_type_cb.setCurrentIndex(bm2_index)
        self.assertEqual(phase.params['eos_type'], 'BM2')
        self.assertEqual(phase.params['thermal_type'], 'AlphaKT')
        self.assertTrue(widget.eos_calculation_status_lbl.isHidden())

    def test_selecting_native_alphakt_keeps_model_and_coefficients(self):
        cb = self.jcpds_widget.thermal_type_cb
        cb.setCurrentIndex(cb.findData('AlphaKT'))
        self.assertEqual(self.phase_model.get_thermal_type(5), 'AlphaKT')
        self.assertTrue(self.jcpds_widget.eos_calculation_status_lbl.isHidden())
        for name, value in [('alpha0', '3e-5'), ('dK_dT', '-0.01')]:
            field = self.jcpds_widget.thermal_parameter_fields['AlphaKT', name]
            field.setText(value)
            field.editingFinished.emit()
        self.assertTrue(self.jcpds_widget.eos_calculation_status_lbl.isHidden())
        self.phase_model.set_pressure_temperature(5, 10, 1000)
        self.assertEqual(self.phase_model.get_thermal_type(5), 'AlphaKT')
        self.assertEqual(self.phase_model.phases[5].params['thermal_parameters']['alpha0'], 3e-5)
        previous_volume = self.phase_model.phases[5].params['v']
        field = self.jcpds_widget.thermal_parameter_fields['AlphaKT', 'dK_dT']
        field.setText('-100')
        field.editingFinished.emit()
        self.assertEqual(self.phase_model.phases[5].params['thermal_parameters']['dK_dT'], -.01)
        self.assertEqual(self.phase_model.phases[5].params['v'], previous_volume)
        self.assertFalse(self.jcpds_widget.eos_calculation_status_lbl.isHidden())

    def test_selecting_mgd_updates_model_and_rows(self):
        self.jcpds_widget.parameter_tabs.setCurrentWidget(self.jcpds_widget.eos_gb)
        cb = self.jcpds_widget.thermal_type_cb
        cb.setCurrentIndex(cb.findData('MieGruneisenDebye'))
        self.assertEqual(self.phase_model.get_thermal_type(5),
                         'MieGruneisenDebye')
        # MGD parameter rows appear, the legacy coefficient rows hide
        self.assertTrue(self.jcpds_widget.eos_theta_txt.isVisibleTo(
            self.jcpds_widget))
        self.assertFalse(self.jcpds_widget.eos_alphaT_txt.isVisibleTo(
            self.jcpds_widget))
        # the molar conversion needs n and Zc — shown even for BM3
        self.assertTrue(self.jcpds_widget.eos_n_txt.isVisibleTo(
            self.jcpds_widget))
        self.assertTrue(self.jcpds_widget.eos_zc_txt.isVisibleTo(
            self.jcpds_widget))
        # temperature spinbox follows has_thermal_expansion
        self.assertTrue(self.phase_model.phases[5].has_thermal_expansion())

        cb.setCurrentIndex(cb.findData('none'))
        self.assertEqual(self.phase_model.get_thermal_type(5), '')
        self.assertFalse(self.jcpds_widget.eos_theta_txt.isVisibleTo(
            self.jcpds_widget))
        self.assertFalse(self.jcpds_widget.eos_n_txt.isVisibleTo(
            self.jcpds_widget))

    def test_editing_mgd_parameters_writes_state(self):
        cb = self.jcpds_widget.thermal_type_cb
        cb.setCurrentIndex(cb.findData('MieGruneisenDebye'))
        self.jcpds_widget.eos_theta_txt.setText('170')
        self.jcpds_widget.eos_theta_txt.editingFinished.emit()
        self.jcpds_widget.eos_gamma_txt.setText('2.97')
        self.jcpds_widget.eos_gamma_txt.editingFinished.emit()
        params = self.phase_model.phases[5].params
        self.assertAlmostEqual(params['theta_t0'], 170.0)
        self.assertAlmostEqual(params['gamma_t0'], 2.97)

    def test_editing_sokolova_parameter_writes_constructor_dictionary(self):
        phase = self.phase_model.phases[5]
        phase.params['eos_type'] = 'Holzapfel'
        phase.params['n'] = 1
        phase.params['z'] = 75
        phase.params['zc'] = 2
        phase.params['thermal_type'] = 'Sokolova2016'
        phase.params['thermal_parameters'] = {
            'Tr': 298.15, 'QE1o': 179.5, 'mE1': 1.5,
            'QE2o': 83.0, 'mE2': 1.5, 'delta': 0.134,
            't': 0.087, 'a_0': 0.0, 'm': 0.0, 'g': 0.0,
            'e_0': 0.0,
        }
        phase.params['t_ref'] = 298.15
        self.controller.show_phase(phase, wavelength=0.31)

        field = self.jcpds_widget.sokolova_parameter_fields['delta']
        field.setText('0.2')
        field.editingFinished.emit()

        self.assertAlmostEqual(
            phase.params['thermal_parameters']['delta'], 0.2)

    def test_editing_thermal_reference_updates_constructor_dictionary(self):
        cb = self.jcpds_widget.thermal_type_cb
        cb.setCurrentIndex(cb.findData('MieGruneisenDebye'))
        self.jcpds_widget.eos_tref_txt.setText('300')
        self.jcpds_widget.eos_tref_txt.editingFinished.emit()

        params = self.phase_model.phases[5].params
        self.assertAlmostEqual(params['t_ref'], 300.0)
        self.assertAlmostEqual(params['thermal_parameters']['Tr'], 300.0)

    def test_adds_a_complete_custom_eos_record(self):
        phase = self.phase_model.phases[5]
        record = self.phase_model.eos_record_from_phase(5)
        record['label'] = 'My referenced fit'
        record['reference'] = {'authors': ['Tester'], 'year': 2026}
        self.controller._record_dialog = MagicMock(return_value=record)

        click_button(self.jcpds_widget.eos_record_add_btn)

        self.assertEqual(len(phase.params['eos_records']), 1)
        self.assertEqual(phase.params['eos_records'][0]['label'],
                         'My referenced fit')
        self.assertEqual(phase.params['eos_record_origins'], ['custom'])
        self.assertTrue(self.jcpds_widget.eos_record_edit_btn.isEnabled())

    def test_bundled_record_requires_duplicate_before_editing(self):
        from ...model import eos

        gold = next(material for material in eos.load_materials()
                    if material.formula == 'Au')
        phase = eos.build_jcpds(gold, record_index=0, origin='bundled')
        self.phase_model.add_jcpds_object(phase, filename=phase.filename)
        self.controller.show_phase(phase, wavelength=0.31)

        self.assertFalse(self.jcpds_widget.eos_K_txt.isEnabled())
        self.assertFalse(self.jcpds_widget.eos_record_edit_btn.isEnabled())
        custom = dict(phase.params['eos_records'][0])
        custom['label'] = 'Editable copy'
        self.controller._record_dialog = MagicMock(return_value=custom)
        click_button(self.jcpds_widget.eos_record_duplicate_btn)

        self.assertEqual(self.phase_model.eos_record_origin(6), 'custom')
        self.assertTrue(self.jcpds_widget.eos_K_txt.isEnabled())
        self.assertTrue(self.jcpds_widget.eos_record_delete_btn.isEnabled())

    def test_failed_duplicate_reports_error_and_preserves_phase(self):
        from copy import deepcopy
        from peritheos import get_material_document
        from ...model import eos

        document = get_material_document('gold')
        index = next(i for i, record in enumerate(document['eos_records'])
                     if record['eos']['type'] == 'Vinet' and not record.get('thermal'))
        phase = eos.build_jcpds(eos.Material.from_dict(document),
                                record_index=index, origin='bundled')
        self.phase_model.add_jcpds_object(phase, filename=phase.filename)
        self.phase_model.set_pressure_temperature(6, 20., 1000.)
        self.controller.show_phase(phase, wavelength=0.31)
        before = self.phase_model._condition_snapshot(phase)
        record = deepcopy(phase.params['eos_records'][index])
        record['equation_kind'] = 'thermal'
        record['thermal'] = {
            'type': 'AlphaKT', 'model': 'thermal_reference_state',
            'parameters': {'Tr': 300., 'alpha0': 3e-5, 'dK_dT': -1.},
        }
        self.controller._record_dialog = MagicMock(return_value=record)
        self.jcpds_widget.show_eos_error = MagicMock()

        click_button(self.jcpds_widget.eos_record_duplicate_btn)

        self.assertEqual(self.phase_model._condition_snapshot(phase), before)
        self.jcpds_widget.show_eos_error.assert_called()
        self.assertIn('non-positive bulk modulus',
                      self.jcpds_widget.show_eos_error.call_args.args[0])

    def test_save_as_eosmat_preserves_records_and_structure(self):
        from ...model import eos

        gold = next(material for material in eos.load_materials()
                    if material.formula == 'Au')
        phase = eos.build_jcpds(gold, record_index=0, origin='bundled')
        self.phase_model.add_jcpds_object(phase, filename=phase.filename)
        self.controller.show_phase(phase, wavelength=0.31)
        filename = os.path.join(jcpds_path, 'dummy.eosmat')

        self.controller.save_as_btn_clicked(filename)
        loaded = eos.load_material_file(filename)

        self.assertEqual(loaded.atom_sites, gold.atom_sites)
        self.assertEqual(loaded.eos_records, gold.eos_records)
