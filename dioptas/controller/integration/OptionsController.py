# SPDX-License-Identifier: MIT


# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel

from ..binding import Binder


class OptionsController:
    """
    Handles the integration options tab: radial bin count display, azimuth
    ranges for 1D/2D integration, solid angle and Poisson-error calculation,
    and dioptrin usage.
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to an IntegrationWidget
        :param dioptas_model: reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """

        self.integration_widget = widget
        self.options_widget = self.integration_widget.integration_control_widget.integration_options_widget

        self.model = dioptas_model

        self._setup_dioptrin_checkbox()
        self.binder = Binder(field_events=self.model.configuration_params_changed)
        self.create_bindings()
        self.connect_signals()
        self.binder.refresh()

    def _setup_dioptrin_checkbox(self):
        import dioptas

        self._dioptrin_available = dioptas._dioptrin_available
        if not self._dioptrin_available:
            self.options_widget.use_dioptrin_cb.setVisible(False)

    def create_bindings(self):
        configuration = lambda: self.model.current_configuration

        self.binder.bind_checkbox(
            self.options_widget.correct_solid_angle_cb,
            configuration,
            "correct_solid_angle",
            event_field="calibration.correct_solid_angle",
        )
        self.binder.bind_checkbox(
            self.options_widget.calculate_poisson_errors_cb,
            configuration,
            "calculate_poisson_errors",
        )
        self.binder.bind_spinbox(
            self.options_widget.cake_azimuth_points_sb,
            configuration,
            "cake_azimuth_points",
        )
        self.binder.bind_optional_range(
            self.options_widget.oned_azimuth_min_txt,
            self.options_widget.oned_azimuth_max_txt,
            self.options_widget.oned_full_toggle_btn,
            configuration,
            "oned_azimuth_range",
        )
        self.binder.bind_optional_range(
            self.options_widget.cake_azimuth_min_txt,
            self.options_widget.cake_azimuth_max_txt,
            self.options_widget.cake_full_toggle_btn,
            configuration,
            "cake_azimuth_range",
            on_full_changed=self._cake_full_range_changed,
        )
        # display-only values
        self.binder.add_render(
            lambda: self.options_widget.bin_count_txt.setText(
                "{:1.0f}".format(self.model.calibration_model.num_points)
            ),
            self.options_widget.bin_count_txt,
        )
        self.binder.add_render(
            lambda: self.options_widget.use_dioptrin_cb.setChecked(
                self.model.calibration_model.use_dioptrin
            ),
            self.options_widget.use_dioptrin_cb,
            field="calibration.use_dioptrin",
        )

    def connect_signals(self):
        self.binder.connect_refresh(self.model.configuration_selected)
        self.binder.connect_refresh(self.model.pattern_changed)
        self.options_widget.use_dioptrin_cb.toggled.connect(self._use_dioptrin_toggled)
        self.options_widget.calculate_poisson_errors_cb.toggled.connect(
            self._poisson_errors_toggled
        )

    def _cake_full_range_changed(self, is_full):
        """The cake azimuth shift slider only makes sense for the full range."""
        slider = self.integration_widget.cake_shift_azimuth_sl
        slider.setDisabled(not is_full)
        if not is_full:
            slider.setValue(0)

    def _use_dioptrin_toggled(self, checked):
        self.model.calibration_model.use_dioptrin = checked
        if checked and self.model.calibration_model.is_calibrated:
            self.model.calibration_model._create_dioptrin_integrator()
        if self.model.calibration_model.is_calibrated:
            self.model.current_configuration.integrate_image_1d()
            if self.model.current_configuration.auto_integrate_cake:
                self.model.current_configuration.integrate_image_2d()

    def _poisson_errors_toggled(self, checked):
        if checked:
            return
        # Error-bearing autocreate formats must not remain active while
        # error calculation is disabled. Selecting either one again invokes
        # the confirmation/reintegration flow in PatternController.
        for checkbox in (
            self.integration_widget.pattern_header_xye_cb,
            self.integration_widget.pattern_header_fxye_cb,
        ):
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        configuration = self.model.current_configuration
        configuration.integrated_patterns_file_formats = [
            suffix
            for suffix in configuration.integrated_patterns_file_formats
            if suffix not in (".xye", ".fxye")
        ]
