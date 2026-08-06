# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore
from pyqtgraph import GraphicsLayoutWidget
from dioptas.widgets.plot_widgets import PatternWidget
from dioptas.widgets.plot_widgets.ImgWidget import IntegrationImgWidget

from .integration.CustomWidgets import MouseUnitCurrentAndClickedWidget
from .CustomWidgets import CheckableFlatButton, IconActionButton
from .MapLayerWidget import MapLayerWidget
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
        # the window region is put up by MapRoiInPatternController
        self.pattern_plot_widget = PatternWidget(self.pattern_pg_layout)

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
        # Watched on the splitter itself rather than in resizeEvent: while
        # the MapWidget is being resized, its children still have their old
        # geometry, so the width read there is one step behind. getattr
        # because the image's own filter above already fires during
        # construction, before the splitter exists.
        if (
            obj is getattr(self, "vertical_splitter", None)
            and event.type() == QtCore.QEvent.Resize
        ):
            self._update_image_home()
        return super().eventFilter(obj, event)

    def create_layout(self):
        self._outer_layout = TightHBoxLayout()
        self._left_layout = TightVBoxLayout()
        self._right_layout = TightVBoxLayout()
        self._upper_right_layout = TightHBoxLayout()

        self._left_widget = QtWidgets.QWidget()
        self._left_widget.setLayout(self._left_layout)
        self._left_layout.addWidget(self.map_panel_host)

        # The detector image sits beside the control tabs while there is
        # room for both, and moves into the tabs (leftmost) when the panel
        # gets too narrow for the pair — side by side at small widths they
        # squeezed each other until neither was usable.
        self.upper_right_splitter = QtWidgets.QSplitter()
        self.upper_right_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.upper_right_splitter.addWidget(self.img_pg_layout)
        self.upper_right_splitter.addWidget(self.control_widget)
        self.upper_right_splitter.setStretchFactor(0, 1)
        self.upper_right_splitter.setStretchFactor(1, 1)
        self._image_tabbed = False
        #: share of the upper-right width the image had in wide mode, kept
        #: across a stay in the tabs so widening restores the user's split
        self._wide_image_share = 0.5

        self._lower_right_layout = TightVBoxLayout()
        self._lower_right_layout.addWidget(self.pattern_pg_layout)
        self._lower_right_layout.addWidget(self.pattern_footer_widget)
        self.pattern_widget.setLayout(self._lower_right_layout)

        self.vertical_splitter = QtWidgets.QSplitter(self)
        self.vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self.vertical_splitter.addWidget(self.upper_right_splitter)
        self.vertical_splitter.addWidget(self.pattern_widget)
        # the pattern is where the windows are set, so it gets the larger half
        self.vertical_splitter.setStretchFactor(0, 4)
        self.vertical_splitter.setStretchFactor(1, 5)

        self.horizontal_splitter = QtWidgets.QSplitter()
        self.horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.horizontal_splitter.addWidget(self._left_widget)
        self.horizontal_splitter.addWidget(self.vertical_splitter)
        # the map is one panel among four; an even split gave it half the
        # window and squeezed everything driving it
        self.horizontal_splitter.setStretchFactor(0, 2)
        self.horizontal_splitter.setStretchFactor(1, 3)

        self._outer_layout.addWidget(self.horizontal_splitter)

        self.setLayout(self._outer_layout)

        # the upper-right width changes with the window and with the divider
        # against the map panel, so both feed the image-placement decision
        self.horizontal_splitter.splitterMoved.connect(
            lambda *_args: self._update_image_home()
        )
        self.vertical_splitter.installEventFilter(self)
        # The share is remembered when the user drags this divider, not when
        # the image is about to leave: shrinking the window squeezes the
        # image against the controls' minimum first, so the sizes at flip
        # time no longer say anything about the split the user chose.
        self.upper_right_splitter.splitterMoved.connect(
            lambda *_args: self._remember_wide_share()
        )

    def _remember_wide_share(self):
        if self._image_tabbed:
            return
        sizes = self.upper_right_splitter.sizes()
        if len(sizes) == 2 and sizes[0] > 0 and sum(sizes) > 0:
            self._wide_image_share = sizes[0] / sum(sizes)

    # --- where the detector image lives ----------------------------------

    #: narrowest pane the detector image is worth showing in; below the
    #: controls' own minimum plus this, the image moves into the tabs
    _IMAGE_PANE_MIN_WIDTH = 300

    def _image_should_be_tabbed(self, available_width: int) -> bool:
        controls_min = self.control_widget.minimumSizeHint().width()
        return available_width < controls_min + self._IMAGE_PANE_MIN_WIDTH

    def _update_image_home(self):
        self._set_image_tabbed(
            self._image_should_be_tabbed(self.vertical_splitter.width())
        )

    def _set_image_tabbed(self, tabbed: bool):
        """Moves the detector image between its two homes.

        Beside the controls while the panel is wide enough for both; the
        leftmost tab when it is not. The tab the user is on stays put in
        either direction.
        """
        if tabbed == self._image_tabbed:
            return
        self._image_tabbed = tabbed
        tab_widget = self.control_widget.tab_widget
        if tabbed:
            current = tab_widget.currentWidget()
            tab_widget.insertTab(0, self.img_pg_layout, "Image")
            if current is not None:
                tab_widget.setCurrentWidget(current)
        else:
            index = tab_widget.indexOf(self.img_pg_layout)
            if index >= 0:
                tab_widget.removeTab(index)
            self.upper_right_splitter.insertWidget(0, self.img_pg_layout)
            self.upper_right_splitter.setStretchFactor(0, 1)
            self.upper_right_splitter.setStretchFactor(1, 1)
            self.img_pg_layout.show()
            # deferred: at the moment of the flip the surrounding splitters
            # are mid-resize and still report their old width, so a split
            # computed now would be scaled from the wrong total
            QtCore.QTimer.singleShot(0, self._apply_wide_split)

    def _apply_wide_split(self):
        """Gives the re-inserted image a real pane, not its size hint.

        A widget inserted into a splitter arrives at its own hint — for the
        image, a sliver a few pixels wide. The pane is restored to the share
        the image had before it moved into the tabs, floored at the width
        that made side-by-side worthwhile in the first place and capped so
        the controls keep their minimum.
        """
        if self._image_tabbed:
            return  # flipped back before the deferred call ran
        total = self.upper_right_splitter.width()
        controls_min = self.control_widget.minimumSizeHint().width()
        if total <= controls_min:
            return
        image = round(total * self._wide_image_share)
        image = max(self._IMAGE_PANE_MIN_WIDTH, min(image, total - controls_min))
        self.upper_right_splitter.setSizes([image, total - image])

    def showEvent(self, event):
        # decided before the first paint, so the mode opens in the layout
        # its size calls for rather than visibly switching a moment later
        super().showEvent(event)
        self._update_image_home()


class MapControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.load_btn = QtWidgets.QPushButton("Load")
        # one row per grid cell rather than per file, so a blank left by a
        # dropped frame is visible and can be dragged around like any other
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.file_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.file_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.file_list.setToolTip(
            "The map cells in order. Drag to rearrange; right-click to insert a\n"
            "blank for a dropped frame or to leave a bad point out of the map."
        )
        self.reintegrate_cb = QtWidgets.QCheckBox("Reintegrate")
        self.reintegrate_cb.setToolTip(
            "Re-integrate the pattern when selecting a new image.\nApplying all current integration settings to the new pattern."
        )
        self.reintegrate_cb.setChecked(False)
        self.layer_widget = MapLayerWidget()

        # The same actions as the list's context menu. A right-click menu is
        # the only place they lived, which meant nobody found them. Icon-only
        # so the column beside the list stays narrow — the tooltips carry the
        # wording, since a glyph alone says less than a name.
        self.move_up_btn = IconActionButton(
            "map_move_up.svg",
            "Move up\n\n"
            "Moves the selected cell one place earlier in the scan order.\n"
            "Works on blanks as well as on points.",
        )
        self.move_down_btn = IconActionButton(
            "map_move_down.svg",
            "Move down\n\n"
            "Moves the selected cell one place later in the scan order.\n"
            "Works on blanks as well as on points.",
        )

        self.insert_blank_btn = IconActionButton(
            "map_insert_blank.svg",
            "Insert blank cell\n\n"
            "Puts an empty cell before the selected one, for a frame the\n"
            "beamline dropped. Everything after it moves along by one.",
        )
        self.remove_blank_btn = IconActionButton(
            "map_remove_blank.svg",
            "Remove blank cell\n\n"
            "Takes the selected empty cell out again, pulling the later\n"
            "points back. Blanks with nothing after them belong to the grid\n"
            "size — shrink the grid (Grid\u2026 below the map) to drop those.",
        )
        self.exclude_btn = IconActionButton(
            "map_exclude_point.svg",
            "Leave point out of the map\n\n"
            "For a saturated frame or a beam dump. Its cell closes up in\n"
            "the map; its row here stays, struck through, to be put back.",
        )

    def set_point_excluded(self, excluded: bool):
        """Shows whether pressing the button puts the point back or takes it
        out, since the one button does both."""
        self.exclude_btn.set_glyph(
            "map_include_point.svg" if excluded else "map_exclude_point.svg"
        )
        self.exclude_btn.setToolTip(
            "Put the point back into the map"
            if excluded
            else "Leave point out of the map\n\n"
            "For a saturated frame or a beam dump. Its cell closes up in\n"
            "the map; its row here stays, struck through, to be put back."
        )

    @property
    def point_action_buttons(self):
        """The action column, in groups: reorder, then edit the grid.
        None is a spacer."""
        return (
            self.move_up_btn,
            self.move_down_btn,
            None,
            self.insert_blank_btn,
            self.remove_blank_btn,
            self.exclude_btn,
        )

    def create_layout(self):
        self._outer_layout = TightVBoxLayout()
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(5)

        # Two jobs, one narrow column: which points the map is made of, and
        # what each point measures. Sharing the height leaves neither enough,
        # so they get a tab each — the same arrangement the integration
        # controls use.
        self.tab_widget = QtWidgets.QTabWidget()

        self._points_widget = QtWidgets.QWidget()
        self._points_layout = TightVBoxLayout()
        self._points_layout.setContentsMargins(0, 5, 0, 0)
        self._points_layout.setSpacing(5)
        self._points_layout.addWidget(self.load_btn)

        self._list_layout = TightHBoxLayout()
        self._list_layout.setSpacing(5)
        self._list_layout.addWidget(self.file_list)
        self._point_action_layout = TightVBoxLayout()
        # the buttons are small squares with no labels between them, so they
        # need visible air to read as separate controls rather than a strip
        self._point_action_layout.setSpacing(8)
        for button in self.point_action_buttons:
            if button is None:
                self._point_action_layout.addSpacing(16)
            else:
                self._point_action_layout.addWidget(button)
        self._point_action_layout.addStretch(1)
        self._list_layout.addLayout(self._point_action_layout)
        self._points_layout.addLayout(self._list_layout)

        self._points_layout.addWidget(self.reintegrate_cb)
        self._points_widget.setLayout(self._points_layout)

        self.tab_widget.addTab(self._points_widget, "Points")
        self.tab_widget.addTab(self.layer_widget, "Layers")

        self._outer_layout.addWidget(self.tab_widget)
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
