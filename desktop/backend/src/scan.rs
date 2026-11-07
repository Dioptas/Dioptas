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
    pub dimension: [usize; 2],
    pub snake: bool,
    pub transpose: bool,
    pub flip_horizontal: bool,
    pub flip_vertical: bool,
    pub slots: Vec<Option<usize>>,
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
impl Scan {
    pub fn new(series: Series, patterns: &Patterns) -> Result<Self, String> {
        let dims = dimensions(series.count());
        let dimension = dims[0];
        let low = series.x.iter().copied().fold(f64::INFINITY, f64::min);
        let high = series.x.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let step = if series.x.len() > 1 {
            (series.x[series.x.len() - 1] - series.x[0]) / (series.x.len() - 1) as f64
        } else {
            (high - low).max(1.0)
        };
        let center = series.x[series.x.len() / 2];
        let mut range = [center - 3.0 * step, center + 3.0 * step];
        range.sort_by(f64::total_cmp);
        let mut s = Self {
            slots: (0..series.count()).map(Some).collect(),
            dimension,
            snake: false,
            transpose: false,
            flip_horizontal: false,
            flip_vertical: false,
            excluded: BTreeSet::new(),
            rois: vec![Roi {
                name: "A".into(),
                min: range[0],
                max: range[1],
                reduction: "sum".into(),
                background: false,
                color: "#ff9800".into(),
            }],
            expressions: vec![],
            active: "A".into(),
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
        };
        s.rebuild(true, patterns)?;
        Ok(s)
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
                    .map(|o| o.curve())
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
            for r in &self.rois {
                let window =
                    map_math::Window::new(&self.series.x, r.min, r.max, &r.reduction, r.background);
                layers.insert(
                    r.name.clone(),
                    self.series
                        .data
                        .chunks_exact(self.series.x.len())
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
        json!({"raster":self.raster.metadata,"unit":self.series.unit,"points":self.series.count(),"canRebuild":!self.series.paths.is_empty(),"dimension":self.dimension,"presets":dimensions(self.series.count()),"snake":self.snake,"transpose":self.transpose,"flip_horizontal":self.flip_horizontal,"flip_vertical":self.flip_vertical,"active":self.active,"rois":self.rois,"expressions":expressions,"selected":self.selected,"selectedCell":cell,"selectedSlot":self.selected.and_then(|i|slots.iter().position(|&p|p==Some(i))).or(self.selected_slot),"normalized":self.series.normalized,"normalizationRange":self.series.normalization,"normalizationReference":self.series.reference,"normalizationCoordinates":self.normalization_coordinates,"slots":slots,"labels":labels,"excluded":self.excluded,"indices":matrix(&self.indices),"slotIndices":matrix(&self.slot_indices),"values":self.values.chunks_exact(cols).map(|r|r.to_vec()).collect::<Vec<_>>(),"displayShape":[rows,cols]})
    }
    pub fn name_available(&self, name: &str) -> bool {
        !self.rois.iter().any(|r| r.name == name)
            && !self.expressions.iter().any(|(n, _)| n == name)
    }
}
