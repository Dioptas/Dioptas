# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from functools import partial

from qtpy import QtWidgets, QtCore

from ..CustomWidgets import NumberTextField, IntegerTextField, LabelAlignRight, SpinBoxAlignRight, FlatButton, \
    CheckableFlatButton, DoubleSpinBoxAlignRight, VerticalSpacerItem, HorizontalLine, HorizontalSpacerItem, \
    ListTableWidget, VerticalLine

from .CustomWidgets import BrowseFileWidget
from .. CustomWidgets import NoRectDelegate


class IntegrationControlWidget(QtWidgets.QTabWidget):
    def __init__(self):
        super(IntegrationControlWidget, self).__init__()

        self.img_control_widget = ImageControlWidget()
        self.pattern_control_widget = PatternControlWidget()
        self.overlay_control_widget = OverlayControlWidget()
        self.phase_control_widget = PhaseControlWidget()
        self.corrections_control_widget = CorrectionsControlWidget()
        self.background_control_widget = BackgroundControlWidget()
        self.integration_options_widget = OptionsWidget()

        self.addTab(self.img_control_widget, 'Image')
        self.addTab(self.pattern_control_widget, 'Pattern')
        self.addTab(self.overlay_control_widget, 'Overlay')
        self.addTab(self.phase_control_widget, 'Phase')
        self.addTab(self.corrections_control_widget, 'Cor')
        self.addTab(self.background_control_widget, 'Bkg')
        self.addTab(self.integration_options_widget, 'X')

        self.style_widgets()

    def style_widgets(self):
        self.setStyleSheet("""
        QTableWidget QPushButton {
            margin: 5px;
        }

        QTableWidget QPushButton::pressed{
            margin-top: 7px;
            margin-left: 7px;
        }

        QTableWidget {
            selection-background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 rgba(177,80,0,255), stop:1 rgba(255,120,0,255));
            selection-color: #F1F1F1;
        }
        """)


class ImageControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(ImageControlWidget, self).__init__()

        self._create_widgets()
        self._create_layout()
        self._style_widgets()

    def _create_widgets(self):
        self.file_widget = BrowseFileWidget(files='Image', checkbox_text='autoprocess')
        self.file_info_btn = FlatButton('File Info')
        self.move_btn = FlatButton('Position')

        self.batch_mode_widget = QtWidgets.QWidget()
        self.batch_mode_lbl = LabelAlignRight("Batch Mode:")
        self.batch_mode_integrate_rb = QtWidgets.QRadioButton("integrate")
        self.batch_mode_add_rb = QtWidgets.QRadioButton("add")
        self.batch_mode_image_save_rb = QtWidgets.QRadioButton("image save")

    def _create_layout(self):
        self._layout = QtWidgets.QVBoxLayout()

        self._layout.addWidget(self.file_widget)
        self._layout.addWidget(HorizontalLine())

        self._file_info_layout = QtWidgets.QHBoxLayout()
        self._file_info_layout.addWidget(self.file_info_btn)
        self._file_info_layout.addWidget(self.move_btn)
        self._file_info_layout.addSpacerItem(HorizontalSpacerItem())

        self._batch_layout = QtWidgets.QHBoxLayout()

        self._batch_layout.addWidget(self.batch_mode_lbl)
        self._batch_layout.addWidget(self.batch_mode_integrate_rb)
        self._batch_layout.addWidget(self.batch_mode_add_rb)
        self._batch_layout.addWidget(self.batch_mode_image_save_rb)
        self.batch_mode_widget.setLayout(self._batch_layout)

        self._file_info_layout.addWidget(self.batch_mode_widget)

        self._layout.addLayout(self._file_info_layout)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)

    def _style_widgets(self):
        self._batch_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_mode_integrate_rb.setChecked(True)


class PatternControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(PatternControlWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.file_widget = BrowseFileWidget(files='Pattern', checkbox_text='autocreate')

        self._layout.addWidget(self.file_widget)
        self._layout.addWidget(HorizontalLine())

        self.pattern_types_gc = QtWidgets.QGroupBox('Pattern data types')
        self.xy_cb = QtWidgets.QCheckBox('.xy')
        self.xy_cb.setChecked(True)
        self.chi_cb = QtWidgets.QCheckBox('.chi')
        self.dat_cb = QtWidgets.QCheckBox('.dat')
        self.fxye_cb = QtWidgets.QCheckBox('.fxye')
        self._pattern_types_gb_layout = QtWidgets.QHBoxLayout()
        self._pattern_types_gb_layout.addWidget(self.xy_cb)
        self._pattern_types_gb_layout.addWidget(self.chi_cb)
        self._pattern_types_gb_layout.addWidget(self.dat_cb)
        self._pattern_types_gb_layout.addWidget(self.fxye_cb)
        self.pattern_types_gc.setLayout(self._pattern_types_gb_layout)

        self._pattern_types_layout = QtWidgets.QHBoxLayout()
        self._pattern_types_layout.addWidget(self.pattern_types_gc)
        self._pattern_types_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._pattern_types_layout)

        self._layout.addItem(VerticalSpacerItem())

        self.setLayout(self._layout)


class PhaseControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(PhaseControlWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.button_widget = QtWidgets.QWidget(self)
        self.button_widget.setObjectName('phase_control_button_widget')
        self._button_layout = QtWidgets.QHBoxLayout()
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(6)

        self.add_btn = FlatButton('Add')
        self.edit_btn = FlatButton('Edit')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')
        self.save_list_btn = FlatButton('Save List')
        self.load_list_btn = FlatButton('Load List')

        self._button_layout.addWidget(self.add_btn)
        self._button_layout.addWidget(self.edit_btn)
        self._button_layout.addWidget(self.delete_btn)
        self._button_layout.addWidget(self.clear_btn)
        self._button_layout.addWidget(VerticalLine())
        self._button_layout.addSpacerItem(HorizontalSpacerItem())
        self._button_layout.addWidget(VerticalLine())
        self._button_layout.addWidget(self.save_list_btn)
        self._button_layout.addWidget(self.load_list_btn)
        self.button_widget.setLayout(self._button_layout)
        self._layout.addWidget(self.button_widget)

        self.parameter_widget = QtWidgets.QWidget()

        self._parameter_layout = QtWidgets.QGridLayout()
        self.pressure_sb = DoubleSpinBoxAlignRight()
        self.temperature_sb = DoubleSpinBoxAlignRight()
        self.pressure_step_txt = NumberTextField('0.5')
        self.temperature_step_txt = NumberTextField('100')
        self.apply_to_all_cb = QtWidgets.QCheckBox('Apply to all phases')
        self.show_in_pattern_cb = QtWidgets.QCheckBox('Show in Pattern')

        self._parameter_layout.addWidget(QtWidgets.QLabel('Parameter'), 0, 1)
        self._parameter_layout.addWidget(QtWidgets.QLabel('Step'), 0, 3)
        self._parameter_layout.addWidget(QtWidgets.QLabel('P:'), 1, 0)
        self._parameter_layout.addWidget(QtWidgets.QLabel('T:'), 2, 0)
        self._parameter_layout.addWidget(QtWidgets.QLabel('GPa'), 1, 2)
        self._parameter_layout.addWidget(QtWidgets.QLabel('K'), 2, 2)

        self._parameter_layout.addWidget(self.pressure_sb, 1, 1)
        self._parameter_layout.addWidget(self.pressure_step_txt, 1, 3)
        self._parameter_layout.addWidget(self.temperature_sb, 2, 1)
        self._parameter_layout.addWidget(self.temperature_step_txt, 2, 3)

        self._parameter_layout.addWidget(self.apply_to_all_cb, 3, 0, 1, 5)
        self._parameter_layout.addWidget(self.show_in_pattern_cb, 4, 0, 1, 5)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0)
        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtWidgets.QHBoxLayout()
        self.phase_tw = ListTableWidget(columns=5)
        self._body_layout.addWidget(self.phase_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.phase_tw.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.parameter_widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.phase_tw.setMinimumHeight(130)

        self.temperature_step_txt.setMaximumWidth(60)
        self.pressure_step_txt.setMaximumWidth(60)
        self.pressure_sb.setMinimumWidth(100)

        self.pressure_sb.setMaximum(9999999)
        self.pressure_sb.setMinimum(-9999999)
        self.pressure_sb.setValue(0)

        self.temperature_sb.setMaximum(99999999)
        self.temperature_sb.setMinimum(0)
        self.temperature_sb.setValue(298)

        self.setStyleSheet("""
            #phase_control_button_widget QPushButton {
                min-width: 95;
            }
        """)

        self.apply_to_all_cb.setChecked(True)
        self.show_in_pattern_cb.setChecked(True)


class OverlayControlWidget(QtWidgets.QWidget):
    color_btn_clicked = QtCore.Signal(int, QtWidgets.QWidget)
    show_cb_state_changed = QtCore.Signal(int, bool)
    name_changed = QtCore.Signal(int, str)

    def __init__(self):
        super(OverlayControlWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.button_widget = QtWidgets.QWidget(self)
        self.button_widget.setObjectName('overlay_control_widget')
        self._button_layout = QtWidgets.QHBoxLayout(self.button_widget)
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(6)

        self.add_btn = FlatButton('Add')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')
        self.move_up_btn = FlatButton('Move Up')
        self.move_down_btn = FlatButton('Move Down')

        self._button_layout.addWidget(self.add_btn)
        self._button_layout.addWidget(self.delete_btn)
        self._button_layout.addWidget(self.clear_btn)
        self._button_layout.addWidget(self.move_up_btn)
        self._button_layout.addWidget(self.move_down_btn)
        self._button_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.button_widget)

        self.parameter_widget = QtWidgets.QWidget(self)
        self._parameter_layout = QtWidgets.QGridLayout(self.parameter_widget)
        self._parameter_layout.setSpacing(6)

        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()
        self.scale_step_txt = NumberTextField('0.01')
        self.offset_step_txt = NumberTextField('100')
        self.waterfall_separation_txt = NumberTextField('100')
        self.waterfall_btn = FlatButton('Waterfall')
        self.waterfall_reset_btn = FlatButton('Reset')
        self.set_as_bkg_btn = CheckableFlatButton('Set as Background')

        self._parameter_layout.addWidget(QtWidgets.QLabel('Step'), 0, 2)
        self._parameter_layout.addWidget(LabelAlignRight('Scale:'), 1, 0)
        self._parameter_layout.addWidget(LabelAlignRight('Offset:'), 2, 0)

        self._parameter_layout.addWidget(self.scale_sb, 1, 1)
        self._parameter_layout.addWidget(self.scale_step_txt, 1, 2)
        self._parameter_layout.addWidget(self.offset_sb, 2, 1)
        self._parameter_layout.addWidget(self.offset_step_txt, 2, 2)

        self._parameter_layout.addItem(VerticalSpacerItem(), 3, 0, 1, 3)

        self._waterfall_layout = QtWidgets.QHBoxLayout()
        self._waterfall_layout.addWidget(self.waterfall_btn)
        self._waterfall_layout.addWidget(self.waterfall_separation_txt)
        self._waterfall_layout.addWidget(self.waterfall_reset_btn)
        self._parameter_layout.addLayout(self._waterfall_layout, 4, 0, 1, 3)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0, 1, 3)

        self._background_layout = QtWidgets.QHBoxLayout()
        self._background_layout.addSpacerItem(HorizontalSpacerItem())
        self._background_layout.addWidget(self.set_as_bkg_btn)
        self._parameter_layout.addLayout(self._background_layout, 6, 0, 1, 3)
        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtWidgets.QHBoxLayout()
        self.overlay_tw = ListTableWidget(columns=3)
        self._body_layout.addWidget(self.overlay_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)
        self.style_widgets()

        self.overlay_tw.cellChanged.connect(self.label_editingFinished)
        self.overlay_tw.setItemDelegate(NoRectDelegate())
        self.show_cbs = []
        self.color_btns = []

    def style_widgets(self):
        step_txt_width = 70
        self.scale_step_txt.setMaximumWidth(step_txt_width)
        self.scale_step_txt.setMinimumWidth(step_txt_width)
        self.offset_step_txt.setMaximumWidth(step_txt_width)
        self.waterfall_separation_txt.setMaximumWidth(step_txt_width)

        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)
        self.scale_sb.setSingleStep(0.01)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)
        self.offset_sb.setSingleStep(100)

        self.setStyleSheet("""
            #overlay_control_widget QPushButton {
                min-width: 95;
            }
            QSpinBox {
                min-width: 110;
                max-width: 110;
            }
        """)

    def add_overlay(self, name, color):
        current_rows = self.overlay_tw.rowCount()
        self.overlay_tw.setRowCount(current_rows + 1)
        self.overlay_tw.blockSignals(True)

        show_cb = QtWidgets.QCheckBox()
        show_cb.setChecked(True)
        show_cb.stateChanged.connect(partial(self.show_cb_changed, show_cb))
        show_cb.setStyleSheet("background-color: transparent")
        self.overlay_tw.setCellWidget(current_rows, 0, show_cb)
        self.show_cbs.append(show_cb)

        color_button = FlatButton()
        color_button.setStyleSheet("background-color: " + color)
        color_button.clicked.connect(partial(self.color_btn_click, color_button))
        self.overlay_tw.setCellWidget(current_rows, 1, color_button)
        self.color_btns.append(color_button)

        name_item = QtWidgets.QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.overlay_tw.setItem(current_rows, 2, QtWidgets.QTableWidgetItem(name))

        self.overlay_tw.setColumnWidth(0, 20)
        self.overlay_tw.setColumnWidth(1, 25)
        self.overlay_tw.setRowHeight(current_rows, 25)
        self.select_overlay(current_rows)
        self.overlay_tw.blockSignals(False)

    def select_overlay(self, ind):
        if self.overlay_tw.rowCount() > 0:
            self.overlay_tw.selectRow(ind)

    def get_selected_overlay_row(self):
        selected = self.overlay_tw.selectionModel().selectedRows()
        try:
            row = selected[0].row()
        except IndexError:
            row = -1
        return row

    def remove_overlay(self, ind):
        self.overlay_tw.blockSignals(True)
        self.overlay_tw.removeRow(ind)
        self.overlay_tw.blockSignals(False)
        del self.show_cbs[ind]
        del self.color_btns[ind]

        if self.overlay_tw.rowCount() > ind:
            self.select_overlay(ind)
        else:
            self.select_overlay(self.overlay_tw.rowCount() - 1)

    def color_btn_click(self, button):
        self.color_btn_clicked.emit(self.color_btns.index(button), button)

    def show_cb_changed(self, checkbox):
        self.show_cb_state_changed.emit(self.show_cbs.index(checkbox), checkbox.isChecked())

    def show_cb_set_checked(self, ind, state):
        checkbox = self.show_cbs[ind]
        checkbox.setChecked(state)

    def show_cb_is_checked(self, ind):
        checkbox = self.show_cbs[ind]
        return checkbox.isChecked()

    def label_editingFinished(self, row, col):
        label_item = self.overlay_tw.item(row, col)
        self.name_changed.emit(row, str(label_item.text()))


class CorrectionsControlWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(CorrectionsControlWidget, self).__init__(*args, **kwargs)

        self._layout = QtWidgets.QVBoxLayout()

        self.cbn_seat_gb = QtWidgets.QGroupBox('cBN Seat Correction')
        self._cbn_seat_layout = QtWidgets.QGridLayout(self)
        self._cbn_seat_layout.setSpacing(6)

        self.anvil_thickness_txt = NumberTextField('2.3')
        self.seat_thickness_txt = NumberTextField('5.3')
        self.seat_inner_radius_txt = NumberTextField('0.4')
        self.seat_outer_radius_txt = NumberTextField('1.95')
        self.cell_tilt_txt = NumberTextField('0.0')
        self.cell_tilt_rotation_txt = NumberTextField('0.0')
        self.center_offset_txt = NumberTextField('0.0')
        self.center_offset_angle_txt = NumberTextField('0.0')
        self.anvil_absorption_length_txt = NumberTextField('13.7')
        self.seat_absorption_length_txt = NumberTextField('21.1')

        self.cbn_seat_plot_btn = CheckableFlatButton('Plot')

        self._cbn_seat_layout.addWidget(LabelAlignRight('Anvil d:'), 0, 0)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat r1:'), 0, 4)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Cell Tilt:'), 0, 8)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Offset:'), 0, 12)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Anvil AL:'), 0, 16)

        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat d:'), 1, 0)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat r2:'), 1, 4)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Tilt Rot:'), 1, 8)
        self._cbn_seat_layout.addWidget(LabelAlignRight(u"Offs. 2θ  :"), 1, 12)
        self._cbn_seat_layout.addWidget(LabelAlignRight('Seat AL:'), 1, 16)

        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 0, 2)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 0, 6)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 0, 14)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 1, 2)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel('mm'), 1, 6)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel(u'°'), 0, 10)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel(u'°'), 1, 10)
        self._cbn_seat_layout.addWidget(QtWidgets.QLabel(u'°'), 1, 14)

        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 3)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 7)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 11)
        self._cbn_seat_layout.addItem(HorizontalSpacerItem(3), 0, 15)

        self._cbn_seat_layout.addWidget(self.anvil_thickness_txt, 0, 1)
        self._cbn_seat_layout.addWidget(self.seat_thickness_txt, 1, 1)
        self._cbn_seat_layout.addWidget(self.seat_inner_radius_txt, 0, 5)
        self._cbn_seat_layout.addWidget(self.seat_outer_radius_txt, 1, 5)
        self._cbn_seat_layout.addWidget(self.cell_tilt_txt, 0, 9)
        self._cbn_seat_layout.addWidget(self.cell_tilt_rotation_txt, 1, 9)
        self._cbn_seat_layout.addWidget(self.center_offset_txt, 0, 13)
        self._cbn_seat_layout.addWidget(self.center_offset_angle_txt, 1, 13)
        self._cbn_seat_layout.addWidget(self.anvil_absorption_length_txt, 0, 17)
        self._cbn_seat_layout.addWidget(self.seat_absorption_length_txt, 1, 17)

        self._cbn_seat_layout.addWidget(self.cbn_seat_plot_btn, 0, 18, 2, 1)

        self.cbn_seat_gb.setLayout(self._cbn_seat_layout)

        self.oiadac_gb = QtWidgets.QGroupBox('Oblique Incidence Angle Detector Absorption Correction')
        self._oiadac_layout = QtWidgets.QHBoxLayout()

        self.detector_thickness_txt = NumberTextField('40')
        self.detector_absorption_length_txt = NumberTextField('465.5')
        self.oiadac_plot_btn = CheckableFlatButton('Plot')

        self._oiadac_layout.addWidget(LabelAlignRight('Det. Thickness:'))
        self._oiadac_layout.addWidget(self.detector_thickness_txt)
        self._oiadac_layout.addWidget(QtWidgets.QLabel('mm'))
        self._oiadac_layout.addSpacing(10)
        self._oiadac_layout.addWidget(LabelAlignRight('Abs. Length:'))
        self._oiadac_layout.addWidget(self.detector_absorption_length_txt)
        self._oiadac_layout.addWidget(QtWidgets.QLabel('um'))
        self._oiadac_layout.addWidget(self.oiadac_plot_btn)
        self._oiadac_layout.addSpacerItem(HorizontalSpacerItem())

        self.oiadac_gb.setLayout(self._oiadac_layout)

        self._layout.addWidget(self.cbn_seat_gb)
        self._layout.addWidget(self.oiadac_gb)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.cbn_seat_gb.setCheckable(True)
        self.cbn_seat_gb.setChecked(False)

        self.setStyleSheet("""
            QLineEdit {
                min-width: 50 px;
                max-width: 60 px;
            }
        """)

        self.cbn_seat_plot_btn.setMaximumHeight(150)
        self.oiadac_plot_btn.setMaximumHeight(150)
        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.detector_thickness_txt.setMinimumWidth(60)
        self.detector_thickness_txt.setMaximumWidth(60)
        self.detector_absorption_length_txt.setMinimumWidth(60)
        self.detector_absorption_length_txt.setMaximumWidth(60)


class BackgroundControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BackgroundControlWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.image_background_gb = QtWidgets.QGroupBox('Image Background', self)
        self._image_background_gb_layout = QtWidgets.QGridLayout(self.image_background_gb)
        self._image_background_gb_layout.setSpacing(6)

        self.load_image_btn = FlatButton('Load')
        self.filename_lbl = QtWidgets.QLabel('None')
        self.remove_image_btn = FlatButton('Remove')
        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()
        self.scale_step_txt = NumberTextField('0.01')
        self.offset_step_txt = NumberTextField('100')

        self._image_background_gb_layout.addWidget(self.load_image_btn, 0, 0)
        self._image_background_gb_layout.addWidget(self.remove_image_btn, 1, 0)
        self._image_background_gb_layout.addWidget(self.filename_lbl, 0, 1, 1, 8)
        self._image_background_gb_layout.addWidget(LabelAlignRight('Scale:'), 1, 1)
        self._image_background_gb_layout.addWidget(self.scale_sb, 1, 2)
        self._image_background_gb_layout.addWidget(self.scale_step_txt, 1, 3)
        self._image_background_gb_layout.addItem(HorizontalSpacerItem(), 1, 4)
        self._image_background_gb_layout.addWidget(LabelAlignRight('Offset:'), 1, 5)
        self._image_background_gb_layout.addWidget(self.offset_sb, 1, 6)
        self._image_background_gb_layout.addWidget(self.offset_step_txt, 1, 7)
        self._image_background_gb_layout.addItem(HorizontalSpacerItem(), 1, 8)

        self.image_background_gb.setLayout(self._image_background_gb_layout)

        self._layout.addWidget(self.image_background_gb)

        self.setLayout(self._layout)

        self.pattern_background_gb = QtWidgets.QGroupBox('Pattern Background')
        self._pattern_background_gb = QtWidgets.QGridLayout()

        self.smooth_with_sb = DoubleSpinBoxAlignRight()
        self.iterations_sb = SpinBoxAlignRight()
        self.poly_order_sb = SpinBoxAlignRight()
        self.x_range_min_txt = NumberTextField('0')
        self.x_range_max_txt = NumberTextField('50')
        self.inspect_btn = CheckableFlatButton('Inspect')

        self._smooth_layout = QtWidgets.QHBoxLayout()
        self._smooth_layout.addWidget(LabelAlignRight('Smooth Width:'))
        self._smooth_layout.addWidget(self.smooth_with_sb)
        self._smooth_layout.addWidget(LabelAlignRight('Iterations:'))
        self._smooth_layout.addWidget(self.iterations_sb)
        self._smooth_layout.addWidget(LabelAlignRight('Poly Order:'))
        self._smooth_layout.addWidget(self.poly_order_sb)

        self._range_layout = QtWidgets.QHBoxLayout()
        self._range_layout.addWidget(QtWidgets.QLabel('X-Range:'))
        self._range_layout.addWidget(self.x_range_min_txt)
        self._range_layout.addWidget(QtWidgets.QLabel('-'))
        self._range_layout.addWidget(self.x_range_max_txt)
        self._range_layout.addSpacerItem(HorizontalSpacerItem())

        self._pattern_background_gb.addLayout(self._smooth_layout, 0, 0)
        self._pattern_background_gb.addLayout(self._range_layout, 1, 0)

        self._pattern_background_gb.addWidget(self.inspect_btn, 0, 2, 2, 1)
        self._pattern_background_gb.addItem(HorizontalSpacerItem(), 0, 3, 2, 1)

        self.pattern_background_gb.setLayout(self._pattern_background_gb)

        self._layout.addWidget(self.pattern_background_gb)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.style_image_background_widgets()
        self.style_pattern_background_widgets()

    def style_image_background_widgets(self):
        step_txt_width = 70
        self.scale_step_txt.setMaximumWidth(step_txt_width)
        self.scale_step_txt.setMinimumWidth(step_txt_width)
        self.offset_step_txt.setMaximumWidth(step_txt_width)

        sb_width = 110
        self.scale_sb.setMaximumWidth(sb_width)
        self.scale_sb.setMinimumWidth(sb_width)
        self.offset_sb.setMaximumWidth(sb_width)
        self.offset_sb.setMinimumWidth(sb_width)

        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)
        self.scale_sb.setSingleStep(0.01)

        self.pattern_background_gb.setCheckable(True)
        self.pattern_background_gb.setChecked(False)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)

    def style_pattern_background_widgets(self):
        self.smooth_with_sb.setValue(0.100)
        self.smooth_with_sb.setMinimum(0)
        self.smooth_with_sb.setMaximum(10000000)
        self.smooth_with_sb.setSingleStep(0.005)
        self.smooth_with_sb.setDecimals(3)
        self.smooth_with_sb.setMaximumWidth(100)

        self.iterations_sb.setMaximum(99999)
        self.iterations_sb.setMinimum(1)
        self.iterations_sb.setValue(150)
        self.poly_order_sb.setMaximum(999999)
        self.poly_order_sb.setMinimum(1)
        self.poly_order_sb.setValue(50)

        self.x_range_min_txt.setMaximumWidth(70)
        self.x_range_max_txt.setMaximumWidth(70)

        self.inspect_btn.setMaximumHeight(150)


class OptionsWidget(QtWidgets.QWidget):
    def __init__(self):
        super(OptionsWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.integration_gb = QtWidgets.QGroupBox('Integration')
        self._integration_gb_layout = QtWidgets.QGridLayout()

        self.bin_count_txt = IntegerTextField('0')
        self.bin_count_cb = QtWidgets.QCheckBox('auto')
        self.supersampling_sb = SpinBoxAlignRight()

        self._integration_gb_layout.addWidget(LabelAlignRight('Number of Bins:'), 0, 0)
        self._integration_gb_layout.addWidget(LabelAlignRight('Supersampling:'), 1, 0)

        self._integration_gb_layout.addWidget(self.bin_count_txt, 0, 1)
        self._integration_gb_layout.addWidget(self.bin_count_cb, 0, 2)
        self._integration_gb_layout.addWidget(self.supersampling_sb, 1, 1)

        self.integration_gb.setLayout(self._integration_gb_layout)

        self._integration_layout = QtWidgets.QHBoxLayout()
        self._integration_layout.addWidget(self.integration_gb)
        self._integration_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._integration_layout)
        self._layout.addItem(VerticalSpacerItem())

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        max_width = 110
        self.bin_count_txt.setMaximumWidth(max_width)
        self.supersampling_sb.setMaximumWidth(max_width)

        self.supersampling_sb.setMinimum(1)
        self.supersampling_sb.setMaximum(20)
        self.supersampling_sb.setSingleStep(1)

        self.bin_count_txt.setEnabled(False)
        self.bin_count_cb.setChecked(True)
