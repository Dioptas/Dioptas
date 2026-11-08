//! Opt-in stage timings for native profiling, written only to stderr.
pub(crate) struct FrameTrace {
    enabled: bool,
    label: &'static str,
    id: u64,
    stamp: std::time::Instant,
    steps: Vec<(&'static str, f64)>,
}
impl FrameTrace {
    pub fn new(label: &'static str, id: u64) -> Self {
        Self {
            enabled: std::env::var_os("DIOPTAS_TRACE_FRAME").is_some(),
            label,
            id,
            stamp: std::time::Instant::now(),
            steps: vec![],
        }
    }
    pub fn mark(&mut self, name: &'static str) {
        if self.enabled {
            let now = std::time::Instant::now();
            self.steps
                .push((name, now.duration_since(self.stamp).as_secs_f64() * 1000.));
            self.stamp = now;
        }
    }
}
impl Drop for FrameTrace {
    fn drop(&mut self) {
        if self.enabled {
            use std::io::Write;
            let line = format!(
                "DIOPTAS_TRACE {}\n",
                serde_json::json!({"stage":self.label,"id":self.id,"steps":self.steps})
            );
            let _ = std::io::stderr().lock().write_all(line.as_bytes());
        }
    }
}
