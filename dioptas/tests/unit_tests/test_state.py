# SPDX-License-Identifier: MIT
import os

import h5py
import numpy as np
import pytest

from dioptas.model.state import (
    ConfigurationParams,
    load_params,
    params_from_dict,
    params_to_dict,
    save_params,
)


def test_defaults():
    params = ConfigurationParams()
    assert params.use_mask is False
    assert params.integration_unit == "2th_deg"
    assert params.integration_rad_points is None
    assert params.cake_azimuth_points == 360
    assert params.integrated_patterns_file_formats == [".xy"]
    assert params.working_directories["calibration"] == ""


def test_field_change_emits_event():
    params = ConfigurationParams()
    got = []
    params.events.use_mask.connect(lambda new, old: got.append((new, old)))

    params.use_mask = True
    assert got == [(True, False)]

    params.use_mask = True  # no change → no emission
    assert got == [(True, False)]


def test_group_signal_reports_any_field_change():
    params = ConfigurationParams()
    got = []
    params.events.connect(lambda info: got.append(info.signal.name))

    params.integration_unit = "q_A^-1"
    params.cake_azimuth_points = 720
    assert got == ["integration_unit", "cake_azimuth_points"]


def test_dict_round_trip():
    params = ConfigurationParams()
    params.use_mask = True
    params.integration_rad_points = 1500
    params.oned_azimuth_range = [-100.0, 100.0]
    params.integrated_patterns_file_formats = [".xy", ".chi"]

    restored = params_from_dict(ConfigurationParams, params_to_dict(params))
    assert restored == params


def test_from_dict_ignores_unknown_keys():
    restored = params_from_dict(
        ConfigurationParams, {"use_mask": True, "some_future_field": 42}
    )
    assert restored.use_mask is True


def test_from_dict_keeps_defaults_for_missing_keys():
    restored = params_from_dict(ConfigurationParams, {"use_mask": True})
    assert restored.integration_unit == "2th_deg"
    assert restored.cake_azimuth_points == 360


def test_hdf5_round_trip(tmp_path):
    params = ConfigurationParams()
    params.transparent_mask = True
    params.integration_rad_points = np.int64(2048)  # numpy scalars must serialize
    params.cake_azimuth_range = [-180.0, 180.0]
    params.trim_trailing_zeros = False

    filename = os.path.join(tmp_path, "state.h5")
    with h5py.File(filename, "w") as f:
        save_params(f, params)

    with h5py.File(filename, "r") as f:
        restored = load_params(f, ConfigurationParams)

    assert restored is not None
    assert restored.transparent_mask is True
    assert restored.integration_rad_points == 2048
    assert restored.cake_azimuth_range == [-180.0, 180.0]
    assert restored.trim_trailing_zeros is False


def test_load_params_returns_none_for_missing_group(tmp_path):
    filename = os.path.join(tmp_path, "empty.h5")
    with h5py.File(filename, "w") as f:
        pass

    with h5py.File(filename, "r") as f:
        assert load_params(f, ConfigurationParams) is None


def test_instances_do_not_share_mutable_defaults():
    a = ConfigurationParams()
    b = ConfigurationParams()
    a.working_directories["image"] = "/somewhere"
    a.integrated_patterns_file_formats.append(".chi")
    assert b.working_directories["image"] != "/somewhere"
    assert b.integrated_patterns_file_formats == [".xy"]
