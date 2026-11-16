//! Scan arrangement and cached reduction products; source patterns stay immutable.
use crate::{display::Raster, map_math, pattern::Patterns, series::Series};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
    sync::Arc,
};
#[derive(Clone, Serialize, Deserialize, PartialEq)]
pub(crate) struct Roi {
    pub name: String,
    pub min: f64,
    pub max: f64,
    pub reduction: String,
    pub background: bool,
    pub color: String,
}
#[derive(Clone)]
pub(crate) struct Scan {
    pub series: Series,
    pub corrected: Option<CorrectedProfiles>,
    pub background_pending: bool,
    pub dimension: [usize; 2],
    pub snake: bool,
    pub transpose: bool,
    pub flip_horizontal: bool,
    pub flip_vertical: bool,
    // Arrangement is shared until a command changes the local scan.
    pub slots: Arc<Vec<Option<usize>>>,
    pub excluded: BTreeSet<usize>,
    pub rois: Vec<Roi>,
    pub expressions: Vec<(String, String)>,
    pub active: String,
    pub selected: Option<usize>,
    pub selected_slot: Option<usize>,
    pub values: Arc<Vec<f64>>,
    pub indices: Arc<Vec<i64>>,
    pub slot_indices: Arc<Vec<i64>>,
    pub raster: Raster,
    pub layers: Arc<BTreeMap<String, Vec<f64>>>,
    pub normalization_coordinates: Value,
    pub pending: BTreeMap<String, (u64, std::time::SystemTime)>,
}
pub(crate) fn dimensions(n: usize) -> Vec<[usize; 2]> {
    let mut dims = vec![];
    for i in 1..=((n as f64 + 1.0).sqrt().floor() as usize) {
        if n.is_multiple_of(i) {
            dims.push([i, n / i]);
            if i != n / i {
                dims.push([n / i, i]);
            }
        }
    }
    dims.sort_by_key(|d| d[0] + d[1]);
    dims
}
pub(crate) struct Analysis {
    pub rois: Vec<Roi>,
    pub expressions: Vec<(String, String)>,
    pub active: String,
}
/// Map reductions use the fitted rows while selection retains the source series.
#[derive(Clone, Default)]
pub(crate) struct CorrectedProfiles {
    pub x: Arc<Vec<f64>>,
    pub data: Arc<Vec<f64>>,
}

#[derive(Clone)]
pub(crate) struct MapBackground {
    patterns: Patterns,
    prepared: Option<Arc<crate::background_fit::ChebyshevFit>>,
}
impl MapBackground {
    pub fn new(patterns: &Patterns) -> Option<Self> {
        if !crate::batch_pattern_background::active(patterns) {
            return None;
        }
        let mut patterns = patterns.clone();
        patterns
            .overlays
            .retain(|o| Some(&o.uid) == patterns.background_uid.as_ref());
        Some(Self {
            patterns,
            prepared: None,
        })
    }
    pub fn apply(
        &mut self,
        mut curve: crate::pattern::Curve,
        unit: &str,
        wavelength: Option<f64>,
        control: &crate::control::Control,
    ) -> Result<crate::pattern::Curve, String> {
        let source_x = curve.x.clone();
        let fit_unit = self.patterns.unit.clone();
        let fit_x = crate::pattern::convert_axis(&source_x, unit, &fit_unit, wavelength)?;
        curve.x = fit_x.clone();
        self.patterns
            .ingest(curve, &fit_unit, "Map pattern", None, false);
        let mut corrected = self
            .patterns
            .build_background_row(control, &mut self.prepared)?;
        if fit_unit != unit {
            // Cropping and d-spacing reversal can change both length and order.
            // Keep the original bin centers exactly for strict ROI boundaries.
            let centers: std::collections::HashMap<_, _> = fit_x
                .iter()
                .zip(source_x.iter())
                .map(|(a, b)| (a.to_bits(), *b))
                .collect();
            corrected.x = Arc::new(corrected.x.iter().map(|x| centers[&x.to_bits()]).collect());
        }
        Ok(corrected)
    }
}
impl CorrectedProfiles {
    #[cfg(any(feature = "dioptrin", test))]
    pub fn push(&mut self, curve: &crate::pattern::Curve) -> Result<(), String> {
        if self.data.is_empty() {
            self.x = curve.x.clone();
        } else if self.x != curve.x {
            return Err("Map background coverage differs between frames.".into());
        }
        Arc::make_mut(&mut self.data).extend_from_slice(&curve.y);
        Ok(())
    }
    pub fn from_series(
        series: &Series,
        patterns: &Patterns,
        control: &crate::control::Control,
    ) -> Result<Option<Self>, String> {
        let Some(mut fit) = MapBackground::new(patterns) else {
            return Ok(None);
        };
        let mut corrected = Self::default();
        corrected.append_series(series, 0, &mut fit, control)?;
        Ok(Some(corrected))
    }
    pub fn append_series(
        &mut self,
        series: &Series,
        start: usize,
        fit: &mut MapBackground,
        control: &crate::control::Control,
    ) -> Result<(), String> {
        if start == series.count() {
            return control.check();
        }
        // Prepare the decomposition once and share it across independent row fits.
        let first = fit.apply(
            series.profile(start, &series.unit)?,
            &series.unit,
            series.wavelength,
            control,
        )?;
        let bins = first.x.len();
        if bins == 0 || (!self.data.is_empty() && self.x != first.x) {
            return Err("Map background coverage differs between frames.".into());
        }
        let mut data = vec![0.0; (series.count() - start) * bins];
        data[..bins].copy_from_slice(&first.y);
        crate::background_workers::rows(
            &mut data[bins..],
            bins,
            start + 1,
            control,
            "Updating map background",
            || fit.clone(),
            |index, output, fit| {
                let curve = fit.apply(
                    series.profile(index, &series.unit)?,
                    &series.unit,
                    series.wavelength,
                    control,
                )?;
                if curve.x != first.x {
                    return Err("Map background coverage differs between frames.".into());
                }
                output.copy_from_slice(&curve.y);
                Ok(())
            },
        )?;
        self.x = first.x;
        if self.data.is_empty() {
            self.data = Arc::new(data);
        } else {
            Arc::make_mut(&mut self.data).extend(data);
        }
        Ok(())
    }
}
impl Scan {
    pub fn analysis(
        x: &[f64],
        unit: &str,
        wavelength: f64,
        previous: Option<&Self>,
    ) -> Result<Analysis, String> {
        let Some(previous) = previous else {
            return Ok(Analysis {
                rois: vec![Self::default_roi(x)],
                expressions: vec![],
                active: "A".into(),
            });
        };
        let mut rois = previous.rois.clone();
        if previous.series.unit != unit {
            let old_wavelength = previous.series.wavelength.unwrap_or(wavelength);
            for roi in &mut rois {
                let convert = |v| {
                    let q = crate::pattern::convert_coordinate(
                        v,
                        &previous.series.unit,
                        "q_A^-1",
                        old_wavelength,
                    );
                    crate::pattern::convert_coordinate(q, "q_A^-1", unit, wavelength)
                };
                let mut range = [convert(roi.min), convert(roi.max)];
                if range.iter().any(|v| !v.is_finite()) {
                    return Err(
                        "An existing map region cannot be converted to the new radial unit.".into(),
                    );
                }
                range.sort_by(f64::total_cmp);
                roi.min = range[0];
                roi.max = range[1];
            }
        }
        Ok(Analysis {
            rois,
            expressions: previous.expressions.clone(),
            active: previous.active.clone(),
        })
    }
    pub fn default_roi(x: &[f64]) -> Roi {
        let low = x.iter().copied().fold(f64::INFINITY, f64::min);
        let high = x.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let step = if x.len() > 1 {
            (x[x.len() - 1] - x[0]) / (x.len() - 1) as f64
        } else {
            (high - low).max(1.0)
        };
        let center = x[x.len() / 2];
        let mut range = [center - 3.0 * step, center + 3.0 * step];
        range.sort_by(f64::total_cmp);
        Roi {
            name: "A".into(),
            min: range[0],
            max: range[1],
            reduction: "sum".into(),
            background: false,
            color: "#ff9800".into(),
        }
    }
    #[cfg(test)]
    pub fn new(
        series: Series,
        patterns: &Patterns,
        control: &crate::control::Control,
    ) -> Result<Self, String> {
        let corrected = CorrectedProfiles::from_series(&series, patterns, control)?;
        Self::new_with_analysis(series, patterns, None, corrected)
    }
    pub fn new_with_analysis(
        mut series: Series,
        patterns: &Patterns,
        previous: Option<&Self>,
        corrected: Option<CorrectedProfiles>,
    ) -> Result<Self, String> {
        // Qt Map consumes Batch data, not its separately extracted background.
        series.background = None;
        series.raw_background = None;
        series.batch_background = Default::default();
        let dims = dimensions(series.count());
        let dimension = dims[0];
        let analysis = Self::analysis(
            corrected.as_ref().map_or(&series.x, |rows| &rows.x),
            &series.unit,
            series.wavelength.unwrap_or(1e-10),
            previous,
        )?;
        let mut s = Self {
            slots: Arc::new((0..series.count()).map(Some).collect()),
            dimension,
            snake: false,
            transpose: false,
            flip_horizontal: false,
            flip_vertical: false,
            excluded: BTreeSet::new(),
            rois: analysis.rois,
            expressions: analysis.expressions,
            active: analysis.active,
            selected: None,
            selected_slot: None,
            values: Arc::new(vec![]),
            indices: Arc::new(vec![]),
            slot_indices: Arc::new(vec![]),
            raster: Raster::image(&[0.0], [1, 1]),
            layers: Arc::new(BTreeMap::new()),
            normalization_coordinates: Value::Null,
            pending: BTreeMap::new(),
            series,
            corrected,
            background_pending: false,
        };
        s.rebuild(true, patterns)?;
        Ok(s)
    }
    pub fn refresh_background(
        &mut self,
        patterns: &Patterns,
        control: &crate::control::Control,
    ) -> Result<(), String> {
        self.corrected = CorrectedProfiles::from_series(&self.series, patterns, control)?;
        self.background_pending = false;
        Ok(())
    }
    pub fn shape(&self) -> [usize; 2] {
        if self.transpose {
            [self.dimension[1], self.dimension[0]]
        } else {
            self.dimension
        }
    }
    pub fn fitted_slots(&self, exclude: bool) -> Vec<Option<usize>> {
        let mut seen = BTreeSet::new();
        let mut slots: Vec<_> = self
            .slots
            .iter()
            .filter_map(|entry| match entry {
                Some(i) if exclude && self.excluded.contains(i) => None,
                Some(i) if *i >= self.series.count() || !seen.insert(*i) => Some(None),
                e => Some(*e),
            })
            .collect();
        let mut missing = (0..self.series.count())
            .filter(|i| !seen.contains(i) && (!exclude || !self.excluded.contains(i)))
            .collect::<Vec<_>>()
            .into_iter();
        for slot in &mut slots {
            if slot.is_none() {
                if let Some(i) = missing.next() {
                    *slot = Some(i);
                } else {
                    break;
                }
            }
        }
        slots.extend(missing.map(Some));
        slots.resize(self.dimension[0] * self.dimension[1], None);
        slots
    }
    pub fn layer_values(&self, name: &str, patterns: &Patterns) -> Result<Vec<f64>, String> {
        if let Some(v) = self.layers.get(name) {
            return Ok(v.clone());
        }
        let expression = self
            .expressions
            .iter()
            .find(|(n, _)| n == name)
            .ok_or("Unknown map layer.")?;
        map_math::Expression::parse(&expression.1)?.evaluate(
            &self.layers,
            self.series.count(),
            &|overlay, window| {
                let roi = self
                    .rois
                    .iter()
                    .find(|r| r.name == window)
                    .ok_or("Unknown overlay window.")?;
                let curve = patterns
                    .overlays
                    .iter()
                    .find(|o| o.name == overlay)
                    .map(|o| o.curve(&self.series.unit))
                    .transpose()?
                    .ok_or_else(|| format!("Unknown overlay {overlay}."))?;
                Ok(map_math::reduce(
                    &curve.x,
                    &curve.y,
                    roi.min,
                    roi.max,
                    &roi.reduction,
                    roi.background,
                ))
            },
        )
    }
    pub fn rebuild(&mut self, reduction: bool, patterns: &Patterns) -> Result<(), String> {
        if self.dimension[0] == 0
            || self.dimension[1] == 0
            || self.dimension[0]
                .checked_mul(self.dimension[1])
                .is_none_or(|n| n > 4_000_000 || n < self.series.count())
        {
            return Err(
                "The grid must hold every scan point, with at most four million cells.".into(),
            );
        }
        if reduction {
            let mut layers = BTreeMap::new();
            let (x, data) = self
                .corrected
                .as_ref()
                .map_or((&self.series.x, &self.series.data), |rows| {
                    (&rows.x, &rows.data)
                });
            for r in &self.rois {
                let window = map_math::Window::new(x, r.min, r.max, &r.reduction, r.background);
                layers.insert(
                    r.name.clone(),
                    data.chunks_exact(x.len())
                        .map(|y| window.reduce(y))
                        .collect(),
                );
            }
            self.layers = Arc::new(layers);
        }
        let values = self.layer_values(&self.active, patterns).or_else(|_| {
            self.layers
                .get(&self.rois[0].name)
                .cloned()
                .ok_or("No map windows.")
        })?;
        let slots = self.fitted_slots(true);
        let allslots = self.fitted_slots(false);
        let visible_slot: Vec<_> = allslots
            .iter()
            .enumerate()
            .filter_map(|(i, p)| (!p.is_some_and(|p| self.excluded.contains(&p))).then_some(i))
            .collect();
        let [rows, cols] = self.dimension;
        let [outrows, outcols] = self.shape();
        let mut index = vec![-1; outrows * outcols];
        let mut slotindex = vec![-1; outrows * outcols];
        let mut data = vec![f64::NAN; outrows * outcols];
        for row in 0..rows {
            for col in 0..cols {
                let src = row * cols
                    + if self.snake && row % 2 == 1 {
                        cols - 1 - col
                    } else {
                        col
                    };
                let (mut r, mut c) = if self.transpose {
                    (col, row)
                } else {
                    (row, col)
                };
                if self.flip_vertical {
                    r = outrows - 1 - r;
                }
                if self.flip_horizontal {
                    c = outcols - 1 - c;
                }
                let k = r * outcols + c;
                if let Some(point) = slots[src] {
                    index[k] = point as i64;
                    data[k] = values[point];
                }
                slotindex[k] = visible_slot.get(src).map_or(-1, |&s| s as i64);
            }
        }
        let display: Vec<_> = data
            .chunks_exact(outcols)
            .rev()
            .flatten()
            .copied()
            .collect();
        self.raster = Raster::image(&display, [outrows, outcols]);
        self.values = Arc::new(data);
        self.indices = Arc::new(index);
        self.slot_indices = Arc::new(slotindex);
        Ok(())
    }
    pub fn metadata(&self) -> Value {
        let [rows, cols] = self.shape();
        let matrix = |v: &[i64]| v.chunks_exact(cols).map(|r| r.to_vec()).collect::<Vec<_>>();
        let slots = self.fitted_slots(false);
        let cell = self
            .selected
            .and_then(|i| self.indices.iter().position(|&v| v == i as i64))
            .map(|k| [k / cols, k % cols]);
        let labels: Vec<_> = slots
            .iter()
            .map(|p| {
                p.map_or_else(
                    || "—".into(),
                    |i| {
                        let e = &self.series.entries[i];
                        let name = Path::new(&e.path)
                            .file_name()
                            .unwrap_or_default()
                            .to_string_lossy();
                        if e.frame == 0 {
                            name.into_owned()
                        } else {
                            format!("{name}:{}", e.frame)
                        }
                    },
                )
            })
            .collect();
        let expressions: serde_json::Map<String, Value> = self
            .expressions
            .iter()
            .map(|(n, e)| (n.clone(), json!(e)))
            .collect();
        json!({"raster":self.raster.metadata,"unit":self.series.unit,"points":self.series.count(),"canRebuild":!self.series.paths.is_empty(),"backgroundPending":self.background_pending,"dimension":self.dimension,"presets":dimensions(self.series.count()),"snake":self.snake,"transpose":self.transpose,"flip_horizontal":self.flip_horizontal,"flip_vertical":self.flip_vertical,"active":self.active,"rois":self.rois,"expressions":expressions,"selected":self.selected,"selectedCell":cell,"selectedSlot":self.selected.and_then(|i|slots.iter().position(|&p|p==Some(i))).or(self.selected_slot),"normalized":self.series.normalized,"normalizationRange":self.series.normalization,"normalizationReference":self.series.reference,"normalizationCoordinates":self.normalization_coordinates,"slots":slots,"labels":labels,"excluded":self.excluded,"indices":matrix(&self.indices),"slotIndices":matrix(&self.slot_indices),"values":self.values.chunks_exact(cols).map(|r|r.to_vec()).collect::<Vec<_>>(),"displayShape":[rows,cols]})
    }
    pub fn name_available(&self, name: &str) -> bool {
        !self.rois.iter().any(|r| r.name == name)
            && !self.expressions.iter().any(|(n, _)| n == name)
    }
}

#[cfg(test)]
mod background_tests {
    use super::*;
    use crate::{
        control::Control,
        pattern::{Curve, Overlay},
        series::Entry,
    };

    #[test]
    fn parallel_map_refits_match_serial_rows_across_units_and_cropped_backgrounds() {
        let count = 513;
        let bins = 1024;
        let x: Vec<_> = (0..bins).map(|i| 1. + i as f64 * 0.01).collect();
        let data: Vec<_> = (0..count)
            .flat_map(|frame| {
                (0..bins).map(move |bin| {
                    100. + bin as f64 * 0.1 + (frame + 1) as f64 * (bin as f64 * 0.03).sin().abs()
                })
            })
            .collect();
        let series = Series::new(
            x.clone(),
            data,
            "q_A^-1".into(),
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
        for unit in ["q_A^-1", "2th_deg", "d_A"] {
            let mut patterns = Patterns::default();
            patterns.unit = unit.into();
            patterns.background.enabled = true;
            patterns.background.order = 9;
            patterns.background.iterations = 15;
            let axis = series.profile(0, unit).unwrap().x;
            let mut range = [axis[100], axis[900]];
            range.sort_by(f64::total_cmp);
            patterns.background.range = Some(range);
            patterns.background_uid = Some("background".into());
            patterns.overlays.push(Overlay {
                uid: "background".into(),
                name: "Background".into(),
                visible: false,
                color: "#ffffff".into(),
                scale: 2.,
                offset: 3.,
                data: Arc::new(Curve {
                    x: axis,
                    y: Arc::new(vec![5.; bins]),
                    sigma: None,
                    spread: None,
                }),
                batch_source: None,
            });
            let control = Control::default();
            let mut serial = CorrectedProfiles::default();
            let mut fit = MapBackground::new(&patterns).unwrap();
            let started = std::time::Instant::now();
            for i in 0..count {
                let curve = fit
                    .apply(
                        series.profile(i, &series.unit).unwrap(),
                        &series.unit,
                        series.wavelength,
                        &control,
                    )
                    .unwrap();
                serial.push(&curve).unwrap();
            }
            let serial_elapsed = started.elapsed();
            let workers = crate::worker_pool::available().min(4);
            let pool = crate::worker_pool::pool(Some(workers)).unwrap();
            let started = std::time::Instant::now();
            let parallel = crate::worker_pool::enter(pool, || {
                CorrectedProfiles::from_series(&series, &patterns, &control)
            })
            .unwrap()
            .unwrap();
            eprintln!(
                "{unit}, {count} x {bins}, {workers} workers: serial {serial_elapsed:?}, parallel {:?}",
                started.elapsed()
            );
            assert_eq!(parallel.x, serial.x);
            assert!(
                parallel
                    .data
                    .iter()
                    .zip(serial.data.iter())
                    .all(|(a, b)| a.to_bits() == b.to_bits())
            );
            assert_eq!(control.progress()["current"], count);
            assert_eq!(control.progress()["total"], count);
            let before = parallel.data.clone();
            let mut cancelled = parallel;
            control.cancel();
            assert!(
                cancelled
                    .append_series(&series, 0, &mut fit, &control)
                    .unwrap_err()
                    .contains("cancelled")
            );
            assert!(Arc::ptr_eq(&before, &cancelled.data));
        }
    }
}
