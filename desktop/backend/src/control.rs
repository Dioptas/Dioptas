//! Detached progress and cancellation; never shares scientific objects.
use serde_json::{Value, json};
use std::sync::{
    Mutex,
    atomic::{AtomicBool, Ordering},
};

#[derive(Default)]
pub struct Control {
    cancelled: AtomicBool,
    progress: Mutex<Value>,
}
impl Control {
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
    }
    pub fn check(&self) -> Result<(), String> {
        if self.cancelled.load(Ordering::Acquire) {
            Err("Calibration cancelled; previous geometry and picked peaks restored.".into())
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
    pub fn finish(&self) {
        self.publish(json!({"running":false,"current":0,"total":0}));
    }
}
