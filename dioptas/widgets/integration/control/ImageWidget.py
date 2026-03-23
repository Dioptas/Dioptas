# SPDX-License-Identifier: MIT


from qtpy import QtWidgets

from ...CustomWidgets import LabelAlignRight, VerticalSpacerItem, HorizontalSpacerItem
from ..CustomWidgets import BrowseFileWidget


class ImageWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self._create_widgets()
        self._create_layout()
        self._style_widgets()
        self._set_tooltips()

    def _create_widgets(self):
        self.file_widget = BrowseFileWidget(files='Image', checkbox_text='autoprocess')
        self.file_info_btn = QtWidgets.QPushButton('File Info')
        self.move_btn = QtWidgets.QPushButton('Position')
        self.batch_btn = QtWidgets.QPushButton('Batch view')

        self.batch_mode_widget = QtWidgets.QWidget()
        self.batch_mode_lbl = LabelAlignRight("Batch Mode:")
        self.batch_mode_integrate_rb = QtWidgets.QRadioButton("integrate")
        self.batch_mode_add_rb = QtWidgets.QRadioButton("add")
        self.batch_mode_average_rb = QtWidgets.QRadioButton("average")
        self.batch_mode_image_save_rb = QtWidgets.QRadioButton("save")

    def _create_layout(self):
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)

        self._layout.addWidget(self.file_widget)

        self._batch_layout = QtWidgets.QHBoxLayout()
        self._batch_layout.addWidget(self.batch_mode_lbl)
        self._batch_layout.addWidget(self.batch_mode_integrate_rb)
        self._batch_layout.addWidget(self.batch_mode_add_rb)
        self._batch_layout.addWidget(self.batch_mode_average_rb)
        self._batch_layout.addWidget(self.batch_mode_image_save_rb)
        self._batch_layout.addItem(HorizontalSpacerItem())
        self._batch_layout.addWidget(self.batch_btn)
        self.batch_mode_widget.setLayout(self._batch_layout)
        self._layout.addWidget(self.batch_mode_widget)

        self._file_info_layout = QtWidgets.QHBoxLayout()
        self._file_info_layout.addWidget(self.file_info_btn)
        self._file_info_layout.addWidget(self.move_btn)
        self._file_info_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._file_info_layout)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)

    def _style_widgets(self):
        self._batch_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_mode_integrate_rb.setChecked(True)
        self.batch_btn.setFixedHeight(25)

    def _set_tooltips(self):
        self.batch_mode_add_rb.setToolTip("Adds all images together")
        self.batch_mode_average_rb.setToolTip("Averages all images")
        self.batch_mode_integrate_rb.setToolTip("Integrates all images")
        self.batch_mode_image_save_rb.setToolTip("Saves all images")