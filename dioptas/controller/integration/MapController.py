# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2019 Clemens Prescher (clemens.prescher@gmail.com)
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
from qtpy import QtCore, QtWidgets
import pyqtgraph as pq
import pyqtgraph.exporters
import numpy as np
from PIL import Image
import re
import os
from xypattern import Pattern

from .PhotoConfig import gsecars_photo
from ...widgets.MapWidgets import Map2DWidget, SetupMapDialog, OpenBGImageDialog, MapErrorDialog
from ...widgets.UtilityWidgets import save_file_dialog, open_files_dialog
from ...widgets.MainWidget import IntegrationWidget
from ...model.MapModel import MapModel


class MapController(object):
    def __init__(self, working_dir, widget, dioptas_model):
        """
        :param widget: Reference to IntegrationWidget
        :param dioptas_model: Reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        :type widget.map_2D_widget: Map2DWidget
        """

        self.working_dir = working_dir
        self.widget = widget  # type: IntegrationWidget
        self.model = dioptas_model  # type: DioptasModel
        self.map_widget = widget.map_2D_widget  # type: Map2DWidget

        self.manual_map_positions_dialog = SetupMapDialog(self.map_widget)
        self.open_bg_image_dialog = OpenBGImageDialog(self.map_widget, gsecars_photo)
        self.map_model = self.model.map_model  # type: MapModel

        self.interactive_mode = True
        self.roi_range = 0.5

        self.bg_image = None
        self.setup_connections()

    def setup_connections(self):
        # Map model Signals
        self.model.map_model.map_changed.connect(self.update_map_image)
        self.model.map_model.map_cleared.connect(self.clear_map)
        self.model.map_model.map_problem.connect(self.map_positions_problem)
        self.model.map_model.roi_problem.connect(self.roi_problem)

        # General Signals
        self.widget.map_btn.clicked.connect(self.map_btn_clicked)
        self.map_widget.widget_raised.connect(self.activate_map)
        self.map_widget.widget_closed.connect(self.deactivate_map)

        self.map_widget.load_map_files_btn.clicked.connect(self.load_map_files_btn_clicked)
        self.map_widget.add_bg_btn.clicked.connect(self.btn_add_bg_image_clicked)
        self.map_widget.bg_opacity_slider.valueChanged.connect(self.modify_map_opacity)
        self.map_widget.snapshot_btn.clicked.connect(self.snapshot_btn_clicked)

        # Pattern widget signals
        self.widget.pattern_widget.map_interactive_roi.sigRegionChanged.connect(self.interactive_roi_range_changed)

        # Map Signals
        self.map_widget.mouse_clicked.connect(self.map_mouse_clicked)
        self.map_widget.mouse_moved.connect(self.map_mouse_moved)

        # ROI
        self.map_widget.roi_add_btn.clicked.connect(self.btn_roi_add_clicked)
        self.map_widget.roi_add_phase_btn.clicked.connect(self.btn_roi_add_phase_clicked)
        self.map_widget.roi_del_btn.clicked.connect(self.btn_roi_del_clicked)
        self.map_widget.roi_clear_btn.clicked.connect(self.btn_roi_clear_clicked)
        self.map_widget.roi_toggle_btn.clicked.connect(self.btn_roi_toggle_clicked)
        self.map_widget.roi_select_all_btn.clicked.connect(self.btn_roi_select_all_clicked)
        self.map_widget.roi_math_txt.textEdited.connect(self.roi_math_txt_changed)
        self.map_widget.roi_list.itemSelectionChanged.connect(self.roi_list_selection_changed)

        # map setup
        self.map_widget.setup_map_btn.clicked.connect(self.manual_map_positions_setup_btn_clicked)
        self.manual_map_positions_dialog.read_list_btn.clicked.connect(self.read_list_btn_clicked)
        self.manual_map_positions_dialog.hor_num_txt.textChanged.connect(self.manual_map_num_points_changed)
        self.manual_map_positions_dialog.ver_num_txt.textChanged.connect(self.manual_map_num_points_changed)
        self.manual_map_positions_dialog.move_up_btn.clicked.connect(self.move_files_up_in_list)
        self.manual_map_positions_dialog.move_down_btn.clicked.connect(self.move_files_down_in_list)
        self.manual_map_positions_dialog.add_empty_btn.clicked.connect(self.add_empty_btn_clicked)
        self.manual_map_positions_dialog.delete_btn.clicked.connect(self.delete_btn_clicked)

    def map_btn_clicked(self):
        if not self.map_widget.isVisible():
            self.map_widget.raise_widget()
        else:
            self.map_widget.close()

    def activate_map(self):
        self.widget.pattern_widget.mouse_left_clicked.connect(self.interactive_roi_pos_changed)
        if self.map_model.is_empty():
            self.load_map_files_btn_clicked()
        else:
            self.widget.pattern_widget.show_map_interactive_roi()
            self.interactive_roi_pos_changed(self.widget.pattern_widget.get_pos_line())

    def deactivate_map(self):
        self.widget.pattern_widget.mouse_left_clicked.disconnect(self.interactive_roi_pos_changed)
        self.widget.pattern_widget.hide_map_interactive_roi()

    def load_map_files_btn_clicked(self):
        filenames = open_files_dialog(self.map_widget, "Load Map files.",
                                      self.model.working_directories['image'])
        if len(filenames):
            self.map_model.reset()

            if os.path.basename(filenames[0]).split('.')[-1] in ['xy', 'chi', 'txt', 'dat']:
                for filename in filenames:
                    self.map_model.add_map_point(filename, Pattern.from_file(filename))

            else:  # assuming the files are image files
                if not self.model.calibration_model.is_calibrated:
                    self.widget.show_error_msg("Can not integrate multiple images without calibration.")
                    return

                self.map_model.map_uses_patterns = False
                self.model.blockSignals()

                progress_dialog = self.widget.get_progress_dialog("Integrating multiple files.", "Abort Integration",
                                                                  len(filenames))

                def callback_fn(current_index):
                    if progress_dialog.wasCanceled():
                        return False
                    progress_dialog.setValue(current_index)
                    QtWidgets.QApplication.processEvents()
                    return ~progress_dialog.wasCanceled()

                self.map_model.load_img_map(filenames, callback_fn)

                    # self.map_model.add_map_point(pattern_path,
                    #                              self.model.pattern,
                    #                              (self.model.img_model.motors_info['Horizontal'],
                    #                               self.model.img_model.motors_info['Vertical']),
                    #                              img_filename=filename)
                self.model.blockSignals(False)
                self.model.img_changed.emit()
                self.model.pattern_changed.emit()

            # now do the necessary steps to update the map
            self.interactive_roi_pos_changed(self.widget.pattern_widget.get_pos_line())
            # self.update_map_status_files_lbl()

    def _integrate_and_save_pattern(self, directory, base_filename):
        self.model.current_configuration.integrate_image_1d()
        path = os.path.join(directory, os.path.splitext(base_filename)[0] + '.xy')
        self.model.current_configuration.save_pattern(path)
        return path

    def _get_map_working_directory(self):
        # if there is no working directory selected A file dialog opens up to choose a directory...
        working_directory = str(QtWidgets.QFileDialog.getExistingDirectory(
            self.map_widget, "Please choose the output directory for the integrated Patterns.",
            self.model.working_directories['pattern']))
        return working_directory

    def interactive_roi_pos_changed(self, line_pos):
        start = line_pos - self.roi_range / 2
        end = line_pos + self.roi_range / 2
        self.update_interactive_roi(start, end)

    def interactive_roi_range_changed(self):
        start = self.widget.pattern_widget.map_interactive_roi.lines[0].value()
        end = self.widget.pattern_widget.map_interactive_roi.lines[1].value()
        self.update_interactive_roi(start, end)

    def update_interactive_roi(self, start, end):
        self.roi_range = end - start
        self.map_model.reset_rois()
        self.map_model.add_roi(start, end, "interactive")
        self.map_model.calculate_map_data()

        if self.widget.pattern_widget.map_interactive_roi not in \
                self.widget.pattern_widget.pattern_plot.items:
            self.widget.pattern_widget.show_map_interactive_roi()
        self.widget.pattern_widget.set_map_interactive_roi(start, end)
        self.update_map_image()

    def map_mouse_clicked(self, x, y):
        position = self.map_model.map.position_from_xy(x, y)
        pattern_filename, img_filename = self.map_model.map.filenames_from_position(position)

        if pattern_filename:
            self.model.pattern_model.load_pattern(pattern_filename)
            self.model.current_configuration.auto_integrate_pattern = False

        if img_filename:
            self.model.img_model.load(img_filename)

        if pattern_filename:
            self.model.current_configuration.auto_integrate_pattern = True

    def map_mouse_moved(self, x, y):
        try:
            position = self.map_model.map.position_from_xy(x, y)
            self.map_widget.map_pos_lbl.setText("{} {}".format(*position))
            pattern_filename, img_filename = self.map_model.map.filenames_from_position(position)
            if pattern_filename:
                self.map_widget.map_filename_lbl.setText("{}".format(os.path.basename(pattern_filename)))
            elif img_filename:
                self.map_widget.map_filename_lbl.setText("{}".format(os.path.basename(img_filename)))

        except AttributeError:
            pass

    def update_map_image(self):
        if self.bg_image is not None:
            map_opacity = self.map_widget.bg_opacity_slider.value()
        else:
            map_opacity = 1.0
        self.map_widget.map_image.setOpacity(map_opacity)
        self.map_widget.map_image.setImage(self.map_model.map.new_image, True)
        self.auto_range()

    # Controls for ROI
    def btn_roi_add_clicked(self, params):
        # roi_num - number of existing ROIs.
        # roi_count - number of rois created (includes deleted rois)
        # calculate ROI position
        try:
            theta_center = params['theta_center']
        except (KeyError, TypeError):
            theta_center = self.map_model.theta_center
        tth_start = theta_center - self.map_model.theta_range
        tth_end = theta_center + self.map_model.theta_range
        roi_start = self.map_model.convert_units(tth_start, '2th_deg', self.map_model.units, self.map_model.wavelength)
        roi_end = self.map_model.convert_units(tth_end, '2th_deg', self.map_model.units, self.map_model.wavelength)

        # add ROI to list
        roi_num = self.map_widget.roi_num
        if roi_num > 25:
            MapErrorDialog(too_many_rois)
            return
        roi_name = self.generate_roi_name(roi_start, roi_end, roi_num)
        roi_list_item = QtWidgets.QListWidgetItem(self.map_widget.roi_list)
        roi_list_item.setText(roi_name)
        roi_list_item.setSelected(True)
        # self.map_widget.map_roi[roi_num]['roi_name'] = roi_name

        # add ROI to pattern view
        roi_count = self.map_widget.roi_count
        self.map_widget.map_roi[roi_count] = {}
        ov = pq.LinearRegionItem.Vertical
        self.map_widget.map_roi[roi_count]['Obj'] = pq.LinearRegionItem(values=[roi_start, roi_end], orientation=ov,
                                                                        movable=True,
                                                                        brush=pq.mkBrush(color=(255, 0, 255, 100)))
        self.map_widget.map_roi[roi_count]['List_Obj'] = self.map_widget.roi_list.item(
            self.map_widget.roi_list.count() - 1)

        self.widget.pattern_widget.pattern_plot.addItem(self.map_widget.map_roi[roi_count]['Obj'])
        self.map_widget.map_roi[roi_count]['Obj'].sigRegionChangeFinished.connect(self.make_roi_changed(roi_count))
        self.map_widget.map_roi[roi_count]['Obj'].sigRegionChanged.connect(self.make_roi_changing(roi_count))
        self.map_widget.roi_num = self.map_widget.roi_num + 1
        self.map_widget.roi_count = self.map_widget.roi_count + 1
        if self.map_widget.roi_num == 1:
            self.toggle_map_widgets_enable(True)
            if self.map_model.map_organized:
                self.map_widget.update_map_btn.click()

        self.roi_list_selection_changed()

    def btn_roi_add_phase_clicked(self):
        cur_ind = self.widget.phase_widget.get_selected_phase_row()
        if cur_ind < 0:
            return
        phase_lines = self.model.phase_model.get_lines_d(cur_ind)
        for line in phase_lines[0:5]:
            tc = {'theta_center': self.map_model.convert_units(line[0], 'd_A', self.map_model.units,
                                                               self.map_model.wavelength)}
            self.btn_roi_add_clicked(tc)

    # create a function for each ROI when ROI modification is done
    def make_roi_changed(self, curr_map_roi):
        def roi_changed():
            if self.map_widget.auto_update_map_cb.isChecked():
                return
            tth_start, tth_end = self.map_widget.map_roi[curr_map_roi]['Obj'].getRegion()
            row = self.map_widget.roi_list.row(self.map_widget.map_roi[curr_map_roi]['List_Obj'])
            new_roi_name = self.generate_roi_name(tth_start, tth_end, row)
            self.map_widget.roi_list.takeItem(row)
            self.map_widget.roi_list.insertItem(row, new_roi_name)
            # self.map_widget.map_roi[curr_map_roi]['roi_name'] = new_roi_name
            self.map_widget.map_roi[curr_map_roi]['List_Obj'] = self.map_widget.roi_list.item(row)
            self.map_widget.roi_list.item(row).setSelected(True)
            self.btn_update_map_clicked()

        return roi_changed

    # create a function for each ROI when ROI modification is going on
    def make_roi_changing(self, curr_map_roi):
        def roi_changing():
            if not self.map_widget.auto_update_map_cb.isChecked():
                return
            tth_start, tth_end = self.map_widget.map_roi[curr_map_roi]['Obj'].getRegion()
            row = self.map_widget.roi_list.row(self.map_widget.map_roi[curr_map_roi]['List_Obj'])
            new_roi_name = self.generate_roi_name(tth_start, tth_end, row)
            self.map_widget.roi_list.takeItem(row)
            self.map_widget.roi_list.insertItem(row, new_roi_name)
            # self.map_widget.map_roi[curr_map_roi]['roi_name'] = new_roi_name
            self.map_widget.map_roi[curr_map_roi]['List_Obj'] = self.map_widget.roi_list.item(row)
            self.map_widget.roi_list.item(row).setSelected(True)
            self.btn_update_map_clicked()

        return roi_changing

    def roi_list_selection_changed(self):
        selected_rois = self.map_widget.roi_list.selectedItems()
        for roi_item in self.map_widget.map_roi:
            if self.map_widget.map_roi[roi_item]['List_Obj'] in selected_rois:
                self.map_widget.map_roi[roi_item]['Obj'].setBrush(pq.mkBrush(color=(255, 255, 0, 100)))
            else:
                self.map_widget.map_roi[roi_item]['Obj'].setBrush(pq.mkBrush(color=(255, 0, 255, 100)))
        # pq.QtGui.QGuiApplication.processEvents()
        self.widget.repaint()

    def generate_roi_name(self, roi_start, roi_end, roi_num):
        roi_name = chr(roi_num + 65) + '_' + '{:.3f}'.format(roi_start) + '-' + '{:.3f}'.format(roi_end)
        return roi_name

    def update_roi_letters(self):
        for row in range(self.map_widget.roi_list.count()):
            curr_roi = self.map_widget.roi_list.item(row)
            curr_roi.setText(chr(row + 65) + '_' + curr_roi.text().split('_')[1])
            # for key in self.map_widget.map_roi:
            #     if self.map_widget.map_roi[key]['List_Obj'] == curr_roi:
            #         self.map_widget.map_roi[key]['roi_name'] = 1
            #         break

    def btn_roi_del_clicked(self):
        for each_roi in self.map_widget.roi_list.selectedItems():
            for key in self.map_widget.map_roi:
                if self.map_widget.map_roi[key]['List_Obj'] == each_roi:
                    self.widget.pattern_widget.pattern_plot.removeItem(self.map_widget.map_roi[key]['Obj'])
                    del self.map_widget.map_roi[key]
                    break
            self.map_widget.roi_list.takeItem(self.map_widget.roi_list.row(each_roi))
            self.map_widget.roi_num = self.map_widget.roi_num - 1
        if self.map_widget.roi_num == 0:
            self.toggle_map_widgets_enable(False)
        else:
            self.update_roi_letters()

    def btn_roi_clear_clicked(self):
        self.map_widget.roi_list.clear()
        for key in self.map_widget.map_roi:
            self.widget.pattern_widget.pattern_plot.removeItem(self.map_widget.map_roi[key]['Obj'])
        self.map_widget.map_roi.clear()
        self.map_widget.roi_num = 0
        self.toggle_map_widgets_enable(False)

    def btn_roi_toggle_clicked(self):
        if self.map_widget.roi_toggle_btn.isChecked():
            for key in self.map_widget.map_roi:
                self.map_widget.map_roi[key]['Obj'].show()
        else:
            for key in self.map_widget.map_roi:
                self.map_widget.map_roi[key]['Obj'].hide()

    def btn_roi_select_all_clicked(self):
        self.map_widget.roi_list.selectAll()

    def roi_math_txt_changed(self):
        existing_rois = []
        roi_math_txt = str(self.map_widget.roi_math_txt.text()).upper()
        roi_math_txt_rois = re.findall('[A-Z]', roi_math_txt)
        for row in range(self.map_widget.roi_list.count()):
            existing_rois.append(self.map_widget.roi_list.item(row).text().split('_')[0])
        for roi in roi_math_txt_rois:
            if roi not in existing_rois:
                self.map_widget.roi_math_txt.setText(self.map_widget.old_roi_math_txt)
                return
        self.map_widget.old_roi_math_txt = roi_math_txt
        self.map_widget.roi_math_txt.setText(roi_math_txt)
        self.btn_update_map_clicked()

    def snapshot_btn_clicked(self):
        snapshot_filename = save_file_dialog(self.widget, "Save Map Snapshot.",
                                             os.path.join(self.working_dir['pattern'], 'map.png'),
                                             'PNG (*.png);;JPG (*.jpg);;TIF (*.tif)')
        exporter = pq.exporters.ImageExporter(self.map_widget.map_view_box)
        exporter.export(snapshot_filename)

    # Auto-range for map image
    def auto_range(self):
        hist_x, hist_y = self.map_widget.map_histogram_LUT.hist_x, self.map_widget.map_histogram_LUT.hist_y
        min_level = hist_x[0]
        max_level = hist_x[-1]
        self.map_widget.map_histogram_LUT.setLevels(min_level, max_level)

    def convert_all_units(self, previous_unit, new_unit, wavelength):
        # also, use this for converting the range if the file is in another unit.
        self.map_widget.roi_list.selectAll()
        for item in self.map_widget.roi_list.selectedItems():
            roi_full_name = item.text().split('_')
            roi_name = roi_full_name[1].split('-')
            roi_start = self.model.map_model.convert_units(float(roi_name[0]), previous_unit, new_unit, wavelength)
            roi_end = self.model.map_model.convert_units(float(roi_name[1]), previous_unit, new_unit, wavelength)
            roi_new_name = self.generate_roi_name(roi_start, roi_end, ord(roi_full_name[0]) - 65)
            item.setText(roi_new_name)
            for key in self.map_widget.map_roi:
                if self.map_widget.map_roi[key]['List_Obj'] == item:
                    self.map_widget.map_roi[key]['Obj'].setRegion((roi_start, roi_end))
                    break

    def btn_add_bg_image_clicked(self):
        if not self.map_widget.map_loaded:
            MapErrorDialog(no_map_loaded)
            return

        load_name = self.load_bg_image_file()

        if not load_name:
            MapErrorDialog(no_bg_image_selected)
            return

        load_name_file = str(load_name).rsplit('/', 1)[-1]
        loaded_bg_image = Image.open(str(load_name).replace('\\', '/'))
        bg_image_tags = loaded_bg_image.tag

        if 'flip_hor_prefixes' in gsecars_photo:
            if load_name_file.split('_')[0] in gsecars_photo['flip_hor_prefixes'].split(','):
                self.open_bg_image_dialog.hor_flip = True
            else:
                self.open_bg_image_dialog.hor_flip = False
        else:
            self.open_bg_image_dialog.hor_flip = gsecars_photo['flip_hor']

        if 'flip_ver_prefixes' in gsecars_photo:
            if load_name_file.split('_')[0] in gsecars_photo['flip_ver_prefixes'].split(','):
                self.open_bg_image_dialog.ver_flip = True
            else:
                self.open_bg_image_dialog.ver_flip = False
        else:
            self.open_bg_image_dialog.ver_flip = gsecars_photo['flip_ver']

        self.bg_hor_ver = self.get_bg_hor_ver(bg_image_tags)
        if 'Horizontal' in self.bg_hor_ver and 'Vertical' in self.bg_hor_ver:
            self.open_bg_image_dialog.hor_center = float(self.bg_hor_ver['Horizontal'])
            self.open_bg_image_dialog.ver_center = float(self.bg_hor_ver['Vertical'])

        self.open_bg_image_dialog.bg_file_name_lbl.setText(load_name)
        self.open_bg_image_dialog.exec_()
        if not self.open_bg_image_dialog.approved:
            return

        img_px_size_hor = self.open_bg_image_dialog.hor_pixel_size
        img_px_size_ver = self.open_bg_image_dialog.ver_pixel_size
        img_hor_px = self.open_bg_image_dialog.hor_num_pixels
        img_ver_px = self.open_bg_image_dialog.ver_num_pixels
        hor_flip = self.open_bg_image_dialog.hor_flip
        ver_flip = self.open_bg_image_dialog.ver_flip
        bg_hor = self.open_bg_image_dialog.hor_center
        bg_ver = self.open_bg_image_dialog.ver_center

        img_width_mm = img_hor_px * img_px_size_hor
        img_height_mm = img_ver_px * img_px_size_ver

        bg_w_px = img_width_mm / self.map_model.hor_um_per_px
        bg_h_px = img_height_mm / self.map_model.ver_um_per_px

        bg_hor_shift = -(-(bg_hor - img_width_mm / 2.0) + self.map_model.min_hor) / self.map_model.hor_um_per_px + \
                       self.map_model.pix_per_hor / 2
        bg_ver_shift = -(-(bg_ver - img_height_mm / 2.0) + self.map_model.min_ver) / self.map_model.ver_um_per_px + \
                       self.map_model.pix_per_ver / 2

        if hor_flip:
            loaded_bg_image = np.fliplr(loaded_bg_image)
        if ver_flip:
            loaded_bg_image = np.flipud(loaded_bg_image)

        self.bg_image = np.rot90(loaded_bg_image, 3)

        self.map_widget.map_bg_image.setImage(self.bg_image)
        bg_rect = QtCore.QRectF(bg_hor_shift, bg_ver_shift, bg_w_px, bg_h_px)
        self.map_widget.map_bg_image.setRect(bg_rect)
        self.modify_map_opacity()

    def load_bg_image_file(self):
        load_name, _ = QtWidgets.QFileDialog.getOpenFileName(QtWidgets.QFileDialog(),
                                                             'Choose file name for loading background image',
                                                             self.working_dir['image'], 'TIFF Files (*.tif)')
        return load_name

    def get_bg_hor_ver(self, tags):
        result = {}
        useful_tags = ['Horizontal:', 'Vertical:']
        for tag in tags:
            for key in useful_tags:
                if key in str(tags[tag]):
                    k, v = str(tags[tag][0]).split(':')
                    result[str(k)] = str(v)
        return result

    def modify_map_opacity(self):
        opacity = self.map_widget.bg_opacity_slider.value() / 100.0
        self.map_widget.map_image.setOpacity(opacity)
        self.map_widget.map_bg_image.setOpacity(1.0 - opacity)

    def clear_map(self):
        self.manual_map_positions_dialog.selected_map_files.clear()

    def map_positions_problem(self):
        MapErrorDialog(map_positions_bad)

    def roi_problem(self):
        MapErrorDialog(wrong_roi_letter)

    def manual_map_positions_setup_btn_clicked(self):
        self.manual_map_positions_dialog.exec_()
        if self.manual_map_positions_dialog.approved:
            map_file_list = []
            for index in range(self.manual_map_positions_dialog.selected_map_files.count()):
                map_file_list.append(str(self.manual_map_positions_dialog.selected_map_files.item(index).text()))
            self.map_model.add_manual_map_positions(self.manual_map_positions_dialog.hor_minimum,
                                                    self.manual_map_positions_dialog.ver_minimum,
                                                    self.manual_map_positions_dialog.hor_step_size,
                                                    self.manual_map_positions_dialog.ver_step_size,
                                                    self.manual_map_positions_dialog.hor_number,
                                                    self.manual_map_positions_dialog.ver_number,
                                                    self.manual_map_positions_dialog.is_hor_first,
                                                    map_file_list)
            self.update_map_status_positions_lbl()
            self.update_map_status_size_and_step_lbl()

    def read_list_btn_clicked(self):
        self.manual_map_positions_dialog.selected_map_files.clear()
        sorted_datalist = self.map_model.sort_map_files_by_natural_name()
        for item in sorted_datalist:
            self.manual_map_positions_dialog.selected_map_files.addItem(QtWidgets.QListWidgetItem(item))
        self.manual_map_positions_dialog.total_files_lbl.setText(
            str(self.manual_map_positions_dialog.selected_map_files.count()) + ' files')
        self.check_num_points()

    def manual_map_num_points_changed(self):
        try:
            self.manual_map_positions_dialog.total_map_points_lbl.setText(str(
                int(self.manual_map_positions_dialog.hor_num_txt.text()) *
                int(self.manual_map_positions_dialog.ver_num_txt.text())) + ' points')
        except ValueError:
            self.manual_map_positions_dialog.total_map_points_lbl.setText('0 points')
        self.check_num_points()

    def check_num_points(self):
        try:
            num_defined = int(self.manual_map_positions_dialog.hor_num_txt.text()) * \
                          int(self.manual_map_positions_dialog.ver_num_txt.text())
            num_in_list = self.manual_map_positions_dialog.selected_map_files.count()
        except ValueError:
            self.manual_map_positions_dialog.ok_btn.setEnabled(False)
            return

        self.manual_map_positions_dialog.ok_btn.setEnabled(num_defined == num_in_list)

    def move_files_up_in_list(self):
        files_list = self.manual_map_positions_dialog.selected_map_files
        selected_files = self.sort_selected_files(files_list)
        for file_name in selected_files:
            row = files_list.row(file_name)
            if row == 0:
                continue
            current_file_name = files_list.takeItem(row)
            files_list.insertItem(row - 1, current_file_name)
            files_list.item(row - 1).setSelected(True)

    def move_files_down_in_list(self):
        files_list = self.manual_map_positions_dialog.selected_map_files
        selected_files = self.sort_selected_files(files_list)
        for file_name in reversed(selected_files):
            row = files_list.row(file_name)
            if row == files_list.count() - 1:
                continue
            current_file_name = files_list.takeItem(row)
            files_list.insertItem(row + 1, current_file_name)
            files_list.item(row + 1).setSelected(True)

    def sort_selected_files(self, files_list):
        selected_files = files_list.selectedItems()
        if not len(selected_files):
            return []
        temp_dict = {}
        for file_name in selected_files:
            temp_dict[files_list.row(file_name)] = file_name

        temp_index = sorted(temp_dict)
        sorted_files = []
        for index in temp_index:
            sorted_files.append(temp_dict[index])
        return sorted_files

    def add_empty_btn_clicked(self):
        files_list = self.manual_map_positions_dialog.selected_map_files
        selected_files = self.sort_selected_files(files_list)
        if selected_files:
            top_row = files_list.row(selected_files[0])
        else:
            top_row = 0
        files_list.insertItem(top_row, "Empty")
        self.manual_map_positions_dialog.total_files_lbl.setText(
            str(self.manual_map_positions_dialog.selected_map_files.count()) + ' files')
        self.check_num_points()

    def delete_btn_clicked(self):
        files_list = self.manual_map_positions_dialog.selected_map_files
        selected_files = self.sort_selected_files(files_list)
        for file_name in selected_files:
            files_list.takeItem(files_list.row(file_name))
        self.manual_map_positions_dialog.total_files_lbl.setText(
            str(self.manual_map_positions_dialog.selected_map_files.count()) + ' files')
        self.check_num_points()


## Map error Messages ####################
##########################################

no_map_loaded = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Please follow these steps first:\n1. Load a map\n2. Click "Update Map"',
    'short_msg': 'Map not fully loaded',
    'informative_text': 'See additional info...',
    'window_title': 'Error: No Map Shown',
}

no_bg_image_selected = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Please make sure to select an image when prompted to, and press "Open"',
    'short_msg': 'No background image selected',
    'informative_text': 'See additional info...',
    'window_title': 'Error: No background image selected',
}

map_positions_bad = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Either not all map files have been loaded or, metadata does not contain map positions.\nPlease'
                    ' set up the map positions manually by clicking "Setup Map"',
    'short_msg': 'Map positions missing',
    'informative_text': 'See additional info...',
    'window_title': 'Warning: Map positions missing',
}

too_many_rois = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Too many ranges created. try deleting some of the ranges',
    'short_msg': 'Too many ranges',
    'informative_text': 'See additional info...',
    'window_title': 'Warning: Maximum of 26 ranges allowed',
}

wrong_roi_letter = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Problem with ROI math',
    'short_msg': 'ROI math error',
    'informative_text': 'See additional info...',
    'window_title': 'ROI Math error',
}

cannot_read_positions_from_image_files = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Please use the Setup Map button in the Map 2D window to setup the map positions',
    'short_msg': 'Could not read positions from image file meta-data',
    'informative_text': 'See additional info...',
    'window_title': 'Positions Missing',
}
