from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pq
from pyqtgraph import GraphicsLayoutWidget
import os
import numpy as np
from PIL import Image
import time


class MapController(object):
    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to IntegrationWidget
        :param dioptas_model: Reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """

        self.widget = widget
        self.model = dioptas_model

        self.map_widget = widget.map_2D_widget

        self.setup_connections()

    def setup_connections(self):
        self.map_widget.show_map_btn.clicked.connect(self.btn_show_map_clicked)
        self.map_widget.roi_add_btn.clicked.connect(self.btn_roi_add_clicked)
        self.map_widget.roi_del_btn.clicked.connect(self.btn_roi_del_clicked)
        self.map_widget.roi_clear_btn.clicked.connect(self.btn_roi_clear_clicked)
        self.map_widget.roi_toggle_btn.clicked.connect(self.btn_roi_toggle_clicked)
        self.map_widget.roi_select_all_btn.clicked.connect(self.btn_roi_select_all_clicked)
        self.map_widget.add_bg_btn.clicked.connect(self.map_widget.btn_add_bg_image_clicked)
        self.map_widget.show_bg_chk.stateChanged.connect(self.map_widget.chk_show_bg_changed)
        self.map_widget.show_map_chk.stateChanged.connect(self.map_widget.chk_show_map_changed)
        self.map_widget.reset_zoom_btn.clicked.connect(self.reset_zoom_btn_clicked)

        self.map_widget.map_image.mouseClickEvent = self.map_widget.myMouseClickEvent
        self.map_widget.hist_layout.scene().sigMouseMoved.connect(self.map_widget.map_mouse_move_event)
        self.map_widget.map_view_box.mouseClickEvent = self.map_widget.do_nothing

    def btn_show_map_clicked(self):
        self.map_widget.update_map()

    # Controls for ROI

    def btn_roi_add_clicked(self):
        # calculate ROI position
        tth_start = self.map_widget.theta_center - self.map_widget.theta_range
        tth_end = self.map_widget.theta_center + self.map_widget.theta_range
        roi_start = self.map_widget.convert_units(tth_start, '2th_deg', self.map_widget.units, self.map_widget.wavelength)
        roi_end = self.map_widget.convert_units(tth_end, '2th_deg', self.map_widget.units, self.map_widget.wavelength)

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
        self.map_widget.map_roi[roi_num]['List_Obj'] = self.map_widget.roi_list.item(self.map_widget.roi_list.count() - 1)
        self.map_widget.spec_plot.addItem(self.map_widget.map_roi[roi_num]['Obj'])
        self.map_widget.map_roi[roi_num]['Obj'].sigRegionChangeFinished.connect(self.make_roi_changed(roi_num))
        self.map_widget.roi_num = self.map_widget.roi_num + 1

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

    def btn_roi_clear_clicked(self):
        self.map_widget.roi_list.clear()
        for key in self.map_widget.map_roi:
            self.map_widget.spec_plot.removeItem(self.map_widget.map_roi[key]['Obj'])
        self.map_widget.map_roi.clear()

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
