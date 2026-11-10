//! Optional display heuristic, independent of units, baselines and old offsets.
pub(crate) const DEFAULT_SPACING: f64 = 100.0;

/// Use 10% of the largest scaled finite peak-to-peak range, rounded up to a
/// readable 1/2/5 step. Some peak overlap is intentional in a waterfall plot;
/// this is a starting point, not an optimal/no-overlap guarantee.
pub(crate) fn estimate<'a>(curves: impl IntoIterator<Item = (&'a [f64], f64)>) -> f64 {
    let mut spacing = 0.0_f64;
    for (y, scale) in curves {
        let (mut low, mut high) = (f64::INFINITY, f64::NEG_INFINITY);
        for &v in y.iter().filter(|v| v.is_finite()) {
            low = low.min(v);
            high = high.max(v);
        }
        if low < high && scale != 0.0 {
            // Divide before subtracting so opposite large endpoints don't overflow.
            spacing = spacing.max((high / 10.0 - low / 10.0) * scale.abs());
        }
    }
    if spacing == 0.0 {
        return DEFAULT_SPACING;
    }
    let spacing = spacing.clamp(0.01, 100_000.0);
    let base = 10.0_f64.powf(spacing.log10().floor());
    let ratio = spacing / base;
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
    fn spacing_tracks_scaled_ranges_without_baseline_or_outdated_offsets() {
        assert_eq!(estimate([(&[0., 20., 100.][..], 1.)]), 10.);
        assert_eq!(estimate([(&[1000., 1020., 1100.][..], 1.)]), 10.);
        assert_eq!(estimate([(&[-20., -10., 0.][..], 2.)]), 5.);
        assert_eq!(estimate([(&[0., 1.][..], 1.)]), 0.1);
        assert_eq!(estimate([(&[0., 1.][..], 1.), (&[0., 7.][..], 10.)]), 10.);
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
            2.
        );
        assert_eq!(estimate([(&[-1e308, 1e308][..], 1e7)]), 100_000.);
        assert_eq!(estimate([(&[0., 1e-12][..], 1.)]), 0.01);
    }
}
