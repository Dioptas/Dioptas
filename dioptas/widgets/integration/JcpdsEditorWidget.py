# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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

from PyQt4 import QtGui, QtCore

from widgets.CustomWidgets import NumberTextField, LabelAlignRight, DoubleSpinBoxAlignRight, HorizontalSpacerItem, \
    VerticalSpacerItem, FlatButton, CleanLooksComboBox

from model.util.HelperModule import convert_d_to_two_theta


class JcpdsEditorWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(JcpdsEditorWidget, self).__init__(parent)

        self._layout = QtGui.QVBoxLayout()

        self._file_layout = QtGui.QGridLayout()
        self._file_layout.addWidget(LabelAlignRight('Filename:'), 0, 0)
        self._file_layout.addWidget(LabelAlignRight('Comment:'), 1, 0)

        self.filename_txt = QtGui.QLineEdit('')
        self.comments_txt = QtGui.QLineEdit('')
        self._file_layout.addWidget(self.filename_txt, 0, 1)
        self._file_layout.addWidget(self.comments_txt, 1, 1)
        self._layout.addLayout((self._file_layout))

        self.lattice_parameters_gb = QtGui.QGroupBox('Lattice Parameters')
        self._lattice_parameters_layout = QtGui.QVBoxLayout()

        self._symmetry_layout = QtGui.QHBoxLayout()
        self._symmetry_layout.addWidget(LabelAlignRight('Symmetry'))
        self.symmetry_cb = CleanLooksComboBox()
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'rhombohedral',
                           'orthorhombic', 'monoclinic', 'triclinic']
        self.symmetry_cb.addItems(self.symmetries)
        self._symmetry_layout.addWidget(self.symmetry_cb)
        self._symmetry_layout.addSpacerItem(HorizontalSpacerItem())
        self._lattice_parameters_layout.addLayout(self._symmetry_layout)

        self._parameters_layout = QtGui.QGridLayout()

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

        self.add_field(self._parameters_layout, self.lattice_a_sb, 'a0:',u"Å", 0, 0)
        self.add_field(self._parameters_layout, self.lattice_b_sb, 'b0:',u"Å", 0, 3)
        self.add_field(self._parameters_layout, self.lattice_c_sb, 'c0:',u"Å", 0, 6)
        self.add_field(self._parameters_layout, self.lattice_length_step_txt, 'st:',u"Å", 0, 9)

        self.lattice_eos_a_txt = NumberTextField()
        self.lattice_eos_b_txt = NumberTextField()
        self.lattice_eos_c_txt = NumberTextField()

        self.add_field(self._parameters_layout, self.lattice_eos_a_txt, 'a:',u"Å", 1, 0)
        self.add_field(self._parameters_layout, self.lattice_eos_b_txt, 'b:',u"Å", 1, 3)
        self.add_field(self._parameters_layout, self.lattice_eos_c_txt, 'c:',u"Å", 1, 6)

        self.lattice_alpha_sb = DoubleSpinBoxAlignRight()
        self.lattice_alpha_sb.setMaximum(180)
        self.lattice_beta_sb = DoubleSpinBoxAlignRight()
        self.lattice_beta_sb.setMaximum(180)
        self.lattice_gamma_sb = DoubleSpinBoxAlignRight()
        self.lattice_gamma_sb.setMaximum(180)
        self.lattice_angle_step_txt = NumberTextField('1')

        self.add_field(self._parameters_layout, self.lattice_alpha_sb, u'α:',u"°", 2, 0)
        self.add_field(self._parameters_layout, self.lattice_beta_sb, u'β:',u"°", 2, 3)
        self.add_field(self._parameters_layout, self.lattice_gamma_sb, u'γ:',u"°", 2, 6)
        self.add_field(self._parameters_layout, self.lattice_angle_step_txt, u'st:',u"°", 2, 9)

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

        self.eos_gb = QtGui.QGroupBox('Equation of State')
        self._eos_layout = QtGui.QGridLayout()

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

        self.reflections_gb = QtGui.QGroupBox('Reflections')
        self._reflection_layout = QtGui.QGridLayout()
        self.reflection_table = QtGui.QTableWidget()
        self.reflection_table.setColumnCount(8)
        self.reflections_add_btn = FlatButton('Add')
        self.reflections_delete_btn = FlatButton('Delete')
        self.reflections_clear_btn = FlatButton('Clear')

        self._reflection_layout.addWidget(self.reflection_table, 0, 0, 1, 3)
        self._reflection_layout.addWidget(self.reflections_add_btn, 1, 0)
        self._reflection_layout.addWidget(self.reflections_delete_btn, 1, 1)
        self._reflection_layout.addWidget(self.reflections_clear_btn, 1, 2)

        self.reflections_gb.setLayout(self._reflection_layout)

        self._body_layout = QtGui.QGridLayout()
        self._body_layout.addWidget(self.eos_gb, 0, 0)
        self._body_layout.addItem(VerticalSpacerItem(), 1, 0)
        self._body_layout.addWidget(self.reflections_gb, 0, 1, 2, 1)


        self._button_layout = QtGui.QHBoxLayout()
        self.save_as_btn = FlatButton('Save As')
        self.reload_file_btn = FlatButton('Reload File')
        self.ok_btn = FlatButton('Ok')
        self.cancel_btn = FlatButton('Cancel')

        self._button_layout.addWidget(self.save_as_btn)
        self._button_layout.addWidget(self.reload_file_btn)
        self._button_layout.addSpacerItem(HorizontalSpacerItem())
        self._button_layout.addWidget(self.ok_btn)
        self._button_layout.addWidget(self.cancel_btn)

        self._layout.addWidget(self.lattice_parameters_gb)
        self._layout.addLayout(self._body_layout)
        self._layout.addLayout(self._button_layout)
        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.lattice_angle_step_txt.setMaximumWidth(60)
        self.lattice_length_step_txt.setMaximumWidth(60)
        self.lattice_ratio_step_txt.setMaximumWidth(60)

        self.reflection_table.setHorizontalHeaderLabels(
            ['h', 'k', 'l', 'Intensity', 'd0', u"2θ_0", 'd', u"2θ"]
        )
        self.reflection_table.setItemDelegate(TextDoubleDelegate(self))
        self.reflection_table.setShowGrid(False)
        self.reflection_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.reflection_table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.reflection_table.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)

        self.eos_gb.setMaximumWidth(200)
        self.eos_gb.setStyleSheet("""
            QLineEdit {
                max-width: 80;
            }
        """)

        reflections_horizontal_header_item = self.reflection_table.horizontalHeaderItem(1)
        reflections_horizontal_header_item.setSizeHint(QtCore.QSize(20, 24))

        self.reflection_table.verticalHeader().setDefaultSectionSize(20)
        # self.reflection_table.verticalHeader().setResizeMode(QtGui.QHeaderView.Fixed)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def add_field(self, layout, widget, label_str, unit, x, y):
        layout.addWidget(LabelAlignRight(label_str), x, y)
        layout.addWidget(widget, x, y+1)
        if unit:
            layout.addWidget(QtGui.QLabel(unit), x, y+2)

    def show_jcpds(self, jcpds_phase, wavelength=None):
        self.blockAllSignals(True)

        self.filename_txt.setText(jcpds_phase.filename)
        self.comments_txt.setText("/n".join(jcpds_phase.comments))

        self.symmetry_cb.setCurrentIndex(self.symmetries.index(jcpds_phase.symmetry.lower()))
        self.update_spinbox_enable(jcpds_phase.symmetry)

        if not self.lattice_a_sb.hasFocus():
            self.lattice_a_sb.setValue(jcpds_phase.a0)
        if not self.lattice_b_sb.hasFocus():
            self.lattice_b_sb.setValue(jcpds_phase.b0)
        if not self.lattice_c_sb.hasFocus():
            self.lattice_c_sb.setValue(jcpds_phase.c0)

        self.lattice_eos_a_txt.setText('{0:.4f}'.format(jcpds_phase.a))
        self.lattice_eos_b_txt.setText('{0:.4f}'.format(jcpds_phase.b))
        self.lattice_eos_c_txt.setText('{0:.4f}'.format(jcpds_phase.c))

        self.lattice_eos_volume_txt.setText('{0:.4f}'.format(jcpds_phase.v))

        try:
            if not self.lattice_ab_sb.hasFocus():
                self.lattice_ab_sb.setValue(jcpds_phase.a0 / float(jcpds_phase.b0))
        except ZeroDivisionError:
            self.lattice_ab_sb.setSpecialValueText('Inf')

        try:
            if not self.lattice_ca_sb.hasFocus():
                self.lattice_ca_sb.setValue(jcpds_phase.c0 / float(jcpds_phase.a0))
        except ZeroDivisionError:
            self.lattice_ca_sb.setSpecialValueText('Inf')

        try:
            if not self.lattice_cb_sb.hasFocus():
                self.lattice_cb_sb.setValue(jcpds_phase.c0 / float(jcpds_phase.b0))
        except ZeroDivisionError:
            self.lattice_cb_sb.setSpecialValueText('Inf')

        self.lattice_volume_txt.setText(str('{0:g}'.format(jcpds_phase.v0)))

        if not self.lattice_alpha_sb.hasFocus():
            self.lattice_alpha_sb.setValue(jcpds_phase.alpha0)
        if not self.lattice_beta_sb.hasFocus():
            self.lattice_beta_sb.setValue(jcpds_phase.beta0)
        if not self.lattice_gamma_sb.hasFocus():
            self.lattice_gamma_sb.setValue(jcpds_phase.gamma0)

        self.eos_K_txt.setText(str(jcpds_phase.k0))
        self.eos_Kp_txt.setText(str(jcpds_phase.k0p))
        self.eos_alphaT_txt.setText(str(jcpds_phase.alpha_t0))
        self.eos_dalphadT_txt.setText(str(jcpds_phase.d_alpha_dt))
        self.eos_dKdT_txt.setText(str(jcpds_phase.dk0dt))
        self.eos_dKpdT_txt.setText(str(jcpds_phase.dk0pdt))

        # update reflections:
        self.reflection_table.clearContents()
        self.reflection_table.setRowCount(0)
        for reflection in jcpds_phase.reflections:
            if wavelength is None:
                self.add_reflection_to_table(reflection.h, reflection.k, reflection.l,
                                             reflection.intensity, reflection.d0, reflection.d)
            else:
                two_theta0 = convert_d_to_two_theta(reflection.d0, wavelength)
                two_theta = convert_d_to_two_theta(reflection.d, wavelength)
                self.add_reflection_to_table(reflection.h, reflection.k, reflection.l,
                                             reflection.intensity, reflection.d0, reflection.d,
                                             two_theta0, two_theta)
        if wavelength is None:
            self.reflection_table.setColumnCount(6)
        else:
            self.reflection_table.setColumnCount(8)

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

        elif symmetry == 'HEXAGONAL':
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
        selected = self.reflection_table.selectionModel().selectedRows()
        try:
            row = []
            for element in selected:
                row.append(int(element.row()))
        except IndexError:
            row = None
        return row

    def add_reflection_to_table(self, h=0., k=0., l=0., intensity=0., d0=0., d=0., two_theta_0=None,
                                two_theta=None):
        self.reflection_table.blockSignals(True)
        new_row_ind = int(self.reflection_table.rowCount())
        self.reflection_table.setRowCount(new_row_ind + 1)

        self.reflection_table.setItem(new_row_ind, 0, CenteredQTableWidgetItem(str('{0:g}'.format(h))))
        self.reflection_table.setItem(new_row_ind, 1, CenteredQTableWidgetItem(str('{0:g}'.format(k))))
        self.reflection_table.setItem(new_row_ind, 2, CenteredQTableWidgetItem(str('{0:g}'.format(l))))
        self.reflection_table.setItem(new_row_ind, 3, CenteredQTableWidgetItem(str('{0:g}'.format(intensity))))
        if two_theta is None or two_theta_0 is None:
            self.reflection_table.setItem(new_row_ind, 4,
                                          CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d0))))
            self.reflection_table.setItem(new_row_ind, 5, CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d))))
        else:
            self.reflection_table.setItem(new_row_ind, 4,
                                          CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d0))))
            self.reflection_table.setItem(new_row_ind, 5,
                                          CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(two_theta_0))))
            self.reflection_table.setItem(new_row_ind, 6, CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d))))
            self.reflection_table.setItem(new_row_ind, 7,
                                          CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(two_theta))))

        self.reflection_table.resizeColumnsToContents()
        self.reflection_table.verticalHeader().setResizeMode(QtGui.QHeaderView.Fixed)
        self.reflection_table.blockSignals(False)

    def remove_reflection_from_table(self, ind):
        self.reflection_table.blockSignals(True)
        self.reflection_table.removeRow(ind)
        self.reflection_table.blockSignals(False)


        # def get_jcpds(self):
        # self.jcpds_phase.filename = str(self.filename_txt.text())
        #     self.jcpds_phase.comments_txt = [str(self.comments_text())]
        #
        #     self.jcpds_phase.symmetry = str(self.symmetry_cb.text()).upper()
        #
        #     self.jcpds_phase.a0 = float(str(self.lattice_a_txt.text()))
        #     self.jcpds_phase.b0 = float(str(self.lattice_b_txt.text()))
        #     self.jcpds_phase.c0 = float(str(self.lattice_c_txt.text()))
        #
        #     self.jcpds_phase.alpha0 = float(str(self.lattice_alpha_txt.text()))
        #     self.jcpds_phase.beta0 = float(str(self.lattice_beta_txt.text()))
        #     self.jcpds_phase.gamma0 = float(str(self.lattice_gamma_txt.text()))
        #
        #     self.jcpds_phase.k0 = float(str(self.eos_K_txt.text()))
        #     self.jcpds_phase.k0p = float(str(self.eos_Kp_txt.text()))
        #     self.jcpds_phase.alpha_t0 = float(str(self.eos_alphaT_txt.text()))
        #     self.jcpds_phase.d_alpha_dt = float(str(self.eos_dalphadT_txt.text()))
        #     self.jcpds_phase.dk0dt = float(str(self.eos_dKdT_txt.text()))
        #     self.jcpds_phase.dk0pdt = float(str(self.eos_dKpdT_txt.text()))


class NoRectDelegate(QtGui.QItemDelegate):
    def __init__(self, parent):
        super(NoRectDelegate, self).__init__(parent)

    def drawFocus(self, painter, option, rect):
        option.state &= ~QtGui.QStyle.State_HasFocus
        QtGui.QItemDelegate.drawFocus(self, painter, option, rect)


class TextDoubleDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent):
        super(TextDoubleDelegate, self).__init__(parent)

    def createEditor(self, parent, _, model):
        self.editor = QtGui.QLineEdit(parent)
        self.editor.setFrame(False)
        self.editor.setValidator(QtGui.QDoubleValidator())
        self.editor.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return self.editor

    def setEditorData(self, parent, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        if value.toString() != '':
            self.editor.setText("{0:g}".format(float(str(value.toString()))))

    def setModelData(self, parent, model, index):
        value = self.editor.text()
        model.setData(index, value, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, _):
        editor.setGeometry(option.rect)


class CenteredQTableWidgetItem(QtGui.QTableWidgetItem):
    def __init__(self, value):
        super(CenteredQTableWidgetItem, self).__init__(value)
        self.setTextAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

    def __gt__(self, other):
        return float(str(self.text()) > float(str(other.text())))

    def __lt__(self, other):
        return float(str(self.text())) < float(str(other.text()))

    def __ge__(self, other):
        return float(str(self.text()) >= float(str(other.text())))

    def __le__(self, other):
        return float(str(self.text())) <= float(str(other.text()))

    def __eq__(self, other):
        return float(str(self.text())) == float(str(other.text()))

    def __ne__(self, other):
        return float(str(self.text())) != float(str(other.text()))


class CenteredNonEditableQTableWidgetItem(CenteredQTableWidgetItem):
    def __init__(self, value):
        super(CenteredNonEditableQTableWidgetItem, self).__init__(value)
        self.setFlags(self.flags() & ~QtCore.Qt.ItemIsEditable)


if __name__ == '__main__':
    app = QtGui.QApplication([])
    from model.util.jcpds import jcpds
    import os
    test_phase = jcpds()
    path = os.path.join(os.path.dirname(__file__), '../../')
    path = os.path.join(path, 'tests', 'data', 'jcpds', 'ag.jcpds')
    print(os.path.abspath(path))
    test_phase.load_file(path)
    widget = JcpdsEditorWidget(None)
    widget.show_jcpds(test_phase, 0.31)
    widget.show()
    widget.raise_()
    app.exec_()

