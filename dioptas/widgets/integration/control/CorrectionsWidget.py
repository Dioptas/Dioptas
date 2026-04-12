# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore

from ...CustomWidgets import (
    HorizontalSpacerItem,
    MenuTabWidget,
    NumberTextField,
    ListTableWidget,
    CheckableButton,
    CheckableFlatButton,
    VerticalSpacerItem,
)


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

    def create_cbn_correction_widgets(self):
        self.cbn_seat_gb = QtWidgets.QGroupBox("cBN Seat Correction")
        self.cbn_seat_plot_btn = CheckableButton("Plot")

        self.cbn_param_tw = ListTableWidget()
        self.cbn_param_tw.setColumnCount(3)

        self.cbn_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.cbn_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        cbn_parameters = [
            ["Anvil thickness", 2.3, "mm"],
            ["Seat thickness", 5.3, "mm"],
            ["Inner seat radius", 0.4, "mm"],
            ["Outer seat radius", 1.95, "mm"],
            ["Cell tilt", 0.0, "°"],
            ["Cell tilt rotation", 0, "°"],
            ["Center offset", 0, "mm"],
            ["Center offset rotation", 0, "°"],
            ["Anvil absorption length", 13.7, "mm"],
            ["Seat absorption length", 12, "mm"],
        ]

        for cbn_parameter in cbn_parameters:
            self.add_param_to_tw(self.cbn_param_tw, *cbn_parameter)

    @staticmethod
    def add_param_to_tw(tw, name, value, unit):
        tw.blockSignals(True)
        new_row_ind = int(tw.rowCount())
        tw.setRowCount(new_row_ind + 1)

        name_item = QtWidgets.QTableWidgetItem(name + ":")
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        name_item.setTextAlignment(int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
        tw.setItem(new_row_ind, 0, name_item)

        value_item = NumberTextField("{:g}".format(value))
        tw.setCellWidget(new_row_ind, 1, value_item)

        unit_item = QtWidgets.QTableWidgetItem(unit)
        unit_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        unit_item.setTextAlignment(int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter))
        tw.setItem(new_row_ind, 2, unit_item)

        tw.resizeColumnToContents(0)
        tw.resizeColumnToContents(2)

        tw.blockSignals(False)

    @staticmethod
    def _create_description_label(text):
        lbl = QtWidgets.QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("QLabel { color: gray; }")
        return lbl

    def create_cbn_correction_layout(self):
        self._cbn_seat_outer_layout = QtWidgets.QVBoxLayout()
        self._cbn_seat_outer_layout.setSpacing(5)
        self._cbn_seat_outer_layout.addWidget(self._create_description_label(
            "Absorption by diamond anvil and cBN seat in a DAC, "
            "modeling the conical seat geometry."
        ))

        self._cbn_seat_layout = QtWidgets.QHBoxLayout()
        self._cbn_seat_layout.addWidget(self.cbn_param_tw)

        self._cbn_seat_right_layout = QtWidgets.QVBoxLayout()
        self._cbn_seat_right_layout.addWidget(self.cbn_seat_plot_btn)
        self._cbn_seat_right_layout.addStretch()
        self._cbn_seat_layout.addLayout(self._cbn_seat_right_layout)

        self._cbn_seat_outer_layout.addLayout(self._cbn_seat_layout)
        self.cbn_seat_gb.setLayout(self._cbn_seat_outer_layout)

    def create_oiadac_widgets(self):
        self.oiadac_gb = QtWidgets.QGroupBox("Detector Incidence Absorption Correction")

        self.oiadac_param_tw = ListTableWidget()
        self.oiadac_param_tw.setColumnCount(3)

        self.oiadac_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.oiadac_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        self.detector_thickness_txt = NumberTextField("40")
        self.detector_absorption_length_txt = NumberTextField("465.5")

        oiadac_parameters = [
            ["Detector thickness", 40, "mm"],
            ["Detector absorption length", 465.5, "um"],
        ]

        for param in oiadac_parameters:
            self.add_param_to_tw(self.oiadac_param_tw, *param)

        self.oiadac_plot_btn = CheckableButton("Plot")

    def create_oiadac_layout(self):
        self._oiadac_outer_layout = QtWidgets.QVBoxLayout()
        self._oiadac_outer_layout.setSpacing(5)
        self._oiadac_outer_layout.addWidget(self._create_description_label(
            "Corrects for oblique incidence angle absorption in the detector material "
            "(e.g. CdTe, Si)."
        ))

        self._oiadac_layout = QtWidgets.QHBoxLayout()
        self._oiadac_layout.addWidget(self.oiadac_param_tw)

        self._oiadac_right_layout = QtWidgets.QVBoxLayout()
        self._oiadac_right_layout.addWidget(self.oiadac_plot_btn)
        self._oiadac_right_layout.addStretch()
        self._oiadac_layout.addLayout(self._oiadac_right_layout)

        self._oiadac_outer_layout.addLayout(self._oiadac_layout)
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
        self._transfer_layout.addWidget(self.transfer_plot_btn, 0, 2)
        self._transfer_layout.setColumnStretch(0, 0)
        self._transfer_layout.setColumnStretch(1, 1)
        self._transfer_layout.setColumnStretch(2, 0)
        self._transfer_layout.setRowStretch(0, 0)
        self._transfer_layout.setRowStretch(1, 0)
        self._transfer_layout.setRowStretch(2, 1)

        self._transfer_outer_layout.addLayout(self._transfer_layout)
        self.transfer_gb.setLayout(self._transfer_outer_layout)

    def create_slab_correction_widgets(self):
        self.slab_gb = QtWidgets.QGroupBox("Slab Absorption Correction")
        self.slab_plot_btn = CheckableButton("Plot")

        self.slab_formula_txt = QtWidgets.QLineEdit("CeO2")
        self.slab_formula_txt.setPlaceholderText("e.g. CeO2, Fe2O3, Au")

        self.slab_param_tw = ListTableWidget()
        self.slab_param_tw.setColumnCount(3)
        self.slab_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.slab_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        slab_parameters = [
            ["Density", 7.22, "g/cm³"],
            ["Thickness", 0.1, "mm"],
            ["Slab tilt", 0.0, "°"],
            ["Slab rotation", 0.0, "°"],
        ]
        for param in slab_parameters:
            self.add_param_to_tw(self.slab_param_tw, *param)

        self.slab_mu_lbl = QtWidgets.QLabel("μ:")

    def create_slab_correction_layout(self):
        self._slab_layout = QtWidgets.QVBoxLayout()
        self._slab_layout.setSpacing(5)

        self._slab_layout.addWidget(self._create_description_label(
            "Sample self-absorption for a flat slab in transmission geometry. "
            "Integrates absorption over the scattering depth within the sample."
        ))

        # Formula row
        formula_layout = QtWidgets.QHBoxLayout()
        formula_layout.addWidget(QtWidgets.QLabel("Formula:"))
        formula_layout.addWidget(self.slab_formula_txt)
        self._slab_layout.addLayout(formula_layout)

        # Parameters + plot button
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.slab_param_tw)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.slab_plot_btn)
        right_layout.addWidget(self.slab_mu_lbl)
        right_layout.addStretch()
        params_layout.addLayout(right_layout)

        self._slab_layout.addLayout(params_layout)
        self.slab_gb.setLayout(self._slab_layout)

    def create_cylinder_correction_widgets(self):
        self.cylinder_gb = QtWidgets.QGroupBox("Cylinder Absorption Correction")
        self.cylinder_plot_btn = CheckableButton("Plot")

        self.cylinder_formula_txt = QtWidgets.QLineEdit("SiO2")
        self.cylinder_formula_txt.setPlaceholderText("e.g. SiO2, LaB6")

        self.cylinder_param_tw = ListTableWidget()
        self.cylinder_param_tw.setColumnCount(3)
        self.cylinder_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.cylinder_param_tw.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )

        cylinder_parameters = [
            ["Density", 2.65, "g/cm³"],
            ["Radius", 0.15, "mm"],
            ["Axis tilt", 0.0, "°"],
            ["Axis rotation", 0.0, "°"],
            ["Beam width", 0.0, "mm"],
        ]
        for param in cylinder_parameters:
            self.add_param_to_tw(self.cylinder_param_tw, *param)

        # Container sub-section
        self.cylinder_container_formula_txt = QtWidgets.QLineEdit("")
        self.cylinder_container_formula_txt.setPlaceholderText("e.g. SiO2 (glass)")

        self.cylinder_container_param_tw = ListTableWidget()
        self.cylinder_container_param_tw.setColumnCount(3)
        self.cylinder_container_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.cylinder_container_param_tw.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )
        container_params = [
            ["Container density", 2.23, "g/cm³"],
            ["Wall thickness", 0.01, "mm"],
        ]
        for param in container_params:
            self.add_param_to_tw(self.cylinder_container_param_tw, *param)

        self.cylinder_mu_lbl = QtWidgets.QLabel("μ:")

    def create_cylinder_correction_layout(self):
        self._cylinder_layout = QtWidgets.QVBoxLayout()
        self._cylinder_layout.setSpacing(5)

        self._cylinder_layout.addWidget(self._create_description_label(
            "Sample self-absorption for a cylindrical sample (e.g. in a capillary), "
            "with optional container wall absorption."
        ))

        # Sample formula row
        formula_layout = QtWidgets.QHBoxLayout()
        formula_layout.addWidget(QtWidgets.QLabel("Formula:"))
        formula_layout.addWidget(self.cylinder_formula_txt)
        self._cylinder_layout.addLayout(formula_layout)

        # Sample parameters + plot/mu
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.cylinder_param_tw)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.cylinder_plot_btn)
        right_layout.addWidget(self.cylinder_mu_lbl)
        right_layout.addStretch()
        params_layout.addLayout(right_layout)
        self._cylinder_layout.addLayout(params_layout)

        # Container section
        container_formula_layout = QtWidgets.QHBoxLayout()
        container_formula_layout.addWidget(QtWidgets.QLabel("Container:"))
        container_formula_layout.addWidget(self.cylinder_container_formula_txt)
        self._cylinder_layout.addLayout(container_formula_layout)

        self._cylinder_layout.addWidget(self.cylinder_container_param_tw)

        self.cylinder_gb.setLayout(self._cylinder_layout)

    def create_sphere_correction_widgets(self):
        self.sphere_gb = QtWidgets.QGroupBox("Sphere Absorption Correction")
        self.sphere_plot_btn = CheckableButton("Plot")

        self.sphere_formula_txt = QtWidgets.QLineEdit("Fe2O3")
        self.sphere_formula_txt.setPlaceholderText("e.g. Fe2O3, Au")

        self.sphere_param_tw = ListTableWidget()
        self.sphere_param_tw.setColumnCount(3)
        self.sphere_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.sphere_param_tw.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )

        sphere_parameters = [
            ["Density", 5.24, "g/cm³"],
            ["Radius", 0.5, "mm"],
            ["Beam width", 0.0, "mm"],
        ]
        for param in sphere_parameters:
            self.add_param_to_tw(self.sphere_param_tw, *param)

        self.sphere_mu_lbl = QtWidgets.QLabel("μ:")

    def create_sphere_correction_layout(self):
        self._sphere_layout = QtWidgets.QVBoxLayout()
        self._sphere_layout.setSpacing(5)

        self._sphere_layout.addWidget(self._create_description_label(
            "Sample self-absorption for a spherical sample."
        ))

        # Formula row
        formula_layout = QtWidgets.QHBoxLayout()
        formula_layout.addWidget(QtWidgets.QLabel("Formula:"))
        formula_layout.addWidget(self.sphere_formula_txt)
        self._sphere_layout.addLayout(formula_layout)

        # Parameters + plot/mu
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.sphere_param_tw)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.sphere_plot_btn)
        right_layout.addWidget(self.sphere_mu_lbl)
        right_layout.addStretch()
        params_layout.addLayout(right_layout)

        self._sphere_layout.addLayout(params_layout)
        self.sphere_gb.setLayout(self._sphere_layout)

    def create_plate_correction_widgets(self):
        self.plate_gb = QtWidgets.QGroupBox("Plate Absorption Correction")
        self.plate_plot_btn = CheckableButton("Plot")

        self.plate_formula_txt = QtWidgets.QLineEdit("C")
        self.plate_formula_txt.setPlaceholderText("e.g. C (diamond), SiO2")

        self.plate_param_tw = ListTableWidget()
        self.plate_param_tw.setColumnCount(3)
        self.plate_param_tw.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.plate_param_tw.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        plate_parameters = [
            ["Density", 3.51, "g/cm³"],
            ["Thickness", 2.0, "mm"],
            ["Plate tilt", 0.0, "°"],
            ["Plate rotation", 0.0, "°"],
        ]
        for param in plate_parameters:
            self.add_param_to_tw(self.plate_param_tw, *param)

        self.plate_mu_lbl = QtWidgets.QLabel("μ:")

    def create_plate_correction_layout(self):
        self._plate_layout = QtWidgets.QVBoxLayout()
        self._plate_layout.setSpacing(5)

        self._plate_layout.addWidget(self._create_description_label(
            "Absorption by a flat plate between sample and detector "
            "(e.g. diamond anvil window, Be window). No scattering depth integration."
        ))

        # Formula row
        formula_layout = QtWidgets.QHBoxLayout()
        formula_layout.addWidget(QtWidgets.QLabel("Formula:"))
        formula_layout.addWidget(self.plate_formula_txt)
        self._plate_layout.addLayout(formula_layout)

        # Parameters + plot button
        params_layout = QtWidgets.QHBoxLayout()
        params_layout.addWidget(self.plate_param_tw)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.plate_plot_btn)
        right_layout.addWidget(self.plate_mu_lbl)
        right_layout.addStretch()
        params_layout.addLayout(right_layout)

        self._plate_layout.addLayout(params_layout)
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
        self._flat_field_layout.addWidget(self.flat_field_plot_btn, 0, 2)
        self._flat_field_layout.setColumnStretch(0, 0)
        self._flat_field_layout.setColumnStretch(1, 1)
        self._flat_field_layout.setColumnStretch(2, 0)
        self._flat_field_layout.setRowStretch(0, 0)
        self._flat_field_layout.setRowStretch(1, 1)

        self._flat_field_outer_layout.addLayout(self._flat_field_layout)
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
