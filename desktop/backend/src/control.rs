//! Detached progress and cancellation; never shares scientific objects.
use crate::protocol::{Buffer, Reply};
use serde_json::{Value, json};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};

#[derive(Default)]
pub struct Control {
    cancelled: Arc<AtomicBool>,
    silent: bool,
    skip_cake: AtomicBool,
    skip_calibration_rings: AtomicBool,
    progress: Mutex<Value>,
    map_preview: Mutex<Option<(Value, Buffer)>>,
}
impl Control {
    /// Frame workers share cancellation but leave operation progress to the
    /// ordered collector; plugin-local progress must not replace series totals.
    pub(crate) fn silent_child(&self) -> Self {
        Self {
            cancelled: self.cancelled.clone(),
            silent: true,
            ..Self::default()
        }
    }
    /// Per-command display demand, shared by all configuration owners. Legacy
    /// callers that do not specify products retain the complete response.
    pub(crate) fn request_cake(&self, requested: bool) {
        self.skip_cake.store(!requested, Ordering::Release);
    }
    pub(crate) fn cake_requested(&self) -> bool {
        !self.skip_cake.load(Ordering::Acquire)
    }
    pub(crate) fn request_calibration_rings(&self, requested: bool) {
        self.skip_calibration_rings
            .store(!requested, Ordering::Release);
    }
    pub(crate) fn calibration_rings_requested(&self) -> bool {
        !self.skip_calibration_rings.load(Ordering::Acquire)
    }
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
        if !self.silent {
            *self.progress.lock().unwrap() = progress;
        }
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

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn child_shares_cancellation_and_preserves_owner_progress() {
        let parent = Control::default();
        parent.publish(json!({"current":12,"total":100,"label":"Integrating series"}));
        let child = parent.silent_child();
        child.publish(json!({"label":"Computing a plugin"}));
        assert_eq!(parent.progress()["current"], 12);
        parent.cancel();
        assert!(child.check().is_err());
    }
}
