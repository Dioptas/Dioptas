import os
import gc
import shutil
from mock import MagicMock

from ..utility import QtTest, click_button

from qtpy import QtWidgets, QtGui

from ...widgets.integration import IntegrationWidget
from ...widgets.plot_widgets.ImgWidget import MyRectangle
from ...controller.integration.BatchController import BatchController
from ...model.DioptasModel import DioptasModel
from dioptas.controller.integration.phase.PhaseController import PhaseController

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')
jcpds_path = os.path.join(unittest_data_path, 'jcpds')


class BatchControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = BatchController(
            widget=self.widget,
            dioptas_model=self.model)

        self.phase_controller = PhaseController(self.widget, self.model)

        # Load existing proc+raw data
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        self.model.batch_model.load_proc_data(filename)
        raw_files = self.model.batch_model.files
        raw_files = [os.path.join(os.path.dirname(filename), os.path.basename(f)) for f in raw_files]
        self.model.batch_model.set_image_files(raw_files)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(self.model.batch_model.n_img - 1)

    def tearDown(self):
        del self.phase_controller
        del self.controller
        del self.model
        del self.widget
        gc.collect()
        gc.garbage

    def test_set_range_img(self):
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(25)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(50)

        self.controller.set_range_img()
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.slider.value(), 25)

        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(20)
        self.controller.set_range_img()
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.slider.value(), 20)

    def test_show_img_mouse_position(self):
        self.widget.batch_widget.activate_stack_plot()
        self.controller.show_img_mouse_position(10, 15)

        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.text(),
                         'Img: 15')
        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.text(),
                         '2θ: 9.7')
        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.cur_pos_widget.int_lbl.text(),
                         'I: 0.1')

    def test_load_raw_data(self):
        files = [os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs'),
                 os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')]

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=files)
        self.controller.load_data()

        self.assertTrue(self.model.batch_model.data is None)
        self.assertTrue(self.model.batch_model.binning is None)
        self.assertTrue(self.model.batch_model.raw_available)

        start, stop, step = self.widget.batch_widget.position_widget.step_raw_widget.get_image_range()
        frame = str(self.widget.batch_widget.position_widget.step_series_widget.pos_label.text())
        self.assertEqual(stop, 19)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(None/20):")

        self.assertEqual(self.widget.batch_widget.file_view_widget.tree_model.columnCount(), 2)
        self.assertTrue((self.model.batch_model.files == files).all())

    def test_load_proc_data(self):
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[filename])
        self.model.working_directories['image'] = os.path.join(unittest_data_path, 'lambda')
        self.controller.load_data()

        self.assertTrue(self.model.batch_model.data is not None)
        # self.assertTrue(self.model.batch_model.raw_available)
        self.assertEqual(self.model.batch_model.data.shape[0], 50)
        self.assertEqual(self.model.batch_model.data.shape[1],
                         self.model.batch_model.binning.shape[0])
        self.assertEqual(self.model.batch_model.data.shape[0],
                         self.model.batch_model.n_img)
        start = int(str(self.widget.batch_widget.position_widget.step_series_widget.start_txt.text()))
        stop = int(str(self.widget.batch_widget.position_widget.step_series_widget.stop_txt.text()))
        frame = str(self.widget.batch_widget.position_widget.step_series_widget.pos_label.text())
        self.assertEqual(stop, 49)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(50/50):")

        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(),
                         'Img: 0')
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.slider.value(), 0)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs').split(
            '/')[-1].split('\\')[-1]
        self.assertTrue(filename in self.widget.batch_widget.windowTitle())
        # self.assertEqual(self.model.calibration_model.calibration_name, 'L2')

    def test_plot_batch_2d(self):
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(10)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(40)
        self.widget.batch_widget.activate_stack_plot()

        self.controller.plot_batch()
        self.assertEqual(self.widget.batch_widget.stack_plot_widget.img_view.img_data.shape, (31, 4038))
        self.assertTrue(self.widget.batch_widget.stack_plot_widget.img_view._max_range)
        self.assertEqual(self.widget.batch_widget.stack_plot_widget.img_view.horizontal_line.value(), 0)
        self.assertAlmostEqual(self.widget.batch_widget.stack_plot_widget.img_view.left_axis_cake.range[0], 7.28502051,
                               places=1)
        self.assertAlmostEqual(self.widget.batch_widget.stack_plot_widget.img_view.left_axis_cake.range[1], 42.7116293,
                               places=1)

    def test_plot_batch_3d(self):
        self.widget.batch_widget.activate_surface_view()
        self.widget.batch_widget.position_widget.step_series_widget.start_txt.setValue(10)
        self.widget.batch_widget.position_widget.step_series_widget.stop_txt.setValue(40)
        self.controller.plot_batch()

        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.step_txt.value(), 1)
        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.data.shape, (31, 4038))
        # self.assertEqual(len(self.widget.batch_widget.surf_view.axis.ticks), 1) --> currently axis is not implemented

    def test_img_mouse_click(self):
        # Test only image loading. Waterfall is already tested
        self.controller.img_mouse_click(10, 15)

        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.g_translate, 0)
        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(),
                         'Img: 15')
        self.assertEqual(self.widget.batch_widget.position_widget.step_series_widget.slider.value(), 15)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")

    def test_process_waterfall(self):
        self.controller.process_waterfall(5, 7)
        self.assertEqual(self.controller.rect.rect().left(), 5)
        self.assertEqual(self.controller.rect.rect().bottom(), 7)
        self.assertEqual(self.controller.clicks, 1)

        self.controller.process_waterfall(10, 17)
        self.assertEqual(self.controller.clicks, 0)

    def test_plot_waterfall(self):
        self.controller.rect = MyRectangle(5, 7, 10, 17, QtGui.QColor(255, 0, 0, 150))

        self.controller.plot_waterfall()

        self.assertEqual(len(self.model.overlay_model.overlays), 17)
        self.assertEqual(self.model.overlay_model.overlays[0].name,
                         'testasapo1_1009_00002_m1_part00002.nxs, 4')
        self.assertEqual(self.model.overlay_model.overlays[0]._pattern_x.shape, (10,))

    def test_normalize(self):
        click_button(self.widget.batch_widget.control_widget.normalize_btn)
        