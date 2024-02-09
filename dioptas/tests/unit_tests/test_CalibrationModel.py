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

import os
import sys
import pytest

import numpy as np
from mock import MagicMock

from pyFAI import detectors
from pyFAI.detectors import Detector

from ...model.CalibrationModel import (
    CalibrationModel,
    NoPointsError,
    get_available_detectors,
    DetectorModes,
)
from ...model.ImgModel import ImgModel
from ... import calibrants_path
import gc

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


def load_pilatus_1M(img_model):
    img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))


def load_small_image(img_model, shape=(10, 10)):
    img_model._img_data = np.ones(shape)


def load_pilatus_1M_with_calibration(calibration_model):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    load_pilatus_1M(calibration_model.img_model)


def load_small_image_with_calibration(calibration_model, shape=(10, 10)):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    load_small_image(calibration_model.img_model, shape)


def load_image_with_distortion(calibration_model):
    calibration_model.img_model.load(
        os.path.join(data_path, "distortion", "CeO2_calib.edf")
    )
    calibration_model.find_peaks_automatic(1025.1, 1226.8, 0)
    calibration_model.set_calibrant(os.path.join(calibrants_path, "CeO2.D"))
    calibration_model.start_values["dist"] = 300e-3
    calibration_model.detector.pixel1 = 50e-6
    calibration_model.detector.pixel2 = 50e-6
    calibration_model.start_values["wavelength"] = 0.1e-10
    calibration_model.calibrate()


def load_LaB6_40keV_with_calibration(calibration_model):
    calibration_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    calibration_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.poni"))


def test_integration_with_supersampling(calibration_model):
    load_small_image_with_calibration(calibration_model)
    x1, y1 = calibration_model.integrate_1d()

    calibration_model.set_supersampling(2)
    x2, y2 = calibration_model.integrate_1d()

    assert len(y2) > len(y1)
    y1_2_interp = np.interp(x2, x1, y1)

    assert np.mean((y2 - y1_2_interp)) == pytest.approx(0, abs=1e-2)


def test_get_pixel_ind(calibration_model):
    load_small_image_with_calibration(calibration_model, shape=(30, 30))
    calibration_model.integrate_1d(60)

    tth_array = calibration_model.pattern_geometry.ttha
    azi_array = calibration_model.pattern_geometry.chia

    for _ in range(10):
        ind1 = np.random.randint(1, 10)
        ind2 = np.random.randint(1, 10)
        # the 0, 0 case is not working with the get_pixel_ind function

        tth = tth_array[ind1, ind2]
        azi = azi_array[ind1, ind2]

        result_ind1, result_ind2 = calibration_model.get_pixel_ind(tth, azi)

        assert ind1 == pytest.approx(result_ind1, abs=1e-3)
        assert ind2 == pytest.approx(result_ind2, abs=1e-3)


def test_use_different_image_sizes_for_1d_integration(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 10))
    calibration_model.integrate_1d()
    load_small_image(img_model, shape=(12, 12))
    calibration_model.integrate_1d()


def test_use_different_image_sizes_for_2d_integration(calibration_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 10))
    calibration_model.integrate_2d()
    load_small_image_with_calibration(calibration_model, shape=(12, 12))
    calibration_model.integrate_2d()


def test_correct_solid_angle(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 10))
    _, y1 = calibration_model.integrate_1d()
    calibration_model.correct_solid_angle = False
    _, y2 = calibration_model.integrate_1d()
    assert np.sum(y1) != np.sum(y2)


def test_distortion_correction(calibration_model, img_model):
    load_image_with_distortion(calibration_model)

    _, y1 = calibration_model.integrate_1d()

    calibration_model.load_distortion(
        os.path.join(data_path, "distortion", "f4mnew.spline")
    )
    calibration_model.calibrate()

    _, y2 = calibration_model.integrate_1d()
    assert np.sum(y1) != np.sum(y2)
    assert y1[100] != pytest.approx(y2[100])


def test_cake_integral(calibration_model):
    load_pilatus_1M_with_calibration(calibration_model)
    calibration_model.integrate_2d(azimuth_points=360)

    cake_tth = calibration_model.cake_tth
    cake_img = calibration_model.cake_img
    cake_step = cake_tth[31] - cake_tth[30]

    # directly selecting value in the tth array
    _, y1 = calibration_model.cake_integral(cake_tth[30])
    assert np.array_equal(y1, calibration_model.cake_img[:, 30])

    # selecting exactly in between two points
    cake_partial = 0.5 * cake_img[:, 30] + 0.5 * cake_img[:, 31]
    _, y2 = calibration_model.cake_integral(cake_tth[30] + 0.5 * cake_step)
    assert np.array_equal(y2, cake_partial)

    # selecting points somewhere in between
    cake_partial = 0.3 * cake_img[:, 30] + 0.7 * cake_img[:, 31]
    _, y3 = calibration_model.cake_integral(cake_tth[30] + 0.7 * cake_step)
    assert np.array_equal(y3, cake_partial)

    # test with larger binsize of 2
    cake_partial = 0.5 * cake_img[:, 30] + 0.5 * cake_img[:, 31]
    _, y4 = calibration_model.cake_integral(cake_tth[30] + 0.5 * cake_step, bins=2)
    assert np.array_equal(y4, cake_partial)

    cake_partial = (0.5 * cake_img[:, 29] + cake_img[:, 30] + 0.5 * cake_img[:, 31]) / 2
    _, y5 = calibration_model.cake_integral(cake_tth[30], bins=2)
    assert np.array_equal(y5, cake_partial)


def test_integration_with_predefined_detector(calibration_model, img_model):
    calibration_model.load_detector("Pilatus CdTe 1M")
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert len(calibration_model.tth) > 0


def test_integration_with_rotated_predefined_detector(calibration_model, img_model):
    load_pilatus_1M_with_calibration(calibration_model)
    calibration_model.load_detector("Pilatus CdTe 1M")
    x1, y1 = calibration_model.integrate_1d()

    # rotate m90
    calibration_model.rotate_detector_m90()
    img_model.rotate_img_m90()
    calibration_model.integrate_1d()

    # rotate p90
    calibration_model.rotate_detector_p90()
    img_model.rotate_img_p90()
    x2, y2 = calibration_model.integrate_1d()

    assert len(x1) == len(x2)
    assert float(np.sum((y1 - y2) ** 2)) == pytest.approx(0)


def test_integration_with_rotation(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 12))
    calibration_model.integrate_1d()

    # rotate m90
    calibration_model.rotate_detector_m90()
    img_model.rotate_img_m90()
    calibration_model.integrate_1d()


def test_integration_with_rotation_and_reset(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 12))
    calibration_model.load_detector("Pilatus CdTe 1M")
    x1, y1 = calibration_model.integrate_1d()

    calibration_model.rotate_detector_m90()
    img_model.rotate_img_m90()
    calibration_model.rotate_detector_m90()
    img_model.rotate_img_m90()
    calibration_model.rotate_detector_p90()
    img_model.rotate_img_p90()

    calibration_model.reset_transformations()
    img_model.reset_transformations()

    x2, y2 = calibration_model.integrate_1d()

    assert len(x1) == len(x2)
    assert float(np.sum((y1 - y2) ** 2)) == pytest.approx(0)

    calibration_model.rotate_detector_p90()
    img_model.rotate_img_p90()
    calibration_model.integrate_1d()


def test_integration_with_transformation_and_change_detector_to_custom(
    calibration_model, img_model
):
    load_small_image_with_calibration(calibration_model, shape=(10, 12))
    calibration_model.load_detector("Pilatus CdTe 1M")
    _ = calibration_model.integrate_1d()

    calibration_model.rotate_detector_m90()
    img_model.rotate_img_m90()


def test_change_detector_after_loading_image_with_different_shapes_integrate_1d(
    calibration_model, img_model
):
    load_small_image(img_model, shape=(10, 12))
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    calibration_model.integrate_1d()

    callback_function = MagicMock()
    calibration_model.detector_reset.connect(callback_function)
    calibration_model.load_detector("Pilatus CdTe 1M")
    calibration_model.integrate_1d()
    callback_function.assert_called_once()


def test_change_detector_after_loading_image_with_different_shapes_integrate_2d(
    calibration_model, img_model
):
    img_model._img_data = np.ones((10, 13))
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    calibration_model.integrate_1d()

    callback_function = MagicMock()
    calibration_model.detector_reset.connect(callback_function)
    calibration_model.load_detector("Pilatus CdTe 1M")
    calibration_model.integrate_2d()
    callback_function.assert_called_once()


def test_loading_calibration_gives_right_pixel_size(calibration_model):
    calibration_model.pattern_geometry.load(
        os.path.join(data_path, "CeO2_Pilatus1M.poni")
    )
    assert calibration_model.pattern_geometry.pixel1 == 0.000172

    calibration_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.poni"))
    assert calibration_model.pattern_geometry.pixel1 == 0.000079


def test_find_peaks_automatic(calibration_model, img_model):
    load_pilatus_1M(img_model)
    find_pilatus_1M_peaks(calibration_model)
    assert len(calibration_model.points) == 6
    for points in calibration_model.points:
        assert len(points) > 0


def test_find_peak(calibration_model, img_model):
    """
    Tests the find_peak function for several maxima and pick points

    """
    points_and_pick_points = [
        [[30, 50], [31, 49]],
        [[30, 50], [34, 46]],
        [[5, 5], [3, 3]],
        [[298, 298], [299, 299]],
    ]

    for data in points_and_pick_points:
        img_model._img_data = np.zeros((300, 300))

        point = data[0]
        pick_point = data[1]
        img_model._img_data[point[0], point[1]] = 100

        peak_point = calibration_model.find_peak(pick_point[0], pick_point[1], 10, 0)
        assert peak_point[0][0] == point[0]
        assert peak_point[0][1] == point[1]


def find_pilatus_1M_peaks(calibration_model):
    points = [
        (517.664434674, 646, 0),
        (667.380513299, 525.252854758, 0),
        (671.110095329, 473.571503774, 0),
        (592.788872703, 350.495296791, 0),
        (387.395462348, 390.987901686, 0),
        (367.94835605, 554.290314848, 0),
    ]
    for point in points:
        calibration_model.find_peaks_automatic(point[0], point[1], 0)


def test_calibration_with_supersampling1(calibration_model, img_model):
    load_pilatus_1M(img_model)
    find_pilatus_1M_peaks(calibration_model)
    calibration_model.set_calibrant(os.path.join(calibrants_path, "CeO2.D"))
    calibration_model.detector.pixel1 = 172e-6
    calibration_model.detector.pixel2 = 172e-6

    calibration_model.calibrate()
    normal_poni1 = calibration_model.pattern_geometry.poni1
    normal_poni2 = calibration_model.pattern_geometry.poni2

    calibration_model.set_supersampling(2)

    calibration_model.calibrate()
    assert pytest.approx(normal_poni1) == calibration_model.pattern_geometry.poni1
    assert pytest.approx(normal_poni2) == calibration_model.pattern_geometry.poni2


def test_calibration_with_supersampling2(calibration_model, img_model):
    load_pilatus_1M(img_model)
    calibration_model.set_calibrant(os.path.join(calibrants_path, "CeO2.D"))
    calibration_model.detector.pixel1 = 172e-6
    calibration_model.detector.pixel2 = 172e-6

    calibration_model.set_supersampling(2)
    find_pilatus_1M_peaks(calibration_model)

    calibration_model.calibrate()
    super_poni1 = calibration_model.pattern_geometry.poni1
    super_poni2 = calibration_model.pattern_geometry.poni2

    calibration_model.set_supersampling(1)
    find_pilatus_1M_peaks(calibration_model)

    calibration_model.calibrate()
    assert (
        pytest.approx(super_poni1, abs=1e-3) == calibration_model.pattern_geometry.poni1
    )
    assert (
        pytest.approx(super_poni2, abs=1e-3) == calibration_model.pattern_geometry.poni2
    )


def test_calibration1(calibration_model, img_model):
    img_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.tif"))
    calibration_model.find_peaks_automatic(1179.6, 1129.4, 0)
    calibration_model.find_peaks_automatic(1268.5, 1119.8, 1)

    calibration_model.set_calibrant(os.path.join(calibrants_path, "LaB6.D"))
    calibration_model.calibrate()

    assert calibration_model.pattern_geometry.poni1 > 0
    assert calibration_model.pattern_geometry.dist == pytest.approx(0.18, abs=0.01)
    assert calibration_model.cake_geometry.poni1 > 0


def test_calibration2(calibration_model, img_model):
    img_model.load(os.path.join(data_path, "LaB6_OffCenter_PE.tif"))
    calibration_model.find_peaks_automatic(1245.2, 1919.3, 0)
    calibration_model.find_peaks_automatic(1334.0, 1823.7, 1)
    calibration_model.set_start_values(
        {"dist": 500e-3, "polarization_factor": 0.99, "wavelength": 0.3344e-10}
    )
    calibration_model.set_pixel_size((200e-6, 200e-6))
    calibration_model.set_calibrant(os.path.join(calibrants_path, "LaB6.D"))
    calibration_model.calibrate()

    assert calibration_model.pattern_geometry.poni1 > 0
    assert calibration_model.pattern_geometry.dist == pytest.approx(0.500, abs=0.01)
    assert calibration_model.cake_geometry.poni1 > 0


def test_calibration3(calibration_model, img_model):
    load_pilatus_1M(img_model)
    find_pilatus_1M_peaks(calibration_model)
    calibration_model.start_values["wavelength"] = 0.406626e-10
    calibration_model.set_start_values(
        {"dist": 200e-3, "polarization_factor": 0.99, "wavelength": 0.406626e-10}
    )
    calibration_model.set_pixel_size((172e-6, 172e-6))
    calibration_model.set_calibrant(os.path.join(calibrants_path, "CeO2.D"))
    calibration_model.calibrate()

    assert calibration_model.pattern_geometry.poni1 > 0
    assert calibration_model.pattern_geometry.dist == pytest.approx(0.208, abs=0.005)
    assert calibration_model.cake_geometry.poni1 > 0


def test_calibration_with_fixed_parameters(calibration_model, img_model):
    load_pilatus_1M(img_model)
    find_pilatus_1M_peaks(calibration_model)
    calibration_model.start_values["wavelength"] = 0.406626e-10
    calibration_model.detector.pixel1 = 172e-6
    calibration_model.detector.pixel2 = 172e-6
    calibration_model.set_calibrant(os.path.join(calibrants_path, "CeO2.D"))

    fixed_values_dicts = [
        {"rot1": 0.001},
        {"rot2": 0.03},
        {"rot1": 0.01, "rot2": 0.003},
        {"poni1": 0.32},
        {"poni1": 0.2, "poni2": 0.13},
        {"dist": 300},
        {"rot1": 0.001, "rot2": 0.004, "poni1": 0.22, "poni2": 0.34},
    ]
    for fixed_values in fixed_values_dicts:
        calibration_model.set_fixed_values(fixed_values)
        calibration_model.calibrate()
        for key, value in fixed_values.items():
            assert getattr(calibration_model.pattern_geometry, key) == value


def test_get_two_theta_img_with_distortion(calibration_model):
    load_image_with_distortion(calibration_model)

    x, y = np.array((100,)), np.array((100,))
    calibration_model.get_two_theta_img(x, y)
    calibration_model.load_distortion(
        os.path.join(data_path, "distortion", "f4mnew.spline")
    )
    calibration_model.get_two_theta_img(x, y)


def test_cake_integration_with_small_azimuth_range(calibration_model, img_model):
    img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))

    full_cake = calibration_model.integrate_2d()
    small_cake = calibration_model.integrate_2d(azimuth_range=(40, 130))
    assert not np.array_equal(full_cake, small_cake)


def test_cake_integration_with_off_azimuth_range(calibration_model, img_model):
    load_pilatus_1M_with_calibration(calibration_model)
    calibration_model.integrate_2d(azimuth_range=(150, -130))

    assert np.min(calibration_model.cake_azi) > 150
    assert np.max(calibration_model.cake_azi) < 230


def test_cake_integration_with_different_num_points(calibration_model, img_model):
    load_pilatus_1M_with_calibration(calibration_model)

    calibration_model.integrate_2d(rad_points=200)
    assert len(calibration_model.cake_tth) == 200

    calibration_model.integrate_2d(azimuth_points=200)
    assert len(calibration_model.cake_azi) == 200


def test_transforms_without_predefined_detector(calibration_model, img_model):
    img_model.load(os.path.join(data_path, "image_001.tif"))
    calibration_model.rotate_detector_p90()
    calibration_model.rotate_detector_m90()
    calibration_model.flip_detector_horizontally()
    calibration_model.img_model.flip_img_horizontally()
    calibration_model.flip_detector_horizontally()


def test_transforms_without_predefined_detector_changing_shape(
    calibration_model, img_model
):
    img_model.load(os.path.join(data_path, "image_001.tif"))
    calibration_model.rotate_detector_p90()
    img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    calibration_model.rotate_detector_m90()
    calibration_model.flip_detector_horizontally()
    calibration_model.img_model.flip_img_horizontally()
    calibration_model.flip_detector_horizontally()


def test_load_detector_list():
    names, classes = get_available_detectors()
    for name, cls in zip(names, classes):
        if name.startswith("Quantum"):
            assert "ADSC_" in str(cls)
        elif name.startswith("aca1300"):
            assert "Basler" in str(cls)
        else:
            assert name[:2].lower() in str(cls).lower()

    assert "Detector" not in names


def test_load_predefined_detector(calibration_model):
    calibration_model.load_detector("MAR 345")

    assert calibration_model.orig_pixel1 == 100e-6
    assert calibration_model.detector.pixel1 == 100e-6


def test_load_predefined_detector_and_poni_after(calibration_model):
    calibration_model.load_detector("Pilatus CdTe 1M")
    assert isinstance(calibration_model.detector, detectors.PilatusCdTe1M)
    assert isinstance(
        calibration_model.pattern_geometry.detector, detectors.PilatusCdTe1M
    )

    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    assert isinstance(calibration_model.detector, detectors.PilatusCdTe1M)
    assert isinstance(
        calibration_model.pattern_geometry.detector, detectors.PilatusCdTe1M
    )


def test_load_predefined_detector_and_poni_with_different_pixel_size(calibration_model):
    calibration_model.load_detector("Pilatus CdTe 1M")
    assert isinstance(calibration_model.detector, detectors.PilatusCdTe1M)
    assert isinstance(
        calibration_model.pattern_geometry.detector, detectors.PilatusCdTe1M
    )

    calibration_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.poni"))
    assert calibration_model.detector_mode == DetectorModes.CUSTOM
    assert isinstance(calibration_model.detector, detectors.Detector)
    assert isinstance(calibration_model.pattern_geometry.detector, detectors.Detector)


def test_load_detector_from_file(calibration_model):
    calibration_model.load_detector_from_file(os.path.join(data_path, "detector.h5"))
    assert calibration_model.orig_pixel1 == pytest.approx(100e-6)
    assert calibration_model.orig_pixel2 == pytest.approx(100e-6)
    assert calibration_model.detector.pixel1 == pytest.approx(100e-6)
    assert calibration_model.detector.pixel2 == pytest.approx(100e-6)
    assert calibration_model.detector.shape == (1048, 1032)


def test_load_detector_with_spline_file(calibration_model, tmp_path):
    # create detector and save it
    spline_detector = Detector()
    spline_detector.set_splineFile(
        os.path.join(data_path, "distortion", "f4mnew.spline")
    )
    spline_detector.save(os.path.join(tmp_path, "detector_with_spline.h5"))

    # load and check if it is working
    calibration_model.load_detector_from_file(
        os.path.join(tmp_path, "detector_with_spline.h5")
    )
    detector = calibration_model.detector
    assert detector.pixel1 == pytest.approx(50e-6)
    assert not detector.uniform_pixel


def test_calibrate_without_points(calibration_model):
    with pytest.raises(NoPointsError):
        calibration_model.calibrate()


def test_refine_without_points(calibration_model):
    with pytest.raises(NoPointsError):
        calibration_model.refine()
