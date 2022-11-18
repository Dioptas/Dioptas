import os

import numpy as np

from ..utility import QtTest, delete_if_exists
from ...model.CalibrationModel import CalibrationModel
from ...model.ImgModel import ImgModel
from ...model.MaskModel import MaskModel
from ...model.BatchModel import BatchModel, iterate_folder
from ...model.util.Pattern import Pattern

import gc
from mock import MagicMock

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
files = [os.path.join(data_path, 'lambda/testasapo1_1009_00002_m1_part00000.nxs'),
         os.path.join(data_path, 'lambda/testasapo1_1009_00002_m1_part00001.nxs')]

cal_file = os.path.join(data_path, 'lambda/L2.poni')


class BatchModelTest(QtTest):
    def setUp(self):
        self.img_model = ImgModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.calibration_model.load(cal_file)
        self.mask_model = MaskModel()
        self.mask_model.mode = False
        self.batch_model = BatchModel(self.calibration_model, self.mask_model)
        self.batch_model.set_image_files(files)

        pattern = Pattern().load(os.path.join(data_path, 'CeO2_Pilatus1M.xy'))
        self.calibration_model.integrate_1d = MagicMock(return_value=(pattern.x,
                                                                            pattern.y))

    def tearDown(self):
        delete_if_exists(os.path.join(data_path, 'detector_with_spline.h5'))
        delete_if_exists(os.path.join(data_path, "test_save_proc.nxs"))
        del self.img_model
        del self.calibration_model.pattern_geometry
        del self.calibration_model
        del self.mask_model
        del self.batch_model
        gc.collect()

    def test_init_state(self):
        self.assertTrue(self.batch_model.raw_available)
        self.assertTrue(np.all(self.batch_model.file_map == [0, 10, 20]))
        self.assertEqual(self.batch_model.n_img_all, 20)
        self.assertEqual(self.batch_model.pos_map_all.shape, (20, 2))

    def test_integrate_raw_data(self):
        num_points = 1500
        start = 2
        stop = 18
        step = 2

        self.batch_model.integrate_raw_data(num_points, start, stop, step, use_all=True)

        self.assertEqual(self.batch_model.data.shape[0], 8)
        self.assertEqual(self.batch_model.n_img, 8)
        self.assertTrue(np.all(self.batch_model.pos_map[0] == [0, 2]))
        self.assertEqual(self.batch_model.pos_map.shape, (8, 2))

    def test_get_image_info(self):
        image = 10
        name, pos = self.batch_model.get_image_info(image, use_all=True)
        self.assertEqual(name, files[1])
        self.assertEqual(pos, 0)

    def test_load_image(self):
        index = 10
        self.batch_model.load_image(index, use_all=True)
        self.assertEqual(self.img_model.img_data.shape, (1833, 1556))

    def test_saving_loading(self):
        num_points = 1500
        start = 2
        stop = 18
        step = 2

        self.batch_model.integrate_raw_data(num_points, start, stop, step, use_all=True)
        self.batch_model.save_proc_data(os.path.join(data_path, "test_save_proc.nxs"))
        self.batch_model.reset_data()
        self.batch_model.load_proc_data(os.path.join(data_path, "test_save_proc.nxs"))

        self.assertEqual(self.batch_model.data.shape[0], 8)
        self.assertEqual(self.batch_model.n_img, 8)
        self.assertTrue(np.all(self.batch_model.pos_map[0] == [0, 2]))
        self.assertEqual(self.batch_model.pos_map.shape, (8, 2))

    def test_save_as_csv(self):
        self.batch_model.integrate_raw_data(num_points=1000, start=5, stop=10, step=2, use_all=True)
        self.batch_model.save_as_csv(os.path.join(data_path, "test_save.csv"))
        self.assertTrue(os.path.exists(os.path.join(data_path, "test_save.csv")))
        os.remove(os.path.join(data_path, "test_save.csv"))

    def test_extract_background(self):
        self.batch_model.integrate_raw_data(num_points=1000, start=5, stop=10, step=2, use_all=True)
        self.batch_model.extract_background(parameters=(0.1, 150, 50))
        self.assertEqual(self.batch_model.bkg.shape[0], 3)

    def test_normalize(self):
        self.batch_model.reset_data()
        self.batch_model.data = np.ones((3, 80))
        for i in range(self.batch_model.data.shape[0]):
            self.batch_model.data[i] *= np.random.random()

        self.batch_model.normalize()
        self.assertAlmostEqual(0, np.sum(np.diff(self.batch_model.data[:, 1])))

    def test_iterate_folder(self):
        self.assertEqual(iterate_folder("r001", 1), "r002")
        self.assertEqual(iterate_folder("r009", 1), "r010")
        self.assertEqual(iterate_folder("r009", -1), "r008")

        self.assertEqual(iterate_folder("test/r009", -1), "test/r008")
        self.assertEqual("exp/0250/test/r002", iterate_folder("exp/0250/test/r001", 1))
        self.assertEqual("exp234/02321/test/r100", iterate_folder("exp234/02321/test/r099", 1))
        self.assertEqual("exp234/02321/test/r1000", iterate_folder("exp234/02321/test/r999", 1))

