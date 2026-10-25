# SPDX-License-Identifier: MIT
"""Display snapshots; physical reciprocal conversion remains in PhaseSmith."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ReciprocalSnapshot:
    name: str
    track_ids: np.ndarray
    track_q: np.ndarray
    track_hkl: np.ndarray
    observation_tracks: np.ndarray
    observation_frames: np.ndarray
    observation_q: np.ndarray
    observation_hkl: np.ndarray
    status: np.ndarray  # per original track: 0 unindexed, 1 indexed, 2 unassessed
    omitted_tracks: int
    reciprocal_basis: np.ndarray

    def points(self, observations=False, fractional=True):
        if observations:
            return (
                self.observation_hkl if fractional else self.observation_q,
                self.observation_tracks,
                self.observation_frames,
                self.status[self.observation_tracks],
            )
        return (
            self.track_hkl if fractional else self.track_q,
            self.track_ids,
            np.full(len(self.track_ids), -1, dtype=np.int64),
            self.status[self.track_ids],
        )


def reciprocal_snapshot(positions, ranked, setting_index):
    """Keep every finite measured position, including tracks filtered from fitting.

    PhaseSmith supplies q in the sample frame, |q|=1/d. Cell-coordinate plotting
    expresses these same vectors in the selected reciprocal basis B: q=h B.
    Fractional h is never rounded or used to change frozen indexing membership.
    Track coordinates use the original weighted x/y/omega centroids, matching
    the cell comparison. The observation view corrects each exposure separately.
    """
    from phasesmith.experimental.reciprocal import reciprocal_vectors

    fit = ranked.comparison.settings[setting_index]
    if not np.isfinite(fit.training_score):
        raise ValueError("Select a cell with a valid fitted model.")
    rank = next(
        r for r in ranked.comparison.ranking if r.setting_index == setting_index
    )
    values = positions.table.values[:, :3]
    ids = np.flatnonzero(np.isfinite(values).all(axis=1))
    q = reciprocal_vectors(values[ids], ranked.geometry)
    observations = positions.table.observations
    observations = observations[np.isfinite(observations).all(axis=1)]
    obs_ids = observations[:, 0].astype(np.int64)
    frames = observations[:, 1].astype(np.int64)
    if (
        np.any(obs_ids != observations[:, 0])
        or np.any(obs_ids < 0)
        or np.any(obs_ids >= len(values))
        or np.any(frames != observations[:, 1])
        or np.any(frames < 0)
    ):
        raise ValueError("Invalid track/frame identifiers in reciprocal observations.")
    observation_q = reciprocal_vectors(observations[:, 2:5], ranked.geometry)
    # This is a display-basis transformation, not a fresh indexing operation.
    h = np.linalg.solve(fit.reciprocal_basis.T, q.T).T
    observation_h = np.linalg.solve(fit.reciprocal_basis.T, observation_q.T).T
    status = np.full(len(values), 2, dtype=np.uint8)
    status[ranked.track_ids] = fit.eligible.astype(np.uint8)
    arrays = (ids, q, h, obs_ids, frames, observation_q, observation_h, status)
    arrays = tuple(np.ascontiguousarray(a) for a in arrays)
    for a in arrays:
        a.flags.writeable = False
    basis = np.array(fit.reciprocal_basis, copy=True)
    basis.flags.writeable = False
    return ReciprocalSnapshot(
        f"Rank {rank.rank} · {fit.setting.symbol} · lattice {ranked.selection[1] + 1} · axis {ranked.selection[0]:+d}",
        *arrays,
        len(values) - len(ids),
        basis,
    )
