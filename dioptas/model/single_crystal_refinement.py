# SPDX-License-Identifier: MIT
"""Fixed-instrument, position-only crystal refinement and prediction snapshots."""

import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class PositionRefinement:
    refinement: object
    initial_scan: object
    refined_scan: object
    track_ids: np.ndarray
    metadata: dict


def preferred_candidate(cells, selection=None):
    if selection is not None:
        sign, index = selection
        search = next((r[2] for r in cells.reports if r[0] == sign), None)
        if search is None or not 0 <= index < len(search.candidates):
            raise ValueError("Selected candidate is no longer available.")
        candidate = search.candidates[index]
        if not candidate.accepted:
            raise ValueError("Selected candidate did not pass the held-out checks.")
        return sign, index, search, candidate
    choices = [
        (c.training_fraction, -c.volume, sign, i, search, c)
        for sign, _, search in cells.reports
        for i, c in enumerate(search.candidates)
    ]
    if not choices:
        raise ValueError("Find a candidate cell first.")
    choice = max(choices, key=lambda c: c[:2])
    if not choice[-1].accepted:
        raise ValueError(
            "The strongest training candidate did not pass the blind cell checks."
        )
    return choice[2:]


def detector_qmax(geometry, shape):
    """Cover a forward flat panel whose direct beam falls within its footprint.

    For other arrangements use the conservative full Ewald diameter. Budgets
    may then require the caller to narrow the resolution range explicitly.
    """
    from phasesmith.experimental.reciprocal import reciprocal_vectors

    height, width = shape
    corners = np.array(
        [
            [-0.5, -0.5, 0],
            [width - 0.5, -0.5, 0],
            [-0.5, height - 0.5, 0],
            [width - 0.5, height - 0.5, 0],
        ]
    )
    origin, fast, slow, beam = geometry.vectors[:4]
    normal = np.cross(fast, slow)
    denominator = np.dot(normal, beam)
    if abs(denominator) < 1e-20:
        return 2 / geometry.wavelength
    intersection = beam * np.dot(normal, origin) / denominator
    xy = np.linalg.lstsq(
        np.column_stack([fast, slow]), intersection - origin, rcond=None
    )[0]
    rays = origin + corners[:, :1] * fast + corners[:, 1:2] * slow
    if not (-0.5 <= xy[0] <= width - 0.5 and -0.5 <= xy[1] <= height - 0.5) or np.any(
        rays @ beam <= 0
    ):
        return 2 / geometry.wavelength
    return float(np.max(np.linalg.norm(reciprocal_vectors(corners, geometry), axis=1)))


def refine_positions(
    positions,
    cells,
    image_shape,
    *,
    progress=None,
    symmetry="triclinic",
    selection=None,
):
    from phasesmith.experimental.reciprocal import PanelGeometry
    from phasesmith.experimental.prediction import (
        refine_crystal,
        predict_scan,
        orientation_matrix,
        RefinementOptions,
    )
    from phasesmith.experimental import prediction
    from phasesmith import _core

    sign, candidate_index, search, candidate = preferred_candidate(cells, selection)
    snapshot = next(m for m in cells.metadata["geometry"] if m["axis_sign"] == sign)
    geometry = PanelGeometry(
        np.asarray(snapshot["vectors"]), snapshot["wavelength_angstrom"]
    )
    ids = cells.track_ids
    observed = positions.table.values[ids, :3]
    basis = np.linalg.inv(candidate.direct_basis).T
    setting_metadata = None
    hkl = candidate.hkl
    if symmetry == "orthorhombic":
        from phasesmith.experimental.orthorhombic import find_orthorhombic_settings

        settings = find_orthorhombic_settings(candidate.direct_basis)
        if not settings:
            raise ValueError(
                "No orthorhombic setting within 0.3° in the bounded integer-axis search."
            )
        setting = settings[0]
        hkl = hkl @ setting.transform.T
        basis = np.linalg.inv(setting.direct_basis).T
        setting_metadata = dict(
            centring=setting.centring,
            lattice_index=setting.index,
            transform=setting.transform.tolist(),
            max_angle_deviation_deg=setting.max_angle_deviation,
            candidates=len(settings),
            angle_tolerance_deg=0.3,
            coefficient_limit=3,
            selection="smallest lattice index, then minimum maximum angular deviation; no validation selection",
            interpretation="metric candidate preserving the input lattice, not a proven Bravais class or space group",
        )
    options = RefinementOptions()
    result = refine_crystal(
        observed,
        hkl,
        basis,
        geometry,
        training=search.training,
        eligible=candidate.indexed,
        options=options,
        progress=progress,
        symmetry=symmetry,
    )
    if progress:
        progress(options.max_iterations, options.max_iterations)
    qmax = detector_qmax(geometry, image_shape)
    bounds = positions.table.omega_bounds
    lattice_transform = (
        None
        if setting_metadata is None
        else np.asarray(setting_metadata["transform"], dtype=np.int64)
    )
    initial_scan = predict_scan(
        basis,
        geometry,
        bounds,
        tuple(map(int, image_shape)),
        qmax=qmax,
        lattice_transform=lattice_transform,
    )
    refined_scan = predict_scan(
        result.reciprocal_basis,
        geometry,
        bounds,
        tuple(map(int, image_shape)),
        qmax=qmax,
        lattice_transform=lattice_transform,
    )
    initial_orientation = orientation_matrix(basis)
    final_orientation = orientation_matrix(result.reciprocal_basis)
    angle = np.rad2deg(
        np.arccos(
            np.clip(
                (np.trace(final_orientation @ initial_orientation.T) - 1) / 2, -1, 1
            )
        )
    )
    track_ids = np.array(ids, copy=True)
    track_ids.flags.writeable = False
    metadata = dict(
        schema="dioptas.experimental.positional-refinement.v1",
        input_cells=cells.metadata,
        geometry=snapshot,
        image_shape=list(image_shape),
        omega_bounds=bounds.tolist(),
        axis_sign=sign,
        candidate_index=candidate_index,
        selection=(
            "explicit candidate selection; provisional pass required"
            if selection is not None
            else "largest training indexed fraction; volume breaks ties; provisional pass required"
        ),
        observed="one original detected-signal-weighted x,y,omega centroid per linked track",
        fixed_instrument=True,
        metric_constraint=symmetry,
        orthorhombic_setting=setting_metadata,
        material_or_cell_priors=False,
        options=asdict(options),
        initial_orientation=initial_orientation.tolist(),
        refined_orientation=final_orientation.tolist(),
        orientation_change_deg=float(angle),
        qmax_A_inverse=qmax,
        predictions="HKLs of the input reciprocal lattice crossing the panel within exposure; no intensity or space-group extinction model",
        native_engine_sha256=hashlib.sha256(
            Path(_core.__file__).read_bytes()
        ).hexdigest(),
        python_algorithm_sha256=hashlib.sha256(
            Path(prediction.__file__).read_bytes()
        ).hexdigest(),
        adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    return PositionRefinement(result, initial_scan, refined_scan, track_ids, metadata)


def refinement_summary(result):
    from phasesmith.experimental.indexing import cell_parameters

    fit = result.refinement
    before = cell_parameters(np.linalg.inv(fit.initial_basis).T)
    lines = [
        f"Position refinement · vertical sign {result.metadata['axis_sign']:+d}",
        "Initial a,b,c (Å), α,β,γ (°): " + ", ".join(f"{v:.4f}" for v in before),
        "Refined a,b,c (Å), α,β,γ (°): " + ", ".join(f"{v:.4f}" for v in fit.cell),
        f"Orientation change: {result.metadata['orientation_change_deg']:.4f}° · instrument fixed",
    ]
    for label, metrics in fit.metrics.items():
        if label == "validation_improved":
            continue
        a, b = metrics["before"], metrics["after"]
        lines.append(
            f"{label.title()} ({metrics['count']}): detector RMS {a['rms_xy']:.3f} → {b['rms_xy']:.3f} px; "
            f"omega RMS {a['rms_omega']:.4f} → {b['rms_omega']:.4f}°"
        )
    setting = result.metadata.get("orthorhombic_setting")
    if setting:
        lines.insert(
            0,
            f"Orthorhombic metric candidate · {setting['centring']} setting · lattice index {setting['lattice_index']}",
        )
        lines.insert(
            1,
            f"Initial angular departure ≤{setting['max_angle_deviation_deg']:.4f}°; fit fixes all angles at 90°.",
        )
        lines.append("Integer setting transform (rows): " + str(setting["transform"]))
        lines.append(
            "Bounded metric search only: primitive lattice and space group remain unproven."
        )
    if fit.metrics["validation_improved"]:
        lines.append("The combined held-out positional residual improved.")
    else:
        lines.append(
            "Held-out residual did not improve. Initial model remains the default overlay; inspect both."
        )
    lines.append(
        "No space group, chemical identity or intensity model assigned. Loss scales are not calibrated uncertainties."
    )
    return "\n".join(lines)


def export_refinement(result, filename):
    path = Path(filename).with_suffix(".json")
    fit = result.refinement
    centroid_path = path.with_name(path.stem + "_centroids.csv")
    prediction_path = path.with_name(path.stem + "_predictions.csv")
    with centroid_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "track_id",
                "h",
                "k",
                "l",
                "training",
                "eligible",
                "fit",
                "observed_x",
                "observed_y",
                "observed_omega",
                "initial_x",
                "initial_y",
                "initial_omega",
                "refined_x",
                "refined_y",
                "refined_omega",
                "dx_initial",
                "dy_initial",
                "domega_initial",
                "dx_refined",
                "dy_refined",
                "domega_refined",
                "initial_flags",
                "refined_flags",
            ]
        )
        for i, track in enumerate(result.track_ids):
            a, b, obs = (
                fit.initial_predictions.values[i],
                fit.predictions.values[i],
                fit.observed[i],
            )
            writer.writerow(
                [
                    int(track) + 1,
                    *fit.hkl[i],
                    bool(fit.training[i]),
                    bool(fit.eligible[i]),
                    bool(fit.fit_mask[i]),
                    *obs,
                    *a,
                    *b,
                    *(a - obs),
                    *(b - obs),
                    int(fit.initial_predictions.flags[i]),
                    int(fit.predictions.flags[i]),
                ]
            )
    with prediction_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "frame_index", "h", "k", "l", "x", "y", "omega"])
        for name, predictions in [
            ("initial", result.initial_scan),
            ("refined", result.refined_scan),
        ]:
            for frame, hkl, values in zip(
                predictions.frame_indices, predictions.hkl, predictions.values
            ):
                writer.writerow([name, int(frame), *hkl, *values])
    record = dict(
        result.metadata,
        summary=refinement_summary(result),
        metrics=fit.metrics,
        initial_reciprocal_basis=fit.initial_basis.tolist(),
        refined_reciprocal_basis=fit.reciprocal_basis.tolist(),
        direct_basis=fit.direct_basis.tolist(),
        refined_cell=fit.cell.tolist(),
        converged=fit.converged,
        training_cost_history=fit.history.tolist(),
        eligible=int(fit.eligible.sum()),
        fitted=int(fit.fit_mask.sum()),
        initial_predictions=len(result.initial_scan.values),
        refined_predictions=len(result.refined_scan.values),
    )

    # Invalid held-out predictions must remain explicit JSON data, not NaN/Inf.
    def finite_json(value):
        if isinstance(value, dict):
            return {k: finite_json(v) for k, v in value.items()}
        if isinstance(value, list):
            return [finite_json(v) for v in value]
        if isinstance(value, float) and not np.isfinite(value):
            return str(value)
        return value

    path.write_text(
        json.dumps(finite_json(record), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path, centroid_path, prediction_path
