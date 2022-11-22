import os
import gc
import numpy as np

from ..utility import QtTest, MockMouseEvent

from ...widgets.integration import IntegrationWidget
from ...controller.integration.BatchController import BatchController
from ...controller.integration.phase.PhaseController import PhaseController
from ...controller.integration.PatternController import PatternController
from ...model.DioptasModel import DioptasModel

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
        self.pattern_controller = PatternController(self.widget, self.model)

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

    def test_initial_state(self):
        self.assertEqual(self.model.batch_model.n_img_all, 50)
        self.assertEqual(self.model.batch_model.n_img, 50)
        self.assertEqual(self.model.batch_model.binning.shape, (4038,))
        self.assertEqual(self.model.batch_model.data.shape, (50, 4038))

    def test_is_proc(self):
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00000.nxs')
        is_proc = self.controller.is_proc(filename)
        self.assertFalse(is_proc)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        is_proc = self.controller.is_proc(filename)
        self.assertTrue(is_proc)

    def test_change_3d_view(self):
        self.widget.batch_widget.activate_surface_view()

        self.controller.set_3d_view_f()
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        self.assertEqual(pg_layout.opts['azimuth'], 0)
        self.assertEqual(pg_layout.opts['elevation'], 0)

        self.controller.set_3d_view_t()
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        self.assertEqual(pg_layout.opts['azimuth'], 0)
        self.assertEqual(pg_layout.opts['elevation'], 90)

        self.controller.set_3d_view_s()
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        self.assertEqual(pg_layout.opts['azimuth'], 90)
        self.assertEqual(pg_layout.opts['elevation'], 0)

        self.controller.set_3d_view_i()
        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        self.assertEqual(pg_layout.opts['azimuth'], 45)
        self.assertEqual(pg_layout.opts['elevation'], 30)

    def test_wheel_event_3d(self):
        self.widget.batch_widget.activate_surface_view()
        self.controller.change_view()

        pg_layout = self.widget.batch_widget.surface_widget.surface_view.pg_layout
        show_scale = self.widget.batch_widget.surface_widget.surface_view.show_scale
        show_range = self.widget.batch_widget.surface_widget.surface_view.show_range
        surf_view = self.widget.batch_widget.surface_widget.surface_view

        self.assertEqual(pg_layout.opts['distance'], 3)
        self.assertTrue(np.all(show_scale == [2, 2, 1]))
        self.assertTrue(np.all(show_range == [0, 1]))
        self.assertEqual(surf_view.g_translate, 0)
        self.assertEqual(surf_view.marker, 0)

        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertLess(pg_layout.opts['distance'], 10)

        self.controller.key_pressed_3d(MockMouseEvent(key=76))
        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertGreater(show_range[0], 0)

        self.controller.key_pressed_3d(MockMouseEvent(key=88))
        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertGreater(show_scale[0], 2.)

        self.controller.key_pressed_3d(MockMouseEvent(key=89))
        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertGreater(show_scale[1], 2.)

        self.controller.key_pressed_3d(MockMouseEvent(key=90))
        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertGreater(show_scale[2], 1.)

        self.controller.key_pressed_3d(MockMouseEvent(key=71))
        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertEqual(surf_view.g_translate, 2)

        self.controller.key_pressed_3d(MockMouseEvent(key=77))
        self.controller.wheel_event_3d(MockMouseEvent())
        self.assertGreater(surf_view.marker, 0)

    def test_pattern_left_click(self):
        self.widget.batch_widget.activate_stack_plot()
        self.controller.change_view()
        self.assertEqual(self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos(), 0)
        self.pattern_controller.pattern_left_click(15, None)
        first_pos = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
        self.pattern_controller.pattern_left_click(16, None)
        second_pos = self.widget.batch_widget.stack_plot_widget.img_view.vertical_line.getXPos()
        self.assertNotEqual(first_pos, second_pos)

    def test_subtract_background(self):
        self.widget.batch_widget.activate_stack_plot()
        self.model.batch_model.data = np.ones((100, 1000))
        self.model.batch_model.bkg = np.ones((100, 1000))
        self.widget.batch_widget.options_widget.background_btn.setChecked(True)
        self.controller.subtract_background()
        self.assertTrue(self.widget.batch_widget.options_widget.background_btn.isChecked())
        self.assertTrue(
            np.all(self.widget.batch_widget.stack_plot_widget.img_view.img_data == self.controller.min_val['lin']))

    def test_extract_background(self):
        self.model.batch_model.data[...] = 1.0
        self.assertTrue(self.model.batch_model.bkg is None)
        self.controller.extract_background()
        self.assertTrue(np.allclose(self.model.batch_model.bkg, 1.0))

    def test_change_scale(self):
        self.widget.batch_widget.activate_stack_plot()
        self.model.batch_model.data[:, :] = 100

        self.controller.change_scale_log(MockMouseEvent())
        self.assertEqual(self.controller.scale, np.log10)
        self.assertTrue(np.all(self.widget.batch_widget.stack_plot_widget.img_view.img_data == 2.))

        self.controller.change_scale_sqrt(MockMouseEvent())
        self.assertEqual(self.controller.scale, np.sqrt)
        self.assertTrue(np.all(self.widget.batch_widget.stack_plot_widget.img_view.img_data == 10.))

        self.controller.change_scale_lin(MockMouseEvent())
        self.assertEqual(self.controller.scale, np.array)
        self.assertTrue(np.all(self.widget.batch_widget.stack_plot_widget.img_view.img_data == 100.))

    def test_process_step(self):
        # Test here only 3D plot, because waterfall is tested on functional tests
        self.widget.batch_widget.activate_surface_view()
        self.controller.plot_batch()

        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.data.shape[0], 50)
        self.widget.batch_widget.position_widget.step_series_widget.step_txt.setValue(2)
        self.controller.process_step()
        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.data.shape[0], 25)

    def test_switch_frame(self):
        self.widget.batch_widget.activate_surface_view()
        self.controller.switch_frame(49)
        self.assertEqual(self.widget.batch_widget.surface_widget.surface_view.g_translate, 49)
        self.assertEqual(self.widget.batch_widget.position_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(),
                         'Img: 49')

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00004.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 9")
