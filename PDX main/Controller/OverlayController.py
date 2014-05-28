__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
import numpy as np
from Data.HelperModule import get_base_name


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