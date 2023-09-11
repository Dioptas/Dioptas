import os
import pytest

import numpy as np

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


@pytest.fixture()
def img_model():
    img_model = ImgModel()
    yield img_model


@pytest.fixture()
def batch_model(img_model):
    calibration_model = CalibrationModel(img_model)
    calibration_model.load(cal_file)
    mask_model = MaskModel()
    mask_model.mode = False
    batch_model = BatchModel(calibration_model, mask_model)
    batch_model.set_image_files(files)

    pattern = Pattern().load(os.path.join(data_path, 'CeO2_Pilatus1M.xy'))
    calibration_model.integrate_1d = MagicMock(return_value=(pattern.x, pattern.y))

    yield batch_model

    reset_calibration_model(calibration_model)


def reset_calibration_model(calibration_model):
    calibration_model.pattern_geometry.reset()
    del calibration_model.pattern_geometry
    if calibration_model.cake_geometry is not None:
        calibration_model.cake_geometry.reset()
        del calibration_model.cake_geometry
    gc.collect()


def test_init_state(batch_model):
    assert batch_model.raw_available
    assert np.all(batch_model.file_map == [0, 10, 20])
    assert batch_model.n_img_all == 20
    assert batch_model.pos_map_all.shape == (20, 2)


def test_integrate_raw_data(batch_model):
    num_points = 1500
    start = 2
    stop = 18
    step = 2

    batch_model.integrate_raw_data(num_points, start, stop, step, use_all=True)

    assert batch_model.data.shape[0] == 8
    assert batch_model.n_img == 8
    assert np.all(batch_model.pos_map[0] == [0, 2])
    assert batch_model.pos_map.shape == (8, 2)


def test_get_image_info(batch_model):
    image = 10
    name, pos = batch_model.get_image_info(image, use_all=True)
    assert name == files[1]
    assert pos == 0


def test_load_image(batch_model, img_model):
    index = 10
    batch_model.load_image(index, use_all=True)
    assert img_model.img_data.shape == (1833, 1556)


def test_saving_loading(batch_model, tmp_path):
    num_points = 1500
    start = 2
    stop = 18
    step = 2

    batch_model.integrate_raw_data(num_points, start, stop, step, use_all=True)
    batch_model.save_proc_data(os.path.join(tmp_path, "test_save_proc.nxs"))
    batch_model.reset_data()
    batch_model.load_proc_data(os.path.join(tmp_path, "test_save_proc.nxs"))

    assert batch_model.data.shape[0] == 8
    assert batch_model.n_img == 8
    assert np.all(batch_model.pos_map[0] == [0, 2])
    assert batch_model.pos_map.shape == (8, 2)


def test_save_as_csv(batch_model, tmp_path):
    batch_model.integrate_raw_data(num_points=1000, start=5, stop=10, step=2, use_all=True)
    batch_model.save_as_csv(os.path.join(tmp_path, "test_save.csv"))
    assert os.path.exists(os.path.join(tmp_path, "test_save.csv"))


def test_extract_background(batch_model):
    batch_model.integrate_raw_data(num_points=1000, start=5, stop=10, step=2, use_all=True)
    batch_model.extract_background(parameters=(0.1, 150, 50))
    assert batch_model.bkg.shape[0] == 3


def test_normalize(batch_model):
    batch_model.reset_data()
    batch_model.data = np.ones((3, 80))
    for i in range(batch_model.data.shape[0]):
        batch_model.data[i] *= np.random.random()

    batch_model.normalize()
    assert pytest.approx(0) == np.sum(np.diff(batch_model.data[:, 1]))


def test_iterate_folder():
    assert iterate_folder("r001", 1) == "r002"
    assert iterate_folder("r009", 1) == "r010"
    assert iterate_folder("r009", -1) == "r008"

    assert iterate_folder("test/r009", -1) == "test/r008"
    assert iterate_folder("test/r009", 1) == "test/r010"

    assert iterate_folder("exp/0250/test/r001", 1) == "exp/0250/test/r002"
    assert iterate_folder("exp/0250/test/r001", -1) == "exp/0250/test/r000"
    assert iterate_folder("exp/0250/test/r001", 10) == "exp/0250/test/r011"
    assert iterate_folder("exp/0250/test/r001", -10) == "exp/0250/test/r000"

    assert iterate_folder("exp234/02321/test/r099", 1) == "exp234/02321/test/r100"
    assert iterate_folder("exp234/02321/test/r099", -1) == "exp234/02321/test/r098"
    assert iterate_folder("exp234/02321/test/r099", 10) == "exp234/02321/test/r109"
    assert iterate_folder("exp234/02321/test/r099", -10) == "exp234/02321/test/r089"

    assert iterate_folder("exp234/02321/test/r999", 1) == "exp234/02321/test/r1000"
    assert iterate_folder("exp234/02321/test/r999", -1) == "exp234/02321/test/r998"
    assert iterate_folder("exp234/02321/test/r999", 10) == "exp234/02321/test/r1009"

    assert iterate_folder("exp234/02321/test/r100", -1) == "exp234/02321/test/r099"
