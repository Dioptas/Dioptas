# SPDX-License-Identifier: MIT

import os

from qtpy import QtWidgets, QtCore, QtGui, QtSvg

from ...CustomWidgets import (
    MenuTabWidget,
    ParameterFormWidget,
    CheckableButton,
    align_parameter_forms,
)
from dioptas.paths import diagrams_path


class CorrectionsWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 5, 0, 0)

        self.create_cbn_correction_widgets()
        self.create_cbn_correction_layout()

        self.create_oiadac_widgets()
        self.create_oiadac_layout()

        self.create_transfer_widgets()
        self.create_transfer_layout()

        self.create_slab_correction_widgets()
        self.create_slab_correction_layout()

        self.create_cylinder_correction_widgets()
        self.create_cylinder_correction_layout()

        self.create_sphere_correction_widgets()
        self.create_sphere_correction_layout()

        self.create_plate_correction_widgets()
        self.create_plate_correction_layout()

        self.create_flat_field_widgets()
        self.create_flat_field_layout()

        self.setLayout(self._layout)

        self.menu_tab_widget = MenuTabWidget()
        self.menu_tab_widget.add_tab("cBN Seat", self.cbn_seat_gb)
        self.menu_tab_widget.add_tab("Inc. Abs.", self.oiadac_gb)
        self.menu_tab_widget.add_tab("Transfer", self.transfer_gb)
        self.menu_tab_widget.add_tab("Slab", self.slab_gb)
        self.menu_tab_widget.add_tab("Cylinder", self.cylinder_gb)
        self.menu_tab_widget.add_tab("Sphere", self.sphere_gb)
        self.menu_tab_widget.add_tab("Plate", self.plate_gb)
        self.menu_tab_widget.add_tab("Flat Field", self.flat_field_gb)
        self.menu_tab_widget.select_tab(0)

        self._layout.addWidget(self.menu_tab_widget)

        self.style_widgets()

    def sizeHint(self):
        """The correction pages scroll inside the menu-tab widget, and the
        tallest of them (cylinder geometry) would otherwise dictate the
        height of the whole control area. Only the menu column cannot
        scroll, so it defines this widget's natural height."""
        hint = super().sizeHint()
        margins = self._layout.contentsMargins()
        hint.setHeight(
            self.menu_tab_widget.menu_height()
            + margins.top() + margins.bottom()
        )
        return hint

    def create_cbn_correction_widgets(self):
        self.cbn_seat_gb = QtWidgets.QGroupBox("cBN Seat Correction")
        self.cbn_seat_plot_btn = CheckableButton("Plot")

        self.cbn_param_form = ParameterFormWidget([
            ("anvil_thickness", "Anvil thickness", 2.3, "mm"),
            ("seat_thickness", "Seat thickness", 5.3, "mm"),
            ("inner_seat_radius", "Inner seat radius", 0.4, "mm"),
            ("outer_seat_radius", "Outer seat radius", 1.95, "mm"),
            ("cell_tilt", "Cell tilt", 0.0, "°"),
            ("cell_tilt_rotation", "Cell tilt rotation", 0, "°"),
            ("center_offset", "Center offset", 0, "mm"),
            ("center_offset_rotation", "Center offset rotation", 0, "°"),
            ("anvil_absorption_length", "Anvil absorption length", 13.7, "mm"),
            ("seat_absorption_length", "Seat absorption length", 12, "mm"),
        ])

    @staticmethod
    def _create_formula_field(default, placeholder):
        txt = QtWidgets.QLineEdit(default)
        txt.setPlaceholderText(placeholder)
        txt.setMaximumWidth(160)
        return txt

    @staticmethod
    def _create_description_label(text):
        lbl = QtWidgets.QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("QLabel { color: gray; }")
        return lbl

    @staticmethod
    def _create_diagram_label(svg_filename):
        """Create a QLabel displaying an SVG diagram from the diagrams directory."""
        svg_path = os.path.join(diagrams_path, svg_filename)
        renderer = QtSvg.QSvgRenderer(svg_path)
        size = renderer.defaultSize()
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        lbl = QtWidgets.QLabel()
        lbl.setPixmap(pixmap)
        lbl.setFixedSize(size)
        return lbl

    def create_cbn_correction_layout(self):
        self._cbn_seat_outer_layout = QtWidgets.QVBoxLayout()
        self._cbn_seat_outer_layout.setSpacing(5)
        self._cbn_seat_outer_layout.addWidget(self._create_description_label(
            "Absorption by diamond anvil and cBN seat in a DAC, "
            "modeling the conical seat geometry."
        ))

        self._cbn_seat_layout = QtWidgets.QHBoxLayout()
        self._cbn_seat_layout.addWidget(self.cbn_param_form)

        self._cbn_seat_right_layout = QtWidgets.QVBoxLayout()
        self._cbn_seat_right_layout.addWidget(self.cbn_seat_plot_btn)
        self._cbn_seat_layout.addSpacing(15)
        self._cbn_seat_layout.addLayout(self._cbn_seat_right_layout)
        self._cbn_seat_layout.setAlignment(
            self._cbn_seat_right_layout, QtCore.Qt.AlignTop
        )
        self._cbn_seat_layout.addStretch()

        self._cbn_seat_outer_layout.addLayout(self._cbn_seat_layout)
        self._cbn_seat_outer_layout.addStretch()
        self.cbn_seat_gb.setLayout(self._cbn_seat_outer_layout)

    def create_oiadac_widgets(self):
        self.oiadac_gb = QtWidgets.QGroupBox("Detector Incidence Absorption Correction")

        self.oiadac_param_form = ParameterFormWidget([
            ("detector_thickness", "Detector thickness", 40, "mm"),
            ("detector_absorption_length", "Detector absorption length", 465.5, "um"),
        ])

        self.oiadac_plot_btn = CheckableButton("Plot")

    def create_oiadac_layout(self):
        self._oiadac_outer_layout = QtWidgets.QVBoxLayout()
        self._oiadac_outer_layout.setSpacing(5)
        self._oiadac_outer_layout.addWidget(self._create_description_label(
            "Corrects for oblique incidence angle absorption in the detector material "
            "(e.g. CdTe, Si)."
        ))

        self._oiadac_layout = QtWidgets.QHBoxLayout()
        self._oiadac_layout.addWidget(self.oiadac_param_form)

        self._oiadac_right_layout = QtWidgets.QVBoxLayout()
        self._oiadac_right_layout.addWidget(self.oiadac_plot_btn)
        self._oiadac_layout.addSpacing(15)
        self._oiadac_layout.addLayout(self._oiadac_right_layout)
        self._oiadac_layout.setAlignment(
            self._oiadac_right_layout, QtCore.Qt.AlignTop
        )
        self._oiadac_layout.addStretch()

        self._oiadac_outer_layout.addLayout(self._oiadac_layout)
        self._oiadac_outer_layout.addStretch()
        self.oiadac_gb.setLayout(self._oiadac_outer_layout)

    def create_transfer_widgets(self):
        self.transfer_gb = QtWidgets.QGroupBox("Transfer Correction")
        self.transfer_load_original_btn = QtWidgets.QPushButton("Load Original")
        self.transfer_load_response_btn = QtWidgets.QPushButton("Load Response")
        self.transfer_original_filename_lbl = QtWidgets.QLabel("None")
        self.transfer_response_filename_lbl = QtWidgets.QLabel("None")
        self.transfer_plot_btn = CheckableButton("Plot")

    def create_transfer_layout(self):
        self._transfer_outer_layout = QtWidgets.QVBoxLayout()
        self._transfer_outer_layout.setSpacing(5)
        self._transfer_outer_layout.addWidget(self._create_description_label(
            "Pixel-by-pixel correction using a measured detector response "
            "(ratio of original to response image)."
        ))

        self._transfer_layout = QtWidgets.QGridLayout()
        self._transfer_layout.setSpacing(5)
        self._transfer_layout.addWidget(self.transfer_load_original_btn, 0, 0)
        self._transfer_layout.addWidget(self.transfer_load_response_btn, 1, 0)
        self._transfer_layout.addWidget(self.transfer_original_filename_lbl, 0, 1)
        self._transfer_layout.addWidget(self.transfer_response_filename_lbl, 1, 1)
        self._transfer_layout.addWidget(
            self.transfer_plot_btn, 2, 0, QtCore.Qt.AlignLeft
        )
        self._transfer_layout.setColumnStretch(0, 0)
        self._transfer_layout.setColumnStretch(1, 1)

        self._transfer_outer_layout.addLayout(self._transfer_layout)
        self._transfer_outer_layout.addStretch()
        self.transfer_gb.setLayout(self._transfer_outer_layout)

    def create_slab_correction_widgets(self):
        self.slab_gb = QtWidgets.QGroupBox("Slab Absorption Correction")
        self.slab_plot_btn = CheckableButton("Plot")

        self.slab_formula_txt = self._create_formula_field(
            "CeO2", "e.g. CeO2, Fe2O3, Au"
        )

        self.slab_param_form = ParameterFormWidget()
        self.slab_param_form.add_row("Formula", self.slab_formula_txt)
        self.slab_param_form.add_parameters([
            ("density", "Density", 7.22, "g/cm³"),
            ("thickness", "Thickness", 0.1, "mm"),
            ("slab_tilt", "Slab tilt", 0.0, "°"),
            ("slab_rotation", "Slab rotation", 0.0, "°"),
        ])

        self.slab_mu_lbl = QtWidgets.QLabel("μ:")

    def create_slab_correction_layout(self):
        self._slab_layout = QtWidgets.QVBoxLayout()
        self._slab_layout.setSpacing(5)

        self._slab_layout.addWidget(self._create_description_label(
            "Sample self-absorption for a flat slab in transmission geometry. "
            "Integrates absorption over the scattering depth within the sample."
        ))

        # Parameters + plot button
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.slab_param_form)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.slab_plot_btn)
        right_layout.addWidget(self.slab_mu_lbl)
        params_layout.addSpacing(15)
        params_layout.addLayout(right_layout)
        params_layout.setAlignment(right_layout, QtCore.Qt.AlignTop)
        params_layout.addStretch()

        self._slab_layout.addLayout(params_layout)
        self._slab_layout.addWidget(self._create_diagram_label("slab_geometry.svg"))
        self._slab_layout.addStretch()
        self.slab_gb.setLayout(self._slab_layout)

    def create_cylinder_correction_widgets(self):
        self.cylinder_gb = QtWidgets.QGroupBox("Cylinder Absorption Correction")
        self.cylinder_plot_btn = CheckableButton("Plot")

        self.cylinder_formula_txt = self._create_formula_field(
            "SiO2", "e.g. SiO2, LaB6"
        )

        self.cylinder_param_form = ParameterFormWidget()
        self.cylinder_param_form.add_row("Formula", self.cylinder_formula_txt)
        self.cylinder_param_form.add_parameters([
            ("density", "Density", 2.65, "g/cm³"),
            ("radius", "Radius", 0.15, "mm"),
            ("axis_tilt", "Axis tilt", 0.0, "°"),
            ("axis_rotation", "Axis rotation", 0.0, "°"),
            ("beam_width", "Beam width", 0.0, "mm"),
        ])

        # Container sub-section
        self.cylinder_container_formula_txt = self._create_formula_field(
            "", "e.g. SiO2 (glass)"
        )

        self.cylinder_container_param_form = ParameterFormWidget()
        self.cylinder_container_param_form.add_row(
            "Container", self.cylinder_container_formula_txt
        )
        self.cylinder_container_param_form.add_parameters([
            ("container_density", "Container density", 2.23, "g/cm³"),
            ("wall_thickness", "Wall thickness", 0.01, "mm"),
        ])

        align_parameter_forms(
            self.cylinder_param_form, self.cylinder_container_param_form
        )

        self.cylinder_mu_lbl = QtWidgets.QLabel("μ:")

    def create_cylinder_correction_layout(self):
        self._cylinder_layout = QtWidgets.QVBoxLayout()
        self._cylinder_layout.setSpacing(5)

        self._cylinder_layout.addWidget(self._create_description_label(
            "Sample self-absorption for a cylindrical sample (e.g. in a capillary), "
            "with optional container wall absorption."
        ))

        # Sample parameters + plot/mu
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.cylinder_param_form)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.cylinder_plot_btn)
        right_layout.addWidget(self.cylinder_mu_lbl)
        params_layout.addSpacing(15)
        params_layout.addLayout(right_layout)
        params_layout.setAlignment(right_layout, QtCore.Qt.AlignTop)
        params_layout.addStretch()
        self._cylinder_layout.addLayout(params_layout)

        # Container section
        self._cylinder_layout.addWidget(self.cylinder_container_param_form)

        self._cylinder_layout.addWidget(self._create_diagram_label("cylinder_geometry.svg"))
        self._cylinder_layout.addStretch()

        self.cylinder_gb.setLayout(self._cylinder_layout)

    def create_sphere_correction_widgets(self):
        self.sphere_gb = QtWidgets.QGroupBox("Sphere Absorption Correction")
        self.sphere_plot_btn = CheckableButton("Plot")

        self.sphere_formula_txt = self._create_formula_field(
            "Fe2O3", "e.g. Fe2O3, Au"
        )

        self.sphere_param_form = ParameterFormWidget()
        self.sphere_param_form.add_row("Formula", self.sphere_formula_txt)
        self.sphere_param_form.add_parameters([
            ("density", "Density", 5.24, "g/cm³"),
            ("radius", "Radius", 0.5, "mm"),
            ("beam_width", "Beam width", 0.0, "mm"),
        ])

        self.sphere_mu_lbl = QtWidgets.QLabel("μ:")

    def create_sphere_correction_layout(self):
        self._sphere_layout = QtWidgets.QVBoxLayout()
        self._sphere_layout.setSpacing(5)

        self._sphere_layout.addWidget(self._create_description_label(
            "Sample self-absorption for a spherical sample."
        ))

        # Parameters + plot/mu
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.sphere_param_form)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.sphere_plot_btn)
        right_layout.addWidget(self.sphere_mu_lbl)
        params_layout.addSpacing(15)
        params_layout.addLayout(right_layout)
        params_layout.setAlignment(right_layout, QtCore.Qt.AlignTop)
        params_layout.addStretch()

        self._sphere_layout.addLayout(params_layout)
        self._sphere_layout.addStretch()
        self.sphere_gb.setLayout(self._sphere_layout)

    def create_plate_correction_widgets(self):
        self.plate_gb = QtWidgets.QGroupBox("Plate Absorption Correction")
        self.plate_plot_btn = CheckableButton("Plot")

        self.plate_formula_txt = self._create_formula_field(
            "C", "e.g. C (diamond), SiO2"
        )

        self.plate_param_form = ParameterFormWidget()
        self.plate_param_form.add_row("Formula", self.plate_formula_txt)
        self.plate_param_form.add_parameters([
            ("density", "Density", 3.51, "g/cm³"),
            ("thickness", "Thickness", 2.0, "mm"),
            ("plate_tilt", "Plate tilt", 0.0, "°"),
            ("plate_rotation", "Plate rotation", 0.0, "°"),
        ])

        self.plate_mu_lbl = QtWidgets.QLabel("μ:")

    def create_plate_correction_layout(self):
        self._plate_layout = QtWidgets.QVBoxLayout()
        self._plate_layout.setSpacing(5)

        self._plate_layout.addWidget(self._create_description_label(
            "Absorption by a flat plate between sample and detector "
            "(e.g. diamond anvil window, Be window). No scattering depth integration."
        ))

        # Parameters + plot button + diagram
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.plate_param_form)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.plate_plot_btn)
        right_layout.addWidget(self.plate_mu_lbl)
        params_layout.addSpacing(15)
        params_layout.addLayout(right_layout)
        params_layout.setAlignment(right_layout, QtCore.Qt.AlignTop)
        params_layout.addStretch()

        self._plate_layout.addLayout(params_layout)
        self._plate_layout.addWidget(self._create_diagram_label("plate_geometry.svg"))
        self._plate_layout.addStretch()
        self.plate_gb.setLayout(self._plate_layout)

    def create_flat_field_widgets(self):
        self.flat_field_gb = QtWidgets.QGroupBox("Flat Field Correction")
        self.flat_field_load_btn = QtWidgets.QPushButton("Load Flat Field")
        self.flat_field_filename_lbl = QtWidgets.QLabel("None")
        self.flat_field_plot_btn = CheckableButton("Plot")

    def create_flat_field_layout(self):
        self._flat_field_outer_layout = QtWidgets.QVBoxLayout()
        self._flat_field_outer_layout.setSpacing(5)
        self._flat_field_outer_layout.addWidget(self._create_description_label(
            "Pixel-by-pixel sensitivity correction using a uniform illumination "
            "(flat field) image. The flat field is normalized by its mean."
        ))

        self._flat_field_layout = QtWidgets.QGridLayout()
        self._flat_field_layout.setSpacing(5)
        self._flat_field_layout.addWidget(self.flat_field_load_btn, 0, 0)
        self._flat_field_layout.addWidget(self.flat_field_filename_lbl, 0, 1)
        self._flat_field_layout.addWidget(
            self.flat_field_plot_btn, 1, 0, QtCore.Qt.AlignLeft
        )
        self._flat_field_layout.setColumnStretch(0, 0)
        self._flat_field_layout.setColumnStretch(1, 1)

        self._flat_field_outer_layout.addLayout(self._flat_field_layout)
        self._flat_field_outer_layout.addStretch()
        self.flat_field_gb.setLayout(self._flat_field_outer_layout)

    def style_widgets(self):
        self.cbn_seat_gb.setCheckable(True)
        self.cbn_seat_gb.setChecked(False)
        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.transfer_gb.setCheckable(True)
        self.transfer_gb.setChecked(False)
        self.slab_gb.setCheckable(True)
        self.slab_gb.setChecked(False)
        self.cylinder_gb.setCheckable(True)
        self.cylinder_gb.setChecked(False)
        self.sphere_gb.setCheckable(True)
        self.sphere_gb.setChecked(False)
        self.plate_gb.setCheckable(True)
        self.plate_gb.setChecked(False)
        self.flat_field_gb.setCheckable(True)
        self.flat_field_gb.setChecked(False)

        self.setStyleSheet(
            """
                    QLineEdit {
                        min-width: 50 px;
                        min-height: 26 px;
                        max-height: 26 px;
                    }
                    """
        )
