//! Source samples remain typed and in stored row order. The numerical/display
//! view flips rows exactly once to the established Dioptas bottom-left convention.
//! Later rotations/flips permute that view without rewriting source samples.
use dioptrin_io::{
    PixelBuffer,
    wrapped::{FrameBuffer, Input, Reader},
};
use rayon::prelude::*;
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

#[cfg(test)]
mod orientation_conversion_tests {
    use super::*;
    fn verify(pixels: PixelBuffer, shape: [usize; 2]) {
        let original = scalar_values(&pixels).unwrap();
        let expected: Vec<_> = original
            .chunks_exact(shape[1])
            .rev()
            .flatten()
            .map(|v| v.to_bits())
            .collect();
        let actual: Vec<_> = oriented_values(&pixels, shape)
            .unwrap()
            .iter()
            .map(|v| v.to_bits())
            .collect();
        assert_eq!(actual, expected);
    }
    #[test]
    fn direct_orientation_preserves_scalar_precision_and_special_values() {
        for pixels in [
            PixelBuffer::U8((0..9).collect()),
            PixelBuffer::I8((-4..5).collect()),
            PixelBuffer::U16(vec![0, 1, 2, 3, 4, 5, 6, 7, u16::MAX]),
            PixelBuffer::U32(vec![0, 1, 2, 3, 4, 5, 6, i32::MAX as u32, u32::MAX]),
            PixelBuffer::I16(vec![i16::MIN, -7, -1, 0, 1, 2, 3, 4, i16::MAX]),
            PixelBuffer::I32(vec![i32::MIN, -7, -1, 0, 1, 2, 3, 4, i32::MAX]),
            PixelBuffer::U64(vec![0, 1, 2, 3, 4, 5, 6, 7, 1 << 53]),
            PixelBuffer::I64(vec![-(1 << 53), -7, -1, 0, 1, 2, 3, 4, 1 << 53]),
            PixelBuffer::F64(vec![
                -0.,
                0.,
                1.,
                f64::NAN,
                f64::from_bits(0x7ff123456789abcd),
                f64::INFINITY,
                f64::NEG_INFINITY,
                f64::MAX,
                -1.25,
            ]),
            PixelBuffer::F32(vec![
                -0.,
                0.,
                1.,
                f32::NAN,
                f32::MAX,
                f32::INFINITY,
                f32::NEG_INFINITY,
                -1.25,
                3.5,
            ]),
            PixelBuffer::F16(vec![
                0, 0x8000, 0x3c00, 0x7c00, 0xfc00, 0x7e01, 1, 0x7bff, 0xbc00,
            ]),
            PixelBuffer::Bool(vec![0, 1, 0, 1, 255, 0, 1, 0, 1]),
        ] {
            verify(pixels, [3, 3]);
        }
        for pixels in [
            PixelBuffer::U64(vec![(1 << 53) + 1]),
            PixelBuffer::I64(vec![-(1 << 53) - 1]),
        ] {
            assert_eq!(
                oriented_values(&pixels, [1, 1]).unwrap_err(),
                scalar_values(&pixels).unwrap_err()
            );
        }
    }
    #[test]
    fn parallel_orientation_handles_odd_heights_and_partial_row_ranges() {
        let shape = [1025, 1027];
        verify(
            PixelBuffer::U32(
                (0..shape[0] * shape[1])
                    .map(|i| (i as u32).wrapping_mul(997))
                    .collect(),
            ),
            shape,
        );
    }
}

#[derive(Clone)]
pub struct Image {
    reader: Option<Arc<Mutex<Reader>>>,
    buffer: Arc<FrameBuffer>,
    combined_pixels: Option<Arc<PixelBuffer>>,
    pub path: PathBuf,
    pub frame: usize,
    pub frames: usize,
    pub shape: [usize; 2],
    pub source_shape: [usize; 2],
    pub source_values: Arc<Vec<f64>>,
    pub(crate) transformations: Vec<crate::transform::Transform>,
    pub values: Arc<Vec<f64>>,
    pub source_dtype: String,
    pub(crate) derived: bool,
    pub(crate) source_variance: Option<Arc<Vec<f64>>>,
    pub ordinary_decodes: u64,
    pub combined: bool,
    pub parallel_pixels: bool,
    pub file_info: Arc<String>,
    pub options: Value,
    pub sources: Vec<crate::hdf5_sources::Source>,
    pub source_discovery_error: Option<String>,
    pub automatic_source: bool,
}
impl Image {
    pub(crate) fn orient(
        &mut self,
        ops: &[crate::transform::Transform],
        control: &crate::control::Control,
    ) -> Result<(), String> {
        self.values =
            crate::transform::apply(&self.source_values, self.source_shape, ops, control)?;
        self.shape = crate::transform::shape(self.source_shape, ops);
        self.transformations = ops.to_vec();
        Ok(())
    }
    pub(crate) fn input_variance(&self) -> Option<Arc<Vec<f64>>> {
        self.source_variance.as_ref().map(|v| {
            crate::transform::apply(
                v,
                self.source_shape,
                &self.transformations,
                &crate::control::Control::default(),
            )
            .expect("validated image transformations")
        })
    }
    pub fn set_derived(
        &mut self,
        values: Vec<f64>,
        variance: Vec<f64>,
        description: &str,
    ) -> Result<(), String> {
        if values.len() != self.shape[0] * self.shape[1] || values.iter().any(|v| !v.is_finite()) {
            return Err("Invalid combined detector samples.".into());
        }
        let values_len = values.len();
        let stored = values
            .chunks_exact(self.shape[1])
            .rev()
            .flatten()
            .copied()
            .collect();
        self.publish_combined(0, self.shape, PixelBuffer::F64(stored))?;
        if variance.len() != values_len || variance.iter().any(|v| !v.is_finite() || *v < 0.0) {
            return Err("Invalid derived image variances.".into());
        }
        self.source_variance = Some(Arc::new(variance));
        self.derived = true;
        self.combined = false;
        self.frames = 1;
        self.file_info = Arc::new(format!("{description}\n{}", self.file_info));
        Ok(())
    }
    pub fn open(path: &Path, options: &Value) -> Result<Self, String> {
        let mut image = Self::prepare(path, options)?;
        image.read(image.frame)?;
        Ok(image)
    }
    /// Discover authoritative metadata and freeze sources without decoding pixels.
    pub fn prepare(path: &Path, options: &Value) -> Result<Self, String> {
        let path = path.canonicalize().map_err(|e| e.to_string())?;
        crate::hdf5_loading::check_snapshot(&path, options)?;
        let mut settings = options.clone();
        settings["path"] = serde_json::json!(path);
        let options = &settings;
        let input = Input::open(&path, Default::default()).map_err(|e| e.to_string())?;
        let follow = match options.get("follow_external_links") {
            None => true,
            Some(v) => v
                .as_bool()
                .ok_or("follow_external_links must be a boolean.")?,
        };
        let hdf5_options = dioptrin_io::hdf5::typed::Options {
            external_links: if follow {
                dioptrin_io::hdf5::typed::ExternalLinks::FollowSnapshot
            } else {
                Default::default()
            },
            ..Default::default()
        };
        let physical_path = input.source_path().map_err(|e| e.to_string())?;
        let owned_transport: Vec<_> = input
            .transport_paths()
            .map_err(|e| e.to_string())?
            .into_iter()
            .filter(|p| *p != path)
            .flat_map(|p| {
                [
                    p.to_path_buf(),
                    p.canonicalize().unwrap_or_else(|_| p.into()),
                ]
            })
            .collect();
        let origin = input
            .provenance()
            .map_err(|e| e.to_string())?
            .origin_directory;
        let mut source_discovery_error = None;
        let mut sources = vec![];
        // Discovery failure must not break an otherwise supported automatic or
        // explicitly selected image. Report it alongside the selected source.
        let codec = if options.get("dataset").is_some() {
            // An explicit selection must work even with conflicting convention
            // metadata; it never falls back to a convention or another dataset.
            dioptrin_io::hdf5::discovery::discover_snapshot(
                physical_path,
                hdf5_options,
                origin.as_deref(),
            )
            .unwrap_or(dioptrin_io::discovery::Codec::Hdf5)
        } else if options.get("cbf_dialect").is_some() {
            dioptrin_io::discovery::Codec::Cbf
        } else if follow {
            match input.discover() {
                Ok(detection) => detection.require_unique().map_err(|e| e.to_string())?,
                Err(_) => dioptrin_io::hdf5::discovery::discover_snapshot(
                    physical_path,
                    hdf5_options,
                    origin.as_deref(),
                )
                .map_err(|e| e.to_string())?,
            }
        } else {
            input
                .discover()
                .map_err(|e| e.to_string())?
                .require_unique()
                .map_err(|e| e.to_string())?
        };
        let is_hdf5 = matches!(
            codec,
            dioptrin_io::discovery::Codec::Hdf5
                | dioptrin_io::discovery::Codec::Eiger
                | dioptrin_io::discovery::Codec::Lima
                | dioptrin_io::discovery::Codec::Lambda
        );
        if is_hdf5 {
            match crate::hdf5_sources::discover(physical_path, hdf5_options, options) {
                Ok(found) => sources = found,
                Err(error) => source_discovery_error = Some(error),
            }
        }
        let mut options = options.clone();
        if codec == dioptrin_io::discovery::Codec::Hdf5 && options.get("dataset").is_none() {
            let first = sources.first().ok_or_else(|| {
                source_discovery_error.clone().unwrap_or_else(|| {
                    "No supported scalar image datasets in this HDF5 file.".into()
                })
            })?;
            options["dataset"] = serde_json::json!(first.dataset);
        }
        let automatic_source = matches!(
            codec,
            dioptrin_io::discovery::Codec::Eiger
                | dioptrin_io::discovery::Codec::Lima
                | dioptrin_io::discovery::Codec::Lambda
        );
        let reader = if is_hdf5 {
            use dioptrin_io::{discovery::Codec, hdf5::typed::Selection};
            let selection = if let Some(dataset) = options.get("dataset") {
                Selection::Dataset(dataset.as_str().ok_or("dataset must be a string.")?)
            } else {
                match codec {
                    Codec::Eiger => Selection::Eiger,
                    Codec::Lima => Selection::Lima,
                    Codec::Lambda => Selection::Lambda,
                    _ => return Err("Choose an HDF5 image dataset.".into()),
                }
            };
            crate::hdf5_loading::open(input, selection, hdf5_options, &options)?
        } else if let Some(dialect) = options.get("cbf_dialect") {
            let mode = match dialect.as_str() {
                Some("legacy32") => dioptrin_io::cbf::ByteOffsetMode::Legacy32,
                Some("extended64") => dioptrin_io::cbf::ByteOffsetMode::Extended64,
                _ => return Err("Choose legacy32 or extended64 CBF dialect.".into()),
            };
            input
                .read(
                    dioptrin_io::wrapped::Format::Cbf(mode),
                    Default::default(),
                    Default::default(),
                )
                .map_err(|e| e.to_string())?
        } else {
            input
                .read_discovered(Default::default(), Default::default())
                .map_err(|e| e.to_string())?
        };
        if is_hdf5 {
            options["follow_external_links"] = serde_json::json!(follow);
            let mut files = vec![];
            for b in reader.source_bindings().map_err(|e| e.to_string())? {
                for p in [b.requested, b.resolved] {
                    if !owned_transport.contains(&p) && !files.iter().any(|(path, _)| *path == p) {
                        files.push((p.clone(), FileIdentity::read(&p)?));
                    }
                }
            }
            options["hdf5_snapshot"] = crate::hdf5_loading::snapshot(&path, files);
        }
        let frames = reader.frames();
        if let Some(dataset) = options.get("dataset").and_then(Value::as_str)
            && !sources.iter().any(|s| s.dataset == dataset)
            && let Some(dioptrin_io::wrapped::Metadata::Hdf5(m)) = reader.metadata(0)
        {
            sources.push(crate::hdf5_sources::Source {
                dataset: dataset.into(),
                needs_bindings: false,
                frames: Some(frames),
                shape: Some(m.shape),
            });
        }
        let frame = match options.get("frame") {
            None => 0,
            Some(v) => usize::try_from(v.as_u64().ok_or("frame must be a nonnegative integer.")?)
                .map_err(|e| e.to_string())?,
        };
        let shape = metadata_shape(reader.metadata(frame));
        if frame >= frames {
            return Err("Frame is outside the detector series.".into());
        }
        if shape != [0, 0]
            && (shape.contains(&0)
                || shape[0]
                    .checked_mul(shape[1])
                    .is_none_or(|n| n > 64 * 1024 * 1024))
        {
            return Err(
                "Detector plane exceeds the native session's 64-million-pixel bound.".into(),
            );
        }
        let image = Self {
            reader: Some(Arc::new(Mutex::new(reader))),
            buffer: Arc::new(FrameBuffer::default()),
            combined_pixels: None,
            path,
            frame,
            frames,
            shape,
            source_shape: shape,
            source_values: Arc::new(vec![]),
            transformations: vec![],
            values: Arc::new(vec![]),
            source_dtype: String::new(),
            derived: false,
            source_variance: None,
            ordinary_decodes: 0,
            combined: false,
            parallel_pixels: false,
            file_info: Arc::new(String::new()),
            sources,
            source_discovery_error,
            automatic_source,
            options: Value::Object(
                [
                    "dataset",
                    "follow_external_links",
                    "cbf_dialect",
                    "hdf5_bindings",
                    "hdf5_printf",
                    "hdf5_snapshot",
                ]
                .into_iter()
                .filter_map(|k| options.get(k).map(|v| (k.into(), v.clone())))
                .collect(),
            ),
        };
        Ok(image)
    }
    pub(crate) fn binding_request(path: &Path, options: &Value) -> Result<Option<Value>, String> {
        use dioptrin_io::{
            discovery::Codec,
            hdf5::typed::{self, Selection},
        };
        let path = path.canonicalize().map_err(|e| e.to_string())?;
        crate::hdf5_loading::check_snapshot(&path, options)?;
        let mut settings = options.clone();
        settings["path"] = serde_json::json!(path);
        let options = &settings;
        let input = Input::open(&path, Default::default()).map_err(|e| e.to_string())?;
        let physical = input.source_path().map_err(|e| e.to_string())?;
        let policy = typed::Options {
            external_links: if options["follow_external_links"].as_bool() == Some(false) {
                typed::ExternalLinks::Reject
            } else {
                typed::ExternalLinks::FollowSnapshot
            },
            ..Default::default()
        };
        if let Some(dataset) = options["dataset"].as_str() {
            return crate::hdf5_loading::request(
                physical,
                Selection::Dataset(dataset),
                policy,
                options,
            );
        }
        let origin = input
            .provenance()
            .map_err(|e| e.to_string())?
            .origin_directory;
        let codec = match input
            .discover()
            .map_err(|e| e.to_string())
            .and_then(|d| d.require_unique().map_err(|e| e.to_string()))
        {
            Ok(c) => c,
            Err(_) => {
                dioptrin_io::hdf5::discovery::discover_snapshot(physical, policy, origin.as_deref())
                    .map_err(|e| e.to_string())?
            }
        };
        let selection = match codec {
            Codec::Eiger => Selection::Eiger,
            Codec::Lima => Selection::Lima,
            Codec::Lambda => Selection::Lambda,
            Codec::Hdf5 => {
                for dataset in
                    dioptrin_io::hdf5::catalog::image_paths(physical, policy, origin.as_deref())
                        .map_err(|e| e.to_string())?
                {
                    if let Some(request) = crate::hdf5_loading::request(
                        physical,
                        Selection::Dataset(&dataset),
                        policy,
                        options,
                    )? {
                        let mut request = request;
                        request["options"]["dataset"] = serde_json::json!(dataset);
                        return Ok(Some(request));
                    }
                }
                return Ok(None);
            }
            _ => return Ok(None),
        };
        crate::hdf5_loading::request(physical, selection, policy, options)
    }
    pub fn from_cached(
        path: PathBuf,
        frame: usize,
        frames: usize,
        shape: [usize; 2],
        values: Vec<f64>,
        options: Value,
    ) -> Result<Self, String> {
        if shape.contains(&0)
            || shape[0]
                .checked_mul(shape[1])
                .is_none_or(|n| n > 64 * 1024 * 1024 || n != values.len())
            || frames == 0
            || frame >= frames
        {
            return Err("Invalid project detector cache dimensions or samples.".into());
        }
        let stored = values
            .chunks_exact(shape[1])
            .rev()
            .flatten()
            .copied()
            .collect();
        let source_values = Arc::new(values);
        Ok(Self {
            reader: None,
            buffer: Arc::new(FrameBuffer::default()),
            combined_pixels: Some(Arc::new(PixelBuffer::F64(stored))),
            path,
            frame,
            frames,
            shape,
            source_shape: shape,
            source_values: source_values.clone(),
            transformations: vec![],
            values: source_values,
            source_dtype: "F64".into(),
            derived: true,
            source_variance: None,
            ordinary_decodes: 0,
            combined: false,
            parallel_pixels: false,
            file_info: Arc::new(
                "Restored project pixels; original source is not reread until navigation.".into(),
            ),
            sources: vec![],
            source_discovery_error: None,
            automatic_source: false,
            options,
        })
    }
    pub fn frame_source_shape(&self, index: usize) -> Result<[usize; 2], String> {
        if let Some(reader) = &self.reader {
            let shape = metadata_shape(reader.lock().unwrap().metadata(index));
            return Ok(if shape == [0, 0] {
                self.source_shape
            } else {
                shape
            });
        }
        let mut options = self.options.clone();
        options["frame"] = serde_json::json!(index);
        Ok(Self::prepare(&self.path, &options)?.source_shape)
    }
    pub fn read(&mut self, index: usize) -> Result<(), String> {
        if self.reader.is_none() {
            let mut options = self.options.clone();
            options["frame"] = serde_json::json!(index);
            let mut candidate = Self::open(&self.path, &options)?;
            candidate.orient(&self.transformations, &crate::control::Control::default())?;
            *self = candidate;
            return Ok(());
        }
        // A failed read must leave the preceding published frame intact.
        let mut candidate = FrameBuffer::default();
        self.reader
            .as_ref()
            .unwrap()
            .lock()
            .unwrap()
            .read_frame_into(index, &mut candidate)
            .map_err(|e| e.to_string())?;
        let shape = candidate
            .shape()
            .ok_or("Only scalar 2D detector planes are supported.")?;
        if shape.contains(&0)
            || shape[0]
                .checked_mul(shape[1])
                .is_none_or(|n| n > 64 * 1024 * 1024)
        {
            return Err(
                "Detector plane exceeds the native session's 64-million-pixel bound.".into(),
            );
        }
        let pixels = candidate
            .pixels()
            .ok_or("The reader returned no original samples.")?;
        if pixels.len() != shape[0] * shape[1] || candidate.sample_shape() != Some(shape.to_vec()) {
            return Err("Color, component and complex arrays require an explicit scientific interpretation.".into());
        }
        let values = oriented_values(pixels, shape)?;
        self.source_dtype = format!("{:?}", pixels.pixel_type());
        self.derived = false;
        self.source_variance = None;
        self.ordinary_decodes += 1;
        self.combined = false;
        self.parallel_pixels = false;
        self.buffer = Arc::new(candidate);
        self.combined_pixels = None;
        self.source_values = Arc::new(values);
        self.source_shape = shape;
        let ops = self.transformations.clone();
        self.orient(&ops, &crate::control::Control::default())?;
        self.frame = index;
        self.file_info = Arc::new(self.metadata_text());
        Ok(())
    }
    pub fn original_pixels(&self) -> &PixelBuffer {
        self.combined_pixels
            .as_deref()
            .unwrap_or_else(|| self.buffer.pixels().expect("published frame has samples"))
    }
    pub fn check_sources(&self) -> Result<(), String> {
        if self.reader.is_none() {
            return Ok(());
        }
        self.reader
            .as_ref()
            .unwrap()
            .lock()
            .unwrap()
            .check_sources()
            .map_err(|e| e.to_string())
    }
    pub fn source_fingerprint(&self) -> Result<Vec<(PathBuf, FileIdentity)>, String> {
        if self.reader.is_none() {
            return Err("Open the original detector source before bulk processing.".into());
        }
        self.check_sources()?;
        if let Some(files) = crate::hdf5_loading::fingerprint(&self.path, &self.options)? {
            return Ok(files);
        }
        let bindings = self
            .reader
            .as_ref()
            .unwrap()
            .lock()
            .unwrap()
            .source_bindings()
            .map_err(|e| e.to_string())?;
        let mut paths = std::collections::BTreeSet::from([self.path.clone()]);
        for b in bindings {
            paths.insert(b.requested);
            paths.insert(b.resolved);
        }
        paths
            .into_iter()
            .map(|p| FileIdentity::read(&p).map(|identity| (p, identity)))
            .collect()
    }
    pub fn single_dataset_series(&self) -> bool {
        let Some(reader) = &self.reader else {
            return false;
        };
        let reader = reader.lock().unwrap();
        matches!(reader.metadata(0), Some(dioptrin_io::wrapped::Metadata::Hdf5(m))
            if m.first_frame == 0 && m.source_shape.first() == Some(&self.frames))
    }
    pub fn combined_source(&self, index: usize) -> Result<Option<CombinedSource>, String> {
        self.check_sources()?;
        if !self.transformations.is_empty() {
            return Ok(None);
        }
        let Some(source_reader) = &self.reader else {
            return Ok(None);
        };
        let reader = source_reader.lock().unwrap();
        let Some(dioptrin_io::wrapped::Metadata::Hdf5(m)) = reader.metadata(index) else {
            return Ok(None);
        };
        // Same narrow admission as Qt; RawReader repeats layout and codec checks.
        if m.virtual_dataset.is_some()
            || m.external_raw.is_some()
            || m.source_file != self.path
            || m.source_shape.len() != 3
            || m.little_endian != cfg!(target_endian = "little")
            || m.filters.len() != 1
            || m.filters[0].id != 32008
            || m.filters[0].parameters.get(4) != Some(&2)
            || !matches!(
                m.pixel_type,
                dioptrin_io::PixelType::U16 | dioptrin_io::PixelType::U32
            )
        {
            return Ok(None);
        }
        Ok(Some(CombinedSource {
            path: self.path.clone(),
            dataset: m.dataset.clone(),
            shape: m.shape,
            frame: index - m.first_frame,
            identity: FileIdentity::read(&self.path)?,
            bindings: reader.source_bindings().map_err(|e| e.to_string())?,
        }))
    }
    pub fn publish_combined(
        &mut self,
        index: usize,
        shape: [usize; 2],
        pixels: PixelBuffer,
    ) -> Result<(), String> {
        let mut trace = crate::frame_trace::FrameTrace::new("source-publish", index as u64);
        self.check_sources()?;
        if shape.contains(&0)
            || shape[0]
                .checked_mul(shape[1])
                .is_none_or(|n| n > 64 * 1024 * 1024)
            || pixels.len() != shape[0] * shape[1]
        {
            return Err("Invalid combined detector dimensions.".into());
        }
        trace.mark("validate source");
        let values = oriented_values(&pixels, shape)?;
        trace.mark("typed to oriented f64");
        self.source_dtype = format!("{:?}", pixels.pixel_type());
        self.derived = false;
        self.source_variance = None;
        self.combined_pixels = Some(Arc::new(pixels));
        self.buffer = Arc::new(FrameBuffer::default());
        self.combined = true;
        self.parallel_pixels = false;
        self.source_values = Arc::new(values);
        self.source_shape = shape;
        let ops = self.transformations.clone();
        self.orient(&ops, &crate::control::Control::default())?;
        self.frame = index;
        self.file_info = Arc::new(self.metadata_text());
        trace.mark("publish metadata");
        Ok(())
    }
    /// Stored acquisition identity/pitch, without altering the original metadata.
    pub fn detector_hints(&self) -> (String, Option<[f64; 2]>) {
        use dioptrin_io::wrapped::Metadata as M;
        let mut description = String::new();
        let mut pixels = None;
        if let Some(reader) = &self.reader {
            let reader = reader.lock().unwrap();
            let header = match reader.metadata(self.frame) {
                Some(M::Cbf(m)) => m.pilatus.as_ref(),
                Some(M::DetectorTiff(m)) => match m.header {
                    dioptrin_io::detector_tiff::Header::Pilatus(h) => Some(h),
                    _ => None,
                },
                _ => None,
            };
            if let Some(h) = header {
                description = h.fields.get("Detector").cloned().unwrap_or_default();
                if let Some(value) = h.fields.get("Pixel_size") {
                    let numbers: Vec<f64> = value
                        .split(|c: char| c.is_whitespace() || c == 'x' || c == ',')
                        .filter_map(|s| s.parse().ok())
                        .collect();
                    if numbers.len() == 2 && !value.contains("um") && !value.contains("µm") {
                        pixels = Some([numbers[1], numbers[0]]);
                    }
                }
            }
            if let Some(h) = reader.hdf5_reader() {
                for (k, v) in h.fields() {
                    if ["detector", "description", "model"].contains(&k.as_str()) {
                        description.push(' ');
                        description.push_str(v);
                    }
                }
            }
        }
        // Supplement HDF5 acquisition metadata from standard NeXus scalar fields.
        if matches!(
            self.path.extension().and_then(|e| e.to_str()),
            Some("h5" | "hdf5" | "nxs")
        ) && let Ok(file) = hdf5::File::open(&self.path)
        {
            for base in [
                "/entry/instrument/detector",
                "/entry/instrument/detector/detectorSpecific",
                "/entry_0000/instrument/eiger/detector_information",
            ] {
                for key in ["description", "detector_model", "model"] {
                    if let Some(dataset) = metadata_dataset(&file, &format!("{base}/{key}"))
                        && dataset.size() == 1
                    {
                        if let Ok(s) = dataset.read_scalar::<hdf5::types::VarLenUnicode>() {
                            description.push(' ');
                            description.push_str(s.as_str());
                        } else if let Ok(s) = dataset.read_scalar::<hdf5::types::VarLenAscii>() {
                            description.push(' ');
                            description.push_str(s.as_str());
                        }
                    }
                }
            }
            let number = |key: &str| {
                metadata_dataset(&file, &format!("/entry/instrument/detector/{key}"))
                    .filter(|d| d.size() == 1)?
                    .read_scalar::<f64>()
                    .ok()
            };
            if let (Some(y), Some(x)) = (number("y_pixel_size"), number("x_pixel_size")) {
                pixels = Some([y, x]);
            }
            if pixels.is_none() {
                let base = "/entry_0000/instrument/eiger/detector_information/pixel_size";
                if let (Some(y), Some(x)) = (
                    metadata_dataset(&file, &format!("{base}/ysize")),
                    metadata_dataset(&file, &format!("{base}/xsize")),
                ) && let (Ok(y), Ok(x)) = (y.read_scalar::<f64>(), x.read_scalar::<f64>())
                {
                    pixels = Some([y, x]);
                }
            }
        }
        // Acquisition headers include generation/readout labels that are not
        // separate physical geometries in the pyFAI catalogue. Normalize only
        // explicit tokens; e.g. Pilatus 300k must keep its model number.
        let mut identity = description
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ")
            .to_ascii_uppercase();
        for (label, physical) in [
            ("PILATUS3 X ", "PILATUS "),
            ("PILATUS3 S ", "PILATUS "),
            ("PILATUS3 ", "PILATUS "),
            ("PILATUS2 X ", "PILATUS "),
            ("PILATUS2 ", "PILATUS "),
            ("EIGER2 XE ", "EIGER2 "),
            ("EIGER2 X ", "EIGER2 "),
            ("EIGER X ", "EIGER "),
        ] {
            identity = identity.replace(label, physical);
        }
        (identity, pixels)
    }
    fn metadata_text(&self) -> String {
        use dioptrin_io::wrapped::Metadata as M;
        let Some(source_reader) = &self.reader else {
            return self.file_info.as_ref().clone();
        };
        let reader = source_reader.lock().unwrap();
        let mut text = format!(
            "Source: {}\nFrame: {} / {}\nShape: {} × {}\nStored dtype: {}\n\n",
            self.path.display(),
            self.frame + 1,
            self.frames,
            self.shape[0],
            self.shape[1],
            self.source_dtype
        );
        let fields = match reader.metadata(self.frame) {
            Some(M::Hdf5(m)) => format!(
                "{m:#?}\nAttributes:\n{:#?}",
                reader.hdf5_reader().unwrap().fields()
            ),
            Some(M::DetectorTiff(m)) => format!("{:#?}\nAcquisition:\n{:#?}", m.image, m.header),
            Some(M::Native(m)) => format!("{m:#?}"),
            Some(M::Edf(m)) => format!("{m:#?}"),
            Some(M::Cbf(m)) => format!("{m:#?}"),
            Some(M::Tiff(m)) => format!("{m:#?}"),
            Some(M::Mar345(m)) => format!("{m:#?}"),
            Some(M::Esperanto(m)) => format!("{m:#?}"),
            Some(M::Fit2d(m)) => format!("{m:#?}"),
            Some(M::Kcd(m)) => format!("{m:#?}"),
            Some(M::Mpa(m)) => format!("{m:#?}"),
            Some(M::Ge(m)) => format!("{m:#?}"),
            Some(M::Pixi(m)) => format!("{m:#?}"),
            Some(M::Spe(m)) => format!("{m:#?}"),
            Some(M::Mrc(m)) => format!("{m:#?}"),
            Some(M::Dm3(m)) => format!("{m:#?}"),
            Some(M::Bruker(m)) => format!("{m:#?}"),
            Some(M::Oxford(m)) => format!("{m:#?}"),
            Some(M::Raxis(m)) => format!("{m:#?}"),
            Some(M::Xsd(m)) => format!("{m:#?}"),
            _ => String::new(),
        };
        text.push_str(&fields);
        if text.len() > 256 * 1024 {
            let mut end = 256 * 1024;
            while !text.is_char_boundary(end) {
                end -= 1;
            }
            text.truncate(end);
            text.push_str("\n[Display metadata truncated; source metadata retained in reader]");
        }
        text
    }
}

#[derive(Clone, PartialEq)]
pub struct CombinedSource {
    pub path: PathBuf,
    pub dataset: String,
    pub shape: [usize; 2],
    pub frame: usize,
    pub bindings: Vec<dioptrin_io::SourceBinding>,
    pub identity: FileIdentity,
}
#[derive(Clone, Debug, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct FileIdentity {
    length: u64,
    modified: std::time::SystemTime,
    object: (u64, u64),
}
impl FileIdentity {
    pub fn read(path: &Path) -> Result<Self, String> {
        #[cfg(not(windows))]
        let m = std::fs::metadata(path).map_err(|e| e.to_string())?;
        #[cfg(windows)]
        let handle = std::fs::File::open(path).map_err(|e| e.to_string())?;
        #[cfg(windows)]
        let m = handle.metadata().map_err(|e| e.to_string())?;
        #[cfg(unix)]
        let object = {
            use std::os::unix::fs::MetadataExt;
            (m.dev(), m.ino())
        };
        #[cfg(windows)]
        let object = {
            use std::os::windows::io::AsRawHandle;
            use windows_sys::Win32::Storage::FileSystem::{
                BY_HANDLE_FILE_INFORMATION, GetFileInformationByHandle,
            };
            let mut information = std::mem::MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
            // SAFETY: the owned file keeps its handle valid, and the output
            // pointer provides enough aligned storage for the Windows struct.
            if unsafe {
                GetFileInformationByHandle(handle.as_raw_handle(), information.as_mut_ptr())
            } == 0
            {
                return Err(std::io::Error::last_os_error().to_string());
            }
            // SAFETY: the successful call initialized the complete struct.
            let information = unsafe { information.assume_init() };
            (
                u64::from(information.dwVolumeSerialNumber),
                (u64::from(information.nFileIndexHigh) << 32)
                    | u64::from(information.nFileIndexLow),
            )
        };
        #[cfg(not(any(unix, windows)))]
        let object = (0, 0);
        Ok(Self {
            length: m.len(),
            modified: m.modified().map_err(|e| e.to_string())?,
            object,
        })
    }
}

#[cfg(test)]
mod file_identity_tests {
    use super::*;

    #[test]
    fn replacing_a_file_with_matching_size_and_mtime_changes_its_identity() {
        let directory = tempfile::tempdir().unwrap();
        let source = directory.path().join("source.bin");
        let replacement = directory.path().join("replacement.bin");
        std::fs::write(&source, [1, 2, 3, 4]).unwrap();
        std::fs::write(&replacement, [5, 6, 7, 8]).unwrap();
        let original = FileIdentity::read(&source).unwrap();
        std::fs::File::options()
            .write(true)
            .open(&replacement)
            .unwrap()
            .set_times(std::fs::FileTimes::new().set_modified(original.modified))
            .unwrap();
        std::fs::rename(&source, directory.path().join("old.bin")).unwrap();
        std::fs::rename(&replacement, &source).unwrap();
        let changed = FileIdentity::read(&source).unwrap();
        assert_eq!(original.length, changed.length);
        assert_eq!(original.modified, changed.modified);
        assert_ne!(original.object, changed.object);
        assert_ne!(original, changed);
    }
}

/// Identification is optional: do not follow metadata aliases/external files
/// outside the authoritative image reader's frozen source graph.
fn metadata_dataset(file: &hdf5::File, path: &str) -> Option<hdf5::Dataset> {
    let parts: Vec<_> = path.trim_start_matches('/').split('/').collect();
    let mut group = file.group("/").ok()?;
    for (index, part) in parts.iter().enumerate() {
        let kind = group
            .find_link(Default::default(), Default::default(), |name, info| {
                Ok((name == *part).then_some(info.link_type))
            })
            .ok()??;
        if kind != hdf5::LinkType::Hard {
            return None;
        }
        if index + 1 == parts.len() {
            return group.dataset(part).ok();
        }
        group = group.group(part).ok()?;
    }
    None
}

// Cast each source row directly into its final bottom-up position. Large planes
// use disjoint row ranges, avoiding the old separate full-plane swapping pass.
fn oriented_values(pixels: &PixelBuffer, shape: [usize; 2]) -> Result<Vec<f64>, String> {
    fn convert<T: Copy + Sync>(
        data: &[T],
        [h, w]: [usize; 2],
        cast: impl Fn(T) -> f64 + Sync,
    ) -> Vec<f64> {
        let mut out = vec![0.; data.len()];
        let write = |source: &[T], target: &mut [f64]| {
            for (row, target) in source.chunks_exact(w).rev().zip(target.chunks_exact_mut(w)) {
                for (&value, target) in row.iter().zip(target) {
                    *target = cast(value);
                }
            }
        };
        if data.len() >= 1_000_000 {
            let workers = crate::worker_pool::threads();
            let rows = h.div_ceil(workers);
            crate::worker_pool::install(|| {
                out.par_chunks_mut(rows * w)
                    .enumerate()
                    .for_each(|(part, target)| {
                        let end = h - part * rows;
                        let begin = end - target.len() / w;
                        write(&data[begin * w..end * w], target);
                    });
            });
        } else {
            write(data, &mut out);
        }
        out
    }
    macro_rules! cast {
        ($values:expr) => {
            convert($values, shape, |v| v as f64)
        };
    }
    Ok(match pixels {
        PixelBuffer::U8(v) => cast!(v),
        PixelBuffer::U16(v) => cast!(v),
        PixelBuffer::U32(v) => cast!(v),
        PixelBuffer::I8(v) => cast!(v),
        PixelBuffer::I16(v) => cast!(v),
        PixelBuffer::I32(v) => cast!(v),
        PixelBuffer::F32(v) => cast!(v),
        PixelBuffer::F64(v) => cast!(v),
        PixelBuffer::Bool(v) => convert(v, shape, |v| f64::from(v != 0)),
        PixelBuffer::F16(v) => convert(v, shape, |v| half::f16::from_bits(v).to_f64()),
        PixelBuffer::U64(v) => {
            if v.iter().any(|&v| v > 1_u64 << 53) {
                return Err(
                    "Integer counts above 2^53 require an exact-integer numerical engine.".into(),
                );
            }
            cast!(v)
        }
        PixelBuffer::I64(v) => {
            if v.iter().any(|&v| v.unsigned_abs() > 1_u64 << 53) {
                return Err(
                    "Integer counts outside ±2^53 require an exact-integer numerical engine."
                        .into(),
                );
            }
            cast!(v)
        }
        _ => {
            return Err(
                "Complex detector samples require an explicit scientific interpretation.".into(),
            );
        }
    })
}
pub fn scalar_values(pixels: &PixelBuffer) -> Result<Vec<f64>, String> {
    macro_rules! convert {
        ($v:expr) => {
            $v.iter().map(|&v| v as f64).collect()
        };
    }
    Ok(match pixels {
        PixelBuffer::U8(v) => convert!(v),
        PixelBuffer::U16(v) => convert!(v),
        PixelBuffer::U32(v) => convert!(v),
        PixelBuffer::I8(v) => convert!(v),
        PixelBuffer::I16(v) => convert!(v),
        PixelBuffer::I32(v) => convert!(v),
        PixelBuffer::F32(v) => convert!(v),
        PixelBuffer::F64(v) => v.clone(),
        PixelBuffer::Bool(v) => v.iter().map(|&v| f64::from(v != 0)).collect(),
        PixelBuffer::F16(v) => v
            .iter()
            .map(|&v| half::f16::from_bits(v).to_f64())
            .collect(),
        PixelBuffer::U64(v) => {
            if v.iter().any(|&v| v > 1_u64 << 53) {
                return Err(
                    "Integer counts above 2^53 require an exact-integer numerical engine.".into(),
                );
            }
            convert!(v)
        }
        PixelBuffer::I64(v) => {
            if v.iter().any(|&v| v.unsigned_abs() > 1_u64 << 53) {
                return Err(
                    "Integer counts outside ±2^53 require an exact-integer numerical engine."
                        .into(),
                );
            }
            convert!(v)
        }
        _ => {
            return Err(
                "Complex detector samples require an explicit scientific interpretation.".into(),
            );
        }
    })
}

fn metadata_shape(metadata: Option<dioptrin_io::wrapped::Metadata<'_>>) -> [usize; 2] {
    use dioptrin_io::wrapped::Metadata as M;
    match metadata {
        Some(M::Hdf5(m)) => m.shape,
        Some(M::Native(m)) => m.shape,
        Some(M::Edf(m)) => m.shape,
        Some(M::Cbf(m)) => m.shape,
        Some(M::Tiff(m)) => m.shape,
        Some(M::DetectorTiff(m)) => m.image.shape,
        Some(M::Mar345(m)) => m.shape,
        Some(M::Esperanto(m)) => m.shape,
        Some(M::Fit2d(m)) => m.shape,
        Some(M::Kcd(m)) => m.shape,
        Some(M::Mpa(m)) => m.shape,
        Some(M::Ge(m)) => m.shape,
        Some(M::Pixi(m)) => m.shape,
        Some(M::Spe(m)) => m.shape,
        Some(M::Mrc(m)) => m.shape,
        Some(M::Dm3(m)) => m.images[m.selected_image].shape,
        Some(M::Bruker(m)) => m.shape,
        Some(M::Oxford(m)) => m.shape,
        Some(M::Raxis(m)) => m.shape,
        Some(M::Xsd(m)) => m.shape,
        _ => [0, 0],
    }
}
