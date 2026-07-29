# SPDX-License-Identifier: MIT

import pytest

from dioptas.model.state import History


class Doc:
    """Stand-in for the captured state: a dict of settings."""

    def __init__(self):
        self.values = {"a": 0, "b": 0}

    def capture(self):
        return dict(self.values)

    def restore(self, state):
        self.values = dict(state)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def doc():
    return Doc()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def history(doc, clock):
    return History(doc.capture, doc.restore, clock=clock)


# ---------------------------------------------------------------------------
# basics
# ---------------------------------------------------------------------------


def test_starts_with_nothing_to_undo(history):
    assert history.can_undo is False
    assert history.can_redo is False
    assert history.depth == 0


def test_undo_restores_previous_state(doc, history):
    doc.values["a"] = 1
    history.record("set a")
    doc.values["a"] = 2
    history.record("set a again")

    assert history.undo() is True
    assert doc.values["a"] == 1
    assert history.undo() is True
    assert doc.values["a"] == 0
    assert history.can_undo is False


def test_redo_reapplies(doc, history):
    doc.values["a"] = 1
    history.record()
    history.undo()
    assert doc.values["a"] == 0

    assert history.redo() is True
    assert doc.values["a"] == 1
    assert history.can_redo is False


def test_undo_redo_return_false_at_the_ends(history):
    assert history.undo() is False
    assert history.redo() is False


def test_new_edit_discards_the_redo_tail(doc, history):
    doc.values["a"] = 1
    history.record()
    doc.values["a"] = 2
    history.record()
    history.undo()
    assert history.can_redo is True

    doc.values["b"] = 9
    history.record()
    assert history.can_redo is False
    history.undo()
    assert doc.values == {"a": 1, "b": 0}


def test_record_without_change_is_not_a_step(doc, history):
    history.record("nothing happened")
    assert history.can_undo is False
    assert history.depth == 0


def test_labels_describe_the_step(doc, history):
    doc.values["a"] = 1
    history.record("change a")
    assert history.undo_label == "change a"
    assert history.redo_label == ""

    history.undo()
    assert history.undo_label == ""
    assert history.redo_label == "change a"


def test_changed_signal_fires_on_record_and_navigation(doc, history):
    seen = []
    history.changed.connect(lambda: seen.append(1))

    doc.values["a"] = 1
    history.record()
    assert len(seen) == 1
    history.undo()
    assert len(seen) == 2
    history.redo()
    assert len(seen) == 3


# ---------------------------------------------------------------------------
# coalescing
# ---------------------------------------------------------------------------


def test_same_key_within_window_coalesces(doc, history, clock):
    doc.values["a"] = 1
    history.record("baseline edit")  # first real step
    for value in range(2, 12):
        clock.advance(0.05)
        doc.values["a"] = value
        history.record("drag a", key="a")

    # the whole drag is one step on top of the first edit
    assert history.depth == 2
    history.undo()
    assert doc.values["a"] == 1


def test_same_key_outside_window_starts_a_new_step(doc, history, clock):
    doc.values["a"] = 1
    history.record("first", key="a")
    clock.advance(5.0)
    doc.values["a"] = 2
    history.record("second", key="a")

    assert history.depth == 2
    history.undo()
    assert doc.values["a"] == 1


def test_different_keys_do_not_coalesce(doc, history, clock):
    doc.values["a"] = 1
    history.record("a", key="a")
    clock.advance(0.01)
    doc.values["b"] = 1
    history.record("b", key="b")

    assert history.depth == 2


def test_no_key_never_coalesces(doc, history, clock):
    doc.values["a"] = 1
    history.record("one")
    clock.advance(0.01)
    doc.values["a"] = 2
    history.record("two")

    assert history.depth == 2


def test_drag_from_the_start_is_one_step_back_to_the_baseline(doc, history, clock):
    """A gesture begun on a fresh history is still a single gesture."""
    for value in (1, 2, 3):
        doc.values["a"] = value
        history.record("drag", key="a")
        clock.advance(0.01)

    assert history.depth == 1
    history.undo()
    assert doc.values["a"] == 0


def test_coalescing_does_not_overwrite_the_oldest_reachable_state(doc, clock):
    """After trimming, steps[0] is real history, not a pristine baseline."""
    history = History(doc.capture, doc.restore, max_steps=3, clock=clock)
    for value in range(1, 9):  # push past max_steps so the front is dropped
        doc.values["a"] = value
        history.record(f"step {value}", key="a")
        clock.advance(5.0)  # far apart: each is its own step

    while history.can_undo:
        oldest = doc.values["a"]
        history.undo()
    oldest = doc.values["a"]

    # a fast same-key edit now must not silently rewrite that oldest state
    doc.values["a"] = 99
    history.record("fast edit", key="a")
    history.undo()
    assert doc.values["a"] == oldest


# ---------------------------------------------------------------------------
# transactions and suspension
# ---------------------------------------------------------------------------


def test_transaction_is_a_single_step(doc, history):
    with history.transaction("compound"):
        doc.values["a"] = 1
        history.record("inner one")
        doc.values["b"] = 1
        history.record("inner two")

    assert history.depth == 1
    assert history.undo_label == "compound"
    history.undo()
    assert doc.values == {"a": 0, "b": 0}


def test_empty_transaction_records_nothing(doc, history):
    with history.transaction("nothing"):
        pass
    assert history.can_undo is False


def test_transaction_without_change_records_nothing(doc, history):
    with history.transaction("no-op"):
        history.record("inner")  # state never actually changed
    assert history.can_undo is False


def test_nested_transactions_join_the_outermost(doc, history):
    with history.transaction("outer"):
        doc.values["a"] = 1
        history.record()
        with history.transaction("inner"):
            doc.values["b"] = 1
            history.record()

    assert history.depth == 1
    assert history.undo_label == "outer"


def test_transaction_takes_the_first_inner_label_when_unlabelled(doc, history):
    with history.transaction():
        doc.values["a"] = 1
        history.record("inner label")
    assert history.undo_label == "inner label"


def test_suspended_records_nothing(doc, history):
    with history.suspended():
        doc.values["a"] = 1
        history.record("ignored")
    assert history.can_undo is False


def test_suspended_wins_over_transaction(doc, history):
    with history.suspended():
        with history.transaction("compound"):
            doc.values["a"] = 1
            history.record()
    assert history.can_undo is False


def test_restore_does_not_record_itself(doc, history):
    """The write-back during undo must not become a new step."""
    doc.values["a"] = 1
    history.record()

    def restore_and_record(state):
        doc.restore(state)
        history.record("reaction to the restore")  # what a params event would do

    history._restore = restore_and_record
    history.undo()

    assert doc.values["a"] == 0
    assert history.can_undo is False
    assert history.can_redo is True


# ---------------------------------------------------------------------------
# bounds and reset
# ---------------------------------------------------------------------------


def test_depth_is_bounded_and_drops_oldest(doc, clock):
    history = History(doc.capture, doc.restore, max_steps=5, clock=clock)
    for value in range(1, 21):
        doc.values["a"] = value
        history.record(f"step {value}")

    assert history.depth == 5
    for _ in range(5):
        history.undo()
    assert history.can_undo is False
    # the oldest reachable state is the 15th, not the original 0
    assert doc.values["a"] == 15


def test_reset_drops_history_and_rebaselines(doc, history):
    doc.values["a"] = 1
    history.record()
    doc.values["a"] = 5

    history.reset()
    assert history.can_undo is False
    assert history.can_redo is False
    assert history.depth == 0

    doc.values["a"] = 6
    history.record()
    history.undo()
    assert doc.values["a"] == 5  # back to the new baseline, not the old history


def test_uncomparable_state_is_treated_as_changed(clock):
    """A snapshot whose == does not yield a bool must not break recording."""

    class Weird:
        def __eq__(self, other):
            raise ValueError("ambiguous")

    states = [Weird(), Weird(), Weird()]
    pos = {"i": 0}
    history = History(lambda: states[pos["i"]], lambda s: None, clock=clock)

    pos["i"] = 1
    history.record("weird")
    assert history.depth == 1
