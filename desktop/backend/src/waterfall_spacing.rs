//! Optional display heuristic, independent of units, baselines and old offsets.
pub(crate) const DEFAULT_SPACING: f64 = 100.0;

/// Use 10% of mean intensity above each curve's minimum, after its scale,
/// averaged equally across nonflat curves and rounded up to a readable 1/2/5
/// step. A narrow high peak contributes only in proportion to its sample count.
/// This display heuristic ignores constant baselines and old waterfall offsets.
pub(crate) fn estimate<'a>(curves: impl IntoIterator<Item = (&'a [f64], f64)>) -> f64 {
    let mut spacing = 0.0_f64;
    let mut curves_used = 0.0;
    for (y, scale) in curves {
        if !scale.is_finite() || scale == 0.0 {
            continue;
        }
        let (mut low, mut high) = (f64::INFINITY, f64::NEG_INFINITY);
        for &v in y.iter().filter(|v| v.is_finite()) {
            low = low.min(v);
            high = high.max(v);
        }
        if low < high {
            let range = high - low;
            let mut samples = 0.0;
            let mut mean = 0.0;
            for &v in y.iter().filter(|v| v.is_finite()) {
                // Scale before subtracting only when the full range overflows.
                let tenth = if range.is_finite() {
                    (v - low) * 0.1
                } else {
                    v * 0.1 - low * 0.1
                };
                samples += 1.0;
                mean += (tenth - mean) / samples;
            }
            curves_used += 1.0;
            // Weighted accumulation also handles an overflowing scaled mean.
            spacing = spacing * (1.0 - 1.0 / curves_used) + mean * scale.abs() / curves_used;
        }
    }
    if spacing == 0.0 {
        return DEFAULT_SPACING;
    }
    let spacing = spacing.clamp(0.01, 100_000.0);
    let base = 10.0_f64.powf(spacing.log10().floor());
    // A display estimate should not jump a whole step on floating-point noise.
    let ratio = spacing / base / (1.0 + 1e-12);
    let step = if ratio <= 1.0 {
        1.0
    } else if ratio <= 2.0 {
        2.0
    } else if ratio <= 5.0 {
        5.0
    } else {
        10.0
    };
    (base * step).min(100_000.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn spacing_tracks_mean_signal_without_baseline_or_outdated_offsets() {
        assert_eq!(estimate([(&[0., 20., 100.][..], 1.)]), 5.);
        assert_eq!(estimate([(&[1000., 1020., 1100.][..], 1.)]), 5.);
        assert_eq!(estimate([(&[-20., -10., 0.][..], 2.)]), 2.);
        assert_eq!(estimate([(&[0., 1.][..], 1.)]), 0.05);
        assert_eq!(estimate([(&[40.25, 41.25][..], 1.)]), 0.05);
        assert_eq!(estimate([(&[0., 1.][..], 1.), (&[0., 7.][..], 10.)]), 2.);
    }
    #[test]
    fn narrow_peaks_and_longer_curves_do_not_dominate_the_estimate() {
        let mut spike = vec![0.0; 100];
        spike[50] = 1000.0;
        assert_eq!(estimate([(&spike[..], 1.0)]), 1.0);
        let shifted: Vec<_> = spike.iter().map(|v| v + 500.0).collect();
        assert_eq!(estimate([(&shifted[..], 1.0)]), 1.0);
        let long_curve: Vec<_> = (0..100)
            .map(|i| if i % 2 == 0 { 0.0 } else { 20.0 })
            .collect();
        assert_eq!(
            estimate([(&[0.0, 100.0][..], 1.0), (&long_curve[..], 1.0)]),
            5.0
        );
    }
    #[test]
    fn degenerate_nonfinite_and_extreme_curves_keep_bounded_useful_spacing() {
        assert_eq!(estimate([]), DEFAULT_SPACING);
        assert_eq!(estimate([(&[7., 7.][..], 1.)]), DEFAULT_SPACING);
        assert_eq!(estimate([(&[0., 100.][..], 0.)]), DEFAULT_SPACING);
        assert_eq!(
            estimate([(&[f64::NAN, f64::INFINITY][..], 1.)]),
            DEFAULT_SPACING
        );
        assert_eq!(
            estimate([(&[f64::NAN, 0., 20., f64::NEG_INFINITY][..], 1.)]),
            1.
        );
        assert_eq!(estimate([(&[-1e308, 1e308][..], 1e7)]), 100_000.);
        assert_eq!(estimate([(&[0., 1e-12][..], 1.)]), 0.01);
    }
}
