# -*- coding: utf8 -*-

from functools import partial

from PyQt4 import QtGui, QtCore

from widgets.CustomWidgets import LabelAlignRight, HorizontalSpacerItem, CheckableFlatButton, FlatButton, \
    NumberTextField, IntegerTextField, VerticalLine


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
        self.configuration_btn_group = QtGui.QButtonGroup()

        self.add_configuration_btn = FlatButton("+")
        self.remove_configuration_btn = FlatButton("-")

        self.factor_lbl = LabelAlignRight("Factor: ")
        self.factor_txt = NumberTextField("1")

        self.file_lbl = LabelAlignRight("File: ")
        self.previous_file_btn = FlatButton("<")
        self.next_file_btn = FlatButton(">")
        self.file_iterator_pos_lbl = LabelAlignRight(" Pos: ")
        self.file_iterator_pos_txt = IntegerTextField("1")

        self.folder_lbl = LabelAlignRight(" Folder:")
        self.next_folder_btn = FlatButton(">")
        self.previous_folder_btn = FlatButton("<")

        self.combine_patterns_btn = CheckableFlatButton("Combine Patterns")
        self.combine_cakes_btn = CheckableFlatButton("Combine Cakes")

    def create_layout(self):
        self.main_layout = QtGui.QHBoxLayout()
        self.main_layout.addWidget(self.configuration_lbl)
        self.main_layout.addWidget(self.add_configuration_btn)
        self.main_layout.addWidget(self.remove_configuration_btn)
        self.main_layout.addWidget(self.configurations_btn_widget)
        self.main_layout.addSpacerItem(HorizontalSpacerItem())
        self.main_layout.addWidget(VerticalLine())
        self.main_layout.addWidget(self.file_lbl)
        self.main_layout.addWidget(self.previous_file_btn)
        self.main_layout.addWidget(self.next_file_btn)
        self.main_layout.addWidget(self.file_iterator_pos_lbl)
        self.main_layout.addWidget(self.file_iterator_pos_txt)
        self.main_layout.addWidget(VerticalLine())
        self.main_layout.addWidget(self.folder_lbl)
        self.main_layout.addWidget(self.previous_folder_btn)
        self.main_layout.addWidget(self.next_folder_btn)
        self.main_layout.addWidget(VerticalLine())
        self.main_layout.addSpacerItem(HorizontalSpacerItem())
        self.main_layout.addWidget(self.factor_lbl)
        self.main_layout.addWidget(self.factor_txt)
        self.main_layout.addSpacerItem(QtGui.QSpacerItem(20, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum))
        self.main_layout.addWidget(self.combine_patterns_btn)
        self.main_layout.addWidget(self.combine_cakes_btn)
        self.setLayout(self.main_layout)

        self.configurations_btn_layout = QtGui.QHBoxLayout(self.configurations_btn_widget)

    def style_widgets(self):
        self.main_layout.setSpacing(7)
        self.next_file_btn.setMaximumWidth(25)
        self.file_iterator_pos_txt.setMaximumWidth(25)
        self.next_folder_btn.setMaximumWidth(25)
        self.previous_folder_btn.setMaximumWidth(25)
        self.previous_file_btn.setMaximumWidth(25)
        self.main_layout.setContentsMargins(5, 5, 5, 3)
        self.factor_txt.setMaximumWidth(35)

    def update_configurations(self, configurations, cur_ind):
        for btn in self.configuration_btns:
            self.configurations_btn_layout.removeWidget(btn)
            self.configuration_btn_group.removeButton(btn)

        self.configuration_btns = []

        for ind, configuration in enumerate(configurations):
            new_button = CheckableFlatButton(str(ind + 1))
            self.configuration_btn_group.addButton(new_button)
            self.configuration_btns.append(new_button)
            self.configurations_btn_layout.addWidget(new_button)
            if ind == cur_ind:
                new_button.setChecked(True)
            new_button.clicked.connect(partial(self.configuration_selected.emit, ind))
