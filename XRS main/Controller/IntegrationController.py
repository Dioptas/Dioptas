from StdSuites.Standard_Suite import _3c_

__author__ = 'Clemens Prescher'
import sys
import os

from PyQt4 import QtGui, QtCore
from Views.IntegrationView import IntegrationView
from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.CalibrationData import CalibrationData
from Data.SpectrumData import SpectrumData
from Data.HelperModule import get_base_name
import pyqtgraph as pg
import time
## Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)
import pyFAI.units
import numpy as np


class IntegrationController(object):
    def __init__(self, view=None, img_data=None, mask_data=None, calibration_data=None, spectrum_data=None):

        if view == None:
            self.view = IntegrationView()
        else:
            self.view = view

        if img_data == None:
            self.img_data = ImgData()
        else:
            self.img_data = img_data

        if mask_data == None:
            self.mask_data = MaskData()
        else:
            self.mask_data = mask_data

        if calibration_data == None:
            self.calibration_data = CalibrationData(self.img_data)
        else:
            self.calibration_data = calibration_data

        if spectrum_data == None:
            self.spectrum_data = SpectrumData()
        else:
            self.spectrum_data = spectrum_data

        self.initialize()
        self.create_sub_controller()

        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def initialize(self):
        self.img_data.load('ExampleData/Mg2SiO4_ambient_001.tif')
        self.mask_data.set_dimension(self.img_data.get_img_data().shape)

    def create_sub_controller(self):
        self.spectrum_controller = IntegrationSpectrumController(self.view, self.img_data, self.mask_data,
                                                                 self.calibration_data, self.spectrum_data)
        self.file_controller = IntegrationFileController(self.view, self.img_data, self.mask_data)
        self.overlay_controller = IntegrationOverlayController(self.view, self.spectrum_data)


class IntegrationOverlayController(object):
    def __init__(self, view, spectrum_data):
        self.view = view
        self.spectrum_data = spectrum_data
        self.overlay_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.overlay_add_btn, self.add_overlay)
        self.connect_click_function(self.view.overlay_del_btn, self.del_overlay)
        self.view.overlay_clear_btn.clicked.connect(self.clear_overlays)
        self.view.overlay_lw.currentItemChanged.connect(self.overlay_item_changed)
        self.view.overlay_scale_step_txt.editingFinished.connect(self.update_overlay_scale_step)
        self.view.overlay_offset_step_txt.editingFinished.connect(self.update_overlay_offset_step)
        self.view.overlay_scale_sb.valueChanged.connect(self.overlay_scale_sb_changed)
        self.view.overlay_offset_sb.valueChanged.connect(self.overlay_offset_sb_changed)

        self.view.overlay_set_as_bkg_btn.clicked.connect(self.overlay_set_as_bkg_btn_clicked)
        self.view.overlay_show_cb.clicked.connect(self.overlay_show_cb_changed)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def add_overlay(self, filename=None):
        dialog = QtGui.QFileDialog()
        dialog.setFileMode(QtGui.QFileDialog.ExistingFiles)
        dialog.setWindowTitle("Load Overlay(s).")

        if filename is None:
            if (dialog.exec_()):
                filenames = dialog.selectedFiles()
                for filename in filenames:
                    filename = str(filename)
                    self.spectrum_data.add_overlay_file(filename)
                    self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
                    self.overlay_lw_items.append(self.view.overlay_lw.addItem(get_base_name(filename)))
                    self.view.overlay_lw.setCurrentRow(len(self.spectrum_data.overlays) - 1)

        else:
            self.spectrum_data.add_overlay_file(filename)
            self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
            self.overlay_lw_items.append(self.view.overlay_lw.addItem(get_base_name(filename)))
            self.view.overlay_lw.setCurrentRow(len(self.spectrum_data.overlays) - 1)

    def del_overlay(self):
        cur_ind = self.view.overlay_lw.currentRow()
        if cur_ind >= 0:
            self.view.overlay_lw.takeItem(cur_ind)
            self.view.overlay_lw.setCurrentRow(cur_ind - 1)
            self.spectrum_data.overlays.remove(self.spectrum_data.overlays[cur_ind])
            self.view.spectrum_view.del_overlay(cur_ind)
            if self.spectrum_data.bkg_ind > cur_ind:
                self.spectrum_data.bkg_ind -= 1
            elif self.spectrum_data.bkg_ind == cur_ind:
                self.spectrum_data.spectrum.reset_background()
                self.spectrum_data.bkg_ind = -1
                self.spectrum_data.notify()

    def clear_overlays(self):
        while self.view.overlay_lw.currentRow() > -1:
            self.del_overlay()

    def update_overlay_scale_step(self):
        value = np.double(self.view.overlay_scale_step_txt.text())
        self.view.overlay_scale_sb.setSingleStep(value)

    def update_overlay_offset_step(self):
        value = np.double(self.view.overlay_offset_step_txt.text())
        self.view.overlay_offset_sb.setSingleStep(value)

    def overlay_item_changed(self):
        cur_ind = self.view.overlay_lw.currentRow()
        self.view.overlay_scale_sb.setValue(self.spectrum_data.overlays[cur_ind].scaling)
        self.view.overlay_offset_sb.setValue(self.spectrum_data.overlays[cur_ind].offset)
        # self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)
        self.view.overlay_show_cb.setChecked(self.view.spectrum_view.overlay_show[cur_ind])
        if cur_ind == self.spectrum_data.bkg_ind:
            self.view.overlay_set_as_bkg_btn.setChecked(True)
        else:
            self.view.overlay_set_as_bkg_btn.setChecked(False)

    def overlay_scale_sb_changed(self, value):
        cur_ind = self.view.overlay_lw.currentRow()
        self.spectrum_data.overlays[cur_ind].scaling = value
        self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)
        if self.view.overlay_set_as_bkg_btn.isChecked():
            self.spectrum_data.notify()

    def overlay_offset_sb_changed(self, value):
        cur_ind = self.view.overlay_lw.currentRow()
        self.spectrum_data.overlays[cur_ind].offset = value
        self.view.spectrum_view.update_overlay(self.spectrum_data.overlays[cur_ind], cur_ind)
        if self.view.overlay_set_as_bkg_btn.isChecked():
            self.spectrum_data.notify()

    def overlay_set_as_bkg_btn_clicked(self):
        cur_ind = self.view.overlay_lw.currentRow()
        if not self.view.overlay_set_as_bkg_btn.isChecked():
            self.spectrum_data.bkg_ind = -1
            self.spectrum_data.spectrum.reset_background()
            self.view.spectrum_view.show_overlay(cur_ind)
            self.view.overlay_show_cb.setChecked(True)
            self.spectrum_data.notify()
        else:
            if self.spectrum_data.bkg_ind is not -1:
                self.view.spectrum_view.show_overlay(self.spectrum_data.bkg_ind)  #show the old overlay again
            self.spectrum_data.bkg_ind = cur_ind
            self.spectrum_data.spectrum.set_background(self.spectrum_data.overlays[cur_ind])
            self.view.spectrum_view.hide_overlay(cur_ind)
            self.view.overlay_show_cb.setChecked(False)
            self.spectrum_data.notify()

    def overlay_show_cb_changed(self):
        cur_ind = self.view.overlay_lw.currentRow()
        state = self.view.overlay_show_cb.isChecked()
        if state:
            self.view.spectrum_view.show_overlay(cur_ind)
        else:
            self.view.spectrum_view.hide_overlay(cur_ind)


class IntegrationSpectrumController(object):
    def __init__(self, view, img_data, mask_data, calibration_data, spectrum_data):
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.calibration_data = calibration_data
        self.spectrum_data = spectrum_data

        self.create_subscriptions()
        self.spectrum_working_dir = 'ExampleData/spectra'
        self.set_status()

        self.create_signals()

    def create_subscriptions(self):
        self.img_data.subscribe(self.image_changed)
        self.spectrum_data.subscribe(self.plot_spectra)

    def set_status(self):
        self.autosave = True
        self.unit = pyFAI.units.TTH_DEG

    def create_signals(self):
        self.connect_click_function(self.view.spec_autocreate_cb, self.autocreate_cb_changed)
        self.connect_click_function(self.view.spec_load_btn, self.load)
        self.connect_click_function(self.view.spec_previous_btn, self.load_previous)
        self.connect_click_function(self.view.spec_next_btn, self.load_next)
        self.connect_click_function(self.view.spec_directory_btn, self.spec_directory_btn_click)
        self.connect_click_function(self.view.spec_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.view.spec_browse_by_time_rb, self.set_iteration_mode_time)
        self.view.connect(self.view.spec_directory_txt, QtCore.SIGNAL('editingFinished()'),
                          self.spec_directory_txt_changed)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def image_changed(self):
        if self.calibration_data.is_calibrated:
            if self.autosave:
                filename = os.path.join(self.spectrum_working_dir,
                                        os.path.basename(self.img_data.filename).split('.')[:-1][0] + '.xy')
                self.view.spec_next_btn.setEnabled(True)
                self.view.spec_previous_btn.setEnabled(True)
                self.view.spec_filename_lbl.setText(os.path.basename(filename))
                self.view.spec_directory_txt.setText(os.path.dirname(filename))
            else:
                self.view.spec_next_btn.setEnabled(False)
                self.view.spec_previous_btn.setEnabled(False)
                filename = None
                self.view.spec_filename_lbl.setText('No File saved or selected')

            tth, I = self.calibration_data.integrate_1d(filename=filename)
            spectrum_filename = os.path.join(self.spectrum_working_dir,
                                             os.path.basename(self.img_data.filename).split('.')[:-1][0] + '.xy')
            self.spectrum_data.set_spectrum(tth, I, spectrum_filename)


    def plot_spectra(self):
        x, y = self.spectrum_data.spectrum.data
        self.view.spectrum_view.plot_data(x, y, self.spectrum_data.spectrum.name)


    def load(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load Spectrum",
                                                             directory=self.spectrum_working_dir))
        if filename is not '':
            self.spectrum_working_dir = os.path.dirname(filename)
            self.view.spec_filename_lbl.setText(os.path.basename(filename))
            self.spectrum_data.load_spectrum(filename)
            self.view.spec_next_btn.setEnabled(True)
            self.view.spec_previous_btn.setEnabled(True)

    def load_previous(self):
        self.spectrum_data.load_previous()
        self.view.spec_filename_lbl.setText(os.path.basename(self.spectrum_data.spectrum_filename))

    def load_next(self):
        self.spectrum_data.load_next()
        self.view.spec_filename_lbl.setText(os.path.basename(self.spectrum_data.spectrum_filename))

    def autocreate_cb_changed(self):
        self.autosave = self.view.spec_autocreate_cb.isChecked()

    def spec_directory_btn_click(self):
        directory_dialog = QtGui.QFileDialog()
        directory_dialog.setDirectory(self.spectrum_working_dir)
        directory_dialog.setFileMode(QtGui.QFileDialog.DirectoryOnly)
        directory_dialog.setWindowTitle("Please choose the default directory for autosaved spectra.")
        if (directory_dialog.exec_()):
            folder = directory_dialog.selectedFiles()[0]
            self.spectrum_working_dir = folder
            self.view.spec_directory_txt.setText(folder)

    def spec_directory_txt_changed(self):
        if os.path.exists(self.view.spec_directory_txt.text()):
            self.spectrum_working_dir = self.view.spec_directory_txt.text()
        else:
            self.view.spec_directory_txt.setText(self.spectrum_working_dir)

    def set_iteration_mode_number(self):
        self.spectrum_data.file_iteration_mode = 'number'

    def set_iteration_mode_time(self):
        self.spectrum_data.file_iteration_mode = 'time'


class IntegrationFileController(object):
    def __init__(self, view, img_data, mask_data):
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self._working_dir = ''
        self._reset_img_levels = False
        self.view.show()
        self.initialize()
        self.img_data.subscribe(self.update_img)
        self.create_signals()

    def initialize(self):
        self.update_img(True)
        self.plot_mask()
        self.view.img_view.img_view_box.autoRange()

    def plot_img(self, reset_img_levels=None):
        if reset_img_levels is None:
            reset_img_levels = self._reset_img_levels
        self.view.img_view.plot_image(self.img_data.get_img_data(), reset_img_levels)
        if reset_img_levels:
            self.view.img_view.auto_range()

    def plot_mask(self):
        if self.view.mask_show_cb.isChecked():
            self.view.img_view.plot_mask(self.mask_data.get_img())
        else:
            self.view.img_view.plot_mask(np.zeros(self.mask_data.get_img().shape))

    def change_mask_colormap(self):
        if self.view.mask_transparent_cb.isChecked():
            self.view.img_view.set_color([255, 0, 0, 100])
        else:
            self.view.img_view.set_color([255, 0, 0, 255])
        self.plot_mask()

    def change_img_levels_mode(self):
        self.view.img_view.img_histogram_LUT.percentageLevel = self.view.img_levels_percentage_rb.isChecked()
        self.view.img_view.img_histogram_LUT.old_hist_x_range = self.view.img_view.img_histogram_LUT.hist_x_range
        self.view.img_view.img_histogram_LUT.first_image = False

    def create_signals(self):
        self.connect_click_function(self.view.next_img_btn, self.load_next_img)
        self.connect_click_function(self.view.prev_img_btn, self.load_previous_img)
        self.connect_click_function(self.view.load_img_btn, self.load_file_btn_click)
        self.connect_click_function(self.view.img_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.view.img_browse_by_time_rb, self.set_iteration_mode_time)
        self.connect_click_function(self.view.mask_show_cb, self.plot_mask)
        self.connect_click_function(self.view.mask_transparent_cb, self.change_mask_colormap)
        self.connect_click_function(self.view.img_levels_absolute_rb, self.change_img_levels_mode)
        self.connect_click_function(self.view.img_levels_percentage_rb, self.change_img_levels_mode)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def load_file_btn_click(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load image data",
                                                             directory=self._working_dir))

        if filename is not '':
            self._working_dir = os.path.dirname(filename)
            self.img_data.load(filename)
            self.plot_img()

    def load_next_img(self):
        self.img_data.load_next()

    def load_previous_img(self):
        self.img_data.load_previous_file()

    def update_img(self, reset_img_levels=False):
        self.plot_img(reset_img_levels)
        self.view.img_filename_lbl.setText(os.path.basename(self.img_data.filename))

    def set_iteration_mode_number(self):
        self.img_data.file_iteration_mode = 'number'

    def set_iteration_mode_time(self):
        self.img_data.file_iteration_mode = 'time'


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = IntegrationController()
    app.exec_()