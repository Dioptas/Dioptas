from PyQt4 import QtGui, QtCore
from pyqtgraph import GraphicsLayoutWidget

from widgets.plot_widgets import MaskImgWidget, CalibrationCakeWidget
from widgets.plot_widgets import SpectrumWidget


class CalibrationWidgetNew(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationWidgetNew, self).__init__(*args, **kwargs)

        self.calibration_display_widget = CalibrationDisplayWidget()
        self.calibration_control_widget = CalibrationControlWidget()

        self._main_splitter = QtGui.QSplitter()
        self._main_splitter.addWidget(self.calibration_display_widget)
        self._main_splitter.addWidget(self.calibration_control_widget)

        self._layout = QtGui.QHBoxLayout()
        self._layout.addWidget(self._main_splitter)
        self.setLayout(self._layout)


class CalibrationDisplayWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationDisplayWidget, self).__init__(*args, **kwargs)

        self._layout = QtGui.QVBoxLayout()

        self.img_layout_widget = GraphicsLayoutWidget()
        self.cake_layout_widget = GraphicsLayoutWidget()
        self.spectrum_layout_widget = GraphicsLayoutWidget()

        self.img_widget = MaskImgWidget(self.img_layout_widget)
        self.cake_widget = CalibrationCakeWidget(self.cake_layout_widget)
        self.spectrum_widget = SpectrumWidget(self.spectrum_layout_widget)

        self.tab_widget = QtGui.QTabWidget()
        self.tab_widget.addTab(self.img_layout_widget, 'Image')
        self.tab_widget.addTab(self.cake_layout_widget, 'Cake')
        self.tab_widget.addTab(self.spectrum_layout_widget, 'Cake')
        self._layout.addWidget(self.tab_widget)

        self._status_layout = QtGui.QHBoxLayout()
        self.calibrate_btn = QtGui.QPushButton("Calibrate")
        self.refine_btn = QtGui.QPushButton("Refine")
        self.position_lbl = QtGui.QLabel("position_lbl")

        self._status_layout.addWidget(self.calibrate_btn)
        self._status_layout.addWidget(self.refine_btn)
        self._status_layout.addSpacerItem(QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding,
                                                            QtGui.QSizePolicy.Minimum))
        self._status_layout.addWidget(self.position_lbl)
        self._layout.addLayout(self._status_layout)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self.calibrate_btn.setMinimumWidth(140)
        self.refine_btn.setMinimumWidth(140)


class CalibrationControlWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationControlWidget, self).__init__(*args, **kwargs)

        self._layout = QtGui.QVBoxLayout()

        self._file_layout = QtGui.QHBoxLayout()
        self.load_img_btn = QtGui.QPushButton("Load File")
        self.load_previous_img_btn = QtGui.QPushButton("<")
        self.load_next_img_btn = QtGui.QPushButton(">")

        self._file_layout.addWidget(self.load_img_btn)
        self._file_layout.addWidget(self.load_previous_img_btn)
        self._file_layout.addWidget(self.load_next_img_btn)

        self._layout.addLayout(self._file_layout)

        self.file_name_txt = QtGui.QLineEdit()
        self._layout.addWidget(self.file_name_txt)

        self.toolbox = QtGui.QToolBox()
        self.calibration_parameter_widget = CalibrationParameterWidget()
        self.toolbox.addItem(self.calibration_parameter_widget, "Calibration Parameter")
        self._layout.addWidget(self.toolbox)

        self.setLayout(self._layout)


class CalibrationParameterWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CalibrationParameterWidget, self).__init__(*args, **kwargs)

        self._layout = QtGui.QVBoxLayout()

        self.start_values_gb = StartValuesGroupBox()
        self.peak_selection_gb = PeakSelectionGroupBox()
        self.refinement_options_gb = RefinementOptionsGroupBox()

        self._layout.addWidget(self.start_values_gb)
        self._layout.addWidget(self.peak_selection_gb)
        self._layout.addWidget(self.refinement_options_gb)

        self.setLayout(self._layout)


class StartValuesGroupBox(QtGui.QGroupBox):
    def __init__(self, *args, **kwargs):
        super(StartValuesGroupBox, self).__init__('Start values', *args, **kwargs)

        self._layout = QtGui.QVBoxLayout()

        self._grid_layout1 = QtGui.QGridLayout()

        self._grid_layout1.addWidget(LabelAlignRight('Distance:'), 0, 0)
        self.distance_txt = NumberTextField('200')
        self.distance_cb = QtGui.QCheckBox()
        self.distance_cb.setChecked(True)
        self._grid_layout1.addWidget(self.distance_txt, 0, 1)
        self._grid_layout1.addWidget(QtGui.QLabel('mm'), 0, 2)
        self._grid_layout1.addWidget(self.distance_cb, 0, 3)

        self._grid_layout1.addWidget(LabelAlignRight('Wavelength:'), 1, 0)
        self.wavelength_txt = NumberTextField('0.3344')
        self.wavelength_cb = QtGui.QCheckBox()
        self._grid_layout1.addWidget(self.wavelength_txt, 1, 1)
        self._grid_layout1.addWidget(QtGui.QLabel('A'), 1, 2)
        self._grid_layout1.addWidget(self.wavelength_cb, 1, 3)

        self._grid_layout1.addWidget(LabelAlignRight('Polarization:'), 2, 0)
        self.polarization_txt = NumberTextField('0.99')
        self._grid_layout1.addWidget(self.polarization_txt, 2, 1)

        self._grid_layout1.addWidget(LabelAlignRight('Pixel width:'), 3, 0)
        self.pixel_width_txt = NumberTextField('72')
        self._grid_layout1.addWidget(self.pixel_width_txt, 3, 1)
        self._grid_layout1.addWidget(QtGui.QLabel('um'))

        self._grid_layout1.addWidget(LabelAlignRight('Pixel height:'), 4, 0)
        self.pixel_height_txt = NumberTextField('72')
        self._grid_layout1.addWidget(self.pixel_height_txt, 4, 1)
        self._grid_layout1.addWidget(QtGui.QLabel('um'))

        self._grid_layout1.addWidget(LabelAlignRight('Calibrant:'), 5, 0)
        self.calibrant_cb = QtGui.QComboBox()
        self._grid_layout1.addWidget(self.calibrant_cb, 5, 1, 1, 2)

        self._grid_layout2 = QtGui.QGridLayout()

        self.rotate_p90_btn = QtGui.QPushButton('Rotate +90')
        self.rotate_m90_btn = QtGui.QPushButton('Rotate -90')
        self._grid_layout2.addWidget(self.rotate_p90_btn, 1, 0)
        self._grid_layout2.addWidget(self.rotate_m90_btn, 1, 1)

        self.flip_horizontal_btn = QtGui.QPushButton('Flip horizontal')
        self.flip_vertical_btn = QtGui.QPushButton('Flip vertical')
        self._grid_layout2.addWidget(self.flip_horizontal_btn, 2, 0)
        self._grid_layout2.addWidget(self.flip_vertical_btn, 2, 1)

        self.reset_transformations_btn = QtGui.QPushButton('Reset transformations')
        self._grid_layout2.addWidget(self.reset_transformations_btn, 3, 0, 1, 2)

        self._layout.addLayout(self._grid_layout1)
        self._layout.addLayout(self._grid_layout2)

        self.setLayout(self._layout)


class PeakSelectionGroupBox(QtGui.QGroupBox):
    def __init__(self):
        super(PeakSelectionGroupBox, self).__init__('Peak Selection')

        self._layout = QtGui.QGridLayout()
        self._layout.addItem(QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding,
                                               QtGui.QSizePolicy.Minimum), 0, 0)
        self._layout.addWidget(LabelAlignRight('Current Ring Number:'), 0, 1, 1, 2)
        self.peak_num_sb = QtGui.QSpinBox()
        self._layout.addWidget(self.peak_num_sb, 0, 3)
        self._layout.addItem(QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding,
                                               QtGui.QSizePolicy.Minimum), 1, 0, 1, 2)
        self.automatic_peak_num_inc_cb = QtGui.QCheckBox('automatic increase')
        self.automatic_peak_num_inc_cb.setChecked(True)
        self._layout.addWidget(self.automatic_peak_num_inc_cb, 1, 2, 1, 2)

        self.automatic_peak_search_rb = QtGui.QRadioButton('automatic peak search')
        self.select_peak_rb = QtGui.QRadioButton('single peak search')
        self._layout.addWidget(self.automatic_peak_search_rb, 2, 0, 1, 4)
        self._layout.addWidget(self.select_peak_rb, 3, 0, 1, 4)

        self._layout.addWidget(LabelAlignRight('Search size:'), 4, 0)
        self.search_size_sb = QtGui.QSpinBox()
        self._layout.addWidget(self.search_size_sb, 4, 1)
        self._layout.addItem(QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding,
                                               QtGui.QSizePolicy.Minimum), 4, 2, 1, 2)

        self.clear_peaks_btn = QtGui.QPushButton("Clear All Peaks")
        self._layout.addWidget(self.clear_peaks_btn, 5, 0, 1, 4)

        self.setLayout(self._layout)


class RefinementOptionsGroupBox(QtGui.QGroupBox):
    def __init__(self):
        super(RefinementOptionsGroupBox, self).__init__('Refinement Options')

        self._layout = QtGui.QGridLayout()

        self.automatic_refinement_cb = QtGui.QCheckBox('automatic refinement')
        self._layout.addWidget(self.automatic_refinement_cb, 0, 0, 1, 2)

        self.use_mask_cb = QtGui.QCheckBox('use mask')
        self._layout.addWidget(self.use_mask_cb, 1, 0)

        self.mask_transparent_cb = QtGui.QCheckBox('transparent')
        self._layout.addWidget(self.mask_transparent_cb, 1, 1)

        self._layout.addWidget(LabelAlignRight('Peak Search Algorithm:'), 2, 0)
        self.peak_search_algorithm_cb = QtGui.QComboBox()
        self.peak_search_algorithm_cb.addItems(['Massif', 'Blob'])
        self._layout.addWidget(self.peak_search_algorithm_cb, 2, 1)

        self._layout.addWidget(LabelAlignRight('Delta 2Th:'), 3, 0)
        self.delta_tth_txt = NumberTextField('0.1')
        self._layout.addWidget(self.delta_tth_txt, 3, 1)

        self._layout.addWidget(LabelAlignRight('Intensity Mean Factor:'), 4, 0)
        self.intensity_mean_factor_sb = QtGui.QDoubleSpinBox()
        self.intensity_mean_factor_sb.setValue(3.0)
        self._layout.addWidget(self.intensity_mean_factor_sb, 4, 1)

        self._layout.addWidget(LabelAlignRight('Intensity Limit:'), 5, 0)
        self.intensity_limit_txt = NumberTextField('55000')
        self._layout.addWidget(self.intensity_limit_txt, 5, 1)

        self._layout.addWidget(LabelAlignRight('Number of rings:'))
        self.number_of_rings_txt = QtGui.QSpinBox()
        self.number_of_rings_txt.setValue(15)
        self._layout.addWidget(self.number_of_rings_txt)

        self.setLayout(self._layout)


class NumberTextField(QtGui.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(NumberTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelAlignRight(QtGui.QLabel):
    def __init__(self, *args, **kwargs):
        super(LabelAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)


if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = CalibrationWidgetNew()
    widget.show()
    widget.setWindowState(widget.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
    widget.activateWindow()
    widget.raise_()
    app.exec_()
