# SPDX-License-Identifier: MIT

from qtpy import QtWidgets
from pyqtgraph import GraphicsLayoutWidget

from .plot_widgets import MaskImgWidget

from .CustomWidgets import NumberTextField, LabelAlignRight, SpinBoxAlignRight, HorizontalSpacerItem, \
    CheckableButton, VerticalSpacerItem, HorizontalLine
from .MaskPluginWidget import MaskPluginWidget


class MaskWidget(QtWidgets.QWidget):
    """
    Defines the main structure of the mask widget, which is separated into two parts.
    Mask Display Widget - shows the image and pattern
    Mask Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName('mask_widget')
        self._layout = QtWidgets.QHBoxLayout()
        self.create_display_widget()
        self.create_control_widget()

        self._layout.addWidget(self._display_widget)
        self._layout.addWidget(self._control_widget)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self.style_widgets()
        self.setLayout(self._layout)

    def create_display_widget(self):
        self._display_widget = QtWidgets.QWidget(self)
        self._display_layout = QtWidgets.QVBoxLayout()
        self._display_layout.setContentsMargins(0, 0, 0, 0)
        self.img_layout_widget = GraphicsLayoutWidget()
        self.img_widget = MaskImgWidget(self.img_layout_widget)

        self._display_layout.addWidget(self.img_layout_widget)

        self._status_layout = QtWidgets.QHBoxLayout()
        self._status_layout.addSpacerItem(HorizontalSpacerItem())

        self.pos_lbl = LabelAlignRight('')
        self._status_layout.addWidget(self.pos_lbl)
        self._display_layout.addLayout(self._status_layout)

        self._display_widget.setLayout(self._display_layout)

    def create_control_widget(self):
        self._control_widget = QtWidgets.QWidget(self)
        self._control_layout = QtWidgets.QVBoxLayout(self._control_widget)
        self._control_layout.setSpacing(6)

        self._rb_layout = QtWidgets.QHBoxLayout()
        self.mask_rb = QtWidgets.QRadioButton('mask')
        self.unmask_rb = QtWidgets.QRadioButton('unmask')
        self._rb_layout.addWidget(self.mask_rb)
        self._rb_layout.addWidget(self.unmask_rb)
        self._control_layout.addLayout(self._rb_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._geometry_layout = QtWidgets.QGridLayout()
        self.circle_btn = CheckableButton('Circle')
        self.rectangle_btn = CheckableButton('Rectangle')
        self.point_btn = CheckableButton('Point')
        self.point_size_sb = SpinBoxAlignRight()
        self.polygon_btn = CheckableButton('Polygon')
        self.arc_btn = CheckableButton('Arc')
        self._geometry_layout.addWidget(self.circle_btn, 0, 0)
        self._geometry_layout.addWidget(self.rectangle_btn, 0, 1)
        self._geometry_layout.addWidget(self.point_btn, 1, 0)
        self._geometry_layout.addWidget(self.point_size_sb, 1, 1)
        self._geometry_layout.addWidget(self.polygon_btn, 2, 0)
        self._geometry_layout.addWidget(self.arc_btn, 2, 1)
        self._control_layout.addLayout(self._geometry_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._threshold_layout = QtWidgets.QGridLayout()
        self.above_thresh_btn = QtWidgets.QPushButton('Above Thresh')
        self.below_thresh_btn = QtWidgets.QPushButton('Below Thresh')
        self.above_thresh_txt = NumberTextField('')
        self.below_thresh_txt = NumberTextField('')
        self._threshold_layout.addWidget(self.above_thresh_btn, 0, 0)
        self._threshold_layout.addWidget(self.above_thresh_txt, 0, 1)
        self._threshold_layout.addWidget(self.below_thresh_btn, 1, 0)
        self._threshold_layout.addWidget(self.below_thresh_txt, 1, 1)
        self._control_layout.addLayout(self._threshold_layout)

        self._control_layout.addWidget(HorizontalLine())

        self._action_layout = QtWidgets.QGridLayout()
        self.grow_btn = QtWidgets.QPushButton('Grow')
        self.shrink_btn = QtWidgets.QPushButton('Shrink')
        self.invert_mask_btn = QtWidgets.QPushButton('Invert')
        self.clear_mask_btn = QtWidgets.QPushButton('Clear')
        self.undo_btn = QtWidgets.QPushButton('Undo')
        self.redo_btn = QtWidgets.QPushButton('Redo')
        self._action_layout.addWidget(self.grow_btn, 0, 0)
        self._action_layout.addWidget(self.shrink_btn, 0, 1)
        self._action_layout.addWidget(self.invert_mask_btn, 1, 0)
        self._action_layout.addWidget(self.clear_mask_btn, 1, 1)
        self._action_layout.addWidget(self.undo_btn, 2, 0)
        self._action_layout.addWidget(self.redo_btn, 2, 1)
        self._control_layout.addLayout(self._action_layout)

        self._control_layout.addWidget(HorizontalLine())

        self.cosmic_btn = QtWidgets.QPushButton('Cosmic Removal')
        self._control_layout.addWidget(self.cosmic_btn)

        self._control_layout.addWidget(HorizontalLine())

        self._plugin_header = QtWidgets.QLabel("Automatic Masking Plugins")
        self._plugin_header.setStyleSheet(
            "font-weight: bold; color: gray; margin-top: 4px;"
        )
        self._control_layout.addWidget(self._plugin_header)
        self.plugin_widget = MaskPluginWidget()
        self._control_layout.addWidget(self.plugin_widget)
        self._plugin_separator = HorizontalLine()
        self._control_layout.addWidget(self._plugin_separator)
        # Hide plugin section until plugins are registered
        self._plugin_header.hide()
        self.plugin_widget.hide()
        self._plugin_separator.hide()

        self._visibility_widget = QtWidgets.QWidget()
        self._visibility_layout = QtWidgets.QHBoxLayout()
        self.fill_rb = QtWidgets.QRadioButton('Fill')
        self.transparent_rb = QtWidgets.QRadioButton('Transparent')
        self._visibility_layout.addWidget(self.fill_rb)
        self._visibility_layout.addWidget(self.transparent_rb)
        self._visibility_widget.setLayout(self._visibility_layout)
        self._control_layout.addWidget(self._visibility_widget)

        self._control_layout.addSpacerItem(VerticalSpacerItem())

        self._file_layout = QtWidgets.QGridLayout()
        self.save_mask_btn = QtWidgets.QPushButton('Save Mask')
        self.load_mask_btn = QtWidgets.QPushButton('Load Mask')
        self.add_mask_btn = QtWidgets.QPushButton('Add Mask')
        self._file_layout.addWidget(self.save_mask_btn, 0, 0, 1, 2)
        self._file_layout.addWidget(self.load_mask_btn, 1, 0)
        self._file_layout.addWidget(self.add_mask_btn, 1, 1)
        self._control_layout.addLayout(self._file_layout)

        self._control_widget.setLayout(self._control_layout)

    def style_widgets(self):
        self.mask_rb.setChecked(True)
        self.fill_rb.setChecked(True)
        self.point_size_sb.setValue(20)

        self._control_widget.setMinimumWidth(200)
        self._control_widget.setMaximumWidth(200)
