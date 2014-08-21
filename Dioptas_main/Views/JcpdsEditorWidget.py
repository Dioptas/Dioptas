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
    def __init__(self, jcpds_phase=None, parent = None):
        super(JcpdsEditorWidget, self).__init__(parent)
        self.setupUi(self)
        self.setup_ui()
        self.set_validators()
        self.show_jcpds(jcpds_phase)
        self.jcpds_phase=jcpds_phase

    def setup_ui(self):
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'rhombohedral',
                           'orthorhombic',  'monoclinc', 'triclinic']
        self.symmetry_cb.clear()
        self.symmetry_cb.addItems(self.symmetries)

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
        self.eos_dKdT_txt.setValidator(QtGui.QDoubleValidator())

    def show_jcpds(self, jcpds_phase=None):
        self.filename_txt.setText(jcpds_phase.filename)
        self.comments_txt.setText(jcpds_phase.comments[0])

        self.symmetry_cb.setCurrentIndex(self.symmetries.index(jcpds_phase.symmetry.lower()))

        self.lattice_a_txt.setText(str(jcpds_phase.a))
        self.lattice_b_txt.setText(str(jcpds_phase.b))
        self.lattice_c_txt.setText(str(jcpds_phase.c))

        self.lattice_volume_txt.setText(str(jcpds_phase.v))

        self.lattice_alpha_txt.setText(str(jcpds_phase.alpha))
        self.lattice_beta_txt.setText(str(jcpds_phase.beta))
        self.lattice_gamma_txt.setText(str(jcpds_phase.gamma))

        self.eos_K_txt.setText(str(jcpds_phase.k0))
        self.eos_Kp_txt.setText(str(jcpds_phase.k0p))
        self.eos_alphaT_txt.setText(str(jcpds_phase.alpha_t0))
        self.eos_dalphadT_txt.setText(str(jcpds_phase.d_alpha_dt))
        self.eos_dKdT_txt.setText(str(jcpds_phase.dk0dt))
        self.eos_dKpdT_txt.setText(str(jcpds_phase.dk0pdt))

    def get_jcpds(self):
        self.jcpds_phase.filename = str(self.filename_txt.text())
        self.jcpds_phase.comments_txt = [str(self.comments_text())]

        self.jcpds_phase.symmetry = str(self.symmetry_cb.text()).upper()

        self.jcpds_phase.a0 = float(str(self.lattice_a_txt.text()))
        self.jcpds_phase.b0 = float(str(self.lattice_b_txt.text()))
        self.jcpds_phase.c0 = float(str(self.lattice_c_txt.text()))

        self.jcpds_phase.alpha0 = float(str(self.lattice_alpha_txt.text()))
        self.jcpds_phase.beta0 = float(str(self.lattice_beta_txt.text()))
        self.jcpds_phase.gamma0 = float(str(self.lattice_gamma_txt.text()))

        self.jcpds_phase.k0 = float(str(self.eos_K_txt.text()))
        self.jcpds_phase.k0p = float(str(self.eos_Kp_txt.text()))
        self.jcpds_phase.alpha_t0 = float(str(self.eos_alphaT_txt.text()))
        self.jcpds_phase.d_alpha_dt = float(str(self.eos_dalphadT_txt.text()))
        self.jcpds_phase.dk0dt = float(str(self.eos_dKdT_txt.text()))
        self.jcpds_phase.dk0pdt = float(str(self.eos_dKpdT_txt.text()))





