//! Two-pass mask-only LA Cosmic, matching the bundled cosmics.py 0.4 by
//! Malte Tewes (2010), based on Pieter van Dokkum's Laplacian algorithm.
//! The clean plane is private scratch for the next pass; source counts never change.
use crate::control::Control;
use serde_json::json;

fn mirror(i: isize, n: usize) -> usize {
    if n == 1 {
        return 0;
    }
    let period = 2 * (n as isize - 1);
    let i = i.rem_euclid(period);
    if i < n as isize {
        i as usize
    } else {
        (period - i) as usize
    }
}
fn median(values: &mut [f64]) -> f64 {
    let len = values.len();
    let mid = len / 2;
    let (left, pivot, _) = values.select_nth_unstable_by(mid, f64::total_cmp);
    let upper = *pivot;
    if mid * 2 + 1 == len {
        upper
    } else {
        (left.iter().copied().fold(f64::NEG_INFINITY, f64::max) + upper) / 2.
    }
}
fn median_filter(
    input: &[f64],
    shape: [usize; 2],
    size: usize,
    control: &Control,
) -> Result<Vec<f64>, String> {
    let [h, w] = shape;
    let half = (size / 2) as isize;
    let mut output = vec![0.; input.len()];
    let mut window = [0.; 49];
    for r in 0..h {
        control.check()?;
        for c in 0..w {
            if c.is_multiple_of(256) {
                control.check()?;
            }
            let mut index = 0;
            for dy in -half..=half {
                let row = mirror(r as isize + dy, h) * w;
                for dx in -half..=half {
                    window[index] = input[row + mirror(c as isize + dx, w)];
                    index += 1;
                }
            }
            output[r * w + c] = median(&mut window[..index]);
        }
    }
    Ok(output)
}
fn progress(control: &Control, pass: usize, stage: &str) {
    control.publish(json!({"running":true,"label":"Cosmic removal","current":pass,"total":2,"iteration":pass+1,"stage":stage}));
}
/// Evaluate each replicated subpixel's symmetric-boundary convolution without
/// materializing the four-times-larger image. Rebin in the source's axis order.
fn laplacian(input: &[f64], shape: [usize; 2], row: usize, col: usize) -> f64 {
    let [h, w] = shape;
    let mut corners = [[0.; 2]; 2];
    let kernel = [[0., -1., 0.], [-1., 4., -1.], [0., -1., 0.]];
    for (dy, out) in corners.iter_mut().enumerate() {
        for (dx, v) in out.iter_mut().enumerate() {
            let mut sum = 0.;
            for (ky, k) in kernel.iter().enumerate() {
                // Convolution reverses the source axes. With one pixel of
                // padding, signal.convolve2d's 'symm' clamps the outer sample.
                let r = (2 * row as isize + dy as isize + 1 - ky as isize)
                    .clamp(0, 2 * h as isize - 1) as usize
                    / 2;
                for (kx, &weight) in k.iter().enumerate() {
                    let c = (2 * col as isize + dx as isize + 1 - kx as isize)
                        .clamp(0, 2 * w as isize - 1) as usize
                        / 2;
                    sum += input[r * w + c] * weight;
                }
            }
            *v = if sum < 0. { 0. } else { sum };
        }
    }
    ((corners[0][0] + corners[1][0]) + (corners[0][1] + corners[1][1])) / 2. / 2.
}
fn grow_selected(
    input: &[u8],
    signal: &[f64],
    shape: [usize; 2],
    threshold: f64,
    control: &Control,
) -> Result<Vec<u8>, String> {
    let [h, w] = shape;
    let mut output = vec![0; input.len()];
    for r in 0..h {
        control.check()?;
        for c in 0..w {
            if c.is_multiple_of(1024) {
                control.check()?;
            }
            if signal[r * w + c] <= threshold {
                continue;
            }
            let mut selected = false;
            for rr in r.saturating_sub(1)..=(r + 1).min(h - 1) {
                for cc in c.saturating_sub(1)..=(c + 1).min(w - 1) {
                    selected |= input[rr * w + cc] != 0;
                }
            }
            output[r * w + c] = u8::from(selected);
        }
    }
    Ok(output)
}
fn clean_masked(
    clean: &mut [f64],
    mask: &[u8],
    raw: &[f64],
    shape: [usize; 2],
    background: &mut Option<f64>,
    control: &Control,
) -> Result<(), String> {
    let [h, w] = shape;
    let mut values = [0.; 25];
    for r in 0..h {
        control.check()?;
        for c in 0..w {
            if c.is_multiple_of(256) {
                control.check()?;
            }
            if mask[r * w + c] == 0 {
                continue;
            }
            let mut count = 0;
            for rr in r.saturating_sub(2)..=(r + 2).min(h - 1) {
                for cc in c.saturating_sub(2)..=(c + 2).min(w - 1) {
                    if mask[rr * w + cc] == 0 {
                        values[count] = clean[rr * w + cc];
                        count += 1;
                    }
                }
            }
            // Masked neighbors are excluded throughout, so replacing masked
            // pixels in place is equivalent to the original frozen padded plane.
            clean[r * w + c] = if count > 0 {
                median(&mut values[..count])
            } else {
                if background.is_none() {
                    control.check()?;
                    *background = Some(median(&mut raw.to_vec()));
                    control.check()?;
                }
                background.unwrap()
            };
            if !clean[r * w + c].is_finite() {
                return Err("LA Cosmic cleaning exceeded the finite intensity range.".into());
            }
        }
    }
    Ok(())
}
pub(crate) fn detect(raw: &[f64], shape: [usize; 2], control: &Control) -> Result<Vec<u8>, String> {
    control.check()?;
    if shape.contains(&0)
        || shape[0].checked_mul(shape[1]) != Some(raw.len())
        || raw.len() > 64 * 1024 * 1024
    {
        return Err("LA Cosmic needs a bounded two-dimensional detector plane.".into());
    }
    if raw.iter().any(|v| !v.is_finite()) {
        return Err(
            "LA Cosmic needs finite processed intensities; the image and mask were retained."
                .into(),
        );
    }
    let mut clean = raw.to_vec();
    let mut mask = vec![0; raw.len()];
    let mut background = None;
    let [h, w] = shape;
    for pass in 0..2 {
        progress(control, pass, "Median 5×5 noise model");
        let final_selection = {
            let mut noise = median_filter(&clean, shape, 5, control)?;
            for n in &mut noise {
                *n = (1. / 2.2) * (2.2 * n.max(0.00001) + 100.).sqrt();
            }
            progress(control, pass, "Laplacian signal");
            let mut signal = vec![0.; raw.len()];
            for r in 0..h {
                control.check()?;
                for c in 0..w {
                    if c.is_multiple_of(256) {
                        control.check()?;
                    }
                    let i = r * w + c;
                    signal[i] = laplacian(&clean, shape, r, c) / (2. * noise[i]);
                    if !signal[i].is_finite() || !noise[i].is_finite() {
                        return Err("LA Cosmic exceeded the finite intensity range; the image and mask were retained.".into());
                    }
                }
            }
            progress(control, pass, "Removing extended structure");
            let mut residual = median_filter(&signal, shape, 5, control)?;
            for (r, s) in residual.iter_mut().zip(signal.iter()) {
                *r = s - *r;
            }
            drop(signal);
            progress(control, pass, "Median 3×3 and 7×7 fine structure");
            let compact = {
                let m3 = median_filter(&clean, shape, 3, control)?;
                let m37 = median_filter(&m3, shape, 7, control)?;
                let mut selected = vec![0; raw.len()];
                for i in 0..raw.len() {
                    if i.is_multiple_of(1024) {
                        control.check()?;
                    }
                    let fine = ((m3[i] - m37[i]) / noise[i]).max(0.01);
                    selected[i] = u8::from(residual[i] > 3. && residual[i] / fine > 3.);
                }
                selected
            };
            drop(noise);
            progress(control, pass, "Growing cosmic-ray neighbors");
            let grown = grow_selected(&compact, &residual, shape, 3., control)?;
            grow_selected(&grown, &residual, shape, 3. * 0.3, control)?
        };
        for (m, &v) in mask.iter_mut().zip(&final_selection) {
            *m |= v;
        }
        progress(control, pass, "Cleaning internal pass image");
        clean_masked(&mut clean, &mask, raw, shape, &mut background, control)?;
        control.check()?;
        control.publish(json!({"running":true,"label":"Cosmic removal","current":pass+1,"total":2,"iteration":pass+1,"stage":"Pass complete"}));
    }
    Ok(mask)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cleaning_uses_frozen_unmasked_neighbors_and_full_image_fallback() {
        let raw = (0..25).map(|v| v as f64).collect::<Vec<_>>();
        let control = Control::default();
        let mut clean = raw.clone();
        let mut mask = vec![0; 25];
        mask[0] = 1;
        mask[1] = 1;
        clean_masked(&mut clean, &mask, &raw, [5, 5], &mut None, &control).unwrap();
        assert_eq!(clean[0], 7.); // [2,5,6,7,10,11,12]
        assert_eq!(clean[1], 7.5); // ten valid samples, average of middle two
        let mut all = raw.clone();
        let mut background = None;
        clean_masked(&mut all, &[1; 25], &raw, [5, 5], &mut background, &control).unwrap();
        assert_eq!(all, vec![12.; 25]);
        assert_eq!(background, Some(12.));
    }
}
