//! Cubic B-spline zoom with mirror prefilter, matching scipy.ndimage order=3.
fn coefficients(values: &mut [f64]) {
    let n = values.len();
    if n < 2 {
        return;
    }
    let z = 3.0_f64.sqrt() - 2.0;
    for v in values.iter_mut() {
        *v *= 6.0;
    }
    let mut sum = values[0] + z.powi((n - 1) as i32) * values[n - 1];
    let mut zn = z;
    let mut z2n = z.powi((2 * n - 3) as i32);
    for &v in &values[1..n - 1] {
        sum += (zn + z2n) * v;
        zn *= z;
        z2n /= z;
    }
    values[0] = sum / (1.0 - z.powi((2 * n - 2) as i32));
    for i in 1..n {
        values[i] += z * values[i - 1];
    }
    values[n - 1] = z / (z * z - 1.0) * (z * values[n - 2] + values[n - 1]);
    for i in (0..n - 1).rev() {
        values[i] = z * (values[i + 1] - values[i]);
    }
}
fn mirror(index: isize, n: usize) -> usize {
    if n == 1 {
        return 0;
    }
    let period = 2 * (n - 1) as isize;
    let i = index.rem_euclid(period);
    if i >= n as isize {
        (period - i) as usize
    } else {
        i as usize
    }
}
fn weight(x: f64) -> f64 {
    let x = x.abs();
    if x < 1.0 {
        2.0 / 3.0 - x * x + 0.5 * x * x * x
    } else if x < 2.0 {
        (2.0 - x).powi(3) / 6.0
    } else {
        0.0
    }
}
pub(crate) fn zoom(data: &[f64], [rows, cols]: [usize; 2], factor: usize, mask: bool) -> Vec<f64> {
    if factor == 1 {
        return data.to_vec();
    }
    let min = data
        .iter()
        .filter(|x| x.is_finite())
        .copied()
        .fold(f64::INFINITY, f64::min);
    let min = if min.is_finite() { min } else { 0.0 };
    let mut coefficients_data: Vec<_> = data
        .iter()
        .map(|v| if v.is_finite() { *v } else { min })
        .collect();
    // SciPy filters axes in order, retaining double-precision coefficients.
    for col in 0..cols {
        let mut v: Vec<_> = (0..rows)
            .map(|r| coefficients_data[r * cols + col])
            .collect();
        coefficients(&mut v);
        for r in 0..rows {
            coefficients_data[r * cols + col] = v[r];
        }
    }
    for row in coefficients_data.chunks_exact_mut(cols) {
        coefficients(row);
    }
    let (outrows, outcols) = (rows * factor, cols * factor);
    let mut out = vec![0.0; outrows * outcols];
    for r in 0..outrows {
        let y = if outrows > 1 {
            r as f64 * (rows - 1) as f64 / (outrows - 1) as f64
        } else {
            0.0
        };
        for c in 0..outcols {
            let x = if outcols > 1 {
                c as f64 * (cols - 1) as f64 / (outcols - 1) as f64
            } else {
                0.0
            };
            if mask
                && !data[(y + 0.5).floor() as usize * cols + (x + 0.5).floor() as usize].is_finite()
            {
                out[r * outcols + c] = f64::NAN;
                continue;
            }
            let mut sum = 0.0;
            for yy in y.floor() as isize - 1..=y.floor() as isize + 2 {
                for xx in x.floor() as isize - 1..=x.floor() as isize + 2 {
                    sum += coefficients_data[mirror(yy, rows) * cols + mirror(xx, cols)]
                        * weight(y - yy as f64)
                        * weight(x - xx as f64);
                }
            }
            out[r * outcols + c] = sum;
        }
    }
    out
}
