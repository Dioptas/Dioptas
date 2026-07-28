# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore
from pyqtgraph import GraphicsLayoutWidget
from dioptas.widgets.plot_widgets import PatternWidget
from dioptas.widgets.plot_widgets.ImgWidget import IntegrationImgWidget

from .integration.CustomWidgets import MouseUnitCurrentAndClickedWidget
from .CustomWidgets import CheckableFlatButton
from .MapPanelWidget import (
    MapPanelHost,
    MapPanelWidget,
    TightHBoxLayout,
    TightVBoxLayout,
)


class MapWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the Map widget, which is separated into several Parts
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()

    def create_widgets(self):
        self.map_panel_widget = MapPanelWidget()
        self.map_panel_host = MapPanelHost()
        self.map_panel_host.take_panel(self.map_panel_widget)

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

        self.pattern_pg_layout = GraphicsLayoutWidget()
        self.pattern_plot_widget = PatternWidget(self.pattern_pg_layout)
        self.pattern_plot_widget.show_map_interactive_roi()

        self.pattern_footer_widget = PatternFooterWidget()
        self.pattern_widget = QtWidgets.QWidget()

        self.control_widget = MapControlWidget()

    # Convenience access to the widgets of the shared map panel. The panel is
    # only borrowed by this widget — it may be reparented into the integration
    # view or a floating window — so these are read through properties.

    @property
    def map_pg_layout(self):
        return self.map_panel_widget.map_pg_layout

    @property
    def map_plot_widget(self):
        return self.map_panel_widget.map_plot_widget

    @property
    def map_image_frame(self):
        return self.map_panel_widget.map_image_frame

    @property
    def map_plot_control_widget(self):
        return self.map_panel_widget.map_plot_control_widget

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
        self._left_layout.addWidget(self.map_panel_host)

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
