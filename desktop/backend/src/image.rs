//! Source samples remain typed and in stored row order. The numerical/display
//! view flips rows exactly once to the established Dioptas bottom-left convention.
use dioptrin_io::{
    PixelBuffer,
    wrapped::{FrameBuffer, Input, Reader},
};
use serde_json::Value;
use std::path::{Path, PathBuf};

pub struct Image {
    reader: Reader,
    buffer: FrameBuffer,
    pub path: PathBuf,
    pub frame: usize,
    pub frames: usize,
    pub shape: [usize; 2],
    pub values: Vec<f64>,
    pub source_dtype: String,
}
impl Image {
    pub fn open(path: &Path, options: &Value) -> Result<Self, String> {
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
        let mut image = Self {
            reader,
            buffer: FrameBuffer::default(),
            path,
            frame,
            frames,
            shape: [0, 0],
            values: vec![],
            source_dtype: String::new(),
        };
        image.read(frame)?;
        Ok(image)
    }
    pub fn read(&mut self, index: usize) -> Result<(), String> {
        // A failed read must leave the preceding published frame intact.
        let mut candidate = FrameBuffer::default();
        self.reader
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
        self.buffer = candidate;
        self.values = values;
        self.shape = shape;
        self.frame = index;
        Ok(())
    }
    pub fn original_pixels(&self) -> &PixelBuffer {
        self.buffer.pixels().expect("published frame has samples")
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
