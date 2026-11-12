//! Owned processed series and Qt-compatible HDF5, with reversible normalization.
use crate::{display::Raster, pattern::Curve};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{HashMap, HashSet},
    path::Path,
    str::FromStr,
    sync::Arc,
};
#[derive(Clone, Serialize, Deserialize)]
pub(crate) struct Entry {
    pub path: String,
    pub frame: usize,
}
#[derive(Default)]
struct FileSummary {
    first: usize,
    entries: usize,
    frame_count: usize,
}
/// Immutable acquisition lookup, shared by cloned series. Build once per
/// source list instead of scanning every frame for each file in each reply.
fn index_files<'a>(
    entries: impl Iterator<Item = (usize, &'a Entry)>,
) -> HashMap<String, FileSummary> {
    let mut files = HashMap::<String, FileSummary>::new();
    for (row, entry) in entries {
        let summary = files
            .entry(entry.path.clone())
            .or_insert_with(|| FileSummary {
                first: row,
                ..Default::default()
            });
        summary.entries += 1;
        summary.frame_count = summary.frame_count.max(entry.frame.saturating_add(1));
    }
    files
}
#[derive(Clone)]
pub(crate) struct Series {
    pub x: Arc<Vec<f64>>,
    pub raw: Arc<Vec<f64>>,
    pub data: Arc<Vec<f64>>,
    pub sigma: Option<Arc<Vec<f64>>>,
    pub raw_sigma: Option<Arc<Vec<f64>>>,
    pub spread: Option<Arc<Vec<f64>>>,
    pub raw_spread: Option<Arc<Vec<f64>>>,
    pub background: Option<Arc<Vec<f64>>>,
    pub raw_background: Option<Arc<Vec<f64>>>,
    pub batch_background: crate::batch_background::State,
    pub unit: String,
    pub wavelength: Option<f64>,
    pub entries: Arc<Vec<Entry>>,
    file_index: Arc<HashMap<String, FileSummary>>,
    // Rollback checkpoints share source metadata; writers copy only their local edits.
    pub paths: Arc<Vec<String>>,
    pub file_counts: Arc<Vec<usize>>,
    pub reader_options: std::collections::BTreeMap<String, Value>,
    pub total: usize,
    pub selected: usize,
    pub normalization: [usize; 2],
    pub reference: usize,
    pub normalized: bool,
    pub raster: Raster,
    pub export_name: Option<String>,
    pub calibration: String,
    pub mask: String,
}
impl Series {
    pub fn append(&self, other: &Self) -> Result<Self, String> {
        if self.normalized || other.normalized {
            return Err("Restore original series data before appending frames.".into());
        }
        if self.unit != other.unit || self.x != other.x || self.wavelength != other.wavelength {
            return Err(
                "Live radial axes or calibration differ; reintegrate the scan before appending."
                    .into(),
            );
        }
        if self
            .data
            .len()
            .checked_add(other.data.len())
            .is_none_or(|n| n > 64_000_000)
        {
            return Err("Processed scan exceeds 64 million samples.".into());
        }
        let mut data = self.data.as_ref().clone();
        data.extend(other.data.iter().copied());
        let mut entries = self.entries.as_ref().clone();
        entries.extend(other.entries.iter().cloned());
        let mut paths = self.paths.as_ref().clone();
        let mut known: HashSet<_> = paths.iter().cloned().collect();
        for p in other.paths.iter() {
            if known.insert(p.clone()) {
                paths.push(p.clone());
            }
        }
        let mut s = Self::new(
            self.x.as_ref().clone(),
            data,
            self.unit.clone(),
            self.wavelength,
            entries,
            paths,
            self.total + other.total,
        )?;
        if self.background.is_some() || other.background.is_some() {
            return Err("Reintegrate series backgrounds before appending frames.".into());
        }
        let mut counts = HashMap::<&str, usize>::new();
        for series in [self, other] {
            for (path, &count) in series.paths.iter().zip(series.file_counts.iter()) {
                let entry = counts.entry(path.as_str()).or_default();
                *entry = (*entry).max(count);
            }
        }
        s.file_counts = s
            .paths
            .iter()
            .map(|p| counts.get(p.as_str()).copied().unwrap_or(0))
            .collect::<Vec<_>>()
            .into();
        match (&self.spread, &other.spread) {
            (Some(a), Some(b)) => {
                let mut spread = a.as_ref().clone();
                spread.extend(b.iter().copied());
                s.spread = Some(Arc::new(spread));
                s.raw_spread = s.spread.clone();
            }
            (None, None) => {}
            _ => {
                return Err(
                    "Live azimuthal spread settings differ; reintegrate the scan before appending."
                        .into(),
                );
            }
        }
        match (&self.sigma, &other.sigma) {
            (Some(a), Some(b)) => {
                let mut sigma = a.as_ref().clone();
                sigma.extend(b.iter().copied());
                s.sigma = Some(Arc::new(sigma));
                s.raw_sigma = s.sigma.clone();
            }
            (None, None) => {}
            _ => {
                return Err(
                    "Live counting uncertainty settings differ; reintegrate before appending."
                        .into(),
                );
            }
        }
        s.reader_options = self.reader_options.clone();
        for (path, options) in &other.reader_options {
            if s.reader_options
                .get(path)
                .is_some_and(|previous| previous != options)
            {
                return Err(
                    "A scan append cannot replace the source contract for an existing file.".into(),
                );
            }
            s.reader_options.insert(path.clone(), options.clone());
        }
        if serde_json::to_vec(&s.reader_options)
            .map_err(|e| e.to_string())?
            .len()
            > 16 * 1024 * 1024
        {
            return Err("Series source contracts exceed the 16 MiB metadata bound.".into());
        }
        s.calibration = self.calibration.clone();
        s.mask = self.mask.clone();
        Ok(s)
    }
    pub fn new(
        x: Vec<f64>,
        data: Vec<f64>,
        unit: String,
        wavelength: Option<f64>,
        entries: Vec<Entry>,
        paths: Vec<String>,
        total: usize,
    ) -> Result<Self, String> {
        if x.is_empty()
            || entries.is_empty()
            || entries.len() > 1_000_000
            || data.len() != x.len().saturating_mul(entries.len())
            || data.len() > 64_000_000
            || x.iter().any(|x| !x.is_finite())
            || !["2th_deg", "q_A^-1", "q_nm^-1", "d_A"].contains(&unit.as_str())
        {
            return Err("A series needs a bounded non-empty intensity matrix, finite radial axis and supported unit.".into());
        }
        let file_index = Arc::new(index_files(entries.iter().enumerate()));
        let file_counts = paths
            .iter()
            .map(|p| file_index.get(p).map_or(0, |file| file.frame_count))
            .collect();
        let raster = Raster::image(&data, [entries.len(), x.len()]);
        let n = x.len();
        let data = Arc::new(data);
        Ok(Self {
            x: Arc::new(x),
            raw: data.clone(),
            data,
            unit,
            wavelength,
            entries: Arc::new(entries),
            file_index,
            paths: Arc::new(paths),
            file_counts: Arc::new(file_counts),
            reader_options: Default::default(),
            total,
            selected: 0,
            normalization: [0, n],
            reference: 0,
            normalized: false,
            raster,
            export_name: None,
            calibration: String::new(),
            mask: String::new(),
            sigma: None,
            raw_sigma: None,
            spread: None,
            raw_spread: None,
            background: None,
            raw_background: None,
            batch_background: Default::default(),
        })
    }
    pub fn count(&self) -> usize {
        self.entries.len()
    }
    pub fn profile(&self, index: usize, unit: &str) -> Result<Curve, String> {
        if index >= self.count() {
            return Err("Choose a frame within the series.".into());
        }
        let x = if unit == self.unit {
            self.x.clone()
        } else {
            if [unit, self.unit.as_str()].contains(&"2th_deg") && self.wavelength.is_none() {
                return Err(
                    "This stored batch has no recorded wavelength for angular conversion.".into(),
                );
            }
            let x = self
                .x
                .iter()
                .map(|&x| {
                    crate::pattern::convert_coordinate(
                        x,
                        &self.unit,
                        unit,
                        self.wavelength.unwrap_or(1e-10),
                    )
                })
                .collect::<Vec<_>>();
            if x.iter().any(|x| !x.is_finite()) {
                return Err(
                    "The requested series axis cannot be converted at the recorded wavelength."
                        .into(),
                );
            }
            Arc::new(x)
        };
        let n = self.x.len();
        Ok(Curve {
            x,
            y: Arc::new(self.data[index * n..(index + 1) * n].to_vec()),
            sigma: self
                .sigma
                .as_ref()
                .map(|v| Arc::new(v[index * n..(index + 1) * n].to_vec())),
            spread: self
                .spread
                .as_ref()
                .map(|s| Arc::new(s[index * n..(index + 1) * n].to_vec())),
        })
    }
    pub fn normalize(
        &mut self,
        enabled: bool,
        range: [usize; 2],
        reference: usize,
    ) -> Result<(), String> {
        let n = self.x.len();
        let mut data = self.raw.clone();
        let mut spread = self.raw_spread.clone();
        let mut sigma = self.raw_sigma.clone();
        let mut background = self.raw_background.clone();
        if enabled {
            if range[0] >= range[1] || range[1] > n || reference >= self.count() {
                return Err("Choose a non-empty normalization interval and a reference frame within the series.".into());
            }
            let means: Vec<_> = self
                .raw
                .chunks_exact(n)
                .map(|row| {
                    row[range[0]..range[1]].iter().sum::<f64>() / (range[1] - range[0]) as f64
                })
                .collect();
            if means.iter().any(|m| !m.is_finite() || *m <= 0.0) {
                return Err("Normalization requires a positive, finite mean intensity in every frame. Choose another bin range.".into());
            }
            let factors: Vec<_> = means.iter().map(|m| means[reference] / m).collect();
            if factors.iter().any(|f| !f.is_finite() || *f <= 0.0) {
                return Err(
                    "Normalization factors are outside the supported intensity range.".into(),
                );
            }
            data = Arc::new(
                self.raw
                    .iter()
                    .enumerate()
                    .map(|(i, v)| v * factors[i / n])
                    .collect(),
            );
            background = self.raw_background.as_ref().map(|s| {
                Arc::new(
                    s.iter()
                        .enumerate()
                        .map(|(i, v)| v * factors[i / n])
                        .collect(),
                )
            });
            sigma = self.raw_sigma.as_ref().map(|s| {
                Arc::new(
                    s.iter()
                        .enumerate()
                        .map(|(i, v)| v * factors[i / n])
                        .collect(),
                )
            });
            spread = self.raw_spread.as_ref().map(|s| {
                Arc::new(
                    s.iter()
                        .enumerate()
                        .map(|(i, v)| v * factors[i / n])
                        .collect(),
                )
            });
        }
        self.raster = Raster::image(&data, [self.count(), n]);
        self.data = data;
        self.spread = spread;
        self.sigma = sigma;
        self.background = background;
        self.normalized = enabled;
        self.normalization = range;
        self.reference = reference;
        self.refresh_batch_background()?;
        Ok(())
    }
    pub fn metadata(&self, unit: &str, phases: Value) -> Value {
        let unit = if self.wavelength.is_none()
            && unit != self.unit
            && [unit, self.unit.as_str()].contains(&"2th_deg")
        {
            self.unit.as_str()
        } else {
            unit
        };
        let curve = self
            .profile(self.selected, unit)
            .or_else(|_| self.profile(self.selected, &self.unit))
            .unwrap();
        let files: Vec<_> = self.paths.iter().enumerate().filter(|(_, p)| !p.is_empty()).map(|(i,p)| {
            let summary = self.file_index.get(p);
            json!({"path":p,"name":Path::new(p).file_name().unwrap_or_default().to_string_lossy(),
                "frames":self.file_counts.get(i).copied().unwrap_or_else(||summary.map_or(0, |f| f.entries)),
                "first":summary.map(|f| f.first)})
        }).collect();
        json!({"id":self.background_raster().buffer.id,"exportBaseName":self.export_name,"waterfallKey":crate::batch_waterfall::identity(self),"raster":self.background_raster().metadata,"backgroundState":self.background_metadata(),"sourceBins":self.background_bins(),"x":&curve.x[self.background_bins()[0]..self.background_bins()[1]],"wavelength":self.wavelength,"unit":unit,"sourceUnit":self.unit,"entries":self.entries.iter().map(|e|json!({"path":e.path,"name":if e.path.is_empty(){"Stored pattern".into()}else{Path::new(&e.path).file_name().unwrap_or_default().to_string_lossy()},"frame":e.frame+1})).collect::<Vec<_>>(),"files":files,"pattern":{"x":curve.x,"y":curve.y,"sigma":curve.sigma,"unit":unit},"selected":self.selected,"total":self.total,"canReintegrate":self.paths.iter().any(|p|!p.is_empty()&&Path::new(p).is_file()),"normalized":self.normalized,"normalizationRange":self.normalization,"normalizationReference":self.reference,"normalizationReferenceName":self.entries.get(self.reference).map(|e|if e.path.is_empty(){format!("Stored pattern · frame {}", self.reference+1)}else{Path::new(&e.path).file_name().unwrap_or_default().to_string_lossy().into_owned()}),"normalizationRegion":{"minimum":self.x[self.normalization[0]].min(self.x[self.normalization[1]-1]),"maximum":self.x[self.normalization[0]].max(self.x[self.normalization[1]-1]),"unit":self.unit},"calibration":self.calibration,"mask":self.mask,"phaseLines":phases,"position":null})
    }
    pub fn save(&self, path: &Path) -> Result<(), String> {
        let mut temp = crate::output::StagedOutput::new(path)?;
        if path
            .extension()
            .is_some_and(|s| s.eq_ignore_ascii_case("csv"))
        {
            use std::io::Write;
            let mut w = csv::Writer::from_writer(&mut temp);
            let mut header = vec!["radial", "frame", "intensity"];
            if self.sigma.is_some() {
                header.push("counting_std");
            }
            if self.spread.is_some() {
                header.push("azimuthal_std");
            }
            w.write_record(header).map_err(|e| e.to_string())?;
            for (j, &x) in self.x.iter().enumerate() {
                for i in 0..self.count() {
                    let k = i * self.x.len() + j;
                    let mut row = vec![x.to_string(), i.to_string(), self.data[k].to_string()];
                    if let Some(s) = &self.sigma {
                        row.push(s[k].to_string());
                    }
                    if let Some(s) = &self.spread {
                        row.push(s[k].to_string());
                    }
                    w.write_record(row).map_err(|e| e.to_string())?;
                }
            }
            w.flush().map_err(|e| e.to_string())?;
            drop(w);
            temp.flush().map_err(|e| e.to_string())?;
        } else {
            let f = hdf5::File::create(temp.path()).map_err(|e| e.to_string())?;
            let entry = f.create_group("processed").map_err(|e| e.to_string())?;
            let result = entry.create_group("result").map_err(|e| e.to_string())?;
            let process = entry.create_group("process").map_err(|e| e.to_string())?;
            result
                .new_dataset::<f64>()
                .shape([self.count(), self.x.len()])
                .create("data")
                .and_then(|d| d.write_raw(self.data.as_slice()))
                .map_err(|e| e.to_string())?;
            let axis = result
                .new_dataset_builder()
                .with_data(self.x.as_slice())
                .create("binning")
                .map_err(|e| e.to_string())?;
            string_attr(&axis, "radial_unit", &self.unit)?;
            if let Some(sigma) = &self.sigma {
                result
                    .new_dataset::<f64>()
                    .shape([self.count(), self.x.len()])
                    .create("counting_std")
                    .and_then(|d| d.write_raw(sigma.as_slice()))
                    .map_err(|e| e.to_string())?;
            }
            if let Some(spread) = &self.spread {
                result
                    .new_dataset::<f64>()
                    .shape([self.count(), self.x.len()])
                    .create("azimuthal_std")
                    .and_then(|d| d.write_raw(spread.as_slice()))
                    .map_err(|e| e.to_string())?;
            }
            let mut paths = self.paths.as_ref().clone();
            let mut path_indices = HashMap::new();
            for (i, path) in paths.iter().enumerate() {
                // Preserve the first occurrence if an imported source list
                // contains duplicate paths, matching the original position map.
                path_indices.entry(path.clone()).or_insert(i);
            }
            for e in self.entries.iter() {
                if let std::collections::hash_map::Entry::Vacant(entry) =
                    path_indices.entry(e.path.clone())
                {
                    entry.insert(paths.len());
                    paths.push(e.path.clone());
                }
            }
            if paths.is_empty() {
                paths.push(String::new());
            }
            let strings: Vec<_> = paths
                .iter()
                .map(|s| hdf5::types::VarLenUnicode::from_str(s).map_err(|e| e.to_string()))
                .collect::<Result<_, _>>()?;
            process
                .new_dataset_builder()
                .with_data(&strings)
                .create("files")
                .map_err(|e| e.to_string())?;
            let positions: Vec<i64> = self
                .entries
                .iter()
                .flat_map(|e| [path_indices[&e.path] as i64, e.frame as i64])
                .collect();
            process
                .new_dataset::<i64>()
                .shape([self.count(), 2])
                .create("pos_map")
                .and_then(|d| d.write_raw(&positions))
                .map_err(|e| e.to_string())?;
            if let Some(background) = &self.background {
                process
                    .new_dataset::<f64>()
                    .shape([self.count(), self.x.len()])
                    .create("bkg")
                    .and_then(|d| d.write_raw(background.as_slice()))
                    .map_err(|e| e.to_string())?;
            }
            let mut filemap = vec![0_u64];
            for (i, p) in paths.iter().enumerate() {
                filemap.push(
                    filemap.last().unwrap()
                        + self
                            .file_counts
                            .get(i)
                            .copied()
                            .unwrap_or_else(|| self.file_index.get(p).map_or(0, |f| f.entries))
                            as u64,
                );
            }
            process
                .new_dataset_builder()
                .with_data(&filemap)
                .create("file_map")
                .map_err(|e| e.to_string())?;
            let all_positions: Vec<i64> =
                paths
                    .iter()
                    .enumerate()
                    .flat_map(|(i, _)| {
                        (0..self.file_counts.get(i).copied().unwrap_or_else(|| {
                            self.file_index.get(&paths[i]).map_or(0, |f| f.entries)
                        }))
                            .flat_map(move |frame| [i as i64, frame as i64])
                    })
                    .collect();
            process
                .new_dataset::<i64>()
                .shape([all_positions.len() / 2, 2])
                .create("pos_map_all")
                .and_then(|d| d.write_raw(&all_positions))
                .map_err(|e| e.to_string())?;
            for (name, value) in [
                ("cal_file", self.calibration.as_str()),
                ("mask_file", self.mask.as_str()),
                ("int_method", "csc"),
                ("int_unit", self.unit.as_str()),
            ] {
                let s = hdf5::types::VarLenUnicode::from_str(value).map_err(|e| e.to_string())?;
                process
                    .new_dataset::<hdf5::types::VarLenUnicode>()
                    .shape(())
                    .create(name)
                    .and_then(|d| d.write_scalar(&s))
                    .map_err(|e| e.to_string())?;
            }
            if let Some(w) = self.wavelength {
                result
                    .new_attr::<f64>()
                    .shape(())
                    .create("desktop_wavelength_m")
                    .and_then(|a| a.write_scalar(&w))
                    .map_err(|e| e.to_string())?;
            }
            let metadata = json!({"entries":self.entries,"paths":paths,"file_counts":self.file_counts,"total":self.total,"selected":self.selected,"normalization":self.normalization,"reference":self.reference,"normalized":self.normalized,"batch_background":self.batch_background,"export_name":self.export_name,"reader_options":self.reader_options});
            let meta = serde_json::to_vec(&metadata).map_err(|e| e.to_string())?;
            if meta.len() > 16 * 1024 * 1024 {
                return Err("Series source metadata exceeds 16 MiB.".into());
            }
            result
                .new_dataset_builder()
                .with_data(&meta)
                .create("desktop_metadata")
                .map_err(|e| e.to_string())?;
            if self.normalized {
                if let Some(background) = &self.raw_background {
                    result
                        .new_dataset::<f64>()
                        .shape([self.count(), self.x.len()])
                        .create("desktop_original_background")
                        .and_then(|d| d.write_raw(background.as_slice()))
                        .map_err(|e| e.to_string())?;
                }
                result
                    .new_dataset::<f64>()
                    .shape([self.count(), self.x.len()])
                    .create("desktop_original")
                    .and_then(|d| d.write_raw(self.raw.as_slice()))
                    .map_err(|e| e.to_string())?;
                if let Some(s) = &self.raw_sigma {
                    result
                        .new_dataset::<f64>()
                        .shape([self.count(), self.x.len()])
                        .create("desktop_original_counting_std")
                        .and_then(|d| d.write_raw(s.as_slice()))
                        .map_err(|e| e.to_string())?;
                }
                if let Some(s) = &self.raw_spread {
                    result
                        .new_dataset::<f64>()
                        .shape([self.count(), self.x.len()])
                        .create("desktop_original_spread")
                        .and_then(|d| d.write_raw(s.as_slice()))
                        .map_err(|e| e.to_string())?;
                }
            }
            f.flush().map_err(|e| e.to_string())?;
        }
        temp.commit(path)
    }
    /// Explicit processed-file opening records its user-facing basename. Embedded
    /// project loads retain the recorded name instead of a temporary .h5 filename.
    pub fn load_processed(path: &Path) -> Result<Self, String> {
        let mut series = Self::load(path)?;
        series.export_name = path
            .file_stem()
            .map(|name| name.to_string_lossy().into_owned());
        Ok(series)
    }
    pub fn load(path: &Path) -> Result<Self, String> {
        let f = hdf5::File::open(path).map_err(|e| e.to_string())?;
        let group = if f.link_exists("processed/result") {
            f.group("processed/result")
        } else {
            f.group("/")
        }
        .map_err(|e| e.to_string())?;
        let d = group.dataset("data").map_err(|e| e.to_string())?;
        let shape = d.shape();
        if shape.len() != 2
            || shape[0] == 0
            || shape[0] > 1_000_000
            || shape[1] == 0
            || shape[0]
                .checked_mul(shape[1])
                .is_none_or(|n| n > 64_000_000)
        {
            return Err("The batch does not contain a bounded non-empty pattern matrix.".into());
        }
        let axis = group.dataset("binning").map_err(|e| e.to_string())?;
        if axis.shape() != [shape[1]] {
            return Err("Batch radial axis differs from the matrix width.".into());
        }
        let unit = axis
            .attr("radial_unit")
            .ok()
            .and_then(|a| read_string_attr(&a))
            .unwrap_or_else(|| "2th_deg".into());
        let wavelength = group
            .attr("desktop_wavelength_m")
            .ok()
            .and_then(|a| a.read_scalar::<f64>().ok())
            .filter(|w| w.is_finite() && *w > 0.0);
        let mut entries = vec![
            Entry {
                path: String::new(),
                frame: 0
            };
            shape[0]
        ];
        for (i, e) in entries.iter_mut().enumerate() {
            e.frame = i;
        }
        let mut paths = vec![];
        let mut calibration = String::new();
        let mut mask = String::new();
        let mut counts = None;
        let mut background = None;
        if let Ok(process) = f.group("processed/process") {
            if let Ok(files) = process.dataset("files") {
                paths = read_strings(&files)?;
            }
            if let Ok(map) = process.dataset("file_map") {
                let map = map.read_raw::<u64>().map_err(|e| e.to_string())?;
                if map.len() != paths.len() + 1
                    || map.first() != Some(&0)
                    || map.windows(2).any(|w| w[0] > w[1])
                    || map.last().copied().unwrap_or(0) > 1_000_000
                {
                    return Err("Invalid batch file map.".into());
                }
                counts = Some(
                    map.windows(2)
                        .map(|w| (w[1] - w[0]) as usize)
                        .collect::<Vec<_>>(),
                );
            }
            if let Ok(bg) = process.dataset("bkg") {
                if bg.shape() != shape {
                    return Err("Batch background matrix has the wrong shape.".into());
                }
                background = Some(Arc::new(bg.read_raw::<f64>().map_err(|e| e.to_string())?));
            }
            if let Ok(pos) = process.dataset("pos_map") {
                if pos.shape() != [shape[0], 2] {
                    return Err("Batch raw position map has the wrong shape.".into());
                }
                let positions = pos.read_raw::<i64>().map_err(|e| e.to_string())?;
                for (e, p) in entries.iter_mut().zip(positions.as_chunks::<2>().0) {
                    if p[0] < 0 || p[1] < 0 {
                        return Err("Negative raw frame mapping.".into());
                    }
                    e.path = paths
                        .get(p[0] as usize)
                        .cloned()
                        .ok_or("Invalid raw file mapping.")?;
                    e.frame = p[1] as usize;
                }
            }
            calibration = process
                .dataset("cal_file")
                .ok()
                .and_then(|d| read_strings(&d).ok())
                .and_then(|s| s.first().cloned())
                .unwrap_or_default();
            mask = process
                .dataset("mask_file")
                .ok()
                .and_then(|d| read_strings(&d).ok())
                .and_then(|s| s.first().cloned())
                .unwrap_or_default();
        }
        let mut s = Self::new(
            axis.read_raw::<f64>().map_err(|e| e.to_string())?,
            d.read_raw::<f64>().map_err(|e| e.to_string())?,
            unit,
            wavelength,
            entries,
            paths,
            shape[0],
        )?;
        if let Some(counts) = counts {
            s.total = counts.iter().sum();
            s.file_counts = Arc::new(counts);
        }
        s.background = background;
        s.raw_background = s.background.clone();
        s.calibration = calibration;
        s.mask = mask;
        if group.link_exists("counting_std") {
            s.sigma = Some(Arc::new(read_std(
                &group.dataset("counting_std").map_err(|e| e.to_string())?,
                &shape,
            )?));
            s.raw_sigma = s.sigma.clone();
        }
        if let Ok(spread) = group.dataset("azimuthal_std") {
            if spread.shape() != shape {
                return Err("Azimuthal spread matrix has the wrong shape.".into());
            }
            s.spread = Some(Arc::new(
                spread.read_raw::<f64>().map_err(|e| e.to_string())?,
            ));
            s.raw_spread = s.spread.clone();
        }
        if let Ok(meta) = group.dataset("desktop_metadata") {
            if meta.size() > 16 * 1024 * 1024 {
                return Err("Series metadata exceeds 16 MiB.".into());
            }
            let v: Value =
                serde_json::from_slice(&meta.read_raw::<u8>().map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;
            if let Some(options) = v.get("reader_options") {
                s.reader_options =
                    serde_json::from_value(options.clone()).map_err(|e| e.to_string())?;
                let known_paths: std::collections::HashSet<_> = s.paths.iter().collect();
                if s.reader_options.len() > s.paths.len()
                    || s.reader_options
                        .iter()
                        .any(|(path, v)| !known_paths.contains(path) || !v.is_object())
                {
                    return Err("Invalid stored series source contracts.".into());
                }
            }
            if let Some(total) = v["total"].as_u64() {
                if total > 1_000_000 {
                    return Err("Stored source count exceeds one million frames.".into());
                }
                s.total = total as usize;
            }
            if let Some(selected) = v["selected"].as_u64() {
                if selected >= s.count() as u64 {
                    return Err("Invalid stored frame selection.".into());
                }
                s.selected = selected as usize;
            }
            if let Some(range) = v.get("normalization") {
                s.normalization =
                    serde_json::from_value(range.clone()).map_err(|e| e.to_string())?;
                s.reference = v["reference"]
                    .as_u64()
                    .ok_or("Invalid normalization reference.")?
                    as usize;
                if s.normalization[0] >= s.normalization[1]
                    || s.normalization[1] > s.x.len()
                    || s.reference >= s.count()
                {
                    return Err("Invalid stored normalization.".into());
                }
            }
            if v["normalized"] == true {
                let original = group
                    .dataset("desktop_original")
                    .map_err(|e| e.to_string())?;
                if original.shape() != shape {
                    return Err("Original series matrix has the wrong shape.".into());
                }
                s.raw = Arc::new(original.read_raw::<f64>().map_err(|e| e.to_string())?);
                s.normalized = true;
                s.normalization = serde_json::from_value(v["normalization"].clone())
                    .map_err(|e| e.to_string())?;
                s.reference = v["reference"]
                    .as_u64()
                    .ok_or("Invalid normalization reference.")?
                    as usize;
                if s.normalization[0] >= s.normalization[1]
                    || s.normalization[1] > s.x.len()
                    || s.reference >= s.count()
                {
                    return Err("Invalid stored normalization.".into());
                }
                if let Ok(background) = group.dataset("desktop_original_background") {
                    if background.shape() != shape {
                        return Err("Original background matrix has the wrong shape.".into());
                    }
                    s.raw_background = Some(Arc::new(
                        background.read_raw::<f64>().map_err(|e| e.to_string())?,
                    ));
                }
                if s.sigma.is_some() {
                    s.raw_sigma = Some(Arc::new(read_std(
                        &group
                            .dataset("desktop_original_counting_std")
                            .map_err(|e| e.to_string())?,
                        &shape,
                    )?));
                }
                if let Ok(spread) = group.dataset("desktop_original_spread") {
                    if spread.shape() != shape {
                        return Err("Original spread matrix has the wrong shape.".into());
                    }
                    s.raw_spread = Some(Arc::new(
                        spread.read_raw::<f64>().map_err(|e| e.to_string())?,
                    ));
                }
            }
            s.export_name = v["export_name"]
                .as_str()
                .filter(|s| !s.is_empty())
                .map(str::to_owned);
            s.restore_batch_background(&v["batch_background"])?;
        }
        Ok(s)
    }
}
fn string_attr(location: &hdf5::Location, name: &str, value: &str) -> Result<(), String> {
    let value = hdf5::types::VarLenUnicode::from_str(value).map_err(|e| e.to_string())?;
    location
        .new_attr::<hdf5::types::VarLenUnicode>()
        .shape(())
        .create(name)
        .and_then(|a| a.write_scalar(&value))
        .map_err(|e| e.to_string())
}
fn read_string_attr(a: &hdf5::Attribute) -> Option<String> {
    a.read_scalar::<hdf5::types::VarLenUnicode>()
        .map(|s| s.as_str().into())
        .or_else(|_| {
            a.read_scalar::<hdf5::types::VarLenAscii>()
                .map(|s| s.as_str().into())
        })
        .ok()
}
fn read_strings(d: &hdf5::Dataset) -> Result<Vec<String>, String> {
    if d.size() > 1_000_000 {
        return Err("Too many raw source paths.".into());
    }
    d.read_raw::<hdf5::types::VarLenUnicode>()
        .map(|v| v.iter().map(|s| s.as_str().into()).collect())
        .or_else(|_| {
            d.read_raw::<hdf5::types::VarLenAscii>()
                .map(|v| v.iter().map(|s| s.as_str().into()).collect())
        })
        .map_err(|e| e.to_string())
}

pub(crate) fn read_std(dataset: &hdf5::Dataset, shape: &[usize]) -> Result<Vec<f64>, String> {
    if dataset.shape() != shape {
        return Err("Counting std dimensions differ from the series.".into());
    }
    let values = dataset.read_raw::<f64>().map_err(|e| e.to_string())?;
    if values.iter().any(|v| !v.is_finite() || *v < 0.0) {
        return Err("Counting std must be finite and nonnegative.".into());
    }
    Ok(values)
}

#[cfg(test)]
mod file_index_tests {
    use super::*;
    #[test]
    fn source_index_consumes_each_frame_once_and_preserves_first_and_sparse_frame_counts() {
        let entries: Vec<_> = (0..100_000)
            .map(|i| Entry {
                path: format!("source_{}.h5", i % 10_000),
                frame: i / 10_000 * 3,
            })
            .collect();
        let mut visits = 0;
        let index = index_files(entries.iter().enumerate().inspect(|_| visits += 1));
        assert_eq!(visits, entries.len());
        assert_eq!(index.len(), 10_000);
        for i in 0..10_000 {
            let file = &index[&format!("source_{i}.h5")];
            assert_eq!(file.first, i);
            assert_eq!(file.entries, 10);
            assert_eq!(file.frame_count, 28);
        }
    }
    fn fixture(entries: &[(&str, usize)], paths: &[&str]) -> Series {
        Series::new(
            vec![1., 2.],
            vec![100.; entries.len() * 2],
            "q_A^-1".into(),
            None,
            entries
                .iter()
                .map(|(p, f)| Entry {
                    path: (*p).into(),
                    frame: *f,
                })
                .collect(),
            paths.iter().map(|p| (*p).into()).collect(),
            20,
        )
        .unwrap()
    }
    #[test]
    fn append_metadata_and_processed_round_trip_share_correct_source_lookup() {
        let mut a = fixture(
            &[("missing/a", 2), ("missing/b", 0), ("missing/a", 5)],
            &["missing/b", "missing/a"],
        );
        a.file_counts = Arc::new(vec![7, 20]);
        let mut b = fixture(
            &[("missing/c", 3), ("missing/a", 8)],
            &["missing/a", "missing/c"],
        );
        b.file_counts = Arc::new(vec![40, 10]);
        let a_checkpoint = a.clone();
        let b_checkpoint = b.clone();
        let s = a.append(&b).unwrap();
        assert!(Arc::ptr_eq(&a.paths, &a_checkpoint.paths));
        assert!(Arc::ptr_eq(&a.file_counts, &a_checkpoint.file_counts));
        assert!(Arc::ptr_eq(&b.paths, &b_checkpoint.paths));
        assert!(Arc::ptr_eq(&b.file_counts, &b_checkpoint.file_counts));
        assert_eq!(*a.paths, ["missing/b", "missing/a"]);
        assert_eq!(*a.file_counts, [7, 20]);
        assert_eq!(*b.paths, ["missing/a", "missing/c"]);
        assert_eq!(*b.file_counts, [40, 10]);
        assert_eq!(*s.paths, vec!["missing/b", "missing/a", "missing/c"]);
        assert_eq!(*s.file_counts, vec![7, 40, 10]);
        let metadata = s.metadata("q_A^-1", Value::Null);
        assert_eq!(metadata["files"][0]["first"], 1);
        assert_eq!(metadata["files"][1]["first"], 0);
        assert_eq!(metadata["files"][2]["first"], 3);
        assert_eq!(metadata["files"][1]["frames"], 40);
        let cloned = s.clone();
        assert!(Arc::ptr_eq(&s.file_index, &cloned.file_index));
        assert!(Arc::ptr_eq(&s.paths, &cloned.paths));
        assert!(Arc::ptr_eq(&s.file_counts, &cloned.file_counts));
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("stored.h5");
        s.save(&p).unwrap();
        let restored = Series::load(&p).unwrap();
        assert_eq!(
            restored.metadata("q_A^-1", Value::Null)["files"],
            metadata["files"]
        );
        assert_eq!(
            restored
                .entries
                .iter()
                .map(|e| (&e.path, e.frame))
                .collect::<Vec<_>>(),
            s.entries
                .iter()
                .map(|e| (&e.path, e.frame))
                .collect::<Vec<_>>()
        );
    }
    #[test]
    fn saving_missing_source_paths_extends_only_local_serialized_metadata() {
        let series = fixture(&[("missing/a", 0), ("missing/b", 2)], &["missing/a"]);
        let checkpoint = series.clone();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("local-source-list.h5");
        series.save(&path).unwrap();
        assert!(Arc::ptr_eq(&series.paths, &checkpoint.paths));
        assert!(Arc::ptr_eq(&series.file_counts, &checkpoint.file_counts));
        assert_eq!(*series.paths, ["missing/a"]);
        assert_eq!(*series.file_counts, [1]);
        let restored = Series::load(&path).unwrap();
        assert_eq!(*restored.paths, ["missing/a", "missing/b"]);
        // The existing save fallback records stored rows for an unlisted source.
        assert_eq!(*restored.file_counts, [1, 1]);
        assert_eq!(restored.data, series.data);
    }
}
