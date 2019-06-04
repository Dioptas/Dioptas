# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np

from ...widgets.CustomWidgets import NumberTextField, LabelAlignRight, DoubleSpinBoxAlignRight, HorizontalSpacerItem, \
    VerticalSpacerItem, FlatButton, CleanLooksComboBox

from ...model.util.HelperModule import convert_d_to_two_theta


class JcpdsEditorWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(JcpdsEditorWidget, self).__init__(parent)

        self.setWindowTitle('Dioptas - JCPDS Editor')

        self._layout = QtWidgets.QVBoxLayout()

        self._file_layout = QtWidgets.QGridLayout()
        self._file_layout.addWidget(LabelAlignRight('Filename:'), 0, 0)
        self._file_layout.addWidget(LabelAlignRight('Comment:'), 1, 0)

        self.filename_txt = QtWidgets.QLineEdit('')
        self.comments_txt = QtWidgets.QLineEdit('')
        self._file_layout.addWidget(self.filename_txt, 0, 1)
        self._file_layout.addWidget(self.comments_txt, 1, 1)
        self._layout.addLayout((self._file_layout))

        self.lattice_parameters_gb = QtWidgets.QGroupBox('Lattice Parameters')
        self._lattice_parameters_layout = QtWidgets.QVBoxLayout()

        self._symmetry_layout = QtWidgets.QHBoxLayout()
        self._symmetry_layout.addWidget(LabelAlignRight('Symmetry'))
        self.symmetry_cb = CleanLooksComboBox()
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'trigonal', 'rhombohedral',
                           'orthorhombic', 'monoclinic', 'triclinic']
        self.symmetry_cb.addItems(self.symmetries)
        self._symmetry_layout.addWidget(self.symmetry_cb)
        self._symmetry_layout.addSpacerItem(HorizontalSpacerItem())
        self._lattice_parameters_layout.addLayout(self._symmetry_layout)

        self._parameters_layout = QtWidgets.QGridLayout()

        self.lattice_a_sb = DoubleSpinBoxAlignRight()
        self.lattice_a_sb.setSingleStep(0.01)
        self.lattice_a_sb.setMinimum(0)
        self.lattice_a_sb.setMaximum(99999)
        self.lattice_a_sb.setDecimals(4)
        self.lattice_b_sb = DoubleSpinBoxAlignRight()
        self.lattice_b_sb.setMinimum(0)
        self.lattice_b_sb.setMaximum(99999)
        self.lattice_b_sb.setDecimals(4)
        self.lattice_b_sb.setSingleStep(0.01)
        self.lattice_c_sb = DoubleSpinBoxAlignRight()
        self.lattice_c_sb.setMinimum(0)
        self.lattice_c_sb.setMaximum(99999)
        self.lattice_c_sb.setDecimals(4)
        self.lattice_c_sb.setSingleStep(0.01)
        self.lattice_length_step_txt = NumberTextField('0.01')

        self.add_field(self._parameters_layout, self.lattice_a_sb, 'a0:', u"Å", 0, 0)
        self.add_field(self._parameters_layout, self.lattice_b_sb, 'b0:', u"Å", 0, 3)
        self.add_field(self._parameters_layout, self.lattice_c_sb, 'c0:', u"Å", 0, 6)
        self.add_field(self._parameters_layout, self.lattice_length_step_txt, 'st:', u"Å", 0, 9)

        self.lattice_eos_a_txt = NumberTextField()
        self.lattice_eos_b_txt = NumberTextField()
        self.lattice_eos_c_txt = NumberTextField()

        self.add_field(self._parameters_layout, self.lattice_eos_a_txt, 'a:', u"Å", 1, 0)
        self.add_field(self._parameters_layout, self.lattice_eos_b_txt, 'b:', u"Å", 1, 3)
        self.add_field(self._parameters_layout, self.lattice_eos_c_txt, 'c:', u"Å", 1, 6)

        self.lattice_alpha_sb = DoubleSpinBoxAlignRight()
        self.lattice_alpha_sb.setMaximum(180)
        self.lattice_beta_sb = DoubleSpinBoxAlignRight()
        self.lattice_beta_sb.setMaximum(180)
        self.lattice_gamma_sb = DoubleSpinBoxAlignRight()
        self.lattice_gamma_sb.setMaximum(180)
        self.lattice_angle_step_txt = NumberTextField('1')

        self.add_field(self._parameters_layout, self.lattice_alpha_sb, u'α:', u"°", 2, 0)
        self.add_field(self._parameters_layout, self.lattice_beta_sb, u'β:', u"°", 2, 3)
        self.add_field(self._parameters_layout, self.lattice_gamma_sb, u'γ:', u"°", 2, 6)
        self.add_field(self._parameters_layout, self.lattice_angle_step_txt, u'st:', u"°", 2, 9)

        self.lattice_volume_txt = NumberTextField()
        self.lattice_eos_volume_txt = NumberTextField()

        self.add_field(self._parameters_layout, self.lattice_volume_txt, 'V0:', u'Å³', 3, 3)
        self.add_field(self._parameters_layout, self.lattice_eos_volume_txt, 'V:', u'Å³', 3, 6)

        self.lattice_ab_sb = DoubleSpinBoxAlignRight()
        self.lattice_ab_sb.setDecimals(4)
        self.lattice_ca_sb = DoubleSpinBoxAlignRight()
        self.lattice_ca_sb.setDecimals(4)
        self.lattice_cb_sb = DoubleSpinBoxAlignRight()
        self.lattice_cb_sb.setDecimals(4)
        self.lattice_ratio_step_txt = NumberTextField('0.01')

        self.add_field(self._parameters_layout, self.lattice_ab_sb, 'a/b:', None, 4, 0)
        self.add_field(self._parameters_layout, self.lattice_ca_sb, 'c/a:', None, 4, 3)
        self.add_field(self._parameters_layout, self.lattice_cb_sb, 'c/b:', None, 4, 6)
        self.add_field(self._parameters_layout, self.lattice_ratio_step_txt, 'st:', None, 4, 9)

        self._lattice_parameters_layout.addLayout(self._parameters_layout)
        self.lattice_parameters_gb.setLayout(self._lattice_parameters_layout)

        self.eos_gb = QtWidgets.QGroupBox('Equation of State')
        self._eos_layout = QtWidgets.QGridLayout()

        self.eos_K_txt = NumberTextField()
        self.eos_Kp_txt = NumberTextField()
        self.eos_alphaT_txt = NumberTextField()
        self.eos_dalphadT_txt = NumberTextField()
        self.eos_dKdT_txt = NumberTextField()
        self.eos_dKpdT_txt = NumberTextField()

        self.add_field(self._eos_layout, self.eos_K_txt, 'K:', 'GPa', 0, 0)
        self.add_field(self._eos_layout, self.eos_Kp_txt, 'Kp:', None, 1, 0)
        self.add_field(self._eos_layout, self.eos_alphaT_txt, u'α<sub>T</sub>:', '1/K', 2, 0)
        self.add_field(self._eos_layout, self.eos_dalphadT_txt, u'dα<sub>T</sub>/dT:', u'1/K²', 3, 0)
        self.add_field(self._eos_layout, self.eos_dKdT_txt, 'dK/dT:', 'GPa/K', 4, 0)
        self.add_field(self._eos_layout, self.eos_dKpdT_txt, "dK'/dT", '1/K', 5, 0)
        self.eos_gb.setLayout(self._eos_layout)

        self.reflections_gb = QtWidgets.QGroupBox('Reflections')
        self._reflection_layout = QtWidgets.QGridLayout()
        self.reflection_table_view = QtWidgets.QTableView()
        self.reflection_table_model = ReflectionTableModel()
        self.reflection_table_view.setModel(self.reflection_table_model)
        # self.reflection_table.setColumnCount(10)
        self.reflections_add_btn = FlatButton('Add')
        self.reflections_delete_btn = FlatButton('Delete')
        self.reflections_clear_btn = FlatButton('Clear')

        self._reflection_layout.addWidget(self.reflection_table_view, 0, 0, 1, 3)
        self._reflection_layout.addWidget(self.reflections_add_btn, 1, 0)
        self._reflection_layout.addWidget(self.reflections_delete_btn, 1, 1)
        self._reflection_layout.addWidget(self.reflections_clear_btn, 1, 2)

        self.reflections_gb.setLayout(self._reflection_layout)

        self._body_layout = QtWidgets.QGridLayout()
        self._body_layout.addWidget(self.eos_gb, 0, 0)
        self._body_layout.addItem(VerticalSpacerItem(), 1, 0)
        self._body_layout.addWidget(self.reflections_gb, 0, 1, 2, 1)

        self._button_layout = QtWidgets.QHBoxLayout()
        self.save_as_btn = FlatButton('Save As')
        self.reload_file_btn = FlatButton('Reload File')

        self._button_layout.addWidget(self.save_as_btn)
        self._button_layout.addWidget(self.reload_file_btn)
        self._button_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addWidget(self.lattice_parameters_gb)
        self._layout.addLayout(self._body_layout)
        self._layout.addLayout(self._button_layout)
        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.lattice_angle_step_txt.setMaximumWidth(60)
        self.lattice_length_step_txt.setMaximumWidth(60)
        self.lattice_ratio_step_txt.setMaximumWidth(60)

        self.reflection_table_view.setShowGrid(False)
        self.reflection_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.reflection_table_view.setItemDelegate(TextDoubleDelegate())
        self.reflection_table_view.horizontalHeader().setResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        self.eos_gb.setMaximumWidth(200)
        self.eos_gb.setStyleSheet("""
            QLineEdit {
                max-width: 80;
            }
        """)

        self.reflection_table_view.verticalHeader().setDefaultSectionSize(20)
        self.reflection_table_view.verticalHeader().setResizeMode(QtWidgets.QHeaderView.Fixed)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def add_field(self, layout, widget, label_str, unit, x, y):
        layout.addWidget(LabelAlignRight(label_str), x, y)
        layout.addWidget(widget, x, y + 1)
        if unit:
            layout.addWidget(QtWidgets.QLabel(unit), x, y + 2)

    def show_jcpds(self, jcpds_phase, wavelength=None):
        self.update_name(jcpds_phase)
        self.update_lattice_parameters(jcpds_phase)
        self.update_eos_parameters(jcpds_phase)
        self.reflection_table_model.update_reflection_data(jcpds_phase.reflections,
                                                           wavelength)

    def update_eos_parameters(self, jcpds_phase):
        self.eos_K_txt.setText(str(jcpds_phase.params['k0']))
        self.eos_Kp_txt.setText(str(jcpds_phase.params['k0p']))
        self.eos_alphaT_txt.setText(str(jcpds_phase.params['alpha_t0']))
        self.eos_dalphadT_txt.setText(str(jcpds_phase.params['d_alpha_dt']))
        self.eos_dKdT_txt.setText(str(jcpds_phase.params['dk0dt']))
        self.eos_dKpdT_txt.setText(str(jcpds_phase.params['dk0pdt']))

    def update_name(self, jcpds_phase):
        self.filename_txt.setText(jcpds_phase.filename)
        self.comments_txt.setText("/n".join(jcpds_phase.params['comments']))

    def update_lattice_parameters(self, jcpds_phase):
        self.blockAllSignals(True)
        self.symmetry_cb.setCurrentIndex(self.symmetries.index(jcpds_phase.params['symmetry'].lower()))
        self.update_spinbox_enable(jcpds_phase.params['symmetry'])

        if not self.lattice_a_sb.hasFocus():
            self.lattice_a_sb.setValue(jcpds_phase.params['a0'])
        if not self.lattice_b_sb.hasFocus():
            self.lattice_b_sb.setValue(jcpds_phase.params['b0'])
        if not self.lattice_c_sb.hasFocus():
            self.lattice_c_sb.setValue(jcpds_phase.params['c0'])

        self.lattice_eos_a_txt.setText('{0:.4f}'.format(jcpds_phase.params['a']))
        self.lattice_eos_b_txt.setText('{0:.4f}'.format(jcpds_phase.params['b']))
        self.lattice_eos_c_txt.setText('{0:.4f}'.format(jcpds_phase.params['c']))

        self.lattice_eos_volume_txt.setText('{0:.4f}'.format(jcpds_phase.params['v']))

        try:
            if not self.lattice_ab_sb.hasFocus():
                self.lattice_ab_sb.setValue(jcpds_phase.params['a0'] / float(jcpds_phase.params['b0']))
        except ZeroDivisionError:
            self.lattice_ab_sb.setSpecialValueText('Inf')

        try:
            if not self.lattice_ca_sb.hasFocus():
                self.lattice_ca_sb.setValue(jcpds_phase.params['c0'] / float(jcpds_phase.params['a0']))
        except ZeroDivisionError:
            self.lattice_ca_sb.setSpecialValueText('Inf')

        try:
            if not self.lattice_cb_sb.hasFocus():
                self.lattice_cb_sb.setValue(jcpds_phase.params['c0'] / float(jcpds_phase.params['b0']))
        except ZeroDivisionError:
            self.lattice_cb_sb.setSpecialValueText('Inf')

        self.lattice_volume_txt.setText(str('{0:g}'.format(jcpds_phase.params['v0'])))

        if not self.lattice_alpha_sb.hasFocus():
            self.lattice_alpha_sb.setValue(jcpds_phase.params['alpha0'])
        if not self.lattice_beta_sb.hasFocus():
            self.lattice_beta_sb.setValue(jcpds_phase.params['beta0'])
        if not self.lattice_gamma_sb.hasFocus():
            self.lattice_gamma_sb.setValue(jcpds_phase.params['gamma0'])

        self.blockAllSignals(False)

    def blockAllSignals(self, bool=True):
        self.lattice_a_sb.blockSignals(bool)
        self.lattice_b_sb.blockSignals(bool)
        self.lattice_c_sb.blockSignals(bool)

        self.lattice_alpha_sb.blockSignals(bool)
        self.lattice_beta_sb.blockSignals(bool)
        self.lattice_gamma_sb.blockSignals(bool)

        self.lattice_ab_sb.blockSignals(bool)
        self.lattice_ca_sb.blockSignals(bool)
        self.lattice_cb_sb.blockSignals(bool)

        self.symmetry_cb.blockSignals(bool)

    def update_spinbox_enable(self, symmetry):
        if symmetry == 'CUBIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(False)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(False)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'TETRAGONAL':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'ORTHORHOMBIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(True)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(True)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(True)

        elif symmetry == 'HEXAGONAL' or symmetry == 'TRIGONAL':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'RHOMBOHEDRAL':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(False)

            self.lattice_alpha_sb.setEnabled(True)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(False)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'MONOCLINIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(True)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(True)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(True)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(True)

        elif symmetry == 'TRICLINIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(True)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(True)
            self.lattice_beta_sb.setEnabled(True)
            self.lattice_gamma_sb.setEnabled(True)

            self.lattice_ab_sb.setEnabled(True)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(True)

        else:
            print('Unknown symmetry: {0}.'.format(symmetry))

    def get_selected_reflections(self):
        selected = self.reflection_table_view.selectionModel().selectedRows()
        try:
            row = []
            for element in selected:
                row.append(int(element.row()))
        except IndexError:
            row = None
        return row


class NoRectDelegate(QtWidgets.QItemDelegate):
    def drawFocus(self, painter, option, rect):
        option.state &= ~QtWidgets.QStyle.State_HasFocus
        QtWidgets.QItemDelegate.drawFocus(self, painter, option, rect)


class TextDoubleDelegate(NoRectDelegate):
    def createEditor(self, parent, _, model):
        self.editor = QtWidgets.QLineEdit(parent)
        self.editor.setFrame(False)
        self.editor.setValidator(QtGui.QDoubleValidator())
        self.editor.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return self.editor


class ReflectionTableModel(QtCore.QAbstractTableModel):
    reflection_edited = QtCore.Signal(int, int, str)  # row, column, value

    def __init__(self, reflections=None, wavelength=None):
        super(ReflectionTableModel, self).__init__()
        self.wavelength = wavelength
        if reflections is not None:
            self.reflections = reflections
            self.update_reflection_data(reflections)
        else:
            self.reflections = []
        self.header_labels = ['h', 'k', 'l', 'Intensity', 'd0', 'd', u"2θ_0", u"2θ", 'Q0', 'Q']

    def rowCount(self, *_):
        return len(self.reflections)

    def columnCount(self, *_):
        return 10

    def data(self, index, role=QtCore.Qt.DisplayRole):
        col = index.column()
        if role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignCenter
        if role == QtCore.Qt.DisplayRole:
            if col < 4:
                format_str = '{0:g}'
            else:
                format_str = '{0:.4f}'
            return format_str.format(self.reflection_data[index.row(), index.column()])
        else:
            return QtCore.QVariant()

    def setData(self, index, value, role):
        self.reflection_edited.emit(index.row(), index.column(), value)
        return True

    def update_reflection_data(self, reflections, wavelength=None):
        if wavelength is None:
            wavelength = self.wavelength
        else:
            self.wavelength = wavelength

        cur_row_num = self.rowCount()
        row_diff = len(reflections) - cur_row_num
        if row_diff < 0:
            self.beginRemoveRows(QtCore.QModelIndex(), cur_row_num + row_diff, cur_row_num - 1)
        elif row_diff > 0:
            self.beginInsertRows(QtCore.QModelIndex(), cur_row_num, cur_row_num + row_diff - 1)

        self.reflections = reflections
        self.reflection_data = np.zeros((len(reflections), self.columnCount()))
        for i, refl in enumerate(reflections):
            self.reflection_data[i, 0] = refl.h
            self.reflection_data[i, 1] = refl.k
            self.reflection_data[i, 2] = refl.l
            self.reflection_data[i, 3] = refl.intensity
            self.reflection_data[i, 4] = refl.d0
            self.reflection_data[i, 5] = refl.d

        if wavelength is not None:
            self.reflection_data[:, 6] = convert_d_to_two_theta(self.reflection_data[:, 4], wavelength)  # two_theta0
            self.reflection_data[:, 7] = convert_d_to_two_theta(self.reflection_data[:, 5], wavelength)  # two_theta
            valid_ind = np.where(self.reflection_data[:, 4] > 0)
            self.reflection_data[valid_ind, 8] = 2.0 * np.pi / self.reflection_data[valid_ind, 4]  # q0
            self.reflection_data[valid_ind, 9] = 2.0 * np.pi / self.reflection_data[valid_ind, 5]  # q

        if row_diff < 0:
            self.endRemoveRows()
        elif row_diff > 0:
            self.endInsertRows()

        self.modelReset.emit()

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.header_labels[section]
        if orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return section + 1

    def flags(self, index):
        col = index.column()
        ans = QtCore.QAbstractTableModel.flags(self, index)
        if col <= 3:
            return QtCore.Qt.ItemIsEditable | ans
        else:
            return ans
