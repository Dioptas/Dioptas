/// One geometry's field, with conservative bounds for short row strips.
/// Skipping strips cannot change a crossing or its interpolation.
pub(crate) struct IndexedField {
    angles: Vec<f64>,
    shape: [usize; 2],
    bounds: Vec<[f64; 2]>,
    limits: [f64; 2],
    blocks: usize,
    strip: usize,
    coordinate_step: usize,
}
const BLOCK: usize = 64;
#[derive(Default)]
struct ContourGraph {
    vertices: std::collections::HashMap<usize, ContourVertex>,
}
#[derive(Clone, Copy, Default)]
struct ContourVertex {
    point: [f64; 2],
    neighbors: [usize; 2],
    degree: usize,
    visited: bool,
}
impl ContourGraph {
    fn cell(
        &mut self,
        values: [f64; 4],
        row: usize,
        col: usize,
        width: usize,
        scale: usize,
        target: f64,
    ) {
        let positions = [
            (row, col),
            (row, col + 1),
            (row + 1, col + 1),
            (row + 1, col),
        ];
        let edge_ids = [
            (row * width + col) * 2,
            (row * width + col + 1) * 2 + 1,
            ((row + 1) * width + col) * 2,
            (row * width + col) * 2 + 1,
        ];
        let mut crossed = [0; 4];
        let mut count = 0;
        for (edge, (a, b)) in [(0, 1), (1, 2), (3, 2), (0, 3)].into_iter().enumerate() {
            if (values[a] < target) == (values[b] < target)
                || !values[a].is_finite()
                || !values[b].is_finite()
            {
                continue;
            }
            let t = (target - values[a]) / (values[b] - values[a]);
            let (ay, ax) = positions[a];
            let (by, bx) = positions[b];
            let [ax, bx, ay, by] = [ax * scale, bx * scale, ay * scale, by * scale];
            self.vertices.entry(edge_ids[edge]).or_default().point = [
                ax as f64 + t * (bx as f64 - ax as f64) + 0.5,
                ay as f64 + t * (by as f64 - ay as f64) + 0.5,
            ];
            crossed[count] = edge_ids[edge];
            count += 1;
        }
        if count == 4 && values[0] >= target && values[2] >= target {
            crossed = [edge_ids[0], edge_ids[3], edge_ids[1], edge_ids[2]];
        }
        for pair in crossed[..count].as_chunks::<2>().0 {
            for (a, b) in [(pair[0], pair[1]), (pair[1], pair[0])] {
                let vertex = self.vertices.get_mut(&a).unwrap();
                vertex.neighbors[vertex.degree] = b;
                vertex.degree += 1;
            }
        }
    }
    fn paths(mut self) -> serde_json::Value {
        use serde_json::json;
        let mut paths = vec![];
        // Hash insertion avoids per-node tree and neighbor allocations. Sort
        // only start IDs to retain the exact legacy path and endpoint order.
        let mut keys: Vec<_> = self
            .vertices
            .iter()
            .filter(|(_, v)| v.degree > 0)
            .map(|(&k, _)| k)
            .collect();
        keys.sort_unstable();
        let starts: Vec<_> = keys
            .iter()
            .copied()
            .filter(|k| self.vertices[k].degree == 1)
            .chain(keys.iter().copied())
            .collect();
        for start in starts {
            if self.vertices[&start].visited {
                continue;
            }
            let mut current = start;
            let mut points = vec![];
            loop {
                let vertex = self.vertices[&current];
                if vertex.visited {
                    break;
                }
                self.vertices.get_mut(&current).unwrap().visited = true;
                points.push(vertex.point);
                let neighbors = &vertex.neighbors[..vertex.degree];
                if let Some(&next) = neighbors.iter().find(|&next| !self.vertices[next].visited) {
                    current = next;
                } else {
                    if neighbors.contains(&start) {
                        points.push(self.vertices[&start].point);
                    }
                    break;
                }
            }
            if points.len() >= 2 {
                paths.push(json!({"ring":0,"points":points}));
            }
        }
        serde_json::Value::Array(paths)
    }
}
impl IndexedField {
    pub fn new(angles: Vec<f64>, shape: [usize; 2]) -> Self {
        Self::sampled(angles, shape, 1)
    }
    /// Retain only the existing display sample grid, with source-pixel
    /// coordinates and full-field limits identical to contours_at_step.
    pub fn sampled(angles: Vec<f64>, shape: [usize; 2], step: usize) -> Self {
        let [h, w] = shape;
        assert_eq!(angles.len(), h * w);
        assert!(step > 0);
        let limits = [
            angles.iter().copied().fold(f64::INFINITY, f64::min),
            angles.iter().copied().fold(f64::NEG_INFINITY, f64::max),
        ];
        let angles = if step == 1 {
            angles
        } else {
            (0..h)
                .step_by(step)
                .flat_map(|row| {
                    let angles = &angles;
                    (0..w).step_by(step).map(move |col| angles[row * w + col])
                })
                .collect()
        };
        let [h, w] = [h.div_ceil(step), w.div_ceil(step)];
        let strip = if step == 1 { BLOCK } else { 16 };
        let blocks = w.saturating_sub(1).div_ceil(strip);
        let mut bounds = Vec::with_capacity(h.saturating_sub(1) * blocks);
        for row in 0..h.saturating_sub(1) {
            for block in 0..blocks {
                let start = block * strip;
                let end = (start + strip).min(w - 1);
                let mut range = [f64::INFINITY, f64::NEG_INFINITY];
                for r in [row, row + 1] {
                    for &v in &angles[r * w + start..=r * w + end] {
                        range[0] = range[0].min(v);
                        range[1] = range[1].max(v);
                    }
                }
                bounds.push(range);
            }
        }
        Self {
            angles,
            shape: [h, w],
            bounds,
            limits,
            blocks,
            strip,
            coordinate_step: step,
        }
    }
    pub fn contour(&self, target: f64) -> serde_json::Value {
        contours(
            &self.angles,
            self.shape,
            &[(0, target)],
            1,
            Some(self),
            true,
        )
    }
    /// Trace changed reflections from every phase together. Each sample cell is
    /// read once, and sorted target angles select only the levels it crosses.
    /// Graph insertion stays in row-major order, matching independent contours.
    pub fn contours(&self, targets: &[f64]) -> Vec<serde_json::Value> {
        let mut active: Vec<_> = targets
            .iter()
            .copied()
            .enumerate()
            .filter(|(_, t)| t.is_finite() && *t > self.limits[0] && *t < self.limits[1])
            .collect();
        // A few moving lines benefit more from the existing strip lookup than
        // from walking the whole shared grid.
        if active.len() < 32 {
            return targets.iter().map(|&t| self.contour(t)).collect();
        }
        active.sort_by(|a, b| a.1.total_cmp(&b.1));
        use rayon::prelude::*;
        let band_size = active
            .len()
            .div_ceil(crate::worker_pool::threads())
            .clamp(8, 32);
        let bands: Vec<Vec<_>> = crate::worker_pool::install(|| {
            active
                .par_chunks(band_size)
                .map(|levels| self.contour_band(levels))
                .collect()
        });
        let mut paths = vec![serde_json::Value::Array(vec![]); targets.len()];
        for (i, value) in bands.into_iter().flatten() {
            paths[i] = value;
        }
        paths
    }
    // Narrow angle bands share cell samples and skip cached strips outside the
    // band's complete range. Each independent band runs within the selected
    // worker pool; its graph insertion remains exactly row-major.
    fn contour_band(&self, levels: &[(usize, f64)]) -> Vec<(usize, serde_json::Value)> {
        let mut graphs: Vec<_> = levels.iter().map(|_| ContourGraph::default()).collect();
        let [h, w] = self.shape;
        let low = levels[0].1;
        let high = levels.last().unwrap().1;
        for row in 0..h.saturating_sub(1) {
            for block in 0..self.blocks {
                let [min, max] = self.bounds[row * self.blocks + block];
                if low > max || high <= min {
                    continue;
                }
                let start_col = block * self.strip;
                for col in start_col..(start_col + self.strip).min(w - 1) {
                    let values = [
                        self.angles[row * w + col],
                        self.angles[row * w + col + 1],
                        self.angles[(row + 1) * w + col + 1],
                        self.angles[(row + 1) * w + col],
                    ];
                    let min = values.into_iter().fold(f64::INFINITY, f64::min);
                    let max = values.into_iter().fold(f64::NEG_INFINITY, f64::max);
                    let start = levels.partition_point(|(_, t)| *t <= min);
                    for (i, &(_, target)) in levels.iter().enumerate().skip(start) {
                        if target > max {
                            break;
                        }
                        graphs[i].cell(values, row, col, w, self.coordinate_step, target);
                    }
                }
            }
        }
        levels
            .iter()
            .zip(graphs)
            .map(|(&(i, _), graph)| (i, graph.paths()))
            .collect()
    }
}
pub(crate) fn contours_at_step(
    angles: &[f64],
    shape: [usize; 2],
    targets: &[(usize, f64)],
    step: usize,
) -> serde_json::Value {
    contours(angles, shape, targets, step, None, true)
}
fn contours(
    angles: &[f64],
    shape: [usize; 2],
    targets: &[(usize, f64)],
    step: usize,
    index: Option<&IndexedField>,
    skip_empty: bool,
) -> serde_json::Value {
    use serde_json::json;
    use std::collections::{BTreeMap, BTreeSet};
    let [h, w] = shape;
    let coordinate_step = index.map_or(1, |i| i.coordinate_step);
    let rows: Vec<_> = (0..h).step_by(step).collect();
    let cols: Vec<_> = (0..w).step_by(step).collect();
    let mut paths = vec![];
    if rows.len() < 2 || cols.len() < 2 {
        return json!(paths);
    }
    // Calibration previews already sample the field for display. Build bounds
    // on that exact sample grid once, then skip strips that cannot cross any
    // given ring. Do not change interpolation, path order or the sample grid.
    let strip = index.map_or(16, |i| i.strip);
    let blocks = (cols.len() - 1).div_ceil(strip);
    let sampled_bounds = if index.is_none() && skip_empty {
        let mut bounds = Vec::with_capacity((rows.len() - 1) * blocks);
        for row in 0..rows.len() - 1 {
            for start in (0..cols.len() - 1).step_by(strip) {
                let end = (start + strip).min(cols.len() - 1);
                let mut range = [f64::INFINITY, f64::NEG_INFINITY];
                for &r in &rows[row..=row + 1] {
                    for &c in &cols[start..=end] {
                        let value = angles[r * w + c];
                        range[0] = range[0].min(value);
                        range[1] = range[1].max(value);
                    }
                }
                bounds.push(range);
            }
        }
        Some(bounds)
    } else {
        None
    };
    let [low, high] = index.map_or_else(
        || {
            [
                angles.iter().copied().fold(f64::INFINITY, f64::min),
                angles.iter().copied().fold(f64::NEG_INFINITY, f64::max),
            ]
        },
        |i| i.limits,
    );
    for &(ring, target) in targets {
        if target <= low || target >= high {
            continue;
        }
        let mut vertices = BTreeMap::new();
        let mut adjacent: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        for row in 0..rows.len() - 1 {
            for start in (0..cols.len() - 1).step_by(strip) {
                let range = if let Some(index) = index {
                    Some(index.bounds[row * index.blocks + start / index.strip])
                } else {
                    sampled_bounds
                        .as_ref()
                        .map(|b| b[row * blocks + start / strip])
                };
                if range.is_some_and(|[min, max]| target <= min || target > max) {
                    continue;
                }
                for col in start..(start + strip).min(cols.len() - 1) {
                    let positions = [
                        (row, col),
                        (row, col + 1),
                        (row + 1, col + 1),
                        (row + 1, col),
                    ];
                    let values = positions.map(|(y, x)| angles[rows[y] * w + cols[x]]);
                    let edge_ids = [
                        (row * cols.len() + col) * 2,
                        (row * cols.len() + col + 1) * 2 + 1,
                        ((row + 1) * cols.len() + col) * 2,
                        (row * cols.len() + col) * 2 + 1,
                    ];
                    let mut crossed = vec![];
                    for (edge, (a, b)) in [(0, 1), (1, 2), (3, 2), (0, 3)].into_iter().enumerate() {
                        if (values[a] < target) == (values[b] < target)
                            || !values[a].is_finite()
                            || !values[b].is_finite()
                        {
                            continue;
                        }
                        let t = (target - values[a]) / (values[b] - values[a]);
                        let (ay, ax) = positions[a];
                        let (by, bx) = positions[b];
                        let [ax, bx, ay, by] = [
                            cols[ax] * coordinate_step,
                            cols[bx] * coordinate_step,
                            rows[ay] * coordinate_step,
                            rows[by] * coordinate_step,
                        ];
                        let point = [
                            ax as f64 + t * (bx as f64 - ax as f64) + 0.5,
                            ay as f64 + t * (by as f64 - ay as f64) + 0.5,
                        ];
                        vertices.insert(edge_ids[edge], point);
                        crossed.push(edge_ids[edge]);
                    }
                    if crossed.len() == 4 && values[0] >= target && values[2] >= target {
                        // Match skimage's default: low-valued saddle pixels are connected.
                        crossed = vec![edge_ids[0], edge_ids[3], edge_ids[1], edge_ids[2]];
                    }
                    for pair in crossed.as_chunks::<2>().0 {
                        adjacent.entry(pair[0]).or_default().push(pair[1]);
                        adjacent.entry(pair[1]).or_default().push(pair[0]);
                    }
                }
            }
        }
        let mut visited = BTreeSet::new();
        let starts: Vec<_> = adjacent
            .iter()
            .filter(|(_, v)| v.len() == 1)
            .map(|(&k, _)| k)
            .chain(adjacent.keys().copied())
            .collect();
        for start in starts {
            if visited.contains(&start) {
                continue;
            }
            let mut current = start;
            let mut points = vec![];
            loop {
                if !visited.insert(current) {
                    break;
                }
                points.push(vertices[&current]);
                if let Some(&next) = adjacent[&current]
                    .iter()
                    .find(|&&next| !visited.contains(&next))
                {
                    current = next;
                } else {
                    if adjacent[&current].contains(&start) {
                        points.push(vertices[&start]);
                    }
                    break;
                }
            }
            if points.len() >= 2 {
                paths.push(json!({"ring":ring,"points":points}));
            }
        }
    }
    json!(paths)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn batched_levels_preserve_independent_paths_with_saddles_duplicates_and_nonfinite_pixels() {
        for [h, w] in [[1, 1], [2, 2], [9, 66], [73, 131]] {
            let mut field: Vec<_> = (0..h * w)
                .map(|i| {
                    let (r, c) = ((i / w) as f64, (i % w) as f64);
                    ((r - h as f64 * 0.4).powi(2) + (c - w as f64 * 0.6).powi(2)).sqrt()
                        + ((i * 17 % 11) as f64) * 0.03
                })
                .collect();
            for special in [false, true] {
                if special {
                    for (i, value) in field.iter_mut().enumerate() {
                        if i % 127 == 0 {
                            *value = f64::NAN;
                        } else if i % 133 == 0 {
                            *value = f64::INFINITY;
                        } else if i % 17 == 0 {
                            *value = 10.;
                        }
                    }
                }
                let low = field
                    .iter()
                    .copied()
                    .filter(|v| v.is_finite())
                    .fold(f64::INFINITY, f64::min);
                let high = field
                    .iter()
                    .copied()
                    .filter(|v| v.is_finite())
                    .fold(f64::NEG_INFINITY, f64::max);
                let mut targets: Vec<_> = (0..80)
                    .map(|i| low + (high - low) * i as f64 / 79.)
                    .collect();
                targets.extend(field.iter().copied().filter(|v| v.is_finite()).take(8));
                targets.extend([0.5, 0.5, f64::NAN, f64::INFINITY, f64::NEG_INFINITY]);
                targets.reverse();
                for step in [1, 2, 7] {
                    let index = IndexedField::sampled(field.clone(), [h, w], step);
                    let actual = index.contours(&targets);
                    for workers in [1, crate::worker_pool::available().min(4)] {
                        let parallel = crate::worker_pool::enter(
                            crate::worker_pool::pool(Some(workers)).unwrap(),
                            || index.contours(&targets),
                        );
                        assert_eq!(parallel, actual, "Worker count must not change path data");
                    }
                    for (&target, paths) in targets.iter().zip(actual) {
                        assert_eq!(
                            paths,
                            contours_at_step(&field, [h, w], &[(0, target)], step),
                            "shape {h}x{w}, step {step}, target {target}, special {special}"
                        );
                    }
                }
            }
        }
        let field = vec![1., 0., 0., 1.];
        let index = IndexedField::new(field.clone(), [2, 2]);
        let targets = vec![0.5; 40];
        for paths in index.contours(&targets) {
            assert_eq!(paths, contours_at_step(&field, [2, 2], &[(0, 0.5)], 1));
        }
    }
    #[test]
    fn indexed_strips_preserve_full_resolution_contours_and_saddle_order() {
        for [h, w] in [[2, 2], [9, 66], [73, 131]] {
            let mut field: Vec<_> = (0..h * w)
                .map(|i| {
                    let (r, c) = ((i / w) as f64, (i % w) as f64);
                    ((r - h as f64 * 0.4).powi(2) + (c - w as f64 * 0.6).powi(2)).sqrt()
                })
                .collect();
            for special in [false, true] {
                if special {
                    for (i, v) in field.iter_mut().enumerate() {
                        if i % 127 == 0 {
                            *v = f64::NAN;
                        } else if i % 133 == 0 {
                            *v = f64::INFINITY;
                        } else if i % 17 == 0 {
                            *v = 10.;
                        }
                    }
                }
                let index = IndexedField::new(field.clone(), [h, w]);
                for target in [-1., 0., 0.5, 1., 2., 5., 10., 20., 40., 1000.] {
                    assert_eq!(
                        index.contour(target),
                        contours_at_step(&field, [h, w], &[(0, target)], 1),
                        "shape {h}x{w}, target {target}, special {special}"
                    );
                }
            }
        }
        let saddle = vec![1., 0., 0., 1.];
        assert_eq!(
            IndexedField::new(saddle.clone(), [2, 2]).contour(0.5),
            contours_at_step(&saddle, [2, 2], &[(0, 0.5)], 1)
        );
    }
    #[test]
    fn sampled_strip_skipping_preserves_exact_paths_for_all_steps() {
        for [h, w] in [[1, 1], [2, 2], [9, 66], [73, 131], [157, 251]] {
            let mut field: Vec<_> = (0..h * w)
                .map(|i| {
                    let (y, x) = ((i / w) as f64, (i % w) as f64);
                    ((y - h as f64 * 0.4).powi(2) + (x - w as f64 * 0.6).powi(2)).sqrt()
                })
                .collect();
            for special in [false, true] {
                if special {
                    for (i, value) in field.iter_mut().enumerate() {
                        if i % 127 == 0 {
                            *value = f64::NAN;
                        } else if i % 133 == 0 {
                            *value = f64::INFINITY;
                        } else if i % 17 == 0 {
                            *value = 10.0;
                        }
                    }
                }
                let targets: Vec<_> = [-1., 0., 0.5, 1., 2., 5., 10., 20., 40., 1000.]
                    .into_iter()
                    .enumerate()
                    .collect();
                for step in [1, 2, 3, 7] {
                    assert_eq!(
                        contours_at_step(&field, [h, w], &targets, step),
                        contours(&field, [h, w], &targets, step, None, false),
                        "shape {h}x{w}, step {step}, special {special}"
                    );
                    let indexed = IndexedField::sampled(field.clone(), [h, w], step);
                    for &(_, target) in &targets {
                        assert_eq!(
                            indexed.contour(target),
                            contours_at_step(&field, [h, w], &[(0, target)], step),
                            "cached sample shape {h}x{w}, step {step}, target {target}, special {special}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn plane_and_low_connected_saddle() {
        // Analytic intersections, with the same half-pixel display convention
        // as skimage.find_contours + 0.5.
        let plane = contours_at_step(&[0.0, 2.0, 1.0, 3.0], [2, 2], &[(1, 1.5)], 1);
        let points = plane[0]["points"].as_array().unwrap();
        assert!(points.contains(&serde_json::json!([1.25, 0.5])));
        assert!(points.contains(&serde_json::json!([0.75, 1.5])));
        let saddle = contours_at_step(&[1.0, 0.0, 0.0, 1.0], [2, 2], &[(1, 0.5)], 1);
        let paths = saddle.as_array().unwrap();
        assert_eq!(paths.len(), 2);
        assert!(paths.iter().any(|p| {
            let points = p["points"].as_array().unwrap();
            points.contains(&serde_json::json!([1.0, 0.5]))
                && points.contains(&serde_json::json!([0.5, 1.0]))
        }));
    }
}
