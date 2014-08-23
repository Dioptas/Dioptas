# -*- coding: utf8 -*-
# - GUI program for fast processing of 2D X-ray data
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

from copy import deepcopy
from functools import wraps
import numpy as np

from PyQt4 import QtGui, QtCore
from Data.jcpds import jcpds

from Views.JcpdsEditorWidget import JcpdsEditorWidget


def _update_view(inner_function):
    @wraps(inner_function)
    def wrapper(self):
        inner_function(self)
        self.jcpds_phase.compute_v0()
        self.jcpds_phase.compute_d0()
        self.view.show_jcpds(self.jcpds_phase)
    return wrapper


class JcpdsEditorController(QtCore.QObject):
    canceled_editor = QtCore.pyqtSignal(jcpds)
    lattice_param_changed = QtCore.pyqtSignal()
    eos_param_changed = QtCore.pyqtSignal()
    reflections_number_changed = QtCore.pyqtSignal()
    reflections_param_changed = QtCore.pyqtSignal()

    def __init__(self, working_dir, jcpds_phase=None):
        super(JcpdsEditorController, self).__init__()
        self.view = JcpdsEditorWidget()
        self.working_dir=working_dir
        self.create_connections()
        if jcpds_phase is not None:
            self.show_phase(jcpds_phase)

    def show_phase(self, jcpds_phase=None):
        if jcpds_phase is None:
            jcpds_phase = jcpds()
        self.start_jcpds_phase = deepcopy(jcpds_phase)
        self.jcpds_phase = jcpds_phase
        self.view.show_jcpds(jcpds_phase)
        self.view.raise_widget()

    def create_connections(self):
        self.view.comments_txt.editingFinished.connect(self.comments_changed)

        self.view.symmetry_cb.currentIndexChanged.connect(self.symmetry_changed)

        self.view.lattice_a_txt.editingFinished.connect(self.lattice_a_changed)
        self.view.lattice_b_txt.editingFinished.connect(self.lattice_b_changed)
        self.view.lattice_c_txt.editingFinished.connect(self.lattice_c_changed)

        self.view.lattice_ab_txt.editingFinished.connect(self.lattice_ab_changed)
        self.view.lattice_ca_txt.editingFinished.connect(self.lattice_ca_changed)
        self.view.lattice_cb_txt.editingFinished.connect(self.lattice_cb_changed)

        self.view.lattice_alpha_txt.editingFinished.connect(self.lattice_alpha_changed)
        self.view.lattice_beta_txt.editingFinished.connect(self.lattice_beta_changed)
        self.view.lattice_gamma_txt.editingFinished.connect(self.lattice_gamma_changed)

        self.view.eos_K_txt.editingFinished.connect(self.eos_K_changed)
        self.view.eos_Kp_txt.editingFinished.connect(self.eos_Kp_changed)
        self.view.eos_alphaT_txt.editingFinished.connect(self.eos_alphaT_changed)
        self.view.eos_dalphadT_txt.editingFinished.connect(self.eos_dalphadT_changed)
        self.view.eos_dKdT_txt.editingFinished.connect(self.eos_dKdT_changed)
        self.view.eos_dKpdT_txt.editingFinished.connect(self.eos_dKpdT_changed)

        self.view.reflections_delete_btn.clicked.connect(self.reflections_delete_btn_click)
        self.view.reflections_add_btn.clicked.connect(self.reflections_add_btn_click)
        self.view.reflections_clear_btn.clicked.connect(self.reflections_clear_btn_click)

        self.view.reflection_table.cellChanged.connect(self.reflection_table_changed)

        self.view.save_as_btn.clicked.connect(self.save_as_btn_click)
        self.view.ok_btn.clicked.connect(self.ok_btn_click)
        self.view.cancel_btn.clicked.connect(self.cancel_btn_click)

    @_update_view
    def comments_changed(self):
        self.jcpds_phase.comments[0] = str(self.view.comments_txt.text())

    @_update_view
    def symmetry_changed(self):
        new_symmetry = str(self.view.symmetry_cb.currentText()).upper()
        self.jcpds_phase.symmetry = new_symmetry

    @_update_view
    def lattice_a_changed(self):
        self.jcpds_phase.a0 = float(str(self.view.lattice_a_txt.text()))
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_b_changed(self):
        self.jcpds_phase.b0 = float(str(self.view.lattice_b_txt.text()))
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_c_changed(self):
        self.jcpds_phase.c0 = float(str(self.view.lattice_c_txt.text()))
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_ab_changed(self):
        ab_ratio = float(str(self.view.lattice_ab_txt.text()))
        self.jcpds_phase.a0 = self.jcpds_phase.b0 * ab_ratio
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_ca_changed(self):
        ca_ratio = float(str(self.view.lattice_ca_txt.text()))
        self.jcpds_phase.c0 = self.jcpds_phase.a0 * ca_ratio
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_cb_changed(self):
        cb_ratio = float(str(self.view.lattice_cb_txt.text()))
        self.jcpds_phase.c0 = self.jcpds_phase.b0 * cb_ratio
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_alpha_changed(self):
        self.jcpds_phase.alpha0 = float(str(self.view.lattice_alpha_txt.text()))
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_beta_changed(self):
        self.jcpds_phase.beta0 = float(str(self.view.lattice_beta_txt.text()))
        self.lattice_param_changed.emit()

    @_update_view
    def lattice_gamma_changed(self):
        self.jcpds_phase.gamma0 = float(str(self.view.lattice_gamma_txt.text()))
        self.lattice_param_changed.emit()

    def eos_K_changed(self):
        self.jcpds_phase.k0 = float(str(self.view.eos_K_txt.text()))
        self.eos_param_changed.emit()

    def eos_Kp_changed(self):
        self.jcpds_phase.k0p0 = float(str(self.view.eos_Kp_txt.text()))
        self.eos_param_changed.emit()

    def eos_alphaT_changed(self):
        self.jcpds_phase.alpha0 = float(str(self.view.eos_alphaT_txt.text()))
        self.eos_param_changed.emit()

    def eos_dalphadT_changed(self):
        self.jcpds_phase.d_alpha_dt =float(str(self.view.eos_dalphadT_txt.text()))
        self.eos_param_changed.emit()

    def eos_dKdT_changed(self):
        self.jcpds_phase.dk0dt = float(str(self.view.eos_dKdT_txt.text()))
        self.eos_param_changed.emit()

    def eos_dKpdT_changed(self):
        self.jcpds_phase.dk0pdt = float(str(self.view.eos_dKpdT_txt.text()))
        self.eos_param_changed.emit()

    def reflections_delete_btn_click(self):
        rows = self.view.get_selected_reflections()
        if rows is None:
            return

        rows.sort()
        rows = np.array(rows)
        for ind in range(len(rows)):
            self.view.remove_reflection_from_table(rows[ind])
            del self.jcpds_phase.reflections[rows[ind]]
            rows = rows - 1
        self.view.reflection_table.resizeColumnsToContents()
        self.reflections_number_changed.emit()

    def reflections_add_btn_click(self):
        self.jcpds_phase.add_reflection()
        self.view.add_reflection_to_table()
        self.view.reflection_table.selectRow(self.view.reflection_table.rowCount()-1)
        self.reflections_number_changed.emit()

    def reflection_table_changed(self, row, col):
        label_item = self.view.reflection_table.item(row, col)
        value = float(str(label_item.text()))
        if col == 0: #h
            self.jcpds_phase.reflections[row].h = value
        elif col == 1: #k
            self.jcpds_phase.reflections[row].k = value
        elif col ==2: #l
            self.jcpds_phase.reflections[row].l = value
        elif col == 3: #intensity
            self.jcpds_phase.reflections[row].intensity = value

        self.jcpds_phase.compute_d0()
        self.view.show_jcpds(self.jcpds_phase)
        self.reflections_param_changed.emit()

    def reflections_clear_btn_click(self):
        self.view.reflection_table.clearContents()
        self.view.reflection_table.setRowCount(0)
        self.view.reflection_table.resizeColumnsToContents()
        self.jcpds_phase.reflections = []
        self.reflections_number_changed.emit()

    def save_as_btn_click(self, filename = False):
        if filename is False:
            filename = str(QtGui.QFileDialog.getSaveFileName(self.view, "Save JCPDS phase.",
                                                             self.working_dir['phase'],
                                                             ('JCPDS Phase (*.jcpds)')))

        if filename != '':
            self.jcpds_phase.write_file(filename)

    def ok_btn_click(self):
        self.view.close()

    def cancel_btn_click(self):
        self.view.close()
        self.jcpds_phase = deepcopy(self.start_jcpds_phase)
        self.canceled_editor.emit(self.jcpds_phase)


