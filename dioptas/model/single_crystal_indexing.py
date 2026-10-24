# SPDX-License-Identifier: MIT
"""Opt-in geometry translation and blind lattice proposals. No material inputs."""

from dataclasses import asdict, dataclass
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def geometry_from_poni(
    filename, *, axis_sign, shape, original_rows=False, transformations=()
):
    """Snapshot pyFAI's own pixel geometry in a right-handed (1,2,3) basis.

    Legacy Dioptas PONI normally describes vertically flipped displayed rows.
    Modern raw-array PONI requires original_rows=True. Explicitly undo every
    subsequent Dioptas flip/quarter turn. Reject non-affine detector distortion.
    """
    import pyFAI
    from phasesmith.experimental.reciprocal import PanelGeometry

    if axis_sign not in (-1, 1):
        raise ValueError("Axis sign must be +1 or -1.")
    ai = pyFAI.load(str(filename))
    if ai.wavelength is None or ai.wavelength <= 0:
        raise ValueError("Calibration must contain a positive wavelength.")
    if len(shape) != 2 or any(int(v) != v or v < 2 for v in shape):
        raise ValueError("Detector image shape must contain two dimensions >=2.")
    h, w = map(int, shape)
    # Work backwards from the actual displayed image to the calibration image.
    matrix = np.eye(3)
    for name in reversed(transformations):
        if name == "flipud":
            inverse = np.array([[1, 0, 0], [0, -1, h - 1], [0, 0, 1]])
        elif name == "fliplr":
            inverse = np.array([[-1, 0, w - 1], [0, 1, 0], [0, 0, 1]])
        elif name == "rotate_matrix_p90":
            inverse = np.array([[0, -1, h - 1], [1, 0, 0], [0, 0, 1]])
            h, w = w, h
        elif name == "rotate_matrix_m90":
            inverse = np.array([[0, 1, 0], [-1, 0, w - 1], [0, 0, 1]])
            h, w = w, h
        else:
            raise ValueError(f"Unsupported image transform: {name}")
        matrix = inverse @ matrix
    if original_rows:
        matrix = np.array([[1, 0, 0], [0, -1, h - 1], [0, 0, 1]]) @ matrix
    xy = np.array(
        [
            [0, 0],
            [1, 0],
            [0, 1],
            [shape[1] - 1, shape[0] - 1],
            [(shape[1] - 1) / 2, (shape[0] - 1) / 2],
        ],
        dtype=float,
    )
    mapped = np.c_[xy, np.ones(len(xy))] @ matrix.T
    z, p1, p2 = ai.calc_pos_zyx(d1=mapped[:, 1], d2=mapped[:, 0], use_cython=False)
    lab = np.column_stack([p1, p2, z])
    origin, fast, slow = lab[0], lab[1] - lab[0], lab[2] - lab[0]
    predicted = origin + xy[:, :1] * fast + xy[:, 1:2] * slow
    if (
        not np.allclose(predicted, lab, atol=1e-9, rtol=1e-8)
        or ai.detector.splinefile
        or not ai.detector.IS_FLAT
        or not ai.detector.uniform_pixel
    ):
        raise ValueError(
            "This experimental geometry supports affine planar detectors only."
        )
    geometry = PanelGeometry(
        np.array([origin, fast, slow, [0, 0, 1], [axis_sign, 0, 0]]),
        ai.wavelength * 1e10,
    )
    metadata = dict(
        calibration_file=str(Path(filename).resolve()),
        calibration_sha256=hashlib.sha256(Path(filename).read_bytes()).hexdigest(),
        original_rows=bool(original_rows),
        transformations=list(transformations),
        image_to_calibration=matrix.tolist(),
        vectors=geometry.vectors.tolist(),
        wavelength_angstrom=geometry.wavelength,
        axis_sign=axis_sign,
        axis_convention="right-handed pyFAI (1=vertical,2=horizontal,3=beam); omega degrees",
        limitations="planar affine detector; no parallax or spatial-distortion correction",
    )
    return geometry, metadata


@dataclass(frozen=True)
class CellSearchResult:
    reports: tuple  # (axis sign, ReciprocalPositions, IndexingResult)
    track_ids: np.ndarray
    metadata: dict


def find_cells(positions, geometries, *, options=None, backend=None):
    from phasesmith.experimental.reciprocal import correct_positions
    from phasesmith.experimental.indexing import find_lattices, IndexingOptions
    from phasesmith import _core
    from phasesmith.experimental import indexing, reciprocal

    from phasesmith.experimental import grains

    backend = backend or (
        "fft_grains"
        if isinstance(options, grains.GrainSearchOptions)
        else "compact_fft"
    )
    if backend == "fft_grains":
        options = options or grains.GrainSearchOptions()
        search_function = grains.find_grains
    elif backend == "compact_fft":
        options = options or IndexingOptions()
        search_function = find_lattices
    else:
        raise ValueError("Unknown experimental cell search backend.")
    table = positions.table
    start, end = table.frame_ranges.T
    # Entire five-frame blocks and whole linked spots stay in one partition.
    training = (start // 5) % 5 != 0
    same_partition = ((end - 1) // 5) % 5 == (start // 5) % 5
    count = table.column("n_observations")
    selection = (table.flags == 0) & (count <= 8) & same_partition
    corrected = [
        (sign, correct_positions(table, geometry), meta)
        for sign, geometry, meta in geometries
    ]
    # One identical position selection for both signs, avoiding sign-specific
    # cleaning that could bias their comparison.
    for _, result, _ in corrected:
        selection &= result.rms <= 0.03
    ids = np.flatnonzero(selection)
    if len(ids) < options.min_indexed + 5:
        raise ValueError("Too few unflagged, compact tracks for a blind cell search.")
    reports = tuple(
        (
            sign,
            result,
            search_function(
                result.points[ids], training=training[ids], options=options
            ),
        )
        for sign, result, _ in corrected
    )
    ids.flags.writeable = False
    metadata = dict(
        schema="dioptas.experimental.blind-cell.v2",
        backend=backend,
        input_positions=positions.metadata,
        geometry=[r[2] for r in corrected],
        options=asdict(options),
        selected_track_ids=(ids + 1).tolist(),
        filter="unflagged; <=8 observations; reciprocal RMS <=0.03 A^-1 in every tested sign",
        partition="five-frame blocks, every fifth block held out; crossing tracks excluded",
        q_convention="sample frame, inverse angstrom, no 2*pi; equal-observation track means",
        material_or_cell_priors=False,
        native_engine_sha256=hashlib.sha256(
            Path(_core.__file__).read_bytes()
        ).hexdigest(),
        python_algorithm_sha256=hashlib.sha256(
            Path(indexing.__file__).read_bytes()
            + Path(reciprocal.__file__).read_bytes()
            + Path(grains.__file__).read_bytes()
        ).hexdigest(),
        adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    return CellSearchResult(reports, ids, metadata)


def cell_summary(result):
    lines = ["Blind candidate cells · no material or symmetry supplied"]
    for sign, _, search in result.reports:
        lines.append(f"\nVertical axis sign {sign:+d}: {search.message}")
        for i, c in enumerate(search.candidates):
            cell = ", ".join(f"{v:.4f}" for v in c.cell)
            lines.append(
                f"{i + 1}. {'PASS' if c.accepted else 'REJECTED'} · a,b,c (Å), α,β,γ (°): {cell}\n"
                f"V={c.volume:.2f} Å³ · training {c.training_fraction:.1%} · "
                f"held out {np.count_nonzero(c.indexed & ~search.training)}/{c.validation_count} "
                f"({c.validation_fraction:.1%}) · "
                f"control ≤{c.null_fraction:.1%}"
            )
    lines.append(
        "\nSize-reduced cell proposals; primitivity and space group are unproven. "
        "A dominant lattice is not a chemical identification."
    )
    return "\n".join(lines)


def export_cells(result, filename):
    """JSON audit and one position/assignment CSV for every returned candidate."""
    path = Path(filename).with_suffix(".json")
    metadata = dict(result.metadata, summary=cell_summary(result), reports=[])
    paths = [path]
    for sign, corrected, search in result.reports:
        candidates = []
        for c in search.candidates:
            candidates.append(
                dict(
                    cell=c.cell.tolist(),
                    direct_basis=c.direct_basis.tolist(),
                    volume=c.volume,
                    training_fraction=c.training_fraction,
                    validation_fraction=c.validation_fraction,
                    null_fraction=c.null_fraction,
                    accepted=c.accepted,
                    training_count=int(np.count_nonzero(c.indexed & search.training)),
                    heldout_count=int(np.count_nonzero(c.indexed & ~search.training)),
                )
            )
        metadata["reports"].append(
            dict(
                axis_sign=sign,
                method=search.method,
                message=search.message,
                candidates=candidates,
                diagnostics=list(search.diagnostics),
            )
        )
        for number, best in enumerate(search.candidates, 1):
            suffix = "" if number == 1 else f"_candidate_{number:02d}"
            csv_path = path.with_name(path.stem + f"_axis_{sign:+d}{suffix}.csv")
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "track_id",
                        "qx",
                        "qy",
                        "qz",
                        "q_rms",
                        "training",
                        "h",
                        "k",
                        "l",
                        "indexed",
                        "residual_A^-1",
                    ]
                )
                for i, track in enumerate(result.track_ids):
                    writer.writerow(
                        [
                            track + 1,
                            *corrected.points[track],
                            corrected.rms[track],
                            bool(search.training[i]),
                            *best.hkl[i],
                            bool(best.indexed[i]),
                            best.residual[i],
                        ]
                    )
            paths.append(csv_path)
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return tuple(paths)
