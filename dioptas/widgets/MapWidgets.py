from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pq
from pyqtgraph import GraphicsLayoutWidget
import os
import numpy as np
from .plot_widgets.HistogramLUTItem import HistogramLUTItem
from PIL import Image
import time


class Map2DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Map2DWidget, self).__init__(parent)

        # setup MAP window
        self.setWindowTitle("2D Map")
        self.setGeometry(200, 100, 800, 600)

        # setup initial data structures and default parameters
        self.map_data = {}
        self.map_roi = {}
        self.theta_center = 5.9
        self.theta_range = 0.1
        self.num_hor = 0
        self.num_ver = 0
        self.roi_num = 0
        self.pix_per_hor = 100
        self.pix_per_ver = 100
        self.map_loaded = False
        self.units = '2th_deg'
        self.wavelength = 0.3344

        # WIDGETS
        self.show_map_btn = QtWidgets.QPushButton(self)
        self.lbl_map_pos = QtWidgets.QLabel()
        # Map Image and Histogram
        self.map_image = pq.ImageItem()
        self.map_histogram_LUT = HistogramLUTItem(self.map_image, orientation='vertical')

        # Background for image
        self.bg_image = np.zeros([1920, 1200])
        self.map_bg_image = pq.ImageItem()
        bg_rect = QtCore.QRectF(0, 0, 1920, 1200)
        self.map_bg_image.setImage(self.bg_image, opacity=0.5)
        self.map_bg_image.setRect(bg_rect)
        self.reset_zoom_btn = QtWidgets.QPushButton(self)

        # ROI Widgets
        self.roi_list = QtWidgets.QListWidget(self)
        self.roi_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.roi_add_btn = QtWidgets.QPushButton(self)
        self.roi_del_btn = QtWidgets.QPushButton(self)
        self.roi_clear_btn = QtWidgets.QPushButton(self)
        self.roi_toggle_btn = QtWidgets.QPushButton(self)
        self.roi_select_all_btn = QtWidgets.QPushButton(self)

        # Background control
        self.add_bg_btn = QtWidgets.QPushButton(self)
        self.show_bg_chk = QtWidgets.QCheckBox(self)
        self.show_map_chk = QtWidgets.QCheckBox(self)

        # positions

        # ROI positions
        self.roi_grid = QtWidgets.QGridLayout()
        self.roi_grid.addWidget(self.roi_add_btn, 0, 0, 1, 1)
        self.roi_grid.addWidget(self.roi_del_btn, 0, 1, 1, 1)
        self.roi_grid.addWidget(self.roi_clear_btn, 1, 0, 1, 1)
        self.roi_grid.addWidget(self.roi_toggle_btn, 1, 1, 1, 1)
        self.roi_grid.addWidget(self.roi_select_all_btn, 2, 0, 1, 1)

        # Widget Properties
        self.setWindowTitle("2D Map")
        self.show_map_btn.setText("Update Map")
        self.roi_add_btn.setText("Add Range")
        self.roi_del_btn.setText("Remove Range")
        self.roi_clear_btn.setText("Clear")
        self.roi_toggle_btn.setText("Toggle Show")
        self.roi_toggle_btn.setCheckable(True)
        self.roi_toggle_btn.setChecked(True)
        self.roi_select_all_btn.setText("Select All")
        self.add_bg_btn.setText("Add BG Image")
        self.show_bg_chk.setText("Show BG Image?")
        self.show_map_chk.setText("Show Map?")
        self.reset_zoom_btn.setText("Reset Zoom")

        # Layout
        self.main_vbox = QtWidgets.QVBoxLayout()
        self.hbox = QtWidgets.QHBoxLayout()
        self.lbl_hbox = QtWidgets.QHBoxLayout()
        self.bg_hbox = QtWidgets.QHBoxLayout()
        self.roi_vbox = QtWidgets.QVBoxLayout()
        self.roi_vbox.addWidget(self.show_map_btn)
        self.roi_vbox.addWidget(self.roi_list)
        self.roi_vbox.addLayout(self.roi_grid)
        self.hbox.addLayout(self.roi_vbox)
        self.hbox.addStretch(1)

        self.bg_hbox.addWidget(self.add_bg_btn)
        self.bg_hbox.addWidget(self.show_bg_chk)
        self.bg_hbox.addWidget(self.show_map_chk)
        self.bg_hbox.addStretch(1)

        self.lbl_hbox.addWidget(self.reset_zoom_btn)
        self.lbl_hbox.addStretch(1)
        self.lbl_hbox.addWidget(self.lbl_map_pos)

        self.hist_layout = GraphicsLayoutWidget()
        self.map_view_box = self.hist_layout.addViewBox(0, 0)

        self.map_view_box.addItem(self.map_bg_image, ignoreBounds=True)  # MAPBG
        self.map_view_box.addItem(self.map_image)
        self.map_histogram_LUT = HistogramLUTItem(self.map_image, orientation='vertical')
        self.hist_layout.addItem(self.map_histogram_LUT, 0, 1)

        self.hbox.addWidget(self.hist_layout)

        self.main_vbox.addLayout(self.hbox)
        self.main_vbox.addLayout(self.lbl_hbox)
        self.main_vbox.addLayout(self.bg_hbox)
        self.main_vbox.addStretch(1)
        self.setLayout(self.main_vbox)

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint |
                            QtCore.Qt.CustomizeWindowHint | QtCore.Qt.MSWindowsFixedSizeDialogHint |
                            QtCore.Qt.X11BypassWindowManagerHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self, img_model, spec_plot, working_dir):
        self.img_model = img_model
        self.spec_plot = spec_plot
        self.working_dir = working_dir
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()
