# SPDX-License-Identifier: MIT

"""Undo/redo through DioptasModel.history.

The mask used to carry its own undo deques; those behaviours are asserted here
against the single global stack that replaced them.
"""

import os

import numpy as np
import pytest

from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.util.MaskPlugin import MaskPluginBase

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")


@pytest.fixture
def model():
    m = DioptasModel()
    # Small image so snapshots stay cheap. It has to go in through the image:
    # the mask dimension follows the image, so forcing the mask size alone
    # would be silently undone the next time the image is recalculated.
    m.img_model._img_data = np.zeros((50, 50))
    m.img_model.img_changed.emit()
    m.history.reset()
    return m


class _Counter:
    """Counts signal emissions (holding a strong ref against the weak-ref bus)."""

    def __init__(self):
        self.count = 0

    def __call__(self, *args):
        self.count += 1


# ---------------------------------------------------------------------------
# mask editing
# ---------------------------------------------------------------------------


def test_undo_restores_previous_mask(model):
    assert model.mask_model.get_img().sum() == 0
    model.mask_model.mask_ellipse(25, 25, 3, 3)
    assert model.mask_model.get_img().sum() > 0

    model.history.undo()
    assert model.mask_model.get_img().sum() == 0


def test_redo_restores_undone_mask(model):
    model.mask_model.mask_ellipse(25, 25, 3, 3)
    masked = model.mask_model.get_img().sum()

    model.history.undo()
    assert model.mask_model.get_img().sum() == 0
    model.history.redo()
    assert model.mask_model.get_img().sum() == masked


def test_undo_with_empty_history_does_nothing(model):
    original = model.mask_model.get_img().copy()
    assert model.history.undo() is False
    assert np.array_equal(model.mask_model.get_img(), original)


def test_redo_at_the_top_does_nothing(model):
    model.mask_model.mask_rect(10, 10, 5, 5)
    original = model.mask_model.get_img().copy()
    assert model.history.redo() is False
    assert np.array_equal(model.mask_model.get_img(), original)


def test_undo_emits_mask_changed(model):
    model.mask_model.mask_ellipse(25, 25, 3, 3)
    counter = _Counter()
    model.mask_model.mask_changed.connect(counter)

    model.history.undo()
    assert counter.count == 1


def test_restore_is_exact_when_drawing_over_an_existing_mask(model):
    """The reason snapshots beat a diff: overlapping draws must round-trip."""
    model.mask_model.mask_rect(10, 10, 20, 20)
    after_first = model.mask_model.get_img().copy()
    model.mask_model.mask_rect(20, 20, 20, 20)  # deliberately overlapping
    after_second = model.mask_model.get_img().copy()

    model.history.undo()
    assert np.array_equal(model.mask_model.get_img(), after_first)
    assert model.mask_model.get_img().dtype == bool

    model.history.redo()
    assert np.array_equal(model.mask_model.get_img(), after_second)


def test_stored_masks_are_compressed(model):
    """A step must not cost a byte per pixel (it used to cost 8x this)."""
    model.img_model._img_data = np.zeros((512, 512))
    model.img_model.img_changed.emit()
    model.history.reset()
    model.mask_model.mask_rect(100, 100, 50, 50)

    payload_id = model.history._steps[-1].state.configurations[0].mask_data
    payload = model.payloads.get(payload_id)
    raw = model.mask_model.get_img().nbytes
    assert payload.shape == (512, 512)
    assert payload.nbytes_stored < raw / 8


def test_masks_are_shared_between_snapshots_that_did_not_touch_them(model):
    """Settings-only steps must not each pay for a copy of the mask."""
    model.mask_model.mask_rect(10, 10, 5, 5)
    model.current_configuration.integration_unit = "q_A^-1"
    model.current_configuration.integration_rad_points = 999

    ids = [s.state.configurations[0].mask_data for s in model.history._steps[-3:]]
    assert ids[0] == ids[1] == ids[2]
    # and the store holds the bytes once, however many snapshots reference them
    assert sum(1 for i in model.payloads._payloads if i == ids[0]) == 1


# ---------------------------------------------------------------------------
# plugin imprints — one step covering mask data and plugin enabled state
# ---------------------------------------------------------------------------


class _RowsPlugin(MaskPluginBase):
    """Masks a fixed band of rows, so its contribution is easy to count."""

    is_dynamic = True

    def __init__(self, name, first, last):
        super().__init__()
        self.name = name
        self._first, self._last = first, last

    def compute_mask(self, img_data, existing_mask=None, **kwargs):
        mask = np.zeros(img_data.shape, dtype=bool)
        mask[self._first : self._last, :] = True
        return mask


def _register(model, plugin):
    manager = model.mask_plugin_manager
    manager.register(plugin)
    manager.update_image(np.zeros((50, 50)))
    manager.set_enabled(plugin.name, True)
    return manager


def test_imprint_undo_restores_mask_and_re_enables_plugin(model):
    manager = _register(model, _RowsPlugin("Rows", 0, 1))
    model.history.reset()

    model.mask_model.imprint_plugin_mask("Rows")
    assert manager.is_enabled("Rows") is False
    assert model.mask_model.get_img().sum() == 50

    model.history.undo()
    assert manager.is_enabled("Rows") is True
    assert model.mask_model.get_img().sum() == 0

    model.history.redo()
    assert manager.is_enabled("Rows") is False
    assert model.mask_model.get_img().sum() == 50


def test_multiple_imprints_undo_in_reverse_order(model):
    manager = _register(model, _RowsPlugin("A", 0, 5))
    _register(model, _RowsPlugin("B", 45, 50))
    model.history.reset()

    model.mask_model.imprint_plugin_mask("A")
    assert model.mask_model.get_img().sum() == 250
    model.mask_model.imprint_plugin_mask("B")
    assert model.mask_model.get_img().sum() == 500

    model.history.undo()
    assert model.mask_model.get_img().sum() == 250
    assert manager.is_enabled("A") is False
    assert manager.is_enabled("B") is True

    model.history.undo()
    assert model.mask_model.get_img().sum() == 0
    assert manager.is_enabled("A") is True
    assert manager.is_enabled("B") is True


def test_undoing_a_plain_draw_does_not_re_enable_a_plugin(model):
    """Only the step that disabled the plugin may re-enable it."""
    manager = _register(model, _RowsPlugin("Rows", 0, 1))
    model.history.reset()

    model.mask_model.imprint_plugin_mask("Rows")
    model.mask_model.mask_rect(10, 10, 5, 5)

    model.history.undo()  # undoes the draw only
    assert manager.is_enabled("Rows") is False
    model.history.undo()  # undoes the imprint
    assert manager.is_enabled("Rows") is True


def test_toggling_a_plugin_is_undoable(model):
    manager = _register(model, _RowsPlugin("Rows", 0, 1))
    model.history.reset()

    manager.set_enabled("Rows", False)
    assert manager.is_enabled("Rows") is False

    model.history.undo()
    assert manager.is_enabled("Rows") is True


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------


def test_settings_change_is_undoable(model):
    model.current_configuration.integration_unit = "q_A^-1"
    assert model.history.undo_label == "integration unit"

    model.history.undo()
    assert model.current_configuration.integration_unit == "2th_deg"
    model.history.redo()
    assert model.current_configuration.integration_unit == "q_A^-1"


def test_sub_model_settings_are_undoable(model):
    model.img_model.factor = 3.0
    model.pattern_model.params.unit = "d_A"
    model.mask_model.mode = False

    model.history.undo()
    assert model.mask_model.mode is True
    model.history.undo()
    assert model.pattern_model.params.unit != "d_A"
    model.history.undo()
    assert model.img_model.factor == 1


def test_mask_and_settings_share_one_stack(model):
    """The point of the exercise: one Ctrl+Z, whatever the last action was."""
    model.mask_model.mask_rect(10, 10, 5, 5)
    model.current_configuration.integration_rad_points = 1234
    masked = model.mask_model.get_img().sum()

    model.history.undo()
    assert model.current_configuration.integration_rad_points is None
    assert model.mask_model.get_img().sum() == masked  # mask untouched

    model.history.undo()
    assert model.mask_model.get_img().sum() == 0


def test_rapid_changes_to_one_field_collapse_into_one_step(model):
    """Dragging a spinbox must not fill the history with forty steps."""
    model.current_configuration.integration_rad_points = 100
    depth_after_first = model.history.depth
    for points in range(101, 140):
        model.current_configuration.integration_rad_points = points

    assert model.history.depth == depth_after_first
    model.history.undo()
    assert model.current_configuration.integration_rad_points is None


def test_writing_the_same_value_does_not_consume_a_step(model):
    model.current_configuration.integration_unit = "q_A^-1"
    depth = model.history.depth
    model.current_configuration.integration_unit = "q_A^-1"
    assert model.history.depth == depth


# ---------------------------------------------------------------------------
# what is deliberately outside the history
# ---------------------------------------------------------------------------


def test_view_state_is_not_undoable(model):
    """Undo is for the work, not the window furniture."""
    model.view.img_mode = "Cake"
    model.view.img_docked = False
    assert model.history.can_undo is False


def test_working_directories_are_not_restored(model):
    model.current_configuration.integration_unit = "q_A^-1"
    model.working_directories = dict(model.working_directories, image="/somewhere")

    model.history.undo()
    assert model.working_directories["image"] == "/somewhere"


# ---------------------------------------------------------------------------
# things that invalidate the stack
# ---------------------------------------------------------------------------


def test_adding_a_configuration_resets_the_history(model):
    model.current_configuration.integration_unit = "q_A^-1"
    assert model.history.can_undo is True

    model.add_configuration()
    assert model.history.can_undo is False


def test_removing_a_configuration_resets_the_history(model):
    model.add_configuration()
    model.current_configuration.integration_unit = "q_A^-1"
    assert model.history.can_undo is True

    model.remove_configuration()
    assert model.history.can_undo is False


def test_a_mask_of_the_wrong_shape_is_not_written_back(model):
    """Resizing the mask without changing the image leaves older snapshots
    holding a mask that no longer fits. Restoring one would put a mask on
    screen that does not match the image, so it is skipped."""
    model.mask_model.mask_rect(10, 10, 5, 5)
    model.mask_model.set_dimension((100, 100))

    while model.history.can_undo:
        model.history.undo()
    assert model.mask_model.get_img().shape == (100, 100)


def test_loading_a_project_resets_the_history(model, tmp_path):
    model.current_configuration.integration_unit = "q_A^-1"
    filename = str(tmp_path / "project.dio")
    model.save(filename)

    model.current_configuration.integration_rad_points = 555
    model.load(filename)
    assert model.history.can_undo is False
    assert model.history.can_redo is False


def test_second_configuration_settings_are_restored(model):
    """Snapshots cover every configuration, not just the selected one."""
    model.add_configuration()
    model.configurations[0].integration_unit = "q_A^-1"
    model.history.reset()

    model.configurations[0].cake_azimuth_points = 720
    model.select_configuration(1)
    model.history.undo()

    assert model.configurations[0].cake_azimuth_points == 360


def test_switching_configuration_is_not_an_undo_step(model):
    model.add_configuration()
    model.history.reset()

    model.select_configuration(0)
    model.select_configuration(1)
    assert model.history.can_undo is False


# ---------------------------------------------------------------------------
# overlays
# ---------------------------------------------------------------------------


@pytest.fixture
def xy():
    x = np.linspace(1.0, 10.0, 100)
    return x, x * 2


def test_adding_an_overlay_is_undoable(model, xy):
    model.overlay_model.add_overlay(*xy, "first")
    assert len(model.overlay_model.overlays) == 1
    assert model.history.undo_label == "add overlay"

    model.history.undo()
    assert model.overlay_model.overlays == []
    model.history.redo()
    assert [o.name for o in model.overlay_model.overlays] == ["first"]


def test_removing_an_overlay_is_undoable(model, xy):
    model.overlay_model.add_overlay(*xy, "first")
    model.overlay_model.add_overlay(*xy, "second")
    model.history.reset()

    model.overlay_model.remove_overlay(0)
    assert [o.name for o in model.overlay_model.overlays] == ["second"]

    model.history.undo()
    assert [o.name for o in model.overlay_model.overlays] == ["first", "second"]


def test_undoing_a_removal_restores_the_original_object(model, xy):
    """Not a look-alike: the pattern view keeps plot items per overlay."""
    model.overlay_model.add_overlay(*xy, "first")
    original = model.overlay_model.overlays[0]
    model.history.reset()

    model.overlay_model.remove_overlay(0)
    model.history.undo()
    assert model.overlay_model.overlays[0] is original


def test_overlay_display_state_is_undoable(model, xy):
    model.overlay_model.add_overlay(*xy, "first")
    model.history.reset()

    model.overlay_model.set_overlay_scaling(0, 5.0)
    model.overlay_model.set_overlay_color(0, "#123456")
    assert model.overlay_model.get_overlay_scaling(0) == 5.0

    model.history.undo()
    assert model.overlay_model.overlays[0].color != "#123456"
    model.history.undo()
    assert model.overlay_model.get_overlay_scaling(0) == 1.0


def test_untouched_overlays_are_not_rebuilt(model, xy):
    """Undoing an unrelated change must leave overlay objects in place."""
    model.overlay_model.add_overlay(*xy, "first")
    model.overlay_model.add_overlay(*xy, "second")
    originals = list(model.overlay_model.overlays)
    model.history.reset()

    model.current_configuration.integration_unit = "q_A^-1"
    model.history.undo()
    assert model.overlay_model.overlays == originals


def test_overlay_data_is_shared_not_copied(model, xy):
    model.overlay_model.add_overlay(*xy, "first")
    model.current_configuration.integration_rad_points = 999

    refs = [s.state.overlays[0].overlay for s in model.history._steps[-2:]]
    assert refs[0] is refs[1] or refs[0] == refs[1]


# ---------------------------------------------------------------------------
# phases
# ---------------------------------------------------------------------------


@pytest.fixture
def phase_file():
    import glob

    files = sorted(glob.glob("dioptas/tests/data/jcpds/*.jcpds"))
    if not files:
        pytest.skip("no jcpds test data")
    return files[0]


def test_adding_a_phase_is_undoable(model, phase_file):
    model.phase_model.add_jcpds(phase_file)
    assert len(model.phase_model.phases) == 1

    model.history.undo()
    assert model.phase_model.phases == []
    model.history.redo()
    assert len(model.phase_model.phases) == 1


def test_adding_a_phase_costs_exactly_one_step(model, phase_file):
    """add_jcpds_object emits phase_added and phase_changed; the second must
    not consume a second undo step."""
    model.phase_model.add_jcpds(phase_file)
    assert model.history.depth == 1


def test_removing_a_phase_is_undoable(model, phase_file):
    model.phase_model.add_jcpds(phase_file)
    name = model.phase_model.phases[0].name
    model.history.reset()

    model.phase_model.del_phase(0)
    assert model.phase_model.phases == []

    model.history.undo()
    assert len(model.phase_model.phases) == 1
    assert model.phase_model.phases[0].name == name
    # the parallel lists must come back in step with the phases
    assert len(model.phase_model.item_params) == 1
    assert len(model.phase_model.reflections) == 1
    assert len(model.phase_model.phase_files) == 1


def test_phase_pressure_is_undoable(model, phase_file):
    model.phase_model.add_jcpds(phase_file)
    model.history.reset()

    model.phase_model.set_pressure(0, 25.0)
    assert model.phase_model.phases[0].params["pressure"] == 25.0

    model.history.undo()
    assert model.phase_model.phases[0].params["pressure"] == 0.0


def test_pressure_with_same_conditions_is_one_step(model, phase_file):
    """Applying to all phases is one action, so it is one Ctrl+Z."""
    import glob

    files = sorted(glob.glob("dioptas/tests/data/jcpds/*.jcpds"))[:2]
    if len(files) < 2:
        pytest.skip("need two jcpds files")
    for f in files:
        model.phase_model.add_jcpds(f)
    model.phase_model.same_conditions = True
    model.history.reset()

    model.phase_model.set_pressure(0, 25.0)
    assert all(p.params["pressure"] == 25.0 for p in model.phase_model.phases)

    model.history.undo()
    assert all(p.params["pressure"] == 0.0 for p in model.phase_model.phases)


def test_undo_does_not_mark_phases_as_modified(model, phase_file):
    """Deep-copying a jcpds flips its modified flag unless handled — that
    shows up as a '*' on the phase name."""
    model.phase_model.add_jcpds(phase_file)
    model.history.reset()
    assert model.phase_model.phases[0].params["modified"] is False

    model.phase_model.set_pressure(0, 25.0)
    model.history.undo()
    assert model.phase_model.phases[0].params["modified"] is False
    assert "*" not in model.phase_model.phases[0].name


def test_snapshots_are_isolated_from_later_phase_edits(model, phase_file):
    """A later in-place edit must not reach back into a stored snapshot —
    snapshots hold the phase as pure content, not as object references."""
    model.phase_model.add_jcpds(phase_file)
    model.history.reset()
    stored = model.history._steps[0].state.phases[0]

    model.phase_model.set_pressure(0, 50.0)
    assert stored.crystal["pressure"] == 0.0


def test_phase_display_state_is_undoable(model, phase_file):
    model.phase_model.add_jcpds(phase_file)
    model.history.reset()

    model.phase_model.set_phase_visible(0, False)
    assert model.phase_model.phase_visible[0] is False

    model.history.undo()
    assert model.phase_model.phase_visible[0] is True


def test_phase_snapshots_hold_no_object_references(model, phase_file):
    """Nothing is copied per step anymore: a phase snapshot is JSON-plain
    content, so settings-only steps stay cheap however many phases exist."""
    model.phase_model.add_jcpds(phase_file)
    model.history.reset()

    for points in range(100, 110):
        model.current_configuration.cake_azimuth_points = points

    first = model.history._steps[0].state.phases
    assert all(s.state.phases == first for s in model.history._steps)


# ---------------------------------------------------------------------------
# how much recomputation an undo costs
# ---------------------------------------------------------------------------


def _count_integrations(configuration):
    """Replaces the integration computations with counters."""
    counts = {"1d": 0, "2d": 0}
    configuration.pattern_integration._compute = lambda: counts.__setitem__(
        "1d", counts["1d"] + 1
    )
    configuration.cake_integration._compute = lambda: counts.__setitem__(
        "2d", counts["2d"] + 1
    )
    return counts


def test_undo_of_an_integration_setting_reintegrates_once(model):
    config = model.current_configuration
    config.integration_rad_points = 1000
    counts = _count_integrations(config)

    model.history.undo()
    assert counts["1d"] == 1


def test_undo_of_several_integration_settings_still_reintegrates_once(model):
    """A step touching three fields must not cost three integrations."""
    config = model.current_configuration
    with model.history.transaction("bulk"):
        config.integration_rad_points = 2000
        config.params.cake_azimuth_points = 720
        config.params.oned_azimuth_range = [0.0, 90.0]
    counts = _count_integrations(config)

    model.history.undo()
    assert counts["1d"] == 1


def test_undo_of_an_unrelated_setting_does_not_reintegrate(model):
    """Nothing that feeds the integration changed, so nothing recomputes."""
    model.mask_model.mode = False
    counts = _count_integrations(model.current_configuration)

    model.history.undo()
    assert counts == {"1d": 0, "2d": 0}


def test_undo_only_reintegrates_the_configuration_it_touched(model):
    model.add_configuration()
    model.select_configuration(0)
    model.history.reset()

    model.configurations[0].integration_rad_points = 4000
    other = _count_integrations(model.configurations[1])

    model.history.undo()
    assert other == {"1d": 0, "2d": 0}


# ---------------------------------------------------------------------------
# calibration peak picking
# ---------------------------------------------------------------------------


@pytest.fixture
def images():
    import glob
    import os

    files = sorted(glob.glob(os.path.join(_DATA, "*.tif")))
    if len(files) < 2:
        pytest.skip("need two test images")
    return files[:2]


def test_picking_a_peak_is_undoable(model):
    model.calibration_model.find_peak(20, 20, 5, 0)
    assert len(model.calibration_model.points) == 1
    assert model.history.undo_label == "calibration peaks"

    model.history.undo()
    assert model.calibration_model.points == []
    model.history.redo()
    assert len(model.calibration_model.points) == 1


def test_each_pick_is_its_own_step(model):
    """Two clicks are two decisions; they must not coalesce into one."""
    model.calibration_model.find_peak(20, 20, 5, 0)
    model.calibration_model.find_peak(30, 30, 5, 1)

    model.history.undo()
    assert len(model.calibration_model.points) == 1
    model.history.undo()
    assert len(model.calibration_model.points) == 0


def test_undo_restores_the_ring_index_of_a_peak(model):
    model.calibration_model.find_peak(20, 20, 5, 3)
    model.history.reset()
    model.calibration_model.find_peak(30, 30, 5, 7)

    model.history.undo()
    assert model.calibration_model.points_index == [3]


def test_clearing_peaks_is_undoable(model):
    model.calibration_model.find_peak(20, 20, 5, 0)
    model.calibration_model.find_peak(30, 30, 5, 0)
    model.history.reset()

    model.calibration_model.clear_peaks()
    assert model.calibration_model.points == []

    model.history.undo()
    assert len(model.calibration_model.points) == 2


def test_restored_peaks_keep_their_coordinates(model):
    model.calibration_model.find_peak(20, 20, 5, 0)
    original = np.array(model.calibration_model.points[0])
    model.history.reset()

    model.calibration_model.clear_peaks()
    model.history.undo()
    assert np.array_equal(np.array(model.calibration_model.points[0]), original)


def test_picking_the_same_peaks_again_is_not_a_new_step(model):
    model.calibration_model.find_peak(20, 20, 5, 0)
    depth = model.history.depth
    model.calibration_model.clear_peaks()
    model.history.undo()  # back to the single peak
    assert model.history.depth == depth + 1  # the clear is the only new step


# ---------------------------------------------------------------------------
# image loading
# ---------------------------------------------------------------------------


def test_loading_an_image_is_undoable(model, images):
    import os

    model.img_model.load(images[0])
    model.history.reset()

    model.img_model.load(images[1])
    assert os.path.basename(model.img_model.filename) == os.path.basename(images[1])

    model.history.undo()
    assert os.path.basename(model.img_model.filename) == os.path.basename(images[0])
    model.history.redo()
    assert os.path.basename(model.img_model.filename) == os.path.basename(images[1])


def test_undoing_an_image_load_brings_back_its_mask(model, images):
    """The two test images have different detector sizes, so this also covers
    the mask being resized by the load."""
    model.img_model.load(images[0])
    model.mask_model.mask_rect(100, 100, 50, 50)
    shape, masked = model.mask_model.get_img().shape, model.mask_model.get_img().sum()
    assert masked > 0

    model.img_model.load(images[1])
    assert model.mask_model.get_img().shape != shape  # resized by the new image

    model.history.undo()
    assert model.mask_model.get_img().shape == shape
    assert model.mask_model.get_img().sum() == masked


def test_a_missing_file_does_not_abort_the_rest_of_the_undo(model, images, tmp_path):
    """The file may be gone by the time you undo; the rest must still apply."""
    import shutil

    temporary = str(tmp_path / "gone.tif")
    shutil.copy(images[0], temporary)
    model.img_model.load(temporary)
    model.history.reset()

    model.img_model.load(images[1])
    model.current_configuration.integration_unit = "q_A^-1"
    os.remove(temporary)

    model.history.undo()  # the settings change
    model.history.undo()  # the image load, whose file is now gone
    assert model.current_configuration.integration_unit == "2th_deg"


# ---------------------------------------------------------------------------
# one user action is one undo step
# ---------------------------------------------------------------------------


@pytest.fixture
def loaded(model):
    """A real image, so transformations have something to act on."""
    model.img_model.load(os.path.join(_DATA, "CeO2_Pilatus1M.tif"))
    model.history.reset()
    return model


def test_rotating_the_image_is_one_step(loaded):
    """The rotation resizes the mask too; that is a consequence, not a second
    action, and recording it separately made the first undo look like a no-op."""
    loaded.img_model.rotate_img_p90()
    assert loaded.history.depth == 1
    assert loaded.history.undo_label == "transformations"


def test_undoing_a_rotation_turns_the_image_back(loaded):
    shape = loaded.img_model.img_data.shape
    loaded.img_model.rotate_img_p90()
    assert loaded.img_model.img_data.shape == shape[::-1]

    loaded.history.undo()
    assert loaded.img_model.params.transformations == []
    # the pixels must follow, not just the list that records them
    assert loaded.img_model.img_data.shape == shape


def test_redoing_a_rotation_applies_it_again(loaded):
    shape = loaded.img_model.img_data.shape
    loaded.img_model.rotate_img_p90()
    loaded.history.undo()
    loaded.history.redo()

    assert loaded.img_model.params.transformations == ["rotate_matrix_p90"]
    assert loaded.img_model.img_data.shape == shape[::-1]


def test_several_transformations_undo_one_at_a_time(loaded):
    loaded.img_model.rotate_img_p90()
    loaded.img_model.flip_img_horizontally()
    assert len(loaded.img_model.params.transformations) == 2

    loaded.history.undo()
    assert len(loaded.img_model.params.transformations) == 1
    loaded.history.undo()
    assert loaded.img_model.params.transformations == []


# ---------------------------------------------------------------------------
# calibration geometry and detector
# ---------------------------------------------------------------------------


@pytest.fixture
def calibratable(model):
    """An image with a matching .poni available to load onto it."""
    model.img_model.load(os.path.join(_DATA, "CeO2_Pilatus1M.tif"))
    model.history.reset()
    return model


def test_loading_a_calibration_is_undoable(calibratable):
    cm = calibratable.calibration_model
    assert cm.is_calibrated is False

    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    assert cm.is_calibrated is True
    assert calibratable.history.undo_label == "calibration"
    distance = float(cm.pattern_geometry.dist)

    calibratable.history.undo()
    assert cm.is_calibrated is False
    assert float(cm.pattern_geometry.dist) != distance

    calibratable.history.redo()
    assert cm.is_calibrated is True
    assert float(cm.pattern_geometry.dist) == distance


def test_undo_restores_the_whole_geometry(calibratable):
    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    first = dict(cm.pattern_geometry.get_config())
    calibratable.history.reset()

    cm.load(os.path.join(_DATA, "LaB6_40keV_MarCCD.poni"))
    assert cm.pattern_geometry.get_config() != first

    calibratable.history.undo()
    restored = cm.pattern_geometry.get_config()
    for key in ("dist", "poni1", "poni2", "rot1", "rot2", "rot3", "wavelength"):
        assert restored[key] == first[key], key


def test_undo_restores_the_calibration_name(calibratable):
    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    assert cm.calibration_name == "CeO2_Pilatus1M"

    calibratable.history.undo()
    assert cm.calibration_name != "CeO2_Pilatus1M"


def test_calibration_is_not_re_recorded_when_nothing_changed(calibratable):
    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    depth = calibratable.history.depth

    cm.parameters_changed.emit()  # as a no-op refinement would
    assert calibratable.history.depth == depth


def test_a_calibration_that_cannot_be_restored_is_skipped(calibratable, caplog):
    """A geometry pyFAI rejects must not abandon the rest of the undo."""
    from dioptas.model.state import snapshot as snapshot_module

    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    calibratable.history.reset()

    calibratable.current_configuration.integration_unit = "q_A^-1"
    # corrupt the stored geometry so restoring it raises
    state = calibratable.history._steps[0].state
    state.configurations[0].calibration["geometry"] = {"dist": object()}

    calibratable.history.undo()
    assert calibratable.current_configuration.integration_unit == "2th_deg"


# ---------------------------------------------------------------------------
# payload lifetime follows the history
# ---------------------------------------------------------------------------


def test_payloads_of_dropped_history_are_swept(model):
    """Resetting the history must not leak the blobs its snapshots held."""
    for offset in range(5):
        model.mask_model.mask_rect(offset * 8, 0, 5, 5)
    grown = len(model.payloads)
    assert grown >= 5

    model.history.reset()
    # only the payloads the baseline snapshot references survive
    live = {s.configurations[0].mask_data for s in model.history.states()}
    assert set(model.payloads._payloads) == live


def test_identical_masks_across_configurations_share_a_payload(model):
    model.add_configuration()
    # give both configurations the same image, hence the same mask shape,
    # and draw the same rectangle in each
    for configuration in model.configurations:
        configuration.img_model._img_data = np.zeros((50, 50))
        configuration.img_model.img_changed.emit()
        configuration.mask_model.mask_rect(10, 10, 5, 5)

    state = model.history.states()[-1]
    ids = {config.mask_data for config in state.configurations}
    assert len(ids) == 1  # identical content, one payload


# ---------------------------------------------------------------------------
# file state as params (step 1 of the state-ubiquity migration)
# ---------------------------------------------------------------------------


def test_loading_keeps_params_and_screen_in_sync(model, images):
    model.img_model.load(images[0])
    assert model.img_model.params.filename == images[0]
    assert model.img_model.params.filename == model.img_model.filename
    assert model.img_model.params.series_pos == model.img_model.series_pos


def test_writing_the_filename_param_loads_the_file(model, images):
    """The store rule: writing state has the same effect as the action."""
    model.img_model.params.filename = images[0]
    assert model.img_model.filename == images[0]
    assert model.img_model.img_data is not None


def test_background_image_is_undoable(model, images):
    model.img_model.load(images[0])
    model.history.reset()

    model.img_model.load_background(images[0])
    assert model.img_model.has_background() is True
    assert model.img_model.params.background_filename == images[0]

    model.history.undo()
    assert model.img_model.has_background() is False
    assert model.img_model.params.background_filename == ""

    model.history.redo()
    assert model.img_model.has_background() is True


def test_removing_the_background_is_undoable(model, images):
    model.img_model.load(images[0])
    model.img_model.load_background(images[0])
    model.history.reset()

    model.img_model.reset_background()
    assert model.img_model.has_background() is False

    model.history.undo()
    assert model.img_model.has_background() is True
    assert model.img_model.params.background_filename == images[0]


def test_missing_background_file_is_skipped_with_params_synced(model, images, tmp_path):
    import shutil

    temporary = str(tmp_path / "bg.tif")
    shutil.copy(images[0], temporary)
    model.img_model.load(images[0])
    model.img_model.load_background(temporary)
    model.history.reset()

    model.img_model.reset_background()
    os.remove(temporary)

    model.history.undo()  # background file is gone
    # the state must not claim a background that is not on screen
    assert model.img_model.has_background() is False
    assert model.img_model.params.background_filename == ""


def test_a_failed_load_leaves_the_model_untouched(model, images):
    """get_image_data runs before any state is mutated."""
    model.img_model.load(images[0])
    with pytest.raises(Exception):
        model.img_model.load("/nowhere/not_an_image.tif")
    assert model.img_model.filename == images[0]
    assert model.img_model.params.filename == images[0]


# ---------------------------------------------------------------------------
# peak selections as params records (step 2a)
# ---------------------------------------------------------------------------


def test_peak_selections_are_plain_nested_tuples(model):
    model.calibration_model.find_peak(20, 20, 5, 3)
    selections = model.calibration_model.params.peak_selections
    assert isinstance(selections, tuple)
    ring, positions = selections[0]
    assert ring == 3
    assert isinstance(positions, tuple)
    assert isinstance(positions[0], tuple)


def test_points_properties_mirror_the_params(model):
    model.calibration_model.find_peak(20, 20, 5, 1)
    model.calibration_model.find_peak(30, 30, 5, 2)
    assert model.calibration_model.points_index == [1, 2]
    assert len(model.calibration_model.points) == 2
    assert model.calibration_model.points[0].shape[-1] == 2


def test_list_shaped_selections_are_canonicalized(model):
    """A JSON round trip delivers nested lists; the reaction normalizes them
    so snapshots and fresh picks always compare equal."""
    model.calibration_model.params.peak_selections = [[1, [[10.0, 12.0]]]]
    selections = model.calibration_model.params.peak_selections
    assert selections == ((1, ((10.0, 12.0),)),)
    assert isinstance(selections, tuple)


def test_picked_peaks_survive_a_project_round_trip(model, tmp_path):
    """Peaks ride the generic params doc now — previously they were lost."""
    model.calibration_model.find_peak(20, 20, 5, 0)
    model.calibration_model.find_peak(30, 30, 5, 1)
    kept = model.calibration_model.params.peak_selections

    filename = str(tmp_path / "peaks.dio")
    model.save(filename)
    model.load(filename)
    assert model.calibration_model.params.peak_selections == kept
    assert model.calibration_model.points_index == [0, 1]


def test_remove_peaks_by_ring_goes_through_params(model):
    model.calibration_model.find_peak(20, 20, 5, 0)
    model.calibration_model.find_peak(30, 30, 5, 1)
    model.history.reset()

    model.calibration_model.remove_peaks_by_ring(0)
    assert model.calibration_model.points_index == [1]

    model.history.undo()
    assert model.calibration_model.points_index == [0, 1]


# ---------------------------------------------------------------------------
# calibration result as params (step 2b)
# ---------------------------------------------------------------------------


def test_calibration_result_lives_in_params(calibratable):
    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))

    assert cm.params.is_calibrated is True
    assert cm.params.geometry is not None
    assert cm.params.geometry["dist"] == float(cm.pattern_geometry.dist)
    assert cm.params.poni_filename.endswith("CeO2_Pilatus1M.poni")
    assert cm.params.calibration_name == "CeO2_Pilatus1M"


def test_writing_the_geometry_param_rebuilds_the_geometry(calibratable):
    """The store rule: writing state has the same effect as the action."""
    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))

    changed = dict(cm.params.geometry)
    changed["dist"] = 0.42
    cm.params.geometry = changed
    assert abs(float(cm.pattern_geometry.dist) - 0.42) < 1e-12


def test_calibration_result_survives_a_project_round_trip(calibratable, tmp_path):
    cm = calibratable.calibration_model
    cm.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    distance = float(cm.pattern_geometry.dist)

    filename = str(tmp_path / "calibrated.dio")
    calibratable.save(filename)
    calibratable.load(filename)

    cm = calibratable.calibration_model  # configurations were rebuilt
    assert cm.is_calibrated is True
    assert abs(float(cm.pattern_geometry.dist) - distance) < 1e-12
    assert cm.calibration_name == "CeO2_Pilatus1M"


# ---------------------------------------------------------------------------
# pattern file + background by overlay reference (step 3)
# ---------------------------------------------------------------------------


@pytest.fixture
def pattern_file():
    import glob

    files = sorted(glob.glob(os.path.join(_DATA, "*.xy")))
    if not files:
        pytest.skip("no .xy test data")
    return files[0]


def test_loading_a_pattern_file_is_undoable(model, pattern_file):
    model.pattern_model.load_pattern(pattern_file)
    assert model.pattern_model.params.pattern_source == "file"
    assert model.pattern_model.params.pattern_filename == pattern_file

    previous_name = model.pattern_model.pattern.name
    model.history.undo()
    assert model.pattern_model.params.pattern_filename == ""
    model.history.redo()
    assert model.pattern_model.pattern.name == previous_name


def test_integrated_patterns_are_never_reloaded_as_files(model, images):
    """An integrated pattern's filename names the IMAGE — reloading it as a
    two-column text file would fail loudly or corrupt the pattern."""
    model.pattern_model.set_pattern(
        np.linspace(1, 10, 50), np.ones(50), images[0], unit="2th_deg"
    )
    assert model.pattern_model.params.pattern_source == "integrated"

    read_attempts = []
    original = model.pattern_model.load_pattern
    model.pattern_model.load_pattern = lambda f: read_attempts.append(f)

    model.history.undo()
    model.history.redo()
    assert read_attempts == []
    model.pattern_model.load_pattern = original


def test_overlays_carry_a_stable_uid(model, xy):
    model.overlay_model.add_overlay(*xy, "first")
    uid = model.overlay_model.overlays[0].params.uid
    assert uid
    assert model.overlay_model.get_overlay_by_uid(uid) is model.overlay_model.overlays[0]


def test_setting_an_overlay_as_background_is_undoable(model, xy):
    model.overlay_model.add_overlay(*xy, "bkg")
    overlay = model.overlay_model.overlays[0]
    model.history.reset()

    model.pattern_model.params.background_overlay_uid = overlay.params.uid
    assert model.pattern_model.background_pattern is overlay

    model.history.undo()
    assert model.pattern_model.background_pattern is None

    model.history.redo()
    assert model.pattern_model.background_pattern is overlay


def test_undoing_background_overlay_removal_restores_the_link(model, xy):
    """The uid must resolve again once the overlay itself is restored."""
    model.overlay_model.add_overlay(*xy, "bkg")
    overlay = model.overlay_model.overlays[0]
    model.pattern_model.params.background_overlay_uid = overlay.params.uid
    model.history.reset()

    # remove: clear the reference, then the overlay (as the controller does)
    model.pattern_model.params.background_overlay_uid = ""
    model.overlay_model.remove_overlay(0)
    assert model.pattern_model.background_pattern is None

    model.history.undo()  # the removal
    model.history.undo()  # the reference clear
    assert model.overlay_model.overlays[0] is overlay
    assert model.pattern_model.background_pattern is overlay


def test_background_uid_survives_a_project_round_trip(model, xy, tmp_path):
    model.overlay_model.add_overlay(*xy, "bkg")
    overlay = model.overlay_model.overlays[0]
    model.pattern_model.params.background_overlay_uid = overlay.params.uid
    uid = overlay.params.uid

    filename = str(tmp_path / "background.dio")
    model.save(filename)
    model.load(filename)

    restored = model.overlay_model.get_overlay_by_uid(uid)
    assert restored is not None
    assert model.pattern_model.background_pattern is restored


# ---------------------------------------------------------------------------
# image corrections as params (step 4 — the last audit gap)
# ---------------------------------------------------------------------------


@pytest.fixture
def calibrated(model):
    model.img_model.load(os.path.join(_DATA, "CeO2_Pilatus1M.tif"))
    model.calibration_model.load(os.path.join(_DATA, "CeO2_Pilatus1M.poni"))
    model.history.reset()
    return model


def _add_cbn(model):
    from dioptas.model.util.ImgCorrection import CbnCorrection

    tth = 180.0 / np.pi * model.calibration_model.tth_array
    azi = 180.0 / np.pi * model.calibration_model.azi_array
    correction = CbnCorrection(tth_array=tth, azi_array=azi)
    correction.set_params(
        {
            "diamond_thickness": 2.2,
            "seat_thickness": 5.3,
            "small_cbn_seat_radius": 0.4,
            "large_cbn_seat_radius": 1.95,
            "tilt": 0.0,
            "tilt_rotation": 0.0,
            "diamond_abs_length": 13.7,
            "seat_abs_length": 14.05,
            "center_offset": 0.0,
            "center_offset_angle": 0.0,
        }
    )
    correction.update()
    model.img_model.add_img_correction(correction, "cbn")


def test_adding_a_correction_is_undoable(calibrated):
    _add_cbn(calibrated)
    assert calibrated.img_model.has_corrections()
    assert "cbn" in calibrated.img_model.params.corrections
    assert calibrated.history.undo_label == "image correction"

    calibrated.history.undo()
    assert not calibrated.img_model.has_corrections()
    assert calibrated.img_model.params.corrections == {}

    calibrated.history.redo()
    assert calibrated.img_model.has_corrections()
    rebuilt = calibrated.img_model.get_img_correction("cbn")
    assert rebuilt is not None
    assert rebuilt.get_params()["diamond_thickness"] == 2.2


def test_removing_a_correction_is_undoable(calibrated):
    _add_cbn(calibrated)
    calibrated.history.reset()

    calibrated.img_model.delete_img_correction("cbn")
    assert not calibrated.img_model.has_corrections()

    calibrated.history.undo()
    assert calibrated.img_model.has_corrections()


def test_changing_correction_parameters_is_undoable(calibrated):
    """The controller replaces the correction object on every edit; the
    params must follow, and undo must bring the old values back."""
    _add_cbn(calibrated)
    calibrated.history.reset()

    _add_cbn(calibrated)  # same name, would be an edit in the GUI
    updated = dict(calibrated.img_model.params.corrections["cbn"])
    updated["diamond_thickness"] = 3.0
    calibrated.img_model.params.corrections = {
        **calibrated.img_model.params.corrections,
        "cbn": updated,
    }
    assert (
        calibrated.img_model.get_img_correction("cbn").get_params()[
            "diamond_thickness"
        ]
        == 3.0
    )

    calibrated.history.undo()
    assert (
        calibrated.img_model.get_img_correction("cbn").get_params()[
            "diamond_thickness"
        ]
        == 2.2
    )


def test_corrections_ride_the_params_doc_in_projects(calibrated, tmp_path):
    _add_cbn(calibrated)

    filename = str(tmp_path / "corrected.dio")
    calibrated.save(filename)
    calibrated.load(filename)

    assert "cbn" in calibrated.img_model.params.corrections
    assert calibrated.img_model.has_corrections()
    assert (
        calibrated.img_model.get_img_correction("cbn").get_params()[
            "diamond_thickness"
        ]
        == 2.2
    )


def test_transfer_correction_state_is_filenames_not_arrays(calibrated):
    original = os.path.join(_DATA, "TransferCorrection", "original.tif")
    response = os.path.join(_DATA, "TransferCorrection", "response.tif")
    if not os.path.isfile(original):
        pytest.skip("no transfer correction test data")

    calibrated.img_model.load(original)
    calibrated.img_model.transfer_correction.load_original_image(original)
    calibrated.img_model.transfer_correction.load_response_image(response)
    calibrated.img_model.enable_transfer_function()
    calibrated.history.reset()

    stored = calibrated.img_model.params.corrections["transfer"]
    assert stored["original_filename"] == original
    assert "original_data" not in stored  # arrays are caches, not state

    calibrated.img_model.disable_transfer_function()
    assert "transfer" not in calibrated.img_model.params.corrections

    calibrated.history.undo()
    assert calibrated.img_model.get_img_correction("transfer") is not None


def test_choosing_a_predefined_detector_is_undoable(calibrated):
    from dioptas.model.CalibrationModel import DetectorModes

    calibrated.calibration_model.load_detector("Pilatus CdTe 1M")
    assert calibrated.calibration_model.detector_mode == DetectorModes.PREDEFINED

    calibrated.history.undo()
    assert calibrated.calibration_model.detector_mode == DetectorModes.CUSTOM
    assert calibrated.calibration_model.detector.name != "Pilatus CdTe 1M"

    calibrated.history.redo()
    assert calibrated.calibration_model.detector_mode == DetectorModes.PREDEFINED
    assert calibrated.calibration_model.detector.name == "Pilatus CdTe 1M"


# ---------------------------------------------------------------------------
# project file format 2: atomic writes and legacy refusal
# ---------------------------------------------------------------------------


def test_projects_are_stamped_with_format_2(model, tmp_path):
    import h5py

    filename = str(tmp_path / "stamped.dio")
    model.save(filename)
    with h5py.File(filename, "r") as f:
        assert int(f.attrs["format_version"]) == 2


def test_old_project_files_are_refused_cleanly(model, tmp_path):
    """A pre-migration file must produce a clear error, never a half-load."""
    import h5py

    from dioptas.model.DioptasModel import UnsupportedProjectFileError

    filename = str(tmp_path / "old.dio")
    with h5py.File(filename, "w") as f:
        f.attrs["format_version"] = 1

    model.current_configuration.integration_unit = "q_A^-1"
    with pytest.raises(UnsupportedProjectFileError, match="0.8.7 or earlier"):
        model.load(filename)
    # the session was not touched by the refusal
    assert model.current_configuration.integration_unit == "q_A^-1"
    assert len(model.configurations) == 1


def test_a_failing_save_leaves_the_previous_file_intact(model, tmp_path):
    filename = str(tmp_path / "precious.dio")
    model.save(filename)
    size_before = os.path.getsize(filename)

    original = model._save_into
    model._save_into = lambda f: (_ for _ in ()).throw(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        model.save(filename)
    model._save_into = original

    assert os.path.getsize(filename) == size_before
    assert model.load(filename) is None  # still a readable project
    leftovers = [n for n in os.listdir(tmp_path) if ".tmp-" in n]
    assert leftovers == []


def test_loading_replaces_phases_and_overlays_instead_of_appending(
    model, phase_file, xy
):
    """Phases and overlays are global, so clearing the configurations is not
    enough — loading into a session that already has some used to double
    them."""
    model.phase_model.add_jcpds(phase_file)
    model.overlay_model.add_overlay(*xy, "one")

    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        filename = os.path.join(directory, "replace.dio")
        model.save(filename)
        model.load(filename)

    assert len(model.phase_model.phases) == 1
    assert len(model.overlay_model.overlays) == 1


# ---------------------------------------------------------------------------
# reported from use: image loads and phase colours
# ---------------------------------------------------------------------------


def test_undoing_the_first_image_load_unloads_it(model, images):
    """"No image" is a real state — a fresh Dioptas is in it — so undoing the
    first load has to return to it. It used to be treated as "there is no
    unload", which left the history believing it had applied a state it had
    not."""
    model.history.reset()
    model.img_model.load(images[0])

    model.history.undo()
    assert model.img_model.filename == ""
    assert model.img_model.img_data.sum() == 0

    model.history.redo()
    assert model.img_model.filename == images[0]
    assert model.img_model.img_data.sum() > 0


def test_undoing_a_second_load_brings_the_first_image_back(model, images):
    """The sequence that exposed it: load, load, undo. The first undo used to
    do nothing while still moving the cursor, so the next edit discarded the
    step that was actually on screen."""
    model.history.reset()
    model.img_model.load(images[0])
    first_sum = float(model.img_model.img_data.sum())
    model.img_model.load(images[1])
    assert float(model.img_model.img_data.sum()) != first_sum

    model.history.undo()
    assert model.img_model.filename == images[0]
    assert abs(float(model.img_model.img_data.sum()) - first_sum) < 1


def test_a_step_that_cannot_be_fully_applied_stays_consistent(model, images):
    """states[cursor] must keep mirroring reality even when a reaction falls
    short, or the next edit throws away a step that is still on screen."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        temporary = os.path.join(directory, "gone.tif")
        shutil.copy(images[0], temporary)
        model.img_model.load(temporary)
        model.img_model.load(images[1])
        os.remove(temporary)

        model.history.undo()  # cannot re-read the deleted file
        # whatever it managed to restore, the step now says so
        recaptured = model.history.states()[model.history._cursor]
        assert recaptured.configurations[0].img["filename"] == (
            model.img_model.filename
        )


def test_phase_colour_survives_undo_and_redo(model, phase_file):
    """Restoring a phase used to route through the new-phase path, which
    assigns the next colour from a counter — so every undo/redo cycle
    repainted the phase in a different colour."""
    model.phase_model.add_jcpds(phase_file)
    colour = tuple(model.phase_model.phase_colors[0])

    for _ in range(3):
        model.history.undo()
        model.history.redo()
        assert tuple(model.phase_model.phase_colors[0]) == colour


def test_restoring_a_phase_does_not_consume_a_colour(model, phase_file):
    """The counter must only advance for genuinely new phases, otherwise a
    phase added after some undoing skips colours."""
    model.phase_model.add_jcpds(phase_file)
    model.history.undo()
    model.history.redo()

    model.phase_model.add_jcpds(phase_file)
    colours = [tuple(c) for c in model.phase_model.phase_colors]
    assert colours[0] != colours[1]  # distinct, and no colour was skipped
    assert model.phase_model._color_counter == 2


def test_the_colour_counter_is_per_model(phase_file):
    """It used to be a class attribute, so one model's phases shifted the
    colours of another's (the bug class the MapModel signals had)."""
    first, second = DioptasModel(), DioptasModel()
    first.phase_model.add_jcpds(phase_file)
    second.phase_model.add_jcpds(phase_file)
    assert (
        tuple(first.phase_model.phase_colors[0])
        == tuple(second.phase_model.phase_colors[0])
    )
