//! Detached progress and cancellation; never shares scientific objects.
use crate::protocol::{Buffer, Reply};
use serde_json::{Value, json};
use std::sync::{
    Mutex,
    atomic::{AtomicBool, Ordering},
};

#[derive(Default)]
pub struct Control {
    cancelled: AtomicBool,
    progress: Mutex<Value>,
    map_preview: Mutex<Option<(Value, Buffer)>>,
}
impl Control {
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
    }
    pub fn check(&self) -> Result<(), String> {
        if self.cancelled.load(Ordering::Acquire) {
            Err("Operation cancelled; previous state restored.".into())
        } else {
            Ok(())
        }
    }
    pub fn publish(&self, progress: Value) {
        *self.progress.lock().unwrap() = progress;
    }
    pub fn progress(&self) -> Value {
        self.progress.lock().unwrap().clone()
    }
    pub fn publish_map_preview(&self, metadata: Value, buffer: Buffer) {
        *self.map_preview.lock().unwrap() = Some((metadata, buffer));
    }
    pub fn progress_reply(&self) -> Reply {
        let mut progress = self.progress();
        let mut buffers = vec![];
        if let Some((metadata, buffer)) = self.map_preview.lock().unwrap().as_ref() {
            progress["mapPreview"] = metadata.clone();
            buffers.push(buffer.clone());
        }
        Reply {
            result: json!({"ok":true,"progress":progress}),
            buffers,
        }
    }
    pub fn finish(&self) {
        *self.map_preview.lock().unwrap() = None;
        self.publish(json!({"running":false,"current":0,"total":0}));
    }
}
