/// One geometry's full-resolution field, with conservative bounds for short
/// row strips. Skipping strips cannot change a crossing or its interpolation.
pub(crate) struct IndexedField {
    angles: Vec<f64>,
    shape: [usize; 2],
    bounds: Vec<[f64; 2]>,
    limits: [f64; 2],
    blocks: usize,
}
const BLOCK: usize = 64;
impl IndexedField {
    pub fn new(angles: Vec<f64>, shape: [usize; 2]) -> Self {
        let [h, w] = shape;
        assert_eq!(angles.len(), h * w);
        let blocks = w.saturating_sub(1).div_ceil(BLOCK);
        let mut bounds = Vec::with_capacity(h.saturating_sub(1) * blocks);
        for row in 0..h.saturating_sub(1) {
            for block in 0..blocks {
                let start = block * BLOCK;
                let end = (start + BLOCK).min(w - 1);
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
        let limits = [
            angles.iter().copied().fold(f64::INFINITY, f64::min),
            angles.iter().copied().fold(f64::NEG_INFINITY, f64::max),
        ];
        Self {
            angles,
            shape,
            bounds,
            limits,
            blocks,
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
    let rows: Vec<_> = (0..h).step_by(step).collect();
    let cols: Vec<_> = (0..w).step_by(step).collect();
    let mut paths = vec![];
    if rows.len() < 2 || cols.len() < 2 {
        return json!(paths);
    }
    // Calibration previews already sample the field for display. Build bounds
    // on that exact sample grid once, then skip strips that cannot cross any
    // given ring. Do not change interpolation, path order or the sample grid.
    let strip = if index.is_some() { BLOCK } else { 16 };
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
                    Some(index.bounds[row * index.blocks + start / BLOCK])
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
                        let point = [
                            cols[ax] as f64 + t * (cols[bx] as f64 - cols[ax] as f64) + 0.5,
                            rows[ay] as f64 + t * (rows[by] as f64 - rows[ay] as f64) + 0.5,
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
