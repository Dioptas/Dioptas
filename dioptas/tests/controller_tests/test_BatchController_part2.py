import os
import gc
import shutil
import numpy as np
from mock import MagicMock

from ..utility import QtTest

from qtpy import QtWidgets, QtCore, QtGui

from ...widgets.integration import IntegrationWidget
from ...widgets.plot_widgets.ImgWidget import MyRectangle
from ...controller.integration.BatchController import BatchController
from ...model.DioptasModel import DioptasModel
from dioptas.controller.integration.phase.PhaseController import PhaseController

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')
jcpds_path = os.path.join(unittest_data_path, 'jcpds')


class TestMouseEvent:
    def __init__(self, key=None, diff=None):
        self.key_value = key
        self.diff = diff

        class TestCoord:
            def x(self):
                return 100

            def y(self):
                return 100

        self.coord = TestCoord()

    def key(self):
        return self.key_value

    def x(self):
        return self.diff

    def angleDelta(self):
        return self.coord

    def modifiers(self):
        return QtCore.Qt.CoverWindow

    def button(self):
        return QtCore.Qt.CoverWindow


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
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(self.model.batch_model.n_img - 1)

    def tearDown(self):
        del self.phase_controller
        del self.controller
        del self.model
        del self.widget
        gc.collect()
        gc.garbage

    def test_set_range_img(self):
        self.widget.batch_widget.step_series_widget.start_txt.setValue(25)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(50)

        self.controller.set_range_img()
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 25)

        self.widget.batch_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(20)
        self.controller.set_range_img()
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 20)

    def test_show_img_mouse_position(self):
        self.controller.show_img_mouse_position(10, 15)

        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.cur_pos_widget.x_pos_lbl.text(), 'Img: 15')
        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.cur_pos_widget.y_pos_lbl.text(), '2θ:9.7')
        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.cur_pos_widget.int_lbl.text(), '0.1')

    def test_directory_txt_changed(self):
        test_raw_folder = os.path.join(unittest_data_path, 'lambda_temp')
        shutil.copytree(os.path.join(unittest_data_path, 'lambda'),
                        test_raw_folder)

        self.widget.img_directory_txt.setText(test_raw_folder)
        self.controller.directory_txt_changed()
        self.assertTrue(test_raw_folder in self.model.batch_model.files[0])

        shutil.rmtree(test_raw_folder)

    def test_load_raw_data(self):
        files = [os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs'),
                 os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')]

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=files)
        self.controller.load_data()

        self.assertTrue(self.model.batch_model.data is None)
        self.assertTrue(self.model.batch_model.binning is None)
        self.assertTrue(self.model.batch_model.raw_available)

        start = int(str(self.widget.batch_widget.step_series_widget.start_txt.text()))
        stop = int(str(self.widget.batch_widget.step_series_widget.stop_txt.text()))
        frame = str(self.widget.batch_widget.step_series_widget.pos_label.text())
        self.assertEqual(stop, 19)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(None/20):")

        self.assertEqual(self.widget.batch_widget.file_view_widget.tree_model.columnCount(), 2)
        self.assertTrue((self.model.batch_model.files == files).all())

    def test_load_proc_data(self):
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[filename])
        self.controller.load_data()

        self.assertTrue(self.model.batch_model.data is not None)
        self.assertTrue(self.model.batch_model.raw_available)
        self.assertEqual(self.model.batch_model.data.shape[0], 50)
        self.assertEqual(self.model.batch_model.data.shape[1],
                         self.model.batch_model.binning.shape[0])
        self.assertEqual(self.model.batch_model.data.shape[0],
                         self.model.batch_model.n_img)
        start = int(str(self.widget.batch_widget.step_series_widget.start_txt.text()))
        stop = int(str(self.widget.batch_widget.step_series_widget.stop_txt.text()))
        frame = str(self.widget.batch_widget.step_series_widget.pos_label.text())
        self.assertEqual(stop, 49)
        self.assertEqual(start, 0)
        self.assertEqual(frame, "Frame(50/50):")

        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(), 'Img: 0')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 0)

        unittest_path = os.path.dirname(__file__)
        tests_dir = unittest_path[:unittest_path.find('controller_tests')]
        filename = os.path.join(tests_dir, 'data', 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 0")
        self.assertEqual(self.model.calibration_model.calibration_name, 'L2')

    def test_plot_batch_2d(self):
        self.widget.batch_widget.step_series_widget.start_txt.setValue(10)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(40)
        self.widget.batch_widget.view_2d_btn.setChecked(True)
        self.controller.plot_batch()
        self.assertEqual(self.widget.batch_widget.img_view.img_data.shape, (31, 4038))
        self.assertTrue(self.widget.batch_widget.img_view._max_range)
        self.assertEqual(self.widget.batch_widget.img_view.horizontal_line.value(), 0)
        self.assertAlmostEqual(self.widget.batch_widget.img_view.left_axis_cake.range[0], 7.28502051, places=3)
        self.assertAlmostEqual(self.widget.batch_widget.img_view.left_axis_cake.range[1], 42.7116293, places=3)

    def test_plot_batch_3d(self):
        self.widget.batch_widget.step_series_widget.start_txt.setValue(10)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(40)
        self.widget.batch_widget.view_3d_btn.setChecked(True)
        self.controller.plot_batch()

        self.assertEqual(self.widget.batch_widget.step_series_widget.step_txt.value(), 1)
        self.assertEqual(self.widget.batch_widget.surf_view.data.shape, (31, 4038))
        self.assertEqual(len(self.widget.batch_widget.surf_view.axis.ticks), 1)

    def test_img_mouse_click(self):
        # Test only image loading. Waterfall is already tested
        self.controller.img_mouse_click(10, 15)

        self.assertEqual(self.widget.batch_widget.surf_view.g_translate, 0)
        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(), 'Img: 15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)

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

    def test_load_single_image(self):
        self.controller.load_single_image(10, 15)

        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(), 'Img: 15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")
        self.assertEqual(self.widget.batch_widget.img_view.horizontal_line.value(), 15)

    def test_plot_pattern(self):
        self.controller.plot_pattern(10, 15)

        self.assertAlmostEqual(self.model.pattern_model.pattern.data[0][0], 9.6926780, places=3)
        self.assertEqual(self.model.pattern_model.pattern.data[1][0], np.float32(0.1))

    def test_plot_image(self):
        self.controller.plot_image(15)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")
        self.assertTrue(self.model.current_configuration.auto_integrate_pattern)

        self.assertEqual(self.widget.batch_widget.step_series_widget.pos_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)
        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(), f'Img: 15')

    def test_update_3d_axis(self):
        self.controller.update_3d_axis(np.full((10, 1000), 80))

        self.assertEqual(self.widget.batch_widget.surf_view.axis.ticks[0].text, '9.69')
        self.assertEqual(self.widget.batch_widget.surf_view.g.spacing(), [10.0, 1000., 1])

    def test_update_y_axis(self):
        self.widget.batch_widget.step_series_widget.slider.setValue(15)
        self.widget.batch_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(28)

        self.controller.update_y_axis()
        self.assertAlmostEqual(self.widget.batch_widget.img_view.left_axis_cake.range[0],
                               2.898080396, places=3)
        self.assertAlmostEqual(self.widget.batch_widget.img_view.left_axis_cake.range[1],
                               30.3251324, places=3)

    def test_integrate(self):
        self.widget.batch_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(28)
        self.widget.batch_widget.step_series_widget.step_txt.setValue(3)

        self.controller.integrate()

        self.assertEqual(self.model.batch_model.data.shape, (8, 4038))
        self.assertEqual(self.model.batch_model.binning.shape, (4038,))
        self.assertEqual(self.model.batch_model.n_img, 8)
        self.assertEqual(self.model.batch_model.n_img_all, 50)
        self.assertEqual(self.model.batch_model.pos_map.shape, (8, 2))

    def test_set_navigation_range(self):
        self.controller.set_navigation_range((10, 50), (15, 80))
        self.assertEqual(self.widget.batch_widget.step_series_widget.start_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.stop_txt.text(), '49')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)

        self.widget.batch_widget.step_series_widget.slider.setValue(60)
        self.controller.set_navigation_range((10, 50), (15, 80))
        self.assertEqual(self.widget.batch_widget.step_series_widget.start_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.stop_txt.text(), '49')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 49)

        self.widget.batch_widget.step_series_widget.slider.setValue(60)
        self.controller.set_navigation_range((10, 50), (15, 40))
        self.assertEqual(self.widget.batch_widget.step_series_widget.start_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.stop_txt.text(), '40')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 40)

        # ToDo Test interaction with other controllers: Integration window vertical line. Patterns
