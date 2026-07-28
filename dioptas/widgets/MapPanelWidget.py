# SPDX-License-Identifier: MIT

"""The map display panel.

Self-contained view of the spatial intensity map: the map plot itself, its
smoothing/contour bar and the control strip below it. It is deliberately
independent of the surrounding mode so the same instance can live in the map
mode, in the integration view's map tab, or in its own floating window.
"""

from qtpy import QtWidgets, QtCore
from pyqtgraph import GraphicsLayoutWidget

from .plot_widgets.ImgWidget import IntegrationImgWidget
from .CustomWidgets import (
    SaveIconButton,
    CheckableFlatButton,
    FlatButton,
    HorizontalSpacerItem,
    CleanLooksComboBox,
)


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


class MapPanelWidget(QtWidgets.QWidget):
    """Map plot with its display controls, usable in any of the map homes."""

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
        self.map_plot_control_widget = MapPlotControlWidget()

    def create_layout(self):
        self._outer_layout = TightVBoxLayout()
        self._outer_layout.addWidget(self.map_image_frame)
        self._outer_layout.addWidget(self.map_plot_control_widget)
        self.setLayout(self._outer_layout)


class MapPanelHost(QtWidgets.QWidget):
    """Slot a :class:`MapPanelWidget` can be placed into.

    The panel is shared between the map mode, the integration view and its
    own window, so each of its homes keeps an (initially empty) slot rather
    than owning a panel of its own.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._panel = None
        self._layout = TightVBoxLayout()
        self.setLayout(self._layout)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

    def minimumSizeHint(self):
        # the map plot has no content-derived height; without a hint the tab
        # machinery collapses it to almost nothing
        return QtCore.QSize(280, 280)

    @property
    def panel(self) -> "MapPanelWidget | None":
        return self._panel

    def take_panel(self, panel: "MapPanelWidget"):
        """Moves *panel* into this slot, removing it from its previous home."""
        if self._panel is panel:
            return
        self._layout.addWidget(panel)
        self._panel = panel
        panel.show()

    def release_panel(self) -> "MapPanelWidget | None":
        """Removes the panel from this slot and returns it."""
        panel = self._panel
        if panel is not None:
            self._layout.removeWidget(panel)
            self._panel = None
        return panel


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


class MapPlotControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.load_btn = FlatButton("Load")
        self.load_btn.setToolTip("Integrate image files into a new map")
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
        self._outer_layout.addWidget(self.load_btn)
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
