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
        crate::background_workers::rows(
            &mut background[n..],
            n,
            1,
            control,
            "Applying pattern background to batch",
            || (fit.clone(), prepared.clone()),
            |row, output, (fit, prepared)| {
                if row_fit.apply(row, output, fit, prepared)? != coverage {
                    return Err("Pattern background coverage differs between Batch frames.".into());
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
        let value = fit
            .build_background_row(self.control, prepared)?
            .ok_or("Pattern background produced no curve.")?;
        let corrected = Curve::from_json(&value)?;
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
