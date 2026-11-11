use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::HashSet, sync::Arc};

#[path = "../../command_contract.rs"]
pub mod command_contract;
pub use command_contract::MAX_REQUEST_BYTES;
#[path = "../../wire_contract.rs"]
pub mod wire_contract;

#[derive(Debug, Deserialize, Serialize)]
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
            assert_eq!(&out.bytes[4..4 + reference_header.len()], reference_header);
            assert!(
                out.bytes[4 + reference_header.len()..4 + size]
                    .iter()
                    .all(|&v| v == b' ')
            );
            assert!(size - reference_header.len() < 4);
            assert_eq!((4 + size) % 4, 0);
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

    #[test]
    fn request_dtos_preserve_wire_numbers_names_and_legacy_dispatch() {
        let original = json!({"id":17,"action":"integration_navigation",
            "payload":{"frame":-1.25,"step":2.0,"requested_products":{"cake":false}},
            "cachedBuffers":["immutable-buffer"]});
        let request: Request = serde_json::from_value(original.clone()).unwrap();
        // Structural validation does not coerce or enforce scientific ranges;
        // the existing handler will reject this invalid fractional frame.
        request.validate().unwrap();
        assert_eq!(serde_json::to_value(&request).unwrap(), original);
        let bad: Request = serde_json::from_value(json!({"id":18,"action":"pixel",
            "payload":{"x":"12","y":3},"cachedBuffers":[]}))
        .unwrap();
        assert!(
            bad.validate()
                .unwrap_err()
                .contains("Invalid pixel arguments")
        );
        let legacy: Request =
            serde_json::from_value(json!({"id":19,"action":"unported_legacy_command",
            "payload":{"uninterpreted":[1,2,3]},"cachedBuffers":[]}))
            .unwrap();
        legacy.validate().unwrap();
        assert!(
            serde_json::from_value::<Request>(json!({"id":20,"action":"state","extra":true}))
                .is_err()
        );
    }

    #[test]
    fn typed_metadata_envelopes_keep_binary_response_framing_compatible() {
        let decision = json!({"path":"source.h5","shape":[2,3]});
        let reply = Reply::deferred(wire_contract::DecisionKind::ImageChange, decision.clone());
        assert_eq!(
            reply.result,
            json!({"ok":true,"cancelled":true,"imageChange":decision})
        );
        let binary = reply.encode(31, &[]).unwrap();
        let length = u32::from_le_bytes(binary[..4].try_into().unwrap()) as usize;
        let header: Value = serde_json::from_slice(&binary[4..4 + length]).unwrap();
        assert_eq!(header["id"], 31);
        assert_eq!(header["result"], reply.result);
        assert_eq!(header["buffers"], json!([]));
        assert_eq!(binary.len(), 4 + length);
        assert_eq!(
            wire_contract::response_metadata(&header["result"])
                .unwrap()
                .disposition,
            wire_contract::ResponseDisposition::Deferred
        );
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
        wire_contract::validate_payload(&self.action, &self.payload)?;
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
            crate::worker_pool::install(|| {
                hash.update_rayon(bytes.as_slice());
            });
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
        Self::metadata(wire_contract::failure_metadata(error))
    }
    pub fn success() -> Self {
        Self::metadata(wire_contract::success_metadata())
    }
    pub fn deferred(kind: wire_contract::DecisionKind, decision: Value) -> Self {
        Self::metadata(wire_contract::deferred_metadata(kind, decision))
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
        let mut header = serde_json::to_vec(&Header {
            id,
            result: &self.result,
            buffers: &table,
        })
        .map_err(|e| e.to_string())?;
        // Valid JSON whitespace aligns the first float32 payload without a
        // wire-format change. Existing clients still read exactly these bytes.
        header.resize(header.len().next_multiple_of(4), b' ');
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
