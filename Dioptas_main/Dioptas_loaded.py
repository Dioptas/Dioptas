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
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import absolute_import

__author__ = 'Clemens Prescher'

import sys

#setup the logger:
import logging
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)



def test_phases(controller):
    controller.calibration_controller.load_calibration(
        'ExampleData/LaB6_p49_001.poni')
    controller.calibration_controller.set_calibrant(7)
    controller.calibration_controller.load_img('ExampleData/LaB6_p49_001.tif')
    controller.view.tabWidget.setCurrentIndex(2)
    controller.view.integration_widget.tabWidget.setCurrentIndex(3)
    controller.integration_controller.phase_controller.add_phase('ExampleData/jcpds/dac_user/au_Anderson.jcpds')
    controller.integration_controller.phase_controller.add_phase('ExampleData/jcpds/dac_user/au_Jamieson.jcpds')
    controller.integration_controller.phase_controller.add_phase('ExampleData/jcpds/dac_user/ar.jcpds')
    controller.integration_controller.phase_controller.add_phase('ExampleData/jcpds/dac_user/fe-hcp.jcpds')


def test_calibration(controller):
    controller.calibration_controller.load_calibration(
        'ExampleData/LaB6_p49_001.poni')
    controller.calibration_controller.set_calibrant(7)
    controller.calibration_controller.load_img('ExampleData/LaB6_p49_001.tif')
    controller.calibration_controller.refine()


def test_integration(controller):
    controller.calibration_controller.load_calibration(
        'ExampleData/LaB6_p49_001.poni')
    # controller.view.tabWidget.setCurrentIndex(2)
    # controller.integration_controller.spectrum_controller.view.spec_q_btn.setChecked(True)
    # controller.integration_controller.spectrum_controller.set_unit_q()
    controller.calibration_controller.load_img('ExampleData/LaB6_p49_001.tif')
    # # get phase
    # controller.integration_controller.phase_controller.add_phase(
    # 'ExampleData/jcpds/dac_user/au_Anderson.jcpds')
    # QtGui.QApplication.processEvents()
    # controller.integration_controller.phase_controller.update_intensities()

def test_overlay_colors(controller):
    load_overlays(controller)
    controller.view.tabWidget.setCurrentIndex(2)
    controller.view.integration_widget.tabWidget.setCurrentIndex(2)
    controller.integration_controller.spectrum_controller.load('ExampleData/Spectra/FoG_D3_003.xy')

def load_overlays(controller):
    load_overlay(controller, 'FoG_D3_001.xy')

def load_overlay(controller, filename):
    controller.integration_controller.overlay_controller.add_overlay(
        'ExampleData/Spectra/' + filename)

if __name__ == "__main__":
    logger.info('')
    logger.info('STARTING A NEW INSTANCE OF DIOPTAS.')
    logger.info('')


    import os
    from PyQt4 import QtGui
    from Controller.MainController import MainController

    app = QtGui.QApplication(sys.argv)

    if os.name is not 'posix':
        app.setStyle('plastique')
        # possible values:
        # "windows", "motif", "cde", "plastique", "windowsxp", or "macintosh"

    controller = MainController(app)
    test_phases(controller)
    app.exec_()