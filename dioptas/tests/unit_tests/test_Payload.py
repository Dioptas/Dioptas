# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from dioptas.model.state import PayloadStore


@pytest.fixture
def store():
    return PayloadStore()


# ---------------------------------------------------------------------------
# round trips
# ---------------------------------------------------------------------------


def test_bool_array_round_trips_exactly(store):
    mask = np.zeros((211, 173), dtype=bool)  # deliberately not byte-aligned
    mask[::7, ::3] = True

    restored = store.array(store.put(mask))
    assert np.array_equal(restored, mask)
    assert restored.dtype == bool
    assert restored.shape == mask.shape


def test_float_array_round_trips_exactly(store):
    data = np.linspace(-1.5, 300.0, 999).reshape(3, 333)
    restored = store.array(store.put(data))
    assert np.array_equal(restored, data)
    assert restored.dtype == data.dtype


def test_integer_dtypes_are_preserved(store):
    for dtype in (np.uint16, np.int32, np.float32):
        data = np.arange(100, dtype=dtype)
        restored = store.array(store.put(data))
        assert restored.dtype == dtype
        assert np.array_equal(restored, data)


def test_non_contiguous_input_is_handled(store):
    data = np.arange(100.0).reshape(10, 10)[:, ::2]  # a strided view
    restored = store.array(store.put(data))
    assert np.array_equal(restored, data)


# ---------------------------------------------------------------------------
# content addressing
# ---------------------------------------------------------------------------


def test_identical_content_stores_once(store):
    a = np.ones((64, 64), dtype=bool)
    b = np.ones((64, 64), dtype=bool)  # distinct object, same content

    assert store.put(a) == store.put(b)
    assert len(store) == 1


def test_different_content_gets_different_ids(store):
    a = np.zeros((64, 64), dtype=bool)
    b = np.ones((64, 64), dtype=bool)
    assert store.put(a) != store.put(b)


def test_same_bytes_different_shape_are_distinct(store):
    """A (2, 8) and an (8, 2) of the same values are different payloads."""
    a = np.arange(16.0).reshape(2, 8)
    b = np.arange(16.0).reshape(8, 2)
    assert store.put(a) != store.put(b)


def test_mutating_the_source_after_put_does_not_change_the_payload(store):
    data = np.zeros((32, 32), dtype=bool)
    payload_id = store.put(data)
    data[:] = True
    assert store.array(payload_id).sum() == 0


def test_returned_arrays_are_independent(store):
    """array() hands out fresh arrays a caller may draw into."""
    payload_id = store.put(np.zeros((32, 32), dtype=bool))
    first = store.array(payload_id)
    first[:] = True  # must be writable, and must not leak back
    assert store.array(payload_id).sum() == 0


# ---------------------------------------------------------------------------
# storage properties
# ---------------------------------------------------------------------------


def test_masks_are_stored_bit_packed_and_compressed(store):
    mask = np.zeros((512, 512), dtype=bool)
    mask[100:150, 100:150] = True

    payload = store.get(store.put(mask))
    assert payload.bit_packed is True
    assert payload.nbytes_stored < mask.nbytes / 8


# ---------------------------------------------------------------------------
# sweeping
# ---------------------------------------------------------------------------


def test_sweep_drops_unreferenced_and_keeps_referenced(store):
    keep = store.put(np.ones(10, dtype=bool))
    drop = store.put(np.zeros(10, dtype=bool))

    assert store.sweep({keep}) == 1
    assert keep in store
    assert drop not in store


def test_sweep_with_everything_live_drops_nothing(store):
    ids = {store.put(np.full(5, v)) for v in range(4)}
    assert store.sweep(ids) == 0
    assert len(store) == 4
