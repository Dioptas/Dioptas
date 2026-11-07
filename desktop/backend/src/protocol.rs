use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::HashSet, sync::Arc};

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
    pub bytes: Arc<[u8]>,
}
impl Buffer {
    pub fn new(bytes: Vec<u8>) -> Self {
        Self {
            id: format!("{:x}", Sha256::digest(&bytes)),
            bytes: bytes.into(),
        }
    }
}

pub struct Reply {
    pub result: Value,
    pub buffers: Vec<Buffer>,
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
    pub fn encode(&self, id: u64, known: &[String]) -> Result<Vec<u8>, String> {
        #[derive(Serialize)]
        struct Entry<'a> {
            id: &'a str,
            length: usize,
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
        let header =
            serde_json::to_vec(&json!({"id": id, "result": self.result, "buffers": table}))
                .map_err(|e| e.to_string())?;
        let length = u32::try_from(header.len()).map_err(|_| "Oversized response header")?;
        let mut result = length.to_le_bytes().to_vec();
        result.extend_from_slice(&header);
        for buffer in buffers {
            result.extend_from_slice(&buffer.bytes);
        }
        Ok(result)
    }
}
