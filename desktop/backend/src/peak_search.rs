//! Native calibration search adapters. Massif reuses Dioptrin; Blob uses a
//! deterministic difference-of-Gaussians scale space on original f64 samples.
use crate::control::Control;

pub fn candidates(
    data: &[f64],
    shape: [usize; 2],
    algorithm: &str,
    control: &Control,
) -> Result<Vec<[f64; 2]>, String> {
    control.check()?;
    let points = if algorithm == "Massif" {
        dioptrin::calibration::find_peaks_image(
            data,
            shape[0],
            shape[1],
            &dioptrin::calibration::ImagePeakOptions {
                threshold_factor: 0.0,
                max_peaks: 100_000,
                ..Default::default()
            },
        )
        .into_iter()
        .map(|(y, x)| [y, x])
        .collect()
    } else {
        blob_candidates(data, shape, control)?
    };
    control.check()?;
    Ok(points)
}

fn gaussian(
    data: &[f64],
    [h, w]: [usize; 2],
    sigma: f64,
    control: &Control,
) -> Result<Vec<f64>, String> {
    let radius = (3.0 * sigma).ceil() as isize;
    let mut kernel: Vec<_> = (-radius..=radius)
        .map(|i| (-0.5 * (i as f64 / sigma).powi(2)).exp())
        .collect();
    let sum: f64 = kernel.iter().sum();
    for weight in &mut kernel {
        *weight /= sum;
    }
    let mut temp = vec![0.0; data.len()];
    let mut output = vec![0.0; data.len()];
    for y in 0..h {
        control.check()?;
        for x in 0..w {
            temp[y * w + x] = kernel
                .iter()
                .enumerate()
                .map(|(k, a)| {
                    a * data[y * w
                        + (x as isize + k as isize - radius).clamp(0, w as isize - 1) as usize]
                })
                .sum();
        }
    }
    for y in 0..h {
        control.check()?;
        for x in 0..w {
            output[y * w + x] = kernel
                .iter()
                .enumerate()
                .map(|(k, a)| {
                    a * temp[(y as isize + k as isize - radius).clamp(0, h as isize - 1) as usize
                        * w
                        + x]
                })
                .sum();
        }
    }
    Ok(output)
}
fn blob_candidates(
    data: &[f64],
    shape: [usize; 2],
    control: &Control,
) -> Result<Vec<[f64; 2]>, String> {
    let [h, w] = shape;
    if h < 3 || w < 3 {
        return Ok(vec![]);
    }
    let mut previous = gaussian(data, shape, 1.0, control)?;
    let mut best = vec![0.0_f64; data.len()];
    for sigma in [2.0, 4.0, 8.0] {
        let next = gaussian(data, shape, sigma, control)?;
        for i in 0..data.len() {
            best[i] = best[i].max(previous[i] - next[i]);
        }
        previous = next;
    }
    let mut points = vec![];
    for y in 1..h - 1 {
        control.check()?;
        for x in 1..w - 1 {
            let v = best[y * w + x];
            if v <= 0.0 {
                continue;
            }
            if (y - 1..=y + 1).any(|row| (x - 1..=x + 1).any(|col| best[row * w + col] > v)) {
                continue;
            }
            let mut peak = (y, x);
            for row in y - 1..=y + 1 {
                for col in x - 1..=x + 1 {
                    if data[row * w + col] > data[peak.0 * w + peak.1] {
                        peak = (row, col);
                    }
                }
            }
            points.push(subpixel(data, shape, peak));
            if points.len() >= 100_000 {
                return Err("Blob search exceeds 100000 candidates; narrow the calibration image or mask noisy regions.".into());
            }
        }
    }
    Ok(points)
}

fn subpixel(data: &[f64], [h, w]: [usize; 2], (y, x): (usize, usize)) -> [f64; 2] {
    if y == 0 || x == 0 || y + 1 >= h || x + 1 >= w {
        return [y as f64, x as f64];
    }
    let v = data[y * w + x];
    let dx = (data[y * w + x + 1] - data[y * w + x - 1]) * 0.5;
    let dy = (data[(y + 1) * w + x] - data[(y - 1) * w + x]) * 0.5;
    let xx = data[y * w + x + 1] + data[y * w + x - 1] - 2.0 * v;
    let yy = data[(y + 1) * w + x] + data[(y - 1) * w + x] - 2.0 * v;
    let xy = (data[(y + 1) * w + x + 1] + data[(y - 1) * w + x - 1]
        - data[(y + 1) * w + x - 1]
        - data[(y - 1) * w + x + 1])
        * 0.25;
    let determinant = xx * yy - xy * xy;
    if determinant > 0.0 && xx < 0.0 && yy < 0.0 {
        let ox = (xy * dy - yy * dx) / determinant;
        let oy = (xy * dx - xx * dy) / determinant;
        if ox.is_finite() && oy.is_finite() && ox.abs() <= 1.0 && oy.abs() <= 1.0 {
            return [y as f64 + oy, x as f64 + ox];
        }
    }
    [y as f64, x as f64]
}

/// Apply Qt's angular band, upper-intensity ceiling and mean-factor + std
/// threshold, then retain distributed candidates rather than a spatial prefix.
pub struct Band {
    pub target: f64,
    pub delta: f64,
    pub factor: f64,
    pub ceiling: f64,
}
pub fn on_ring(
    data: &[f64],
    angles: &[f64],
    mask: &[u8],
    shape: [usize; 2],
    candidates: &[[f64; 2]],
    band: Band,
    control: &Control,
) -> Result<Vec<[f64; 2]>, String> {
    let Band {
        target,
        delta,
        factor,
        ceiling,
    } = band;
    let eligible = |i: usize| {
        data[i].is_finite()
            && data[i] <= ceiling
            && mask[i] == 0
            && (angles[i] - target).abs() <= delta.to_radians()
    };
    let mut n = 0.0;
    let mut mean = 0.0;
    let mut m2 = 0.0;
    for (i, &value) in data.iter().enumerate() {
        if i % 65536 == 0 {
            control.check()?;
        }
        if eligible(i) {
            n += 1.0;
            let d = value - mean;
            mean += d / n;
            m2 += d * (value - mean);
        }
    }
    if n == 0.0 {
        return Ok(vec![]);
    }
    let threshold = factor * mean + (m2 / n).sqrt();
    let count = (0..data.len())
        .filter(|&i| eligible(i) && data[i] > threshold)
        .count();
    let keep = (count as f64).sqrt().ceil() as usize;
    if keep == 0 {
        return Ok(vec![]);
    }
    let mut points = vec![];
    for &p in candidates {
        let row = p[0].round().clamp(0.0, shape[0] as f64 - 1.0) as usize;
        let col = p[1].round().clamp(0.0, shape[1] as f64 - 1.0) as usize;
        let i = row * shape[1] + col;
        if eligible(i)
            && data[i] > threshold
            && !points
                .iter()
                .any(|q: &[f64; 2]| (p[0] - q[0]).hypot(p[1] - q[1]) < 1.0)
        {
            points.push(p);
        }
    }
    // Candidate order is scan order. Uniform subsampling avoids selecting only
    // one detector edge when a ring contains more peaks than the Qt keep count.
    if points.len() > keep {
        points = (0..keep).map(|i| points[i * points.len() / keep]).collect();
    }
    Ok(points)
}

/// Display-only marching-squares paths. Coordinates are detector pixel centers;
/// fitting and searches always use the original full-resolution field.
pub fn contours(angles: &[f64], shape: [usize; 2], targets: &[(usize, f64)]) -> serde_json::Value {
    contours_at_step(
        angles,
        shape,
        targets,
        shape[0].max(shape[1]).div_ceil(450).max(1),
    )
}
pub fn full_contours(angles: &[f64], shape: [usize; 2], target: f64) -> serde_json::Value {
    contours_at_step(angles, shape, &[(0, target)], 1)
}
use crate::contours::contours_at_step;
