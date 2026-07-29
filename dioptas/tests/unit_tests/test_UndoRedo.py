# SPDX-License-Identifier: MIT

"""Undo/redo through DioptasModel.history.

The mask used to carry its own undo deques; those behaviours are asserted here
against the single global stack that replaced them.
"""

import numpy as np
import pytest

from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.util.MaskPlugin import MaskPluginBase


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

    blob = model.history._steps[-1].state.configurations[0].mask_data
    raw = model.mask_model.get_img().nbytes
    assert blob.shape == (512, 512)
    assert len(blob.data) < raw / 8


def test_masks_are_shared_between_snapshots_that_did_not_touch_them(model):
    """Settings-only steps must not each pay for a copy of the mask."""
    model.mask_model.mask_rect(10, 10, 5, 5)
    model.current_configuration.integration_unit = "q_A^-1"
    model.current_configuration.integration_rad_points = 999

    blobs = [s.state.configurations[0].mask_data for s in model.history._steps[-3:]]
    assert blobs[0] is blobs[1] is blobs[2]


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


def test_loading_an_image_is_not_undoable(model, tmp_path):
    """Undo covers edits, not navigation."""
    model.img_model._img_data = np.ones((50, 50))
    model.img_model.img_changed.emit()
    assert model.history.can_undo is False


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


def test_resizing_the_mask_resets_the_history(model):
    """Older snapshots hold a mask of the wrong shape for the new image."""
    model.mask_model.mask_rect(10, 10, 5, 5)
    assert model.history.can_undo is True

    model.mask_model.set_dimension((100, 100))
    assert model.history.can_undo is False


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
