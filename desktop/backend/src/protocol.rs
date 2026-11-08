use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::HashSet,
    sync::{Arc, OnceLock},
};

pub const MAX_REQUEST_BYTES: usize = 16 * 1024 * 1024;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub id: u64,
    pub action: String,
    #[serde(default = "empty_object")]
    pub payload: Value,
    #[serde(default, rename = "cachedBuffers")]
    pub cached_buffers: Vec<String>,
}

#[cfg(test)]
mod packet_write_tests {
    use super::*;
    use std::io::{self, IoSlice, Write};
    struct ShortWriter {
        bytes: Vec<u8>,
        calls: usize,
    }
    impl Write for ShortWriter {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            self.write_vectored(&[IoSlice::new(bytes)])
        }
        fn write_vectored(&mut self, parts: &[IoSlice<'_>]) -> io::Result<usize> {
            self.calls += 1;
            if self.calls.is_multiple_of(5) {
                return Err(io::ErrorKind::Interrupted.into());
            }
            let mut remaining = 7;
            let mut written = 0;
            for part in parts {
                let take = remaining.min(part.len());
                self.bytes.extend_from_slice(&part[..take]);
                remaining -= take;
                written += take;
                if remaining == 0 {
                    break;
                }
            }
            Ok(written)
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    #[test]
    fn streamed_packets_preserve_framing_bytes_duplicates_and_cache_omission() {
        let first = Buffer::new(vec![0, 10, 13, 255, 0, 1, 2]);
        let second = Buffer::new((0..255).collect());
        let empty = Buffer::new(vec![]);
        let reply = Reply {
            result: json!({"ok":true,"name":"α detector"}),
            buffers: vec![first.clone(), second.clone(), first.clone(), empty],
        };
        for known in [
            vec![],
            vec![first.id.clone()],
            vec![first.id.clone(), second.id.clone()],
        ] {
            let mut out = ShortWriter {
                bytes: vec![],
                calls: 0,
            };
            reply
                .packet_parts(42, &known)
                .unwrap()
                .write_to(&mut out)
                .unwrap();
            let size = u32::from_le_bytes(out.bytes[..4].try_into().unwrap()) as usize;
            let header: Value = serde_json::from_slice(&out.bytes[4..4 + size]).unwrap();
            let reference_header = serde_json::to_vec(&json!({
                "id":42,"result":reply.result,"buffers":header["buffers"]
            }))
            .unwrap();
            assert_eq!(&out.bytes[4..4 + size], reference_header);
            assert_eq!(header["id"], 42);
            assert_eq!(header["result"], reply.result);
            let mut expected = vec![];
            for entry in header["buffers"].as_array().unwrap() {
                let b = reply
                    .buffers
                    .iter()
                    .find(|b| b.id == entry["id"].as_str().unwrap())
                    .unwrap();
                assert!(!known.contains(&b.id));
                expected.extend_from_slice(&b.bytes);
            }
            assert_eq!(&out.bytes[4 + size..], expected);
            assert_eq!(out.bytes, reply.encode(42, &known).unwrap());
        }
    }
}
fn empty_object() -> Value {
    json!({})
}

impl Request {
    pub fn validate(&self) -> Result<(), String> {
        if !self.payload.is_object() {
            return Err("Command arguments must be an object.".into());
        }
        if self.cached_buffers.len() > 64 || self.cached_buffers.iter().any(|s| s.len() > 128) {
            return Err("Invalid cached buffer list.".into());
        }
        Ok(())
    }
}

#[derive(Clone)]
pub struct Buffer {
    pub id: String,
    pub bytes: Arc<Vec<u8>>,
}
impl Buffer {
    pub fn new(bytes: Vec<u8>) -> Self {
        Self::shared(Arc::new(bytes))
    }
    pub fn shared(bytes: Arc<Vec<u8>>) -> Self {
        // These opaque IDs identify live display bytes, independently of the
        // SHA256 identities stored in .dio project files.
        let mut hash = blake3::Hasher::new();
        if bytes.len() >= 1_000_000 {
            static POOL: OnceLock<Option<rayon::ThreadPool>> = OnceLock::new();
            let pool = POOL.get_or_init(|| {
                rayon::ThreadPoolBuilder::new()
                    .num_threads(
                        std::thread::available_parallelism()
                            .map_or(1, |n| n.get())
                            .min(8),
                    )
                    .thread_name(|i| format!("display-hash-{i}"))
                    .build()
                    .ok()
            });
            if let Some(pool) = pool {
                pool.install(|| {
                    hash.update_rayon(bytes.as_slice());
                });
            } else {
                hash.update(bytes.as_slice());
            }
        } else {
            hash.update(bytes.as_slice());
        }
        Self {
            id: format!("b3:{}", hash.finalize().to_hex()),
            bytes,
        }
    }
}

pub struct Reply {
    pub result: Value,
    pub buffers: Vec<Buffer>,
}
pub(crate) struct PacketParts<'a> {
    pub header: Vec<u8>,
    pub buffers: Vec<&'a Buffer>,
}
impl PacketParts<'_> {
    pub fn write_to(&self, output: &mut impl std::io::Write) -> std::io::Result<()> {
        use std::io::{Error, ErrorKind, IoSlice};
        let mut slices: Vec<_> = std::iter::once(IoSlice::new(&self.header))
            .chain(
                self.buffers
                    .iter()
                    .filter(|b| !b.bytes.is_empty())
                    .map(|b| IoSlice::new(&b.bytes)),
            )
            .collect();
        let mut remaining = slices.as_mut_slice();
        while !remaining.is_empty() {
            match output.write_vectored(remaining) {
                Ok(0) => {
                    return Err(Error::new(
                        ErrorKind::WriteZero,
                        "Could not write processing packet",
                    ));
                }
                Ok(n) => IoSlice::advance_slices(&mut remaining, n),
                Err(e) if e.kind() == ErrorKind::Interrupted => continue,
                Err(e) => return Err(e),
            }
        }
        Ok(())
    }
}
impl Reply {
    pub fn metadata(result: Value) -> Self {
        Self {
            result,
            buffers: vec![],
        }
    }
    pub fn error(error: impl ToString) -> Self {
        Self::metadata(json!({"ok": false, "error": error.to_string()}))
    }
    /// The Python processor and Tauri IPC use this same wire format. Buffer IDs
    /// hash immutable display bytes; scientific sample storage is separate.
    pub(crate) fn packet_parts(
        &self,
        id: u64,
        known: &[String],
    ) -> Result<PacketParts<'_>, String> {
        #[derive(Serialize)]
        struct Entry<'a> {
            id: &'a str,
            length: usize,
        }
        #[derive(Serialize)]
        struct Header<'a> {
            id: u64,
            result: &'a Value,
            buffers: &'a [Entry<'a>],
        }
        let mut seen: HashSet<&str> = known.iter().map(String::as_str).collect();
        let buffers: Vec<_> = self.buffers.iter().filter(|b| seen.insert(&b.id)).collect();
        let table: Vec<_> = buffers
            .iter()
            .map(|b| Entry {
                id: &b.id,
                length: b.bytes.len(),
            })
            .collect();
        // Borrow the result: json! would recursively clone/serialize the complete
        // calibration contour and workflow tree before encoding it a second time.
        let header = serde_json::to_vec(&Header {
            id,
            result: &self.result,
            buffers: &table,
        })
        .map_err(|e| e.to_string())?;
        let length = u32::try_from(header.len()).map_err(|_| "Oversized response header")?;
        let mut result = length.to_le_bytes().to_vec();
        result.extend_from_slice(&header);
        Ok(PacketParts {
            header: result,
            buffers,
        })
    }
    pub fn encode(&self, id: u64, known: &[String]) -> Result<Vec<u8>, String> {
        let parts = self.packet_parts(id, known)?;
        let mut result = Vec::with_capacity(
            parts.header.len() + parts.buffers.iter().map(|b| b.bytes.len()).sum::<usize>(),
        );
        parts.write_to(&mut result).map_err(|e| e.to_string())?;
        Ok(result)
    }
}
