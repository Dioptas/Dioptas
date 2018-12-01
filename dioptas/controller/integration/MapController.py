from qtpy import QtCore, QtWidgets
import pyqtgraph as pq
import pyqtgraph.exporters
import numpy as np
from PIL import Image
import re
import os

from .PhotoConfig import gsecars_photo
from ...widgets.MapWidgets import Map2DWidget
from ...widgets.MapWidgets import ManualMapPositionsDialog
from ...widgets.MapWidgets import OpenBGImageDialog
from ...widgets.UtilityWidgets import save_file_dialog, open_files_dialog
from ...widgets.MainWidget import IntegrationWidget
from .MapErrors import *
from ...model.MapModel import MapModel
from ...model.DioptasModel import DioptasModel


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

        self.manual_map_positions_dialog = ManualMapPositionsDialog(self.map_widget)
        self.open_bg_image_dialog = OpenBGImageDialog(self.map_widget, gsecars_photo)
        self.map_model = self.model.map_model  # type: MapModel

        self.bg_image = None
        self.setup_connections()
        self.toggle_map_widgets_enable(toggle=False)

    def setup_connections(self):
        self.model.map_model.map_changed.connect(self.update_map_image)
        self.model.map_model.map_cleared.connect(self.clear_map)
        self.model.map_model.map_problem.connect(self.map_positions_problem)
        self.model.map_model.roi_problem.connect(self.roi_problem)
        self.model.map_model.map_images_loaded.connect(self.map_images_loaded)

        self.map_widget.load_ascii_files_btn.clicked.connect(self.load_ascii_files_btn_clicked)
        self.map_widget.update_map_btn.clicked.connect(self.btn_update_map_clicked)
        self.map_widget.roi_add_btn.clicked.connect(self.btn_roi_add_clicked)
        self.map_widget.roi_add_phase_btn.clicked.connect(self.btn_roi_add_phase_clicked)
        self.map_widget.roi_del_btn.clicked.connect(self.btn_roi_del_clicked)
        self.map_widget.roi_clear_btn.clicked.connect(self.btn_roi_clear_clicked)
        self.map_widget.roi_toggle_btn.clicked.connect(self.btn_roi_toggle_clicked)
        self.map_widget.roi_select_all_btn.clicked.connect(self.btn_roi_select_all_clicked)
        self.map_widget.add_bg_btn.clicked.connect(self.btn_add_bg_image_clicked)
        self.map_widget.bg_opacity_slider.valueChanged.connect(self.modify_map_opacity)
        self.map_widget.reset_zoom_btn.clicked.connect(self.reset_zoom_btn_clicked)
        self.map_widget.snapshot_btn.clicked.connect(self.snapshot_btn_clicked)
        self.map_widget.roi_math_txt.textEdited.connect(self.roi_math_txt_changed)
        self.map_widget.roi_list.itemSelectionChanged.connect(self.roi_list_selection_changed)

        self.map_widget.map_image.mouseClickEvent = self.myMouseClickEvent
        self.map_widget.hist_layout.scene().sigMouseMoved.connect(self.map_mouse_move_event)
        self.map_widget.map_view_box.mouseClickEvent = self.do_nothing
        self.map_widget.map_window_raised.connect(self.map_window_raised)

        self.map_widget.manual_map_positions_setup_btn.clicked.connect(self.manual_map_positions_setup_btn_clicked)
        self.manual_map_positions_dialog.read_list_btn.clicked.connect(self.read_list_btn_clicked)
        self.manual_map_positions_dialog.hor_num_txt.textChanged.connect(self.manual_map_num_points_changed)
        self.manual_map_positions_dialog.ver_num_txt.textChanged.connect(self.manual_map_num_points_changed)
        self.manual_map_positions_dialog.move_up_btn.clicked.connect(self.move_files_up_in_list)
        self.manual_map_positions_dialog.move_down_btn.clicked.connect(self.move_files_down_in_list)
        self.manual_map_positions_dialog.add_empty_btn.clicked.connect(self.add_empty_btn_clicked)
        self.manual_map_positions_dialog.delete_btn.clicked.connect(self.delete_btn_clicked)

    def toggle_map_widgets_enable(self, toggle=True):
        self.map_widget.update_map_btn.setEnabled(toggle)
        self.map_widget.manual_map_positions_setup_btn.setEnabled(toggle)
        self.map_widget.roi_del_btn.setEnabled(toggle)
        self.map_widget.roi_clear_btn.setEnabled(toggle)
        self.map_widget.roi_select_all_btn.setEnabled(toggle)
        self.map_widget.reset_zoom_btn.setEnabled(toggle)
        self.map_widget.snapshot_btn.setEnabled(toggle)
        self.map_widget.add_bg_btn.setEnabled(toggle)
        self.map_widget.bg_opacity_slider.setEnabled(toggle)
        if toggle:
            self.set_map_widget_style('color: white')
        else:
            self.set_map_widget_style('color: black')

    def set_map_widget_style(self, new_style):
        self.map_widget.update_map_btn.setStyleSheet(new_style)
        self.map_widget.manual_map_positions_setup_btn.setStyleSheet(new_style)
        self.map_widget.roi_del_btn.setStyleSheet(new_style)
        self.map_widget.roi_clear_btn.setStyleSheet(new_style)
        self.map_widget.roi_select_all_btn.setStyleSheet(new_style)
        self.map_widget.reset_zoom_btn.setStyleSheet(new_style)
        self.map_widget.snapshot_btn.setStyleSheet(new_style)
        self.map_widget.add_bg_btn.setStyleSheet(new_style)
        self.map_widget.bg_opacity_slider.setStyleSheet(new_style)

    def map_images_loaded(self):
        self.update_map_status_files_lbl()
        self.update_map_status_positions_lbl()
        if self.map_model.all_positions_defined_in_files:
            self.map_model.organize_map_files()
        else:
            MapError(cannot_read_positions_from_image_files)
        self.update_map_status_size_and_step_lbl()

    def update_map_status_files_lbl(self):
        num_files = self.map_model.num_map_files
        if not num_files:
            self.map_widget.map_status_files_lbl.setText('No Files')
            self.map_widget.map_status_files_lbl.setStyleSheet('color: red')
        status_lbl = str(num_files)
        if self.map_model.map_uses_patterns:
            status_lbl = status_lbl + ' patterns'
        else:
            status_lbl = status_lbl + ' images'
        self.map_widget.map_status_files_lbl.setText(status_lbl)
        self.map_widget.map_status_files_lbl.setStyleSheet('color: green')

    def update_map_status_positions_lbl(self):
        self.map_widget.map_status_positions_lbl.setStyleSheet('color: green')

        if self.map_model.all_positions_defined_in_files:
            status_pos_lbl = "Positions Found"

        elif self.map_model.positions_set_manually:
            status_pos_lbl = "Manual Positions"

        else:
            status_pos_lbl = "No Positions"
            self.map_widget.map_status_positions_lbl.setStyleSheet('color: red')

        self.map_widget.map_status_positions_lbl.setText(status_pos_lbl)

    def update_map_status_size_and_step_lbl(self):
        if self.map_model.all_positions_defined_in_files or self.map_model.positions_set_manually:
            map_size = str(self.map_model.num_hor) + 'x' + str(self.map_model.num_ver)
            map_range = '\tX:\tRange: ' + "{:.4f}".format(self.map_model.min_hor) + ',' + \
                        "{:.4f}".format(self.map_model.min_hor + (self.map_model.num_hor-1)*self.map_model.diff_hor) + \
                        '\tStep: ' + "{:.4f}".format(self.map_model.diff_hor) + '\n' + '\tY:\tRange: ' + \
                        "{:.4f}".format(self.map_model.min_ver) + ',' + \
                        "{:.4f}".format(self.map_model.min_ver + (self.map_model.num_ver-1)*self.map_model.diff_ver) + \
                        '\tStep: ' + "{:.4f}".format(self.map_model.diff_ver)
            self.map_widget.map_status_size_and_step_lbl.setText(map_size + map_range)
            self.map_widget.map_status_size_and_step_lbl.setStyleSheet('color: green')
        else:
            self.map_widget.map_status_size_and_step_lbl.setStyleSheet('color: red')
            self.map_widget.map_status_size_and_step_lbl.setText("No Info")

    def load_ascii_files_btn_clicked(self):
        filenames = open_files_dialog(self.map_widget, "Load Map files.",
                                      self.model.working_directories['pattern'])
        if len(filenames):
            self.map_model.reset_map_data()
            self.map_model.map_uses_patterns = True
            self.model.working_directories['pattern'] = os.path.dirname(filenames[0])
            for filename in filenames:
                filename = str(filename)
                self.map_model.add_file_to_map_data(filename, self.model.working_directories['pattern'], None)
            self.model.working_directories['overlay'] = os.path.dirname(str(filenames[0]))
            self.update_map_status_files_lbl()
            MapError(cannot_read_positions_from_image_files)

    def btn_update_map_clicked(self):
        self.map_model.map_roi_list = []
        roi_math = str(self.map_widget.roi_math_txt.text())
        if not roi_math == '':
            self.map_widget.roi_list.selectAll()
        for item in self.map_widget.roi_list.selectedItems():
            roi_full_name = item.text().split('_')
            roi_name = roi_full_name[1].split('-')
            self.map_model.add_roi_to_roi_list({'roi_letter': roi_full_name[0], 'roi_start': roi_name[0],
                                                'roi_end': roi_name[1]})
        self.map_model.roi_math = roi_math
        self.map_model.update_map()
        self.map_widget.map_loaded = True

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
            MapError(too_many_rois)
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
        roi_name = chr(roi_num+65) + '_' + '{:.3f}'.format(roi_start) + '-' + '{:.3f}'.format(roi_end)
        return roi_name

    def update_roi_letters(self):
        for row in range(self.map_widget.roi_list.count()):
            curr_roi = self.map_widget.roi_list.item(row)
            curr_roi.setText(chr(row+65) + '_' + curr_roi.text().split('_')[1])
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

    def reset_zoom_btn_clicked(self):
        self.map_widget.map_view_box.autoRange()

    def snapshot_btn_clicked(self):
        snapshot_filename = save_file_dialog(self.widget, "Save Map Snapshot.",
                                             os.path.join(self.working_dir['pattern'], 'map.png'),
                                             'PNG (*.png);;JPG (*.jpg);;TIF (*.tif)')
        exporter = pq.exporters.ImageExporter(self.map_widget.map_view_box)
        exporter.export(snapshot_filename)

    def update_map_image(self):
        if self.bg_image is not None:
            map_opacity = self.map_widget.bg_opacity_slider.value()
        else:
            map_opacity = 1.0
        self.map_widget.map_image.setOpacity(map_opacity)
        self.map_widget.map_image.setImage(self.map_model.new_image, True)
        self.auto_range()
        self.map_widget.map_loaded = True
        self.update_map_status_size_and_step_lbl()

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
            roi_new_name = self.generate_roi_name(roi_start, roi_end, ord(roi_full_name[0])-65)
            item.setText(roi_new_name)
            for key in self.map_widget.map_roi:
                if self.map_widget.map_roi[key]['List_Obj'] == item:
                    self.map_widget.map_roi[key]['Obj'].setRegion((roi_start, roi_end))
                    break

    # replaces the LMB click event for loading the pattern according to map pos, complete unzoom on right-click
    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and ev.modifiers() & QtCore.Qt.ControlModifier):
            self.map_widget.map_view_box.autoRange()

        elif ev.button() == QtCore.Qt.LeftButton:
            pos = ev.pos()
            x = pos.x()
            y = pos.y()
            hor, ver = self.xy_to_horver(x, y)
            file_name = self.horver_to_file_name(hor, ver)
            if self.map_model.map_uses_patterns:
                self.model.pattern_model.load_pattern(str(file_name))
            else:
                self.model.img_model.load(str(file_name))

    def xy_to_horver(self, x, y):
        hor = self.map_model.min_hor + x // self.map_model.pix_per_hor * self.map_model.diff_hor
        ver = self.map_model.min_ver + y // self.map_model.pix_per_ver * self.map_model.diff_ver
        return hor, ver

    def horver_to_file_name(self, hor, ver):
        for filename, filedata in self.map_model.map_data.items():
            if abs(float(filedata['pos_hor']) - hor) < 2E-4 and abs(float(filedata['pos_ver']) - ver) < 2E-4:
                return filename
        dist_sqr = {}
        for filename, filedata in self.map_model.map_data.items():
            dist_sqr[filename] = abs(float(filedata['pos_hor']) - hor) ** 2 + abs(float(filedata['pos_ver']) - ver) ** 2

        return min(dist_sqr, key=dist_sqr.get)

    def map_mouse_move_event(self, pos):
        pos = self.map_widget.map_image.mapFromScene(pos)
        x = pos.x()
        y = pos.y()
        try:
            hor, ver = self.xy_to_horver(x, y)
            file_name = self.horver_to_file_name(hor, ver)
            self.map_widget.lbl_map_pos.setText(str(file_name) + ":\t hor=" + str(round(hor, 3)) + '\tver:=' +
                                                str(round(ver, 3)))
        except Exception:
            pass

    # prevents right-click from opening menu
    def do_nothing(self, ev):
        pass

    def btn_add_bg_image_clicked(self):
        if not self.map_widget.map_loaded:
            MapError(no_map_loaded)
            return

        load_name = self.load_bg_image_file()

        if not load_name:
            MapError(no_bg_image_selected)
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
        opacity = self.map_widget.bg_opacity_slider.value()/100.0
        self.map_widget.map_image.setOpacity(opacity)
        self.map_widget.map_bg_image.setOpacity(1.0 - opacity)

    def clear_map(self):
        self.manual_map_positions_dialog.selected_map_files.clear()

    def map_positions_problem(self):
        MapError(map_positions_bad)

    def roi_problem(self):
        MapError(wrong_roi_letter)

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

    def map_window_raised(self):
        self.widget.img_batch_mode_map_rb.setChecked(True)
