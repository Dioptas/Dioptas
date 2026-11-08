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
