# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore
from pyqtgraph import GraphicsLayoutWidget
from dioptas.widgets.plot_widgets import PatternWidget
from dioptas.widgets.plot_widgets.ImgWidget import IntegrationImgWidget

from .integration.CustomWidgets import MouseUnitCurrentAndClickedWidget
from .CustomWidgets import SaveIconButton, CheckableFlatButton, HorizontalSpacerItem, CleanLooksComboBox


class MapWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the Map widget, which is separated into several Parts
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()

    def create_widgets(self):
        self.map_pg_layout = GraphicsLayoutWidget()
        self.map_plot_widget = IntegrationImgWidget(
            self.map_pg_layout, orientation="horizontal"
        )
        self.map_image_frame = MapImageFrame(self.map_pg_layout)

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_plot_widget = IntegrationImgWidget(
            self.img_pg_layout, orientation="horizontal", padding=0
        )
        self.img_autoscale_btn = CheckableFlatButton("A", self.img_pg_layout)
        self.img_autoscale_btn.setChecked(True)
        self.img_autoscale_btn.setToolTip("Auto-scale image intensity")
        self.img_autoscale_btn.setFixedSize(22, 22)
        self.img_autoscale_btn.raise_()
        self.img_pg_layout.installEventFilter(self)

        self.map_plot_control_widget = (
            MapPlotControlWidget()
        )  # widget below the map image

        self.pattern_pg_layout = GraphicsLayoutWidget()
        self.pattern_plot_widget = PatternWidget(self.pattern_pg_layout)
        self.pattern_plot_widget.show_map_interactive_roi()

        self.pattern_footer_widget = PatternFooterWidget()
        self.pattern_widget = QtWidgets.QWidget()

        self.control_widget = MapControlWidget()

    def eventFilter(self, obj, event):
        if obj is self.img_pg_layout and event.type() == QtCore.QEvent.Resize:
            self.img_autoscale_btn.move(
                self.img_pg_layout.width() - self.img_autoscale_btn.width() - 5,
                self.img_pg_layout.height() - self.img_autoscale_btn.height() - 5,
            )
        return super().eventFilter(obj, event)

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()
        self._left_layout = TightVBoxLayout()
        self._right_layout = TightVBoxLayout()
        self._upper_right_layout = TightHBoxLayout()

        self._left_widget = QtWidgets.QWidget()
        self._left_widget.setLayout(self._left_layout)
        self._left_layout.addWidget(self.map_image_frame)
        self._left_layout.addWidget(self.map_plot_control_widget)

        self.upper_right_splitter = QtWidgets.QSplitter()
        self.upper_right_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.upper_right_splitter.addWidget(self.img_pg_layout)
        self.upper_right_splitter.addWidget(self.control_widget)

        self._lower_right_layout = TightVBoxLayout()
        self._lower_right_layout.addWidget(self.pattern_pg_layout)
        self._lower_right_layout.addWidget(self.pattern_footer_widget)
        self.pattern_widget.setLayout(self._lower_right_layout)

        self.vertical_splitter = QtWidgets.QSplitter(self)
        self.vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter.addWidget(self.upper_right_splitter)
        self.vertical_splitter.addWidget(self.pattern_widget)

        self.horizontal_splitter = QtWidgets.QSplitter()
        self.horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.horizontal_splitter.addWidget(self._left_widget)
        self.horizontal_splitter.addWidget(self.vertical_splitter)

        self._outer_layout.addWidget(self.horizontal_splitter)

        self.setLayout(self._outer_layout)


class TightHBoxLayout(QtWidgets.QHBoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)


class TightVBoxLayout(QtWidgets.QVBoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)


class MapImageFrame(QtWidgets.QWidget):
    """Frame wrapping the map plot with a black control bar matching integration widget style."""

    def __init__(self, map_pg_layout: GraphicsLayoutWidget, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.frame = QtWidgets.QWidget()
        self.frame.setObjectName('map_image_frame')

        self.map_pg_layout = map_pg_layout

        self.smooth_btn = CheckableFlatButton("Smooth")
        self.smooth_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.smooth_slider.setRange(2, 10)
        self.smooth_slider.setValue(5)
        self.smooth_slider.setMaximumWidth(160)
        self.smooth_slider.setVisible(False)
        self.smooth_label = QtWidgets.QLabel("5")
        self.smooth_label.setFixedWidth(20)
        self.smooth_label.setVisible(False)

        self.contour_btn = CheckableFlatButton("Contours")
        self.contour_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.contour_slider.setRange(3, 20)
        self.contour_slider.setValue(5)
        self.contour_slider.setMaximumWidth(160)
        self.contour_slider.setVisible(False)
        self.contour_label = QtWidgets.QLabel("5")
        self.contour_label.setFixedWidth(20)
        self.contour_label.setVisible(False)

        self._control_layout = QtWidgets.QHBoxLayout()
        self._control_layout.setContentsMargins(6, 2, 6, 2)
        self._control_layout.setSpacing(6)
        self._control_layout.addWidget(self.smooth_btn)
        self._control_layout.addWidget(self.smooth_slider)
        self._control_layout.addWidget(self.smooth_label)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._control_layout.addWidget(self.contour_label)
        self._control_layout.addWidget(self.contour_slider)
        self._control_layout.addWidget(self.contour_btn)

        self._frame_layout = QtWidgets.QVBoxLayout()
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)
        self._frame_layout.addWidget(self.map_pg_layout)
        self._frame_layout.addLayout(self._control_layout)
        self.frame.setLayout(self._frame_layout)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.frame)
        self.setLayout(self._layout)

        self.setStyleSheet("""
            #map_image_frame {
                background: black;
            }
            #map_image_frame QPushButton {
                padding-top: 2px;
                padding-bottom: 2px;
                padding-left: 5px;
                padding-right: 5px;
            }
            #map_image_frame QSlider {
                background: transparent;
            }
            #map_image_frame QLabel {
                background: transparent;
            }
        """)


class MapControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.load_btn = QtWidgets.QPushButton("Load")
        self.file_list = QtWidgets.QListWidget()
        self.reintegrate_cb = QtWidgets.QCheckBox("Reintegrate")
        self.reintegrate_cb.setToolTip(
            "Re-integrate the pattern when selecting a new image.\nApplying all current integration settings to the new pattern."
        )
        self.reintegrate_cb.setChecked(False)

    def create_layout(self):
        self._outer_layout = TightVBoxLayout()
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(5)

        self._outer_layout.addWidget(self.load_btn)
        self._outer_layout.addWidget(self.file_list)
        self._outer_layout.addWidget(self.reintegrate_cb)

        self.setLayout(self._outer_layout)

    def style_widgets(self):
        pass


class MapPlotControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.save_map_btn = SaveIconButton()
        self.map_dimension_cb = CleanLooksComboBox()
        self.map_dimension_cb.setMinimumWidth(80)
        self.mouse_x_label = QtWidgets.QLabel("X: ")
        self.mouse_y_label = QtWidgets.QLabel("Y: ")
        self.mouse_int_label = QtWidgets.QLabel("I: ")
        self.filename_label = QtWidgets.QLabel("")

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()

        self._left_layout = TightVBoxLayout()
        self._mouse_pos_layout = TightHBoxLayout()
        self._mouse_pos_layout.addWidget(self.mouse_x_label)
        self._mouse_pos_layout.addWidget(self.mouse_y_label)
        self._mouse_pos_layout.addWidget(self.mouse_int_label)
        self._left_layout.addLayout(self._mouse_pos_layout)
        self._left_layout.addWidget(self.filename_label)
        self._outer_layout.addWidget(self.save_map_btn)
        self._outer_layout.addWidget(QtWidgets.QLabel("Dim: "))
        self._outer_layout.addWidget(self.map_dimension_cb)
        self._outer_layout.addStretch(1)
        self._outer_layout.addLayout(self._left_layout)
        self.setLayout(self._outer_layout)

    def style_widgets(self):
        self._outer_layout.setContentsMargins(6, 3, 0, 0)
        self.mouse_x_label.setFixedWidth(50)
        self.mouse_y_label.setFixedWidth(50)
        self.mouse_int_label.setMinimumWidth(80)
        self.setMinimumHeight(30)


class PatternFooterWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget()
        self.log_btn = CheckableFlatButton('Log')
        self.sqrt_btn = CheckableFlatButton(u'\u221a')

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()
        self._outer_layout.addWidget(self.mouse_unit_widget)
        self._outer_layout.addStretch(1)
        self._outer_layout.addWidget(self.log_btn)
        self._outer_layout.addWidget(self.sqrt_btn)
        self.setLayout(self._outer_layout)

    def style_widgets(self):
        self._outer_layout.setContentsMargins(6, 3, 6, 0)
        self.setMinimumHeight(30)
