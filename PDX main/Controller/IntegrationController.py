from StdSuites.Standard_Suite import _3c_
# -*- coding: utf8 -*-
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

import matplotlib.pyplot as plt


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

        self.create_sub_controller()

        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()


    def create_sub_controller(self):
        self.spectrum_controller = IntegrationSpectrumController(self.view, self.img_data, self.mask_data,
                                                                 self.calibration_data, self.spectrum_data)
        self.file_controller = IntegrationImageController(self.view, self.img_data,
                                                          self.mask_data, self.calibration_data)
        self.overlay_controller = IntegrationOverlayController(self.view, self.spectrum_data)


class IntegrationOverlayController(object):
    def __init__(self, view, spectrum_data):
        self.view = view
        self.spectrum_data = spectrum_data
        self._working_dir = ''
        self.overlay_lw_items = []
        self.create_signals()

    def create_signals(self):
        self.connect_click_function(self.view.overlay_add_btn, self.add_overlay)
        self.connect_click_function(self.view.overlay_del_btn, self.del_overlay)
        self.connect_click_function(self.view.set_as_overlay_btn, self.set_as_overlay)
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
        dialog.setDirectory(self._working_dir)

        if filename is None:
            if (dialog.exec_()):
                filenames = dialog.selectedFiles()
                for filename in filenames:
                    filename = str(filename)
                    self.spectrum_data.add_overlay_file(filename)
                    self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
                    self.overlay_lw_items.append(self.view.overlay_lw.addItem(get_base_name(filename)))
                    self.view.overlay_lw.setCurrentRow(len(self.spectrum_data.overlays) - 1)
                self._working_dir = os.path.dirname(str(filenames[0]))

        else:
            self.spectrum_data.add_overlay_file(filename)
            self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
            self.overlay_lw_items.append(self.view.overlay_lw.addItem(get_base_name(filename)))
            self.view.overlay_lw.setCurrentRow(len(self.spectrum_data.overlays) - 1)
            self._working_dir = os.path.dirname(str(filename))
        print self._working_dir

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

    def set_as_overlay(self):
        self.spectrum_data.set_current_spectrum_as_overlay()
        self.view.spectrum_view.add_overlay(self.spectrum_data.overlays[-1])
        self.overlay_lw_items.append(self.view.overlay_lw.addItem(get_base_name(self.spectrum_data.overlays[-1].name)))
        self.view.overlay_lw.setCurrentRow(len(self.spectrum_data.overlays) - 1)

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
        if cur_ind is -1:
            self.view.overlay_set_as_bkg_btn.setChecked(False)
            return

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
        self._working_dir = ''
        self.integration_unit = '2th_deg'
        self.set_status()

        self.create_signals()

    def create_subscriptions(self):
        self.img_data.subscribe(self.image_changed)
        self.spectrum_data.subscribe(self.plot_spectra)
        self.view.spectrum_view.add_left_click_observer(self.spectrum_left_click)

    def set_status(self):
        self.autocreate = False
        self.unit = pyFAI.units.TTH_DEG

    def create_signals(self):
        self.connect_click_function(self.view.spec_autocreate_cb, self.autocreate_cb_changed)
        self.connect_click_function(self.view.spec_load_btn, self.load)
        self.connect_click_function(self.view.spec_previous_btn, self.load_previous)
        self.connect_click_function(self.view.spec_next_btn, self.load_next)
        self.connect_click_function(self.view.spec_directory_btn, self.spec_directory_btn_click)
        self.connect_click_function(self.view.spec_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.view.spec_browse_by_time_rb, self.set_iteration_mode_time)
        self.connect_click_function(self.view.spec_unit_tth_rb, self.set_unit_tth)
        self.connect_click_function(self.view.spec_unit_q_rb, self.set_unit_q)
        self.view.connect(self.view.spec_directory_txt, QtCore.SIGNAL('editingFinished()'),
                          self.spec_directory_txt_changed)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def image_changed(self):
        if self.calibration_data.is_calibrated:
            if self.autocreate:
                filename = self.img_data.filename
                if filename is not '':
                    filename = os.path.join(self._working_dir,
                                            os.path.basename(self.img_data.filename).split('.')[:-1][0] + '.xy')

                self.view.spec_next_btn.setEnabled(True)
                self.view.spec_previous_btn.setEnabled(True)
                self.view.spec_filename_lbl.setText(os.path.basename(filename))
                self.view.spec_directory_txt.setText(os.path.dirname(filename))
            else:
                self.view.spec_next_btn.setEnabled(False)
                self.view.spec_previous_btn.setEnabled(False)
                self.view.spec_filename_lbl.setText('No File saved or selected')
                filename = None

            if self.view.mask_use_cb.isChecked():
                mask = self.mask_data.get_mask()
            else:
                mask = None

            tth, I = self.calibration_data.integrate_1d(filename=filename, mask=mask, unit=self.integration_unit)
            if filename is not None:
                spectrum_name = filename
            else:
                spectrum_name = self.img_data.filename
            self.spectrum_data.set_spectrum(tth, I, spectrum_name)


    def plot_spectra(self):
        x, y = self.spectrum_data.spectrum.data
        self.view.spectrum_view.plot_data(x, y, self.spectrum_data.spectrum.name)

        #save the background subtracted file:
        if self.spectrum_data.bkg_ind is not -1:
            if self.autocreate:
                directory = os.path.join(self._working_dir, 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                header = self.calibration_data.geometry.makeHeaders()
                header += "\n# Background_File: " + self.spectrum_data.overlays[self.spectrum_data.bkg_ind].name
                data = np.dstack((x, y))[0]
                filename = os.path.join(directory, self.spectrum_data.spectrum.name + '_bkg_subtracted.xy')
                np.savetxt(filename, data, header=header)


    def load(self, filename=None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load Spectrum",
                                                             directory=self._working_dir))
        if filename is not '':
            self._working_dir = os.path.dirname(filename)
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
        self.autocreate = self.view.spec_autocreate_cb.isChecked()

    def spec_directory_btn_click(self):
        directory_dialog = QtGui.QFileDialog()
        directory_dialog.setDirectory(self._working_dir)
        directory_dialog.setFileMode(QtGui.QFileDialog.DirectoryOnly)
        directory_dialog.setWindowTitle("Please choose the default directory for autosaved spectra.")
        if (directory_dialog.exec_()):
            folder = str(directory_dialog.selectedFiles()[0])
            self._working_dir = folder
            self.view.spec_directory_txt.setText(folder)

    def spec_directory_txt_changed(self):
        if os.path.exists(self.view.spec_directory_txt.text()):
            self._working_dir = self.view.spec_directory_txt.text()
        else:
            self.view.spec_directory_txt.setText(self._working_dir)

    def set_iteration_mode_number(self):
        self.spectrum_data.file_iteration_mode = 'number'

    def set_iteration_mode_time(self):
        self.spectrum_data.file_iteration_mode = 'time'

    def set_unit_tth(self):
        self.integration_unit = '2th_deg'
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel('bottom', u'2θ', u'°')

        cur_line_pos = self.view.spectrum_view.pos_line.getPos()[0]
        new_line_pos = np.arcsin(cur_line_pos * 1e10 * self.calibration_data.geometry.wavelength / (4 * np.pi)) * 2
        new_line_pos = new_line_pos / np.pi * 180
        self.view.spectrum_view.set_pos_line(new_line_pos)

    def set_unit_q(self):
        self.integration_unit = "q_A^-1"
        self.image_changed()
        self.view.spectrum_view.spectrum_plot.setLabel('bottom', 'Q', 'A<sup>-1</sup>')

        cur_line_pos = self.view.spectrum_view.pos_line.getPos()[0]
        new_line_pos = 4 * np.pi * np.sin(cur_line_pos / 360 * np.pi) / self.calibration_data.geometry.wavelength / 1e10
        self.view.spectrum_view.set_pos_line(new_line_pos)

    def spectrum_left_click(self, x, y):
        self.view.spectrum_view.set_pos_line(x)
        if self.view.spec_unit_q_rb.isChecked():
            x = np.arcsin(x * 1e10 * self.calibration_data.geometry.wavelength / (4 * np.pi)) * 2
            x = x / np.pi * 180

        if self.view.cake_rb.isChecked():  #cake mode
            upper_ind = np.where(self.calibration_data.cake_tth > x)
            lower_ind = np.where(self.calibration_data.cake_tth < x)
            spacing = self.calibration_data.cake_tth[upper_ind[0][0]] - \
                      self.calibration_data.cake_tth[lower_ind[-1][-1]]
            new_pos = lower_ind[-1][-1] + \
                      (x - self.calibration_data.cake_tth[lower_ind[-1][-1]]) / spacing

            self.view.img_view.vertical_line.setValue(new_pos)
        else:  #image mode
            if self.calibration_data.is_calibrated:
                self.view.img_view.set_circle_scatter_tth(self.calibration_data.geometry._ttha, x / 180 * np.pi)


class IntegrationImageController(object):
    def __init__(self, view, img_data, mask_data, calibration_data):
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.calibration_data = calibration_data
        self._working_dir = ''
        self._reset_img_levels = False
        self._first_plot = True

        self.view.show()
        self.initialize()
        self.img_data.subscribe(self.update_img)
        self.view.img_view.add_mouse_move_observer(self.show_img_mouse_position)
        self.view.img_view.add_left_click_observer(self.img_mouse_click)
        self.create_signals()

    def initialize(self):
        self.update_img(True)
        self.plot_mask()
        self.view.img_view.img_view_box.autoRange()

    def plot_img(self, reset_img_levels=None):
        if reset_img_levels is None:
            reset_img_levels = self._reset_img_levels
        if self._first_plot == True:
            reset_img_levels = True
            if self.img_data.get_img_data().sum() > 0:
                self._first_plot = False

        self.view.img_view.plot_image(self.img_data.get_img_data(), reset_img_levels)
        if reset_img_levels:
            self.view.img_view.auto_range()


    def plot_cake(self, reset_img_levels=None):
        if reset_img_levels is None:
            reset_img_levels = self._reset_img_levels
        self.view.img_view.plot_image(self.calibration_data.cake_img, reset_img_levels)
        if reset_img_levels:
            self.view.img_view.auto_range()

    def plot_mask(self):
        if self.view.mask_use_cb.isChecked() and self.view.image_rb.isChecked():
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
        self.connect_click_function(self.view.auto_img_btn, self.auto_img_btn_click)
        self.connect_click_function(self.view.img_browse_by_name_rb, self.set_iteration_mode_number)
        self.connect_click_function(self.view.img_browse_by_time_rb, self.set_iteration_mode_time)
        self.connect_click_function(self.view.mask_use_cb, self.mask_use_cb_changed)
        self.connect_click_function(self.view.mask_transparent_cb, self.change_mask_colormap)
        self.connect_click_function(self.view.img_levels_absolute_rb, self.change_img_levels_mode)
        self.connect_click_function(self.view.img_levels_percentage_rb, self.change_img_levels_mode)
        self.connect_click_function(self.view.image_rb, self.change_view_mode)
        self.connect_click_function(self.view.cake_rb, self.change_view_mode)

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

    def mask_use_cb_changed(self):
        self.plot_mask()
        self.img_data.notify()

    def load_next_img(self):
        self.img_data.load_next()

    def load_previous_img(self):
        self.img_data.load_previous_file()

    def auto_img_btn_click(self):
        if self.calibration_data.is_calibrated:
            cake_state = self.view.cake_rb.isChecked()
            if cake_state:
                self.view.image_rb.setChecked(True)
                QtGui.QApplication.processEvents()

            while self.img_data.load_next() == True:
                print 'integrated ' + self.img_data.filename
            print 'finished!'

            if cake_state:
                self.view.cake_rb.setChecked(True)
                QtGui.QApplication.processEvents()
                self.update_img()


    def update_img(self, reset_img_levels=False):
        self.view.img_filename_lbl.setText(os.path.basename(self.img_data.filename))
        if self.view.cake_rb.isChecked() and self.calibration_data.is_calibrated:
            if self.view.mask_use_cb.isChecked():
                mask = self.mask_data.get_mask()
            else:
                mask = None
            self.calibration_data.integrate_2d(mask)
            self.plot_cake()
            self.view.img_view.plot_mask(np.zeros(self.mask_data.get_img().shape))
            self.view.img_view.activate_vertical_line()
            self.view.img_view.img_view_box.setAspectLocked(False)
        else:
            self.plot_img(reset_img_levels)
            self.plot_mask()
            self.view.img_view.deactivate_vertical_line()
            self.view.img_view.img_view_box.setAspectLocked(True)

    def change_view_mode(self):
        if self.view.cake_rb.isChecked() and not self.calibration_data.is_calibrated:
            self.view.image_rb.setChecked(True)
        else:
            if self.view.cake_rb.isChecked():
                self.view.img_view.deactivate_circle_scatter()
                self._update_cake_line_pos()

            else:
                self.view.img_view.activate_circle_scatter()
                self._update_image_scatter_pos()
            self.update_img()

    def _update_cake_line_pos(self):
        cur_tth = self.view.spectrum_view.pos_line.getPos()[0]
        upper_ind = np.where(self.calibration_data.cake_tth > cur_tth)
        lower_ind = np.where(self.calibration_data.cake_tth < cur_tth)
        spacing = self.calibration_data.cake_tth[upper_ind[0][0]] - \
                  self.calibration_data.cake_tth[lower_ind[-1][-1]]
        new_pos = lower_ind[-1][-1] + \
                  (cur_tth - self.calibration_data.cake_tth[lower_ind[-1][-1]]) / spacing
        self.view.img_view.vertical_line.setValue(new_pos)

    def _update_image_scatter_pos(self):
        cur_tth = self.view.spectrum_view.pos_line.getPos()[0]
        self.view.img_view.set_circle_scatter_tth(self.calibration_data.geometry._ttha, cur_tth / 180 * np.pi)


    def show_img_mouse_position(self, x, y):
        try:
            if x > 0 and y > 0:
                x_pos_string = 'X:  %4d' % x
                y_pos_string = 'Y:  %4d' % y
                self.view.x_lbl.setText(x_pos_string)
                self.view.y_lbl.setText(y_pos_string)

                int_string = 'I:   %5d' % self.view.img_view.img_data[np.floor(x), np.floor(y)]
                self.view.int_lbl.setText(int_string)
                if self.calibration_data.is_calibrated:
                    x_temp = x
                    x = np.array([y])
                    y = np.array([x_temp])
                    if self.view.cake_rb.isChecked():
                        tth = self.calibration_data.cake_tth[np.round(y[0])]
                        azi = self.calibration_data.cake_azi[np.round(x[0])]
                        q_value = 4 * np.pi * np.sin(
                            tth / 360.0 * np.pi) / self.calibration_data.geometry.wavelength / 1e10

                    else:
                        tth = self.calibration_data.geometry.tth(x, y)[0]
                        tth = tth / np.pi * 180.0
                        q_value = self.calibration_data.geometry.qFunction(x, y) / 10.0
                        azi = self.calibration_data.geometry.chi(x, y)[0] / np.pi * 180

                    azi = azi + 360 if azi < 0 else azi
                    d = self.calibration_data.geometry.wavelength / (2 * np.sin(tth / 180. * np.pi * 0.5)) * 1e10
                    tth_str = u'2θ:%9.2f  ' % tth
                    self.view.two_theta_lbl.setText(tth_str)
                    self.view.d_lbl.setText(u'd:%9.2f  ' % d)
                    self.view.q_lbl.setText(u'Q:%9.2f  ' % q_value)
                    self.view.azi_lbl.setText(u'X:%9.2f  ' % azi)
        except (IndexError, AttributeError):
            pass

    def img_mouse_click(self, x, y):
        if self.view.cake_rb.isChecked():  #cake mode
            y = np.array([y])
            tth = self.calibration_data.cake_tth[np.round(y[0])]
            if self.view.spec_unit_q_rb.isChecked():
                q = 4 * np.pi * np.sin(tth / 360.0 * np.pi) / self.calibration_data.geometry.wavelength / 1e10
                self.view.spectrum_view.set_pos_line(q)
            else:
                self.view.spectrum_view.set_pos_line(tth)

        else:  #image mode
            x = np.array([x])
            y = np.array([y])
            if self.calibration_data.is_calibrated:
                tth = self.calibration_data.geometry.tth(x, y)[0]
                self.view.img_view.set_circle_scatter_tth(self.calibration_data.geometry._ttha, tth)
                if self.view.spec_unit_q_rb.isChecked():
                    q = 4 * np.pi * np.sin(tth / 2) / self.calibration_data.geometry.wavelength / 1e10
                    self.view.spectrum_view.set_pos_line(q)
                else:
                    self.view.spectrum_view.set_pos_line(tth / np.pi * 180)


    def set_iteration_mode_number(self):
        self.img_data.file_iteration_mode = 'number'

    def set_iteration_mode_time(self):
        self.img_data.file_iteration_mode = 'time'


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = IntegrationController()
    controller.file_controller.load_file_btn_click('../ExampleData/Mg2SiO4_ambient_001.tif')
    controller.spectrum_controller._working_dir = '../ExampleData/spectra'
    controller.mask_data.set_dimension(controller.img_data.get_img_data().shape)
    controller.overlay_controller.add_overlay('../ExampleData/spectra/Mg2SiO4_ambient_005.xy')
    controller.calibration_data.load('../ExampleData/calibration.poni')
    controller.file_controller.load_file_btn_click('../ExampleData/Mg2SiO4_ambient_001.tif')
    app.exec_()