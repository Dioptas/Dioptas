# SPDX-License-Identifier: MIT
import time

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


class CleanLooksComboBox(QtWidgets.QComboBox):
    cleanlooks = QtWidgets.QStyleFactory.create("motif")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(CleanLooksComboBox.cleanlooks)
        self.setLineEdit(CleanLooksLineEdit())
        self.lineEdit().clicked.connect(self.showPopup)
        self.popup_closed_time = time.time()

    def showPopup(self):
        if time.time() - self.popup_closed_time > 0.01:
            # prevents showing popup immediately after closing by clicking onto lineEdit.
            super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        self.popup_closed_time = time.time()


class CleanLooksLineEdit(QtWidgets.QLineEdit):
    clicked = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.installEventFilter(self)
        self.setReadOnly(True)
        self.setStyleSheet(
            """
                margin: 2px; 
                background: #3C3C3C;
            """
        )

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.clicked.emit()
            return True
        if event.type() == QtCore.QEvent.MouseMove:
            return True
        return super().eventFilter(obj, event)


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


class SaveIconButton(FlatButton):
    def __init__(self):
        super().__init__()
        self.setIcon(QtGui.QIcon(os.path.join(icons_path, "save.ico")))


class OpenIconButton(FlatButton):
    def __init__(self):
        super().__init__()
        self.setIcon(QtGui.QIcon(os.path.join(icons_path, "open.ico")))


class ResetIconButton(FlatButton):
    def __init__(self):
        super().__init__()
        self.setIcon(QtGui.QIcon(os.path.join(icons_path, "reset.ico")))


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
