from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pq
from pyqtgraph import GraphicsLayoutWidget
from pyqtgraph.opengl import GLViewWidget
import os
import numpy as np

from ..plot_widgets.ImgWidget import SurfWidget, IntegrationBatchWidget
from .CustomWidgets import FlatButton, StepFrameWidget, HorizontalSpacerItem
from .CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget

from . import CLICKED_COLOR


class ScanWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(ScanWidget, self).__init__(parent)

        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName('ScanFrame')
        self.frame.setWindowTitle("Scan")

        self._frame_layout = QtWidgets.QVBoxLayout()
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)

        self.view_mode = 0  # 0 - 2D, 1 - 3D

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_view = IntegrationBatchWidget(self.img_pg_layout, orientation='horizontal')
        self._frame_layout.addWidget(self.img_pg_layout)

        self.surf_pg_layout = GLViewWidget()
        self.surf_view = SurfWidget(self.surf_pg_layout, orientation='horizontal')
        self._frame_layout.addWidget(self.surf_pg_layout)
        self.surf_pg_layout.hide()

        self.step_series_widget = StepFrameWidget()
        self._frame_layout.addWidget(self.step_series_widget)

        # Position and unit layout
        self.position_and_unit_widget = QtWidgets.QWidget()
        self.position_and_unit_widget.setObjectName('img_position_and_unit_widget')
        self._position_and_unit_layout = QtWidgets.QHBoxLayout()
        self._position_and_unit_layout.setContentsMargins(0, 0, 0, 0)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)
        #self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget(CLICKED_COLOR)

        self._position_and_unit_layout.addWidget(self.mouse_pos_widget)
        #self._position_and_unit_layout.addSpacerItem(HorizontalSpacerItem())
        #self._position_and_unit_layout.addWidget(self.mouse_unit_widget)

        self.position_and_unit_widget.setLayout(self._position_and_unit_layout)
        self._frame_layout.addWidget(self.position_and_unit_widget)


        self.load_files_btn = FlatButton("Load Files")
        self.integrate_btn = FlatButton("Integrate")
        self.load_proc_btn = FlatButton("Load proc data")
        self.save_btn = FlatButton("Save proc data")
        self.change_view_btn = FlatButton("Show in 3D")

        self.main_control_layout = QtWidgets.QVBoxLayout()
        self.main_control_layout.addWidget(self.load_files_btn)
        self.main_control_layout.addWidget(self.integrate_btn)
        self.main_control_layout.addWidget(self.load_proc_btn)
        self.main_control_layout.addWidget(self.save_btn)
        self.main_control_layout.addWidget(self.change_view_btn)

        self._frame_layout.addLayout(self.main_control_layout)

        self.frame.setLayout(self._frame_layout)



    def show(self):
        img_frame_size = QtCore.QSize(400, 500)
        img_frame_position = QtCore.QPoint(0, 0)

        self.frame.resize(img_frame_size)
        self.frame.move(img_frame_position)

        self.frame.show()
