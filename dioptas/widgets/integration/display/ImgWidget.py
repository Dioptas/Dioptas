# SPDX-License-Identifier: MIT

import os

from qtpy import QtWidgets, QtCore, QtGui
from pyqtgraph import GraphicsLayoutWidget

from ...plot_widgets.ImgWidget import IntegrationImgWidget, IntegrationCakeWidget
from ...CustomWidgets import FlatButton, CheckableFlatButton, HorizontalSpacerItem, SaveIconButton, DarkCheckableFlatButton
from ..CustomWidgets import MouseCurrentAndClickedWidget, MouseUnitCurrentAndClickedWidget
from .. import CLICKED_COLOR


class IntegrationImgDisplayWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.frame = QtWidgets.QWidget()
        self.frame.setObjectName('img_frame')

        self._frame_layout = QtWidgets.QVBoxLayout()
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_view = IntegrationImgWidget(self.img_pg_layout, orientation='horizontal')
        self.cake_pg_layout = GraphicsLayoutWidget()
        self.cake_view = IntegrationCakeWidget(self.cake_pg_layout, orientation='horizontal')
        self._frame_layout.addWidget(self.img_pg_layout)
        self._frame_layout.addWidget(self.cake_pg_layout)
        self.cake_pg_layout.hide()

        self.position_and_unit_widget = QtWidgets.QWidget()
        self.position_and_unit_widget.setObjectName('img_position_and_unit_widget')
        self._position_and_unit_layout = QtWidgets.QHBoxLayout()
        self._position_and_unit_layout.setContentsMargins(0, 0, 0, 0)

        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget(CLICKED_COLOR)

        self._position_and_unit_layout.addWidget(self.mouse_pos_widget)
        self._position_and_unit_layout.addSpacerItem(HorizontalSpacerItem())
        self._position_and_unit_layout.addWidget(self.mouse_unit_widget)

        self.position_and_unit_widget.setLayout(self._position_and_unit_layout)

        self._frame_layout.addWidget(self.position_and_unit_widget)

        self._control_layout = QtWidgets.QHBoxLayout()
        self._control_layout.setContentsMargins(6, 6, 6, 6)
        self._control_layout.setSpacing(6)

        self.save_image_btn = SaveIconButton()
        self.save_image_btn.setToolTip("Save Image")

        self.roi_btn = CheckableFlatButton('ROI')
        self.mode_btn = FlatButton('Cake')
        self.cake_shift_azimuth_sl = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.mask_btn = CheckableFlatButton('Mask')
        self.phases_btn = CheckableFlatButton('Show Phases')
        self.show_background_subtracted_img_btn = CheckableFlatButton('bkg')
        self.transparent_cb = QtWidgets.QCheckBox('trans')
        self.autoscale_btn = CheckableFlatButton('AutoScale')
        self.undock_btn = FlatButton('Undock')

        self._control_layout.addWidget(self.save_image_btn)
        self._control_layout.addWidget(self.roi_btn)
        self._control_layout.addWidget(self.mode_btn)
        self._control_layout.addWidget(self.cake_shift_azimuth_sl)
        self._control_layout.addWidget(self.mask_btn)
        self._control_layout.addWidget(self.transparent_cb)
        self._control_layout.addWidget(self.show_background_subtracted_img_btn)
        self._control_layout.addWidget(self.phases_btn)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._control_layout.addWidget(self.autoscale_btn)
        self._control_layout.addWidget(self.undock_btn)

        self._frame_layout.addLayout(self._control_layout)
        self.frame.setLayout(self._frame_layout)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.frame)

        self.setLayout(self._layout)

        self.style_widgets()
        self.set_tooltips()
        self.cake_shift_azimuth_sl.setVisible(False)
        self.show_background_subtracted_img_btn.setVisible(False)

    def style_widgets(self):
        self.setStyleSheet("""
            #img_frame, #img_position_and_unit_widget {
                background: black;
            }
            """)
        self.autoscale_btn.setChecked(True)
        self.phases_btn.setChecked(False)
        self.phases_btn.setVisible(False)
        self.position_and_unit_widget.hide()

        self.save_image_btn.setIconSize(QtCore.QSize(13, 13))
        self.save_image_btn.setWidth(25)

        # btns = [self.roi_btn, self.mode_btn, self.mask_btn, self.transparent_cb, self.show_background_subtracted_img_btn, 
        #         self.autoscale_btn, self.undock_btn]
        
        # for btn in btns:
        #     btn.setFixedHeight(25)

    def set_tooltips(self):
        self.show_background_subtracted_img_btn.setToolTip("Toggle background subtraction")
        self.mask_btn.setToolTip("Toggle mask")
        self.mode_btn.setToolTip("Toggle between image and cake mode")
        self.undock_btn.setToolTip("Undock image to new window")