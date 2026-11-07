pub(crate) fn contours_at_step(
    angles: &[f64],
    shape: [usize; 2],
    targets: &[(usize, f64)],
    step: usize,
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
    let low = angles.iter().copied().fold(f64::INFINITY, f64::min);
    let high = angles.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    for &(ring, target) in targets {
        if target <= low || target >= high {
            continue;
        }
        let mut vertices = BTreeMap::new();
        let mut adjacent: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        for row in 0..rows.len() - 1 {
            for col in 0..cols.len() - 1 {
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
