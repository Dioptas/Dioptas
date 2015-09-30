# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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

__author__ = 'Clemens Prescher'

from PyQt4 import QtCore, QtGui

from .UiFiles.JcpdsUI import Ui_JcpdsEditorWidget
from model.util.HelperModule import convert_d_to_two_theta


class JcpdsEditorWidget(QtGui.QWidget, Ui_JcpdsEditorWidget):
    def __init__(self, parent=None):
        super(JcpdsEditorWidget, self).__init__(parent)
        self.setupUi(self)
        self.setup_ui()
        self.set_validators()

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def setup_ui(self):
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'rhombohedral',
                           'orthorhombic', 'monoclinic', 'triclinic']
        self.symmetry_cb.clear()
        self.symmetry_cb.addItems(self.symmetries)
        self.reflection_table.setItemDelegate(TextDoubleDelegate(self))
        cleanlooks = QtGui.QStyleFactory.create('cleanlooks')
        self.symmetry_cb.setStyle(cleanlooks)

        reflections_horizontal_header_item = self.reflection_table.horizontalHeaderItem(1)
        reflections_horizontal_header_item.setSizeHint(QtCore.QSize(20, 24))

        self.reflection_table.verticalHeader().setDefaultSectionSize(20)
        self.reflection_table.verticalHeader().setResizeMode(QtGui.QHeaderView.Fixed)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def set_validators(self):
        self.lattice_length_step_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_angle_step_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_ratio_step_txt.setValidator(QtGui.QDoubleValidator())

        self.eos_K_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_Kp_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_alphaT_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_dalphadT_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_dKdT_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_dKpdT_txt.setValidator(QtGui.QDoubleValidator())

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
            self.reflection_table.setItem(new_row_ind, 4, CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d0))))
            self.reflection_table.setItem(new_row_ind, 5, CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d))))
        else:
            self.reflection_table.setItem(new_row_ind, 4, CenteredNonEditableQTableWidgetItem(str('{0:.4f}'.format(d0))))
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

