# SPDX-License-Identifier: MIT
import os
from qtpy import QtCore, QtWidgets, QtGui
from math import floor, log10

from .. import icons_path


class NumberTextField(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def text(self):
        return super().text().replace(",", ".")

    def value(self):
        return float(self.text())


class IntegerTextField(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setValidator(QtGui.QIntValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelAlignRight(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelExpandable(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet(
            """
            color: #F1F1F1;
            background: #3C3C3C;
        """
        )
        self.setReadOnly(True)


class SpinBoxAlignRight(QtWidgets.QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)


class DoubleSpinBoxAlignRight(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.setDecimals(10)

    def textFromValue(self, value):
        if value == 0:
            return "0"
        return f"{value:g}"


class DoubleMultiplySpinBoxAlignRight(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.setDecimals(10)

    def stepBy(self, p_int):
        self.setValue(self.calc_new_step(self.value(), p_int))

    def textFromValue(self, value):
        if value == 0:
            return "0"
        return f"{value:g}"

    def calc_new_step(self, value, p_int):
        pow10floor = 10 ** floor(log10(value))
        if p_int > 0:
            if value / pow10floor < 1.9:
                return pow10floor * 2.0
            elif value / pow10floor < 4.9:
                return pow10floor * 5.0
            else:
                return pow10floor * 10.0
        else:
            if value / pow10floor < 1.1:
                return pow10floor / 2.0
            elif value / pow10floor < 2.1:
                return pow10floor
            elif value / pow10floor < 5.1:
                return pow10floor * 2.0
            else:
                return pow10floor * 5.0


class ConservativeSpinBox(QtWidgets.QSpinBox):
    """
    This is a modification of the QSpinBox class. The ConservativeSpinbox does not emit the valueChanged signal for
    every keypress in the lineedit. The signal is only emitted for the following occasions:
      - pressing enter
      - the spinbox loses focus
      - pressing the up or down arrows
    Also the wheel events are disabled.

    This Spinbox is intended for usage with applications were the change in the spinbox value causes long calculations
    and does a valueChanged signal on every keypress results in a strange behavior.
    """

    valueChanged = QtCore.Signal()

    def __init__(self):
        super().__init__()

        self.lineEdit().editingFinished.connect(self.valueChanged)
        self.lineEdit().setAlignment(QtCore.Qt.AlignRight)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        opt = QtWidgets.QStyleOptionSpinBox()
        self.initStyleOption(opt)

        if (
            self.style()
            .subControlRect(
                QtWidgets.QStyle.CC_SpinBox, opt, QtWidgets.QStyle.SC_SpinBoxUp
            )
            .contains(e.pos())
        ):
            self.setValue(self.value() + 1)
            self.valueChanged.emit()
        elif (
            self.style()
            .subControlRect(
                QtWidgets.QStyle.CC_SpinBox, opt, QtWidgets.QStyle.SC_SpinBoxDown
            )
            .contains(e.pos())
        ):
            self.setValue(self.value() - 1)
            self.valueChanged.emit()

    def wheelEvent(self, e: QtGui.QWheelEvent):
        pass


class FlatButton(QtWidgets.QPushButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setFlat(True)

    def setHeight(self, height):
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def setWidth(self, width):
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)


class CheckableButton(QtWidgets.QPushButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setCheckable(True)


class CheckableFlatButton(FlatButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setCheckable(True)


class DarkCheckableFlatButton(QtWidgets.QPushButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setObjectName("dark_checkable_flat_btn")
        self.setCheckable(True)
        self.setFlat(True)

    def setHeight(self, height):
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def setWidth(self, width):
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)


class RotatedCheckableFlatButton(CheckableFlatButton):
    def __init__(self, *args):
        super().__init__(*args)

    def paintEvent(self, event):
        painter = QtWidgets.QStylePainter(self)
        painter.rotate(270)
        painter.translate(-1 * self.height(), 0)
        painter.drawControl(QtWidgets.QStyle.CE_PushButton, self.getSyleOptions())

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        size.transpose()
        return size

    def sizeHint(self):
        size = super().sizeHint()
        size.transpose()
        return size

    def getSyleOptions(self):
        options = QtWidgets.QStyleOptionButton()
        options.initFrom(self)
        size = options.rect.size()
        size.transpose()
        options.rect.setSize(size)
        if self.isFlat():
            options.features |= QtWidgets.QStyleOptionButton.Flat
        if self.menu():
            options.features |= QtWidgets.QStyleOptionButton.HasMenu
        if self.autoDefault() or self.isDefault():
            options.features |= QtWidgets.QStyleOptionButton.AutoDefaultButton
        if self.isDefault():
            options.features |= QtWidgets.QStyleOptionButton.DefaultButton
        if self.isDown() or (self.menu() and self.menu().isVisible()):
            options.state |= QtWidgets.QStyle.State_Sunken
        if self.isChecked():
            options.state |= QtWidgets.QStyle.State_On
        if not self.isFlat() and not self.isDown():
            options.state |= QtWidgets.QStyle.State_Raised

        options.text = self.text()
        options.icon = self.icon()
        options.iconSize = self.iconSize()
        return options


#: text color of the theme's flat buttons
ACCENT_COLOR = "#ff9500"

#: icon buttons sitting among the flat text buttons of a plot header (e.g.
#: save). A cool steel blue: deliberately outside the orange accent's hue
#: family, so an icon-only utility reads as a different kind of control
#: than the labelled actions next to it instead of competing with them.
PLOT_ICON_COLOR = "#8fa3b8"

#: display size of those icons, matched to the cap height of the flat text
#: buttons beside them so the row reads as one line of controls
PLOT_ICON_SIZE = 18

#: reserved for controls that discard user work in one click (clear all
#: phases/overlays). Semantic, not decorative — do not use it to make an
#: ordinary button stand out.
DANGER_COLOR = "#e0554d"


def set_icon_button_hover_color(button, color):
    """Gives an icon-only button a hover border in the icon's own colour.

    The theme's global rule borders every hovered button in the orange
    accent, which contradicts a deliberately non-orange icon (the steel
    save glyph, the red clear-all). Set per instance because the colour
    lives in Python, so the two cannot drift apart.
    """
    button.setStyleSheet(
        "QPushButton:hover {{ border: 1px solid {0}; }}"
        "QPushButton:flat:hover {{ border: 1px solid {0}; }}".format(color)
    )


class SaveIconButton(FlatButton):
    def __init__(self, color=None):
        super().__init__()
        self.setIcon(render_icon("save.svg", color=color))
        if color is not None:
            set_icon_button_hover_color(self, color)


class OpenIconButton(FlatButton):
    def __init__(self):
        super().__init__()
        self.setIcon(render_icon("open.svg"))


class ResetIconButton(FlatButton):
    def __init__(self):
        super().__init__()
        self.setIcon(render_icon("reset.svg"))


class IconActionButton(FlatButton):
    """Icon-only action whose disabled state reads as unavailable.

    With a stylesheet applied Qt draws through QStyleSheetStyle, which
    ignores an icon's disabled mode, and the theme fills a disabled flat
    button with a muted accent — so an action that cannot be used came out
    looking more prominent than one that can. The fade is therefore applied
    by hand, as the history buttons do, and the fill removed.
    """

    _SIZE = 28
    _DISABLED_OPACITY = 0.3

    def __init__(self, icon_name: str, tooltip: str):
        super().__init__()
        self.setIconSize(QtCore.QSize(PLOT_ICON_SIZE, PLOT_ICON_SIZE))
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setToolTip(tooltip)
        self.setStyleSheet(
            "QPushButton {{ background: transparent;"
            " border: 1px solid transparent; }}"
            "QPushButton:hover:enabled {{ border: 1px solid {0}; }}"
            "QPushButton:disabled {{ background: transparent;"
            " border: 1px solid transparent; }}".format(PLOT_ICON_COLOR)
        )
        self.set_glyph(icon_name)

    def set_glyph(self, icon_name: str):
        """Swaps which glyph the button shows, keeping its faded twin."""
        self._icons = (
            render_icon(icon_name, color=PLOT_ICON_COLOR),
            render_icon(icon_name, self._DISABLED_OPACITY, color=PLOT_ICON_COLOR),
        )
        self._apply_icon()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._apply_icon()

    def _apply_icon(self):
        self.setIcon(self._icons[0 if self.isEnabled() else 1])


class HorizontalLine(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setFixedHeight(1)


class VerticalLine(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setFixedWidth(1)


class ListTableWidget(QtWidgets.QTableWidget):
    def __init__(self, columns=3):
        super().__init__()

        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setColumnCount(columns)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.AdjustToContents
        )


class NoRectDelegate(QtWidgets.QItemDelegate):
    def __init__(self):
        super().__init__()

    def drawFocus(self, painter, option, rect):
        option.state &= ~QtWidgets.QStyle.State_HasFocus
        QtWidgets.QItemDelegate.drawFocus(self, painter, option, rect)


def HorizontalSpacerItem(minimum_width=0):
    return QtWidgets.QSpacerItem(
        minimum_width,
        0,
        QtWidgets.QSizePolicy.MinimumExpanding,
        QtWidgets.QSizePolicy.Minimum,
    )


def VerticalSpacerItem():
    return QtWidgets.QSpacerItem(
        0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.MinimumExpanding
    )


class MenuTabWidget(QtWidgets.QWidget):
    """
    A widget that switches between added widgets using a menu on the left.
    This is used to substitute the built-in tab widget, because we need horizontal text buttons on the left.

    Example:
    ```
    menu_tab_widget = MenuTabWidget()
    menu_tab_widget.add_tab("Tab 1", QtWidgets.QWidget())
    menu_tab_widget.add_tab("Tab 2", QtWidgets.QWidget())
    ```
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._menu_layout = QtWidgets.QVBoxLayout()
        self._menu_layout.setContentsMargins(0, 0, 0, 0)
        self._menu_layout.setSpacing(0)
        self._menu_btn_widget = QtWidgets.QWidget()
        self._menu_btn_widget.setObjectName("MenuTabWidgetMenu")
        self._menu_btn_layout = QtWidgets.QVBoxLayout()
        self._menu_btn_layout.setContentsMargins(0, 0, 0, 0)
        self._menu_btn_layout.setSpacing(0)
        self._menu_btn_widget.setLayout(self._menu_btn_layout)
        self._menu_layout.addWidget(self._menu_btn_widget)
        self._menu_layout.addStretch()

        self._menu_button_group = QtWidgets.QButtonGroup()

        self._layout.addLayout(self._menu_layout)
        self.setLayout(self._layout)

        self.menu_btns = []
        self.tab_widgets = []

        self.set_menu_width()

    def add_tab(self, title: str, widget: QtWidgets.QWidget):
        """
        Add a tab to the tab widget.
        :param title: The title of the tab.
        :param widget: The widget that should be shown when the tab is selected.
        """
        btn = CheckableFlatButton(title)
        btn.setFixedHeight(30)
        btn.setProperty("tab_title", title)
        self.menu_btns.append(btn)
        self._menu_button_group.addButton(btn)
        self._menu_btn_layout.addWidget(btn)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        btn.clicked.connect(lambda: self.show_tab(scroll_area))
        self.tab_widgets.append(scroll_area)
        self._layout.addWidget(scroll_area)
        scroll_area.hide()

        # If the widget is a QGroupBox, update the tab button to indicate
        # when the correction is enabled (toggled signal works even if
        # setCheckable is called later)
        if isinstance(widget, QtWidgets.QGroupBox):
            widget.toggled.connect(
                lambda checked, b=btn, t=title: b.setText(
                    "\u2022 " + t if checked else t
                )
            )

        if len(self.menu_btns) == 1:
            self.select_tab(0)

    def show_tab(self, widget: QtWidgets.QWidget):
        """
        Show the widget. Widg must habe been added with add_tab before.
        """
        for tab_widget in self.tab_widgets:
            tab_widget.hide()
        widget.show()

    def select_tab(self, index):
        """
        Select the tab with the given index.
        """
        self.menu_btns[index].setChecked(True)
        self.show_tab(self.tab_widgets[index])

    def set_menu_width(self, width: int = 100):
        """
        Set the width of the menu on the left.
        """
        self._menu_btn_widget.setFixedWidth(width)

    def menu_height(self) -> int:
        """Height of the menu button column — the part of the widget that
        cannot scroll and therefore always needs to be visible."""
        return self._menu_btn_widget.sizeHint().height()


class ParameterFormWidget(QtWidgets.QWidget):
    """A form of (label, number field, unit) rows with by-name access.

    Replaces parameter tables: fields are addressed by parameter name
    instead of row index, so controllers cannot mix up rows. ``changed``
    is emitted when the user finishes editing any field; programmatic
    ``set_value`` does not emit.

    Rows stay compact: fields keep a fixed width instead of stretching with
    the panel, and the form only claims the height its rows need.
    """

    changed = QtCore.Signal()

    field_width = 90

    def __init__(self, parameters=None):
        """
        :param parameters: iterable of (name, label, default, unit) tuples
        """
        super().__init__()
        self._fields = {}
        self._labels = []
        self._row_count = 0
        self._grid = QtWidgets.QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(5)
        self._grid.setColumnStretch(3, 1)  # empty column absorbs extra width
        self.setLayout(self._grid)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum
        )
        self.add_parameters(parameters or [])

    def add_parameters(self, parameters):
        for parameter in parameters:
            self.add_parameter(*parameter)

    def add_parameter(self, name, label, default, unit=""):
        field = NumberTextField("{:g}".format(default))
        field.editingFinished.connect(self.changed)
        field.setMaximumWidth(self.field_width)
        self.add_row(label, field, unit)
        self._fields[name] = field
        return field

    def add_row(self, label, widget, unit=""):
        """Add a row with an arbitrary widget, so that non-numeric input
        (e.g. a chemical formula) lines up with the parameter rows."""
        row = self._row_count
        label_widget = LabelAlignRight(label + ":")
        self._labels.append(label_widget)
        self._grid.addWidget(label_widget, row, 0)
        self._grid.addWidget(
            widget, row, 1, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        )
        if unit:
            self._grid.addWidget(QtWidgets.QLabel(unit), row, 2)
        self._row_count += 1

    def label_width(self):
        """Natural width of the label column."""
        return max((lbl.sizeHint().width() for lbl in self._labels), default=0)

    def set_label_width(self, width):
        self._grid.setColumnMinimumWidth(0, width)

    def field(self, name):
        return self._fields[name]

    def value(self, name):
        return self._fields[name].value()

    def set_value(self, name, value):
        self._fields[name].setText(str(value))

    def values(self):
        return {name: field.value() for name, field in self._fields.items()}

    def parameter_names(self):
        return list(self._fields)


def align_parameter_forms(*forms):
    """Give several ParameterFormWidgets a common label column width, so that
    their fields line up when stacked in the same panel."""
    width = max(form.label_width() for form in forms)
    for form in forms:
        form.set_label_width(width)


def render_icon(filename, opacity=1.0, sizes=(14, 28, 56), color=None):
    """Renders an SVG icon to pixmaps, optionally faded or recoloured.

    Rendered here rather than handed to QIcon as a file for two reasons: an
    icon backed by the SVG engine regenerates every mode from the source and
    ignores an added disabled pixmap, and with a stylesheet applied Qt draws
    the button through QStyleSheetStyle, which does not use the icon's
    disabled mode at all. Callers therefore keep a faded icon of their own and
    swap it in — see MainWidget.set_history_enabled.

    Several sizes are provided because Qt picks the closest match, including
    the 2x and 4x variants for high-DPI screens.

    :param color: replaces the glyph set's base colour (#f1f1f1), e.g. with
        PLOT_ICON_COLOR for icon buttons that sit among flat text
        buttons, or DANGER_COLOR for destructive ones.
    """
    from qtpy import QtSvg

    path = os.path.join(icons_path, filename)
    if color is None:
        renderer = QtSvg.QSvgRenderer(path)
    else:
        with open(path) as svg_file:
            svg = svg_file.read().replace("#f1f1f1", color)
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode()))
    icon = QtGui.QIcon()
    for size in sizes:
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setOpacity(opacity)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class EmptyStateOverlay(QtWidgets.QLabel):
    """Dimmed, centered hint text laid over a host widget while a view has
    no data yet (e.g. "Load an image to begin"). The overlay tracks the
    host's size, ignores mouse events and is simply hidden once content
    arrives.
    """

    def __init__(self, host: QtWidgets.QWidget, text: str):
        super().__init__(text, host)
        self._host = host
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setWordWrap(True)
        self.setTextFormat(QtCore.Qt.RichText)
        self.setStyleSheet('background: transparent; color: #8A8A8A;')
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        host.installEventFilter(self)
        self._sync_geometry()

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() in (
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
        ):
            self._sync_geometry()
        return False

    def _sync_geometry(self):
        self.setGeometry(self._host.rect())
        self.raise_()
