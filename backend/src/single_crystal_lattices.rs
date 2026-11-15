//! Find lattices: PhaseSmith's multi-grain discovery
//! (`phasesmith_single_crystal::grains::find`) on the reciprocal spot cloud.
//!
//! PhaseSmith searches in rounds, each on the training spots no accepted
//! lattice explains yet, so later rounds find further grains in what the
//! earlier ones leave. It refines and reduces each candidate cell, refits all
//! lattices with exclusive spot ownership, and validates them on the withheld
//! fifth of the spots against rotated copies of them. "FFT" proposes cells
//! from the spots' Fourier periodicities; "Row search" (DAFi, Aslandukov et
//! al. 2022) from groups of spots on equally spaced reciprocal rows; "FFT +
//! row search" pools both and keeps the lattices that explain the spots best.
//!
//! Dioptas settings: every fifth spot withheld; the 64 bundled rotations
//! (`data/scxrd-null-rotations-v1.json`); 16 rotated copies to rank each
//! round's cells, preferring a smaller cell on the same spots; withheld
//! matches must sit near the nodes (3/4 within half the tolerance); up to
//! `2 · max_grains + 2` rounds, since a round's lattice can fail validation.
//! Dioptas adds the diamond-supercell filter (the anvils), the ordering, the
//! cap and the reduced cell shown.
use super::processing::{det, parameters};
use super::*;
use phasesmith_single_crystal::{grains, row_search, spots::SpotError};

/// Same lattice within refinement scatter (PhaseSmith's test).
pub(super) use grains::related;

/// Which search found a lattice. Older products carry no field: FFT. With
/// "FFT + row search" PhaseSmith pools both searches' cells and reports no
/// per-lattice origin, so those lattices are marked `Both`.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub(super) enum Found {
    #[default]
    Fft,
    Rows,
    Both,
}

/// `Config::max_grains`: default and upper limit.
pub(super) const MAX_GRAINS: usize = 20;
pub(super) fn default_grains() -> usize {
    5
}

/// `Config::lattice_method` values; the first is the default.
pub(super) const METHODS: [&str; 3] = ["both", "fft", "rows"];
pub(super) fn default_method() -> String {
    METHODS[0].into()
}

/// `Config::merge_angle`: default and upper limit (degrees).
pub(super) const MERGE_ANGLE_MAX: f64 = 5.;
pub(super) fn default_merge_angle() -> f64 {
    0.5
}
/// Cells of one crystal agree within this relative length and angle
/// (degrees) once one basis is mapped onto the other. Refinement scatter of
/// one grain is about 0.02 % and 0.02° (enstatite split: 0.03 %, 0.02°).
const MERGE_LENGTH: f64 = 0.005;
const MERGE_ANGLES: f64 = 0.5;
/// A merged lattice must index this share of the spots its parts indexed;
/// otherwise the parts are separate grains and stay apart.
pub(super) const MERGE_KEEP: f64 = 0.85;
/// Least-squares cycles of the merged refit, at twice and at the tolerance.
const REFIT_CYCLES: usize = 4;

/// A lattice merged from domains of one crystal: how many lattices it
/// replaces and the largest misorientation among them (degrees).
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Merged {
    pub domains: usize,
    pub angle: f64,
}

/// PhaseSmith's ownership ambiguity ratio (`grains::Options::default`).
pub(super) const AMBIGUITY: f64 = 0.8;
/// Rotated copies ranking each round's cells (`grains::Options::round_controls`).
const ROUND_CONTROLS: usize = 16;
/// Share of withheld matches within half the tolerance.
const MIN_TIGHT_FRACTION: f64 = 0.75;
/// Wall limit of the row grouping.
const ROW_SECONDS: f64 = 120.;
/// PhaseSmith's limits for a lattice to be validated at all.
const MIN_TRAIN: usize = 20;
const MIN_TEST: usize = 6;

fn null_rotations() -> Vec<M3> {
    serde_json::from_str(include_str!("../data/scxrd-null-rotations-v1.json"))
        .expect("bundled null rotations")
}
fn inv(a: M3) -> Option<M3> {
    fft::inverse_transpose(a).ok()
}
fn length(v: V3) -> f64 {
    fft::dot(v, v).sqrt()
}
/// `v` as a row vector times `a`.
fn row(v: V3, a: M3) -> V3 {
    std::array::from_fn(|j| (0..3).map(|k| v[k] * a[k][j]).sum())
}

/// PhaseSmith's selected row-search settings for sparse, noisy rows
/// (`tests/row_search_adaptive.rs`, `ROW_SEARCH_ALGORITHM.md`).
fn row_options() -> row_search::Options {
    row_search::Options {
        projection_grids: 4,
        phase_min_row: 3,
        relative_gap: true,
        naive_max_points: 2048,
        workers: crate::worker_pool::threads().clamp(1, 8),
        seconds: ROW_SECONDS,
        ..row_search::Options::default()
    }
}
fn options(config: &Config, cap: usize) -> grains::Options {
    let mut o = grains::Options::default();
    o.min_length = config.min_cell;
    o.max_length = config.max_cell;
    o.reciprocal_tolerance = config.tolerance;
    o.max_grains = (2 * cap + 2).min(40);
    o.round_controls = ROUND_CONTROLS;
    o.min_tight_fraction = MIN_TIGHT_FRACTION;
    o
}

/// The three shortest independent vectors among small combinations of a
/// reduced basis, right-handed: the familiar reduced cell.
fn shortest_basis(a: M3) -> M3 {
    let mut vectors: Vec<V3> = Vec::with_capacity(26);
    for i in -1..=1 {
        for j in -1..=1 {
            for k in -1..=1 {
                if (i, j, k) != (0, 0, 0) {
                    vectors.push(row([f64::from(i), f64::from(j), f64::from(k)], a));
                }
            }
        }
    }
    vectors.sort_by(|x, y| fft::dot(*x, *x).total_cmp(&fft::dot(*y, *y)));
    let volume = det(a).abs();
    for (i, &x) in vectors.iter().enumerate() {
        for (j, &y) in vectors.iter().enumerate().skip(i + 1) {
            for &z in &vectors[j + 1..] {
                let d = det([x, y, z]);
                if (d.abs() / volume - 1.).abs() < 1e-6 {
                    return if d > 0. { [x, y, z] } else { [y, x, z] };
                }
            }
        }
    }
    a
}

/// Misorientation (degrees) of two lattices of one crystal: an integer
/// unimodular change of basis maps `b` onto `a` (so symmetry-equivalent
/// settings compare as one), the mapped cell agrees with `a` within
/// `MERGE_LENGTH` and `MERGE_ANGLES`, and the angle is that of the rotation
/// taking one onto the other. None for different lattices.
pub(super) fn misorientation(a: M3, b: M3) -> Option<f64> {
    let dual = inv(b)?;
    let t: M3 = a.map(|r| dual.map(|d| fft::dot(r, d)));
    if t.iter().flatten().any(|v| (v - v.round()).abs() > 0.25) {
        return None;
    }
    let t = t.map(|r| r.map(f64::round));
    if (det(t).abs() - 1.).abs() > 1e-6 {
        return None;
    }
    let mapped: M3 = t.map(|r| row(r, b));
    let (p, m) = (parameters(a), parameters(mapped));
    if (0..3).any(|i| (p[i] - m[i]).abs() > MERGE_LENGTH * p[i])
        || (3..6).any(|i| (p[i] - m[i]).abs() > MERGE_ANGLES)
    {
        return None;
    }
    // Rows: a = mapped · M. The rotation is the orthogonal factor of M
    // (polar decomposition), so the cells' small strain does not count;
    // ± alike, since the lattice is centrosymmetric.
    let matrix = |m: M3| nalgebra::Matrix3::from_fn(|r, c| m[r][c]);
    let mut m = matrix(mapped).try_inverse()? * matrix(a);
    if m.determinant() < 0. {
        m = -m;
    }
    let svd = m.svd(true, true);
    let rotation = svd.u? * svd.v_t?;
    Some(
        ((rotation.trace() - 1.) / 2.)
            .clamp(-1., 1.)
            .acos()
            .to_degrees(),
    )
}
/// Least squares of the reciprocal basis on the `use_spot` positions, each
/// indexed by the current basis within twice and then once the tolerance;
/// the result reduced. None with too few spots or a singular fit.
fn refit(q: &[V3], use_spot: &[bool], start: M3, tolerance: f64) -> Option<M3> {
    let mut a = start;
    for factor in [2., 1.] {
        for _ in 0..REFIT_CYCLES {
            let b = inv(a)?;
            let (mut hh, mut hq, mut n) = ([[0.; 3]; 3], [[0.; 3]; 3], 0);
            for (p, _) in q.iter().zip(use_spot).filter(|(_, u)| **u) {
                let (h, d) = fft::indexed(*p, a, b);
                if h == [0.; 3] || d >= factor * tolerance {
                    continue;
                }
                n += 1;
                for r in 0..3 {
                    for c in 0..3 {
                        hh[r][c] += h[r] * h[c];
                        hq[r][c] += h[r] * p[c];
                    }
                }
            }
            if n < MIN_TRAIN {
                return None;
            }
            // (HᵀH)⁻¹ = transpose of the inverse transpose; HᵀH is symmetric.
            let hinv = inv(hh)?;
            let reciprocal: M3 = std::array::from_fn(|r| {
                std::array::from_fn(|c| (0..3).map(|k| hinv[r][k] * hq[k][c]).sum())
            });
            a = inv(reciprocal)?;
        }
    }
    Some(grains::reduce(a))
}
/// Merge accepted lattices of one crystal (misorientation within
/// `Config::merge_angle`, largest lattices first): refit on the training
/// spots both index, then validate the whole list again. A merge stands when
/// the merged lattice passes validation and indexes at least `MERGE_KEEP` of
/// the spots its parts indexed; otherwise the parts stay apart.
fn merge_domains(
    q: &[V3],
    training: &[bool],
    mut found: Vec<(grains::Grain, Option<Merged>)>,
    controls: &[M3],
    options: &grains::Options,
    limit: f64,
) -> Result<Vec<(grains::Grain, Option<Merged>)>, String> {
    if limit <= 0. {
        return Ok(found);
    }
    let mut refused: Vec<(M3, M3)> = Vec::new();
    loop {
        found.sort_by_key(|g| std::cmp::Reverse(g.0.training));
        let pair = (0..found.len()).find_map(|i| {
            (i + 1..found.len()).find_map(|j| {
                let (a, b) = (&found[i].0, &found[j].0);
                if !a.accepted || !b.accepted || refused.contains(&(a.direct, b.direct)) {
                    return None;
                }
                misorientation(a.direct, b.direct)
                    .filter(|&angle| angle <= limit)
                    .map(|angle| (i, j, angle))
            })
        });
        let Some((i, j, angle)) = pair else {
            return Ok(found);
        };
        let (a, b) = (&found[i].0, &found[j].0);
        let both: Vec<bool> = (0..q.len())
            .map(|k| training[k] && (a.indexed[k] || b.indexed[k]))
            .collect();
        let parts = a.training + a.withheld + b.training + b.withheld;
        let merged = refit(q, &both, a.direct, options.reciprocal_tolerance);
        let mut models: Vec<M3> = found.iter().map(|g| g.0.direct).collect();
        let accepted = merged.and_then(|m| {
            models[i] = m;
            models.remove(j);
            let grains = grains::validate(q, training, &models, controls, options).ok()?;
            let g = &grains[i];
            (g.accepted && (g.training + g.withheld) as f64 >= MERGE_KEEP * parts as f64)
                .then_some(grains)
        });
        let Some(grains) = accepted else {
            refused.push((a.direct, b.direct));
            continue;
        };
        let info: Vec<Option<Merged>> = found.iter().map(|g| g.1).collect();
        let joined = |k: usize| info[k].map_or((1, 0.), |m| (m.domains, m.angle));
        let ((di, ai), (dj, aj)) = (joined(i), joined(j));
        let mut info = info;
        info[i] = Some(Merged {
            domains: di + dj,
            angle: angle.max(ai).max(aj),
        });
        info.remove(j);
        found = grains.into_iter().zip(info).collect();
        refused.clear();
    }
}

/// Diamond (a = 3.567 Å): its reciprocal primitive vectors (body-centred
/// cubic) have length √3/a and pairwise |cos| = 1/3; their cell is 4/a³.
const DIAMOND: f64 = 3.567;
/// Whether a lattice's reciprocal nodes include a diamond reciprocal lattice:
/// the cell is then a supercell of diamond (it indexes the anvils' residual
/// reflections), not a grain of the sample.
pub(super) fn contains_diamond(direct: M3) -> bool {
    let Some(b) = inv(direct) else {
        return false;
    };
    let target = 3f64.sqrt() / DIAMOND;
    let span = direct.map(|r| (target * length(r) * 1.02).ceil() as i32);
    let mut nodes: Vec<V3> = Vec::new();
    for h in -span[0]..=span[0] {
        for k in -span[1]..=span[1] {
            for l in -span[2]..=span[2] {
                // One of each ± pair.
                if (h, k, l) <= (0, 0, 0) {
                    continue;
                }
                let q = row([f64::from(h), f64::from(k), f64::from(l)], b);
                if (length(q) / target - 1.).abs() < 0.015 {
                    nodes.push(q);
                }
            }
        }
    }
    let third =
        |u: V3, v: V3| (fft::dot(u, v).abs() / (length(u) * length(v)) - 1. / 3.).abs() < 0.02;
    let volume = 4. / DIAMOND.powi(3);
    for (i, &u) in nodes.iter().enumerate() {
        for (j, &v) in nodes.iter().enumerate().skip(i + 1) {
            if !third(u, v) {
                continue;
            }
            if nodes[j + 1..].iter().any(|&w| {
                third(u, w) && third(v, w) && (det([u, v, w]).abs() / volume - 1.).abs() < 0.05
            }) {
                return true;
            }
        }
    }
    false
}

/// Validated grains, most training spots first, without diamond supercells
/// after the first.
fn accepted(mut cells: Vec<(Cell, usize)>) -> Vec<Cell> {
    cells.sort_by_key(|c| std::cmp::Reverse(c.1));
    cells
        .into_iter()
        .enumerate()
        .filter(|(i, c)| *i == 0 || !contains_diamond(c.0.direct))
        .map(|(_, c)| c.0)
        .collect()
}
/// Validated lattices, one per grain, most training spots first, at most
/// `Config::max_grains`.
pub(super) fn find(q: &[V3], config: &Config, control: &Control) -> Result<Vec<Cell>, String> {
    let training: Vec<bool> = (0..q.len()).map(|i| i % 5 != 0).collect();
    let train = training.iter().filter(|&&t| t).count();
    if train < MIN_TRAIN || q.len() - train < MIN_TEST {
        return Ok(vec![]);
    }
    let cap = config.max_grains.clamp(1, MAX_GRAINS);
    let (method, found) = match config.lattice_method.as_str() {
        "fft" => (grains::Method::Fft, Found::Fft),
        "rows" => (grains::Method::Rows(row_options()), Found::Rows),
        _ => (grains::Method::Both(row_options()), Found::Both),
    };
    let found_grains = grains::find(
        q,
        &training,
        &null_rotations(),
        &options(config, cap),
        &method,
        &mut |done, total| {
            control.publish(
                json!({"running":true,"current":done,"total":total,"label":"Finding grains"}),
            );
            control.check().map_err(SpotError)
        },
    )
    .map_err(|e| e.0)?;
    control.check()?;
    let found_grains = merge_domains(
        q,
        &training,
        found_grains.into_iter().map(|g| (g, None)).collect(),
        &null_rotations(),
        &options(config, cap),
        config.merge_angle,
    )?;
    control.check()?;
    let cells = found_grains
        .into_iter()
        .filter(|g| g.0.accepted)
        .filter_map(|(g, merged)| {
            let b = inv(g.direct)?;
            let withheld: Vec<f64> = (0..q.len())
                .filter(|&i| g.indexed[i] && !training[i])
                .map(|i| fft::indexed(q[i], g.direct, b).1)
                .collect();
            let rms =
                (withheld.iter().map(|d| d * d).sum::<f64>() / withheld.len().max(1) as f64).sqrt();
            let direct = shortest_basis(g.direct);
            Some((
                Cell {
                    direct,
                    parameters: parameters(direct),
                    indexed: g.training + g.withheld,
                    total: q.len(),
                    rms,
                    validation: g.withheld,
                    found,
                    kept: false,
                    merged,
                },
                g.training,
            ))
        })
        .collect();
    let mut cells = accepted(cells);
    cells.truncate(cap);
    Ok(cells)
}
#[cfg(test)]
#[path = "single_crystal_lattices_tests.rs"]
mod tests;
