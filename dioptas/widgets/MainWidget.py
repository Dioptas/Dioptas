# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore

from .ConfigurationWidget import ConfigurationWidget
from .CalibrationWidget import CalibrationWidget
from .MaskWidget import MaskWidget
from .integration import IntegrationWidget
from .MapWidget import MapWidget
from .MapPanelWidget import MapPanelWindow
from .CustomWidgets import (
    VerticalSpacerItem,
    CheckableFlatButton,
    FlatButton,
    VerticalLine,
    HorizontalLine,
    render_icon,
)


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._create_layouts()

        self.setLayout(self._outer_layout)

        self._create_menu()
        self._create_mode_menu()
        self._create_history_menu()

        self._left_layout.addLayout(self._menu_layout)
        # undo/redo sit with the other application-wide actions at the top,
        # above the mode buttons — they act on the whole session, not on
        # whichever mode happens to be showing
        self._left_layout.addLayout(self._history_layout)
        self._left_layout.addLayout(self._mode_layout)
        self._left_layout.addLayout(self._external_actions_layout)

        self._outer_layout.addLayout(self._left_layout)
        self._outer_layout.addWidget(VerticalLine())
        self._outer_layout.addLayout(self._content_layout)

        self.configuration_widget = ConfigurationWidget(self)
        self.configuration_widget.setVisible(False)
        self._content_layout.addWidget(self.configuration_widget)

        self._create_main_frame()

        self._style_layouts()
        self.style_widgets()
        self.add_menu_popup()
        self.add_tooltips()

        self._content_layout.addWidget(self.main_frame)

    def _style_layouts(self):
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setStretchFactor(self._left_layout, 0)
        self._outer_layout.setStretchFactor(self._content_layout, 100)
        self._outer_layout.setSpacing(0)
        self._mode_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_layout.setSpacing(0)
        self._content_layout.setSpacing(0)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setSpacing(6)
        self._external_actions_layout.setContentsMargins(6, 6, 6, 6)
        self._external_actions_layout.setSpacing(6)

    def _create_layouts(self):
        self._outer_layout = QtWidgets.QHBoxLayout()
        self._left_layout = QtWidgets.QVBoxLayout()
        self._external_actions_layout = QtWidgets.QVBoxLayout()
        self._content_layout = QtWidgets.QVBoxLayout()
        self._mode_layout = QtWidgets.QVBoxLayout()
        self._history_layout = QtWidgets.QVBoxLayout()

    def _create_mode_menu(self):
        self.mode_btn_group = QtWidgets.QButtonGroup()
        self.calibration_mode_btn = CheckableFlatButton("CALIB", self)
        self.calibration_mode_btn.setObjectName("calibration_mode_btn")
        self.calibration_mode_btn.setChecked(True)
        self.mask_mode_btn = CheckableFlatButton("MASK", self)
        self.mask_mode_btn.setObjectName("mask_mode_btn")
        self.integration_mode_btn = CheckableFlatButton("INT", self)
        self.integration_mode_btn.setObjectName("integration_mode_btn")
        self.map_mode_btn = CheckableFlatButton("MAP", self)
        self.map_mode_btn.setObjectName("map_mode_btn")

        self.mode_btn_group.addButton(self.calibration_mode_btn)
        self.mode_btn_group.addButton(self.mask_mode_btn)
        self.mode_btn_group.addButton(self.integration_mode_btn)
        self.mode_btn_group.addButton(self.map_mode_btn)

        # leads the mode block, so it sits flush against the first mode
        # button instead of being separated from it by the sidebar spacing
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.calibration_mode_btn)
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.mask_mode_btn)
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.integration_mode_btn)
        self._mode_layout.addWidget(HorizontalLine())
        self._mode_layout.addWidget(self.map_mode_btn)
        self._mode_layout.addSpacerItem(VerticalSpacerItem())

    def _create_menu(self):
        self.menu_btn = QtWidgets.QPushButton("...")
        self.menu_btn.setObjectName("menu_btn")

        self.show_configuration_menu_btn = CheckableFlatButton("C")

        self._menu_layout = QtWidgets.QHBoxLayout()
        self._menu_layout.setContentsMargins(6, 6, 3, 0)
        self._menu_layout.setSpacing(12)

        self._menu_layout.addWidget(self.menu_btn)
        self._menu_layout.addWidget(self.show_configuration_menu_btn)

        self.save_btn = FlatButton("Save Project")
        self.load_btn = FlatButton("Open Project")
        self.reset_btn = FlatButton("Reset Project")

    def _create_history_menu(self):
        """Undo/redo near the top of the sidebar.

        The history is application-wide, so the controls belong with the
        other global actions rather than inside any one mode — the mask had
        the only visible pair before, which left undo undiscoverable
        everywhere else.
        """
        # icons rather than labels: undo/redo are universally recognised
        # symbols, and SVG keeps them crisp at any scale without depending on
        # a font shipping the glyphs
        # Two icons per button, swapped by set_history_enabled: with a
        # stylesheet applied Qt draws through QStyleSheetStyle, which ignores
        # an icon's disabled mode, so the fade has to be applied by hand.
        self._undo_icons = (render_icon("undo.svg"), render_icon("undo.svg", 0.35))
        self._redo_icons = (render_icon("redo.svg"), render_icon("redo.svg", 0.35))

        self.undo_btn = FlatButton(self)
        self.undo_btn.setObjectName("undo_btn")
        self.redo_btn = FlatButton(self)
        self.redo_btn.setObjectName("redo_btn")
        self.set_history_enabled(False, False)

        # side by side, the conventional arrangement for the pair, centred
        # in the column rather than filling it — they are small actions
        self._history_btn_layout = QtWidgets.QHBoxLayout()
        self._history_btn_layout.setContentsMargins(0, 0, 0, 0)
        self._history_btn_layout.setSpacing(2)
        self._history_btn_layout.addStretch()
        self._history_btn_layout.addWidget(self.undo_btn)
        self._history_btn_layout.addWidget(self.redo_btn)
        self._history_btn_layout.addStretch()

        self._history_layout.setContentsMargins(0, 2, 0, 2)
        self._history_layout.setSpacing(0)
        self._history_layout.addLayout(self._history_btn_layout)

    def set_history_enabled(self, can_undo, can_redo):
        """Enables the history buttons and picks the matching icon.

        The greyed-out icon is the whole disabled cue: the buttons carry no
        background of their own (see qt_material.css), so an unavailable one
        simply fades rather than gaining a highlight.
        """
        for button, icons, enabled in (
            (self.undo_btn, self._undo_icons, can_undo),
            (self.redo_btn, self._redo_icons, can_redo),
        ):
            button.setEnabled(enabled)
            button.setIcon(icons[0] if enabled else icons[1])

    def _create_main_frame(self):
        self.main_frame = QtWidgets.QWidget(self)
        self._layout_main_frame = QtWidgets.QVBoxLayout()
        self._layout_main_frame.setContentsMargins(0, 2, 6, 6)
        self._layout_main_frame.setSpacing(0)
        self.main_frame.setLayout(self._layout_main_frame)

        self.calibration_widget = CalibrationWidget(self)
        self.mask_widget = MaskWidget(self)
        self.integration_widget = IntegrationWidget(self)
        self.map_widget = MapWidget(self)
        # home for the map panel while it is undocked; parented so it is torn
        # down with the main window, but shown as its own window
        self.map_panel_window = MapPanelWindow(self)

        self._layout_main_frame.addWidget(self.calibration_widget)
        self._layout_main_frame.addWidget(self.mask_widget)
        self._layout_main_frame.addWidget(self.integration_widget)
        self._layout_main_frame.addWidget(self.map_widget)

        self.mask_widget.setVisible(False)
        self.integration_widget.setVisible(False)
        self.map_widget.setVisible(False)

        self._content_layout.addWidget(self.main_frame)
        self._content_layout.setStretchFactor(self.main_frame, 100)

        self.style_widgets()
        self.add_tooltips()

    def style_widgets(self):
        self._style_mode_btns()
        self._style_menu_btn()
        self._style_history_btns()

        button_height = 24
        button_width = 24
        adjust_height_btns = [
            self.show_configuration_menu_btn,
        ]
        for btn in adjust_height_btns:
            btn.setHeight(button_height)
            btn.setWidth(button_width)

        self.configuration_widget.setMaximumHeight(28)

    def _style_menu_btn(self):
        self.menu_btn.setFixedWidth(30)
        self.menu_btn.setFixedHeight(30)

    def _style_history_btns(self):
        # small: these are quick actions sitting above the mode buttons, not
        # modes themselves
        for btn in (self.undo_btn, self.redo_btn):
            btn.setWidth(26)
            btn.setHeight(22)
            btn.setIconSize(QtCore.QSize(14, 14))

    def _style_mode_btns(self):
        mode_btn_width = 75
        mode_btn_height = 75
        mode_btns = [
            self.calibration_mode_btn,
            self.mask_mode_btn,
            self.integration_mode_btn,
            self.map_mode_btn,
        ]
        for btn in mode_btns:
            # btn.setCheckable(True)
            btn.setFixedWidth(mode_btn_width)
            btn.setFixedHeight(mode_btn_height)

    def add_menu_popup(self):
        self.menu_btn.clicked.connect(self.show_menu_popup)

    def show_menu_popup(self):
        widget = MenuPopup(self, [self.load_btn, self.save_btn, self.reset_btn])
        btn = self.menu_btn
        widget.adjustSize()
        position = self.mapToGlobal(QtCore.QPoint(btn.x() + btn.width() + 3, btn.y()))
        widget.move(position)
        widget.show()

    def add_tooltips(self):
        self.menu_btn.setToolTip("Project Menu")
        self.show_configuration_menu_btn.setToolTip("Show Configurations")
        self.calibration_mode_btn.setToolTip("Calibration Mode")
        self.mask_mode_btn.setToolTip("Mask Mode")
        self.integration_mode_btn.setToolTip("Integration Mode")

    def create_external_actions(self, quick_actions):
        self.external_action_btns = {}
        for action in quick_actions:
            btn = QtWidgets.QPushButton(action['name'])
            self.external_action_btns[action['name']] = btn
            self._external_actions_layout.addWidget(btn)


class MenuPopup(QtWidgets.QFrame):
    def __init__(self, parent=None, menu_items=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.setLineWidth(1)
        self.setMidLineWidth(0)
        self.setObjectName("MenuPopup")
        self.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setWindowOpacity(0.9)
        self.setFixedWidth(150)
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setLayout(self._layout)

        self.create_menu(menu_items)

    def create_menu(self, menu_items):
        for item in menu_items:
            self._layout.addWidget(item)
