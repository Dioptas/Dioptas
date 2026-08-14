# SPDX-License-Identifier: MIT

from copy import deepcopy
from functools import partial

import numpy as np
from qtpy import QtWidgets, QtCore, QtGui

from ....widgets.UtilityWidgets import save_file_dialog
from ....widgets.EosRecordDialog import EosRecordDialog
from ....widgets.integration.PhaseEditorWidget import PhaseEditorWidget
from ....model.PhaseModel import PhaseLoadError

# imports for type hinting in PyCharm -- DO NOT DELETE
from ....model.util.jcpds import jcpds, jcpds_reflection
from ....model.DioptasModel import DioptasModel
from ....widgets.integration import IntegrationWidget


class PhaseEditorController(QtCore.QObject):
    """
    PhaseEditorController handles all the signals and changes associated with Jcpds editor widget
    """
    canceled_editor = QtCore.Signal(jcpds)

    # lattice_param_changed = QtCore.Signal()
    # eos_param_changed = QtCore.Signal()
    #
    # reflection_line_edited = QtCore.Signal()
    # reflection_line_removed = QtCore.Signal(int)
    # reflection_line_cleared = QtCore.Signal()

    def __init__(self, integration_widget, dioptas_model=None, jcpds_phase=None):
        """
        :param integration_widget: Reference to an IntegrationWidget
        :param dioptas_model: Reference to DioptasModel object
        :param jcpds_phase: Reference to JcpdsPhase object

        :type integration_widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        :type jcpds_phase: jcpds
        """
        super().__init__()
        self.integration_widget = integration_widget
        self.jcpds_widget = PhaseEditorWidget(integration_widget)
        self.phase_widget = self.integration_widget.phase_widget
        self.model = dioptas_model
        self.phase_model = self.model.phase_model
        self._configure_eos_types()
        self.create_connections()

        self.previous_header_item_index_sorted = None
        self.active = False
        self.phase_ind = -1

        if jcpds_phase is not None:
            self.show_phase(jcpds_phase)

    def show_phase(self, jcpds_phase=None, wavelength=None):
        self.start_jcpds_phase = deepcopy(jcpds_phase)
        self.jcpds_phase = jcpds_phase
        self.phase_ind = self.phase_model.phases.index(jcpds_phase)
        if wavelength is None:
            if self.model.calibration_model is not None:
                wavelength = self.model.calibration_model.wavelength * 1e10
        self.jcpds_widget.show_jcpds(jcpds_phase, wavelength)
        self._update_eos_record_controls()

    def _configure_eos_types(self):
        """Fill the EoS combobox with every equation Peritheos supports,
        each with the parameter rows its constructor needs (Holzapfel
        additionally shows the material data n/Z/Zc it converts with)."""
        from ....model.util.eos_phase import (
            RT_EOS_TYPES, EOS_DISPLAY_NAMES, eos_parameter_names)

        eos_types = []
        for key in RT_EOS_TYPES:
            names = eos_parameter_names(key)
            if key == 'Holzapfel':
                names = names + ['Zc']
            eos_types.append((key, EOS_DISPLAY_NAMES.get(key, key), names))
        self.jcpds_widget.configure_eos_types(eos_types)

    def create_connections(self):
        # Phase Widget Signals
        self.phase_widget.edit_btn.clicked.connect(self.edit_btn_callback)
        self.phase_widget.phase_tw.currentCellChanged.connect(self.phase_selection_changed)

        # Phase Model signals
        self.phase_model.phase_changed.connect(self.phase_changed)
        self.phase_model.reflection_added.connect(self.update_reflection_table)
        self.phase_model.reflection_deleted.connect(self.update_reflection_table)

        # Information fields
        self.jcpds_widget.comments_txt.editingFinished.connect(self.comments_changed)
        self.jcpds_widget.symmetry_cb.currentIndexChanged.connect(self.symmetry_changed)
        #
        # Lattice Parameter fields
        self.jcpds_widget.lattice_a_sb.valueChanged.connect(partial(self.param_sb_changed,
                                                                    widget=self.jcpds_widget.lattice_a_sb,
                                                                    param='a0'))
        self.jcpds_widget.lattice_b_sb.valueChanged.connect(partial(self.param_sb_changed,
                                                                    widget=self.jcpds_widget.lattice_b_sb,
                                                                    param='b0'))
        self.jcpds_widget.lattice_c_sb.valueChanged.connect(partial(self.param_sb_changed,
                                                                    widget=self.jcpds_widget.lattice_c_sb,
                                                                    param='c0'))

        self.jcpds_widget.lattice_ab_sb.valueChanged.connect(self.lattice_ab_changed)
        self.jcpds_widget.lattice_ca_sb.valueChanged.connect(self.lattice_ca_changed)
        self.jcpds_widget.lattice_cb_sb.valueChanged.connect(self.lattice_cb_changed)

        self.jcpds_widget.lattice_alpha_sb.valueChanged.connect(partial(self.param_sb_changed,
                                                                        widget=self.jcpds_widget.lattice_alpha_sb,
                                                                        param='alpha0'))
        self.jcpds_widget.lattice_beta_sb.valueChanged.connect(partial(self.param_sb_changed,
                                                                       widget=self.jcpds_widget.lattice_beta_sb,
                                                                       param='beta0'))
        self.jcpds_widget.lattice_gamma_sb.valueChanged.connect(partial(self.param_sb_changed,
                                                                        widget=self.jcpds_widget.lattice_gamma_sb,
                                                                        param='gamma0'))

        self.jcpds_widget.lattice_length_step_txt.editingFinished.connect(self.lattice_length_step_changed)
        self.jcpds_widget.lattice_angle_step_txt.editingFinished.connect(self.lattice_angle_step_changed)
        self.jcpds_widget.lattice_ratio_step_txt.editingFinished.connect(self.lattice_ratio_step_changed)

        # Equation of state fields
        self.jcpds_widget.eos_type_cb.currentIndexChanged.connect(self.eos_type_changed)
        self.jcpds_widget.thermal_type_cb.currentIndexChanged.connect(self.thermal_type_changed)
        self.jcpds_widget.eos_record_cb.currentIndexChanged.connect(
            self.eos_record_changed)
        self.jcpds_widget.eos_record_add_btn.clicked.connect(
            self.add_eos_record)
        self.jcpds_widget.eos_record_duplicate_btn.clicked.connect(
            self.duplicate_eos_record)
        self.jcpds_widget.eos_record_edit_btn.clicked.connect(
            self.edit_eos_record)
        self.jcpds_widget.eos_record_delete_btn.clicked.connect(
            self.delete_eos_record)
        self.jcpds_widget.eos_record_default_btn.clicked.connect(
            self.set_default_eos_record)
        self.jcpds_widget.eos_K_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                    widget=self.jcpds_widget.eos_K_txt,
                                                                    param='k0'))
        self.jcpds_widget.eos_Kp_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                     widget=self.jcpds_widget.eos_Kp_txt,
                                                                     param='k0p0'))
        self.jcpds_widget.eos_Kpp_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                      widget=self.jcpds_widget.eos_Kpp_txt,
                                                                      param='k0pp0'))
        self.jcpds_widget.eos_n_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                    widget=self.jcpds_widget.eos_n_txt,
                                                                    param='n'))
        self.jcpds_widget.eos_z_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                    widget=self.jcpds_widget.eos_z_txt,
                                                                    param='z'))
        self.jcpds_widget.eos_zc_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                     widget=self.jcpds_widget.eos_zc_txt,
                                                                     param='zc'))
        self.jcpds_widget.eos_theta_txt.editingFinished.connect(partial(
            self.thermal_param_txt_changed,
            widget=self.jcpds_widget.eos_theta_txt,
            parameter='theta0', state_param='theta_t0'))
        self.jcpds_widget.eos_gamma_txt.editingFinished.connect(partial(
            self.thermal_param_txt_changed,
            widget=self.jcpds_widget.eos_gamma_txt,
            parameter='gamma0', state_param='gamma_t0'))
        self.jcpds_widget.eos_qt_txt.editingFinished.connect(partial(
            self.thermal_param_txt_changed,
            widget=self.jcpds_widget.eos_qt_txt,
            parameter='q', state_param='q_t0'))
        self.jcpds_widget.eos_tref_txt.editingFinished.connect(partial(
            self.thermal_param_txt_changed,
            widget=self.jcpds_widget.eos_tref_txt,
            parameter='Tr', state_param='t_ref'))
        for parameter, field in (
                self.jcpds_widget.sokolova_parameter_fields.items()):
            field.editingFinished.connect(partial(
                self.thermal_param_txt_changed,
                widget=field, parameter=parameter))
        self.jcpds_widget.eos_alphaT_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                         widget=self.jcpds_widget.eos_alphaT_txt,
                                                                         param='alpha_t0'))
        self.jcpds_widget.eos_dalphadT_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                           widget=self.jcpds_widget.eos_dalphadT_txt,
                                                                           param='d_alpha_dt'))
        self.jcpds_widget.eos_dKdT_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                       widget=self.jcpds_widget.eos_dKdT_txt,
                                                                       param='dk0dt'))
        self.jcpds_widget.eos_dKpdT_txt.editingFinished.connect(partial(self.param_txt_changed,
                                                                        widget=self.jcpds_widget.eos_dKpdT_txt,
                                                                        param='dk0pdt'))

        # Reflections Controls
        self.jcpds_widget.reflections_add_btn.clicked.connect(self.reflections_add_btn_click)
        self.jcpds_widget.reflections_delete_btn.clicked.connect(self.reflections_delete_btn_click)
        self.jcpds_widget.reflections_clear_btn.clicked.connect(self.reflections_clear_btn_click)
        self.jcpds_widget.reflection_table_model.reflection_edited.connect(self.reflection_table_changed)

        # Table Widgets events
        self.jcpds_widget.reflection_table_view.keyPressEvent = self.reflection_table_key_pressed
        self.jcpds_widget.reflection_table_view.verticalScrollBar().valueChanged.connect(self.reflection_table_scrolled)
        self.jcpds_widget.reflection_table_view.horizontalHeader().sectionClicked.connect(
            self.horizontal_header_clicked)
        #
        # Button fields
        self.jcpds_widget.reload_file_btn.clicked.connect(self.reload_file_btn_clicked)
        self.jcpds_widget.save_as_btn.clicked.connect(self.save_as_btn_clicked)
        #
        # # Closing and opening
        self.jcpds_widget.closeEvent = self.view_closed

    def edit_btn_callback(self):
        selected_row = self.phase_widget.get_selected_phase_row()
        if selected_row >= 0:
            self.show_phase(self.model.phase_model.phases[selected_row])
            self.show_view()

    def phase_selection_changed(self, row, *_):
        if self.active:
            self.show_phase(self.model.phase_model.phases[row])

    def phase_changed(self, ind):
        if self.active and self.phase_ind == ind:
            self.jcpds_phase = self.phase_model.phases[ind]
            self.jcpds_widget.show_jcpds(self.jcpds_phase,
                                         wavelength=self.model.calibration_model.wavelength * 1e10)
            self._update_eos_record_controls()

    def update_filename(self):
        self.jcpds_widget.filename_txt.setText(self.jcpds_phase.filename)

    def comments_changed(self):
        self.jcpds_phase.params['comments'][0] = str(self.jcpds_widget.comments_txt.text())

    def symmetry_changed(self):
        self.phase_model.set_param(self.phase_ind, 'symmetry',
                                   str(self.jcpds_widget.symmetry_cb.currentText()).upper())

    def param_sb_changed(self, widget, param):
        self.phase_model.set_param(self.phase_ind, param, widget.value())

    def param_txt_changed(self, widget, param):
        try:
            value = float(widget.text())
        except ValueError:
            # empty or unparsable (e.g. the n/Z/Zc fields of a legacy
            # phase) — restore what the model has instead of crashing
            self.jcpds_widget.update_eos_parameters(self.jcpds_phase)
            return
        if param == 'zc':
            value = int(value)
        self.phase_model.set_param(self.phase_ind, param, value)

    def thermal_param_txt_changed(self, widget, parameter,
                                  state_param=None):
        """Write an editable thermal constructor parameter back to state."""
        try:
            value = float(widget.text())
        except ValueError:
            self.jcpds_widget.update_eos_parameters(self.jcpds_phase)
            return

        thermal_parameters = dict(
            self.jcpds_phase.params.get('thermal_parameters') or {})
        thermal_parameters[parameter] = value
        # Keep the legacy scalar fields in sync for project compatibility
        # and for UI code that reads them directly.
        if state_param is not None:
            self.jcpds_phase.params[state_param] = value
        self.phase_model.set_param(
            self.phase_ind, 'thermal_parameters', thermal_parameters)

    def eos_type_changed(self):
        eos_type = self.jcpds_widget.get_eos_type()
        if eos_type is None or self.phase_ind < 0:
            return
        self.jcpds_widget.update_eos_parameter_visibility()
        self.phase_model.set_eos_type(self.phase_ind, eos_type)

    def thermal_type_changed(self):
        if self.phase_ind < 0:
            return
        key = self.jcpds_widget.get_thermal_type()
        self.jcpds_widget.update_thermal_parameter_visibility()
        self.jcpds_widget.update_eos_parameter_visibility()
        if key in ('MieGruneisenDebye', 'MieGruneisenEinstein',
                   'Sokolova2016'):
            # full peritheos engine; computes once theta0/gamma0 (and
            # n/Zc) are filled in — until then it logs and behaves like
            # a phase without thermal expansion
            self.phase_model.set_thermal_type(self.phase_ind, key)
            return
        if self.phase_model.get_thermal_type(self.phase_ind):
            self.phase_model.set_thermal_type(self.phase_ind, '')
        if key == 'none':
            # removing the thermal model zeroes its coefficients — the
            # phase then computes purely from the room-temperature EoS
            for param in ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'):
                if self.jcpds_phase.params[param]:
                    self.phase_model.set_param(self.phase_ind, param, 0.0)
        # selecting 'alphakt' only reveals its (zero-valued) fields;
        # nothing is written until the user enters coefficients

    def _update_eos_record_controls(self):
        if self.phase_ind < 0:
            return
        phase = self.phase_model.phases[self.phase_ind]
        self.jcpds_widget.update_eos_records(
            self.phase_model.get_eos_reference_labels(self.phase_ind),
            phase.params['eos_current_index'],
            origins=list(phase.params.get('eos_record_origins') or []),
            default_index=phase.params.get('eos_default_index') or 0,
            material_origin=phase.params.get('material_origin') or 'legacy',
            reloadable=self.phase_model.can_reload(self.phase_ind),
        )

    def eos_record_changed(self, record_index):
        if self.phase_ind < 0 or record_index < 0:
            return
        self.phase_model.set_eos_reference(self.phase_ind, record_index)

    def _record_dialog(self, record, title):
        dialog = EosRecordDialog(record, self.jcpds_widget, title=title)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return None
        return dialog.record()

    def add_eos_record(self):
        if self.phase_ind < 0:
            return
        record = self.phase_model.eos_record_from_phase(self.phase_ind)
        record.setdefault('label', 'Custom EoS')
        edited = self._record_dialog(record, 'Add EoS Record')
        if edited is not None:
            self.phase_model.add_eos_record(
                self.phase_ind, edited, origin='custom')

    def duplicate_eos_record(self):
        if self.phase_ind < 0:
            return
        phase = self.phase_model.phases[self.phase_ind]
        index = phase.params['eos_current_index']
        records = phase.params['eos_records']
        if not 0 <= index < len(records):
            return
        record = deepcopy(records[index])
        record.pop('default', None)
        record['label'] = f"{record.get('label') or 'EoS record'} (custom)"
        edited = self._record_dialog(record, 'Duplicate as Custom EoS Record')
        if edited is not None:
            self.phase_model.duplicate_eos_record(
                self.phase_ind, index, edited)

    def edit_eos_record(self):
        if self.phase_ind < 0:
            return
        phase = self.phase_model.phases[self.phase_ind]
        index = phase.params['eos_current_index']
        if not self.phase_model.is_eos_record_editable(self.phase_ind, index):
            return
        records = phase.params['eos_records']
        if not 0 <= index < len(records):
            return
        live_record = self.phase_model.eos_record_from_phase(
            self.phase_ind, records[index])
        edited = self._record_dialog(live_record, 'Edit EoS Record')
        if edited is not None:
            self.phase_model.update_eos_record(
                self.phase_ind, index, edited)

    def delete_eos_record(self):
        if self.phase_ind < 0:
            return
        phase = self.phase_model.phases[self.phase_ind]
        index = phase.params['eos_current_index']
        if not self.phase_model.is_eos_record_editable(self.phase_ind, index):
            return
        records = phase.params['eos_records']
        if not 0 <= index < len(records):
            return
        label = records[index].get('label') or 'this EoS record'
        answer = QtWidgets.QMessageBox.question(
            self.jcpds_widget,
            'Delete EoS Record',
            f'Delete “{label}” from this material?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.phase_model.delete_eos_record(self.phase_ind, index)

    def set_default_eos_record(self):
        if self.phase_ind < 0:
            return
        index = self.phase_model.phases[
            self.phase_ind].params['eos_current_index']
        if self.phase_model.is_eos_record_editable(self.phase_ind, index):
            self.phase_model.set_eos_default(self.phase_ind, index)

    def lattice_ab_changed(self):
        ab_ratio = float(self.jcpds_widget.lattice_ab_sb.value())
        self.phase_model.set_param(self.phase_ind, 'a0',
                                   self.jcpds_phase.params['b0'] * ab_ratio)

    def lattice_ca_changed(self):
        ca_ratio = float(self.jcpds_widget.lattice_ca_sb.value())
        self.phase_model.set_param(self.phase_ind, 'c0',
                                   self.jcpds_phase.params['a0'] * ca_ratio)

    def lattice_cb_changed(self):
        cb_ratio = float(self.jcpds_widget.lattice_cb_sb.value())
        self.phase_model.set_param(self.phase_ind, 'c0',
                                   self.jcpds_phase.params['b0'] * cb_ratio)

    def lattice_length_step_changed(self):
        value = float(str(self.jcpds_widget.lattice_length_step_txt.text()))
        self.jcpds_widget.lattice_a_sb.setSingleStep(value)
        self.jcpds_widget.lattice_b_sb.setSingleStep(value)
        self.jcpds_widget.lattice_c_sb.setSingleStep(value)

    def lattice_angle_step_changed(self):
        value = float(str(self.jcpds_widget.lattice_angle_step_txt.text()))
        self.jcpds_widget.lattice_alpha_sb.setSingleStep(value)
        self.jcpds_widget.lattice_beta_sb.setSingleStep(value)
        self.jcpds_widget.lattice_gamma_sb.setSingleStep(value)

    def lattice_ratio_step_changed(self):
        value = float(str(self.jcpds_widget.lattice_ratio_step_txt.text()))
        self.jcpds_widget.lattice_ab_sb.setSingleStep(value)
        self.jcpds_widget.lattice_ca_sb.setSingleStep(value)
        self.jcpds_widget.lattice_cb_sb.setSingleStep(value)

    def reflections_delete_btn_click(self):
        rows = self.jcpds_widget.get_selected_reflections()
        self.phase_model.delete_multiple_reflections(self.phase_ind, rows)
        if self.jcpds_widget.reflection_table_model.rowCount() >= min(rows) + 1:
            self.jcpds_widget.reflection_table_view.selectRow(min(rows))
        else:
            self.jcpds_widget.reflection_table_view.selectRow(
                self.jcpds_widget.reflection_table_model.rowCount() - 1)

    def reflections_add_btn_click(self):
        self.phase_model.add_reflection(self.phase_ind)
        self.jcpds_widget.reflection_table_view.selectRow(self.jcpds_widget.reflection_table_model.rowCount() - 1)

    def reflections_clear_btn_click(self):
        self.phase_model.clear_reflections(self.phase_ind)

    def reflection_table_changed(self, row, column, value):
        if value != '':
            value = float(value)
            reflection = self.phase_model.phases[self.phase_ind].reflections[row]
            if column == 0:  # h
                reflection.h = value
            elif column == 1:  # k
                reflection.k = value
            elif column == 2:  # l
                reflection.l = value
            elif column == 3:  # intensity
                reflection.intensity = value
            self.phase_model.update_reflection(self.phase_ind, row, reflection)
            self.jcpds_widget.reflection_table_model.update_reflection_data(
                self.phase_model.phases[self.phase_ind].reflections)

    def update_reflection_table(self, phase_ind, *_):
        if phase_ind != self.phase_ind:
            return
        self.jcpds_widget.reflection_table_model.update_reflection_data(self.phase_model.phases[phase_ind].reflections)

    def reflection_table_key_pressed(self, key_press_event):
        if key_press_event == QtGui.QKeySequence.Copy:
            select = self.jcpds_widget.reflection_table_view.selectionModel()
            if not select.hasSelection():
                return # nothing selected

            lines = []
            if self.jcpds_widget.reflection_table_model.wavelength is None:
                lines.append('\t'.join(self.jcpds_widget.reflection_table_model.header_labels)) # Header
                for item in select.selectedRows():
                    line = '{:.0f}\t{:.0f}\t{:.0f}\t{:.2f}\t{:.4f}\t{:.4f}'.format(
                        *self.jcpds_widget.reflection_table_model.reflection_data[item.row(), :]
                    )
                    lines.append(line)
            else:
                lines.append('\t'.join(self.jcpds_widget.reflection_table_model.header_labels)) # Header
                for item in select.selectedRows():
                    line = '{:.0f}\t{:.0f}\t{:.0f}\t{:.2f}\t{:.4f}\t{:.4f}\t{:.4f}\t{:.4f}\t{:.4f}\t{:.4f}'.format(
                        *self.jcpds_widget.reflection_table_model.reflection_data[item.row(), :]
                    )
                    lines.append(line)
            QtWidgets.QApplication.clipboard().setText('\n'.join(lines))

        elif key_press_event == QtGui.QKeySequence.SelectAll:
            self.jcpds_widget.reflection_table_view.selectAll()

    def reflection_table_scrolled(self):
        self.jcpds_widget.reflection_table_view.resizeColumnsToContents()

    def horizontal_header_clicked(self, ind):
        if self.previous_header_item_index_sorted == ind:
            reversed_toggle = True
        else:
            reversed_toggle = False

        if ind == 0:
            self.jcpds_phase.sort_reflections_by_h(reversed_toggle)
        elif ind == 1:
            self.jcpds_phase.sort_reflections_by_k(reversed_toggle)
        elif ind == 2:
            self.jcpds_phase.sort_reflections_by_l(reversed_toggle)
        elif ind == 3:
            self.jcpds_phase.sort_reflections_by_intensity(reversed_toggle)
        elif ind == 4 or ind == 6:
            self.jcpds_phase.sort_reflections_by_d(reversed_toggle)
        elif ind == 5 or ind == 7:
            self.jcpds_phase.sort_reflections_by_d(not reversed_toggle)

        self.jcpds_widget.show_jcpds(self.jcpds_phase, wavelength=self.model.calibration_model.wavelength * 1e10)
        self.jcpds_widget.reflection_table_view.resizeColumnsToContents()

        if self.previous_header_item_index_sorted == ind:
            self.previous_header_item_index_sorted = None
        else:
            self.previous_header_item_index_sorted = ind

    def save_as_btn_clicked(self, filename=False):
        if filename is False:
            filename = save_file_dialog(self.jcpds_widget, "Save phase or material.",
                                        self.model.working_directories['phase'],
                                        ('EoS Material (*.eosmat);;JCPDS Phase (*.jcpds);;Export Table (*.txt)'))

        if filename != '':
            if filename.endswith('.eosmat'):
                from ....model.eos import (
                    material_from_jcpds, save_material_file)
                save_material_file(
                    filename, material_from_jcpds(self.jcpds_phase))
            elif filename.endswith('.jcpds'):
                self.phase_model.save_phase_as(self.phase_ind, filename)
            elif filename.endswith('.txt'):
                self.export_table_data(filename)
            self.show_phase(self.jcpds_phase)

    def export_table_data(self, filename):
        fp = open(filename, 'w', encoding='utf-8')
        for col in range(self.jcpds_widget.reflection_table_model.columnCount()):
            fp.write(self.jcpds_widget.reflection_table_model.header_labels[col] + '\t')
        fp.write('\n')
        for row in range(self.jcpds_widget.reflection_table_model.rowCount()):
            line = ''
            for col in range(self.jcpds_widget.reflection_table_model.columnCount()):
                line = line + self.jcpds_widget.reflection_table_model.index(row, col).data() + '\t'
            line = line + '\n'
            fp.write(line)
        fp.close()

    def reload_file_btn_clicked(self):
        try:
            self.phase_model.reload(self.phase_ind)
        except PhaseLoadError as error:
            self.integration_widget.show_error_msg(
                f'Could not reload:\n\n{error.filename}.\n\n'
                'Please check that the source file still exists and is valid.')

    def show_view(self):
        self.active = True
        self.jcpds_widget.raise_widget()

    def close_view(self):
        self.active = False
        self.jcpds_widget.close()

    def view_closed(self, _):
        self.close_view()
