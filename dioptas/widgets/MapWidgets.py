from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pq
from pyqtgraph import GraphicsLayoutWidget
import os
import numpy as np
from .plot_widgets.HistogramLUTItem import HistogramLUTItem

from .CustomWidgets import FlatButton

widget_path = os.path.dirname(__file__)


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
        self.roi_count = 0
        self.pix_per_hor = 100
        self.pix_per_ver = 100
        self.map_loaded = False
        self.units = '2th_deg'
        self.wavelength = 0.3344
        self.old_roi_math_txt = ''

        # WIDGETS
        self.update_map_btn = QtWidgets.QPushButton(self)
        self.manual_map_positions_setup_btn = QtWidgets.QPushButton("Setup Map")
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
        self.roi_math_txt = QtWidgets.QLineEdit()
        self.roi_add_btn = QtWidgets.QPushButton(self)
        self.roi_del_btn = QtWidgets.QPushButton(self)
        self.roi_clear_btn = QtWidgets.QPushButton(self)
        self.roi_toggle_btn = QtWidgets.QPushButton(self)
        self.roi_select_all_btn = QtWidgets.QPushButton(self)

        # Background control
        self.add_bg_btn = QtWidgets.QPushButton(self)
        self.bg_opacity_lbl = QtWidgets.QLabel("Opacity: BG")
        self.bg_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.map_opacity_lbl = QtWidgets.QLabel("Map")

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
        self.update_map_btn.setText("Update Map")
        self.roi_add_btn.setText("Add Range")
        self.roi_del_btn.setText("Remove Range")
        self.roi_clear_btn.setText("Clear")
        self.roi_toggle_btn.setText("Toggle Show")
        self.roi_toggle_btn.setCheckable(True)
        self.roi_toggle_btn.setChecked(True)
        self.roi_select_all_btn.setText("Select All")
        self.add_bg_btn.setText("Add BG Image")
        self.reset_zoom_btn.setText("Reset Zoom")
        self.bg_opacity_slider.setMinimum(0)
        self.bg_opacity_slider.setMaximum(100)
        self.bg_opacity_slider.setValue(50)
        self.bg_opacity_slider.setSingleStep(5)
        self.bg_opacity_slider.setPageStep(20)

        # Layout
        self.main_vbox = QtWidgets.QVBoxLayout()
        self.hbox = QtWidgets.QHBoxLayout()
        self.lbl_hbox = QtWidgets.QHBoxLayout()
        self.bg_hbox = QtWidgets.QHBoxLayout()
        self.roi_vbox = QtWidgets.QVBoxLayout()
        self.roi_vbox.addWidget(self.manual_map_positions_setup_btn)
        self.roi_vbox.addWidget(self.update_map_btn)
        self.roi_vbox.addWidget(self.roi_list)
        self.roi_vbox.addWidget(self.roi_math_txt)
        self.roi_vbox.addLayout(self.roi_grid)
        self.hbox.addLayout(self.roi_vbox)
        self.hbox.addStretch(1)

        self.bg_hbox.addWidget(self.add_bg_btn)
        self.bg_hbox.addWidget(self.bg_opacity_lbl)
        self.bg_hbox.addWidget(self.bg_opacity_slider)
        self.bg_hbox.addWidget(self.map_opacity_lbl)
        self.bg_hbox.addStretch(1)

        self.lbl_hbox.addWidget(self.reset_zoom_btn)
        self.lbl_hbox.addStretch(1)
        self.lbl_hbox.addWidget(self.lbl_map_pos)

        self.hist_layout = GraphicsLayoutWidget()
        self.map_view_box = self.hist_layout.addViewBox(0, 0, lockAspect=1.0)

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

    def raise_widget(self, img_model, spec_plot, working_dir, widget):
        self.img_model = img_model
        self.spec_plot = spec_plot
        self.widget = widget
        self.working_dir = working_dir

        self.widget.img_batch_mode_map_rb.setChecked(True)
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()


class ManualMapPositionsDialog(QtWidgets.QDialog):
    """
    Dialog for inputting map positions manually
    """

    def __init__(self, parent):
        super(ManualMapPositionsDialog, self).__init__()

        self._parent = parent
        self._create_widgets()
        self._layout_widgets()
        self._style_widgets()

        self._connect_widgets()
        self.approved = False

    def _create_widgets(self):
        self.selected_map_files = QtWidgets.QListWidget()
        self.read_list_btn = QtWidgets.QPushButton('Read Files')
        self.move_up_btn = QtWidgets.QPushButton(u'\u2191')
        self.move_down_btn = QtWidgets.QPushButton(u'\u2193')
        self.add_empty_btn = QtWidgets.QPushButton('Empty')
        self.delete_btn = QtWidgets.QPushButton('Delete')

        self.hor_lbl = QtWidgets.QLabel("Horizontal")
        self.ver_lbl = QtWidgets.QLabel("Vertical")
        self.min_lbl = QtWidgets.QLabel("Minimum")
        self.step_lbl = QtWidgets.QLabel("Step")
        self.num_lbl = QtWidgets.QLabel("Number")
        self.first_lbl = QtWidgets.QLabel("First")
        self.total_files_lbl = QtWidgets.QLabel("0 Files")
        self.total_map_points_lbl = QtWidgets.QLabel("0 points")

        self.hor_min_txt = QtWidgets.QLineEdit()
        self.hor_step_txt = QtWidgets.QLineEdit()
        self.hor_num_txt = QtWidgets.QLineEdit()
        self.ver_min_txt = QtWidgets.QLineEdit()
        self.ver_step_txt = QtWidgets.QLineEdit()
        self.ver_num_txt = QtWidgets.QLineEdit()
        self.first_hor_rb = QtWidgets.QRadioButton("Horizontal")
        self.first_ver_rb = QtWidgets.QRadioButton("Vertical")

        self.first_hor_rb.setToolTip("Horizontal position changes between first two files")
        self.first_ver_rb.setToolTip("Vertical position changes between first two files")

        self.min_unit_lbl = QtWidgets.QLabel("mm")
        self.step_unit_lbl = QtWidgets.QLabel("mm")

        self.ok_btn = FlatButton("Done")
        self.cancel_btn = FlatButton("Cancel")

    def _layout_widgets(self):
        self._grid_layout = QtWidgets.QGridLayout()
        self._hbox_layout = QtWidgets.QHBoxLayout()
        self._vbox_list_layout = QtWidgets.QVBoxLayout()
        self._vbox_list_controls_layout = QtWidgets.QVBoxLayout()

        self._grid_layout.addWidget(self.hor_lbl, 0, 1)
        self._grid_layout.addWidget(self.ver_lbl, 0, 2)
        self._grid_layout.addWidget(self.min_lbl, 1, 0)
        self._grid_layout.addWidget(self.hor_min_txt, 1, 1)
        self._grid_layout.addWidget(self.ver_min_txt, 1, 2)
        self._grid_layout.addWidget(self.min_unit_lbl, 1, 3)
        self._grid_layout.addWidget(self.step_lbl, 2, 0)
        self._grid_layout.addWidget(self.hor_step_txt, 2, 1)
        self._grid_layout.addWidget(self.ver_step_txt, 2, 2)
        self._grid_layout.addWidget(self.step_unit_lbl, 2, 3)
        self._grid_layout.addWidget(self.num_lbl, 3, 0)
        self._grid_layout.addWidget(self.hor_num_txt, 3, 1)
        self._grid_layout.addWidget(self.ver_num_txt, 3, 2)
        self._grid_layout.addWidget(self.total_map_points_lbl, 3, 3)
        self._grid_layout.addWidget(self.first_lbl, 4, 0)
        self._grid_layout.addWidget(self.first_hor_rb, 4, 1)
        self._grid_layout.addWidget(self.first_ver_rb, 4, 2)
        self._grid_layout.addWidget(self.ok_btn, 5, 2)
        self._grid_layout.addWidget(self.cancel_btn, 5, 3)

        self._hbox_layout.addLayout(self._grid_layout)

        self._vbox_list_layout.addWidget(self.selected_map_files)
        self._vbox_list_layout.addWidget(self.total_files_lbl)
        self._hbox_layout.addLayout(self._vbox_list_layout)

        self._vbox_list_controls_layout.addWidget(self.read_list_btn)
        self._vbox_list_controls_layout.addWidget(self.move_up_btn)
        self._vbox_list_controls_layout.addWidget(self.add_empty_btn)
        self._vbox_list_controls_layout.addWidget(self.delete_btn)
        self._vbox_list_controls_layout.addWidget(self.move_down_btn)

        self._hbox_layout.addLayout(self._vbox_list_controls_layout)
        self.setLayout(self._hbox_layout)

    def _style_widgets(self):
        """
        Makes everything pretty and set double/int validators for the line edits.
        """

        self.selected_map_files.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.hor_min_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.hor_min_txt.setMaximumWidth(40)
        self.ver_min_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ver_min_txt.setMaximumWidth(40)
        self.hor_step_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.hor_step_txt.setMaximumWidth(40)
        self.ver_step_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ver_step_txt.setMaximumWidth(40)
        self.hor_num_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.hor_num_txt.setMaximumWidth(40)
        self.ver_num_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ver_num_txt.setMaximumWidth(40)

        self.hor_min_txt.setValidator(QtGui.QDoubleValidator())
        self.ver_min_txt.setValidator(QtGui.QDoubleValidator())
        self.hor_step_txt.setValidator(QtGui.QDoubleValidator())
        self.ver_step_txt.setValidator(QtGui.QDoubleValidator())
        self.hor_num_txt.setValidator(QtGui.QIntValidator())
        self.ver_num_txt.setValidator(QtGui.QIntValidator())

        self.ok_btn.setEnabled(False)

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        file = open(os.path.join(widget_path, "stylesheet.qss"))
        stylesheet = file.read()
        self.setStyleSheet(stylesheet)
        file.close()

    def _connect_widgets(self):
        """
        Connecting actions to slots.
        """
        self.ok_btn.clicked.connect(self.accept_manual_map_positions)
        self.cancel_btn.clicked.connect(self.reject_manual_map_positions)

    def accept_manual_map_positions(self):
        self.approved = True
        self.accept()

    def reject_manual_map_positions(self):
        self.approved = False
        self.reject()

    @property
    def hor_minimum(self):
        return float(str(self.hor_min_txt.text()))

    @property
    def ver_minimum(self):
        return float(str(self.ver_min_txt.text()))

    @property
    def hor_step_size(self):
        return float(str(self.hor_step_txt.text()))

    @property
    def ver_step_size(self):
        return float(str(self.ver_step_txt.text()))

    @property
    def hor_number(self):
        return int(str(self.hor_num_txt.text()))

    @property
    def ver_number(self):
        return int(str(self.ver_num_txt.text()))

    @property
    def is_hor_first(self):
        """
        Returns: True if horizontal is first, False if vertical is first
        """
        return self.first_hor_rb.isChecked()

    def exec_(self):
        """
        Overwriting the dialog exec_ function to center the widget in the parent window before execution.
        """
        parent_center = self._parent.window().mapToGlobal(self._parent.window().rect().center())
        self.move(parent_center.x() - 101, parent_center.y() - 48)
        super(ManualMapPositionsDialog, self).exec_()


class OpenBGImageDialog(QtWidgets.QDialog):
    """
    Dialog for setting up a background image
    """

    def __init__(self, parent, default_config):
        super(OpenBGImageDialog, self).__init__()

        self._parent = parent
        self._default_config = default_config
        self._create_widgets()
        self._layout_widgets()
        self._style_widgets()

        self._connect_widgets()
        self.approved = False

    def _create_widgets(self):
        self.bg_file_name_lbl = QtWidgets.QLabel()
        self.hor_lbl = QtWidgets.QLabel("Horizontal")
        self.ver_lbl = QtWidgets.QLabel("Vertical")
        self.img_px_lbl = QtWidgets.QLabel("Number of Pixels")
        self.img_px_size_lbl = QtWidgets.QLabel("Pixel Size")
        self.img_center_lbl = QtWidgets.QLabel("Center Position")
        self.flip_lbl = QtWidgets.QLabel("Flip?")

        self.img_hor_px_txt = QtWidgets.QLineEdit(str(self._default_config['img_hor_px']))
        self.img_ver_px_txt = QtWidgets.QLineEdit(str(self._default_config['img_ver_px']))
        self.img_hor_px_size_txt = QtWidgets.QLineEdit(str(self._default_config['img_px_size_hor']))
        self.img_ver_px_size_txt = QtWidgets.QLineEdit(str(self._default_config['img_px_size_ver']))
        self.img_hor_center_txt = QtWidgets.QLineEdit()
        self.img_ver_center_txt = QtWidgets.QLineEdit()
        self.flip_hor_cb = QtWidgets.QCheckBox()
        self.flip_ver_cb = QtWidgets.QCheckBox()

        self.ok_btn = FlatButton("Done")
        self.cancel_btn = FlatButton("Cancel")

    def _layout_widgets(self):
        self._grid_layout = QtWidgets.QGridLayout()

        self._grid_layout.addWidget(self.hor_lbl, 1, 1, 1, 1)
        self._grid_layout.addWidget(self.ver_lbl, 1, 2, 1, 1)

        self._grid_layout.addWidget(self.img_px_lbl, 2, 0, 1, 1)
        self._grid_layout.addWidget(self.img_hor_px_txt, 2, 1, 1, 1)
        self._grid_layout.addWidget(self.img_ver_px_txt, 2, 2, 1, 1)
        self._grid_layout.addWidget(self.img_px_size_lbl, 3, 0, 1, 1)
        self._grid_layout.addWidget(self.img_hor_px_size_txt, 3, 1, 1, 1)
        self._grid_layout.addWidget(self.img_ver_px_size_txt, 3, 2, 1, 1)
        self._grid_layout.addWidget(self.img_center_lbl, 4, 0, 1, 1)
        self._grid_layout.addWidget(self.img_hor_center_txt, 4, 1, 1, 1)
        self._grid_layout.addWidget(self.img_ver_center_txt, 4, 2, 1, 1)

        self._grid_layout.addWidget(self.flip_lbl, 5, 0, 1, 1)
        self._grid_layout.addWidget(self.flip_hor_cb, 5, 1, 1, 1)
        self._grid_layout.addWidget(self.flip_ver_cb, 5, 2, 1, 1)

        self._grid_layout.addWidget(self.ok_btn, 6, 1, 1, 1)
        self._grid_layout.addWidget(self.cancel_btn, 6, 2, 1, 1)

        self.setLayout(self._grid_layout)

    def _style_widgets(self):
        """
        Makes everything pretty and set double/int validators for the line edits.
        """
        self.img_hor_px_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.img_hor_px_txt.setMaximumWidth(60)
        self.img_ver_px_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.img_ver_px_txt.setMaximumWidth(60)
        self.img_hor_px_size_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.img_hor_px_size_txt.setMaximumWidth(60)
        self.img_ver_px_size_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.img_ver_px_size_txt.setMaximumWidth(60)
        self.img_hor_center_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.img_hor_center_txt.setMaximumWidth(60)
        self.img_ver_center_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.img_ver_center_txt.setMaximumWidth(60)

        self.img_hor_px_size_txt.setValidator(QtGui.QDoubleValidator())
        self.img_ver_px_size_txt.setValidator(QtGui.QDoubleValidator())
        self.img_hor_center_txt.setValidator(QtGui.QDoubleValidator())
        self.img_ver_center_txt.setValidator(QtGui.QDoubleValidator())
        self.img_hor_px_txt.setValidator(QtGui.QIntValidator())
        self.img_ver_px_txt.setValidator(QtGui.QIntValidator())

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        file = open(os.path.join(widget_path, "stylesheet.qss"))
        stylesheet = file.read()
        self.setStyleSheet(stylesheet)
        file.close()

    def _connect_widgets(self):
        """
        Connecting actions to slots.
        """
        self.ok_btn.clicked.connect(self.accept_bg_properties)
        self.cancel_btn.clicked.connect(self.reject_bg_properties)

    def accept_bg_properties(self):
        self.approved = True
        self.accept()

    def reject_bg_properties(self):
        self.approved = False
        self.reject()

    @property
    def hor_num_pixels(self):
        return int(str(self.img_hor_px_txt.text()))

    @property
    def ver_num_pixels(self):
        return int(str(self.img_ver_px_txt.text()))

    @property
    def hor_pixel_size(self):
        return float(str(self.img_hor_px_size_txt.text()))

    @property
    def ver_pixel_size(self):
        return float(str(self.img_ver_px_size_txt.text()))

    @property
    def hor_flip(self):
        return self.flip_hor_cb.isChecked()

    @hor_flip.setter
    def hor_flip(self, flip_value):
        self.flip_hor_cb.setChecked(flip_value)

    @property
    def ver_flip(self):
        return self.flip_ver_cb.isChecked()

    @ver_flip.setter
    def ver_flip(self, flip_value):
        self.flip_ver_cb.setChecked(flip_value)

    @property
    def hor_center(self):
        return float(str(self.img_hor_center_txt.text()))

    @hor_center.setter
    def hor_center(self, center):
        self.img_hor_center_txt.setText('{0:.4f}'.format(center))

    @property
    def ver_center(self):
        return float(str(self.img_ver_center_txt.text()))

    @ver_center.setter
    def ver_center(self, center):
        self.img_ver_center_txt.setText('{0:.4f}'.format(center))

    def exec_(self):
        """
        Overwriting the dialog exec_ function to center the widget in the parent window before execution.
        """
        parent_center = self._parent.window().mapToGlobal(self._parent.window().rect().center())
        self.move(parent_center.x() - 101, parent_center.y() - 48)
        super(OpenBGImageDialog, self).exec_()

