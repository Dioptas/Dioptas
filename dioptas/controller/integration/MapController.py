from qtpy import QtCore, QtWidgets
import pyqtgraph as pq
import numpy as np
from PIL import Image

from .PhotoConfig import gsecars_photo
from ...widgets.MapWidgets import Map2DWidget
from ...widgets.MapWidgets import ManualMapPositionsDialog

class MapController(object):
    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to IntegrationWidget
        :param dioptas_model: Reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        :type widget.map_2D_widget: Map2DWidget
        """

        self.widget = widget
        self.model = dioptas_model

        self.manual_map_positions_dialog = ManualMapPositionsDialog(self.widget)
        self.map_model = self.model.map_model
        self.map_widget = widget.map_2D_widget
        # self.bg_opacity = 0.5
        self.bg_image = None
        self.setup_connections()
        self.toggle_map_widgets_enable(toggle=False)

    def setup_connections(self):
        self.model.map_model.map_changed.connect(self.update_map_image)

        self.map_widget.manual_map_positions_setup_btn.clicked.connect(self.manual_map_positions_setup_btn_clicked)
        self.map_widget.show_map_btn.clicked.connect(self.btn_show_map_clicked)
        self.map_widget.roi_add_btn.clicked.connect(self.btn_roi_add_clicked)
        self.map_widget.roi_del_btn.clicked.connect(self.btn_roi_del_clicked)
        self.map_widget.roi_clear_btn.clicked.connect(self.btn_roi_clear_clicked)
        self.map_widget.roi_toggle_btn.clicked.connect(self.btn_roi_toggle_clicked)
        self.map_widget.roi_select_all_btn.clicked.connect(self.btn_roi_select_all_clicked)
        self.map_widget.add_bg_btn.clicked.connect(self.btn_add_bg_image_clicked)
        self.map_widget.bg_opacity_slider.valueChanged.connect(self.modify_map_opacity)
        # self.map_widget.show_bg_chk.stateChanged.connect(self.chk_show_bg_changed)
        # self.map_widget.show_map_chk.stateChanged.connect(self.chk_show_map_changed)
        self.map_widget.reset_zoom_btn.clicked.connect(self.reset_zoom_btn_clicked)

        self.map_widget.map_image.mouseClickEvent = self.myMouseClickEvent
        self.map_widget.hist_layout.scene().sigMouseMoved.connect(self.map_mouse_move_event)
        self.map_widget.map_view_box.mouseClickEvent = self.do_nothing

    def toggle_map_widgets_enable(self, toggle=True):
        self.map_widget.show_map_btn.setEnabled(toggle)
        self.map_widget.manual_map_positions_setup_btn.setEnabled(toggle)
        self.map_widget.roi_del_btn.setEnabled(toggle)
        self.map_widget.roi_clear_btn.setEnabled(toggle)
        self.map_widget.roi_select_all_btn.setEnabled(toggle)
        self.map_widget.reset_zoom_btn.setEnabled(toggle)
        self.map_widget.add_bg_btn.setEnabled(toggle)
        self.map_widget.bg_opacity_slider.setEnabled(toggle)

    def btn_show_map_clicked(self):
        self.map_model.map_roi_list = []
        for item in self.map_widget.roi_list.selectedItems():
            roi_name = item.text().split('-')
            self.map_model.map_roi_list.append({'roi_start': roi_name[0], 'roi_end': roi_name[1]})

        self.map_model.update_map()
        self.map_widget.map_loaded = True

    # Controls for ROI

    def btn_roi_add_clicked(self):
        # calculate ROI position
        tth_start = self.map_model.theta_center - self.map_model.theta_range
        tth_end = self.map_model.theta_center + self.map_model.theta_range
        roi_start = self.map_model.convert_units(tth_start, '2th_deg', self.map_model.units, self.map_model.wavelength)
        roi_end = self.map_model.convert_units(tth_end, '2th_deg', self.map_model.units, self.map_model.wavelength)

        # add ROI to list
        roi_name = self.generate_roi_name(roi_start, roi_end)
        roi_list_item = QtWidgets.QListWidgetItem(self.map_widget.roi_list)
        roi_num = self.map_widget.roi_num
        roi_list_item.setText(roi_name)
        roi_list_item.setSelected(True)
        self.map_widget.map_roi[roi_num] = {}
        self.map_widget.map_roi[roi_num]['roi_name'] = roi_name

        # add ROI to pattern view
        ov = pq.LinearRegionItem.Vertical
        self.map_widget.map_roi[roi_num]['Obj'] = pq.LinearRegionItem(values=[roi_start, roi_end], orientation=ov,
                                                                      movable=True,
                                                                      brush=pq.mkBrush(color=(255, 0, 255, 100)))
        self.map_widget.map_roi[roi_num]['List_Obj'] = self.map_widget.roi_list.item(self.map_widget.roi_list.count()
                                                                                     - 1)
        self.map_widget.spec_plot.addItem(self.map_widget.map_roi[roi_num]['Obj'])
        self.map_widget.map_roi[roi_num]['Obj'].sigRegionChangeFinished.connect(self.make_roi_changed(roi_num))
        self.map_widget.roi_num = self.map_widget.roi_num + 1
        if self.map_widget.roi_num == 1:
            self.toggle_map_widgets_enable(True)

    # create a function for each ROI when ROI is modified
    def make_roi_changed(self, curr_map_roi):
        def roi_changed():
            tth_start, tth_end = self.map_widget.map_roi[curr_map_roi]['Obj'].getRegion()
            new_roi_name = self.generate_roi_name(tth_start, tth_end)
            row = self.map_widget.roi_list.row(self.map_widget.map_roi[curr_map_roi]['List_Obj'])
            self.map_widget.roi_list.takeItem(row)
            self.map_widget.roi_list.insertItem(row, new_roi_name)
            self.map_widget.map_roi[curr_map_roi]['roi_name'] = new_roi_name
            self.map_widget.map_roi[curr_map_roi]['List_Obj'] = self.map_widget.roi_list.item(row)
            self.map_widget.roi_list.item(row).setSelected(True)

        return roi_changed

    def generate_roi_name(self, roi_start, roi_end):
        roi_name = '{:.3f}'.format(roi_start) + '-' + '{:.3f}'.format(roi_end)
        return roi_name

    def btn_roi_del_clicked(self):
        for each_roi in self.map_widget.roi_list.selectedItems():
            for key in self.map_widget.map_roi:
                if self.map_widget.map_roi[key]['List_Obj'] == each_roi:
                    self.map_widget.spec_plot.removeItem(self.map_widget.map_roi[key]['Obj'])
                    del self.map_widget.map_roi[key]
                    break
            self.map_widget.roi_list.takeItem(self.map_widget.roi_list.row(each_roi))
        if self.map_widget.roi_num == 0:
            self.toggle_map_widgets_enable(False)

    def btn_roi_clear_clicked(self):
        self.map_widget.roi_list.clear()
        for key in self.map_widget.map_roi:
            self.map_widget.spec_plot.removeItem(self.map_widget.map_roi[key]['Obj'])
        self.map_widget.map_roi.clear()
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

    def reset_zoom_btn_clicked(self):
        self.map_widget.map_view_box.autoRange()

    def update_map_image(self):
        if self.bg_image:
            map_opacity = self.map_widget.bg_opacity_slider.value()
        else:
            map_opacity = 1.0
        # if self.map_widget.show_bg_chk.isChecked():
        #     map_opacity = 1.0 - self.bg_opacity
        # else:
        #     map_opacity = 1.0
        self.map_widget.map_image.setOpacity(map_opacity)
        self.map_widget.map_image.setImage(self.map_model.new_image, True)
        self.auto_range()
        self.map_widget.map_loaded = True
        # self.map_widget.show_map_chk.setChecked(True)

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
            roi_name = item.text().split('-')
            roi_start = self.model.map_model.convert_units(float(roi_name[0]), previous_unit, new_unit, wavelength)
            roi_end = self.model.map_model.convert_units(float(roi_name[1]), previous_unit, new_unit, wavelength)
            roi_new_name = self.generate_roi_name(roi_start, roi_end)
            item.setText(roi_new_name)
            for key in self.map_widget.map_roi:
                if self.map_widget.map_roi[key]['List_Obj'] == item:
                    self.map_widget.map_roi[key]['Obj'].setRegion((roi_start, roi_end))
                    break

    # replaces the LMB click event for loading the spectrum according to map pos, complete unzoom on right-click
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
            self.map_widget.img_model.load(str(file_name))

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
        load_name = self.load_bg_image_file()
        if not load_name:
            print("No file chosen for background")
            return

        load_name_file = str(load_name).rsplit('/', 1)[-1]
        loaded_bg_image = Image.open(str(load_name).replace('\\', '/'))
        bg_image_tags = loaded_bg_image.tag

        img_px_size_hor = gsecars_photo['img_px_size_hor']
        img_px_size_ver = gsecars_photo['img_px_size_ver']
        img_hor_px = gsecars_photo['img_hor_px']
        img_ver_px = gsecars_photo['img_ver_px']
        img_width_mm = img_hor_px * img_px_size_hor
        img_height_mm = img_ver_px * img_px_size_ver

        self.bg_hor_ver = self.get_bg_hor_ver(bg_image_tags)
        bg_w_px = img_width_mm / self.map_model.hor_um_per_px
        bg_h_px = img_height_mm / self.map_model.ver_um_per_px
        bg_hor = float(self.bg_hor_ver['Horizontal'])
        bg_ver = float(self.bg_hor_ver['Vertical'])

        bg_hor_shift = -(-(bg_hor - img_width_mm / 2.0) + self.map_model.min_hor) / self.map_model.hor_um_per_px + \
                       self.map_model.pix_per_hor / 2
        bg_ver_shift = -(-(bg_ver - img_height_mm / 2.0) + self.map_model.min_ver) / self.map_model.ver_um_per_px + \
                       self.map_model.pix_per_ver / 2

        if load_name_file.split('_', 1)[0] in gsecars_photo['flip_prefixes']:
            loaded_bg_image = np.fliplr(loaded_bg_image)

        self.bg_image = np.rot90(loaded_bg_image, 3)

        self.map_widget.map_bg_image.setImage(self.bg_image)
        bg_rect = QtCore.QRectF(bg_hor_shift, bg_ver_shift, bg_w_px, bg_h_px)
        self.map_widget.map_bg_image.setRect(bg_rect)
        self.modify_map_opacity()
        # self.map_widget.show_bg_chk.setChecked(True)

    def load_bg_image_file(self):
        load_name = None
        if not self.map_widget.map_loaded:
            msg = "Please load a map, choose a region and update the map"
            bg_msg = QtWidgets.QMessageBox()
            bg_msg.setIcon(QtWidgets.QMessageBox.Information)
            bg_msg.setText("No Map Loaded")
            bg_msg.setInformativeText("See additional info...")
            bg_msg.setWindowTitle("Error: No Map")
            bg_msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            bg_msg.setDetailedText(msg)
            bg_msg.exec_()
            return

        load_name, _ = QtWidgets.QFileDialog.getOpenFileName(QtWidgets.QFileDialog(),
                                                             'Choose file name for loading background image',
                                                             self.map_widget.working_dir['image'], 'TIFF Files (*.tif)')
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

    # def chk_show_bg_changed(self):
    #     if self.map_widget.show_bg_chk.isChecked():
    #         self.map_widget.map_image.setOpacity(0.5)
    #         self.map_widget.map_bg_image.setOpacity(0.5)
    #         self.map_widget.show_map_chk.setEnabled(True)
    #     else:
    #         self.map_widget.map_image.setOpacity(1.0)
    #         self.map_widget.map_bg_image.setOpacity(0.0)
    #         self.map_widget.show_map_chk.setChecked(True)
    #         self.map_widget.show_map_chk.setEnabled(False)
    #
    # def chk_show_map_changed(self):
    #     if self.map_widget.show_map_chk.isChecked():
    #         if self.map_widget.show_bg_chk.isChecked():
    #             self.map_widget.map_image.setOpacity(0.5)
    #             self.map_widget.map_bg_image.setOpacity(0.5)
    #         else:
    #             self.map_widget.map_image.setOpacity(1.0)
    #             self.map_widget.map_bg_image.setOpacity(0.0)
    #     else:
    #         self.map_widget.map_image.setOpacity(0.0)
    #         self.map_widget.map_bg_image.setOpacity(1.0)

    def manual_map_positions_setup_btn_clicked(self):
        dialog_result = self.manual_map_positions_dialog.exec_()
        if dialog_result == QtWidgets.QDialog.Accepted:
            self.map_model.add_manual_map_positions(self.manual_map_positions_dialog.hor_minimum,
                                                    self.manual_map_positions_dialog.ver_minimum,
                                                    self.manual_map_positions_dialog.hor_step_size,
                                                    self.manual_map_positions_dialog.ver_step_size,
                                                    self.manual_map_positions_dialog.hor_number,
                                                    self.manual_map_positions_dialog.ver_number,
                                                    self.manual_map_positions_dialog.is_hor_first)
