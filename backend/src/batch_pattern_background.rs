//! Apply the actual Integration pattern pipeline to every Batch row. The
//! unmodified series remains the source; fitted and loaded backgrounds share
//! the same subtraction, ROI, interpolation and axis rules as the pattern view.
use crate::{
    control::Control,
    pattern::{Curve, Patterns},
    series::Series,
};
use std::{collections::HashMap, sync::Arc};

pub(crate) fn active(patterns: &Patterns) -> bool {
    patterns.background.enabled
        || patterns.background_uid.is_some()
        || patterns.anonymous_background.is_some()
}
/// Changes to ordinary overlay colors, names or visibility do not refit a
/// series. The designated background's actual values and transforms do.
pub(crate) fn changed(before: &Patterns, after: &Patterns) -> bool {
    let before_overlay = before
        .overlays
        .iter()
        .find(|o| Some(&o.uid) == before.background_uid.as_ref());
    let after_overlay = after
        .overlays
        .iter()
        .find(|o| Some(&o.uid) == after.background_uid.as_ref());
    let same_overlay = match (before_overlay, after_overlay) {
        (None, None) => true,
        (Some(a), Some(b)) => {
            a.data == b.data
                && a.scale == b.scale
                && a.offset == b.offset
                && a.batch_source == b.batch_source
        }
        _ => false,
    };
    before.background != after.background
        || before.background_uid != after.background_uid
        || before.anonymous_background != after.anonymous_background
        || !same_overlay
        || (before.unit != after.unit && (active(before) || active(after)))
}
impl Series {
    pub(crate) fn apply_pattern_background(
        &mut self,
        patterns: &Patterns,
        control: &Control,
    ) -> Result<(), String> {
        if !active(patterns) {
            return Err("Enable a background in the Integration pattern view first.".into());
        }
        let unit = &patterns.unit;
        let axis = self.profile(0, unit)?.x;
        let columns: HashMap<_, _> = axis
            .iter()
            .enumerate()
            .map(|(i, x)| (x.to_bits(), i))
            .collect();
        if columns.len() != axis.len() {
            return Err("Pattern background needs distinct radial samples.".into());
        }
        if patterns.background.enabled
            && axis
                .len()
                .checked_mul((patterns.background.order + 1).pow(2))
                .is_none_or(|n| n > 200_000_000)
        {
            return Err("Background polynomial exceeds the interactive fitting limit; reduce order or bin count.".into());
        }
        let mut fit = patterns.clone();
        // Only the designated background overlay participates in this pipeline.
        // Keep its scale, offset and recorded wavelength, but omit legend curves.
        fit.overlays
            .retain(|o| Some(&o.uid) == fit.background_uid.as_ref());
        for overlay in &mut fit.overlays {
            overlay.visible = false;
        }
        let n = self.x.len();
        let mut background = vec![0.0; self.data.len()];
        let row_fit = RowFit {
            series: self,
            unit,
            columns: &columns,
            control,
        };
        let mut prepared = None;
        // Prepare on the actual first-row pipeline, including ROI/interpolation.
        // All workers share this immutable decomposition, never a fitted curve.
        control.publish(serde_json::json!({"running":true,"current":0,"total":self.count(),"label":"Applying pattern background to batch"}));
        let coverage = row_fit.apply(0, &mut background[..n], &mut fit, &mut prepared)?;
        crate::background_workers::groups::<4, _, _, _>(
            &mut background[n..],
            n,
            1,
            control,
            "Applying pattern background to batch",
            || (fit.clone(), prepared.clone()),
            |row, output, (fit, prepared)| {
                let mut raw = Vec::with_capacity(output.len() / n);
                for i in row..row + output.len() / n {
                    fit.ingest(self.profile(i, unit)?, unit, "Batch pattern", None, false);
                    raw.push(fit.raw.as_ref().unwrap().as_ref().clone());
                }
                let curves = fit.build_background_group(&raw, control, prepared)?;
                for (i, (curve, values)) in
                    curves.iter().zip(output.chunks_exact_mut(n)).enumerate()
                {
                    if row_fit.store(row + i, values, curve)? != coverage {
                        return Err(
                            "Pattern background coverage differs between Batch frames.".into()
                        );
                    }
                }
                Ok(())
            },
        )?;
        control.check()?;
        if self.normalized {
            let [start, stop] = self.normalization;
            let means: Vec<_> = self
                .raw
                .chunks_exact(n)
                .map(|row| row[start..stop].iter().sum::<f64>() / (stop - start) as f64)
                .collect();
            for (row, mean) in background.chunks_exact_mut(n).zip(&means) {
                let factor = means[self.reference] / mean;
                for value in row {
                    *value /= factor;
                }
            }
        }
        let first = coverage[0];
        let last = *coverage.last().unwrap();
        let mut edges = [self.x[first], self.x[last]];
        edges.sort_by(f64::total_cmp);
        self.raw_background = Some(Arc::new(background));
        self.batch_background.parameters = crate::batch_background::Parameters {
            smoothing: patterns.background.smoothing,
            iterations: patterns.background.iterations,
            order: patterns.background.order,
        };
        self.batch_background.extracted = Some(self.batch_background.parameters.clone());
        self.batch_background.parameters_unit = Some(unit.clone());
        self.batch_background.pattern_settings = true;
        self.batch_background.subtract = true;
        self.batch_background.cut = coverage.len() != n;
        self.batch_background.range = Some(edges);
        self.normalize(self.normalized, self.normalization, self.reference)
    }
}

struct RowFit<'a> {
    series: &'a Series,
    unit: &'a str,
    columns: &'a HashMap<u64, usize>,
    control: &'a Control,
}
impl RowFit<'_> {
    fn apply(
        &self,
        row: usize,
        output: &mut [f64],
        fit: &mut Patterns,
        prepared: &mut Option<Arc<crate::background_fit::ChebyshevFit>>,
    ) -> Result<Vec<usize>, String> {
        self.control.check()?;
        fit.ingest(
            self.series.profile(row, self.unit)?,
            self.unit,
            "Batch pattern",
            None,
            false,
        );
        let corrected = fit.build_background_row(self.control, prepared)?;
        self.store(row, output, &corrected)
    }
    fn store(
        &self,
        row: usize,
        output: &mut [f64],
        corrected: &Curve,
    ) -> Result<Vec<usize>, String> {
        let mut indices = Vec::with_capacity(corrected.x.len());
        for (&x, &y) in corrected.x.iter().zip(corrected.y.iter()) {
            let col = *self
                .columns
                .get(&x.to_bits())
                .ok_or("Pattern background changed the source radial grid.")?;
            if !y.is_finite() {
                return Err("Pattern background produced nonfinite intensities.".into());
            }
            output[col] = self.series.data[row * output.len() + col] - y;
            indices.push(col);
        }
        indices.sort_unstable();
        if indices.len() < 2 || indices.last().unwrap() - indices[0] + 1 != indices.len() {
            return Err(
                "Pattern background must cover at least two consecutive source samples.".into(),
            );
        }
        Ok(indices)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{pattern::Overlay, series::Entry};

    #[test]
    fn grouped_batch_backgrounds_match_scalar_rows_bit_for_bit() {
        let control = Control::default();
        let bins = 97;
        let count = 13;
        for (source_unit, fit_unit) in [("d_A", "d_A"), ("2th_deg", "q_A^-1"), ("q_A^-1", "q_A^-1")]
        {
            let x: Vec<_> = (0..bins)
                .map(|i| {
                    crate::pattern::convert_coordinate(
                        1. + i as f64 * 0.1,
                        "q_A^-1",
                        source_unit,
                        4e-11,
                    )
                })
                .collect();
            let data: Vec<_> = (0..count * bins)
                .map(|i| 100. + (i / bins) as f64 * 7. + (i as f64 * 0.13).sin().abs() * 50.)
                .collect();
            let mut series = Series::new(
                x,
                data,
                source_unit.into(),
                Some(4e-11),
                (0..count)
                    .map(|frame| Entry {
                        path: String::new(),
                        frame,
                    })
                    .collect(),
                vec![],
                count,
            )
            .unwrap();
            let source = series.raw.clone();
            let axis = series.profile(0, fit_unit).unwrap().x;
            let columns = axis
                .iter()
                .enumerate()
                .map(|(i, x)| (x.to_bits(), i))
                .collect();
            let mut patterns = Patterns::default();
            patterns.unit = fit_unit.into();
            patterns.background.enabled = true;
            patterns.background.order = 5;
            patterns.background.iterations = 11;
            let mut range = [axis[10], axis[85]];
            range.sort_by(f64::total_cmp);
            patterns.background.range = Some(range);
            patterns.background_uid = Some("reference".into());
            patterns.overlays.push(Overlay {
                uid: "reference".into(),
                name: "Background".into(),
                visible: false,
                color: "#ffffff".into(),
                scale: 1.7,
                offset: 0.3,
                data: Arc::new(Curve {
                    x: axis,
                    y: Arc::new(vec![2.5; bins]),
                    sigma: None,
                    spread: None,
                }),
                batch_source: None,
            });
            let mut expected = vec![0.; count * bins];
            let reference = RowFit {
                series: &series,
                unit: fit_unit,
                columns: &columns,
                control: &control,
            };
            let mut fit = patterns.clone();
            let mut prepared = None;
            for (row, values) in expected.chunks_exact_mut(bins).enumerate() {
                reference
                    .apply(row, values, &mut fit, &mut prepared)
                    .unwrap();
            }
            series
                .apply_pattern_background(&patterns, &control)
                .unwrap();
            assert!(
                series
                    .raw_background
                    .as_ref()
                    .unwrap()
                    .iter()
                    .zip(expected)
                    .all(|(a, b)| a.to_bits() == b.to_bits())
            );
            assert!(Arc::ptr_eq(&source, &series.raw));
        }
    }
}
