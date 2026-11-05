import os

import numpy as np
import pytest
from qtpy import QtCore
from qtpy.QtTest import QTest

from ..utility import QtTest, click_button

from ...widgets.integration import IntegrationWidget
from ...controller.integration.BatchController import BatchController
from ...model.DioptasModel import DioptasModel
from dioptas.controller.integration.phase.PhaseController import PhaseController
from dioptas import resources_path
from dioptas.widgets.plot_widgets.SurfaceWidget import SurfaceWidget
from dioptas.widgets.plot_widgets.utils import auto_level

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')
jcpds_path = os.path.join(unittest_data_path, 'jcpds')


def test_surface_autoscale_button(qapp, qtbot):
    widget = SurfaceWidget()
    qtbot.addWidget(widget)
    histogram = widget.img_histogram_LUT_horizontal
    # Safe before a surface has been loaded.
    QTest.mouseClick(histogram.autoscale_btn, QtCore.Qt.LeftButton)
    data = np.arange(1, 101, dtype=float).reshape(10, 10)
    widget.plot_surface(data, start=0, step=1)
    histogram.setLevels(20, 30)

    QTest.mouseClick(histogram.autoscale_btn, QtCore.Qt.LeftButton)

    assert histogram.getExpLevels() == pytest.approx(auto_level.get_range(data))


class SurfaceView(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.set_stylesheet()
        self.model = DioptasModel()

        self.controller = BatchController(
            widget=self.widget,
            dioptas_model=self.model,
            run_async_integration=False)

        self.phase_controller = PhaseController(self.widget, self.model)

        # Load existing proc+raw data
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        self.model.batch_model.load_proc_data(filename)
        raw_files = self.model.batch_model.files
        raw_files = [os.path.join(os.path.dirname(filename), os.path.basename(f)) for f in raw_files]
        self.model.batch_model.set_image_files(raw_files)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(self.model.batch_model.n_img - 1)

    def set_stylesheet(self):
        with open(os.path.join(resources_path, "style", "stylesheet.qss")) as file:
            stylesheet = file.read()
            self.widget.setStyleSheet(stylesheet)

    def test_surface_widget(self):
        self.widget.batch_widget.show()
        click_button(self.widget.batch_widget.mode_widget.view_3d_btn)
        self.app.processEvents()

    def test_batch_widget_design(self):
        self.widget.batch_widget.raise_widget()
        self.app.processEvents()
