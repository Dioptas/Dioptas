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

        self._layout = QtGui.QGridLayout()

        self.start_values_gb = QtGui.QGroupBox('Start values')
        self._gb_layout = QtGui.QGridLayout()

        self._gb_layout.addWidget(LabelAlignRight('Distance:'), 0, 0)
        self.distance_txt = NumberTextField('200')
        self.distance_cb = QtGui.QCheckBox()
        self.distance_cb.setChecked(True)
        self._gb_layout.addWidget(self.distance_txt, 0, 1)
        self._gb_layout.addWidget(QtGui.QLabel('mm'), 0, 2)
        self._gb_layout.addWidget(self.distance_cb, 0, 3)

        self._gb_layout.addWidget(LabelAlignRight('Wavelength:'), 1, 0)
        self.wavelength_txt = NumberTextField('0.3344')
        self.wavelength_cb = QtGui.QCheckBox()
        self._gb_layout.addWidget(self.wavelength_txt, 1, 1)
        self._gb_layout.addWidget(QtGui.QLabel('A'), 1, 2)
        self._gb_layout.addWidget(self.wavelength_cb, 1, 3)

        self._gb_layout.addWidget(LabelAlignRight('Polarization:'), 2, 0)
        self.polarization_txt = NumberTextField('0.99')
        self._gb_layout.addWidget(self.polarization_txt, 2, 1)

        self._gb_layout.addWidget(LabelAlignRight('Pixel width:'), 3, 0)
        self.pixel_width_txt = NumberTextField('72')
        self._gb_layout.addWidget(self.pixel_width_txt, 3, 1)
        self._gb_layout.addWidget(QtGui.QLabel('um'))

        self._gb_layout.addWidget(LabelAlignRight('Pixel height:'), 4, 0)
        self.pixel_height_txt = NumberTextField('72')
        self._gb_layout.addWidget(self.pixel_height_txt, 4, 1)
        self._gb_layout.addWidget(QtGui.QLabel('um'))

        self._gb_layout.addWidget(LabelAlignRight('Calibrant:'), 5, 0)
        self.calibrant_cb = QtGui.QComboBox()
        self._gb_layout.addWidget(self.calibrant_cb, 5, 1, 1, 2)

        self.start_values_gb.setLayout(self._gb_layout)

        self._layout.addWidget(self.start_values_gb, 0, 0, 1, 2)

        self.rotate_p90_btn = QtGui.QPushButton('Rotate +90')
        self.rotate_m90_btn = QtGui.QPushButton('Rotate -90')
        self._layout.addWidget(self.rotate_p90_btn, 1, 0)
        self._layout.addWidget(self.rotate_m90_btn, 1, 1)

        self.flip_horizontal_btn = QtGui.QPushButton('Flip horizontal')
        self.flip_vertical_btn = QtGui.QPushButton('Flip vertical')
        self._layout.addWidget(self.flip_horizontal_btn, 2, 0)
        self._layout.addWidget(self.flip_vertical_btn, 2, 1)

        self.reset_transformations_btn = QtGui.QPushButton('Reset transformations')
        self._layout.addWidget(self.reset_transformations_btn, 3, 0, 1, 2)

        self.setLayout(self._layout)


class NumberTextField(QtGui.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(NumberTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator())
        self.setAlignment(QtCore.Qt.AlignRight)


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
