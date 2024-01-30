import os

from qtpy import QtWidgets, QtCore, QtGui
from pyqtgraph import GraphicsLayoutWidget, ColorButton

from ..plot_widgets.ImgWidget import IntegrationBatchWidget
from .CustomWidgets import MouseCurrentAndClickedWidget
from ..CustomWidgets import FlatButton, CheckableFlatButton, HorizontalSpacerItem, VerticalSpacerItem, LabelAlignRight, LabelExpandable

from . import CLICKED_COLOR
from ... import icons_path

try:
    from ..plot_widgets.SurfaceWidget import SurfaceWidget

    open_gl = True
except ModuleNotFoundError:
    open_gl = False


class BatchWidget(QtWidgets.QWidget):
    """
    Class describe a widget for batch integration
    """

    def __init__(self, parent=None):
        super(BatchWidget, self).__init__(parent)

        self.frame = QtWidgets.QWidget()
        self.frame.setObjectName('batch_frame')

        self._frame_layout = QtWidgets.QVBoxLayout()
        self._top_layout = QtWidgets.QHBoxLayout()
        self._central_layout = QtWidgets.QHBoxLayout()

        self.black_container = QtWidgets.QWidget()
        self.black_container.setObjectName("black_container")
        self._black_container_layout = QtWidgets.QVBoxLayout()

        # top
        self.file_control_widget = BatchFileControlWidget()
        self.mode_widget = BatchModeWidget()

        # central
        self.file_view_widget = BatchFileViewWidget()
        self.stack_plot_widget = BatchStackWidget()
        if open_gl:
            self.surface_widget = BatchSurfaceWidget()
        self.options_widget = BatchOptionsWidget()

        # bottom
        self.control_widget = BatchControlWidget()
        self.position_widget = BatchImgPositionWidget()

        self.create_layout()
        self.style_widgets()

        self.setLayout(self._layout)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("Batch widget")

        self.activate_files_view()

    def create_layout(self):
        self._top_layout.addWidget(self.file_control_widget)
        self._top_layout.addWidget(self.mode_widget)

        self._central_layout.addWidget(self.file_view_widget)
        self._central_layout.addWidget(self.stack_plot_widget)
        if open_gl:
            self._central_layout.addWidget(self.surface_widget)
        self._central_layout.addWidget(self.options_widget)

        self._frame_layout.addLayout(self._top_layout)

        self._black_container_layout.addLayout(self._central_layout)
        self._black_container_layout.addWidget(self.control_widget)
        self.black_container.setLayout(self._black_container_layout)

        self._frame_layout.addWidget(self.black_container)
        self._frame_layout.addWidget(self.position_widget)

        self.frame.setLayout(self._frame_layout)
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.addWidget(self.frame)

    def style_widgets(self):
        zero_spacing_layouts = [self._frame_layout, self._top_layout, self._layout,
                                self._central_layout, self._black_container_layout]

        for layout in zero_spacing_layouts:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

        self.setStyleSheet(
            """
            #black_container {
                background: black;
            }
            """
        )

    def sizeHint(self):
        return QtCore.QSize(800, 600)

    def activate_files_view(self):
        self.mode_widget.view_f_btn.setChecked(True)

        self.file_view_widget.show()
        if open_gl:
            self.surface_widget.hide()
        self.stack_plot_widget.hide()
        self.options_widget.hide()

        self.position_widget.step_raw_widget.show()
        self.position_widget.step_series_widget.hide()
        self.control_widget.waterfall_btn.hide()
        self.control_widget.phases_btn.hide()
        self.control_widget.autoscale_btn.hide()
        self.control_widget.normalize_btn.hide()
        self.control_widget.integrate_btn.show()

    def activate_stack_plot(self):
        self.position_widget.step_raw_widget.hide()
        self.position_widget.step_series_widget.show()
        self.mode_widget.view_2d_btn.setChecked(True)

        self.file_view_widget.hide()
        self.stack_plot_widget.show()
        self.options_widget.show()
        if open_gl:
            self.surface_widget.hide()
        self.control_widget.waterfall_btn.show()
        self.control_widget.phases_btn.show()
        self.control_widget.autoscale_btn.show()
        self.control_widget.normalize_btn.show()
        self.control_widget.integrate_btn.hide()

    def activate_surface_view(self):
        self.position_widget.step_raw_widget.hide()
        self.position_widget.step_series_widget.show()

        self.mode_widget.view_3d_btn.setChecked(True)

        y = self.position_widget.step_series_widget.slider.value()
        self.surface_widget.surface_view.g_translate = y

        self.file_view_widget.hide()
        self.stack_plot_widget.hide()
        self.options_widget.show()
        self.surface_widget.show()

        self.control_widget.waterfall_btn.hide()
        self.control_widget.phases_btn.hide()
        self.control_widget.autoscale_btn.hide()
        self.control_widget.normalize_btn.hide()
        self.control_widget.integrate_btn.hide()

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()


class BatchFileViewWidget(QtWidgets.QWidget):
    """
    Widget to show raw files, calibration and mask files

    Widget contains:
        QLine: calibration file
        QLine: mask file
        QTreeView: raw files
    """

    iteration_name = ''

    def __init__(self):
        super(BatchFileViewWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()
        self._file_lbl_widget = QtWidgets.QWidget()
        self._file_lbl_layout = QtWidgets.QGridLayout()

        self.cal_file_lbl = LabelExpandable('undefined')
        self.mask_file_lbl = LabelExpandable('undefined')

        self.treeView = QtWidgets.QTreeView()
        self.treeView.setObjectName('treeView')

        self.tree_model = QtGui.QStandardItemModel()
        self.treeView.setModel(self.tree_model)
        self.treeView.setColumnWidth(0, 350)

        self.style_widgets()
        self.create_layout()

    def create_layout(self):
        self._file_lbl_layout.addWidget(LabelAlignRight("Calibration File:"), 0, 0)
        self._file_lbl_layout.addWidget(self.cal_file_lbl, 0, 1)
        self._file_lbl_layout.addItem(HorizontalSpacerItem(), 0, 2)

        self._file_lbl_layout.addWidget(LabelAlignRight("Mask File:"), 1, 0)
        self._file_lbl_layout.addWidget(self.mask_file_lbl, 1, 1)

        self._file_lbl_widget.setLayout(self._file_lbl_layout)
        self._layout.addWidget(self._file_lbl_widget)
        self._layout.addWidget(self.treeView)
        self.setLayout(self._layout)

    def style_widgets(self):
        self._file_lbl_layout.setContentsMargins(5, 3, 5, 2)
        self._file_lbl_layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setStyleSheet("""
            #treeView {
                background: black;
                color: yellow;
            }
        """)

    def set_raw_files(self, files, images):
        self.tree_model.clear()
        self.tree_model.setColumnCount(2)
        self.tree_model.setHorizontalHeaderLabels(["Raw file name", "N images"])
        self.treeView.setColumnWidth(0, 400)

        for i, file in enumerate(files):
            self.tree_model.appendRow(QtGui.QStandardItem(f"{file}"))
            self.tree_model.setItem(i, 1, QtGui.QStandardItem(f"{images[i]}"))

    def set_cal_file(self, file_path):
        if file_path is None:
            file_path = 'undefined'
        self.cal_file_lbl.setText(file_path)
        self.cal_file_lbl.setToolTip("Calibration used for integration")

    def set_mask_file(self, file_path):
        if file_path is None:
            file_path = 'undefined'
        self.mask_file_lbl.setText(file_path)
        self.mask_file_lbl.setToolTip("Mask used for integration")


class BatchFileControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchFileControlWidget, self).__init__()
        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)

        self.load_btn = FlatButton()
        self.load_btn.setToolTip("Load raw/proc data")
        self.load_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'open.ico')))
        self.load_btn.setIconSize(QtCore.QSize(13, 13))
        self.load_btn.setMaximumWidth(25)

        self.load_previous_folder_btn = FlatButton('<')
        self.load_previous_folder_btn.setToolTip("Load files in previous folder")

        self.load_next_folder_btn = FlatButton('>')
        self.load_next_folder_btn.setToolTip("Loads files in next folder")

        self.save_btn = FlatButton()
        self.save_btn.setToolTip("Save data")
        self.save_btn.setIcon(QtGui.QIcon(os.path.join(icons_path, 'save.ico')))
        self.save_btn.setIconSize(QtCore.QSize(13, 13))
        self.save_btn.setMaximumWidth(25)

        self.folder_lbl = LabelExpandable("...")

        self.create_layout()

    def create_layout(self):
        self._layout.addWidget(self.load_btn)
        self._layout.addWidget(self.load_previous_folder_btn)
        self._layout.addWidget(self.load_next_folder_btn)
        self._layout.addWidget(self.save_btn)
        self._layout.addWidget(self.folder_lbl)

        self.setLayout(self._layout)


class BatchModeWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchModeWidget, self).__init__()
        self._layout = QtWidgets.QHBoxLayout()

        self.view_f_btn = CheckableFlatButton("Files")
        self.view_2d_btn = CheckableFlatButton("2D")
        self.view_3d_btn = CheckableFlatButton("3D")

        self.unit_view_group = QtWidgets.QButtonGroup()
        self.unit_view_group.addButton(self.view_2d_btn)
        self.unit_view_group.addButton(self.view_3d_btn)
        self.unit_view_group.addButton(self.view_f_btn)

        self._layout.addWidget(self.view_f_btn)
        self._layout.addWidget(self.view_2d_btn)
        if open_gl:  # hide 3d plot when now opengl is present
            self._layout.addWidget(self.view_3d_btn)

        self.setLayout(self._layout)
        self.style_widgets()

    def style_widgets(self):
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

        mode_btn_height = 35
        mode_btn_width = 65

        mode_btns = [self.view_f_btn, self.view_2d_btn, self.view_3d_btn]

        for btn in mode_btns:
            btn.setMinimumWidth(mode_btn_width)
            btn.setMaximumWidth(mode_btn_width)

            btn.setMinimumHeight(mode_btn_height)
            btn.setMaximumHeight(mode_btn_height)

        self.view_f_btn.setObjectName("file_btn")

        self.setStyleSheet("""
            QPushButton {
               font: normal 12px;
                border-radius: 0px;
            }
            
            #file_btn {
                border-radius: 0px;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
            }
            
        """)


class BatchStackWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchStackWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()

        self.img_pg_layout = GraphicsLayoutWidget()
        self.img_view = IntegrationBatchWidget(self.img_pg_layout, orientation='horizontal')

        self._layout.addWidget(self.img_pg_layout)
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)


class BatchOptionsWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchOptionsWidget, self).__init__()
        self._layout = QtWidgets.QVBoxLayout()

        self.tth_btn = CheckableFlatButton(u"2θ")
        self.tth_btn.setChecked(True)
        self.q_btn = CheckableFlatButton('Q')
        self.d_btn = CheckableFlatButton('d')
        self.unit_btn_group = QtWidgets.QButtonGroup()
        self.unit_btn_group.addButton(self.tth_btn)
        self.unit_btn_group.addButton(self.q_btn)
        self.unit_btn_group.addButton(self.d_btn)
        self.background_btn = CheckableFlatButton('bg')
        self.bkg_cut_btn = CheckableFlatButton('T')
        self.bkg_cut_btn.setToolTip("Trim data to show only region where background is calculated")

        self.scale_log_btn = CheckableFlatButton("log")
        self.scale_sqrt_btn = CheckableFlatButton("√")
        self.scale_lin_btn = CheckableFlatButton("lin")
        self.scale_lin_btn.setChecked(True)
        self.unit_scale_group = QtWidgets.QButtonGroup()
        self.unit_scale_group.addButton(self.scale_log_btn)
        self.unit_scale_group.addButton(self.scale_sqrt_btn)
        self.unit_scale_group.addButton(self.scale_lin_btn)

        self.create_layout()
        self.style_widgets()
        self.set_tooltips()

    def create_layout(self):
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.tth_btn)
        self._layout.addWidget(self.q_btn)
        self._layout.addWidget(self.d_btn)
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.scale_lin_btn)
        self._layout.addWidget(self.scale_sqrt_btn)
        self._layout.addWidget(self.scale_log_btn)
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.background_btn)
        self._layout.addWidget(self.bkg_cut_btn)

        self.setLayout(self._layout)

    def style_widgets(self):
        self._layout.setContentsMargins(4, 0, 4, 6)
        self._layout.setSpacing(4)

        self.setStyleSheet(
            """QPushButton{
                padding: 0px;
                padding-right: 1px;
                border-radius: 3px;
            }
            """)

    def set_tooltips(self):
        self.scale_log_btn.setToolTip("Change scale to log")
        self.scale_sqrt_btn.setToolTip("Change scale to sqrt")
        self.scale_lin_btn.setToolTip("Change scale to linear")


class BatchSurfaceWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchSurfaceWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()
        self.control_widget = BatchSurfaceViewNavigationWidget()

        self.surface_view = SurfaceWidget()
        self.pg_layout = self.surface_view.pg_layout

        self._layout.addWidget(self.control_widget)
        self._layout.addWidget(self.surface_view)
        self.setLayout(self._layout)

        self._layout.setContentsMargins(0, 0, 0, 0)


class BatchSurfaceViewNavigationWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchSurfaceViewNavigationWidget, self).__init__()

        self._layout = QtWidgets.QVBoxLayout()

        self.view3d_f_btn = FlatButton("F")
        self.view3d_s_btn = FlatButton("R")
        self.view3d_t_btn = FlatButton("T")
        self.view3d_i_btn = FlatButton("I")

        self.scale_x_btn = CheckableFlatButton('x')
        self.scale_y_btn = CheckableFlatButton('y')
        self.scale_z_btn = CheckableFlatButton('z')
        self.scale_s_btn = CheckableFlatButton('s')
        self.trim_h_btn = CheckableFlatButton('h')
        self.trim_l_btn = CheckableFlatButton('l')
        self.move_g_btn = CheckableFlatButton('g')
        self.move_m_btn = CheckableFlatButton('m')
        self.scale_s_btn.setChecked(True)

        self.scroll_btn_group = QtWidgets.QButtonGroup()
        self.scroll_btn_group.addButton(self.scale_x_btn)
        self.scroll_btn_group.addButton(self.scale_y_btn)
        self.scroll_btn_group.addButton(self.scale_z_btn)
        self.scroll_btn_group.addButton(self.scale_s_btn)
        self.scroll_btn_group.addButton(self.trim_h_btn)
        self.scroll_btn_group.addButton(self.trim_l_btn)
        self.scroll_btn_group.addButton(self.move_g_btn)
        self.scroll_btn_group.addButton(self.move_m_btn)

        self.m_color_btn = ColorButton()

        self.set_layout()
        self.style_widgets()
        self.set_tooltips()

    def set_layout(self):
        self._layout.addWidget(self.m_color_btn)
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.view3d_f_btn)
        self._layout.addWidget(self.view3d_s_btn)
        self._layout.addWidget(self.view3d_t_btn)
        self._layout.addWidget(self.view3d_i_btn)
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.scale_x_btn)
        self._layout.addWidget(self.scale_y_btn)
        self._layout.addWidget(self.scale_z_btn)
        self._layout.addWidget(self.scale_s_btn)
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.trim_h_btn)
        self._layout.addWidget(self.trim_l_btn)
        self._layout.addSpacerItem(VerticalSpacerItem())
        self._layout.addWidget(self.move_g_btn)
        self._layout.addWidget(self.move_m_btn)
        self.setLayout(self._layout)

    def set_tooltips(self):
        self.view3d_f_btn.setToolTip("Set front view")
        self.view3d_s_btn.setToolTip("Set right view")
        self.view3d_t_btn.setToolTip("Set top view")
        self.view3d_i_btn.setToolTip("Set isometric view")

        self.scale_x_btn.setToolTip("Scale plot in X direction")
        self.scale_y_btn.setToolTip("Scale plot in Y direction")
        self.scale_z_btn.setToolTip("Scale plot in Z direction")
        self.scale_s_btn.setToolTip("Scale plot")

        self.trim_h_btn.setToolTip("Cut higher values")
        self.trim_l_btn.setToolTip("Cut lower values")

        self.move_g_btn.setToolTip("Move grid along y axis")
        self.move_m_btn.setToolTip("Move marker along x axis")

        self.m_color_btn.setToolTip("Set marker color")

    def style_widgets(self):
        self._layout.setContentsMargins(4, 6, 4, 6)
        self._layout.setSpacing(4)

        self.setObjectName('pattern_left_control_widget')
        self.setMaximumWidth(30)
        self.setMinimumWidth(30)

        self.m_color_btn.setColor(0)
        self.m_color_btn.setMinimumHeight(80)

        self.setStyleSheet(
            """
                QPushButton{
                    padding: 0px;
                    padding-left: 1px;
                    border-radius: 3px;
                }
            """)


class BatchControlWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchControlWidget, self).__init__()
        self.integrate_btn = FlatButton("Integrate")
        self.load_proc_btn = FlatButton("Load proc data")

        self.waterfall_btn = CheckableFlatButton("Waterfall")

        self.calc_bkg_btn = FlatButton("Calc bkg")

        self.phases_btn = CheckableFlatButton('Show Phases')
        self.autoscale_btn = FlatButton("AutoScale")
        self.normalize_btn = FlatButton("Normalize")

        self._layout = QtWidgets.QHBoxLayout()

        self.create_layout()
        self.set_tooltips()
        self.style_widgets()

    def create_layout(self):
        self._layout.addWidget(self.integrate_btn)
        self._layout.addWidget(self.calc_bkg_btn)
        self._layout.addWidget(self.waterfall_btn)
        self._layout.addWidget(self.phases_btn)
        self._layout.addWidget(self.autoscale_btn)
        self._layout.addWidget(self.normalize_btn)

        self._layout.addSpacerItem(HorizontalSpacerItem())

        self.setLayout(self._layout)

    def set_tooltips(self):
        self.waterfall_btn.setToolTip("Create waterfall plot")
        self.calc_bkg_btn.setToolTip("Extract background")

    def style_widgets(self):
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(4)


class BatchImgPositionWidget(QtWidgets.QWidget):
    def __init__(self):
        super(BatchImgPositionWidget, self).__init__()

        self._layout = QtWidgets.QHBoxLayout()

        self.step_series_widget = StepBatchWidget()
        self.step_raw_widget = StepBatchWidget()
        self.step_raw_widget.hide()
        self.mouse_pos_widget = MouseCurrentAndClickedWidget(CLICKED_COLOR)

        self._layout = QtWidgets.QHBoxLayout()
        self.create_layout()
        self.style_widgets()

    def create_layout(self):
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.addWidget(self.step_series_widget)
        self._layout.addWidget(self.step_raw_widget)
        self._layout.addSpacerItem(HorizontalSpacerItem())
        self._layout.addWidget(self.mouse_pos_widget)

        self.setLayout(self._layout)

    def style_widgets(self):
        self.setStyleSheet(
            """
                QPushButton{
                    padding: 0px;
                    padding-right: 5px;
                    padding-left: 5px;
                    border-radius: 3px;
                }
            """)


class StepBatchWidget(QtWidgets.QWidget):
    """
    Widget to navigate across frame in the batch

    Widget contains:
        buttons: next, previous
        slider
        fields: step, min, max, current
    """
    switch_frame = QtCore.Signal(int)

    iteration_name = ''

    def __init__(self):
        super(StepBatchWidget, self).__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

        self.small_btn_max_width = 50
        self.small_btn_min_width = 20

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(5, 0, 0, 5)
        self.init_navigator()

        self.setLayout(self._layout)

    def init_navigator(self):
        self.next_btn = FlatButton('>')
        self.next_btn.setToolTip('Loads next {}'.format(self.iteration_name))
        self.previous_btn = FlatButton('<')
        self.previous_btn.setToolTip(('Loads previous {}'.format(self.iteration_name)))

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)

        self.step_txt = QtWidgets.QSpinBox()
        self.step_txt.setValue(1)
        self.step_txt.setRange(1, 10000)

        self.stop_txt = QtWidgets.QSpinBox()
        self.stop_txt.setValue(0)
        self.stop_txt.setRange(0, 99000)

        self.start_txt = QtWidgets.QSpinBox()
        self.start_txt.setValue(0)
        self.start_txt.setRange(0, 99000)

        self.next_btn.setMaximumWidth(self.small_btn_max_width)
        self.previous_btn.setMaximumWidth(self.small_btn_max_width)
        self.next_btn.setMinimumWidth(self.small_btn_min_width)
        self.previous_btn.setMinimumWidth(self.small_btn_min_width)
        self.step_txt.setMinimumWidth(25)

        self._navigator_layout = QtWidgets.QGridLayout()
        self._navigator_layout.addWidget(self.previous_btn, 0, 0)
        self._navigator_layout.addWidget(self.slider, 0, 1)
        self._navigator_layout.addWidget(self.next_btn, 0, 2)

        self._step_layout = QtWidgets.QHBoxLayout()
        self._step_layout.addWidget(LabelAlignRight('Start:'))
        self._step_layout.addWidget(self.start_txt)
        self._step_layout.addWidget(LabelAlignRight('Stop:'))
        self._step_layout.addWidget(self.stop_txt)
        self._step_layout.addWidget(LabelAlignRight('Step:'))
        self._step_layout.addWidget(self.step_txt)
        self._navigator_layout.addLayout(self._step_layout, 1, 0, 1, 3)
        self._layout.addLayout(self._navigator_layout)

        self.pos_txt = QtWidgets.QLineEdit()
        self.pos_validator = QtGui.QIntValidator(1, 1)
        self.pos_txt.setText('0')
        self.pos_txt.setValidator(self.pos_validator)
        self.pos_txt.setToolTip('Currently loaded frame')
        self.pos_label = QtWidgets.QLabel('Frame:')
        self.pos_label.setToolTip("Number of frames: integrated/raw")
        self.pos_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)

        self._pos_layout = QtWidgets.QVBoxLayout()
        self._pos_layout.addWidget(self.pos_label)
        self._pos_layout.addWidget(self.pos_txt)
        self._layout.addLayout(self._pos_layout)

        self.pos_txt.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Maximum)

        self.next_btn.clicked.connect(self.process_next_img)
        self.previous_btn.clicked.connect(self.process_prev_img)
        self.pos_txt.editingFinished.connect(self.process_pos_img)
        self.slider.sliderReleased.connect(self.process_slider)

    def process_next_img(self):
        step = self.step_txt.value()
        stop = self.stop_txt.value()
        pos = int(self.pos_txt.text())
        y = pos + step
        if y > stop:
            return
        self.pos_txt.setText(str(y))
        self.slider.setValue(y)
        self.switch_frame.emit(y)

    def process_prev_img(self):
        step = self.step_txt.value()
        start = self.start_txt.value()
        pos = int(self.pos_txt.text())
        y = pos - step
        if y < start:
            return
        self.pos_txt.setText(str(y))
        self.slider.setValue(y)
        self.switch_frame.emit(y)

    def process_pos_img(self):
        y = int(self.pos_txt.text())
        self.pos_txt.setText(str(y))
        self.slider.setValue(y)
        self.switch_frame.emit(y)

    def process_slider(self):
        y = self.slider.value()
        self.pos_txt.setText(str(y))
        self.switch_frame.emit(y)

    def get_image_range(self):
        step = self.step_txt.value()
        stop = self.stop_txt.value()
        start = self.start_txt.value()
        return start, stop, step
