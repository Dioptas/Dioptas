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
    assert params.calculate_poisson_errors is False
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
    params.calculate_poisson_errors = True
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


def test_hdf5_round_trip_with_numpy_bool(tmp_path):
    # legacy h5py attribute reads assign numpy scalars into params fields;
    # saving must not choke on them (autosave used to crash with
    # "Object of type bool is not JSON serializable")
    params = ConfigurationParams()
    params.use_mask = np.bool_(True)
    params.transparent_mask = np.bool_(False)

    filename = os.path.join(tmp_path, "state_bool.h5")
    with h5py.File(filename, "w") as f:
        save_params(f, params)

    with h5py.File(filename, "r") as f:
        restored = load_params(f, ConfigurationParams)

    assert restored is not None
    assert restored.use_mask is True
    assert restored.transparent_mask is False


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


# ---------------------------------------------------------------------------
# Derived
# ---------------------------------------------------------------------------

from dioptas.model.state import Derived
from dioptas.model.util.signal import Signal


def test_derived_recomputes_on_dependency_change():
    dep = Signal()
    runs = []
    derived = Derived(lambda: runs.append(1), dependencies=[dep])
    dep.emit()
    dep.emit()
    assert len(runs) == 2


def test_derived_inactive_discards_triggers():
    dep = Signal()
    runs = []
    derived = Derived(lambda: runs.append(1), dependencies=[dep], active=False)
    dep.emit()
    assert runs == []

    # enabling does not recompute retroactively
    derived.active = True
    assert runs == []
    dep.emit()
    assert len(runs) == 1


def test_derived_recompute_ignores_active():
    runs = []
    derived = Derived(lambda: runs.append(1), active=False)
    derived.recompute()
    assert len(runs) == 1


def test_derived_hold_coalesces():
    dep = Signal()
    runs = []
    derived = Derived(lambda: runs.append(1), dependencies=[dep])
    with derived.hold():
        dep.emit()
        dep.emit()
        dep.emit()
        assert runs == []
    assert len(runs) == 1


def test_derived_hold_without_trigger_does_not_compute():
    runs = []
    derived = Derived(lambda: runs.append(1))
    with derived.hold():
        pass
    assert runs == []


def test_derived_hold_flush_false_discards():
    dep = Signal()
    runs = []
    derived = Derived(lambda: runs.append(1), dependencies=[dep])
    with derived.hold(flush=False):
        dep.emit()
    assert runs == []
    # a later trigger still works
    dep.emit()
    assert len(runs) == 1


def test_derived_nested_holds_outermost_flush_wins():
    dep = Signal()
    runs = []
    derived = Derived(lambda: runs.append(1), dependencies=[dep])
    with derived.hold(flush=False):
        with derived.hold(flush=True):
            dep.emit()
        assert runs == []
    assert runs == []

    with derived.hold(flush=True):
        with derived.hold(flush=False):
            dep.emit()
    assert len(runs) == 1


def test_derived_add_dependency_later():
    dep = Signal()
    runs = []
    derived = Derived(lambda: runs.append(1))
    dep.emit()
    assert runs == []
    derived.add_dependency(dep)
    dep.emit()
    assert len(runs) == 1


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

from dioptas.model.state import SCHEMA_VERSION


def test_load_params_skips_newer_schema_version(tmp_path):
    """A params group written by a future encoding is skipped so callers
    fall back to the legacy attributes."""
    filename = os.path.join(tmp_path, "future.h5")
    with h5py.File(filename, "w") as f:
        save_params(f, ConfigurationParams())
        f["params"].attrs["schema_version"] = SCHEMA_VERSION + 1

    with h5py.File(filename, "r") as f:
        assert load_params(f, ConfigurationParams) is None


def test_load_params_accepts_current_and_missing_schema_version(tmp_path):
    filename = os.path.join(tmp_path, "current.h5")
    with h5py.File(filename, "w") as f:
        save_params(f, ConfigurationParams())
        assert int(f["params"].attrs["schema_version"]) == SCHEMA_VERSION

    with h5py.File(filename, "r") as f:
        assert load_params(f, ConfigurationParams) is not None


def test_load_params_tolerates_corrupt_group(tmp_path):
    """A corrupt params group must not abort loading — callers fall back to
    the legacy attributes."""
    filename = os.path.join(tmp_path, "corrupt.h5")
    with h5py.File(filename, "w") as f:
        save_params(f, ConfigurationParams())
        f["params"].attrs["data"] = "{not valid json"

    with h5py.File(filename, "r") as f:
        assert load_params(f, ConfigurationParams) is None

    with h5py.File(filename, "r+") as f:
        del f["params"].attrs["data"]  # missing data attribute

    with h5py.File(filename, "r") as f:
        assert load_params(f, ConfigurationParams) is None

    with h5py.File(filename, "r+") as f:
        f["params"].attrs["data"] = "{}"
        f["params"].attrs["schema_version"] = "garbage"  # non-numeric version

    with h5py.File(filename, "r") as f:
        assert load_params(f, ConfigurationParams) is None


# ---------------------------------------------------------------------------
# ImgParams
# ---------------------------------------------------------------------------

from dioptas.model.state import ImgParams


def test_img_params_defaults_and_events():
    params = ImgParams()
    assert params.factor == 1.0
    assert params.file_iteration_mode == "number"

    got = []
    params.events.factor.connect(lambda new, old: got.append((new, old)))
    params.factor = 2.0
    assert got == [(2.0, 1.0)]


# ---------------------------------------------------------------------------
# PatternParams
# ---------------------------------------------------------------------------

from dioptas.model.state import PatternParams


def test_pattern_params_defaults_and_events():
    params = PatternParams()
    assert params.unit == ""
    assert params.file_iteration_mode == "number"

    got = []
    params.events.unit.connect(lambda new, old: got.append((new, old)))
    params.unit = "q_A^-1"
    assert got == [("q_A^-1", "")]


# ---------------------------------------------------------------------------
# MaskParams
# ---------------------------------------------------------------------------

from dioptas.model.state import MaskParams


def test_mask_params_defaults_and_events():
    params = MaskParams()
    assert params.mode is True
    assert params.roi is None

    got = []
    params.events.mode.connect(lambda new, old: got.append((new, old)))
    params.mode = False
    assert got == [(False, True)]


# ---------------------------------------------------------------------------
# CalibrationParams
# ---------------------------------------------------------------------------

from dioptas.model.state import CalibrationParams


def test_calibration_params_defaults_and_events():
    params = CalibrationParams()
    assert params.polarization_factor == 0.99
    assert params.correct_solid_angle is True
    assert params.start_values["dist"] == 200e-3
    assert params.fixed_values == {}

    got = []
    params.events.polarization_factor.connect(lambda new, old: got.append(new))
    params.polarization_factor = 0.5
    assert got == [0.5]


def test_calibration_params_instances_do_not_share_dicts():
    a = CalibrationParams()
    b = CalibrationParams()
    a.start_values["dist"] = 1.0
    a.fixed_values["rot1"] = 0.5
    assert b.start_values["dist"] == 200e-3
    assert b.fixed_values == {}


# ---------------------------------------------------------------------------
# MapParams / PhaseParams
# ---------------------------------------------------------------------------

from dioptas.model.state import MapParams, PhaseParams


def test_map_params_defaults():
    params = MapParams()
    assert params.rois == []
    assert params.expressions == {}
    assert params.active_layer == "A"
    assert params.dimension is None
    assert params.slots is None
    assert params.snake is False
    assert params.excluded_points == []


def test_phase_params_defaults_and_events():
    params = PhaseParams()
    assert params.same_conditions is True

    got = []
    params.events.same_conditions.connect(lambda new, old: got.append(new))
    params.same_conditions = False
    assert got == [False]


# ---------------------------------------------------------------------------
# Per-item params
# ---------------------------------------------------------------------------

from dioptas.model.state import OverlayItemParams, PhaseItemParams


def test_overlay_item_params_events():
    params = OverlayItemParams(name="test", color="#ff0000")
    got = []
    params.events.scaling.connect(lambda new, old: got.append(new))
    params.scaling = 2.0
    assert got == [2.0]


def test_phase_item_params_events():
    params = PhaseItemParams()
    assert params.visible is True
    got = []
    params.events.visible.connect(lambda new, old: got.append(new))
    params.visible = False
    assert got == [False]


def test_tuple_fields_survive_the_json_round_trip():
    """JSON has no tuple type; declared tuple fields must not become lists."""
    params = MaskParams(roi=(10, 20, 30, 40))
    restored = params_from_dict(MaskParams, params_to_dict(params))
    assert restored.roi == (10, 20, 30, 40)
    assert isinstance(restored.roi, tuple)

    item = PhaseItemParams(color=(1, 2, 3))
    restored_item = params_from_dict(PhaseItemParams, params_to_dict(item))
    assert isinstance(restored_item.color, tuple)


def test_list_of_params_dataclasses_round_trips():
    """MapParams holds a list of MapRoiParams; the generic dict round trip
    has to rebuild the items as dataclasses, not leave them as dicts."""
    from dioptas.model.state import MapParams, MapRoiParams
    from dioptas.model.state.hdf5 import params_from_dict, params_to_dict

    params = MapParams(
        rois=[
            MapRoiParams(name="A", x_min=1.0, x_max=2.0, reduction="area"),
            MapRoiParams(name="B", x_min=3.0, x_max=4.0),
        ],
        expressions={"r": "A/B"},
    )

    restored = params_from_dict(MapParams, params_to_dict(params))

    assert [type(roi) for roi in restored.rois] == [MapRoiParams, MapRoiParams]
    assert restored.rois[0].reduction == "area"
    assert restored.rois[1].name == "B"
    assert restored.expressions == {"r": "A/B"}
