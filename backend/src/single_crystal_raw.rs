//! Parallel frame decoding for HDF5 Bitshuffle/LZ4 scans.
//!
//! The HDF5 library serialises every call behind one global lock, so decoding
//! a scan through `Image::open` does not scale with threads (about 12 ms per
//! Eiger frame, half of it repeated discovery). Datasets with one full-frame
//! chunk per frame are indexed once with dioptrin-io's `RawReader`; frames are
//! then read with positional I/O and decompressed outside the HDF5 lock. The
//! counts are the same as `Image::open` gives (same rows-up orientation);
//! every other source keeps the general reader.
use super::*;
use dioptrin_io::hdf5::{
    Limits,
    raw::{FrameBuffer, RawReader},
};
use std::{
    collections::HashMap,
    sync::{Mutex, OnceLock},
};

/// Raw-chunk readers by source file; `None` marks a file that needs the
/// general reader. Shared by clones of the session state.
#[derive(Clone, Default)]
pub(super) struct RawFrames(Arc<Mutex<HashMap<PathBuf, Option<Arc<Raw>>>>>);

/// One indexed source file and the frames whose counts were checked through it.
pub(super) struct Raw {
    reader: RawReader,
    /// Per frame of the file: the digest of its decoded counts once a read
    /// through this reader matched the digest its source records. The reader
    /// is a frozen snapshot that rejects every read after the file changed
    /// (size, modification and status-change times, device, inode or path
    /// binding), so later reads through it give the same counts and need not
    /// hash them again (see `Crystal::read`).
    verified: Vec<OnceLock<String>>,
}
impl std::ops::Deref for Raw {
    type Target = RawReader;
    fn deref(&self) -> &RawReader {
        &self.reader
    }
}
impl Raw {
    pub(super) fn verified(&self, frame: usize) -> Option<&OnceLock<String>> {
        self.verified.get(frame)
    }
}

impl RawFrames {
    fn reader(&self, path: &Path, frames: usize, shape: [usize; 2]) -> Option<Arc<Raw>> {
        if let Some(found) = self.0.lock().unwrap().get(path) {
            return found.clone();
        }
        // Indexing is cheap HDF5 metadata work; a concurrent duplicate is harmless.
        let reader = open(path, frames, shape).map(Arc::new);
        self.0
            .lock()
            .unwrap()
            .entry(path.to_path_buf())
            .or_insert(reader)
            .clone()
    }
    fn forget(&self, path: &Path) {
        self.0.lock().unwrap().insert(path.to_path_buf(), None);
    }
}

fn open(path: &Path, frames: usize, shape: [usize; 2]) -> Option<Raw> {
    let image = Image::prepare(path, &json!({})).ok()?;
    if image.frames != frames || image.shape != shape || !image.single_dataset_series() {
        return None;
    }
    let source = image.combined_source(0).ok()??;
    let reader = RawReader::open_snapshot(&source.path, &source.dataset, Limits::default()).ok()?;
    (reader.shape() == [frames, shape[0], shape[1]]).then(|| Raw {
        reader,
        verified: (0..frames).map(|_| OnceLock::new()).collect(),
    })
}

thread_local! {
    static BUFFER: std::cell::Cell<FrameBuffer> = std::cell::Cell::new(FrameBuffer::default());
}

/// Block medians straight from stored integer rows (stored bottom row first,
/// as `oriented_values` flips them); same values and rules as
/// `dac_fit::block_medians` on the decoded frame and its base mask.
fn medians<T: Copy + Into<u64>>(
    data: &[T],
    [h, w]: [usize; 2],
    block: usize,
    saturation: f64,
    rects: &[[usize; 4]],
) -> Vec<f64> {
    let (rows, columns) = (h.div_ceil(block), w.div_ceil(block));
    let masked = |x: usize, y: usize| {
        rects
            .iter()
            .any(|&[x0, y0, x1, y1]| x >= x0 && x < x1 && y >= y0 && y < y1)
    };
    let mut out = vec![f64::NAN; rows * columns];
    // Counts below LOW are tallied; larger ones (spots, rare) are kept and
    // selected only when the median falls among them. Same element as
    // selecting the median of all values.
    const LOW: usize = 256;
    let mut tally = [0u16; LOW];
    let mut high: Vec<u64> = Vec::with_capacity(block * block);
    for by in 0..rows {
        let ys = by * block..((by + 1) * block).min(h);
        for bx in 0..columns {
            let xs = bx * block..((bx + 1) * block).min(w);
            tally.fill(0);
            high.clear();
            let mut used = 0usize;
            for y in ys.clone() {
                let row = (h - 1 - y) * w;
                for (x, &v) in xs.clone().zip(&data[row + xs.start..row + xs.end]) {
                    let v: u64 = v.into();
                    if (v as f64) < saturation && (rects.is_empty() || !masked(x, y)) {
                        used += 1;
                        if (v as usize) < LOW {
                            tally[v as usize] += 1;
                        } else {
                            high.push(v);
                        }
                    }
                }
            }
            if 2 * used >= ys.len() * xs.len() && used > 0 {
                let m = used / 2;
                let low = used - high.len();
                out[by * columns + bx] = if m < low {
                    let mut seen = 0usize;
                    let mut found = 0;
                    for (v, &n) in tally.iter().enumerate() {
                        seen += usize::from(n);
                        if seen > m {
                            found = v;
                            break;
                        }
                    }
                    found as f64
                } else {
                    *high.select_nth_unstable(m - low).1 as f64
                };
            }
        }
    }
    out
}

/// Stored integer rows (bottom row first) seen as the decoded frame and its
/// base mask: same values, same usable pixels.
struct Stored<'a, T> {
    data: &'a [T],
    shape: [usize; 2],
    saturation: f64,
    rects: &'a [[usize; 4]],
}
impl<T: Copy + Into<u64> + Sync> diamond::FramePixels for Stored<'_, T> {
    fn value(&self, i: usize) -> f64 {
        let [h, w] = self.shape;
        let v: u64 = self.data[(h - 1 - i / w) * w + i % w].into();
        v as f64
    }
    fn usable(&self, i: usize) -> bool {
        let w = self.shape[1];
        let (x, y) = (i % w, i / w);
        self.value(i) < self.saturation
            && !self
                .rects
                .iter()
                .any(|&[x0, y0, x1, y1]| x >= x0 && x < x1 && y >= y0 && y < y1)
    }
    // Row-wise copy (same values and usability as the per-pixel accessors).
    fn row(&self, y: usize, width: usize, out: &mut [f64]) {
        let h = self.shape[0];
        let stored = &self.data[(h - 1 - y) * width..(h - y) * width];
        for (x, (o, &v)) in out.iter_mut().zip(stored).enumerate() {
            let v: u64 = v.into();
            let v = v as f64;
            let masked = !self.rects.is_empty()
                && self
                    .rects
                    .iter()
                    .any(|&[x0, y0, x1, y1]| x >= x0 && x < x1 && y >= y0 && y < y1);
            *o = if v < self.saturation && !masked {
                v
            } else {
                f64::NAN
            };
        }
    }
}

impl Crystal {
    /// Diamond-spot scan of one frame (settings independent: every bin above
    /// the lowest level), from the raw chunk when possible. Not a processing
    /// read: no count digest.
    pub(super) fn diamond_scan(&self, index: usize) -> Result<diamond::Scan, String> {
        use dioptrin_io::PixelBuffer;
        if self.excluded_frames.contains(&index) {
            return Ok(diamond::Scan::default());
        }
        let s = self
            .sources
            .get(index)
            .ok_or("Frame is outside the loaded series.")?;
        let frames = self.sources.iter().filter(|o| o.path == s.path).count();
        if let Some(reader) = self.raw_frames.reader(&s.path, frames, self.shape) {
            let mut buffer = BUFFER.take();
            let (shape, saturation, rects) = (self.shape, self.config.saturation, &self.mask[..]);
            let found =
                reader
                    .read_frame_into(s.frame, &mut buffer)
                    .ok()
                    .and_then(|()| match buffer.pixels()? {
                        PixelBuffer::U16(data) => Some(diamond::scan(
                            &Stored {
                                data,
                                shape,
                                saturation,
                                rects,
                            },
                            shape,
                        )),
                        PixelBuffer::U32(data) => Some(diamond::scan(
                            &Stored {
                                data,
                                shape,
                                saturation,
                                rects,
                            },
                            shape,
                        )),
                        _ => None,
                    });
            BUFFER.set(buffer);
            match found {
                Some(found) => return Ok(found),
                None => self.raw_frames.forget(&s.path),
            }
        }
        let values = self.decode(index)?;
        let excluded = self.base_mask(&values, index);
        Ok(diamond::scan(
            &diamond::Decoded {
                values: &values,
                excluded: &excluded,
            },
            self.shape,
        ))
    }
    /// Persistent-pixel hits of one frame (see `persistent::frame_hits`),
    /// straight from the stored rows when possible. Not a processing read.
    pub(super) fn persistent_hits(&self, index: usize) -> Result<Vec<u32>, String> {
        use dioptrin_io::PixelBuffer;
        fn stored<T: Copy + Into<u64> + Into<f64>>(
            data: &[T],
            shape: [usize; 2],
            saturation: f64,
            rects: &[[usize; 4]],
        ) -> Vec<u32> {
            let m = medians(data, shape, persistent::BLOCK, saturation, rects);
            persistent::frame_hits(
                &persistent::Frame {
                    data,
                    shape,
                    flipped: true,
                    saturation,
                    rects,
                },
                &m,
            )
        }
        if self.excluded_frames.contains(&index) {
            return Ok(vec![]);
        }
        let s = self
            .sources
            .get(index)
            .ok_or("Frame is outside the loaded series.")?;
        let frames = self.sources.iter().filter(|o| o.path == s.path).count();
        if let Some(reader) = self.raw_frames.reader(&s.path, frames, self.shape) {
            let mut buffer = BUFFER.take();
            let (shape, saturation, rects) = (self.shape, self.config.saturation, &self.mask[..]);
            let found =
                reader
                    .read_frame_into(s.frame, &mut buffer)
                    .ok()
                    .and_then(|()| match buffer.pixels()? {
                        PixelBuffer::U16(data) => Some(stored(data, shape, saturation, rects)),
                        PixelBuffer::U32(data) => Some(stored(data, shape, saturation, rects)),
                        _ => None,
                    });
            BUFFER.set(buffer);
            match found {
                Some(found) => return Ok(found),
                None => self.raw_frames.forget(&s.path),
            }
        }
        let values = self.decode(index)?;
        let unusable = self.base_mask(&values, index);
        let m = dac_fit::block_medians(&values, &unusable, self.shape, persistent::BLOCK);
        let values: Vec<f64> = values
            .iter()
            .zip(&unusable)
            .map(|(&v, &u)| if u { f64::NAN } else { v })
            .collect();
        Ok(persistent::frame_hits(
            &persistent::Frame {
                data: &values,
                shape: self.shape,
                flipped: false,
                saturation: f64::INFINITY,
                rects: &[],
            },
            &m,
        ))
    }
    /// Block medians of one frame for the shadow measurements, read from the
    /// raw chunk when possible (no full-frame f64 copy). Same values as the
    /// decoded frame with its base mask. Not a processing read: no count
    /// digest, the measurements are coarse and Find spots checks the counts.
    pub(super) fn frame_medians(&self, index: usize, block: usize) -> Result<Vec<f64>, String> {
        let [h, w] = self.shape;
        if self.excluded_frames.contains(&index) {
            return Ok(vec![f64::NAN; h.div_ceil(block) * w.div_ceil(block)]);
        }
        if let Some(found) = self.raw_medians(index, block) {
            return Ok(found);
        }
        let raw = self.decode(index)?;
        let unusable = self.base_mask(&raw, index);
        Ok(dac_fit::block_medians(&raw, &unusable, self.shape, block))
    }
    fn raw_medians(&self, index: usize, block: usize) -> Option<Vec<f64>> {
        use dioptrin_io::PixelBuffer;
        let s = self.sources.get(index)?;
        let frames = self.sources.iter().filter(|o| o.path == s.path).count();
        let reader = self.raw_frames.reader(&s.path, frames, self.shape)?;
        let mut buffer = BUFFER.take();
        let found = reader
            .read_frame_into(s.frame, &mut buffer)
            .ok()
            .and_then(|()| {
                let (shape, sat, rects) = (self.shape, self.config.saturation, &self.mask[..]);
                match buffer.pixels()? {
                    PixelBuffer::U16(v) => Some(medians(v, shape, block, sat, rects)),
                    PixelBuffer::U32(v) => Some(medians(v, shape, block, sat, rects)),
                    _ => None,
                }
            });
        BUFFER.set(buffer);
        if found.is_none() {
            self.raw_frames.forget(&s.path);
        }
        found
    }
    /// Counts of one frame through the raw-chunk reader, or None when the
    /// source needs the general reader.
    pub(super) fn decode_raw(&self, index: usize) -> Option<Vec<f64>> {
        self.decode_raw_snapshot(index).map(|(values, _)| values)
    }
    /// `decode_raw` with the reader the counts came from.
    pub(super) fn decode_raw_snapshot(&self, index: usize) -> Option<(Vec<f64>, Arc<Raw>)> {
        let s = self.sources.get(index)?;
        let frames = self.sources.iter().filter(|o| o.path == s.path).count();
        let reader = self.raw_frames.reader(&s.path, frames, self.shape)?;
        // Taken out of the slot: the orientation step runs parallel work, and
        // work stealing may decode another frame on this thread meanwhile.
        let mut buffer = BUFFER.take();
        let values = reader
            .read_frame_into(s.frame, &mut buffer)
            .ok()
            .and_then(|()| crate::image::oriented_values(buffer.pixels()?, self.shape).ok());
        BUFFER.set(buffer);
        if values.is_none() {
            // A changed or unreadable file: the general reader reports it.
            self.raw_frames.forget(&s.path);
        }
        Some((values?, reader))
    }
}
