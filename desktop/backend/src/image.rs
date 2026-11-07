//! Source samples remain typed and in stored row order. The numerical/display
//! view flips rows exactly once to the established Dioptas bottom-left convention.
use dioptrin_io::{
    PixelBuffer,
    wrapped::{FrameBuffer, Input, Reader},
};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

#[derive(Clone)]
pub struct Image {
    reader: Option<Arc<Mutex<Reader>>>,
    buffer: Arc<FrameBuffer>,
    combined_pixels: Option<Arc<PixelBuffer>>,
    pub path: PathBuf,
    pub frame: usize,
    pub frames: usize,
    pub shape: [usize; 2],
    pub values: Arc<Vec<f64>>,
    pub source_dtype: String,
    pub ordinary_decodes: u64,
    pub combined: bool,
    pub file_info: Arc<String>,
    pub options: Value,
}
impl Image {
    pub fn set_derived(&mut self, values: Vec<f64>, description: &str) -> Result<(), String> {
        if values.len() != self.shape[0] * self.shape[1] || values.iter().any(|v| !v.is_finite()) {
            return Err("Invalid combined detector samples.".into());
        }
        let stored = values
            .chunks_exact(self.shape[1])
            .rev()
            .flatten()
            .copied()
            .collect();
        self.publish_combined(0, self.shape, PixelBuffer::F64(stored))?;
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
        let input = Input::open(&path, Default::default()).map_err(|e| e.to_string())?;
        let follow = match options.get("follow_external_links") {
            None => false,
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
        let reader = if let Some(dataset) = options.get("dataset") {
            input.read_hdf5(
                dioptrin_io::hdf5::typed::Selection::Dataset(
                    dataset.as_str().ok_or("dataset must be a string.")?,
                ),
                hdf5_options,
                None,
            )
        } else if let Some(dialect) = options.get("cbf_dialect") {
            let mode = match dialect.as_str() {
                Some("legacy32") => dioptrin_io::cbf::ByteOffsetMode::Legacy32,
                Some("extended64") => dioptrin_io::cbf::ByteOffsetMode::Extended64,
                _ => return Err("Choose legacy32 or extended64 CBF dialect.".into()),
            };
            input.read(
                dioptrin_io::wrapped::Format::Cbf(mode),
                Default::default(),
                Default::default(),
            )
        } else {
            use dioptrin_io::{discovery::Codec, hdf5::typed::Selection};
            let codec = input
                .discover()
                .map_err(|e| e.to_string())?
                .require_unique()
                .map_err(|e| e.to_string())?;
            match codec {
                Codec::Eiger => input.read_hdf5(Selection::Eiger, hdf5_options, None),
                Codec::Lima => input.read_hdf5(Selection::Lima, hdf5_options, None),
                Codec::Lambda => input.read_hdf5(Selection::Lambda, hdf5_options, None),
                _ => input.read_discovered(Default::default(), Default::default()),
            }
        }
        .map_err(|e| e.to_string())?;
        let frames = reader.frames();
        let frame = match options.get("frame") {
            None => 0,
            Some(v) => usize::try_from(v.as_u64().ok_or("frame must be a nonnegative integer.")?)
                .map_err(|e| e.to_string())?,
        };
        use dioptrin_io::wrapped::Metadata as M;
        let shape = match reader.metadata(frame) {
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
        };
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
            values: Arc::new(vec![]),
            source_dtype: String::new(),
            ordinary_decodes: 0,
            combined: false,
            file_info: Arc::new(String::new()),
            options: Value::Object(
                ["dataset", "follow_external_links", "cbf_dialect"]
                    .into_iter()
                    .filter_map(|k| options.get(k).map(|v| (k.into(), v.clone())))
                    .collect(),
            ),
        };
        Ok(image)
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
        Ok(Self {
            reader: None,
            buffer: Arc::new(FrameBuffer::default()),
            combined_pixels: Some(Arc::new(PixelBuffer::F64(stored))),
            path,
            frame,
            frames,
            shape,
            values: Arc::new(values),
            source_dtype: "F64".into(),
            ordinary_decodes: 0,
            combined: false,
            file_info: Arc::new(
                "Restored project pixels; original source is not reread until navigation.".into(),
            ),
            options,
        })
    }
    pub fn read(&mut self, index: usize) -> Result<(), String> {
        if self.reader.is_none() {
            let mut options = self.options.clone();
            options["frame"] = serde_json::json!(index);
            let candidate = Self::open(&self.path, &options)?;
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
        let mut values = scalar_values(pixels)?;
        let width = shape[1];
        for row in 0..shape[0] / 2 {
            let opposite = (shape[0] - 1 - row) * width;
            for col in 0..width {
                values.swap(row * width + col, opposite + col);
            }
        }
        self.source_dtype = format!("{:?}", pixels.pixel_type());
        self.ordinary_decodes += 1;
        self.combined = false;
        self.buffer = Arc::new(candidate);
        self.combined_pixels = None;
        self.values = Arc::new(values);
        self.shape = shape;
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
    pub fn combined_source(&self, index: usize) -> Result<Option<CombinedSource>, String> {
        self.check_sources()?;
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
        self.check_sources()?;
        if shape.contains(&0)
            || shape[0]
                .checked_mul(shape[1])
                .is_none_or(|n| n > 64 * 1024 * 1024)
            || pixels.len() != shape[0] * shape[1]
        {
            return Err("Invalid combined detector dimensions.".into());
        }
        let mut values = scalar_values(&pixels)?;
        for row in 0..shape[0] / 2 {
            for col in 0..shape[1] {
                values.swap(row * shape[1] + col, (shape[0] - row - 1) * shape[1] + col);
            }
        }
        self.source_dtype = format!("{:?}", pixels.pixel_type());
        self.combined_pixels = Some(Arc::new(pixels));
        self.buffer = Arc::new(FrameBuffer::default());
        self.combined = true;
        self.values = Arc::new(values);
        self.shape = shape;
        self.frame = index;
        self.file_info = Arc::new(self.metadata_text());
        Ok(())
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
#[derive(Clone, PartialEq)]
pub struct FileIdentity {
    length: u64,
    modified: std::time::SystemTime,
    object: (u64, u64),
}
impl FileIdentity {
    pub fn read(path: &Path) -> Result<Self, String> {
        let m = std::fs::metadata(path).map_err(|e| e.to_string())?;
        #[cfg(unix)]
        let object = {
            use std::os::unix::fs::MetadataExt;
            (m.dev(), m.ino())
        };
        #[cfg(not(unix))]
        let object = (0, 0);
        Ok(Self {
            length: m.len(),
            modified: m.modified().map_err(|e| e.to_string())?,
            object,
        })
    }
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
