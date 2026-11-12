//! Optional lossless stage outputs for independent standalone comparisons.
use super::*;
use phasesmith_persistence::numeric_archive::{NumericArray, write_numeric_npz};
struct Array {
    name: String,
    dtype: &'static str,
    shape: Vec<usize>,
    bytes: Vec<u8>,
}
pub(super) struct Audit {
    arrays: Vec<Array>,
    directory: Arc<tempfile::TempDir>,
}
impl Audit {
    pub fn new() -> Result<Self, String> {
        Ok(Self {
            arrays: vec![],
            directory: Arc::new(tempfile::tempdir().map_err(err)?),
        })
    }
    pub fn f(&mut self, name: &str, shape: &[usize], values: impl IntoIterator<Item = f64>) {
        self.arrays.push(Array {
            name: name.into(),
            dtype: "<f8",
            shape: shape.into(),
            bytes: values.into_iter().flat_map(f64::to_le_bytes).collect(),
        });
    }
    pub fn i(&mut self, name: &str, shape: &[usize], values: impl IntoIterator<Item = i64>) {
        self.arrays.push(Array {
            name: name.into(),
            dtype: "<i8",
            shape: shape.into(),
            bytes: values.into_iter().flat_map(i64::to_le_bytes).collect(),
        });
    }
    pub fn b(&mut self, name: &str, shape: &[usize], values: &[bool]) {
        self.arrays.push(Array {
            name: name.into(),
            dtype: "|b1",
            shape: shape.into(),
            bytes: values.iter().map(|&v| u8::from(v)).collect(),
        });
    }
    pub fn u(&mut self, name: &str, values: &[u32]) {
        self.arrays.push(Array {
            name: name.into(),
            dtype: "<u4",
            shape: vec![values.len()],
            bytes: values.iter().flat_map(|v| v.to_le_bytes()).collect(),
        });
    }
    pub fn finish(self) -> Result<Arc<tempfile::TempDir>, String> {
        let arrays: Vec<_> = self
            .arrays
            .iter()
            .map(|a| NumericArray {
                name: &a.name,
                dtype: a.dtype,
                shape: &a.shape,
                bytes: &a.bytes,
            })
            .collect();
        write_numeric_npz(&self.directory.path().join("stages.npz"), &arrays, 1).map_err(err)?;
        Ok(self.directory)
    }
}
