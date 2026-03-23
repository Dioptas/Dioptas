# SPDX-License-Identifier: MIT

from qtpy import QtWidgets

from ...CustomWidgets import LabelAlignRight, HorizontalSpacerItem
from ..CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget
from .. import CLICKED_COLOR


class IntegrationStatusWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(6, 3, 6, 0)
        self._layout.setSpacing(6)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget(CLICKED_COLOR)
        self.bkg_name_lbl = LabelAlignRight('')
        self.change_view_btn = QtWidgets.QPushButton('Change View')

        self._layout.addWidget(self.change_view_btn)
        self._layout.addWidget(self.mouse_pos_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.mouse_unit_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.bkg_name_lbl)

        self.setLayout(self._layout)
