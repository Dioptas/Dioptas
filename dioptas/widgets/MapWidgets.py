from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pq
from pyqtgraph import GraphicsLayoutWidget
import os
import numpy as np
from .plot_widgets.HistogramLUTItem import HistogramLUTItem

from .CustomWidgets import FlatButton
from .. import style_path


class Map2DWidget(QtWidgets.QWidget):
    widget_raised = QtCore.Signal()
    widget_closed = QtCore.Signal()

    mouse_clicked = QtCore.Signal(float, float)
    mouse_moved = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super(Map2DWidget, self).__init__(parent)

        # setup MAP window
        self.setWindowTitle("2D Map")
        self.setGeometry(200, 100, 800, 600)

        # setup initial data structures and default parameters
        self.map_roi = {}
        self.roi_num = 0  # number of existing ROIs
        self.roi_count = 0  # number of created ROIs, including deleted ones
        self.map_loaded = False
        self.old_roi_math_txt = ''

        # WIDGETS
        self.load_map_files_btn = QtWidgets.QPushButton("Load Map Files")
        self.load_map_files_btn.setToolTip("Load the image or pattern files for your map")
        self.manual_map_positions_setup_btn = QtWidgets.QPushButton("Setup Map")
        self.auto_update_map_cb = QtWidgets.QCheckBox('Auto Update?')
        self.auto_update_map_cb.setChecked(True)
        self.update_map_btn = QtWidgets.QPushButton("Update Map")
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
        self.snapshot_btn = QtWidgets.QPushButton("Snapshot")

        # ROI Widgets
        self.roi_list = QtWidgets.QListWidget()
        self.roi_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.roi_math_lbl = QtWidgets.QLabel('Math:')
        self.roi_math_txt = QtWidgets.QLineEdit()
        self.roi_add_btn = QtWidgets.QPushButton("Add Range")
        self.roi_add_phase_btn = QtWidgets.QPushButton("Add Phase")
        self.roi_del_btn = QtWidgets.QPushButton("Remove Range(s)")
        self.roi_clear_btn = QtWidgets.QPushButton("Clear Ranges")
        self.roi_toggle_btn = QtWidgets.QPushButton("Toggle Show")
        self.roi_select_all_btn = QtWidgets.QPushButton("Select All")

        # Background control
        self.add_bg_btn = QtWidgets.QPushButton("Add BG Image")
        self.bg_opacity_lbl = QtWidgets.QLabel("Opacity: BG")
        self.bg_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.map_opacity_lbl = QtWidgets.QLabel("Map")

        # Status Line
        self.map_status_lbl = QtWidgets.QLabel("Map:")
        self.map_status_files_lbl = QtWidgets.QLabel("No Files")
        self.map_status_positions_lbl = QtWidgets.QLabel("No Positions")
        self.map_status_size_and_step_lbl = QtWidgets.QLabel("No Info")

        # positions

        # ROI positions
        self.roi_grid = QtWidgets.QGridLayout()
        self.roi_grid.addWidget(self.roi_add_btn, 0, 0)
        self.roi_grid.addWidget(self.roi_add_phase_btn, 0, 1)
        self.roi_grid.addWidget(self.roi_del_btn, 1, 0)
        self.roi_grid.addWidget(self.roi_clear_btn, 1, 1)
        self.roi_grid.addWidget(self.roi_toggle_btn, 2, 1)
        self.roi_grid.addWidget(self.roi_select_all_btn, 2, 0)

        # Widget Properties
        self.roi_toggle_btn.setCheckable(True)
        self.roi_toggle_btn.setChecked(True)
        self.bg_opacity_slider.setMinimum(0)
        self.bg_opacity_slider.setMaximum(100)
        self.bg_opacity_slider.setValue(50)
        self.bg_opacity_slider.setSingleStep(5)
        self.bg_opacity_slider.setPageStep(20)
        self.map_status_files_lbl.setStyleSheet('color: red')
        self.map_status_positions_lbl.setStyleSheet('color: red')
        self.map_status_size_and_step_lbl.setStyleSheet('color: red')
        self.manual_map_positions_setup_btn.setToolTip('Load files and add range first')

        # Layout
        self.main_vbox = QtWidgets.QVBoxLayout()
        self.hbox = QtWidgets.QHBoxLayout()
        self.lbl_hbox = QtWidgets.QHBoxLayout()
        self.bg_hbox = QtWidgets.QHBoxLayout()
        self.math_hbox = QtWidgets.QHBoxLayout()
        self.roi_vbox = QtWidgets.QVBoxLayout()
        self.update_hbox = QtWidgets.QHBoxLayout()
        self.status_hbox = QtWidgets.QHBoxLayout()

        self.roi_vbox.addWidget(self.load_map_files_btn)
        self.roi_vbox.addWidget(self.manual_map_positions_setup_btn)
        self.update_hbox.addWidget(self.auto_update_map_cb)
        self.update_hbox.addWidget(self.update_map_btn)
        self.roi_vbox.addLayout(self.update_hbox)
        self.roi_vbox.addWidget(self.roi_list)

        self.math_hbox.addWidget(self.roi_math_lbl)
        self.math_hbox.addWidget(self.roi_math_txt)
        self.roi_vbox.addLayout(self.math_hbox)
        self.roi_vbox.addLayout(self.roi_grid)
        self.hbox.addLayout(self.roi_vbox)
        self.hbox.addStretch(1)

        self.bg_hbox.addWidget(self.add_bg_btn)
        self.bg_hbox.addWidget(self.bg_opacity_lbl)
        self.bg_hbox.addWidget(self.bg_opacity_slider)
        self.bg_hbox.addWidget(self.map_opacity_lbl)
        self.bg_hbox.addStretch(1)

        self.lbl_hbox.addWidget(self.snapshot_btn)
        self.lbl_hbox.addStretch(1)
        self.lbl_hbox.addWidget(self.lbl_map_pos)

        self.status_hbox.addWidget(self.map_status_lbl)
        self.status_hbox.addWidget(self.map_status_files_lbl)
        self.status_hbox.addWidget(self.map_status_positions_lbl)
        self.status_hbox.addWidget(self.map_status_size_and_step_lbl)

        self.hist_layout = GraphicsLayoutWidget()
        self.map_view_box = self.hist_layout.addViewBox(0, 0, lockAspect=1.0)

        self.map_view_box.addItem(self.map_bg_image, ignoreBounds=True)  # MAPBG
        self.map_view_box.addItem(self.map_image)
        # self.map_hor_axis = pq.AxisItem(orientation='bottom')
        # self.hist_layout.addItem(self.map_hor_axis)
        # self.map_ver_axis = pq.AxisItem(orientation='left')
        # self.hist_layout.addItem(self.map_ver_axis)
        self.map_histogram_LUT = HistogramLUTItem(self.map_image, orientation='vertical')
        self.hist_layout.addItem(self.map_histogram_LUT, 0, 1)

        self.hbox.addWidget(self.hist_layout)

        self.main_vbox.addLayout(self.hbox)
        self.main_vbox.addLayout(self.lbl_hbox)
        self.main_vbox.addLayout(self.bg_hbox)
        self.main_vbox.addStretch(1)
        self.main_vbox.addLayout(self.status_hbox)
        self.setLayout(self.main_vbox)

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint |
                            QtCore.Qt.CustomizeWindowHint | QtCore.Qt.MSWindowsFixedSizeDialogHint |
                            QtCore.Qt.X11BypassWindowManagerHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

        # Map mouse events
        self.map_image.mouseClickEvent = self.mouse_click_event
        self.map_view_box.mouseClickEvent = self.do_nothing
        self.hist_layout.scene().sigMouseMoved.connect(self.map_mouse_move_event)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()
        self.widget_raised.emit()

    def closeEvent(self, a0: QtGui.QCloseEvent):
        self.widget_closed.emit()
        super(Map2DWidget, self).closeEvent(a0)

    def set_control_widgets_style(self, new_style):
        self.update_map_btn.setStyleSheet(new_style)
        self.manual_map_positions_setup_btn.setStyleSheet(new_style)
        self.roi_del_btn.setStyleSheet(new_style)
        self.roi_clear_btn.setStyleSheet(new_style)
        self.roi_select_all_btn.setStyleSheet(new_style)
        self.snapshot_btn.setStyleSheet(new_style)
        self.add_bg_btn.setStyleSheet(new_style)
        self.bg_opacity_slider.setStyleSheet(new_style)

    def enable_control_widgets(self, toggle):
        self.update_map_btn.setEnabled(toggle)
        self.manual_map_positions_setup_btn.setEnabled(toggle)
        self.roi_del_btn.setEnabled(toggle)
        self.roi_clear_btn.setEnabled(toggle)
        self.roi_select_all_btn.setEnabled(toggle)
        self.snapshot_btn.setEnabled(toggle)
        self.add_bg_btn.setEnabled(toggle)
        self.bg_opacity_slider.setEnabled(toggle)

        if toggle:
            self.set_control_widgets_style('color: white')
        else:
            self.set_control_widgets_style('color: black')

    def mouse_click_event(self, ev):
        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and ev.modifiers() & QtCore.Qt.ControlModifier):
            self.map_view_box.autoRange()

        elif ev.button() == QtCore.Qt.LeftButton:
            pos = ev.pos()
            x = pos.x()
            y = pos.y()
            self.mouse_clicked.emit(x, y)

    def map_mouse_move_event(self, pos):
        pos = self.map_image.mapFromScene(pos)
        x = pos.x()
        y = pos.y()
        self.mouse_moved.emit(x, y)

    # prevents right-click from opening menu
    def do_nothing(self, ev):
        pass


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

        file = open(os.path.join(style_path, "stylesheet.qss"))
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
        self.ok_btn.setToolTip('# of files must equal # of points')

        file = open(os.path.join(style_path, "stylesheet.qss"))
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
        Overriding the dialog exec_ function to center the widget in the parent window before execution.
        """
        parent_center = self._parent.window().mapToGlobal(self._parent.window().rect().center())
        self.move(parent_center.x() - 101, parent_center.y() - 48)
        super(OpenBGImageDialog, self).exec_()


class MapErrorDialog(object):
    def __init__(self, msg):
        err_msg = QtWidgets.QMessageBox()
        err_msg.setIcon(eval(msg['icon']))
        err_msg.setText(msg['short_msg'])
        err_msg.setInformativeText(msg['informative_text'])
        err_msg.setWindowTitle(msg['window_title'])
        err_msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        err_msg.setDetailedText(msg['detailed_msg'])
        err_msg.exec_()
