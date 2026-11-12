//! Cache-friendly, order-preserving spatial mask kernels.
use super::{Control, Value, number, reflect};

#[derive(Default)]
pub(super) struct Workspace {
    cosmic_image: Vec<f64>,
    vertical: Vec<[f64; 3]>,
    means: Vec<[f64; 3]>,
    values: Vec<f64>,
    deviations: Vec<f64>,
    gaussian: Vec<f32>,
    filtered: Vec<f32>,
    row: Vec<f32>,
    sums: Vec<f64>,
}
// Scratch never becomes a copied scientific checkpoint or shared mutable state.
impl Clone for Workspace {
    fn clone(&self) -> Self {
        Self::default()
    }
}

pub(super) struct Groups {
    pub user: String,
    offsets: Vec<usize>,
    pixels: Vec<u32>,
    #[cfg(feature = "dioptrin")]
    pub largest: usize,
}
impl Groups {
    pub fn new(indices: &[usize], user: &[u8], bins: usize, id: String) -> Result<Self, String> {
        if indices.len() != user.len()
            || indices.len() > u32::MAX as usize
            || indices.iter().any(|&b| b >= bins)
        {
            return Err("Invalid spatial-mask bin dimensions.".into());
        }
        let mut offsets = vec![0; bins + 1];
        for (&b, &m) in indices.iter().zip(user) {
            if m == 0 {
                offsets[b + 1] += 1;
            }
        }
        #[cfg(feature = "dioptrin")]
        let largest = offsets.iter().copied().max().unwrap_or(0);
        for b in 0..bins {
            offsets[b + 1] += offsets[b];
        }
        let mut next = offsets[..bins].to_vec();
        let mut pixels = vec![0; offsets[bins]];
        for (p, (&b, &m)) in indices.iter().zip(user).enumerate() {
            if m == 0 {
                pixels[next[b]] = p as u32;
                next[b] += 1;
            }
        }
        Ok(Self {
            user: id,
            offsets,
            pixels,
            #[cfg(feature = "dioptrin")]
            largest,
        })
    }
}

#[inline]
fn moments(v: f64) -> [f64; 3] {
    if v > 0. { [1., v, v * v] } else { [0.; 3] }
}
pub(super) fn cosmic(
    data: &[f64],
    shape: [usize; 2],
    p: &Value,
    c: &Control,
    work: &mut Workspace,
) -> Result<Vec<u8>, String> {
    let [h, w] = shape;
    let window = number(p, "window_size") as usize;
    let iterations = number(p, "iterations") as usize;
    let minimum = number(p, "min_intensity");
    let sigma = number(p, "sigma");
    let left = window as isize / 2;
    let divisor = window as f64;
    let row_add: Vec<_> = (0..h)
        .map(|r| reflect(r as isize + window as isize - left, h))
        .collect();
    let row_remove: Vec<_> = (0..h).map(|r| reflect(r as isize - left, h)).collect();
    let col_add: Vec<_> = (0..w)
        .map(|v| reflect(v as isize + window as isize - left, w))
        .collect();
    let col_remove: Vec<_> = (0..w).map(|v| reflect(v as isize - left, w)).collect();
    work.cosmic_image.clear();
    work.cosmic_image.extend_from_slice(data);
    work.vertical.resize(w, [0.; 3]);
    work.means.resize(w, [0.; 3]);
    let mut mask = vec![0; data.len()];
    for iteration in 0..iterations {
        c.check()?;
        c.publish(serde_json::json!({"running":true,"current":iteration,"total":iterations,"label":"Computing Cosmic Ray Mask"}));
        work.vertical.fill([0.; 3]);
        for d in -left..window as isize - left {
            let row = reflect(d, h) * w;
            for (sum, &v) in work
                .vertical
                .iter_mut()
                .zip(&work.cosmic_image[row..row + w])
            {
                let v = moments(v);
                for k in 0..3 {
                    sum[k] += v[k];
                }
            }
        }
        for r in 0..h {
            if r % 32 == 0 {
                c.check()?;
            }
            for (mean, sum) in work.means.iter_mut().zip(&work.vertical) {
                for k in 0..3 {
                    mean[k] = sum[k] / divisor;
                }
            }
            let mut sum = [0.; 3];
            for d in -left..window as isize - left {
                let v = work.means[reflect(d, w)];
                for k in 0..3 {
                    sum[k] += v[k];
                }
            }
            for col in 0..w {
                let counts = sum[0] / divisor;
                let sums = sum[1] / divisor;
                let squares = sum[2] / divisor;
                let mean = if counts > 0. { sums / counts } else { 0. };
                let std = if counts > 0. {
                    (squares / counts - mean * mean).max(0.).sqrt()
                } else {
                    0.
                };
                let i = r * w + col;
                let v = work.cosmic_image[i];
                let z = if v > 0. && std > 0. {
                    (v - mean) / (std + 1e-10)
                } else {
                    0.
                };
                if v > minimum && v > 0. && (z > sigma || v > 2. * mean) {
                    mask[i] = 1;
                }
                let add = work.means[col_add[col]];
                let remove = work.means[col_remove[col]];
                for k in 0..3 {
                    sum[k] += add[k] - remove[k];
                }
            }
            let add = row_add[r] * w;
            let remove = row_remove[r] * w;
            for (col, sum) in work.vertical.iter_mut().enumerate() {
                let a = moments(work.cosmic_image[add + col]);
                let b = moments(work.cosmic_image[remove + col]);
                for k in 0..3 {
                    sum[k] += a[k] - b[k];
                }
            }
        }
        // All moments in this pass see the same image, just as the original
        // fully materialized filters did before their rejection loop.
        for (v, &m) in work.cosmic_image.iter_mut().zip(&mask) {
            if m != 0 {
                *v = f64::NAN;
            }
        }
    }
    Ok(mask)
}

fn median(v: &mut [f64]) -> f64 {
    let middle = v.len() / 2;
    *v.select_nth_unstable_by(middle, f64::total_cmp).1
}
pub(super) fn spot(
    data: &[f64],
    shape: [usize; 2],
    user: &[u8],
    groups: &Groups,
    p: &Value,
    c: &Control,
    work: &mut Workspace,
) -> Result<Vec<u8>, String> {
    let robust = p["method"] == "median";
    let multiplier = number(p, "esdmul");
    let mut mask = vec![0; data.len()];
    for (b, pair) in groups.offsets.windows(2).enumerate() {
        if b % 64 == 0 {
            c.check()?;
        }
        let ids = &groups.pixels[pair[0]..pair[1]];
        if ids.len() < 3 {
            continue;
        }
        work.values.clear();
        work.values.extend(ids.iter().map(|&i| data[i as usize]));
        let mean = work.values.iter().sum::<f64>() / ids.len() as f64;
        let std = (work.values.iter().map(|v| v * v).sum::<f64>() / ids.len() as f64 - mean * mean)
            .max(0.)
            .sqrt();
        let (center, spread) = if robust {
            let center = median(&mut work.values);
            work.deviations.clear();
            work.deviations
                .extend(work.values.iter().map(|v| (v - center).abs()));
            let mad = median(&mut work.deviations) * 1.4826;
            (center, if mad <= 0. { std } else { mad })
        } else {
            (mean, std)
        };
        if spread <= 0. {
            continue;
        }
        let threshold = center + multiplier * spread;
        for &i in ids {
            mask[i as usize] = u8::from(data[i as usize] > threshold);
        }
    }
    let sigma = number(p, "smooth_sigma");
    if sigma > 0. {
        smooth(
            &mask,
            shape,
            user,
            sigma,
            number(p, "smooth_threshold"),
            c,
            work,
        )
    } else {
        Ok(mask)
    }
}

fn dilate(
    mask: &[u8],
    shape: [usize; 2],
    iterations: usize,
    c: &Control,
) -> Result<Vec<u8>, String> {
    let [h, w] = shape;
    let mut out = mask.to_vec();
    let mut before = vec![0; mask.len()];
    for _ in 0..iterations {
        c.check()?;
        before.copy_from_slice(&out);
        for row in 0..h {
            for col in 0..w {
                let i = row * w + col;
                out[i] = before[i]
                    | if row > 0 { before[i - w] } else { 0 }
                    | if row + 1 < h { before[i + w] } else { 0 }
                    | if col > 0 { before[i - 1] } else { 0 }
                    | if col + 1 < w { before[i + 1] } else { 0 };
            }
        }
    }
    Ok(out)
}

pub(super) fn smooth(
    mask: &[u8],
    shape: [usize; 2],
    gap: &[u8],
    sigma: f64,
    threshold: f64,
    c: &Control,
    work: &mut Workspace,
) -> Result<Vec<u8>, String> {
    let [h, w] = shape;
    work.gaussian.clear();
    work.gaussian.extend(mask.iter().map(|&v| v as f32));
    let reach = if gap.iter().any(|&v| v != 0) {
        let deep = dilate(mask, shape, (sigma * 3.).ceil().max(1.) as usize, c)?;
        for (i, &v) in gap.iter().enumerate() {
            if v != 0 {
                work.gaussian[i] = deep[i] as f32;
            }
        }
        Some(dilate(
            mask,
            shape,
            sigma.round_ties_even().max(1.) as usize,
            c,
        )?)
    } else {
        None
    };
    let radius = (sigma * 4. + 0.5).floor() as isize;
    let mut kernel: Vec<_> = (-radius..=radius)
        .map(|x| (-0.5 * (x as f64 / sigma).powi(2)).exp())
        .collect();
    let sum = kernel.iter().sum::<f64>();
    for k in &mut kernel {
        *k /= sum;
    }
    work.filtered.resize(mask.len(), 0.);
    work.sums.resize(w, 0.);
    // Vertical taps read contiguous rows; each pixel retains tap/sum order.
    for r in 0..h {
        if r % 32 == 0 {
            c.check()?;
        }
        work.sums.fill(0.);
        for (d, &k) in (-radius..=radius).zip(&kernel) {
            let start = reflect(r as isize + d, h) * w;
            for (sum, &v) in work.sums.iter_mut().zip(&work.gaussian[start..start + w]) {
                *sum += v as f64 * k;
            }
        }
        for (out, &v) in work.filtered[r * w..(r + 1) * w].iter_mut().zip(&work.sums) {
            *out = v as f32;
        }
    }
    std::mem::swap(&mut work.gaussian, &mut work.filtered);
    let padding = kernel.len() - 1;
    work.row.resize(w + padding, 0.);
    let columns: Vec<_> = (0..w + padding)
        .map(|v| reflect(v as isize - radius, w))
        .collect();
    for r in 0..h {
        if r % 32 == 0 {
            c.check()?;
        }
        let row = &work.gaussian[r * w..(r + 1) * w];
        for (v, &col) in work.row.iter_mut().zip(&columns) {
            *v = row[col];
        }
        for (out, window) in work.filtered[r * w..(r + 1) * w]
            .iter_mut()
            .zip(work.row.windows(kernel.len()))
        {
            *out = window
                .iter()
                .zip(&kernel)
                .map(|(&v, &k)| v as f64 * k)
                .sum::<f64>() as f32;
        }
    }
    Ok(work
        .filtered
        .iter()
        .enumerate()
        .map(|(i, &v)| {
            u8::from(
                v > threshold as f32 && reach.as_ref().is_none_or(|r| r[i] != 0 && gap[i] == 0),
            )
        })
        .collect())
}
