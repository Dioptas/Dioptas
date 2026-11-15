//! Find lattices: PhaseSmith's grain discovery on the reciprocal spot cloud,
//! with both of its grain-finding methods.
//!
//! The procedure follows `phasesmith-workflows/src/single_crystal/grains.rs`
//! (`discover`, `joint`, `discover_and_validate`), which PhaseSmith keeps
//! private behind its full structure workflow; it is rebuilt here from the
//! public `fft::Engine` and `fft::SupportBits` calls it is made of.
//!
//! - Rounds (until `Config::max_grains` lattices pass): each searches only the training spots that no
//!   lattice accepted so far explains, so further grains are found in what
//!   the earlier ones leave over.
//! - FFT seeds: the strongest periodicities of those spots, triples ranked by
//!   how many spots lie on all three row families (`SupportBits`).
//! - Row-search seeds (PhaseSmith `row_search`, Aslandukov et al. 2022): the
//!   spots split into groups on parallel, equally spaced reciprocal rows,
//!   about one grain each; each group's own periodicities give more triples,
//!   so a grain with few spots is searched on its own spots.
//! - Every triple is refined, reduced and checked for a smaller cell that
//!   explains the same spots; a cell whose spots an earlier lattice already
//!   explains is dropped. The best cell of the round is kept, and all kept
//!   cells are refit together with exclusive spot ownership.
//! - Validation on the withheld fifth of the spots against 64 rotated copies
//!   of them (`data/scxrd-null-rotations-v1.json`), as PhaseSmith does, plus
//!   `tight` withheld matches.
//!
//! Deviations from PhaseSmith, each needed on real multi-grain clouds: up to
//! rounds follow `Config::max_grains` instead of a fixed 5; each round's lattice chosen against rotated copies
//! of its spots with a preference for smaller cells (`Search::best`); the
//! `tight` gate; and diamond supercells (the anvils) dropped after the first
//! grain.
use super::processing::{det, parameters};
use super::*;
use nalgebra::{DMatrix, Matrix3};
use phasesmith_single_crystal::row_search;
use rayon::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};

/// Which search found a lattice. Older products carry no field: FFT.
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

// PhaseSmith grain discovery constants (grains.rs). PhaseSmith stops after
// 5 rounds; here the rounds follow `Config::max_grains` (`rounds`).
const MAXIMA: usize = 192;
const DIRECTIONS: usize = 64;
const PAIRS: usize = 96;
const TRIES: usize = 32;
const ROW_PHASE: f64 = 0.15;
const MAX_CONDITION: f64 = 20.;
const MIN_VOLUME: f64 = 15.;
const MAX_VOLUME: f64 = 20000.;
/// Fewest training spots a lattice must own (and a round must have left).
const MIN_SPOTS: usize = 20;
const MIN_TEST: usize = 6;
/// A cell is a duplicate when an earlier lattice explains this share of its spots.
const DUPLICATE: f64 = 0.8;
/// A spot within tolerance of two lattices goes to neither unless the nearer
/// is closer than this share of the other's distance.
pub(super) const AMBIGUITY: f64 = 0.8;
/// Distinct cells per round compared on rotated copies, and how many copies.
const ROUND_FINALISTS: usize = 16;
const ROUND_ROTATIONS: usize = 16;
// Row search.
const MIN_GROUP: usize = 20;
const MAX_GROUPS: usize = 16;
const ROW_SECONDS: f64 = 120.;

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
fn matrix(a: M3) -> Matrix3<f64> {
    Matrix3::from_fn(|i, j| a[i][j])
}
fn condition(a: M3) -> f64 {
    let s = matrix(a).svd(false, false).singular_values;
    s.max() / s.min()
}
/// `v` as a row vector times `a`.
fn row(v: V3, a: M3) -> V3 {
    std::array::from_fn(|j| (0..3).map(|k| v[k] * a[k][j]).sum())
}
fn mul(a: M3, b: M3) -> M3 {
    std::array::from_fn(|i| std::array::from_fn(|j| (0..3).map(|k| a[i][k] * b[k][j]).sum()))
}
/// Least-squares reciprocal rows `b` with `q ≈ h·b`; None when rank-deficient.
fn least(h: &[V3], q: &[V3]) -> Option<M3> {
    let a = DMatrix::from_fn(h.len(), 3, |i, j| h[i][j]);
    let b = DMatrix::from_fn(q.len(), 3, |i, j| q[i][j]);
    let svd = a.svd(true, true);
    let max = svd.singular_values.max();
    let eps = max * h.len() as f64 * f64::EPSILON;
    if svd.singular_values.iter().filter(|&&x| x > eps).count() < 3 {
        return None;
    }
    let x = svd.solve(&b, eps).ok()?;
    Some(std::array::from_fn(|i| std::array::from_fn(|j| x[(i, j)])))
}
/// Pairwise length reduction, shortest first, right-handed (PhaseSmith `reduce`).
fn reduce(mut a: M3) -> M3 {
    for _ in 0..100 {
        a.sort_by(|x, y| fft::dot(*x, *x).total_cmp(&fft::dot(*y, *y)));
        let mut changed = false;
        for j in 1..3 {
            for i in (0..j).rev() {
                let k = (fft::dot(a[i], a[j]) / fft::dot(a[i], a[i])).round_ties_even();
                let t = std::array::from_fn(|n| a[j][n] - k * a[i][n]);
                if fft::dot(t, t) < fft::dot(a[j], a[j]) - 1e-10 {
                    a[j] = t;
                    changed = true;
                }
            }
        }
        if !changed {
            break;
        }
    }
    if det(a) < 0. {
        a[2] = a[2].map(|x| -x);
    }
    a
}
/// Integer row basis of the lattice the indices span (Hermite form), or None.
#[allow(clippy::float_cmp)] // Indices are exact rounded integers.
fn integer_basis(indices: &[V3]) -> Option<M3> {
    let mut basis: [Option<[i128; 3]>; 3] = [None; 3];
    for h in indices {
        if h.iter()
            .any(|x| !x.is_finite() || x.abs() > 1_000_000. || *x != x.round_ties_even())
        {
            return None;
        }
        let mut r = h.map(|x| x as i128);
        for col in 0..3 {
            while r[col] != 0 {
                if let Some(pivot) = basis[col] {
                    let k = r[col].div_euclid(pivot[col]);
                    for j in 0..3 {
                        r[j] = r[j].checked_sub(k.checked_mul(pivot[j])?)?;
                    }
                    if r[col] != 0 {
                        if r[col] < 0 {
                            r = r.map(|x| -x);
                        }
                        basis[col] = Some(r);
                        r = pivot;
                    }
                } else {
                    basis[col] = Some(if r[col] > 0 { r } else { r.map(|x| -x) });
                    r = [0; 3];
                    break;
                }
            }
        }
    }
    Some([
        basis[0]?.map(|x| x as f64),
        basis[1]?.map(|x| x as f64),
        basis[2]?.map(|x| x as f64),
    ])
}

/// One refined cell tried in a round.
struct Trial {
    direct: M3,
    count: usize,
    excess: f64,
    rms: f64,
    order: usize,
    found: Found,
}

pub(super) struct Search<'a> {
    pub q: &'a [V3],
    /// Training membership; every fifth spot is withheld for validation.
    pub training: Vec<bool>,
    pub train: Vec<V3>,
    pub tolerance: f64,
    pub min_cell: f64,
    pub max_cell: f64,
    engine: fft::Engine,
}
impl<'a> Search<'a> {
    pub fn new(q: &'a [V3], config: &Config) -> Result<Self, String> {
        let training: Vec<bool> = (0..q.len()).map(|i| i % 5 != 0).collect();
        let train = q
            .iter()
            .zip(&training)
            .filter_map(|(&p, &t)| t.then_some(p))
            .collect();
        Ok(Self {
            q,
            training,
            train,
            tolerance: config.tolerance,
            min_cell: config.min_cell,
            max_cell: config.max_cell,
            engine: fft::Engine::new(4)?,
        })
    }
    fn score(&self, q: &[V3], a: M3) -> Option<Vec<(V3, f64)>> {
        Some(self.engine.score(q, a, inv(a)?))
    }
    /// Spots within tolerance of a non-origin node.
    #[allow(clippy::float_cmp)] // Exact zero-index sentinel.
    fn mask(&self, s: &[(V3, f64)]) -> Vec<bool> {
        s.iter()
            .map(|(h, d)| *d < self.tolerance && *h != [0.; 3])
            .collect()
    }
    fn explained(&self, q: &[V3], a: M3) -> Vec<bool> {
        self.score(q, a)
            .map_or_else(|| vec![false; q.len()], |s| self.mask(&s))
    }
    /// Exclusive owner of each spot, 1-based; 0 for none or ambiguous.
    fn assign(&self, q: &[V3], models: &[M3]) -> Vec<i32> {
        let models: Vec<_> = models.iter().filter_map(|&a| Some((a, inv(a)?))).collect();
        self.engine.assign(q, &models, self.tolerance, AMBIGUITY).0
    }
    fn valid(&self, a: M3) -> bool {
        let volume = det(a).abs();
        a.iter().flatten().all(|x| x.is_finite())
            && a.iter()
                .all(|&v| (self.min_cell..=self.max_cell).contains(&length(v)))
            && (MIN_VOLUME..=MAX_VOLUME).contains(&volume)
            && condition(a) <= MAX_CONDITION
    }
    /// Least-squares cycles (double tolerance first), reduction, then the
    /// smallest cell that still explains 90 % of the same spots.
    #[allow(clippy::float_cmp)] // Exact zero-index sentinel.
    fn refine(&self, q: &[V3], mut a: M3) -> Option<M3> {
        for cycle in 0..8 {
            let tolerance = if cycle < 2 { 2. } else { 1. } * self.tolerance;
            let (h, p): (Vec<V3>, Vec<V3>) = q
                .iter()
                .zip(self.score(q, a)?)
                .filter(|(_, (h, d))| *d < tolerance && *h != [0.; 3])
                .map(|(&p, (h, _))| (h, p))
                .unzip();
            if h.len() < 6 {
                return None;
            }
            let b = least(&h, &p)?;
            if det(b).abs() < 1e-12 {
                return None;
            }
            let updated = inv(b)?;
            let delta = a
                .iter()
                .flatten()
                .zip(updated.iter().flatten())
                .map(|(x, y)| (x - y).abs())
                .fold(0., f64::max);
            a = updated;
            if cycle >= 2 && delta < 1e-8 {
                break;
            }
        }
        a = reduce(a);
        if !self.valid(a) {
            return None;
        }
        let s = self.score(q, a)?;
        let selected = self.mask(&s);
        let total = selected.iter().filter(|&&v| v).count();
        let mut ids: Vec<_> = (0..q.len()).filter(|&i| selected[i]).collect();
        ids.sort_by(|&i, &j| s[i].1.total_cmp(&s[j].1));
        let mut best = a;
        for size in [24, 48, 96] {
            if ids.len() < size {
                continue;
            }
            let hs: Vec<_> = ids[..size].iter().map(|&i| s[i].0).collect();
            let Some(h) = integer_basis(&hs) else {
                continue;
            };
            if det(h).round().abs() <= 1. {
                continue;
            }
            let Some(t) = inv(mul(h, inv(a)?)).map(reduce) else {
                continue;
            };
            if !self.valid(t) {
                continue;
            }
            let m = self.explained(q, t);
            let kept = (0..q.len()).filter(|&i| m[i] && selected[i]).count();
            if kept as f64 >= 0.9 * total as f64 && det(t).abs() < det(best).abs() {
                best = t;
            }
        }
        Some(best)
    }
    /// All lattices refit together on the spots each exclusively owns.
    fn joint(&self, q: &[V3], mut models: Vec<M3>) -> (Vec<M3>, Vec<i32>) {
        let mut labels = self.assign(q, &models);
        for _ in 0..8 {
            let mut updated = Vec::new();
            let mut stable = true;
            for (i, &a) in models.iter().enumerate() {
                let block: Vec<_> = q
                    .iter()
                    .zip(&labels)
                    .filter_map(|(&p, &l)| (l == i as i32 + 1).then_some(p))
                    .collect();
                let h: Vec<V3> = self
                    .score(&block, a)
                    .unwrap_or_default()
                    .into_iter()
                    .map(|x| x.0)
                    .collect();
                let mut b = a;
                if block.len() >= 6
                    && let Some(fit) = least(&h, &block)
                    && det(fit).abs() > 1e-12
                    && let Some(t) = inv(fit)
                    && self.valid(t)
                {
                    b = t;
                }
                stable &= block
                    .iter()
                    .zip(&h)
                    .all(|(&p, h)| (0..3).all(|j| fft::dot(p, b[j]).round_ties_even() == h[j]));
                updated.push(b);
            }
            let next = self.assign(q, &updated);
            let changed = labels != next;
            models = updated;
            labels = next;
            if !changed && stable {
                break;
            }
        }
        (models, labels)
    }
    fn step(&self) -> f64 {
        let qmax = self
            .q
            .iter()
            .flatten()
            .copied()
            .map(f64::abs)
            .fold(0., f64::max);
        (2. * qmax / 252.).min(1. / (2.1 * self.max_cell))
    }
    /// Up to 64 distinct directions among the strongest refined periodicities.
    fn vectors(&self, q: &[V3]) -> Result<Vec<V3>, String> {
        let step = self.step();
        let (initial, _, _) =
            self.engine
                .windowed_maxima(q, 256, step, self.min_cell, self.max_cell, MAXIMA)?;
        if initial.is_empty() {
            return Ok(initial);
        }
        let refined = self
            .engine
            .refine_fourier(q, &initial, 1.5 / (256. * step))
            .map_err(err)?;
        let mut order: Vec<_> = (0..refined.len()).collect();
        order.sort_by(|&i, &j| refined[j].1[0].total_cmp(&refined[i].1[0]));
        let mut chosen: Vec<V3> = Vec::new();
        for i in order {
            let v = refined[i].0;
            let n = length(v);
            if !(self.min_cell..=self.max_cell).contains(&n)
                || chosen
                    .iter()
                    .any(|&x| fft::dot(v, x).abs() / (n * length(x)) > 0.9995)
            {
                continue;
            }
            chosen.push(v);
            if chosen.len() == DIRECTIONS {
                break;
            }
        }
        Ok(chosen)
    }
    /// Triples of `v` with the most spots of `q` on all three row families.
    fn seeds(&self, q: &[V3], v: &[V3]) -> Vec<M3> {
        let rows = v
            .iter()
            .map(|&a| {
                let mut bits = vec![0u64; q.len().div_ceil(64)];
                for (i, &p) in q.iter().enumerate() {
                    let x = fft::dot(p, a);
                    if (x - x.round_ties_even()).abs() < ROW_PHASE {
                        bits[i / 64] |= 1 << (i % 64);
                    }
                }
                bits
            })
            .collect();
        let bits = fft::SupportBits {
            rows,
            count: q.len(),
            pool: self.engine.pool.clone(),
        };
        let keys: Vec<_> = bits
            .candidate_keys(PAIRS)
            .into_iter()
            .filter(|k| (MIN_VOLUME..=MAX_VOLUME).contains(&det(k.map(|i| v[i])).abs()))
            .collect();
        let volumes: Vec<_> = keys.iter().map(|k| det(k.map(|i| v[i])).abs()).collect();
        let (order, _) = bits.rank_triplets(&keys, &volumes);
        order
            .into_iter()
            .map(|i| keys[i].map(|k| v[k]))
            .filter(|&a| condition(a) <= MAX_CONDITION)
            .take(TRIES)
            .collect()
    }
    /// Seeds refined on the round's spots; new lattices with their excess
    /// over chance (spots a random lattice of that volume would catch).
    fn trials(&self, block: &[V3], seeds: Vec<M3>, models: &[M3], found: Found) -> Vec<Trial> {
        seeds
            .into_par_iter()
            .enumerate()
            .filter_map(|(order, a)| {
                let a = self.refine(block, a)?;
                let s = self.score(block, a)?;
                let selected = self.mask(&s);
                let own: Vec<V3> = block
                    .iter()
                    .zip(&selected)
                    .filter_map(|(&p, &ok)| ok.then_some(p))
                    .collect();
                if own.len() < MIN_SPOTS {
                    return None;
                }
                let duplicate = models.iter().any(|&old| {
                    let n = self.explained(&own, old).iter().filter(|&&x| x).count();
                    n as f64 >= DUPLICATE * own.len() as f64
                });
                if duplicate {
                    return None;
                }
                let volume = det(a).abs();
                let count = own.len() as f64;
                let chance = block.len() as f64 * volume * 4. * std::f64::consts::PI / 3.
                    * self.tolerance.powi(3);
                let rms = (s
                    .iter()
                    .zip(&selected)
                    .filter_map(|(s, &ok)| ok.then_some(s.1 * s.1))
                    .sum::<f64>()
                    / count)
                    .sqrt();
                Some(Trial {
                    direct: a,
                    count: own.len(),
                    excess: count - chance,
                    rms,
                    order,
                    found,
                })
            })
            .collect()
    }
    /// Row groups of the training spots (indices into `train`), largest first.
    fn groups(&self, control: &Control) -> Result<Vec<Vec<usize>>, String> {
        control.publish(
            json!({"running":true,"current":0,"total":1,"label":"Row search: grouping spots"}),
        );
        let options = row_search::Options {
            // PhaseSmith's selected settings for sparse, noisy rows
            // (tests/row_search_adaptive.rs, ROW_SEARCH_ALGORITHM.md).
            projection_grids: 4,
            phase_min_row: 3,
            relative_gap: true,
            naive_max_points: 2048,
            workers: crate::worker_pool::threads().clamp(1, 8),
            seconds: ROW_SECONDS,
            ..row_search::Options::default()
        };
        let cancel = AtomicBool::new(false);
        let finished = AtomicBool::new(false);
        let result = std::thread::scope(|scope| {
            let worker = scope.spawn(|| {
                let r = row_search::run(&self.train, &options, &cancel);
                finished.store(true, Ordering::Release);
                r
            });
            while !finished.load(Ordering::Acquire) {
                if control.check().is_err() {
                    cancel.store(true, Ordering::Relaxed);
                }
                std::thread::sleep(std::time::Duration::from_millis(20));
            }
            worker.join().map_err(|_| "Row search failed.".to_owned())?
        })?;
        control.check()?;
        let mut groups: Vec<_> = result
            .groups
            .into_iter()
            .filter(|g| g.len() >= MIN_GROUP)
            .collect();
        groups.sort_by_key(|g| std::cmp::Reverse(g.len()));
        groups.truncate(MAX_GROUPS);
        Ok(groups)
    }
    /// Grain discovery on the training spots: one lattice per round, found
    /// among the spots no earlier lattice explains, until `grains` pass
    /// validation or a round finds nothing. A round's lattice may fail
    /// validation, so up to `2 · grains + 2` rounds run.
    fn discover(
        &self,
        fft: bool,
        rows: bool,
        grains: usize,
        control: &Control,
    ) -> Result<Vec<(M3, Found)>, String> {
        let rounds = 2 * grains + 2;
        let groups = if rows { self.groups(control)? } else { vec![] };
        let train = &self.train;
        let mut models: Vec<M3> = Vec::new();
        let mut found: Vec<Found> = Vec::new();
        let mut labels = vec![0; train.len()];
        for round in 0..rounds {
            control.check()?;
            control.publish(json!({"running":true,"current":round,"total":rounds,
                "label":format!("Finding grains: {} found", models.len())}));
            let mut free: Vec<bool> = labels.iter().map(|&l| l == 0).collect();
            for &a in &models {
                for (f, e) in free.iter_mut().zip(self.explained(train, a)) {
                    *f &= !e;
                }
            }
            let block: Vec<V3> = (0..train.len())
                .filter(|&i| free[i])
                .map(|i| train[i])
                .collect();
            if block.len() < MIN_SPOTS {
                break;
            }
            let mut trials = Vec::new();
            if fft {
                let v = self.vectors(&block)?;
                trials.extend(self.trials(&block, self.seeds(&block, &v), &models, Found::Fft));
            }
            for g in &groups {
                control.check()?;
                // The group's spots this round still has to explain; a group
                // mostly explained already belongs to a lattice found before.
                let points: Vec<V3> = g.iter().filter(|&&i| free[i]).map(|&i| train[i]).collect();
                if points.len() < MIN_GROUP || points.len() * 2 < g.len() {
                    continue;
                }
                let v = self.vectors(&points)?;
                trials.extend(self.trials(&block, self.seeds(&points, &v), &models, Found::Rows));
            }
            let Some(best) = self.best(&block, &trials) else {
                break;
            };
            // Found by both when the other search reached the same lattice.
            let both = trials
                .iter()
                .any(|t| t.found != best.found && related(t.direct, best.direct));
            models.push(best.direct);
            found.push(if both { Found::Both } else { best.found });
            (models, labels) = self.joint(train, models);
            if models.len() >= grains {
                let current: Vec<_> = models.iter().copied().zip(found.iter().copied()).collect();
                if accepted(self.validate(&current)).len() >= grains {
                    break;
                }
            }
        }
        Ok(models.into_iter().zip(found).collect())
    }
    /// The round's lattice: among the distinct trials ranked best by excess
    /// over uniform chance (PhaseSmith's ranking), the one indexing the most
    /// spots beyond the same cell in rotated copies of the round's spots,
    /// or a smaller cell explaining nearly as much on the same spots.
    /// Uniform chance is far too low on real clouds (shells, leftover rows of
    /// other grains), so a large cell can outrank a small grain it then hides;
    /// rotated copies keep that structure. Training spots only.
    fn best<'t>(&self, block: &[V3], trials: &'t [Trial]) -> Option<&'t Trial> {
        let mut ranked: Vec<&Trial> = trials.iter().collect();
        ranked.sort_by(|a, b| {
            b.excess
                .total_cmp(&a.excess)
                .then(a.rms.total_cmp(&b.rms))
                .then(det(a.direct).abs().total_cmp(&det(b.direct).abs()))
                .then((a.found as u8).cmp(&(b.found as u8)))
                .then(a.order.cmp(&b.order))
        });
        let mut distinct: Vec<&Trial> = Vec::new();
        for t in ranked {
            if !distinct.iter().any(|d| related(d.direct, t.direct)) {
                distinct.push(t);
                if distinct.len() == ROUND_FINALISTS {
                    break;
                }
            }
        }
        let rotated: Vec<Vec<V3>> = null_rotations()
            .into_iter()
            .take(ROUND_ROTATIONS)
            .map(|r| block.iter().map(|&p| row(p, r)).collect())
            .collect();
        let scored: Vec<(f64, Vec<bool>)> = distinct
            .par_iter()
            .map(|t| {
                let null: usize = rotated
                    .iter()
                    .map(|q| self.explained(q, t.direct).iter().filter(|&&x| x).count())
                    .sum();
                let beyond = t.count as f64 - null as f64 / rotated.len() as f64;
                (beyond, self.explained(block, t.direct))
            })
            .collect();
        let volume = |i: usize| det(distinct[i].direct).abs();
        let mut chosen = (0..distinct.len())
            .max_by(|&i, &j| scored[i].0.total_cmp(&scored[j].0).then(j.cmp(&i)))?;
        // A smaller cell on the same spots that keeps 90 % of what the larger
        // one explains beyond the rotated copies: the larger one is a
        // (near-)supercell whose extra spots are chance.
        loop {
            let (beyond, mask) = &scored[chosen];
            let smaller = (0..distinct.len())
                .filter(|&i| volume(i) < 0.67 * volume(chosen))
                .filter(|&i| {
                    let shared = mask
                        .iter()
                        .zip(&scored[i].1)
                        .filter(|(a, b)| **a && **b)
                        .count();
                    scored[i].0 >= 0.9 * beyond && shared as f64 >= 0.8 * distinct[i].count as f64
                })
                .max_by(|&i, &j| scored[i].0.total_cmp(&scored[j].0).then(j.cmp(&i)));
            match smaller {
                Some(i) => chosen = i,
                None => break,
            }
        }
        Some(distinct[chosen])
    }
    /// PhaseSmith's withheld validation: each lattice must own enough
    /// withheld spots and clearly more than in every rotated copy of them.
    fn validate(&self, models: &[(M3, Found)]) -> Vec<(Cell, usize)> {
        let directs: Vec<M3> = models.iter().map(|m| m.0).collect();
        let labels = self.assign(self.q, &directs);
        let held: Vec<V3> = self
            .q
            .iter()
            .zip(&self.training)
            .filter_map(|(&p, &t)| (!t).then_some(p))
            .collect();
        let rotations = null_rotations();
        let nulls: Vec<Vec<usize>> = rotations
            .par_iter()
            .map(|&r| {
                let rotated: Vec<V3> = held.iter().map(|&p| row(p, r)).collect();
                let l = self.assign(&rotated, &directs);
                (0..directs.len())
                    .map(|i| l.iter().filter(|&&x| x == i as i32 + 1).count())
                    .collect()
            })
            .collect();
        let mut cells = Vec::new();
        for (i, &(direct, found)) in models.iter().enumerate() {
            let Some(s) = self.score(self.q, direct) else {
                continue;
            };
            let own = |j: usize| labels[j] == i as i32 + 1;
            let ntrain = (0..self.q.len())
                .filter(|&j| own(j) && self.training[j])
                .count();
            let test: Vec<f64> = (0..self.q.len())
                .filter(|&j| own(j) && !self.training[j])
                .map(|j| s[j].1)
                .collect();
            let ntest = test.len();
            let null: Vec<usize> = nulls.iter().map(|n| n[i]).collect();
            let mean = null.iter().sum::<usize>() as f64 / null.len() as f64;
            let var = null.iter().map(|&v| (v as f64 - mean).powi(2)).sum::<f64>()
                / (null.len() - 1) as f64;
            let trained: Vec<V3> = (0..self.q.len())
                .filter(|&j| own(j) && self.training[j])
                .map(|j| s[j].0)
                .collect();
            let unique = trained
                .iter()
                .map(|h| h.map(|x| x as i64))
                .collect::<std::collections::BTreeSet<_>>()
                .len();
            let rank = unique >= MIN_SPOTS && least(&trained, &trained).is_some();
            let n = ntest as f64;
            let inner = test.iter().filter(|&&d| d < self.tolerance / 2.).count();
            let accepted = tight(ntest, inner)
                && ntrain >= MIN_SPOTS
                && ntest >= MIN_TEST
                && ntest > null.iter().copied().max().unwrap_or(0)
                && n >= 2. * mean.max(1.)
                && n >= mean + 4. * var.max(mean).max(1.).sqrt()
                && n >= 0.5 * ntrain as f64 * held.len() as f64 / self.train.len() as f64
                && rank;
            if !accepted {
                continue;
            }
            let direct = shortest_basis(direct);
            let rms = (test.iter().map(|d| d * d).sum::<f64>() / n).sqrt();
            cells.push((
                Cell {
                    direct,
                    parameters: parameters(direct),
                    indexed: ntrain + ntest,
                    total: self.q.len(),
                    rms,
                    validation: ntest,
                    found,
                    kept: false,
                },
                ntrain,
            ));
        }
        cells
    }
}

/// Withheld matches of a real grain sit close to its nodes; chance matches
/// spread over the whole tolerance sphere (on real clouds about half of them
/// fall within half the tolerance). Not in PhaseSmith's gate: without it,
/// loose cells (withheld rms about half the tolerance) pass on multi-grain
/// clouds.
pub(super) fn tight(withheld: usize, inner: usize) -> bool {
    inner * 4 >= withheld * 3
}

/// Same lattice within refinement scatter: an integer, unimodular change of basis.
pub(super) fn related(a: M3, b: M3) -> bool {
    let Some(inverse) = inv(b) else {
        return false;
    };
    let t = a.map(|r| inverse.map(|dual| fft::dot(r, dual)));
    t.iter().flatten().all(|v| (v - v.round()).abs() < 0.05) && (det(t).abs() - 1.).abs() < 0.05
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

/// Validated grains, the one owning the most training spots first. A grain
/// after the first that is a diamond supercell is the anvils, not the sample.
pub(super) fn find(q: &[V3], config: &Config, control: &Control) -> Result<Vec<Cell>, String> {
    let search = Search::new(q, config)?;
    let method = config.lattice_method.as_str();
    let grains = config.max_grains.clamp(1, MAX_GRAINS);
    let models = search.discover(method != "rows", method != "fft", grains, control)?;
    control.check()?;
    let mut cells = accepted(search.validate(&models));
    cells.truncate(grains);
    Ok(cells)
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
#[cfg(test)]
#[path = "single_crystal_lattices_tests.rs"]
mod tests;
