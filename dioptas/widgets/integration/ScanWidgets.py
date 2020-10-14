import os

from qtpy import QtWidgets
from qtpy import QtWidgets, QtCore, QtGui
from pyqtgraph import GraphicsLayoutWidget
from pyqtgraph.opengl import GLViewWidget

from ..plot_widgets.ImgWidget import SurfWidget, IntegrationBatchWidget
from .CustomWidgets import FlatButton, StepFrameWidget, HorizontalSpacerItem
from .CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget
from ..CustomWidgets import LabelAlignRight, FlatButton, CheckableFlatButton, HorizontalSpacerItem, VerticalSpacerItem

from . import CLICKED_COLOR
from ... import icons_path

class ScanWidget(QtWidgets.QWidget):
    """
    Class describe a widget for batch integration
    """

    def __init__(self, parent=None):
        super(ScanWidget, self).__init__(parent)

        self._frame_layout = QtWidgets.QVBoxLayout()
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)

        self.view_mode = 0  # 0 - 2D, 1 - 3D

        # central layout
        self._central_layout = QtWidgets.QHBoxLayout()
        self._central_layout.setSpacing(0)

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_view = IntegrationBatchWidget(self.img_pg_layout, orientation='horizontal')
        self._central_layout.addWidget(self.img_pg_layout)

        self.surf_pg_layout = GLViewWidget()
        self.surf_view = SurfWidget(self.surf_pg_layout, orientation='horizontal')
        self._central_layout.addWidget(self.surf_pg_layout)
        self.surf_pg_layout.hide()

        # Right control
        self.right_control_widget = QtWidgets.QWidget()
        self.right_control_widget.setObjectName('pattern_right_control_widget')
        self.right_control_widget.setMaximumWidth(22)
        self.right_control_widget.setMinimumWidth(22)
        self._right_control_layout = QtWidgets.QVBoxLayout()
        self._right_control_layout.setContentsMargins(0, 0, 0, 6)
        self._right_control_layout.setSpacing(4)

        self.tth_btn = CheckableFlatButton(u"2θ")
        self.q_btn = CheckableFlatButton('Q')
        self.d_btn = CheckableFlatButton('d')
        self.unit_btn_group = QtWidgets.QButtonGroup()
        self.unit_btn_group.addButton(self.tth_btn)
        self.unit_btn_group.addButton(self.q_btn)
        self.unit_btn_group.addButton(self.d_btn)
        self.background_btn = CheckableFlatButton('bg')
        self.background_inspect_btn = CheckableFlatButton('I')
        self.antialias_btn = CheckableFlatButton('AA')
        self.auto_range_btn = CheckableFlatButton('A')

        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.tth_btn)
        self._right_control_layout.addWidget(self.q_btn)
        self._right_control_layout.addWidget(self.d_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.background_btn)
        self.right_control_widget.setLayout(self._right_control_layout)

        self._central_layout.addWidget(self.right_control_widget)
        self._frame_layout.addLayout(self._central_layout)

        # Bottom control layout
        self.bottom_control_widget = QtWidgets.QWidget()
        self.bottom_control_widget.setObjectName('pattern_bottom_control_widget')

        self.load_btn = FlatButton()
        self.load_btn.setToolTip("Load raw/proc data")
        self.load_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'open.ico')))
        self.load_btn.setIconSize(QtCore.QSize(13, 13))
        self.load_btn.setMinimumHeight(25)
        self.load_btn.setMaximumHeight(25)
        self.load_btn.setMinimumWidth(25)
        self.load_btn.setMaximumWidth(25)

        self.integrate_btn = FlatButton("Integrate")
        self.load_proc_btn = FlatButton("Load proc data")

        self.save_btn = FlatButton()
        self.save_btn.setToolTip("Save data")
        self.save_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'save.ico')))
        self.save_btn.setIconSize(QtCore.QSize(13, 13))
        self.save_btn.setMaximumWidth(25)

        self.change_view_btn = FlatButton("3D")
        self.change_view_btn.setToolTip("Change view to 3D")

        self.change_scale_btn = CheckableFlatButton("log")
        self.change_scale_btn.setToolTip("Change scale to log")

        self.waterfall_btn = CheckableFlatButton("Waterfall")
        self.waterfall_btn.setToolTip("Create waterfall plot")

        self.phases_btn = CheckableFlatButton('Show Phases')

        self.bottom_control_layout = QtWidgets.QHBoxLayout()
        self.bottom_control_layout.addWidget(self.load_btn)
        self.bottom_control_layout.addWidget(self.save_btn)

        self.bottom_control_layout.addWidget(self.integrate_btn)
        self.bottom_control_layout.addWidget(self.waterfall_btn)
        self.bottom_control_layout.addWidget(self.phases_btn)

        self.bottom_control_layout.addSpacerItem(HorizontalSpacerItem())
        self.bottom_control_layout.addWidget(self.change_view_btn)
        self.bottom_control_layout.addWidget(self.change_scale_btn)
        self.bottom_control_layout.addSpacerItem(HorizontalSpacerItem())

        self.bottom_control_widget.setLayout(self.bottom_control_layout)

        self._frame_layout.addWidget(self.bottom_control_widget)

        # Sliding and positioning
        self._positioning_layout = QtWidgets.QHBoxLayout()
        self._positioning_layout.setSpacing(0)

        self.step_series_widget = StepFrameWidget()
        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)

        self._positioning_layout.addWidget(self.step_series_widget)
        self._positioning_layout.addSpacerItem(HorizontalSpacerItem())
        self._positioning_layout.addWidget(self.mouse_pos_widget)

        self._frame_layout.addLayout(self._positioning_layout)

        self.setLayout(self._frame_layout)
        self.setWindowFlags(QtCore.Qt.Tool)

        self.right_control_widget.setStyleSheet("""
                    #pattern_frame, #pattern_right_control_widget, QLabel {
                        background: black;
                        color: yellow;
                    }
                    #pattern_right_control_widget QPushButton{
                        padding: 0px;
        	            padding-right: 1px;
        	            border-radius: 3px;
                    }
        	    """)

        self.bottom_control_widget.setStyleSheet("""
                    #pattern_bottom_control_widget QPushButton{
                        padding: 0px;
        	            padding-right: 1px;
        	            border-radius: 3px;
                    }
                    #pattern_frame, #pattern_bottom_control_widget, QLabel {
                        background: black;
                        color: yellow;
                    }
        	    """)

    def raise_widget(self):
        print("show something")
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()
