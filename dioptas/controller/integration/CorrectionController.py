# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
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

import numpy as np
import time
from qtpy import QtWidgets

from ...model.util.ImgCorrection import CbnCorrection, ObliqueAngleDetectorAbsorptionCorrection

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel


class CorrectionController(object):
    """
    The CorrectionController manages the Correction controls in the integration window.
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to IntegrationWidget
        :param dioptas_model: Reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """

        self.widget = widget
        self.model = dioptas_model

        self.create_signals()

    def create_signals(self):
        self.widget.cbn_groupbox.clicked.connect(self.cbn_groupbox_changed)
        for row_ind in range(self.widget.cbn_param_tw.rowCount()):
            self.widget.cbn_param_tw.cellWidget(row_ind, 1).editingFinished.connect(self.cbn_groupbox_changed)
        self.widget.cbn_plot_correction_btn.clicked.connect(self.cbn_plot_correction_btn_clicked)

        self.widget.oiadac_groupbox.clicked.connect(self.oiadac_groupbox_changed)
        for row_ind in range(self.widget.oiadac_param_tw.rowCount()):
            self.widget.oiadac_param_tw.cellWidget(row_ind, 1).editingFinished.connect(self.oiadac_groupbox_changed)
        self.widget.oiadac_plot_btn.clicked.connect(self.oiadac_plot_btn_clicked)

        self.model.img_changed.connect(self.reset_plot_btns)
        self.model.cake_changed.connect(self.reset_plot_btns)

    def cbn_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.cbn_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(self.widget,
                                           'ERROR',
                                           'Please calibrate the geometry first or load an existent calibration file. ' + \
                                           'The cBN seat correction needs a calibrated geometry.')
            return

        if self.widget.cbn_groupbox.isChecked():
            diamond_thickness = self.widget.cbn_param_tw.cellWidget(0, 1).value()
            seat_thickness = self.widget.cbn_param_tw.cellWidget(1, 1).value()
            inner_seat_radius = self.widget.cbn_param_tw.cellWidget(2, 1).value()
            outer_seat_radius = self.widget.cbn_param_tw.cellWidget(3, 1).value()
            tilt = self.widget.cbn_param_tw.cellWidget(4, 1).value()
            tilt_rotation = self.widget.cbn_param_tw.cellWidget(5, 1).value()
            center_offset = self.widget.cbn_param_tw.cellWidget(6, 1).value()
            center_offset_angle = self.widget.cbn_param_tw.cellWidget(7, 1).value()
            seat_absorption_length = self.widget.cbn_param_tw.cellWidget(8, 1).value()
            anvil_absorption_length = self.widget.cbn_param_tw.cellWidget(9, 1).value()

            tth_array = 180.0 / np.pi * self.model.calibration_model.pattern_geometry.ttha
            azi_array = 180.0 / np.pi * self.model.calibration_model.pattern_geometry.chia

            new_cbn_correction = CbnCorrection(
                tth_array=tth_array,
                azi_array=azi_array,
                diamond_thickness=diamond_thickness,
                seat_thickness=seat_thickness,
                small_cbn_seat_radius=inner_seat_radius,
                large_cbn_seat_radius=outer_seat_radius,
                tilt=tilt,
                tilt_rotation=tilt_rotation,
                center_offset=center_offset,
                center_offset_angle=center_offset_angle,
                cbn_abs_length=seat_absorption_length,
                diamond_abs_length=anvil_absorption_length
            )
            if not new_cbn_correction == self.model.img_model.get_img_correction("cbn"):
                t1 = time.time()
                new_cbn_correction.update()
                print("Time needed for correction calculation: {0}".format(time.time() - t1))
                try:
                    self.model.img_model.delete_img_correction("cbn")
                except KeyError:
                    pass
                self.model.img_model.add_img_correction(new_cbn_correction, "cbn")
        else:
            self.model.img_model.delete_img_correction("cbn")

    def cbn_plot_correction_btn_clicked(self):
        if str(self.widget.cbn_plot_correction_btn.text()) == 'Plot':
            self.widget.img_widget.plot_image(self.model.img_model.img_corrections.get_correction("cbn").get_data(),
                                              True)
            self.widget.cbn_plot_correction_btn.setText('Back')
            self.widget.oiadac_plot_btn.setText('Plot')
        else:
            self.widget.cbn_plot_correction_btn.setText('Plot')
            if self.widget.img_mode == 'Cake':
                self.model.cake_changed.emit()
            elif self.widget.img_mode == 'Image':
                self.model.img_changed.emit()

    def update_cbn_widgets(self):
        params = self.model.img_model.img_corrections.get_correction("cbn").get_params()
        self.widget.cbn_param_tw.cellWidget(0, 1).setText(str(params['diamond_thickness']))
        self.widget.cbn_param_tw.cellWidget(1, 1).setText(str(params['seat_thickness']))
        self.widget.cbn_param_tw.cellWidget(2, 1).setText(str(params['small_cbn_seat_radius']))
        self.widget.cbn_param_tw.cellWidget(3, 1).setText(str(params['large_cbn_seat_radius']))
        self.widget.cbn_param_tw.cellWidget(4, 1).setText(str(params['tilt']))
        self.widget.cbn_param_tw.cellWidget(5, 1).setText(str(params['tilt_rotation']))
        self.widget.cbn_param_tw.cellWidget(6, 1).setText(str(params['diamond_abs_length']))
        self.widget.cbn_param_tw.cellWidget(7, 1).setText(str(params['seat_abs_length']))
        self.widget.cbn_param_tw.cellWidget(8, 1).setText(str(params['center_offset']))
        self.widget.cbn_param_tw.cellWidget(9, 1).setText(str(params['center_offset_angle']))
        self.widget.cbn_groupbox.setChecked(True)

    def oiadac_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.oiadac_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                'ERROR',
                'Please calibrate the geometry first or load an existent calibration file. ' +
                'The oblique incidence angle detector absorption correction needs a calibrated' +
                'geometry.'
            )
            return

        if self.widget.oiadac_groupbox.isChecked():
            detector_thickness = self.widget.oiadac_param_tw.cellWidget(0, 1).value()
            absorption_length = self.widget.oiadac_param_tw.cellWidget(1, 1).value()

            _, fit2d_parameter = self.model.calibration_model.get_calibration_parameter()
            detector_tilt = fit2d_parameter['tilt']
            detector_tilt_rotation = fit2d_parameter['tiltPlanRotation']

            tth_array = self.model.calibration_model.pattern_geometry.ttha
            azi_array = self.model.calibration_model.pattern_geometry.chia
            import time

            t1 = time.time()

            oiadac_correction = ObliqueAngleDetectorAbsorptionCorrection(
                tth_array, azi_array,
                detector_thickness=detector_thickness,
                absorption_length=absorption_length,
                tilt=detector_tilt,
                rotation=detector_tilt_rotation,
            )
            print("Time needed for correction calculation: {0}".format(time.time() - t1))
            try:
                self.model.img_model.delete_img_correction("oiadac")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(oiadac_correction, "oiadac")
        else:
            self.model.img_model.delete_img_correction("oiadac")

    def oiadac_plot_btn_clicked(self):
        if str(self.widget.oiadac_plot_btn.text()) == 'Plot':
            self.widget.img_widget.plot_image(self.model.img_model._img_corrections.get_correction("oiadac").get_data(),
                                              True)
            self.widget.oiadac_plot_btn.setText('Back')
            self.widget.cbn_plot_correction_btn.setText('Plot')
        else:
            self.widget.oiadac_plot_btn.setText('Plot')
            if self.widget.img_mode == 'Cake':
                self.model.cake_changed.emit()
            elif self.widget.img_mode == 'Image':
                self.model.img_changed.emit()

    def update_oiadac_widgets(self):
        params = self.model.img_model.img_corrections.get_correction("oiadac").get_params()
        self.widget.oiadac_param_tw.cellWidget(0, 1).setText(str(params['detector_thickness']))
        self.widget.oiadac_param_tw.cellWidget(1, 1).setText(str(params['absorption_length']))
        self.widget.oiadac_groupbox.setChecked(True)

    def reset_plot_btns(self):
        self.widget.oiadac_plot_btn.setText('Plot')
        self.widget.oiadac_plot_btn.setChecked(False)
        self.widget.cbn_plot_correction_btn.setText('Plot')
        self.widget.cbn_plot_correction_btn.setChecked(False)
