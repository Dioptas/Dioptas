//! Apply the actual Integration pattern pipeline to every Batch row. The
//! unmodified series remains the source; fitted and loaded backgrounds share
//! the same subtraction, ROI, interpolation and axis rules as the pattern view.
use crate::{
    control::Control,
    pattern::{Curve, Patterns},
    series::Series,
};
use serde_json::json;
use std::{collections::HashMap, sync::Arc};

pub(crate) fn active(patterns: &Patterns) -> bool {
    patterns.background.enabled
        || patterns.background_uid.is_some()
        || patterns.anonymous_background.is_some()
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
        let mut coverage: Option<Vec<usize>> = None;
        for row in 0..self.count() {
            control.check()?;
            control.publish(json!({"running":true,"current":row,"total":self.count(),"label":"Applying pattern background to batch"}));
            fit.ingest(self.profile(row, unit)?, unit, "Batch pattern", None, false);
            let value = fit
                .build_background_row(control)?
                .ok_or("Pattern background produced no curve.")?;
            let corrected = Curve::from_json(&value)?;
            let mut indices = Vec::with_capacity(corrected.x.len());
            for (&x, &y) in corrected.x.iter().zip(corrected.y.iter()) {
                let col = *columns
                    .get(&x.to_bits())
                    .ok_or("Pattern background changed the source radial grid.")?;
                if !y.is_finite() {
                    return Err("Pattern background produced nonfinite intensities.".into());
                }
                background[row * n + col] = self.data[row * n + col] - y;
                indices.push(col);
            }
            indices.sort_unstable();
            if indices.len() < 2 || indices.last().unwrap() - indices[0] + 1 != indices.len() {
                return Err(
                    "Pattern background must cover at least two consecutive source samples.".into(),
                );
            }
            if coverage
                .as_ref()
                .is_some_and(|previous| *previous != indices)
            {
                return Err("Pattern background coverage differs between Batch frames.".into());
            }
            coverage = Some(indices);
        }
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
        let coverage = coverage.unwrap();
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
