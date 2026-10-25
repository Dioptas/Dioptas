# SPDX-License-Identifier: MIT
"""Experimental ranked Bravais settings and read-only positional previews.

PhaseSmith owns the comparison and fits. This adapter retains the selected blind
lattice/axis and maps GUI selections to stable PhaseSmith fit-pool indices.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .single_crystal_refinement import (
    PositionRefinement,
    preferred_candidate,
    detector_qmax,
)


@dataclass(frozen=True)
class RankedCells:
    comparison: object
    track_ids: np.ndarray
    observed: np.ndarray
    geometry: object
    selection: tuple
    metadata: dict


def rank_cells(positions, cells, *, selection=None, options=None):
    from phasesmith.experimental.cell_comparison import (
        compare_cells,
        CellComparisonOptions,
    )
    from phasesmith.experimental.reciprocal import PanelGeometry, reciprocal_vectors

    sign, candidate_index, search, candidate = preferred_candidate(cells, selection)
    snapshot = next(m for m in cells.metadata["geometry"] if m["axis_sign"] == sign)
    geometry = PanelGeometry(
        np.asarray(snapshot["vectors"]), snapshot["wavelength_angstrom"]
    )
    ids = np.array(cells.track_ids, dtype=np.int64, copy=True)
    observed = np.array(positions.table.values[ids, :3], copy=True)
    # The q membership and subsequent detector fit use the same weighted centroid.
    q = reciprocal_vectors(observed, geometry)
    options = options or CellComparisonOptions(max_subcell_index=8)
    result = compare_cells(
        q,
        candidate.direct_basis,
        training=search.training,
        observed=observed,
        geometry=geometry,
        options=options,
    )
    ids.flags.writeable = observed.flags.writeable = False
    metadata = dict(
        schema="dioptas.experimental.ranked-cells.v1",
        input_cells=cells.metadata,
        geometry=snapshot,
        axis_sign=sign,
        candidate_index=candidate_index,
        options=asdict(options),
        material_or_cell_priors=False,
        interpretation="Ranked lattice metrics, not proven primitive cells or space groups",
        q_convention="q from the measured weighted x,y,omega centroids; inverse angstrom; no 2pi",
    )
    return RankedCells(
        result, ids, observed, geometry, (sign, candidate_index), metadata
    )


def preview_ranked_cell(result, positions, image_shape, setting_index):
    """Predict one already-fitted setting; never refit it or change its ranking."""
    from phasesmith.experimental.prediction import (
        CrystalRefinement,
        RefinementOptions,
        predict_spots,
        predict_scan,
        orientation_matrix,
        _statistics,
    )

    comparison = result.comparison
    if type(setting_index) is not int or not 0 <= setting_index < len(
        comparison.settings
    ):
        raise ValueError("Ranked cell is no longer available.")
    fit = comparison.settings[setting_index]
    if not np.isfinite(fit.training_score):
        raise ValueError(
            "This setting has an invalid training fit; inspect its diagnostics."
        )
    rank = next(r for r in comparison.ranking if r.setting_index == setting_index)
    before = np.linalg.inv(fit.setting.direct_basis).T
    initial = predict_spots(fit.hkl, before, result.geometry, result.observed[:, 2])
    final = predict_spots(
        fit.hkl, fit.reciprocal_basis, result.geometry, result.observed[:, 2]
    )
    opt = comparison.options
    scales = np.array([opt.xy_scale, opt.xy_scale, opt.omega_scale])
    metrics = _statistics(
        result.observed,
        initial.values,
        final.values,
        comparison.training,
        fit.eligible,
        scales,
    )
    # Use the comparison's own statistics for invalid held-out crossings too.
    for label, recorded in [
        ("training", fit.training_metrics),
        ("validation", fit.validation_metrics),
    ]:
        metrics[label]["after"] = {k: v for k, v in recorded.items() if k != "count"}
    metrics["validation_improved"] = bool(
        metrics["validation"]["after"]["rms_scaled"]
        < metrics["validation"]["before"]["rms_scaled"]
    )
    refinement = CrystalRefinement(
        before,
        fit.reciprocal_basis,
        initial,
        final,
        result.observed,
        fit.hkl,
        comparison.training,
        fit.eligible,
        comparison.training & fit.eligible,
        fit.history,
        metrics,
        RefinementOptions(
            xy_scale=opt.xy_scale,
            omega_scale=opt.omega_scale,
            huber=opt.huber,
            max_iterations=opt.max_iterations,
        ),
        fit.converged,
    )
    qmax = detector_qmax(result.geometry, image_shape)
    kwargs = dict(qmax=qmax, lattice_transform=fit.setting.transform)
    bounds = positions.table.omega_bounds
    shape = tuple(map(int, image_shape))
    initial_scan = predict_scan(before, result.geometry, bounds, shape, **kwargs)
    final_scan = predict_scan(
        fit.reciprocal_basis, result.geometry, bounds, shape, **kwargs
    )
    orientation0, orientation1 = (
        orientation_matrix(before),
        orientation_matrix(fit.reciprocal_basis),
    )
    angle = np.rad2deg(
        np.arccos(np.clip((np.trace(orientation1 @ orientation0.T) - 1) / 2, -1, 1))
    )
    metadata = dict(
        result.metadata,
        ranked_setting=dict(asdict(rank), symbol=fit.setting.symbol),
        setting_index=setting_index,
        metric_constraint=fit.setting.symbol,
        orthorhombic_setting=None,
        fixed_instrument=True,
        image_shape=list(shape),
        omega_bounds=bounds.tolist(),
        qmax_A_inverse=qmax,
        initial_orientation=orientation0.tolist(),
        refined_orientation=orientation1.tolist(),
        orientation_change_deg=float(angle),
        lattice_transform=fit.setting.transform.tolist(),
        selection="Explicit ranked setting; display its fitted model, no held-out selection or refitting",
        predictions="Selected reciprocal lattice only; no intensity or space-group extinction model",
    )
    return PositionRefinement(
        refinement, initial_scan, final_scan, result.track_ids, metadata
    )


def export_ranked_cells(result, filename):
    """Save all ranked rows and rejected primitive support without nonfinite JSON."""
    comparison = result.comparison
    record = dict(
        result.metadata,
        ranking=[asdict(r) for r in comparison.ranking],
        settings=[
            dict(
                setting_index=i,
                symbol=f.setting.symbol,
                cell=f.cell.tolist(),
                transform=f.setting.transform.tolist(),
                reciprocal_basis=f.reciprocal_basis.tolist(),
                training=f.training_metrics,
                validation=f.validation_metrics,
                training_score=f.training_score,
                converged=f.converged,
                status=f.status,
            )
            for i, f in enumerate(comparison.settings)
        ],
        primitive_hypotheses=[
            dict(
                id=p.id,
                index=p.index,
                cell=p.cell.tolist(),
                hnf=p.reciprocal_hnf.tolist(),
                supported=p.supported,
                reason=p.reason,
                retained_training=p.training_count,
                excluded_training=p.excluded_training,
                retained_validation=p.validation_count,
                excluded_validation=p.excluded_validation,
            )
            for p in comparison.primitives
        ],
    )

    def finite(value):
        if isinstance(value, dict):
            return {k: finite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [finite(v) for v in value]
        if isinstance(value, float) and not np.isfinite(value):
            return str(value)
        return value

    path = Path(filename).with_suffix(".json")
    path.write_text(
        json.dumps(finite(record), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return path
