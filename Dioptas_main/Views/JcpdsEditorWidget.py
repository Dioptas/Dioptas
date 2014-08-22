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

from PyQt4 import QtCore, QtGui
from .UiFiles.JcpdsUI import Ui_JcpdsEditorWidget


class JcpdsEditorWidget(QtGui.QWidget, Ui_JcpdsEditorWidget):

    def __init__(self, parent = None):
        super(JcpdsEditorWidget, self).__init__(parent)
        self.setupUi(self)
        self.setup_ui()
        self.set_validators()

    def setup_ui(self):
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'rhombohedral',
                           'orthorhombic',  'monoclinc', 'triclinic']
        self.symmetry_cb.clear()
        self.symmetry_cb.addItems(self.symmetries)
        self.reflection_table.setItemDelegate(TextDoubleDelegate(self))

    def set_validators(self):
        self.lattice_a_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_b_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_c_txt.setValidator(QtGui.QDoubleValidator())

        self.lattice_alpha_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_beta_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_gamma_txt.setValidator(QtGui.QDoubleValidator())

        self.lattice_volume_txt.setValidator(QtGui.QDoubleValidator())

        self.lattice_ab_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_ca_txt.setValidator(QtGui.QDoubleValidator())
        self.lattice_cb_txt.setValidator(QtGui.QDoubleValidator())

        self.eos_K_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_Kp_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_alphaT_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_dalphadT_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_dKdT_txt.setValidator(QtGui.QDoubleValidator())
        self.eos_dKpdT_txt.setValidator(QtGui.QDoubleValidator())

    def show_jcpds(self, jcpds_phase=None):
        self.filename_txt.setText(jcpds_phase.filename)
        self.comments_txt.setText(jcpds_phase.comments[0])

        self.symmetry_cb.setCurrentIndex(self.symmetries.index(jcpds_phase.symmetry.lower()))
        self.update_txt_enable(jcpds_phase.symmetry)

        self.lattice_a_txt.setText(str(jcpds_phase.a0))
        self.lattice_b_txt.setText(str(jcpds_phase.b0))
        self.lattice_c_txt.setText(str(jcpds_phase.c0))

        self.lattice_ab_txt.setText(str(jcpds_phase.a0/float(jcpds_phase.b0)))
        self.lattice_ca_txt.setText(str(jcpds_phase.c0/float(jcpds_phase.a0)))
        self.lattice_cb_txt.setText(str(jcpds_phase.c0/float(jcpds_phase.b0)))

        self.lattice_volume_txt.setText(str(jcpds_phase.v0))

        self.lattice_alpha_txt.setText(str(jcpds_phase.alpha0))
        self.lattice_beta_txt.setText(str(jcpds_phase.beta0))
        self.lattice_gamma_txt.setText(str(jcpds_phase.gamma0))

        self.eos_K_txt.setText(str(jcpds_phase.k0))
        self.eos_Kp_txt.setText(str(jcpds_phase.k0p))
        self.eos_alphaT_txt.setText(str(jcpds_phase.alpha_t0))
        self.eos_dalphadT_txt.setText(str(jcpds_phase.d_alpha_dt))
        self.eos_dKdT_txt.setText(str(jcpds_phase.dk0dt))
        self.eos_dKpdT_txt.setText(str(jcpds_phase.dk0pdt))

        #update reflections:
        self.reflection_table.clear()
        self.reflection_table.setRowCount(0)
        for reflection in jcpds_phase.reflections:
            self.add_reflection_to_table(reflection.h, reflection.k, reflection.l,
                                         reflection.intensity, reflection.d0)


    def update_txt_enable(self, symmetry):
        if symmetry == 'CUBIC':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(False)
            self.lattice_c_txt.setEnabled(False)

            self.lattice_alpha_txt.setEnabled(False)
            self.lattice_beta_txt.setEnabled(False)
            self.lattice_gamma_txt.setEnabled(False)

            self.lattice_ab_txt.setEnabled(False)
            self.lattice_ca_txt.setEnabled(False)
            self.lattice_cb_txt.setEnabled(False)

        elif symmetry == 'TETRAGONAL':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(False)
            self.lattice_c_txt.setEnabled(True)

            self.lattice_alpha_txt.setEnabled(False)
            self.lattice_beta_txt.setEnabled(False)
            self.lattice_gamma_txt.setEnabled(False)

            self.lattice_ab_txt.setEnabled(False)
            self.lattice_ca_txt.setEnabled(True)
            self.lattice_cb_txt.setEnabled(False)

        elif symmetry == 'ORTHORHOMBIC':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(True)
            self.lattice_c_txt.setEnabled(True)

            self.lattice_alpha_txt.setEnabled(False)
            self.lattice_beta_txt.setEnabled(False)
            self.lattice_gamma_txt.setEnabled(False)

            self.lattice_ab_txt.setEnabled(True)
            self.lattice_ca_txt.setEnabled(True)
            self.lattice_cb_txt.setEnabled(True)

        elif symmetry == 'HEXAGONAL':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(False)
            self.lattice_c_txt.setEnabled(True)

            self.lattice_alpha_txt.setEnabled(False)
            self.lattice_beta_txt.setEnabled(False)
            self.lattice_gamma_txt.setEnabled(False)

            self.lattice_ab_txt.setEnabled(False)
            self.lattice_ca_txt.setEnabled(True)
            self.lattice_cb_txt.setEnabled(False)

        elif symmetry == 'RHOMBOHEDRAL':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(False)
            self.lattice_c_txt.setEnabled(False)

            self.lattice_alpha_txt.setEnabled(True)
            self.lattice_beta_txt.setEnabled(False)
            self.lattice_gamma_txt.setEnabled(False)

            self.lattice_ab_txt.setEnabled(False)
            self.lattice_ca_txt.setEnabled(False)
            self.lattice_cb_txt.setEnabled(False)

        elif symmetry == 'MONOCLINC':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(True)
            self.lattice_c_txt.setEnabled(True)

            self.lattice_alpha_txt.setEnabled(False)
            self.lattice_beta_txt.setEnabled(True)
            self.lattice_gamma_txt.setEnabled(False)

            self.lattice_ab_txt.setEnabled(True)
            self.lattice_ca_txt.setEnabled(True)
            self.lattice_cb_txt.setEnabled(True)

        elif symmetry == 'TRICLINIC':
            self.lattice_a_txt.setEnabled(True)
            self.lattice_b_txt.setEnabled(True)
            self.lattice_c_txt.setEnabled(True)

            self.lattice_alpha_txt.setEnabled(True)
            self.lattice_beta_txt.setEnabled(True)
            self.lattice_gamma_txt.setEnabled(True)

            self.lattice_ab_txt.setEnabled(True)
            self.lattice_ca_txt.setEnabled(True)
            self.lattice_cb_txt.setEnabled(True)

        else:
            print('Unknown symmetry: {}.'.format(symmetry))

    def get_selected_reflections(self):
        selected = self.reflection_table.selectionModel().selectedRows()
        try:
            row = []
            for element in selected:
                row.append(int(element.row()))
        except IndexError:
            row = None
        return row

    def add_reflection_to_table(self, h=0., k=0., l=0., intensity=0., d=0.):
        self.reflection_table.blockSignals(True)
        new_row_ind = int(self.reflection_table.rowCount())
        self.reflection_table.setRowCount(new_row_ind+1)

        self.reflection_table.setItem(new_row_ind, 0, CenteredQTableWidgetItem(str(h)))
        self.reflection_table.setItem(new_row_ind, 1, CenteredQTableWidgetItem(str(k)))
        self.reflection_table.setItem(new_row_ind, 2, CenteredQTableWidgetItem(str(l)))
        self.reflection_table.setItem(new_row_ind, 3, CenteredQTableWidgetItem(str(intensity)))
        self.reflection_table.setItem(new_row_ind, 4, CenteredQTableWidgetItem(str(d)))

        self.reflection_table.resizeColumnsToContents()
        self.reflection_table.blockSignals(False)

    def remove_reflection_from_table(self, ind):
        self.reflection_table.blockSignals(True)
        self.reflection_table.removeRow(ind)
        self.reflection_table.blockSignals(False)



    # def get_jcpds(self):
    #     self.jcpds_phase.filename = str(self.filename_txt.text())
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
        self.editor.setText("{:g}".format(float(str(value.toString()))))

    def setModelData(self, parent, model, index):
        value = self.editor.text()
        model.setData(index, value, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, _):
        editor.setGeometry(option.rect)

class CenteredQTableWidgetItem(QtGui.QTableWidgetItem):
    def __init__(self, value):
        super(CenteredQTableWidgetItem, self).__init__(value)
        self.setTextAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
