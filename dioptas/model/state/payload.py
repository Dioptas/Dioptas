# SPDX-License-Identifier: MIT

"""Content-addressed storage for owned binary payloads.

The state layer distinguishes three kinds of data. Structured settings live in
params dataclasses. *External* payloads (the diffraction image) are re-readable
from a source file, so their state is the path and the pixels are a cache.
This module is for the third kind: *owned* payloads — binary data that cannot
be reproduced from anywhere, like the user-drawn mask or an overlay created
from the pattern that happened to be on screen. For those the bytes themselves
are the state.

The design is git's: a tree of small values referencing immutable blobs by
content hash. Params fields hold payload *ids* (plain strings, so they are
JSON-serializable and comparable like any other field); the store maps ids to
the encoded bytes. What falls out of content addressing, rather than being
built:

- structural sharing between undo snapshots — an unchanged mask contributes
  the same id string to every snapshot, never a second copy;
- deduplication — two configurations holding identical masks store one blob;
- cheap equality — comparing snapshots compares strings, never arrays (numpy
  ``==`` inside a snapshot is the failure mode the id indirection removes).

Payloads are immutable; ``array()`` returns a fresh array per call, so callers
may freely mutate what they get back (the mask model draws into its working
array in place). The store grows monotonically between sweeps; the recorder
sweeps it against the ids reachable from live state and history whenever the
history changes.
"""

from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass

import numpy as np

__all__ = ["Payload", "PayloadStore"]


@dataclass(frozen=True)
class Payload:
    """An immutable encoded array. Created through :meth:`PayloadStore.put`."""

    id: str
    data: bytes
    dtype: str
    shape: tuple[int, ...]
    #: bool arrays are stored bit-packed (numpy spends a byte per boolean;
    #: packing divides the mask payload by eight before compression)
    bit_packed: bool

    def array(self) -> np.ndarray:
        """Decodes into a fresh, writable array.

        Fresh on purpose: the caller may draw into it (the mask model mutates
        its working array in place), which must never reach back into the
        stored bytes or into other holders of the same payload.
        """
        raw = zlib.decompress(self.data)
        if self.bit_packed:
            size = int(np.prod(self.shape))
            bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))
            return bits[:size].reshape(self.shape).astype(bool)
        return np.frombuffer(raw, dtype=self.dtype).reshape(self.shape).copy()

    @property
    def nbytes_stored(self) -> int:
        return len(self.data)


def _encode(array: np.ndarray) -> tuple[bytes, bool]:
    """Canonical raw encoding of an array (before compression)."""
    if array.dtype == bool:
        return np.packbits(array).tobytes(), True
    return np.ascontiguousarray(array).tobytes(), False


class PayloadStore:
    """Maps content ids to :class:`Payload` objects.

    ``put`` is the only way in; it computes the id from the content, so the
    same array can never be stored twice and an id uniquely names its bytes
    for the lifetime of the store. Ids are only meaningful within one store
    (or one project file written and read consistently) — they are not a
    stable cross-version format.
    """

    def __init__(self) -> None:
        self._payloads: dict[str, Payload] = {}

    def put(self, array: np.ndarray) -> str:
        """Stores an array (deduplicated) and returns its content id."""
        raw, bit_packed = _encode(array)
        digest = hashlib.sha1(
            f"{array.dtype.str}:{array.shape}:".encode() + raw
        ).hexdigest()
        if digest not in self._payloads:
            self._payloads[digest] = Payload(
                id=digest,
                # level 1: cheapest setting, and these payloads (masks
                # especially) are redundant enough that higher levels buy
                # ~1% for 4x the CPU (measured for the 0.8.7 mask storage)
                data=zlib.compress(raw, 1),
                dtype=array.dtype.str,
                shape=tuple(array.shape),
                bit_packed=bit_packed,
            )
        return digest

    def get(self, payload_id: str) -> Payload:
        return self._payloads[payload_id]

    def array(self, payload_id: str) -> np.ndarray:
        return self._payloads[payload_id].array()

    def __contains__(self, payload_id: str) -> bool:
        return payload_id in self._payloads

    def __len__(self) -> int:
        return len(self._payloads)

    def sweep(self, live: set[str]) -> int:
        """Drops every payload whose id is not in *live*; returns the count.

        The caller owns liveness: the recorder passes the union of ids
        reachable from the current state and every held history snapshot.
        """
        dead = [pid for pid in self._payloads if pid not in live]
        for pid in dead:
            del self._payloads[pid]
        return len(dead)
