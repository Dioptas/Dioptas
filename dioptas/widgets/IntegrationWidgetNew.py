# -*- coding: utf8 -*-

import os

from PyQt4 import QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from widgets.plot_widgets.ImgWidget import IntegrationImgView
from widgets.plot_widgets import SpectrumWidget

from widgets.CustomWidgets import NumberTextField, IntegerTextField, LabelAlignRight, SpinBoxAlignRight, \
    DoubleSpinBoxAlignRight, FlatButton, CheckableFlatButton, HorizontalSpacerItem, VerticalSpacerItem

clicked_color = '#00DD00'


class IntegrationWidget(QtGui.QWidget):
    """
    Defines the main structure of the calibration widget, which is separated into two parts.
    Calibration Display Widget - shows the image and pattern
    Calibration Control Widget - shows all the controls on the right side of the widget
    """

    def __init__(self, *args, **kwargs):
        super(IntegrationWidget, self).__init__(*args, **kwargs)

        self.integration_image_widget = IntegrationImgWidget()
        self.integration_control_widget = IntegrationControlWidget()
        self.integration_pattern_widget = IntegrationPatternWidget()
        self.integration_status_widget = IntegrationStatusWidget()

        self._layout = QtGui.QVBoxLayout()

        self._vertical_splitter = QtGui.QSplitter()
        self._vertical_splitter.setOrientation(QtCore.Qt.Vertical)
        self._vertical_splitter.addWidget(self.integration_control_widget)
        self._vertical_splitter.addWidget(self.integration_pattern_widget)

        self._horizontal_splitter = QtGui.QSplitter()
        self._horizontal_splitter.setOrientation(QtCore.Qt.Horizontal)
        self._horizontal_splitter.addWidget(self.integration_image_widget)
        self._horizontal_splitter.addWidget(self._vertical_splitter)
        self._layout.addWidget(self._horizontal_splitter, 10)
        self._layout.addWidget(self.integration_status_widget, 0)
        self.setLayout(self._layout)


class IntegrationImgWidget(QtGui.QWidget):
    def __init__(self):
        super(IntegrationImgWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self._layout.addWidget(self.img_pg_layout)

        self._mouse_position_layout = QtGui.QHBoxLayout()

        self.mouse_position_widget = MouseCurrentAndClickedWidget()
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget()

        self._mouse_position_layout.addWidget(self.mouse_position_widget)
        self._mouse_position_layout.addSpacerItem(HorizontalSpacerItem())
        self._mouse_position_layout.addWidget(self.mouse_unit_widget)

        self._layout.addLayout(self._mouse_position_layout)

        self._control_layout = QtGui.QHBoxLayout()

        self.roi_btn = CheckableFlatButton('ROI')
        self.mode_btn = FlatButton('Cake')
        self.mask_btn = CheckableFlatButton('Mask')
        self.transparent_cb = QtGui.QCheckBox('trans')
        self.autoscale_btn = CheckableFlatButton('AutoScale')
        self.undock_btn = FlatButton('Undock')

        self._control_layout.addWidget(self.roi_btn)
        self._control_layout.addWidget(self.mode_btn)
        self._control_layout.addWidget(self.mask_btn)
        self._control_layout.addWidget(self.transparent_cb)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._control_layout.addWidget(self.autoscale_btn)
        self._control_layout.addWidget(self.undock_btn)

        self._layout.addLayout(self._control_layout)

        self.setLayout(self._layout)


class IntegrationControlWidget(QtGui.QTabWidget):
    def __init__(self):
        super(IntegrationControlWidget, self).__init__()

        self.img_control_widget = ImageControlWidget()
        self.pattern_control_widget = PatternControlWidget()
        self.phase_control_widget = PhaseControlWidget()
        self.overlay_control_widget = OverlayControlWidget()
        self.corrections_control_widget = CorrectionsControlWidget()
        self.background_control_widget = BackgroundControlWidget()
        self.integration_options_widget = OptionsWidget()

        self.addTab(self.img_control_widget, 'Image')
        self.addTab(self.pattern_control_widget, 'Pattern')
        self.addTab(self.phase_control_widget, 'Phase')
        self.addTab(self.overlay_control_widget, 'Overlay')
        self.addTab(self.corrections_control_widget, 'Cor')
        self.addTab(self.background_control_widget, 'Bkg')
        self.addTab(self.integration_options_widget, 'X')


class ImageControlWidget(QtGui.QWidget):
    def __init__(self):
        super(ImageControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self.file_widget = BrowseFileWidget(files='Image', checkbox_text='autoprocess')
        self.file_info_btn = FlatButton('File Info')

        self._layout.addWidget(self.file_widget)

        self._file_info_layout = QtGui.QHBoxLayout()
        self._file_info_layout.addWidget(self.file_info_btn)
        self._file_info_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(self._file_info_layout)
        self._layout.addSpacerItem(VerticalSpacerItem())

        self.setLayout(self._layout)


class PatternControlWidget(QtGui.QWidget):
    def __init__(self):
        super(PatternControlWidget, self).__init__()

        self._layout = QtGui.QGridLayout()

        self.file_widget = BrowseFileWidget(files='Pattern', checkbox_text='autocreate')

        self.xy_cb = QtGui.QCheckBox('.xy')
        self.xy_cb.setChecked(True)
        self.chi_cb = QtGui.QCheckBox('.chi')
        self.dat_cb = QtGui.QCheckBox('.dat')

        self._layout.addWidget(self.file_widget, 0, 0, 1, 2)

        self.pattern_types_gc = QtGui.QGroupBox('Pattern data types')
        self._pattern_layout = QtGui.QHBoxLayout()
        self._pattern_layout.addWidget(self.xy_cb)
        self._pattern_layout.addWidget(self.chi_cb)
        self._pattern_layout.addWidget(self.dat_cb)
        self.pattern_types_gc.setLayout(self._pattern_layout)
        self._layout.addWidget(self.pattern_types_gc, 1, 0)

        self._layout.addItem(VerticalSpacerItem(), 2, 0)

        self.setLayout(self._layout)


class PhaseControlWidget(QtGui.QWidget):
    def __init__(self):
        super(PhaseControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self._control_layout = QtGui.QHBoxLayout()
        self.add_btn = FlatButton('Add')
        self.edit_btn = FlatButton('Edit')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')

        self._control_layout.addWidget(self.add_btn)
        self._control_layout.addWidget(self.edit_btn)
        self._control_layout.addWidget(self.delete_btn)
        self._control_layout.addWidget(self.clear_btn)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(self._control_layout)

        self.parameter_widget = QtGui.QWidget()
        self._parameter_layout = QtGui.QGridLayout()
        self.pressure_sb = DoubleSpinBoxAlignRight()
        self.temperature_sb = DoubleSpinBoxAlignRight()
        self.pressure_step_txt = NumberTextField('0.5')
        self.temperature_step_txt = NumberTextField('100')
        self.apply_to_all_cb = QtGui.QCheckBox('Apply to all phases')
        self.show_in_spectrum_cb = QtGui.QCheckBox('Show in Spectrum')

        self._parameter_layout.addWidget(QtGui.QLabel('Parameter'), 0, 1)
        self._parameter_layout.addWidget(QtGui.QLabel('Step'), 0, 3)
        self._parameter_layout.addWidget(QtGui.QLabel('P:'), 1, 0)
        self._parameter_layout.addWidget(QtGui.QLabel('T:'), 2, 0)
        self._parameter_layout.addWidget(QtGui.QLabel('GPa'), 1, 2)
        self._parameter_layout.addWidget(QtGui.QLabel('K'), 2, 2)

        self._parameter_layout.addWidget(self.pressure_sb, 1, 1)
        self._parameter_layout.addWidget(self.pressure_step_txt, 1, 3)
        self._parameter_layout.addWidget(self.temperature_sb, 2, 1)
        self._parameter_layout.addWidget(self.temperature_step_txt, 2, 3)

        self._parameter_layout.addWidget(self.apply_to_all_cb, 3, 0, 1, 5)
        self._parameter_layout.addWidget(self.show_in_spectrum_cb, 4, 0, 1, 5)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0)
        self.parameter_widget.setLayout(self._parameter_layout)

        self._body_layout = QtGui.QHBoxLayout()

        self.phase_tw = QtGui.QTableWidget()
        self._body_layout.addWidget(self.phase_tw, 10)
        self._body_layout.addWidget(self.parameter_widget, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.phase_tw.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.MinimumExpanding)
        self.parameter_widget.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        self.phase_tw.setMinimumHeight(130)

        self.temperature_step_txt.setMaximumWidth(60)
        self.pressure_step_txt.setMaximumWidth(60)
        self.pressure_sb.setMinimumWidth(100)

        self.pressure_sb.setMaximum(999999)
        self.pressure_sb.setMinimum(0)
        self.pressure_sb.setValue(0)

        self.temperature_sb.setMaximum(99999999)
        self.temperature_sb.setMinimum(0)
        self.temperature_sb.setValue(298)


class OverlayControlWidget(QtGui.QWidget):
    def __init__(self):
        super(OverlayControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self._control_layout = QtGui.QHBoxLayout()
        self.add_btn = FlatButton('Add')
        self.delete_btn = FlatButton('Delete')
        self.clear_btn = FlatButton('Clear')

        self._control_layout.addWidget(self.add_btn)
        self._control_layout.addWidget(self.delete_btn)
        self._control_layout.addWidget(self.clear_btn)
        self._control_layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addLayout(self._control_layout)

        self._parameter_layout = QtGui.QGridLayout()

        self.scale_sb = DoubleSpinBoxAlignRight()
        self.offset_sb = DoubleSpinBoxAlignRight()
        self.scale_step_txt = NumberTextField('0.01')
        self.offset_step_txt = NumberTextField('100')
        self.waterfall_separation_txt = NumberTextField('100')
        self.waterfall_btn = FlatButton('Waterfall')
        self.waterfall_reset_btn = FlatButton('Reset')
        self.set_as_background_btn = CheckableFlatButton('Set as Background')

        self._parameter_layout.addWidget(QtGui.QLabel('Step'), 0, 2)
        self._parameter_layout.addWidget(LabelAlignRight('Scale:'), 1, 0)
        self._parameter_layout.addWidget(LabelAlignRight('Offset:'), 2, 0)

        self._parameter_layout.addWidget(self.scale_sb, 1, 1)
        self._parameter_layout.addWidget(self.scale_step_txt, 1, 2)
        self._parameter_layout.addWidget(self.offset_sb, 2, 1)
        self._parameter_layout.addWidget(self.offset_step_txt, 2, 2)

        self._parameter_layout.addItem(VerticalSpacerItem(), 3, 0, 1, 3)

        self._waterfall_layout = QtGui.QHBoxLayout()
        self._waterfall_layout.addWidget(self.waterfall_btn)
        self._waterfall_layout.addWidget(self.waterfall_separation_txt)
        self._waterfall_layout.addWidget(self.waterfall_reset_btn)
        self._parameter_layout.addLayout(self._waterfall_layout, 4, 0, 1, 3)
        self._parameter_layout.addItem(VerticalSpacerItem(), 5, 0, 1, 3)

        self._background_layout = QtGui.QHBoxLayout()
        self._background_layout.addSpacerItem(HorizontalSpacerItem())
        self._background_layout.addWidget(self.set_as_background_btn)
        self._parameter_layout.addLayout(self._background_layout, 6, 0, 1, 3)

        self._body_layout = QtGui.QHBoxLayout()
        self.overlay_tw = QtGui.QTableWidget()
        self._body_layout.addWidget(self.overlay_tw, 10)
        self._body_layout.addLayout(self._parameter_layout, 0)

        self._layout.addLayout(self._body_layout)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        step_txt_width = 70
        self.scale_step_txt.setMaximumWidth(step_txt_width)
        self.scale_step_txt.setMinimumWidth(step_txt_width)
        self.offset_step_txt.setMaximumWidth(step_txt_width)
        self.waterfall_separation_txt.setMaximumWidth(step_txt_width)

        sb_width = 110
        self.scale_sb.setMaximumWidth(sb_width)
        self.scale_sb.setMinimumWidth(sb_width)
        self.offset_sb.setMaximumWidth(sb_width)
        self.offset_sb.setMinimumWidth(sb_width)

        self.scale_sb.setMinimum(-9999999)
        self.scale_sb.setMaximum(9999999)
        self.scale_sb.setValue(1)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)


class CorrectionsControlWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CorrectionsControlWidget, self).__init__(*args, **kwargs)

        self._layout = QtGui.QVBoxLayout()

        self.cbn_seat_gb = QtGui.QGroupBox('cBN Seat Correction')
        self._cbn_seat_layout = QtGui.QGridLayout()

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

        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 0, 2)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 0, 6)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 0, 14)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 1, 2)
        self._cbn_seat_layout.addWidget(QtGui.QLabel('mm'), 1, 6)
        self._cbn_seat_layout.addWidget(QtGui.QLabel(u'°'), 0, 10)
        self._cbn_seat_layout.addWidget(QtGui.QLabel(u'°'), 1, 10)
        self._cbn_seat_layout.addWidget(QtGui.QLabel(u'°'), 1, 14)

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


        self.oiadac_gb = QtGui.QGroupBox('Oblique Incidence Angle Detector Absorption Correction')
        self._oiadac_layout = QtGui.QHBoxLayout()

        self.detector_thickness_txt = NumberTextField('40')
        self.detector_absorption_length_txt = NumberTextField('465.5')
        self.oiadac_plot_btn = CheckableFlatButton('Plot')

        self._oiadac_layout.addWidget(LabelAlignRight('Det. Thickness:'))
        self._oiadac_layout.addWidget(self.detector_thickness_txt)
        self._oiadac_layout.addWidget(QtGui.QLabel('mm'))
        self._oiadac_layout.addSpacing(10)
        self._oiadac_layout.addWidget(LabelAlignRight('Abs. Length:'))
        self._oiadac_layout.addWidget(self.detector_absorption_length_txt)
        self._oiadac_layout.addWidget(QtGui.QLabel('um'))
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

        txt_width = 50
        self.anvil_thickness_txt.setMinimumWidth(txt_width)
        self.seat_thickness_txt.setMinimumWidth(txt_width)
        self.seat_inner_radius_txt.setMinimumWidth(txt_width)
        self.seat_outer_radius_txt.setMinimumWidth(txt_width)
        self.cell_tilt_txt.setMinimumWidth(txt_width)
        self.cell_tilt_rotation_txt.setMinimumWidth(txt_width)
        self.center_offset_txt.setMinimumWidth(txt_width)
        self.center_offset_angle_txt.setMinimumWidth(txt_width)
        self.anvil_absorption_length_txt.setMinimumWidth(txt_width)
        self.seat_absorption_length_txt.setMinimumWidth(txt_width)

        self.anvil_thickness_txt.setMaximumWidth(txt_width)
        self.seat_thickness_txt.setMaximumWidth(txt_width)
        self.seat_inner_radius_txt.setMaximumWidth(txt_width)
        self.seat_outer_radius_txt.setMaximumWidth(txt_width)
        self.cell_tilt_txt.setMaximumWidth(txt_width)
        self.cell_tilt_rotation_txt.setMaximumWidth(txt_width)
        self.center_offset_txt.setMaximumWidth(txt_width)
        self.center_offset_angle_txt.setMaximumWidth(txt_width)
        self.anvil_absorption_length_txt.setMaximumWidth(txt_width)
        self.seat_absorption_length_txt.setMaximumWidth(txt_width)

        self.cbn_seat_plot_btn.setMaximumHeight(150)


        self.oiadac_gb.setCheckable(True)
        self.oiadac_gb.setChecked(False)
        self.detector_thickness_txt.setMinimumWidth(60)
        self.detector_thickness_txt.setMaximumWidth(60)
        self.detector_absorption_length_txt.setMinimumWidth(60)
        self.detector_absorption_length_txt.setMaximumWidth(60)




class BackgroundControlWidget(QtGui.QWidget):
    def __init__(self):
        super(BackgroundControlWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self.image_background_gb = QtGui.QGroupBox('Image Background')
        self._image_background_gb_layout = QtGui.QGridLayout()

        self.load_image_btn = FlatButton('Load')
        self.filename_lbl = QtGui.QLabel('')
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

        self._layout.addSpacerItem(VerticalSpacerItem())
        self.setLayout(self._layout)

        self.pattern_background_gb = QtGui.QGroupBox('Pattern Background')
        self._pattern_background_gb = QtGui.QGridLayout()

        self.smooth_with_sb = DoubleSpinBoxAlignRight()
        self.iterations_sb = SpinBoxAlignRight()
        self.poly_order_sb = SpinBoxAlignRight()
        self.x_range_min_txt = NumberTextField('0')
        self.x_range_max_txt = NumberTextField('50')
        self.inspect_btn = CheckableFlatButton('Inspect')

        self._smooth_layout = QtGui.QHBoxLayout()
        self._smooth_layout.addWidget(LabelAlignRight('Smooth Width:'))
        self._smooth_layout.addWidget(self.smooth_with_sb)
        self._smooth_layout.addWidget(LabelAlignRight('Iterations:'))
        self._smooth_layout.addWidget(self.iterations_sb)
        self._smooth_layout.addWidget(LabelAlignRight('Poly Order:'))
        self._smooth_layout.addWidget(self.poly_order_sb)

        self._range_layout = QtGui.QHBoxLayout()
        self._range_layout.addWidget(QtGui.QLabel('X-Range:'))
        self._range_layout.addWidget(self.x_range_min_txt)
        self._range_layout.addWidget(QtGui.QLabel('-'))
        self._range_layout.addWidget(self.x_range_max_txt)
        self._range_layout.addSpacerItem(HorizontalSpacerItem())

        self._pattern_background_gb.addLayout(self._smooth_layout, 0, 0)
        self._pattern_background_gb.addLayout(self._range_layout, 1, 0)

        self._pattern_background_gb.addWidget(self.inspect_btn, 0, 2, 2, 1)
        self._pattern_background_gb.addItem(HorizontalSpacerItem(), 0, 3, 2, 1)

        self.pattern_background_gb.setLayout(self._pattern_background_gb)

        self._layout.addWidget(self.pattern_background_gb)

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

        self.pattern_background_gb.setCheckable(True)
        self.pattern_background_gb.setChecked(False)

        self.offset_sb.setMaximum(999999998)
        self.offset_sb.setMinimum(-99999999)

    def style_pattern_background_widgets(self):
        self.smooth_with_sb.setValue(0.100)
        self.smooth_with_sb.setMinimum(0)
        self.smooth_with_sb.setMaximum(10000000)
        self.smooth_with_sb.setSingleStep(0.02)
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


class OptionsWidget(QtGui.QWidget):
    def __init__(self):
        super(OptionsWidget, self).__init__()

        self._layout = QtGui.QGridLayout()

        self.integration_gb = QtGui.QGroupBox('Integration')
        self._integration_layout = QtGui.QGridLayout()

        self.bin_count_txt = IntegerTextField('0')
        self.bin_count_cb = QtGui.QCheckBox('auto')
        self.supersampling_sb = SpinBoxAlignRight()

        self._integration_layout.addWidget(LabelAlignRight('Number of Bins:'), 0, 0)
        self._integration_layout.addWidget(LabelAlignRight('Supersampling:'), 1, 0)

        self._integration_layout.addWidget(self.bin_count_txt, 0, 1)
        self._integration_layout.addWidget(self.bin_count_cb, 0, 2)

        self._integration_layout.addWidget(self.supersampling_sb, 1, 1)

        self.integration_gb.setLayout(self._integration_layout)

        self._layout.addWidget(self.integration_gb, 0, 0)
        self._layout.addItem(HorizontalSpacerItem(), 0, 1)
        self._layout.addItem(VerticalSpacerItem(), 1, 0, 1, 2)

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

class BrowseFileWidget(QtGui.QWidget):
    def __init__(self, files, checkbox_text):
        super(BrowseFileWidget, self).__init__()

        self._layout = QtGui.QGridLayout()

        self.load_btn = FlatButton('Load {}(s)'.format(files))
        self.file_cb = QtGui.QCheckBox(checkbox_text)
        self.next_btn = FlatButton('>')
        self.previous_btn = FlatButton('<')
        self.step_txt = QtGui.QLineEdit('1')
        self.step_txt.setValidator(QtGui.QIntValidator())
        self.browse_by_name_rb = QtGui.QRadioButton('By Name')
        self.browse_by_name_rb.setChecked(True)
        self.browse_by_time_rb = QtGui.QRadioButton('By Time')
        self.directory_txt = QtGui.QLineEdit('')
        self.directory_btn = FlatButton('...')
        self.file_txt = QtGui.QLineEdit('')

        self._layout.addWidget(self.load_btn, 0, 0)
        self._layout.addWidget(self.file_cb, 1, 0)

        self._layout.addWidget(self.previous_btn, 0, 1)
        self._layout.addWidget(self.next_btn, 0, 2)
        self._step_layout = QtGui.QHBoxLayout()
        self._step_layout.addWidget(LabelAlignRight('Step:'))
        self._step_layout.addWidget(self.step_txt)
        self._layout.addLayout(self._step_layout, 1, 1, 1, 2)

        self._layout.addWidget(self.browse_by_name_rb, 0, 3)
        self._layout.addWidget(self.browse_by_time_rb, 1, 3)

        self._layout.addWidget(self.file_txt, 0, 4, 1, 2)
        self._layout.addWidget(self.directory_txt, 1, 4)
        self._layout.addWidget(self.directory_btn, 1, 5)

        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.load_btn.setMaximumWidth(120)
        self.load_btn.setMinimumWidth(120)
        maximum_width = 40

        self.next_btn.setMaximumWidth(maximum_width)
        self.previous_btn.setMaximumWidth(maximum_width)
        self.directory_btn.setMaximumWidth(maximum_width)

        self.step_txt.setMaximumWidth(30)


class IntegrationPatternWidget(QtGui.QWidget):
    def __init__(self):
        super(IntegrationPatternWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self._top_control_layout = QtGui.QHBoxLayout()

        self.save_image_btn = FlatButton('Save Image')
        self.save_pattern_btn = FlatButton('Save Pattern')
        self.as_overlay_btn = FlatButton('As Overlay')
        self.as_bkg_btn = FlatButton('As Bkg')
        self.load_calibration_btn = FlatButton('Load Calibration')
        self.calibration_lbl = LabelAlignRight('None')

        self._top_control_layout.addWidget(self.save_image_btn)
        self._top_control_layout.addWidget(self.save_pattern_btn)
        self._top_control_layout.addWidget(self.as_overlay_btn)
        self._top_control_layout.addWidget(self.as_bkg_btn)
        self._top_control_layout.addSpacerItem(HorizontalSpacerItem())
        self._top_control_layout.addWidget(self.load_calibration_btn)
        self._top_control_layout.addWidget(self.calibration_lbl)

        self._layout.addLayout(self._top_control_layout)

        self._right_control_layout = QtGui.QVBoxLayout()

        self.tth_btn = CheckableFlatButton(u"2θ")
        self.q_btn = CheckableFlatButton('Q')
        self.d_btn = CheckableFlatButton('d')
        self.background_btn = CheckableFlatButton('bg')
        self.antialias_btn = CheckableFlatButton('AA')
        self.auto_range_btn = CheckableFlatButton('A')

        self._right_control_layout.addWidget(self.tth_btn)
        self._right_control_layout.addWidget(self.q_btn)
        self._right_control_layout.addWidget(self.d_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.background_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.antialias_btn)
        self._right_control_layout.addSpacerItem(VerticalSpacerItem())
        self._right_control_layout.addWidget(self.auto_range_btn)

        self._central_layout = QtGui.QHBoxLayout()

        self.spectrum_pg_layout = GraphicsLayoutWidget()
        self.spectrum_view = SpectrumWidget(self.spectrum_pg_layout)

        self._central_layout.addWidget(self.spectrum_pg_layout)
        self._central_layout.addLayout(self._right_control_layout)
        self._layout.addLayout(self._central_layout)

        self.setLayout(self._layout)


class IntegrationStatusWidget(QtGui.QWidget):
    def __init__(self):
        super(IntegrationStatusWidget, self).__init__()

        self._layout = QtGui.QHBoxLayout()

        self.mouse_pos_widget = MouseCurrentAndClickedWidget()
        self.mouse_unit_widget = MouseUnitCurrentAndClickedWidget()
        self.bkg_name_lbl = LabelAlignRight('')

        self._layout.addWidget(self.mouse_pos_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.mouse_unit_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.bkg_name_lbl)

        self.setLayout(self._layout)


class MouseCurrentAndClickedWidget(QtGui.QWidget):
    def __init__(self):
        super(MouseCurrentAndClickedWidget, self).__init__()

        self._layout = QtGui.QVBoxLayout()

        self.cur_pos_widget = MousePositionWidget()
        self.clicked_pos_widget = MousePositionWidget(clicked_color)

        self._layout.addWidget(self.cur_pos_widget)
        self._layout.addWidget(self.clicked_pos_widget)

        self.setLayout(self._layout)


class MousePositionWidget(QtGui.QWidget):
    def __init__(self, color=None):
        super(MousePositionWidget, self).__init__()

        self._layout = QtGui.QHBoxLayout()

        self.x_pos_lbl = LabelAlignRight('X:')
        self.y_pos_lbl = LabelAlignRight('Y:')
        self.int_lbl = LabelAlignRight('I:')

        self._layout.addWidget(self.x_pos_lbl)
        self._layout.addWidget(self.y_pos_lbl)
        self._layout.addWidget(self.int_lbl)

        self.setLayout(self._layout)

        if color is not None:
            style_str = 'color: {};'.format(color)
            self.x_pos_lbl.setStyleSheet(style_str)
            self.y_pos_lbl.setStyleSheet(style_str)
            self.int_lbl.setStyleSheet(style_str)


class MouseUnitCurrentAndClickedWidget(QtGui.QWidget):
    def __init__(self):
        super(MouseUnitCurrentAndClickedWidget, self).__init__()
        self._layout = QtGui.QVBoxLayout()

        self.cur_unit_widget = MouseUnitWidget()
        self.clicked_unit_widget = MouseUnitWidget(clicked_color)

        self._layout.addWidget(self.cur_unit_widget)
        self._layout.addWidget(self.clicked_unit_widget)

        self.setLayout(self._layout)


class MouseUnitWidget(QtGui.QWidget):
    def __init__(self, color=None):
        super(MouseUnitWidget, self).__init__()

        self._layout = QtGui.QHBoxLayout()

        self.tth_lbl = LabelAlignRight(u"2θ:")
        self.q_lbl = LabelAlignRight('Q:')
        self.d_lbl = LabelAlignRight('d:')
        self.azi_lbl = LabelAlignRight('X:')

        self._layout.addWidget(self.tth_lbl)
        self._layout.addWidget(self.q_lbl)
        self._layout.addWidget(self.d_lbl)
        self._layout.addWidget(self.azi_lbl)

        self.setLayout(self._layout)

        if color is not None:
            style_str = 'color: {};'.format(color)
            self.tth_lbl.setStyleSheet(style_str)
            self.d_lbl.setStyleSheet(style_str)
            self.q_lbl.setStyleSheet(style_str)
            self.azi_lbl.setStyleSheet(style_str)


if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = IntegrationWidget()
    widget.show()
    # widget.setWindowState(widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
    # widget.activateWindow()
    # widget.raise_()
    app.exec_()
