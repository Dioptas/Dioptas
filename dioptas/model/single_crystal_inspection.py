# SPDX-License-Identifier: MIT
"""Read-only inspection of existing cell assignments and prediction snapshots."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SpotCellDetails:
    model: str
    indexed: bool | None = None
    hkl: tuple | None = None
    residual: tuple | None = None  # calculated minus measured x/y/omega, px/px/deg
    note: str = ""


def spot_cell_details(
    positions,
    track,
    *,
    cells=None,
    selection=None,
    ranked=None,
    setting_index=None,
    refinement=None,
    refined=True,
):
    """Inspect frozen assignments; never reassign, fit, or alter cell rankings.

    Indexed means membership in the selected snapshot's indexed/eligible set.
    Filtered-out tracks are unassessed, rather than failed indexing attempts.
    Residuals use the linked signal-weighted centroid, as in positional fitting.
    """
    predicted = None
    if ranked is not None and setting_index is not None:
        fit = ranked.comparison.settings[setting_index]
        rank = next(
            r for r in ranked.comparison.ranking if r.setting_index == setting_index
        )
        name = f"Rank {rank.rank} · {fit.setting.symbol} · {'fitted' if refined else 'initial'}"
        if not np.isfinite(fit.training_score):
            return SpotCellDetails(name, note="Selected cell has an invalid fit.")
        ids, hkl, indexed = ranked.track_ids, fit.hkl, fit.eligible
        observed = ranked.observed
        geometry = ranked.geometry
        basis = (
            fit.reciprocal_basis
            if refined
            else np.linalg.inv(fit.setting.direct_basis).T
        )
    elif refinement is not None:
        fit = refinement.refinement
        name = f"Candidate {refinement.metadata['candidate_index'] + 1} · {'refined' if refined else 'initial'}"
        ids, hkl, indexed = refinement.track_ids, fit.hkl, fit.eligible
        observed = fit.observed
        predicted = fit.predictions if refined else fit.initial_predictions
    elif cells is not None and selection is not None:
        sign, number = selection
        candidate = next(r[2] for r in cells.reports if r[0] == sign).candidates[number]
        name = f"Candidate {number + 1} · axis {sign:+d} · indexed model"
        ids, hkl, indexed = cells.track_ids, candidate.hkl, candidate.indexed
        observed = positions.table.values[ids, :3]
        snapshot = next(m for m in cells.metadata["geometry"] if m["axis_sign"] == sign)
        geometry = snapshot
        basis = np.linalg.inv(candidate.direct_basis).T
    else:
        return SpotCellDetails("No cell selected", note="Find or select a cell first.")
    matches = np.flatnonzero(ids == track)
    if not len(matches):
        return SpotCellDetails(name, note="Excluded from cell search.")
    i = int(matches[0])
    if not indexed[i]:
        return SpotCellDetails(name, False, note="No accepted assignment for this cell.")
    assignment = tuple(map(int, hkl[i]))
    if predicted is None:
        from phasesmith.experimental.prediction import predict_spots
        from phasesmith.experimental.reciprocal import PanelGeometry

        if isinstance(geometry, dict):
            geometry = PanelGeometry(
                np.asarray(geometry["vectors"]), geometry["wavelength_angstrom"]
            )
        prediction = predict_spots(
            hkl[i : i + 1], basis, geometry, observed[i : i + 1, 2]
        )
        value, flag = prediction.values[0], prediction.flags[0]
    else:
        value, flag = predicted.values[i], predicted.flags[i]
    if flag or not np.isfinite(value).all():
        return SpotCellDetails(
            name, True, assignment, note="No valid predicted detector crossing."
        )
    return SpotCellDetails(
        name, True, assignment, tuple(map(float, value - observed[i]))
    )
