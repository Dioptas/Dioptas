# -*- coding: utf8 -*-

from functools import partial

from PyQt4 import QtGui, QtCore

from widgets.CustomWidgets import NumberTextField, LabelAlignRight, SpinBoxAlignRight, \
    HorizontalSpacerItem, CheckableFlatButton, FlatButton, VerticalSpacerItem, HorizontalLine


class ConfigurationWidget(QtGui.QWidget):
    configuration_selected = QtCore.pyqtSignal(int)  # configuration index

    def __init__(self, parent=None):
        super(ConfigurationWidget, self).__init__(parent)
        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.configuration_lbl = LabelAlignRight("Configuration:")

        self.configuration_btns = []
        self.configurations_btn_widget = QtGui.QWidget()
        self.configuration_name_lbl = LabelAlignRight("Name:")
        self.configuration_name_txt = QtGui.QLineEdit("default")

    def create_layout(self):
        self.main_layout = QtGui.QHBoxLayout()
        self.main_layout.addWidget(self.configuration_lbl)
        self.main_layout.addWidget(self.configurations_btn_widget)
        self.main_layout.addWidget(self.configuration_name_lbl)
        self.main_layout.addWidget(self.configuration_name_txt)
        self.main_layout.addSpacerItem(HorizontalSpacerItem())
        self.setLayout(self.main_layout)

    def style_widgets(self):
        self.main_layout.setContentsMargins(5, 5, 5, 3)

        self.configuration_name_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.configuration_name_txt.setMaximumWidth(150)

    def update_configurations(self, configurations, cur_ind):
        self.main_layout.removeWidget(self.configurations_btn_widget)
        self.configuration_btn_group = QtGui.QButtonGroup()
        self.configurations_btn_widget = QtGui.QWidget()
        self.configurations_btn_layout = QtGui.QHBoxLayout(self.configurations_btn_widget)
        self.configuration_btns.clear()

        for ind, configuration in enumerate(configurations):
            new_button = CheckableFlatButton(str(ind + 1))
            self.configuration_btn_group.addButton(new_button)
            self.configuration_btns.append(new_button)
            self.configurations_btn_layout.addWidget(new_button)
            if ind == cur_ind:
                new_button.setChecked(True)
            new_button.pressed.connect(partial(self.configuration_selected, ind))
