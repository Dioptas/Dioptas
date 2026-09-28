# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore

from ...CustomWidgets import (
    IntegerTextField,
    MenuTabWidget,
    NumberTextField,
    LabelAlignRight,
    SpinBoxAlignRight,
    ConservativeSpinBox,
    CheckableFlatButton,
    FlatButton,
    SaveIconButton,
    DoubleSpinBoxAlignRight,
)


class OptionsWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.create_integration_gb()
        self.create_cake_gb()
        self.create_phase_gb()

        self.style_integration_widgets()
        self.style_cake_widgets()
        self.set_tooltips()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 5, 0, 0)
        self._layout.setSpacing(0)

        self._tab_widget = MenuTabWidget()
        self._tab_widget.add_tab("1D Integration", self.integration_gb)
        self._tab_widget.add_tab("2D Integration", self.cake_gb)
        self._tab_widget.add_tab("Phase", self.phase_gb)

        self._layout.addWidget(self._tab_widget)

        self.setLayout(self._layout)
        self.set_stylesheet()
        self._integration_columns = 2
        self._integration_viewport = self._tab_widget.tab_widgets[0].viewport()
        self._integration_viewport.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._integration_viewport and event.type() == QtCore.QEvent.Resize:
            groups = (self.sampling_gb, self.azimuth_gb,
                      self.corrections_gb, self.spottiness_gb)
            required = (max(groups[0].minimumSizeHint().width(), groups[2].minimumSizeHint().width())
                        + max(groups[1].minimumSizeHint().width(), groups[3].minimumSizeHint().width())
                        + 30)
            columns = 2 if event.size().width() >= required else 1
            if columns != self._integration_columns:
                self._integration_columns = columns
                for group in groups:
                    self._integration_gb_layout.removeWidget(group)
                for index, group in enumerate(groups):
                    self._integration_gb_layout.addWidget(group, index // columns, index % columns)
                self._integration_gb_layout.setColumnStretch(1, 1 if columns == 2 else 0)
        return super().eventFilter(watched, event)

    def create_phase_gb(self):
        self.phase_gb = QtWidgets.QGroupBox("Phase options")
        layout = QtWidgets.QVBoxLayout(self.phase_gb)
        layout.setContentsMargins(8, 8, 8, 7)
        layout.setSpacing(10)

        self.dac_thermal_pressure_cb = QtWidgets.QCheckBox("DAC thermal pressure")
        self.dac_thermal_pressure_factor_sb = DoubleSpinBoxAlignRight()
        self.dac_thermal_pressure_factor_sb.setDecimals(4)
        self.dac_thermal_pressure_factor_sb.setRange(0.0, 0.9999)
        self.dac_thermal_pressure_factor_sb.setSingleStep(0.01)
        self.dac_thermal_pressure_factor_sb.setValue(0.25)
        self.dac_thermal_pressure_factor_sb.setFixedWidth(70)
        self.dac_thermal_pressure_factor_sb.setEnabled(False)
        self.dac_thermal_pressure_cb.setToolTip(
            "Predict heated phase volumes from cold/reference pressure, "
            "including diamond-anvil-cell confinement.")
        self.dac_thermal_pressure_factor_sb.setToolTip(
            "Fraction of the thermal-pressure increase retained by confinement. "
            "0.25 means 25%; the allowed range is 0 to less than 1.")

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self.dac_thermal_pressure_cb)
        controls.addSpacing(15)
        controls.addWidget(QtWidgets.QLabel("Fraction"))
        controls.addWidget(self.dac_thermal_pressure_factor_sb)
        controls.addStretch()
        layout.addLayout(controls)

        self.dac_thermal_pressure_info = QtWidgets.QLabel(
            "<p>Predicts phase-line positions during heating in a diamond anvil cell, "
            "including the pressure rise caused by confinement.</p>"
            "<p>When enabled, enter the <b>cold/reference pressure P₀</b> in the phase "
            "table and choose the hot temperature. The same fraction applies to all "
            "phases with a Peritheos thermal equation of state, including newly added phases.</p>"
            "<p>A fraction of <b>0.25 retains 25%</b> of the thermal-pressure increase; "
            "0 gives constant-pressure heating. Use a value below 1. "
            "Leave this off if your input is already the measured hot pressure.</p>"
        )
        self.dac_thermal_pressure_info.setWordWrap(True)
        self.dac_thermal_pressure_info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.dac_thermal_pressure_info)
        layout.addStretch()

    def set_dac_thermal_pressure(self, enabled, factor):
        with QtCore.QSignalBlocker(self.dac_thermal_pressure_cb), \
                QtCore.QSignalBlocker(self.dac_thermal_pressure_factor_sb):
            self.dac_thermal_pressure_cb.setChecked(enabled)
            self.dac_thermal_pressure_factor_sb.setValue(factor)
        self.dac_thermal_pressure_factor_sb.setEnabled(enabled)

    def show_dac_condition_rejected(self, message):
        control = self.dac_thermal_pressure_cb
        QtWidgets.QToolTip.showText(
            control.mapToGlobal(control.rect().bottomLeft()), message, control)

    @staticmethod
    def _control_group(title):
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QGridLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignTop)
        return group, layout

    def create_integration_gb(self):
        self.integration_gb = QtWidgets.QGroupBox("1D integration")
        self._integration_gb_layout = QtWidgets.QGridLayout(self.integration_gb)
        self._integration_gb_layout.setContentsMargins(8, 8, 8, 8)
        self._integration_gb_layout.setSpacing(10)
        self._integration_gb_layout.setAlignment(QtCore.Qt.AlignTop)

        self.sampling_gb, sampling = self._control_group("Sampling")
        self.azimuth_gb, azimuth = self._control_group("Azimuth range")
        self.corrections_gb, corrections = self._control_group("Corrections and errors")
        self.spottiness_gb, spottiness = self._control_group("Spottiness")
        for row, column, group in (
            (0, 0, self.sampling_gb), (0, 1, self.azimuth_gb),
            (1, 0, self.corrections_gb), (1, 1, self.spottiness_gb),
        ):
            self._integration_gb_layout.addWidget(group, row, column)
        self._integration_gb_layout.setColumnStretch(0, 1)
        self._integration_gb_layout.setColumnStretch(1, 1)

        self.bin_count_txt = IntegerTextField("0")
        self.bin_count_cb = QtWidgets.QCheckBox("Auto")
        self.supersampling_sb = SpinBoxAlignRight()
        self.use_dioptrin_cb = QtWidgets.QCheckBox("Use Dioptrin")
        sampling.addWidget(LabelAlignRight("Radial bins:"), 0, 0)
        sampling.addWidget(self.bin_count_txt, 0, 1)
        sampling.addWidget(self.bin_count_cb, 0, 2)
        sampling.addWidget(LabelAlignRight("Supersampling:"), 1, 0)
        sampling.addWidget(self.supersampling_sb, 1, 1)
        sampling.addWidget(self.use_dioptrin_cb, 2, 0, 1, 3)

        self.oned_azimuth_min_txt = NumberTextField("-180")
        self.oned_azimuth_max_txt = NumberTextField("180")
        self.oned_full_toggle_btn = CheckableFlatButton("Full range")
        azimuth.addWidget(LabelAlignRight("From (°):"), 0, 0)
        azimuth.addWidget(self.oned_azimuth_min_txt, 0, 1)
        azimuth.addWidget(LabelAlignRight("To (°):"), 1, 0)
        azimuth.addWidget(self.oned_azimuth_max_txt, 1, 1)
        azimuth.addWidget(self.oned_full_toggle_btn, 2, 1)

        self.correct_solid_angle_cb = QtWidgets.QCheckBox("Correct solid angle")
        self.correct_solid_angle_cb.setChecked(True)
        self.calculate_poisson_errors_cb = QtWidgets.QCheckBox("Calculate Poisson errors")
        corrections.addWidget(self.correct_solid_angle_cb, 0, 0, QtCore.Qt.AlignLeft)
        corrections.addWidget(self.calculate_poisson_errors_cb, 1, 0, QtCore.Qt.AlignLeft)

        self.calculate_azimuthal_std_cb = QtWidgets.QCheckBox("Show Spottiness")
        self.calculate_azimuthal_std_cb.setToolTip(
            "Calculate azimuthal standard deviation and show the Spottiness panel")
        self.spottiness_relative_cb = QtWidgets.QCheckBox("Relative spread (std / mean)")
        self.spottiness_relative_cb.setToolTip(
            "Uses the original integrated mean. Nonpositive and near-zero means are omitted.")
        self.spottiness_relative_cb.setEnabled(False)
        self.save_spottiness_btn = FlatButton("Save Spottiness…")
        self.save_spottiness_btn.setToolTip("Export mean, azimuthal std and relative spread to CSV")
        self.save_spottiness_btn.setEnabled(False)
        spottiness.addWidget(self.calculate_azimuthal_std_cb, 0, 0, QtCore.Qt.AlignLeft)
        spottiness.addWidget(self.spottiness_relative_cb, 1, 0, QtCore.Qt.AlignLeft)
        spottiness.addWidget(self.save_spottiness_btn, 2, 0)

    def create_cake_gb(self):
        self.cake_gb = QtWidgets.QGroupBox("2D (Cake-) integration")
        self._cake_gb_layout = QtWidgets.QGridLayout()
        self._cake_gb_layout.setContentsMargins(5, 8, 5, 7)
        self._cake_gb_layout.setSpacing(5)

        self.cake_azimuth_points_sb = ConservativeSpinBox()
        self.cake_azimuth_min_txt = NumberTextField("-180")
        self.cake_azimuth_max_txt = NumberTextField("180")
        self.cake_full_toggle_btn = CheckableFlatButton("Full")
        self.cake_integral_width_sb = ConservativeSpinBox()
        self.cake_save_integral_btn = SaveIconButton()

        self._cake_gb_layout.addWidget(LabelAlignRight("Azimuth bins:"), 0, 0)
        self._cake_gb_layout.addWidget(self.cake_azimuth_points_sb, 0, 1)
        self._cake_gb_layout.addWidget(LabelAlignRight("Azimuth range:"), 1, 0)
        self._azi_range_layout = QtWidgets.QHBoxLayout()
        self._azi_range_layout.setContentsMargins(0, 0, 0, 0)
        self._azi_range_layout.setSpacing(5)
        self._azi_range_layout.addWidget(self.cake_azimuth_min_txt)
        self._azi_range_layout.addWidget(LabelAlignRight("-"))
        self._azi_range_layout.addWidget(self.cake_azimuth_max_txt)
        self._cake_gb_layout.addLayout(self._azi_range_layout, 1, 1, 1, 2)
        self._cake_gb_layout.addWidget(self.cake_full_toggle_btn, 1, 3)
        self._cake_gb_layout.addWidget(LabelAlignRight("Integral Width:"), 2, 0)
        self._cake_gb_layout.addWidget(self.cake_integral_width_sb, 2, 1)
        self._cake_gb_layout.addWidget(self.cake_save_integral_btn, 2, 2)

        self._cake_gb_layout.setRowStretch(0, 0)
        self._cake_gb_layout.setRowStretch(1, 0)
        self._cake_gb_layout.setRowStretch(2, 0)
        self._cake_gb_layout.setRowStretch(3, 1)
        self._cake_gb_layout.setColumnStretch(0, 0)
        self._cake_gb_layout.setColumnStretch(1, 0)
        self._cake_gb_layout.setColumnStretch(2, 0)
        self._cake_gb_layout.setColumnStretch(3, 0)
        self._cake_gb_layout.setColumnStretch(4, 1)

        self.cake_gb.setLayout(self._cake_gb_layout)

    def style_integration_widgets(self):
        self.supersampling_sb.setMinimum(1)
        self.supersampling_sb.setMaximum(20)
        self.supersampling_sb.setSingleStep(1)

        self.bin_count_txt.setEnabled(False)
        self.bin_count_cb.setChecked(True)

        self.oned_full_toggle_btn.setChecked(True)
        self.oned_azimuth_min_txt.setDisabled(True)
        self.oned_azimuth_max_txt.setDisabled(True)

    def style_cake_widgets(self):
        self.cake_azimuth_points_sb.setMinimum(1)
        self.cake_azimuth_points_sb.setMaximum(10000)
        self.cake_azimuth_points_sb.setSingleStep(100)

        self.cake_full_toggle_btn.setChecked(True)
        self.cake_azimuth_min_txt.setDisabled(True)
        self.cake_azimuth_max_txt.setDisabled(True)

        self.cake_integral_width_sb.setMinimum(1)
        self.cake_integral_width_sb.setSingleStep(1)
        self.cake_integral_width_sb.setMaximum(1000000)
        button_width = 25
        button_height = 25
        self.cake_save_integral_btn.setIconSize(QtCore.QSize(15, 15))
        self.cake_save_integral_btn.setWidth(button_width)
        self.cake_save_integral_btn.setHeight(button_height)

    def set_tooltips(self):
        self.cake_full_toggle_btn.setToolTip("Set to full available range")
        self.oned_full_toggle_btn.setToolTip("Set to full available range")
        self.calculate_poisson_errors_cb.setToolTip(
            "Calculate and store propagated Poisson uncertainties during 1D integration"
        )
        self.cake_save_integral_btn.setToolTip(
            "Save the tth integral next to the cake image"
        )
        self.cake_integral_width_sb.setToolTip(
            "Sets the width used for the integral plot\nnext to the cake image."
        )

    def set_stylesheet(self):
        self.setStyleSheet(
            """
            QSpinBox, QDoubleSpinBox, QLineEdit {
                width: 60px;
            } 
            """
        )
