# SPDX-License-Identifier: MIT

import os
from types import SimpleNamespace
import sys
import logging
import pytest

import numpy as np
from mock import MagicMock

from pyFAI import detectors
from pyFAI.detectors import Detector
from pyFAI.detectors.orientation import Orientation

from ...model.CalibrationModel import (
    NoPointsError,
    get_available_detectors,
    DetectorModes,
)
from ... import calibrants_path

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


def test_load_poni_file_without_orientation(calibration_model, tmp_path):
    calibration_model.load(os.path.join(data_path, "LaB6_40keV_MarCCD.poni"))

    poni_config = calibration_model.pattern_geometry.get_config()
    orientation = poni_config["detector_config"].pop("orientation")

    assert orientation == Orientation.BottomRight

    # Save to temporary path instead of data_path
    temp_poni_file = os.path.join(tmp_path, "LaB6_40keV_MarCCD_new_with_orientation.poni")
    calibration_model.save(temp_poni_file)


    # Check that the orientation is still BottomRight
    calibration_model.load(temp_poni_file)

    poni_config = calibration_model.pattern_geometry.get_config()
    orientation = poni_config["detector_config"].pop("orientation")

    assert orientation == Orientation.BottomRight

    # Check that the orientation is TopRight in the poni file
    from pyFAI.io.ponifile import PoniFile
    poni_file = PoniFile(temp_poni_file)
    poni_dict = poni_file.as_dict()
    orientation = poni_dict["detector_config"]["orientation"]

    assert orientation == Orientation.TopRight


def test_load_poni_file_with_orientation(calibration_model):
    poni_file = os.path.join(data_path, "LaB6_40keV_MarCCD_new_with_orientation.poni")
    calibration_model.load(poni_file)

    poni_config = calibration_model.pattern_geometry.get_config()
    orientation = poni_config["detector_config"].pop("orientation")

    assert orientation == Orientation.BottomRight


def test_integration_with_supersampling(calibration_model):
    load_small_image_with_calibration(calibration_model)
    x1, y1 = calibration_model.integrate_1d()

    calibration_model.set_supersampling(2)
    x2, y2 = calibration_model.integrate_1d()

    assert len(y2) >= len(y1)
    y1_2_interp = np.interp(x2, x1, y1)

    assert np.mean((y2 - y1_2_interp)) == pytest.approx(0, abs=1e-2)


def test_poisson_errors_are_only_calculated_when_requested(calibration_model):
    load_small_image_with_calibration(calibration_model)

    calibration_model.integrate_1d()
    assert calibration_model.sigma is None

    x, _ = calibration_model.integrate_1d(calculate_errors=True)
    assert calibration_model.sigma is not None
    assert len(calibration_model.sigma) == len(x)
    assert np.all(np.isfinite(calibration_model.sigma))
    assert np.all(calibration_model.sigma >= 0)


def test_dioptrin_poisson_errors_are_requested_and_stored(calibration_model):
    load_small_image_with_calibration(calibration_model)

    class FakeDioptrinIntegrator:
        def set_method(self, *args, **kwargs):
            pass

        def set_unit(self, *args, **kwargs):
            pass

        def set_mask(self, *args, **kwargs):
            pass

        def set_polarization_factor(self, *args, **kwargs):
            pass

        def integrate1d(self, _image, num_points, **kwargs):
            assert kwargs == {"errors": True}
            return SimpleNamespace(
                radial=np.arange(num_points, dtype=float),
                intensity=np.ones(num_points),
                errors=np.full(num_points, 0.25),
            )

    calibration_model._check_detector_and_image_shape()
    calibration_model.use_dioptrin = True
    calibration_model._dioptrin_integrator = FakeDioptrinIntegrator()
    x, _ = calibration_model.integrate_1d(num_points=10, calculate_errors=True)

    np.testing.assert_allclose(x, np.arange(10))
    np.testing.assert_allclose(calibration_model.sigma, 0.25)


def test_get_pixel_ind(calibration_model):
    load_small_image_with_calibration(calibration_model, shape=(30, 30))
    calibration_model.integrate_1d(60)

    tth_array = calibration_model.tth_array
    azi_array = calibration_model.azi_array

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
    assert np.allclose(y2, cake_partial, rtol=1e-6, atol=1e-6)

    # selecting points somewhere in between
    cake_partial = 0.3 * cake_img[:, 30] + 0.7 * cake_img[:, 31]
    _, y3 = calibration_model.cake_integral(cake_tth[30] + 0.7 * cake_step)
    assert np.allclose(y3, cake_partial, rtol=1e-6, atol=1e-6)

    # test with larger binsize of 2
    cake_partial = 0.5 * cake_img[:, 30] + 0.5 * cake_img[:, 31]
    _, y4 = calibration_model.cake_integral(cake_tth[30] + 0.5 * cake_step, bins=2)
    assert np.allclose(y4, cake_partial, rtol=1e-6, atol=1e-6)

    cake_partial = (0.5 * cake_img[:, 29] + cake_img[:, 30] + 0.5 * cake_img[:, 31]) / 2
    _, y5 = calibration_model.cake_integral(cake_tth[30], bins=2)
    assert np.allclose(y5, cake_partial, rtol=1e-6, atol=1e-6)


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
    spline_detector.splinefile = os.path.join(
        data_path, "distortion", "f4mnew.spline"
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


def test_dioptrin_integrator_recreated_on_image_shape_change(calibration_model, img_model):
    """Switching to an image with a different shape must recreate the dioptrin integrator."""
    load_pilatus_1M_with_calibration(calibration_model)

    calibration_model.use_dioptrin = True
    calibration_model._dioptrin_integrator = MagicMock()
    calibration_model._create_dioptrin_integrator = MagicMock()

    # Loading an image with a different shape should trigger recreation
    img_model.load(os.path.join(data_path, "image_001.tif"))
    calibration_model._create_dioptrin_integrator.assert_called_once()

    # Loading an image with the same shape should NOT trigger recreation
    calibration_model._create_dioptrin_integrator.reset_mock()
    img_model._img_data = np.ones(img_model.img_data.shape)
    img_model.img_changed.emit()
    calibration_model._create_dioptrin_integrator.assert_not_called()


def test_clear_peaks(calibration_model, img_model):
    load_pilatus_1M(img_model)
    calibration_model.find_peaks_automatic(517.664434674, 646, 0)
    calibration_model.find_peaks_automatic(667.380513299, 525.252854758, 1)
    assert len(calibration_model.points) == 2
    assert len(calibration_model.points_index) == 2

    calibration_model.clear_peaks()
    assert calibration_model.points == []
    assert calibration_model.points_index == []


def test_remove_peaks_by_ring(calibration_model, img_model):
    load_pilatus_1M(img_model)
    calibration_model.find_peaks_automatic(517.664434674, 646, 0)
    calibration_model.find_peaks_automatic(667.380513299, 525.252854758, 1)
    calibration_model.find_peaks_automatic(671.110095329, 473.571503774, 0)
    assert len(calibration_model.points) == 3
    assert calibration_model.points_index == [0, 1, 0]

    calibration_model.remove_peaks_by_ring(0)
    assert len(calibration_model.points) == 1
    assert calibration_model.points_index == [1]


def test_remove_peaks_by_ring_all(calibration_model, img_model):
    """Removing all peaks by ring leaves empty lists."""
    load_pilatus_1M(img_model)
    calibration_model.find_peaks_automatic(517.664434674, 646, 0)
    calibration_model.find_peaks_automatic(671.110095329, 473.571503774, 0)

    calibration_model.remove_peaks_by_ring(0)
    assert calibration_model.points == []
    assert calibration_model.points_index == []


def test_remove_last_peak(calibration_model, img_model):
    load_pilatus_1M(img_model)
    calibration_model.find_peaks_automatic(517.664434674, 646, 0)
    calibration_model.find_peaks_automatic(667.380513299, 525.252854758, 1)
    assert len(calibration_model.points) == 2

    num_removed = calibration_model.remove_last_peak()
    assert num_removed is not None
    assert num_removed > 0
    assert len(calibration_model.points) == 1
    assert calibration_model.points_index == [0]


def test_remove_last_peak_empty(calibration_model):
    """Removing last peak when no peaks exist returns None."""
    result = calibration_model.remove_last_peak()
    assert result is None


def test_remove_peak_selection(calibration_model):
    calibration_model.params.peak_selections = (
        (0, ((1.0, 2.0),)),
        (1, ((3.0, 4.0),)),
        (2, ((5.0, 6.0),)),
    )
    calibration_model.remove_peak_selection(1)
    assert calibration_model.points_index == [0, 2]

    # out-of-range indices are ignored
    calibration_model.remove_peak_selection(5)
    calibration_model.remove_peak_selection(-1)
    assert calibration_model.points_index == [0, 2]


def test_set_peak_selection_ring(calibration_model):
    calibration_model.params.peak_selections = (
        (0, ((1.0, 2.0),)),
        (1, ((3.0, 4.0),)),
    )
    calibration_model.set_peak_selection_ring(0, 4)
    assert calibration_model.points_index == [4, 1]
    assert np.array_equal(calibration_model.points[0], np.array([[1.0, 2.0]]))

    calibration_model.set_peak_selection_ring(7, 2)  # out of range: ignored
    assert calibration_model.points_index == [4, 1]


def test_set_pixel_size(calibration_model):
    calibration_model.set_pixel_size((200e-6, 300e-6))
    assert calibration_model.orig_pixel1 == 200e-6
    assert calibration_model.orig_pixel2 == 300e-6
    assert calibration_model.detector.pixel1 == 200e-6
    assert calibration_model.detector.pixel2 == 300e-6


def test_set_fixed_values(calibration_model):
    fixed = {"rot1": 0.001, "poni1": 0.32}
    calibration_model.set_fixed_values(fixed)
    assert calibration_model.fixed_values == fixed
    assert calibration_model.fixed_values["rot1"] == 0.001
    assert calibration_model.fixed_values["poni1"] == 0.32


def test_create_cake_geometry(calibration_model):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    assert calibration_model.cake_geometry is not None

    # Verify cake_geometry has matching config
    cake_dist = calibration_model.cake_geometry.dist
    pattern_dist = calibration_model.pattern_geometry.dist
    assert cake_dist == pytest.approx(pattern_dist)


def test_load_distortion_sets_attribute(calibration_model):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    spline_path = os.path.join(data_path, "distortion", "f4mnew.spline")
    calibration_model.load_distortion(spline_path)

    assert calibration_model.distortion_spline_filename == spline_path
    # pyFAI normalizes the path, so compare with os.path.normpath
    assert os.path.normpath(calibration_model.pattern_geometry.splinefile) == os.path.normpath(spline_path)
    assert os.path.normpath(calibration_model.cake_geometry.splinefile) == os.path.normpath(spline_path)


def test_reset_distortion_correction(calibration_model):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    spline_path = os.path.join(data_path, "distortion", "f4mnew.spline")
    calibration_model.load_distortion(spline_path)

    calibration_model.reset_distortion_correction()
    assert calibration_model.distortion_spline_filename is None
    assert calibration_model.pattern_geometry.splinefile is None
    assert calibration_model.cake_geometry.splinefile is None


def test_save_and_reload(calibration_model, tmp_path):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    original_dist = calibration_model.pattern_geometry.dist
    original_poni1 = calibration_model.pattern_geometry.poni1

    save_path = os.path.join(tmp_path, "test_save.poni")
    calibration_model.save(save_path)
    assert os.path.exists(save_path)
    assert calibration_model.calibration_name == "test_save"
    assert calibration_model.filename == save_path

    # Reload and verify parameters match
    calibration_model.load(save_path)
    assert calibration_model.pattern_geometry.dist == pytest.approx(original_dist)
    assert calibration_model.pattern_geometry.poni1 == pytest.approx(original_poni1)


def test_get_calibration_parameter(calibration_model):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    pyFAI_params, fit2d_params = calibration_model.get_calibration_parameter()

    expected_keys = [
        "pixel1", "pixel2", "dist", "poni1", "poni2",
        "rot1", "rot2", "rot3", "wavelength", "polarization_factor",
    ]
    for key in expected_keys:
        assert key in pyFAI_params, f"Missing key: {key}"

    assert pyFAI_params["dist"] > 0
    assert pyFAI_params["wavelength"] > 0

    assert fit2d_params is not None
    assert "wavelength" in fit2d_params
    assert "polarization_factor" in fit2d_params


def test_set_pyfai_uses_current_config_api(calibration_model, caplog):
    parameters = {
        "dist": 0.2,
        "poni1": 0.08,
        "poni2": 0.081,
        "rot1": 0.0043,
        "rot2": 0.002,
        "rot3": 0.001,
        "pixel1": 7.4e-5,
        "pixel2": 7.6e-5,
        "wavelength": 0.31e-10,
        "polarization_factor": 0.99,
    }
    detector = calibration_model.detector
    caplog.set_level(logging.WARNING, logger="pyFAI.DEPRECATION")

    calibration_model.set_pyFAI(parameters)

    assert calibration_model.pattern_geometry.detector is detector
    assert calibration_model.pattern_geometry.dist == pytest.approx(0.2)
    assert calibration_model.pattern_geometry.poni1 == pytest.approx(0.08)
    assert detector.pixel1 == pytest.approx(7.4e-5)
    assert detector.pixel2 == pytest.approx(7.6e-5)
    assert not any(
        "setPyFAI" in record.message or "splineFile" in record.message
        for record in caplog.records
    )


def test_set_supersampling_changes_pixel_size(calibration_model):
    calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    orig_pixel1 = calibration_model.orig_pixel1
    orig_pixel2 = calibration_model.orig_pixel2

    calibration_model.set_supersampling(2)
    assert calibration_model.supersampling_factor == 2
    assert calibration_model.detector.pixel1 == pytest.approx(orig_pixel1 / 2.0)
    assert calibration_model.detector.pixel2 == pytest.approx(orig_pixel2 / 2.0)

    # Original pixel sizes should be unchanged
    assert calibration_model.orig_pixel1 == pytest.approx(orig_pixel1)
    assert calibration_model.orig_pixel2 == pytest.approx(orig_pixel2)

    # Reset back to 1
    calibration_model.set_supersampling(1)
    assert calibration_model.detector.pixel1 == pytest.approx(orig_pixel1)
    assert calibration_model.detector.pixel2 == pytest.approx(orig_pixel2)


def test_tth_array_and_azi_array_shape(calibration_model):
    load_small_image_with_calibration(calibration_model, shape=(15, 20))
    tth = calibration_model.tth_array
    azi = calibration_model.azi_array

    assert tth.shape == (15, 20)
    assert azi.shape == (15, 20)


def test_integrate_1d_d_spacing(calibration_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 10))
    x_tth, _ = calibration_model.integrate_1d(unit="2th_deg")
    x_d, _ = calibration_model.integrate_1d(unit="d_A")

    # d-spacing values should be positive and different from 2theta
    assert np.all(x_d > 0)
    # d-spacing is typically larger values (Angstrom) in a different range than 2theta (degrees)
    assert not np.allclose(x_tth, x_d)


def test_load_transformations_string_list(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 12))
    original_pixel1 = calibration_model.detector.pixel1
    original_pixel2 = calibration_model.detector.pixel2
    original_shape = calibration_model.detector.shape

    calibration_model.load_transformations_string_list(["rotate_matrix_m90"])
    # After m90 rotation, shape should be swapped
    if original_shape is not None:
        new_shape = calibration_model.detector.shape
        assert new_shape == (original_shape[1], original_shape[0])

    # Reset and try multiple transformations
    calibration_model.reset_transformations()
    calibration_model.load_transformations_string_list(["flipud", "fliplr"])
    # Flips should not change shape or pixel size
    assert calibration_model.detector.pixel1 == pytest.approx(original_pixel1)
    assert calibration_model.detector.pixel2 == pytest.approx(original_pixel2)


def test_swap_detector_shape(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 12))
    original_pixel1 = calibration_model.detector.pixel1
    original_pixel2 = calibration_model.detector.pixel2

    calibration_model.swap_detector_shape()
    # Pixel sizes should be swapped
    assert calibration_model.detector.pixel1 == pytest.approx(original_pixel2)
    assert calibration_model.detector.pixel2 == pytest.approx(original_pixel1)


def test_rotate_detector_m90_and_p90(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 12))
    orig_shape = calibration_model.detector.shape

    calibration_model.rotate_detector_m90()
    if orig_shape is not None:
        assert calibration_model.detector.shape == (orig_shape[1], orig_shape[0])

    # Rotating p90 should swap back
    calibration_model.rotate_detector_p90()
    if orig_shape is not None:
        assert calibration_model.detector.shape == orig_shape


def test_flip_detector_horizontally_and_vertically(calibration_model, img_model):
    load_small_image_with_calibration(calibration_model, shape=(10, 10))
    original_pixel1 = calibration_model.detector.pixel1

    calibration_model.flip_detector_horizontally()
    # Flip should not change pixel sizes
    assert calibration_model.detector.pixel1 == pytest.approx(original_pixel1)

    calibration_model.flip_detector_vertically()
    assert calibration_model.detector.pixel1 == pytest.approx(original_pixel1)
