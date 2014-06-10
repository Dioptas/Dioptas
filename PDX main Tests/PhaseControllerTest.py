# -*- coding: utf8 -*-
# Py2DeX - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
#
# This program is free software: you can redistribute it and/or modify
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

import unittest

from PySide import QtGui
from Data.ImgData import ImgData
from Controller.MainController import MainController

import sys


class phaseControllerTest(unittest.TestCase):
    def setUp(self):
        self.app = QtGui.QApplication(sys.argv)
        self.image_data = ImgData()
        self.controller = MainController()
        self.controller.calibration_controller.load_calibration(
            'Data/LaB6_p49_40keV_006.poni')
        self.controller.view.tabWidget.setCurrentIndex(2)
        self.controller.calibration_controller.load_img('Data/Mg2SiO4_ambient_001.tif')

        self.phase_controller = self.controller.integration_controller.phase_controller
        self.phase_data = self.controller.phase_data
        self.phase_view = self.controller.view.integration_widget
        self.phase_lw = self.phase_view.phase_lw

    def test_manual_deleting_phases(self):
        self.load_phases()
        QtGui.QApplication.processEvents()

        self.assertEqual(self.phase_lw.count(), 6)
        self.assertEqual(len(self.phase_data.phases), 6)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 6)
        self.assertEqual(self.phase_lw.currentRow(), 5)

        self.phase_controller.del_phase()
        self.assertEqual(self.phase_lw.count(), 5)
        self.assertEqual(len(self.phase_data.phases), 5)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 5)
        self.assertEqual(self.phase_lw.currentRow(), 4)

        self.phase_lw.setCurrentRow(1)
        self.phase_controller.del_phase()
        self.assertEqual(self.phase_lw.count(), 4)
        self.assertEqual(len(self.phase_data.phases), 4)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 4)
        self.assertEqual(self.phase_lw.currentRow(), 1)

        self.phase_lw.setCurrentRow(0)
        self.phase_controller.del_phase()
        self.assertEqual(self.phase_lw.count(), 3)
        self.assertEqual(len(self.phase_data.phases), 3)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 3)
        self.assertEqual(self.phase_lw.currentRow(), 0)

        self.phase_controller.del_phase()
        self.phase_controller.del_phase()
        self.phase_controller.del_phase()
        self.assertEqual(self.phase_lw.count(), 0)
        self.assertEqual(len(self.phase_data.phases), 0)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 0)
        self.assertEqual(self.phase_lw.currentRow(), -1)

        self.phase_controller.del_phase()
        self.assertEqual(self.phase_lw.count(), 0)
        self.assertEqual(len(self.phase_data.phases), 0)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 0)
        self.assertEqual(self.phase_lw.currentRow(), -1)

    def test_automatic_deleting_phases(self):
        self.load_phases()
        self.load_phases()
        self.assertEqual(self.phase_lw.count(), 12)
        self.assertEqual(len(self.phase_data.phases), 12)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 12)
        self.phase_controller.clear_phases()
        self.assertEqual(self.phase_lw.count(), 0)
        self.assertEqual(len(self.phase_data.phases), 0)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 0)
        self.assertEqual(self.phase_lw.currentRow(), -1)

        multiplier = 10
        for dummy_index in range(multiplier):
            self.load_phases()

        self.assertEqual(self.phase_lw.count(), multiplier * 6)
        self.phase_controller.clear_phases()
        self.assertEqual(self.phase_lw.count(), 0)
        self.assertEqual(len(self.phase_data.phases), 0)
        self.assertEqual(len(self.phase_view.spectrum_view.phases), 0)
        self.assertEqual(self.phase_lw.currentRow(), -1)

    def load_phases(self):
        self.load_phase('ar.jcpds')
        self.load_phase('ag.jcpds')
        self.load_phase('au_Anderson.jcpds')
        self.load_phase('mo.jcpds')
        self.load_phase('pt.jcpds')
        self.load_phase('re.jcpds')

    def load_phase(self, filename):
        self.controller.integration_controller.phase_controller.add_phase(
            'Data/jcpds/' + filename)

    def tearDown(self):
        QtGui.QApplication.processEvents()