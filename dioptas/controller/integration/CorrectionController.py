# SPDX-License-Identifier: MIT

import logging
import numpy as np
import time
import os
from qtpy import QtWidgets

from ...model.util.ImgCorrection import (
    CbnCorrection,
    ObliqueAngleDetectorAbsorptionCorrection,
    SlabAbsorptionCorrection,
    CylinderAbsorptionCorrection,
    SphereAbsorptionCorrection,
    PlateAbsorptionCorrection,
)
from ...model.util.calc import calculate_mu, wavelength_to_energy

# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...widgets.UtilityWidgets import open_file_dialog
from ...model.DioptasModel import DioptasModel

logger = logging.getLogger(__name__)


class CorrectionController:
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
        # cbn correction
        self.widget.cbn_groupbox.clicked.connect(self.cbn_groupbox_changed)
        for row_ind in range(self.widget.cbn_param_tw.rowCount()):
            self.widget.cbn_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.cbn_groupbox_changed
            )
        self.widget.cbn_plot_btn.clicked.connect(self.cbn_plot_correction_btn_clicked)

        # oiadac correction
        self.widget.oiadac_groupbox.clicked.connect(self.oiadac_groupbox_changed)
        for row_ind in range(self.widget.oiadac_param_tw.rowCount()):
            self.widget.oiadac_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.oiadac_groupbox_changed
            )
        self.widget.oiadac_plot_btn.clicked.connect(self.oiadac_plot_btn_clicked)

        # slab correction
        self.widget.slab_groupbox.clicked.connect(self.slab_groupbox_changed)
        for row_ind in range(self.widget.slab_param_tw.rowCount()):
            self.widget.slab_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.slab_groupbox_changed
            )
        self.widget.slab_formula_txt.editingFinished.connect(self.slab_groupbox_changed)
        self.widget.slab_plot_btn.clicked.connect(self.slab_plot_btn_clicked)

        # cylinder correction
        self.widget.cylinder_groupbox.clicked.connect(self.cylinder_groupbox_changed)
        for row_ind in range(self.widget.cylinder_param_tw.rowCount()):
            self.widget.cylinder_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.cylinder_groupbox_changed
            )
        self.widget.cylinder_formula_txt.editingFinished.connect(self.cylinder_groupbox_changed)
        self.widget.cylinder_container_formula_txt.editingFinished.connect(self.cylinder_groupbox_changed)
        for row_ind in range(self.widget.cylinder_container_param_tw.rowCount()):
            self.widget.cylinder_container_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.cylinder_groupbox_changed
            )
        self.widget.cylinder_plot_btn.clicked.connect(self.cylinder_plot_btn_clicked)

        # sphere correction
        self.widget.sphere_groupbox.clicked.connect(self.sphere_groupbox_changed)
        for row_ind in range(self.widget.sphere_param_tw.rowCount()):
            self.widget.sphere_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.sphere_groupbox_changed
            )
        self.widget.sphere_formula_txt.editingFinished.connect(self.sphere_groupbox_changed)
        self.widget.sphere_plot_btn.clicked.connect(self.sphere_plot_btn_clicked)

        # plate correction
        self.widget.plate_groupbox.clicked.connect(self.plate_groupbox_changed)
        for row_ind in range(self.widget.plate_param_tw.rowCount()):
            self.widget.plate_param_tw.cellWidget(row_ind, 1).editingFinished.connect(
                self.plate_groupbox_changed
            )
        self.widget.plate_formula_txt.editingFinished.connect(self.plate_groupbox_changed)
        self.widget.plate_plot_btn.clicked.connect(self.plate_plot_btn_clicked)

        # flat field correction
        self.widget.flat_field_load_btn.clicked.connect(
            self.flat_field_load_btn_clicked
        )
        self.widget.flat_field_plot_btn.clicked.connect(self.flat_field_plot_btn_clicked)
        self.widget.flat_field_gb.toggled.connect(self.flat_field_gb_toggled)

        # transfer correction
        self.widget.transfer_load_original_btn.clicked.connect(
            self.transfer_load_original_btn_clicked
        )
        self.widget.transfer_load_response_btn.clicked.connect(
            self.transfer_load_response_btn_clicked
        )
        self.widget.transfer_plot_btn.clicked.connect(self.transfer_plot_btn_clicked)
        self.widget.transfer_gb.toggled.connect(self.transfer_gb_toggled)

        # general
        self.model.img_model.corrections_removed.connect(self.corrections_removed)

        # resetting plot buttons
        self.model.img_changed.connect(self.reset_plot_btns)
        self.model.cake_changed.connect(self.reset_plot_btns)

        # configurations
        self.model.configuration_selected.connect(self.update_gui)

    def transfer_load_original_btn_clicked(self):
        filename = open_file_dialog(
            self.widget,
            caption="Load Original Image File",
            directory=self.model.working_directories["image"],
        )
        if filename != "":
            self.widget.transfer_original_filename_lbl.setText(
                os.path.basename(filename)
            )
            self.model.img_model.transfer_correction.load_original_image(filename)
            self.model.img_model.enable_transfer_function()

    def transfer_load_response_btn_clicked(self):
        filename = open_file_dialog(
            self.widget,
            caption="Load Response Image File",
            directory=self.model.working_directories["image"],
        )
        if filename != "":
            self.widget.transfer_response_filename_lbl.setText(
                os.path.basename(filename)
            )
            self.model.img_model.transfer_correction.load_response_image(filename)
            self.model.img_model.enable_transfer_function()

    def transfer_plot_btn_clicked(self):
        if self.widget.transfer_plot_btn.isChecked():
            transfer_data = self.model.img_model.transfer_correction.get_data()
            if transfer_data is not None:
                self.widget.img_widget.plot_image(transfer_data, auto_level=True)
                self.widget.transfer_plot_btn.setText("Back")
            else:
                self.widget.transfer_plot_btn.setChecked(False)
        else:
            self.widget.transfer_plot_btn.setText("Plot")
            self.reset_img_widget()

    def update_transfer_widgets(self):
        original_filename = self.model.img_model.transfer_correction.original_filename
        response_filename = self.model.img_model.transfer_correction.response_filename
        if original_filename is not None:
            self.widget.transfer_original_filename_lbl.setText(
                os.path.basename(original_filename)
            )
        else:
            self.widget.transfer_original_filename_lbl.setText("None")
        if original_filename is not None:
            self.widget.transfer_response_filename_lbl.setText(
                os.path.basename(response_filename)
            )
        else:
            self.widget.transfer_response_filename_lbl.setText("None")

    def transfer_gb_toggled(self):
        if self.widget.transfer_gb.isChecked():
            self.model.img_model.enable_transfer_function()
        else:
            self.model.img_model.disable_transfer_function()

    def flat_field_load_btn_clicked(self):
        filename = open_file_dialog(
            self.widget,
            caption="Load Flat Field Image",
            directory=self.model.working_directories["image"],
        )
        if filename != "":
            self.widget.flat_field_filename_lbl.setText(
                os.path.basename(filename)
            )
            self.model.img_model.flat_field_correction.load(filename)
            self.widget.flat_field_gb.setChecked(True)
            self.model.img_model.enable_flat_field()

    def flat_field_plot_btn_clicked(self):
        if self.widget.flat_field_plot_btn.isChecked():
            flat_field_data = self.model.img_model.flat_field_correction.get_data()
            if flat_field_data is not None:
                self.widget.img_widget.plot_image(flat_field_data, auto_level=True)
                self.widget.flat_field_plot_btn.setText("Back")
            else:
                self.widget.flat_field_plot_btn.setChecked(False)
        else:
            self.widget.flat_field_plot_btn.setText("Plot")
            self.reset_img_widget()

    def flat_field_gb_toggled(self):
        if self.widget.flat_field_gb.isChecked():
            self.model.img_model.enable_flat_field()
        else:
            self.model.img_model.disable_flat_field()

    def update_flat_field_widgets(self):
        filename = self.model.img_model.flat_field_correction.filename
        if filename is not None:
            self.widget.flat_field_filename_lbl.setText(
                os.path.basename(filename)
            )
        else:
            self.widget.flat_field_filename_lbl.setText("None")

    def corrections_removed(self):
        self.widget.cbn_groupbox.setChecked(False)
        self.widget.oiadac_groupbox.setChecked(False)
        self.widget.transfer_gb.setChecked(False)
        self.widget.transfer_original_filename_lbl.setText("None")
        self.widget.transfer_response_filename_lbl.setText("None")
        self.widget.flat_field_gb.setChecked(False)
        self.widget.flat_field_filename_lbl.setText("None")
        self.widget.slab_groupbox.setChecked(False)
        self.widget.slab_mu_lbl.setText("μ:")
        self.widget.cylinder_groupbox.setChecked(False)
        self.widget.cylinder_mu_lbl.setText("μ:")
        self.widget.sphere_groupbox.setChecked(False)
        self.widget.sphere_mu_lbl.setText("μ:")
        self.widget.plate_groupbox.setChecked(False)
        self.widget.plate_mu_lbl.setText("μ:")
        QtWidgets.QMessageBox.critical(
            self.widget,
            "Shape Mismatch",
            "The loaded image and corrections have different shapes. "
            + "The corrections have been reset.",
        )

    def cbn_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.cbn_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                "ERROR",
                "Please calibrate the geometry first or load an existent calibration file. "
                + "The cBN seat correction needs a calibrated geometry.",
            )
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

            tth_array = (
                180.0 / np.pi * self.model.calibration_model.tth_array
            )
            azi_array = (
                180.0 / np.pi * self.model.calibration_model.azi_array
            )

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
                diamond_abs_length=anvil_absorption_length,
            )
            if not new_cbn_correction == self.model.img_model.get_img_correction("cbn"):
                t1 = time.time()
                new_cbn_correction.update()
                logger.info(
                    "Time needed for cBN correction calculation: %.3fs",
                    time.time() - t1,
                )
                try:
                    self.model.img_model.delete_img_correction("cbn")
                except KeyError:
                    pass
                self.model.img_model.add_img_correction(new_cbn_correction, "cbn")
        else:
            self.model.img_model.delete_img_correction("cbn")

    def cbn_plot_correction_btn_clicked(self):
        if str(self.widget.cbn_plot_btn.text()) == "Plot":
            self.widget.img_widget.plot_image(
                self.model.img_model.img_corrections.get_correction("cbn").get_data(),
                True,
            )
            self.widget.cbn_plot_btn.setText("Back")
            self.widget.oiadac_plot_btn.setText("Plot")
            self.widget.slab_plot_btn.setText("Plot")
            self.widget.cylinder_plot_btn.setText("Plot")
            self.widget.sphere_plot_btn.setText("Plot")
            self.widget.plate_plot_btn.setText("Plot")
            self.widget.flat_field_plot_btn.setText("Plot")
        else:
            self.widget.cbn_plot_btn.setText("Plot")
            self.reset_img_widget()

    def update_cbn_widgets(self):
        params = self.model.img_model.img_corrections.get_correction("cbn").get_params()
        self.widget.cbn_param_tw.cellWidget(0, 1).setText(
            str(params["diamond_thickness"])
        )
        self.widget.cbn_param_tw.cellWidget(1, 1).setText(str(params["seat_thickness"]))
        self.widget.cbn_param_tw.cellWidget(2, 1).setText(
            str(params["small_cbn_seat_radius"])
        )
        self.widget.cbn_param_tw.cellWidget(3, 1).setText(
            str(params["large_cbn_seat_radius"])
        )
        self.widget.cbn_param_tw.cellWidget(4, 1).setText(str(params["tilt"]))
        self.widget.cbn_param_tw.cellWidget(5, 1).setText(str(params["tilt_rotation"]))
        self.widget.cbn_param_tw.cellWidget(6, 1).setText(
            str(params["diamond_abs_length"])
        )
        self.widget.cbn_param_tw.cellWidget(7, 1).setText(
            str(params["seat_abs_length"])
        )
        self.widget.cbn_param_tw.cellWidget(8, 1).setText(str(params["center_offset"]))
        self.widget.cbn_param_tw.cellWidget(9, 1).setText(
            str(params["center_offset_angle"])
        )
        self.widget.cbn_groupbox.setChecked(True)

    def oiadac_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.oiadac_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                "ERROR",
                "Please calibrate the geometry first or load an existent calibration file. "
                + "The oblique incidence angle detector absorption correction needs a calibrated"
                + "geometry.",
            )
            return

        if self.widget.oiadac_groupbox.isChecked():
            detector_thickness = self.widget.oiadac_param_tw.cellWidget(0, 1).value()
            absorption_length = self.widget.oiadac_param_tw.cellWidget(1, 1).value()

            _, fit2d_parameter = (
                self.model.calibration_model.get_calibration_parameter()
            )
            detector_tilt = fit2d_parameter["tilt"]
            detector_tilt_rotation = fit2d_parameter["tiltPlanRotation"]

            tth_array = self.model.calibration_model.tth_array
            azi_array = self.model.calibration_model.azi_array
            import time

            t1 = time.time()

            oiadac_correction = ObliqueAngleDetectorAbsorptionCorrection(
                tth_array,
                azi_array,
                detector_thickness=detector_thickness,
                absorption_length=absorption_length,
                tilt=detector_tilt,
                rotation=detector_tilt_rotation,
            )
            logger.info(
                "Time needed for OIADAC correction calculation: %.3fs",
                time.time() - t1,
            )
            try:
                self.model.img_model.delete_img_correction("oiadac")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(oiadac_correction, "oiadac")
        else:
            self.model.img_model.delete_img_correction("oiadac")

    def oiadac_plot_btn_clicked(self):
        if str(self.widget.oiadac_plot_btn.text()) == "Plot":
            self.widget.img_widget.plot_image(
                self.model.img_model._img_corrections.get_correction(
                    "oiadac"
                ).get_data(),
                True,
            )
            self.widget.oiadac_plot_btn.setText("Back")
            self.widget.cbn_plot_btn.setText("Plot")
            self.widget.slab_plot_btn.setText("Plot")
            self.widget.cylinder_plot_btn.setText("Plot")
            self.widget.sphere_plot_btn.setText("Plot")
            self.widget.plate_plot_btn.setText("Plot")
            self.widget.flat_field_plot_btn.setText("Plot")
        else:
            self.widget.oiadac_plot_btn.setText("Plot")
            self.reset_img_widget()

    def reset_img_widget(self):
        if self.widget.img_mode == "Cake":
            self.model.cake_changed.emit()
        elif self.widget.img_mode == "Image":
            self.model.img_changed.emit()

    def update_slab_widgets(self):
        correction = self.model.img_model.img_corrections.get_correction("slab")
        if correction is None:
            return
        params = correction.get_params()
        self.widget.slab_param_tw.cellWidget(1, 1).setText(str(params["thickness"]))
        self.widget.slab_param_tw.cellWidget(2, 1).setText(str(params["slab_tilt"]))
        self.widget.slab_param_tw.cellWidget(3, 1).setText(str(params["slab_rotation"]))
        mu = params["absorption_coefficient"]
        self.widget.slab_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")
        self.widget.slab_groupbox.setChecked(True)

    def update_oiadac_widgets(self):
        params = self.model.img_model.img_corrections.get_correction(
            "oiadac"
        ).get_params()
        self.widget.oiadac_param_tw.cellWidget(0, 1).setText(
            str(params["detector_thickness"])
        )
        self.widget.oiadac_param_tw.cellWidget(1, 1).setText(
            str(params["absorption_length"])
        )
        self.widget.oiadac_groupbox.setChecked(True)

    def slab_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.slab_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                "ERROR",
                "Please calibrate the geometry first or load an existent calibration file. "
                + "The slab absorption correction needs a calibrated geometry.",
            )
            return

        if self.widget.slab_groupbox.isChecked():
            formula = self.widget.slab_formula_txt.text().strip()
            if not formula:
                self.widget.slab_groupbox.setChecked(False)
                return

            density = self.widget.slab_param_tw.cellWidget(0, 1).value()
            thickness = self.widget.slab_param_tw.cellWidget(1, 1).value()
            slab_tilt = self.widget.slab_param_tw.cellWidget(2, 1).value()
            slab_rotation = self.widget.slab_param_tw.cellWidget(3, 1).value()

            # Calculate mu from formula + density + wavelength
            wavelength_m = self.model.calibration_model.wavelength
            energy_eV = wavelength_to_energy(wavelength_m)
            try:
                mu = calculate_mu(formula, energy_eV, density=density if density > 0 else None)
            except Exception as e:
                self.widget.slab_groupbox.setChecked(False)
                self.widget.slab_mu_lbl.setText("μ:")
                QtWidgets.QMessageBox.critical(
                    self.widget,
                    "Invalid Formula",
                    f"Could not calculate absorption coefficient:\n{e}",
                )
                return

            self.widget.slab_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")

            tth_array = 180.0 / np.pi * self.model.calibration_model.tth_array
            azi_array = 180.0 / np.pi * self.model.calibration_model.azi_array

            new_correction = SlabAbsorptionCorrection(
                tth_array=tth_array,
                azi_array=azi_array,
                thickness=thickness,
                absorption_coefficient=mu,
                slab_tilt=slab_tilt,
                slab_rotation=slab_rotation,
            )
            new_correction.update()
            try:
                self.model.img_model.delete_img_correction("slab")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(new_correction, "slab")
        else:
            try:
                self.model.img_model.delete_img_correction("slab")
            except KeyError:
                pass
            self.widget.slab_mu_lbl.setText("μ:")

    def slab_plot_btn_clicked(self):
        if str(self.widget.slab_plot_btn.text()) == "Plot":
            correction = self.model.img_model.img_corrections.get_correction("slab")
            if correction is not None:
                self.widget.img_widget.plot_image(correction.get_data(), True)
                self.widget.slab_plot_btn.setText("Back")
                self.widget.cbn_plot_btn.setText("Plot")
                self.widget.oiadac_plot_btn.setText("Plot")
                self.widget.cylinder_plot_btn.setText("Plot")
                self.widget.sphere_plot_btn.setText("Plot")
                self.widget.plate_plot_btn.setText("Plot")
                self.widget.flat_field_plot_btn.setText("Plot")
            else:
                self.widget.slab_plot_btn.setChecked(False)
        else:
            self.widget.slab_plot_btn.setText("Plot")
            self.reset_img_widget()

    def cylinder_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.cylinder_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                "ERROR",
                "Please calibrate the geometry first or load an existent calibration file. "
                + "The cylinder absorption correction needs a calibrated geometry.",
            )
            return

        if self.widget.cylinder_groupbox.isChecked():
            formula = self.widget.cylinder_formula_txt.text().strip()
            if not formula:
                self.widget.cylinder_groupbox.setChecked(False)
                return

            density = self.widget.cylinder_param_tw.cellWidget(0, 1).value()
            radius = self.widget.cylinder_param_tw.cellWidget(1, 1).value()
            axis_tilt = self.widget.cylinder_param_tw.cellWidget(2, 1).value()
            axis_rotation = self.widget.cylinder_param_tw.cellWidget(3, 1).value()
            beam_width = self.widget.cylinder_param_tw.cellWidget(4, 1).value()

            wavelength_m = self.model.calibration_model.wavelength
            energy_eV = wavelength_to_energy(wavelength_m)
            try:
                mu = calculate_mu(formula, energy_eV, density=density if density > 0 else None)
            except Exception as e:
                self.widget.cylinder_groupbox.setChecked(False)
                self.widget.cylinder_mu_lbl.setText("μ:")
                QtWidgets.QMessageBox.critical(
                    self.widget, "Invalid Formula",
                    f"Could not calculate absorption coefficient:\n{e}",
                )
                return

            # Container parameters
            container_formula = self.widget.cylinder_container_formula_txt.text().strip()
            mu_container = 0
            wall_thickness = self.widget.cylinder_container_param_tw.cellWidget(1, 1).value()
            if container_formula and wall_thickness > 0:
                container_density = self.widget.cylinder_container_param_tw.cellWidget(0, 1).value()
                try:
                    mu_container = calculate_mu(
                        container_formula, energy_eV,
                        density=container_density if container_density > 0 else None,
                    )
                except Exception:
                    mu_container = 0

            self.widget.cylinder_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")

            tth_array = 180.0 / np.pi * self.model.calibration_model.tth_array
            azi_array = 180.0 / np.pi * self.model.calibration_model.azi_array

            new_correction = CylinderAbsorptionCorrection(
                tth_array=tth_array,
                azi_array=azi_array,
                radius=radius,
                absorption_coefficient=mu,
                axis_tilt=axis_tilt,
                axis_rotation=axis_rotation,
                beam_width=beam_width,
                container_absorption_coefficient=mu_container,
                wall_thickness=wall_thickness,
            )
            new_correction.update()
            try:
                self.model.img_model.delete_img_correction("cylinder")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(new_correction, "cylinder")
        else:
            try:
                self.model.img_model.delete_img_correction("cylinder")
            except KeyError:
                pass
            self.widget.cylinder_mu_lbl.setText("μ:")

    def cylinder_plot_btn_clicked(self):
        if str(self.widget.cylinder_plot_btn.text()) == "Plot":
            correction = self.model.img_model.img_corrections.get_correction("cylinder")
            if correction is not None:
                self.widget.img_widget.plot_image(correction.get_data(), True)
                self.widget.cylinder_plot_btn.setText("Back")
                self.widget.cbn_plot_btn.setText("Plot")
                self.widget.oiadac_plot_btn.setText("Plot")
                self.widget.slab_plot_btn.setText("Plot")
                self.widget.sphere_plot_btn.setText("Plot")
                self.widget.plate_plot_btn.setText("Plot")
                self.widget.flat_field_plot_btn.setText("Plot")
            else:
                self.widget.cylinder_plot_btn.setChecked(False)
        else:
            self.widget.cylinder_plot_btn.setText("Plot")
            self.reset_img_widget()

    def update_cylinder_widgets(self):
        correction = self.model.img_model.img_corrections.get_correction("cylinder")
        if correction is None:
            return
        params = correction.get_params()
        self.widget.cylinder_param_tw.cellWidget(1, 1).setText(str(params["radius"]))
        self.widget.cylinder_param_tw.cellWidget(2, 1).setText(str(params["axis_tilt"]))
        self.widget.cylinder_param_tw.cellWidget(3, 1).setText(str(params["axis_rotation"]))
        self.widget.cylinder_param_tw.cellWidget(4, 1).setText(str(params["beam_width"]))
        mu = params["absorption_coefficient"]
        self.widget.cylinder_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")
        self.widget.cylinder_groupbox.setChecked(True)

    def sphere_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.sphere_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                "ERROR",
                "Please calibrate the geometry first or load an existent calibration file. "
                + "The sphere absorption correction needs a calibrated geometry.",
            )
            return

        if self.widget.sphere_groupbox.isChecked():
            formula = self.widget.sphere_formula_txt.text().strip()
            if not formula:
                self.widget.sphere_groupbox.setChecked(False)
                return

            density = self.widget.sphere_param_tw.cellWidget(0, 1).value()
            radius = self.widget.sphere_param_tw.cellWidget(1, 1).value()
            beam_width = self.widget.sphere_param_tw.cellWidget(2, 1).value()

            wavelength_m = self.model.calibration_model.wavelength
            energy_eV = wavelength_to_energy(wavelength_m)
            try:
                mu = calculate_mu(formula, energy_eV, density=density if density > 0 else None)
            except Exception as e:
                self.widget.sphere_groupbox.setChecked(False)
                self.widget.sphere_mu_lbl.setText("μ:")
                QtWidgets.QMessageBox.critical(
                    self.widget, "Invalid Formula",
                    f"Could not calculate absorption coefficient:\n{e}",
                )
                return

            self.widget.sphere_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")

            tth_array = 180.0 / np.pi * self.model.calibration_model.tth_array
            azi_array = 180.0 / np.pi * self.model.calibration_model.azi_array

            new_correction = SphereAbsorptionCorrection(
                tth_array=tth_array,
                azi_array=azi_array,
                radius=radius,
                absorption_coefficient=mu,
                beam_width=beam_width,
            )
            new_correction.update()
            try:
                self.model.img_model.delete_img_correction("sphere")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(new_correction, "sphere")
        else:
            try:
                self.model.img_model.delete_img_correction("sphere")
            except KeyError:
                pass
            self.widget.sphere_mu_lbl.setText("μ:")

    def sphere_plot_btn_clicked(self):
        if str(self.widget.sphere_plot_btn.text()) == "Plot":
            correction = self.model.img_model.img_corrections.get_correction("sphere")
            if correction is not None:
                self.widget.img_widget.plot_image(correction.get_data(), True)
                self.widget.sphere_plot_btn.setText("Back")
                self.widget.cbn_plot_btn.setText("Plot")
                self.widget.oiadac_plot_btn.setText("Plot")
                self.widget.slab_plot_btn.setText("Plot")
                self.widget.cylinder_plot_btn.setText("Plot")
                self.widget.plate_plot_btn.setText("Plot")
                self.widget.flat_field_plot_btn.setText("Plot")
            else:
                self.widget.sphere_plot_btn.setChecked(False)
        else:
            self.widget.sphere_plot_btn.setText("Plot")
            self.reset_img_widget()

    def update_sphere_widgets(self):
        correction = self.model.img_model.img_corrections.get_correction("sphere")
        if correction is None:
            return
        params = correction.get_params()
        self.widget.sphere_param_tw.cellWidget(1, 1).setText(str(params["radius"]))
        self.widget.sphere_param_tw.cellWidget(2, 1).setText(str(params["beam_width"]))
        mu = params["absorption_coefficient"]
        self.widget.sphere_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")
        self.widget.sphere_groupbox.setChecked(True)

    def plate_groupbox_changed(self):
        if not self.model.calibration_model.is_calibrated:
            self.widget.plate_groupbox.setChecked(False)
            QtWidgets.QMessageBox.critical(
                self.widget,
                "ERROR",
                "Please calibrate the geometry first or load an existent calibration file. "
                + "The plate absorption correction needs a calibrated geometry.",
            )
            return

        if self.widget.plate_groupbox.isChecked():
            formula = self.widget.plate_formula_txt.text().strip()
            if not formula:
                self.widget.plate_groupbox.setChecked(False)
                return

            density = self.widget.plate_param_tw.cellWidget(0, 1).value()
            thickness = self.widget.plate_param_tw.cellWidget(1, 1).value()
            plate_tilt = self.widget.plate_param_tw.cellWidget(2, 1).value()
            plate_rotation = self.widget.plate_param_tw.cellWidget(3, 1).value()

            wavelength_m = self.model.calibration_model.wavelength
            energy_eV = wavelength_to_energy(wavelength_m)
            try:
                mu = calculate_mu(formula, energy_eV, density=density if density > 0 else None)
            except Exception as e:
                self.widget.plate_groupbox.setChecked(False)
                self.widget.plate_mu_lbl.setText("μ:")
                QtWidgets.QMessageBox.critical(
                    self.widget,
                    "Invalid Formula",
                    f"Could not calculate absorption coefficient:\n{e}",
                )
                return

            self.widget.plate_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")

            tth_array = 180.0 / np.pi * self.model.calibration_model.tth_array
            azi_array = 180.0 / np.pi * self.model.calibration_model.azi_array

            new_correction = PlateAbsorptionCorrection(
                tth_array=tth_array,
                azi_array=azi_array,
                thickness=thickness,
                absorption_coefficient=mu,
                plate_tilt=plate_tilt,
                plate_rotation=plate_rotation,
            )
            new_correction.update()
            try:
                self.model.img_model.delete_img_correction("plate")
            except KeyError:
                pass
            self.model.img_model.add_img_correction(new_correction, "plate")
        else:
            try:
                self.model.img_model.delete_img_correction("plate")
            except KeyError:
                pass
            self.widget.plate_mu_lbl.setText("μ:")

    def plate_plot_btn_clicked(self):
        if str(self.widget.plate_plot_btn.text()) == "Plot":
            correction = self.model.img_model.img_corrections.get_correction("plate")
            if correction is not None:
                self.widget.img_widget.plot_image(correction.get_data(), True)
                self.widget.plate_plot_btn.setText("Back")
                self.widget.cbn_plot_btn.setText("Plot")
                self.widget.oiadac_plot_btn.setText("Plot")
                self.widget.slab_plot_btn.setText("Plot")
                self.widget.cylinder_plot_btn.setText("Plot")
                self.widget.sphere_plot_btn.setText("Plot")
                self.widget.flat_field_plot_btn.setText("Plot")
            else:
                self.widget.plate_plot_btn.setChecked(False)
        else:
            self.widget.plate_plot_btn.setText("Plot")
            self.reset_img_widget()

    def update_plate_widgets(self):
        correction = self.model.img_model.img_corrections.get_correction("plate")
        if correction is None:
            return
        params = correction.get_params()
        self.widget.plate_param_tw.cellWidget(1, 1).setText(str(params["thickness"]))
        self.widget.plate_param_tw.cellWidget(2, 1).setText(str(params["plate_tilt"]))
        self.widget.plate_param_tw.cellWidget(3, 1).setText(str(params["plate_rotation"]))
        mu = params["absorption_coefficient"]
        self.widget.plate_mu_lbl.setText(f"μ: {mu:.4f} 1/mm")
        self.widget.plate_groupbox.setChecked(True)

    def reset_plot_btns(self):
        self.widget.oiadac_plot_btn.setText("Plot")
        self.widget.oiadac_plot_btn.setChecked(False)
        self.widget.cbn_plot_btn.setText("Plot")
        self.widget.cbn_plot_btn.setChecked(False)
        self.widget.transfer_plot_btn.setText("Plot")
        self.widget.transfer_plot_btn.setChecked(False)
        self.widget.slab_plot_btn.setText("Plot")
        self.widget.slab_plot_btn.setChecked(False)
        self.widget.cylinder_plot_btn.setText("Plot")
        self.widget.cylinder_plot_btn.setChecked(False)
        self.widget.sphere_plot_btn.setText("Plot")
        self.widget.sphere_plot_btn.setChecked(False)
        self.widget.plate_plot_btn.setText("Plot")
        self.widget.plate_plot_btn.setChecked(False)
        self.widget.flat_field_plot_btn.setText("Plot")
        self.widget.flat_field_plot_btn.setChecked(False)

    def update_gui(self):
        if self.model.img_model.get_img_correction("cbn") is not None:
            self.update_cbn_widgets()
            self.widget.cbn_groupbox.blockSignals(True)
            self.widget.cbn_groupbox.setChecked(True)
            self.widget.cbn_groupbox.blockSignals(False)
        else:
            self.widget.cbn_groupbox.setChecked(False)

        if self.model.img_model.get_img_correction("oiadac") is not None:
            self.update_oiadac_widgets()
            self.widget.oiadac_groupbox.blockSignals(True)
            self.widget.oiadac_groupbox.setChecked(True)
            self.widget.oiadac_groupbox.blockSignals(False)
        else:
            self.widget.oiadac_groupbox.setChecked(False)

        if self.model.img_model.get_img_correction("transfer") is not None:
            self.update_transfer_widgets()
            # self.widget.transfer_gb.blockSignals(True)
            self.widget.transfer_gb.setChecked(True)
            # self.widget.transfer_gb.blockSignals(False)
        else:
            self.widget.transfer_gb.setChecked(False)

        if self.model.img_model.get_img_correction("slab") is not None:
            self.update_slab_widgets()
            self.widget.slab_groupbox.blockSignals(True)
            self.widget.slab_groupbox.setChecked(True)
            self.widget.slab_groupbox.blockSignals(False)
        else:
            self.widget.slab_groupbox.setChecked(False)
            self.widget.slab_mu_lbl.setText("μ:")

        if self.model.img_model.get_img_correction("cylinder") is not None:
            self.update_cylinder_widgets()
            self.widget.cylinder_groupbox.blockSignals(True)
            self.widget.cylinder_groupbox.setChecked(True)
            self.widget.cylinder_groupbox.blockSignals(False)
        else:
            self.widget.cylinder_groupbox.setChecked(False)
            self.widget.cylinder_mu_lbl.setText("μ:")

        if self.model.img_model.get_img_correction("sphere") is not None:
            self.update_sphere_widgets()
            self.widget.sphere_groupbox.blockSignals(True)
            self.widget.sphere_groupbox.setChecked(True)
            self.widget.sphere_groupbox.blockSignals(False)
        else:
            self.widget.sphere_groupbox.setChecked(False)
            self.widget.sphere_mu_lbl.setText("μ:")

        if self.model.img_model.get_img_correction("plate") is not None:
            self.update_plate_widgets()
            self.widget.plate_groupbox.blockSignals(True)
            self.widget.plate_groupbox.setChecked(True)
            self.widget.plate_groupbox.blockSignals(False)
        else:
            self.widget.plate_groupbox.setChecked(False)
            self.widget.plate_mu_lbl.setText("μ:")

        if self.model.img_model.get_img_correction("flat_field") is not None:
            self.update_flat_field_widgets()
            self.widget.flat_field_gb.setChecked(True)
        else:
            self.widget.flat_field_gb.setChecked(False)
