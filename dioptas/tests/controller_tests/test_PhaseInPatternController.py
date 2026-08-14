# SPDX-License-Identifier: MIT

from ..utility import QtTest
import os
import gc

from mock import MagicMock
import numpy as np

from ...controller.integration import PhaseInPatternController, PatternController
from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget


unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
jcpds_path = os.path.join(data_path, "jcpds")


class PhaseInPatternControllerTest(QtTest):
    def setUp(self) -> None:
        self.model = DioptasModel()
        self.model.calibration_model.is_calibrated = True
        self.model.calibration_model.pattern_geometry.wavelength = 0.31e-10
        self.model.calibration_model.integrate_1d = MagicMock(
            return_value=(
                self.model.calibration_model.tth,
                self.model.calibration_model.int,
            )
        )
        self.widget = IntegrationWidget()

        self.controller = PhaseInPatternController(
            self.widget.pattern_widget, self.model
        )
        self.pattern_controller = PatternController(self.widget, self.model)
        self.model.pattern_model.load_pattern(os.path.join(data_path, "pattern_001.xy"))

    def tearDown(self) -> None:
        del self.controller
        del self.widget
        self.model.delete_configurations()
        del self.model
        gc.collect()

    # Utility Functions
    #######################
    def load_phase(self, filename):
        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, filename))

    def load_phases(self):
        self.load_phase("ar.jcpds")
        self.load_phase("ag.jcpds")
        self.load_phase("au_Anderson.jcpds")
        self.load_phase("mo.jcpds")
        self.load_phase("pt.jcpds")
        self.load_phase("re.jcpds")

    # Tests
    #######################
    def test_loading_a_phase(self):
        self.assertEqual(len(self.widget.pattern_widget.phases), 0)
        self.load_phase("ar.jcpds")

        self.assertEqual(len(self.widget.pattern_widget.phases), 1)

    def test_remove_phase(self):
        self.load_phases()
        self.assertEqual(len(self.widget.pattern_widget.phases), 6)
        self.model.phase_model.del_phase(3)
        self.assertEqual(len(self.widget.pattern_widget.phases), 5)

    def test_changing_pressure(self):
        self.load_phase("ar.jcpds")
        first_line_position = (
            self.widget.pattern_widget.phases[0].line_items[0].getData()[0][0]
        )
        self.model.phase_model.set_pressure(0, 4)
        self.assertNotEqual(
            first_line_position,
            self.widget.pattern_widget.phases[0].line_items[0].getData()[0][0],
        )

    def test_changing_temperature_and_pressure(self):
        self.load_phase("pt.jcpds")
        self.model.phase_model.set_pressure(0, 100)
        first_line_position = (
            self.widget.pattern_widget.phases[0].line_items[0].getData()[0][0]
        )
        self.model.phase_model.set_temperature(0, 3000)
        self.assertNotEqual(
            first_line_position,
            self.widget.pattern_widget.phases[0].line_items[0].getData()[0][0],
        )

    def test_changing_color(self):
        self.load_phase("pt.jcpds")
        green_value = (
            self.widget.pattern_widget.phases[0]
            .line_items[0]
            .opts["pen"]
            .color()
            .green()
        )
        self.model.phase_model.set_color(0, (230, 22, 0))
        self.assertNotEqual(
            green_value,
            self.widget.pattern_widget.phases[0]
            .line_items[0]
            .opts["pen"]
            .color()
            .green(),
        )

    def test_auto_scaling_of_lines_in_pattern_view(self):
        pattern_view = self.widget.pattern_widget

        pattern_view_range = pattern_view.view_box.viewRange()
        pattern_y = pattern_view.plot_item.getData()[1]
        expected_maximum_height = np.max(pattern_y) - pattern_view_range[1][0]

        self.load_phase("au_Anderson.jcpds")
        phase_plot = pattern_view.phases[0]
        line_heights = []
        for line in phase_plot.line_items:
            line_data = line.getData()
            height = line_data[1][1] - line_data[1][0]
            line_heights.append(height)

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

        pattern_view_range = pattern_view.view_box.viewRange()
        pattern_y = pattern_view.plot_item.getData()[1]
        expected_maximum_height = np.max(pattern_y) - pattern_view_range[1][0]

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

    def test_line_height_in_pattern_view_after_zooming(self):
        pattern_view = self.widget.pattern_widget
        self.load_phase("au_Anderson.jcpds")

        pattern_view.view_box.setRange(xRange=[17, 30])
        pattern_view.emit_sig_range_changed()

        phase_plot = pattern_view.phases[0]
        line_heights = []
        for line in phase_plot.line_items:
            line_data = line.getData()
            if (line_data[0][0] > 17) and (line_data[0][1] < 30):
                height = line_data[1][1] - line_data[1][0]
                line_heights.append(height)

        pattern_view_range = pattern_view.view_box.viewRange()
        pattern_x, pattern_y = pattern_view.plot_item.getData()
        pattern_y_max_in_range = np.max(
            pattern_y[
                (pattern_x > pattern_view_range[0][0])
                & (pattern_x < pattern_view_range[0][1])
            ]
        )
        expected_maximum_height = pattern_y_max_in_range - pattern_view_range[1][0]

        self.assertAlmostEqual(expected_maximum_height, np.max(line_heights))

    def test_add_reflection(self):
        pattern_view = self.widget.pattern_widget
        self.load_phase("au_Anderson.jcpds")
        num_line_items = len(pattern_view.phases[0].line_items)
        self.model.phase_model.add_reflection(0)
        self.assertEqual(len(pattern_view.phases[0].line_items), num_line_items + 1)

    def test_delete_reflection(self):
        pattern_view = self.widget.pattern_widget
        self.load_phase("au_Anderson.jcpds")
        num_line_items = len(pattern_view.phases[0].line_items)
        self.model.phase_model.delete_reflection(0, 0)
        self.assertEqual(len(pattern_view.phases[0].line_items), num_line_items - 1)

    def test_reload_phase(self):
        self.load_phase("au_Anderson.jcpds")
        self.model.phase_model.reload(0)

    def test_reload_phase_after_deleting_a_reflection(self):
        self.load_phase("au_Anderson.jcpds")
        self.model.phase_model.delete_reflection(0, 0)
        self.model.phase_model.reload(0)

    def test_larger_pattern_q_range_extends_structure_phase_lines(self):
        from ...model import eos

        self.model.integration_unit = "q_A^-1"
        gold = next(
            material
            for material in eos.load_materials()
            if material.formula == "Au" and material.atom_sites
        )
        phase = eos.build_jcpds(gold)
        self.model.phase_model.add_jcpds_object(phase, filename=phase.filename)
        initial_count = len(phase.reflections)

        x = np.linspace(1.0, 20.0, 100)
        self.model.pattern_model.set_pattern(
            x,
            np.ones_like(x),
            unit="q_A^-1",
        )

        self.assertGreater(len(phase.reflections), initial_count)
        self.assertAlmostEqual(phase.state.reflection_q_max, 21.0)
        self.assertEqual(
            len(self.widget.pattern_widget.phases[0].line_items),
            len(phase.reflections),
        )

    def test_completed_calibration_checks_reflection_coverage(self):
        ensure_coverage = MagicMock()
        self.model.phase_model.ensure_structure_reflection_coverage = (
            ensure_coverage
        )

        self.model.calibration_model.parameters_changed.emit()

        ensure_coverage.assert_called_once()

    def test_configuration_reselection_reconnects_calibration_signal(self):
        self.model.configuration_selected.emit(0)

        self.assertIs(
            self.controller._calibration_model,
            self.model.calibration_model,
        )
        self.assertTrue(
            self.model.calibration_model.parameters_changed.has_listener(
                self.controller.pattern_data_changed
            )
        )
