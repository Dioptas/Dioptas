# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest

import pytest
from mock import MagicMock
import os

import numpy as np

from ...model.ImgModel import ImgModel, BackgroundDimensionWrongException
from ...model.util.ImgCorrection import DummyCorrection

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')
spe_path = os.path.join(data_path, 'spe')


@pytest.fixture
def img_model():
    img_model = ImgModel()
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    return ImgModel()


def test_load_karabo_nexus_file(img_model):
    img_model.load(os.path.join(data_path, 'karabo_epix.h5'))


def perform_transformations_tests(img_model):
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.rotate_img_m90()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.flip_img_horizontally()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.rotate_img_p90()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.flip_img_vertically()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.reset_transformations()
    assert np.sum(np.absolute(img_model.img_data)) == 0


def test_load_emits_signal(img_model):
    callback_fcn = MagicMock()
    img_model.img_changed.connect(callback_fcn)
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    callback_fcn.assert_called_once_with()


def test_flipping_images(img_model):
    original_image = np.copy(img_model._img_data)
    img_model.flip_img_vertically()
    assert np.array_equal(img_model._img_data, np.flipud(original_image))


def test_simple_background_subtraction(img_model):
    first_image = np.copy(img_model.img_data)
    img_model.load_next_file()
    second_image = np.copy(img_model.img_data)

    img_model.load(os.path.join(data_path, 'image_001.tif'))
    img_model.load_background(os.path.join(data_path, 'image_002.tif'))

    assert not np.array_equal(first_image, img_model.img_data)

    img_model.load_next_file()
    assert np.sum(img_model.img_data) == 0


def test_background_subtraction_with_transformation(img_model):
    img_model.load_background(os.path.join(data_path, 'image_002.tif'))
    original_img = np.copy(img_model._img_data)
    original_background = np.copy(img_model._background_data)

    assert img_model._background_data is not None
    assert not np.array_equal(img_model.img_data, img_model._img_data)

    original_img_background_subtracted = np.copy(img_model.img_data)
    assert np.array_equal(original_img_background_subtracted, original_img - original_background)

    ### now comes the main process - flipping the image
    img_model.flip_img_vertically()
    flipped_img = np.copy(img_model._img_data)
    assert np.array_equal(np.flipud(original_img), flipped_img)

    flipped_background = np.copy(img_model._background_data)
    assert np.array_equal(np.flipud(original_background), flipped_background)

    flipped_img_background_subtracted = np.copy(img_model.img_data)
    assert np.array_equal(flipped_img_background_subtracted, flipped_img - flipped_background)

    assert np.array_equal(np.flipud(original_img_background_subtracted), flipped_img_background_subtracted)
    assert np.sum(np.flipud(original_img_background_subtracted) - flipped_img_background_subtracted) == 0

    img_model.load(os.path.join(data_path, 'image_002.tif'))
    perform_transformations_tests(img_model)


def test_background_scaling_and_offset(img_model):
    img_model.load_background(os.path.join(data_path, 'image_002.tif'))

    # assure that everything is correct before
    assert np.array_equal(img_model.img_data, img_model._img_data - img_model._background_data)

    # set scaling and see difference
    img_model.background_scaling = 2.4
    assert np.array_equal(img_model.img_data, img_model._img_data - 2.4 * img_model._background_data)

    # set offset and see the difference
    img_model.background_scaling = 1.0
    img_model.background_offset = 100.0
    assert np.array_equal(img_model.img_data, img_model._img_data - (img_model._background_data + 100.0))

    # use offset and scaling combined
    img_model.background_scaling = 2.3
    img_model.background_offset = 100.0
    assert np.array_equal(img_model.img_data, img_model._img_data - (2.3 * img_model._background_data + 100))


def test_background_with_different_shape(img_model):
    with pytest.raises(BackgroundDimensionWrongException):
        img_model.load_background(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
    assert img_model._background_data is None

    img_model.load_background(os.path.join(data_path, 'image_002.tif'))
    assert img_model._background_data is not None

    img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
    assert img_model._background_data is None


def test_absorption_correction_with_different_image_sizes(img_model):
    dummy_correction = DummyCorrection(img_model.img_data.shape, 0.4)
    # self.img_data.set_absorption_correction(np.ones(self.img_data._img_data.shape)*0.4)
    img_model.add_img_correction(dummy_correction, "Dummy 1")
    assert img_model._img_corrections.has_items()

    img_model.load(os.path.join(data_path, 'CeO2_Pilatus1M.tif'))
    assert not img_model.has_corrections()


def test_adding_several_absorption_corrections(img_model):
    original_image = np.copy(img_model.img_data)
    img_shape = original_image.shape
    img_model.add_img_correction(DummyCorrection(img_shape, 0.4))
    img_model.add_img_correction(DummyCorrection(img_shape, 3))
    img_model.add_img_correction(DummyCorrection(img_shape, 5))

    assert np.sum(original_image) / (0.5 * 3 * 5) == np.sum(img_model.img_data)

    img_model.delete_img_correction(1)
    assert np.sum(original_image) / (0.5 * 5) == np.sum(img_model.img_data)


def test_saving_data(img_model, tmp_path):
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    filename = os.path.join(tmp_path, 'test.tif')
    img_model.save(filename)
    first_img_array = np.copy(img_model._img_data)
    img_model.load(filename)
    assert np.array_equal(first_img_array, img_model._img_data)
    assert os.path.exists(filename)


def test_negative_rotation(img_model):
    pre_transformed_data = img_model.img_data
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_combined_rotation(img_model):
    pre_transformed_data = img_model.img_data
    img_model.rotate_img_m90()
    img_model.rotate_img_p90()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_flip_img_horizontally(img_model):
    pre_transformed_data = img_model.img_data
    img_model.flip_img_horizontally()
    img_model.flip_img_horizontally()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_flip_img_vertically(img_model):
    pre_transformed_data = img_model.img_data
    img_model.flip_img_vertically()
    img_model.flip_img_vertically()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_combined_rotation_and_flipping(img_model):
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    img_model.flip_img_vertically()
    img_model.flip_img_horizontally()
    img_model.rotate_img_m90()
    img_model.rotate_img_p90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.flip_img_horizontally()
    transformed_data = img_model.img_data
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    assert np.array_equal(img_model.img_data, transformed_data)


def test_reset_img_transformation(img_model):
    pre_transformed_data = img_model.img_data
    img_model.rotate_img_m90()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.rotate_img_p90()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.flip_img_horizontally()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.flip_img_vertically()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.flip_img_vertically()
    img_model.flip_img_horizontally()
    img_model.rotate_img_m90()
    img_model.rotate_img_p90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.flip_img_horizontally()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_loading_a_tagged_tif_file_and_retrieving_info_string(img_model):
    img_model.load(os.path.join(data_path, "attrib.tif"))
    assert "areaDetector" in img_model.file_info


def test_loading_spe_file(img_model):
    img_model.load(os.path.join(spe_path, 'CeO2_PI_CCD_Mo.SPE'))
    assert img_model.img_data.shape == (1042, 1042)


def test_loading_ESRF_hdf5_file(img_model):
    img_model.load(os.path.join(data_path, 'hdf5_dataset', 'ma4500_demoh5.h5'))
    assert img_model.img_data.shape == (2048, 2048)

    img1 = img_model.img_data
    img_model.select_source(img_model.sources[2])
    img2 = img_model.img_data
    assert np.sum(img1 - img2) != 0


def test_summing_files(img_model):
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    data1 = np.copy(img_model._img_data).astype(np.uint64)
    img_model.add(os.path.join(data_path, 'image_001.tif'))
    assert np.array_equal(2 * data1, img_model._img_data)


def test_summing_rotated(img_model):
    img_model.load(os.path.join(data_path, 'image_001.tif'))
    img_model.rotate_img_m90()
    data1 = np.copy(img_model._img_data).astype(np.uint32)
    img_model.add(os.path.join(data_path, 'image_001.tif'))
    assert np.array_equal(2 * data1, img_model._img_data)
