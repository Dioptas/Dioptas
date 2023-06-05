import os
from dioptas.model.util.cosmics import cosmicsimage
from dioptas.model.ImgModel import ImgModel

from ..utility import unittest_data_path


def test_cosmics_image():
    img_model = ImgModel()
    img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
    test = cosmicsimage(img_model.img_data, sigclip=3.0, objlim=3.0)
    test.lacosmiciteration(True)
    test.clean()
    assert test is not None
    assert test.mask.shape == img_model.img_data.shape
