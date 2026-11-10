//! Qt Batch backgrounds are a separate, reversible overview operation. The
//! scientific matrix stays un-subtracted; Integration keeps its own settings.
use crate::{control::Control, display::Raster, series::Series};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Parameters {
    pub smoothing: f64,
    pub iterations: usize,
    pub order: usize,
}
impl Default for Parameters {
    fn default() -> Self {
        Self {
            smoothing: 0.1,
            iterations: 150,
            order: 50,
        }
    }
}
impl Parameters {
    fn validate(&self) -> Result<(), String> {
        if !self.smoothing.is_finite()
            || !(1e-6..=1e7).contains(&self.smoothing)
            || !(1..=99999).contains(&self.iterations)
            || !(1..=1000).contains(&self.order)
        {
            return Err(
                "Choose a positive smooth width, 1–99999 iterations and polynomial order 1–1000."
                    .into(),
            );
        }
        Ok(())
    }
}
#[derive(Clone, Default, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub(crate) struct State {
    pub parameters: Parameters,
    pub extracted: Option<Parameters>,
    /// Inclusive sample centers, always in the stored source unit.
    pub range: Option<[f64; 2]>,
    pub subtract: bool,
    pub cut: bool,
    pub parameters_unit: Option<String>,
    pub pattern_settings: bool,
    #[serde(skip)]
    view: Option<View>,
}
#[derive(Clone)]
struct View {
    data: Arc<Vec<f64>>,
    raster: Raster,
    bins: [usize; 2],
}
/// The xypattern Cython/PhaseSmith Bruckner scan, with cancellation checkpoints
/// inside a long row. Padding stays fixed for the entire extraction; calling
/// the ordinary smoother in iteration chunks would change those boundaries.
pub(crate) fn smooth_cancellable(
    y: &[f64],
    points: usize,
    iterations: usize,
    control: &Control,
) -> Result<Vec<f64>, String> {
    control.check()?;
    if y.iter().any(|v| !v.is_finite()) {
        return Err("Background input samples must be finite.".into());
    }
    let end = y.len().saturating_sub(points.saturating_add(2));
    if points >= end {
        return Ok(y.to_vec());
    }
    let window = points * 2 + 1;
    let mut extended = Vec::new();
    extended
        .try_reserve_exact(y.len() + points * 2)
        .map_err(|_| "Cannot allocate the background smoothing buffer.")?;
    extended.resize(points, y[0]);
    extended.extend_from_slice(y);
    extended.resize(y.len() + points * 2, y[y.len() - 1]);
    for _ in 0..iterations {
        control.check()?;
        let mut sum = 0.0;
        for value in &extended[..window] {
            sum += value;
        }
        let mut average = sum / window as f64;
        for i in points..end {
            if i.is_multiple_of(4096) {
                control.check()?;
            }
            let outgoing = extended[i - points];
            let incoming = extended[i + points + 1];
            if extended[i] > average {
                let old = extended[i];
                extended[i] = average;
                average += ((average - old) + (incoming - outgoing)) / window as f64;
            } else {
                average += (incoming - outgoing) / window as f64;
            }
        }
    }
    Ok(extended[points..points + y.len()].to_vec())
}
impl Series {
    pub fn background_metadata(&self) -> Value {
        json!({"parameters":self.batch_background.parameters,"extracted":self.batch_background.extracted,
            "range":self.batch_background.range,"unit":self.unit,"available":self.background.is_some(),
            "parametersUnit":self.batch_background.parameters_unit.as_deref().unwrap_or(&self.unit),"patternSettings":self.batch_background.pattern_settings,
            "subtract":self.batch_background.subtract,"cut":self.batch_background.cut,
            "stale":self.background.is_some() && self.batch_background.extracted.as_ref().is_some_and(|p|p != &self.batch_background.parameters)})
    }
    pub fn background_bins(&self) -> [usize; 2] {
        self.batch_background
            .view
            .as_ref()
            .map_or([0, self.x.len()], |v| v.bins)
    }
    pub fn background_raster(&self) -> &Raster {
        self.batch_background
            .view
            .as_ref()
            .map_or(&self.raster, |v| &v.raster)
    }
    pub fn background_data(&self) -> &[f64] {
        self.batch_background
            .view
            .as_ref()
            .map_or(&self.data, |v| &v.data)
    }
    pub fn configure_batch_background(&mut self, args: &Value) -> Result<(), String> {
        let mut state = self.batch_background.clone();
        if let Some(parameters) = args.get("parameters") {
            state.parameters =
                serde_json::from_value(parameters.clone()).map_err(|e| e.to_string())?;
            if state.parameters != self.batch_background.parameters {
                state.pattern_settings = false;
            }
        }
        state.parameters.validate()?;
        if let Some(value) = args.get("range") {
            state.range = if value.is_null() {
                None
            } else {
                let range: [f64; 2] = serde_json::from_value(value.clone())
                    .map_err(|_| "Background range needs two finite coordinates.")?;
                if range.iter().any(|x| !x.is_finite()) || range[0] >= range[1] {
                    return Err("Background minimum must be below maximum.".into());
                }
                let unit = args["unit"].as_str().unwrap_or(&self.unit);
                if !["2th_deg", "q_A^-1", "q_nm^-1", "d_A"].contains(&unit) {
                    return Err("Choose a supported background range unit.".into());
                }
                // Conversion is validated by the same source-axis path used for
                // profile selection, including stored-only batches without λ.
                let axis = self.profile(0, unit)?.x;
                let ids: Vec<_> = axis
                    .iter()
                    .enumerate()
                    .filter_map(|(i, &x)| (x >= range[0] && x <= range[1]).then_some(i))
                    .collect();
                if ids.len() < 2 {
                    return Err("Background range must include at least two stored samples.".into());
                }
                let mut edges = [self.x[*ids.first().unwrap()], self.x[*ids.last().unwrap()]];
                edges.sort_by(f64::total_cmp);
                Some(edges)
            };
        }
        for (key, slot) in [("subtract", &mut state.subtract), ("cut", &mut state.cut)] {
            if let Some(value) = args.get(key) {
                *slot = value
                    .as_bool()
                    .ok_or("Background display flags must be boolean.")?;
            }
        }
        if state.subtract && self.background.is_none() {
            return Err("Extract the batch background before subtracting it.".into());
        }
        if state.cut && state.range.is_none() {
            return Err("Choose a background range before cutting the overview.".into());
        }
        self.batch_background = state;
        self.refresh_batch_background()
    }
    pub fn extract_batch_background(&mut self, control: &Control) -> Result<(), String> {
        let parameters = self.batch_background.parameters.clone();
        parameters.validate()?;
        if self.x.len() < 2 {
            return Err("Background extraction needs at least two distinct radial samples.".into());
        }
        // xypattern preserves the source sample order, including descending d.
        // Bruckner's one-sided in-place scan makes reversing that order change
        // the result, so use the stored axis exactly as Qt BatchModel does.
        let fit_axis = self
            .profile(
                0,
                self.batch_background
                    .parameters_unit
                    .as_deref()
                    .unwrap_or(&self.unit),
            )?
            .x;
        let x = fit_axis.as_slice();
        let ascending = x[1] > x[0];
        if x.windows(2)
            .any(|w| w[0] == w[1] || (w[1] > w[0]) != ascending)
        {
            return Err("Background extraction needs a strictly monotonic radial axis.".into());
        }
        let points = (parameters.smoothing / (x[1] - x[0])).abs() as usize;
        if points > 2_000_000 {
            return Err(
                "Background smoothing window exceeds the bounded working allocation.".into(),
            );
        }
        // The SVD is the only uninterruptible stage. Bound its work as well as
        // pattern::chebyshev's allocation before starting any frame.
        if x.len()
            .checked_mul((parameters.order + 1).pow(2))
            .is_none_or(|n| n > 200_000_000)
        {
            return Err("Background polynomial exceeds the interactive fitting limit; reduce order or bin count.".into());
        }
        control.check()?;
        let prepared = crate::background_fit::ChebyshevFit::new(x, parameters.order)?;
        let mut background = vec![0.0; self.data.len()];
        crate::background_workers::rows(
            &mut background,
            x.len(),
            0,
            control,
            "Extracting batch background",
            || (),
            |index, output, _| {
                let row = &self.data[index * x.len()..(index + 1) * x.len()];
                let smoothed = smooth_cancellable(row, points, parameters.iterations, control)?;
                control.check()?;
                output.copy_from_slice(&prepared.fit(&smoothed)?);
                Ok(())
            },
        )?;
        control.check()?;
        // Qt extracts on the current (possibly normalized) scale. Store a
        // source-scale background so future normalization never compounds.
        // Fitting raw and then scaling is not numerically interchangeable with
        // xypattern's in-place smoother, particularly for a zero-point window.
        if self.normalized {
            let [start, stop] = self.normalization;
            let means: Vec<_> = self
                .raw
                .chunks_exact(x.len())
                .map(|row| row[start..stop].iter().sum::<f64>() / (stop - start) as f64)
                .collect();
            for (row, mean) in background.chunks_exact_mut(x.len()).zip(&means) {
                let factor = means[self.reference] / mean;
                for value in row {
                    *value /= factor;
                }
            }
        }
        // Commit only a complete extraction. The intensity source stays exact.
        self.raw_background = Some(Arc::new(background));
        self.batch_background.extracted = Some(parameters);
        self.batch_background.pattern_settings = false;
        self.normalize(self.normalized, self.normalization, self.reference)
    }
    pub fn refresh_batch_background(&mut self) -> Result<(), String> {
        let state = &self.batch_background;
        state.parameters.validate()?;
        if let Some(p) = &state.extracted {
            p.validate()?;
        }
        if state.subtract
            && self
                .background
                .as_ref()
                .is_none_or(|v| v.len() != self.data.len())
        {
            return Err("Batch background is missing or has the wrong shape.".into());
        }
        let bins = if state.cut {
            let range = state.range.ok_or("Background cut has no range.")?;
            if range.iter().any(|v| !v.is_finite()) || range[0] >= range[1] {
                return Err("Invalid stored background range.".into());
            }
            let ids: Vec<_> = self
                .x
                .iter()
                .enumerate()
                .filter_map(|(i, &x)| (x >= range[0] && x <= range[1]).then_some(i))
                .collect();
            if ids.len() < 2 || ids.last().unwrap() - ids[0] + 1 != ids.len() {
                return Err(
                    "Background cut must contain at least two consecutive source bins.".into(),
                );
            }
            [ids[0], ids.last().unwrap() + 1]
        } else {
            [0, self.x.len()]
        };
        let columns = self.x.len();
        self.batch_background.view = if state.subtract || state.cut {
            let values: Vec<_> = (0..self.count())
                .flat_map(|row| (bins[0]..bins[1]).map(move |col| row * columns + col))
                .map(|i| {
                    self.data[i]
                        - if state.subtract {
                            self.background.as_ref().unwrap()[i]
                        } else {
                            0.0
                        }
                })
                .collect();
            let raster = Raster::image(&values, [self.count(), bins[1] - bins[0]]);
            Some(View {
                data: Arc::new(values),
                raster,
                bins,
            })
        } else {
            None
        };
        Ok(())
    }
    pub fn restore_batch_background(&mut self, value: &Value) -> Result<(), String> {
        if !value.is_null() {
            self.batch_background =
                serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
        }
        self.refresh_batch_background()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::series::Entry;
    fn cases() -> Value {
        serde_json::from_str(include_str!("../tests/fixtures/batch_background_qt.json")).unwrap()
    }
    fn series(case: &Value) -> Series {
        let mut s = Series::new(
            serde_json::from_value(case["x"].clone()).unwrap(),
            serde_json::from_value(case["data"].clone()).unwrap(),
            case["unit"].as_str().unwrap().into(),
            None,
            (0..3)
                .map(|frame| Entry {
                    path: String::new(),
                    frame,
                })
                .collect(),
            vec![],
            3,
        )
        .unwrap();
        s.sigma = Some(Arc::new(s.data.iter().map(|y| y.sqrt()).collect()));
        s.raw_sigma = s.sigma.clone();
        s.configure_batch_background(&json!({"parameters":case["parameters"]}))
            .unwrap();
        s
    }
    fn close(actual: &[f64], expected: &[f64]) {
        assert_eq!(actual.len(), expected.len());
        for (i, (&a, &b)) in actual.iter().zip(expected).enumerate() {
            assert!(
                (a - b).abs() < 2e-9 * b.abs().max(1.0),
                "sample {i}: {a} != {b}"
            );
        }
    }
    #[test]
    fn qt_backgrounds_match_including_descending_d_and_default_polynomial_order() {
        for case in cases()["cases"].as_array().unwrap() {
            let mut s = series(case);
            s.extract_batch_background(&Control::default()).unwrap();
            let expected: Vec<f64> = serde_json::from_value(case["background"].clone()).unwrap();
            close(s.background.as_ref().unwrap(), &expected);
            assert_eq!(s.raw, s.data);
        }
    }
    #[test]
    fn normalization_subtraction_and_cutting_never_compound_or_change_source_axis_and_std() {
        for case in cases()["cases"].as_array().unwrap() {
            let mut s = series(case);
            let original = s.data.clone();
            let original_std = s.sigma.clone();
            let axis = s.x.clone();
            s.normalize(true, [4, 70], 1).unwrap();
            s.extract_batch_background(&Control::default()).unwrap();
            let normalized = s.data.clone();
            let normalized_std = s.sigma.clone();
            let qt_data: Vec<f64> =
                serde_json::from_value(case["normalized_data"].clone()).unwrap();
            let qt_background: Vec<f64> =
                serde_json::from_value(case["normalized_background"].clone()).unwrap();
            close(&normalized, &qt_data);
            close(s.background.as_ref().unwrap(), &qt_background);
            s.configure_batch_background(&json!({"subtract":true}))
                .unwrap();
            let subtracted = s.background_data().to_vec();
            let expected: Vec<_> = s
                .data
                .iter()
                .zip(s.background.as_ref().unwrap().iter())
                .map(|(y, b)| y - b)
                .collect();
            assert_eq!(subtracted, expected);
            s.extract_batch_background(&Control::default()).unwrap();
            assert_eq!(s.background_data(), subtracted);
            for _ in 0..3 {
                s.configure_batch_background(&json!({"subtract":false}))
                    .unwrap();
                assert_eq!(s.background_data(), normalized.as_slice());
                s.configure_batch_background(&json!({"subtract":true}))
                    .unwrap();
                assert_eq!(s.background_data(), subtracted);
            }
            let mut edges = [axis[10], axis[80]];
            edges.sort_by(f64::total_cmp);
            s.configure_batch_background(&json!({"range":edges,"cut":true}))
                .unwrap();
            assert_eq!(s.background_bins(), [10, 81]);
            assert_eq!(s.background_data().len(), 3 * 71);
            assert_eq!(&s.background_data()[..71], &subtracted[10..81]);
            assert_eq!(s.sigma, normalized_std);
            assert_eq!(s.x, axis);
            s.normalize(false, [4, 70], 1).unwrap();
            assert_eq!(s.data, original);
            assert_eq!(s.sigma, original_std);
            s.configure_batch_background(&json!({"subtract":false,"cut":false}))
                .unwrap();
            assert_eq!(s.background_data(), original.as_slice());
        }
    }
    #[test]
    fn saved_background_state_reopens_and_normalization_restores_original_f64_values() {
        let case = &cases()["cases"][0];
        let mut s = series(case);
        s.extract_batch_background(&Control::default()).unwrap();
        s.normalize(true, [8, 60], 1).unwrap();
        s.configure_batch_background(&json!({"subtract":true,"range":[2.0,8.0],"cut":true}))
            .unwrap();
        let file = tempfile::NamedTempFile::new().unwrap();
        s.save(file.path()).unwrap();
        let mut restored = Series::load(file.path()).unwrap();
        assert_eq!(restored.background_metadata(), s.background_metadata());
        assert_eq!(restored.background_data(), s.background_data());
        assert_eq!(restored.data, s.data);
        assert_eq!(restored.sigma, s.sigma);
        restored
            .normalize(false, restored.normalization, restored.reference)
            .unwrap();
        assert_eq!(restored.raw, restored.data);
        assert_eq!(restored.data, s.raw);
        assert_eq!(restored.sigma, s.raw_sigma);
    }
    #[test]
    fn cancelled_or_failed_extraction_never_publishes_a_partial_background() {
        let mut s = series(&cases()["cases"][0]);
        s.extract_batch_background(&Control::default()).unwrap();
        let background = s.raw_background.clone();
        let control = Control::default();
        control.cancel();
        assert!(
            s.extract_batch_background(&control)
                .unwrap_err()
                .contains("cancelled")
        );
        assert_eq!(s.raw_background, background);
        Arc::make_mut(&mut s.data)[200] = f64::NAN;
        assert!(s.extract_batch_background(&Control::default()).is_err());
        assert_eq!(s.raw_background, background);
    }
}
