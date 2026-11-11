//! Bounded, disposable maps shared by frame processing, snapshots and Plot.
use crate::{control::Control, display::Raster, geometry::Geometry, transform::Transform};
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    sync::{Arc, Condvar, Mutex, OnceLock},
    time::Duration,
};

#[derive(Clone)]
pub(crate) enum Key {
    Analytical(Value, Box<Geometry>, [usize; 2]),
    References(
        Arc<Vec<f64>>,
        Option<Arc<Vec<f64>>>,
        [usize; 2],
        Vec<Transform>,
    ),
}
impl PartialEq for Key {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Analytical(p, g, s), Self::Analytical(q, h, t)) => p == q && g == h && s == t,
            (Self::References(a, b, s, x), Self::References(c, d, t, y)) => {
                Arc::ptr_eq(a, c)
                    && match (b, d) {
                        (None, None) => true,
                        (Some(b), Some(d)) => Arc::ptr_eq(b, d),
                        _ => false,
                    }
                    && s == t
                    && x == y
            }
            _ => false,
        }
    }
}
struct Entry {
    kind: String,
    key: Key,
    values: Arc<Vec<f64>>,
}
type AngularArrays = (Arc<Vec<f64>>, Arc<Vec<f64>>);
struct Angles {
    geometry: Geometry,
    shape: [usize; 2],
    tth: Arc<Vec<f64>>,
    azi: Arc<Vec<f64>>,
}
struct Preview {
    kind: String,
    key: Option<Key>,
    values: Arc<Vec<f64>>,
    shape: [usize; 2],
    mode: String,
    percentile: f64,
    raster: Raster,
}
#[derive(Clone)]
struct Job {
    kind: String,
    key: Key,
    values: Arc<Vec<f64>>,
    shape: [usize; 2],
    ticket: u64,
}
#[derive(Default)]
struct State {
    entries: Vec<Entry>,
    angles: Option<Angles>,
    previews: Vec<Preview>,
    queued: Vec<Job>,
    running: Option<Job>,
    latest: HashMap<String, u64>,
    failures: HashMap<String, String>,
    next_ticket: u64,
    worker_scheduled: bool,
    #[cfg(test)]
    defer_workers: bool,
    sample_builds: usize,
    sample_hits: usize,
}
#[derive(Default)]
struct Inner {
    state: Mutex<State>,
    changed: Condvar,
}
#[derive(Clone, Default)]
pub(crate) struct Maps(Arc<Inner>);
fn background_pool() -> Option<&'static rayon::ThreadPool> {
    static POOL: OnceLock<Option<rayon::ThreadPool>> = OnceLock::new();
    POOL.get_or_init(|| {
        rayon::ThreadPoolBuilder::new()
            .num_threads(1)
            .thread_name(|_| "dioptas-preview".into())
            .start_handler(|_| {
                #[cfg(target_os = "macos")]
                // SAFETY: this adjusts only the calling preview thread's QoS.
                unsafe {
                    let _ = libc::pthread_set_qos_class_self_np(
                        libc::qos_class_t::QOS_CLASS_UTILITY,
                        0,
                    );
                }
            })
            .build()
            .ok()
    })
    .as_ref()
}

impl Maps {
    pub fn bytes(&self) -> usize {
        let s = self.0.state.lock().unwrap();
        let mut maps: Vec<&Arc<Vec<f64>>> = vec![];
        for values in s
            .entries
            .iter()
            .map(|e| &e.values)
            .chain(s.previews.iter().map(|p| &p.values))
            .chain(s.queued.iter().map(|j| &j.values))
            .chain(s.running.iter().map(|j| &j.values))
        {
            if !maps.iter().any(|other| Arc::ptr_eq(other, values)) {
                maps.push(values);
            }
        }
        maps.iter().map(|v| v.len() * 8).sum::<usize>()
            + s.angles
                .as_ref()
                .map_or(0, |a| (a.tth.len() + a.azi.len()) * 8)
            + s.previews
                .iter()
                .map(|p| p.raster.buffer.bytes.len())
                .sum::<usize>()
    }
    pub fn diagnostics(&self) -> Value {
        let s = self.0.state.lock().unwrap();
        json!({"sampleCorrectionBuilds":s.sample_builds,"sampleCorrectionHits":s.sample_hits})
    }
    pub fn clear(&self, kind: &str) {
        let mut s = self.0.state.lock().unwrap();
        s.entries.retain(|e| e.kind != kind);
        s.previews.retain(|p| p.kind != kind);
        s.queued.retain(|j| j.kind != kind);
        s.latest.remove(kind);
        s.failures.remove(kind);
        self.0.changed.notify_all();
    }
    pub fn get(
        &self,
        kind: &str,
        key: Key,
        control: &Control,
        build: impl FnOnce() -> Result<Arc<Vec<f64>>, String>,
    ) -> Result<Arc<Vec<f64>>, String> {
        control.check()?;
        {
            let mut s = self.0.state.lock().unwrap();
            if let Some(e) = s
                .entries
                .iter()
                .position(|e| e.kind == kind && e.key == key)
            {
                let e = s.entries.remove(e);
                let values = e.values.clone();
                let preview_kind = if kind == "transfer-preview" {
                    "transfer"
                } else {
                    kind
                };
                let restart = kind != "transfer"
                    && !s.latest.contains_key(preview_kind)
                    && !s
                        .previews
                        .iter()
                        .any(|p| p.kind == preview_kind && Arc::ptr_eq(&p.values, &values));
                let key = e.key.clone();
                let shape = match &key {
                    Key::Analytical(_, _, shape) => *shape,
                    Key::References(_, _, shape, transforms) => {
                        crate::transform::shape(*shape, transforms)
                    }
                };
                s.entries.push(e);
                if ["cylinder", "sphere"].contains(&kind) {
                    s.sample_hits += 1;
                }
                drop(s);
                if restart {
                    self.queue_preview(preview_kind, key, values.clone(), shape);
                }
                return Ok(values);
            }
        }
        let values = build()?;
        control.check()?;
        let shape = match &key {
            Key::Analytical(_, _, shape) => *shape,
            Key::References(_, _, shape, transforms) => crate::transform::shape(*shape, transforms),
        };
        let mut s = self.0.state.lock().unwrap();
        s.entries.retain(|e| e.kind != kind);
        // At most one entry per kind, plus a 256 MiB map budget. Snapshots
        // retain their own Arcs if processing needs more active maps at once.
        while !s.entries.is_empty()
            && s.entries.iter().map(|e| e.values.len() * 8).sum::<usize>() + values.len() * 8
                > 256 * 1024 * 1024
        {
            s.entries.remove(0);
        }
        s.entries.push(Entry {
            kind: kind.into(),
            key: key.clone(),
            values: values.clone(),
        });
        if ["cylinder", "sphere"].contains(&kind) {
            s.sample_builds += 1;
        }
        drop(s);
        // Transfer processing multiplies by a gain. Its reciprocal divisor is
        // prepared separately, so no preview can accidentally show that gain.
        if kind != "transfer" {
            self.queue_preview(
                if kind == "transfer-preview" {
                    "transfer"
                } else {
                    kind
                },
                key,
                values.clone(),
                shape,
            );
        }
        Ok(values)
    }
    #[cfg(feature = "dioptrin")]
    pub fn angles(
        &self,
        geometry: &Geometry,
        shape: [usize; 2],
        control: &Control,
    ) -> Result<AngularArrays, String> {
        control.check()?;
        if let Some(a) = self.0.state.lock().unwrap().angles.as_ref()
            && a.geometry == *geometry
            && a.shape == shape
        {
            return Ok((a.tth.clone(), a.azi.clone()));
        }
        let native = geometry.native_geometry(shape)?;
        let tth = Arc::new(native.calc_tth_all());
        control.check()?;
        let azi = Arc::new(native.calc_azimuth_all());
        control.check()?;
        self.0.state.lock().unwrap().angles = Some(Angles {
            geometry: geometry.clone(),
            shape,
            tth: tth.clone(),
            azi: azi.clone(),
        });
        Ok((tth, azi))
    }
    fn retain_preview(s: &mut State, preview: Preview) {
        s.previews.retain(|p| p.kind != preview.kind);
        let size = |p: &Preview| p.values.len() * 8 + p.raster.buffer.bytes.len();
        while !s.previews.is_empty()
            && s.previews.iter().map(size).sum::<usize>() + size(&preview) > 256 * 1024 * 1024
        {
            s.previews.remove(0);
        }
        s.previews.push(preview);
    }
    fn queue_preview(&self, kind: &str, key: Key, values: Arc<Vec<f64>>, shape: [usize; 2]) {
        let start = {
            let mut s = self.0.state.lock().unwrap();
            s.next_ticket += 1;
            let ticket = s.next_ticket;
            s.latest.insert(kind.into(), ticket);
            s.failures.remove(kind);
            s.queued.retain(|j| j.kind != kind);
            s.previews.retain(|p| p.kind != kind);
            while !s.queued.is_empty()
                && s.queued.iter().map(|j| j.values.len() * 8).sum::<usize>() + values.len() * 8
                    > 256 * 1024 * 1024
            {
                s.queued.remove(0);
            }
            s.queued.push(Job {
                kind: kind.into(),
                key,
                values,
                shape,
                ticket,
            });
            let start = !s.worker_scheduled;
            #[cfg(test)]
            let start = start && !s.defer_workers;
            if start {
                s.worker_scheduled = true;
            }
            self.0.changed.notify_all();
            start
        };
        if start {
            if let Some(pool) = background_pool() {
                let weak = Arc::downgrade(&self.0);
                pool.spawn(move || {
                    while let Some(inner) = weak.upgrade() {
                        let job = {
                            let mut s = inner.state.lock().unwrap();
                            if s.queued.is_empty() {
                                s.worker_scheduled = false;
                                inner.changed.notify_all();
                                break;
                            }
                            let job = s.queued.remove(0);
                            s.running = Some(job.clone());
                            job
                        };
                        Self::run_job(&inner, job);
                    }
                });
            } else {
                // Plot retains its ordinary native on-demand path if a display
                // worker cannot be started. Scientific Apply does not depend on it.
                let mut s = self.0.state.lock().unwrap();
                s.worker_scheduled = false;
                s.queued.clear();
                self.0.changed.notify_all();
            }
        }
    }
    fn run_job(inner: &Inner, job: Job) {
        let current = inner.state.lock().unwrap().latest.get(&job.kind) == Some(&job.ticket);
        let result = if current {
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                if job.values.iter().any(|v| !v.is_finite() || *v <= 0.) {
                    return Err(
                        "Correction preview is not finite and positive across this detector."
                            .to_string(),
                    );
                }
                Ok(Raster::correction(
                    &job.values,
                    job.shape,
                    "percentile",
                    2.5,
                ))
            }))
            .unwrap_or_else(|_| Err("Correction preview preparation failed.".into()))
        } else {
            Err("Superseded correction preview.".into())
        };
        let mut s = inner.state.lock().unwrap();
        if s.latest.get(&job.kind) == Some(&job.ticket) {
            match result {
                Ok(raster) => Self::retain_preview(
                    &mut s,
                    Preview {
                        kind: job.kind.clone(),
                        key: Some(job.key),
                        values: job.values,
                        shape: job.shape,
                        mode: "percentile".into(),
                        percentile: 2.5,
                        raster,
                    },
                ),
                Err(error) => {
                    s.failures.insert(job.kind.clone(), error);
                }
            }
        }
        if s.running.as_ref().is_some_and(|j| j.ticket == job.ticket) {
            s.running = None;
        }
        inner.changed.notify_all();
    }
    pub fn cancel_preparation(&self) {
        let mut s = self.0.state.lock().unwrap();
        s.queued.clear();
        s.latest.clear();
        s.failures.clear();
        self.0.changed.notify_all();
    }
    pub fn prepared(&self, specs: &[(String, Key)]) -> (Vec<Raster>, bool) {
        let s = self.0.state.lock().unwrap();
        let rasters = specs
            .iter()
            .filter_map(|(kind, key)| {
                s.previews
                    .iter()
                    .find(|p| p.kind == *kind && p.key.as_ref() == Some(key))
                    .map(|p| p.raster.clone())
            })
            .collect();
        let matches = |j: &Job| {
            s.latest.get(&j.kind) == Some(&j.ticket)
                && specs
                    .iter()
                    .any(|(kind, key)| *kind == j.kind && *key == j.key)
        };
        let pending = s.queued.iter().any(matches) || s.running.as_ref().is_some_and(matches);
        (rasters, pending)
    }
    pub fn preview(
        &self,
        kind: &str,
        values: Arc<Vec<f64>>,
        shape: [usize; 2],
        mode: &str,
        percentile: f64,
        control: &Control,
    ) -> Result<Raster, String> {
        control.check()?;
        let key = {
            let mut s = self.0.state.lock().unwrap();
            loop {
                control.check()?;
                let same = |j: &Job| {
                    j.kind == kind
                        && Arc::ptr_eq(&j.values, &values)
                        && j.shape == shape
                        && s.latest.get(kind) == Some(&j.ticket)
                };
                if !s.queued.iter().any(same) && !s.running.as_ref().is_some_and(same) {
                    break;
                }
                // An early Plot promotes its queued map and waits without
                // holding the cache lock or blocking UI/progress/cancellation.
                if let Some(i) = s
                    .queued
                    .iter()
                    .position(|j| j.kind == kind && Arc::ptr_eq(&j.values, &values))
                {
                    let j = s.queued.remove(i);
                    s.queued.insert(0, j);
                }
                s = self
                    .0
                    .changed
                    .wait_timeout(s, Duration::from_millis(10))
                    .unwrap()
                    .0;
            }
            if let Some(error) = s.failures.get(kind) {
                return Err(error.clone());
            }
            let entry_kind = if kind == "transfer" {
                "transfer-preview"
            } else {
                kind
            };
            s.entries
                .iter()
                .find(|e| e.kind == entry_kind && Arc::ptr_eq(&e.values, &values))
                .map(|e| e.key.clone())
        };

        let cached =
            {
                let mut s = self.0.state.lock().unwrap();
                if let Some(i) = s.previews.iter().position(|p| {
                    p.kind == kind && Arc::ptr_eq(&p.values, &values) && p.shape == shape
                }) {
                    let p = s.previews.remove(i);
                    let ready = p.mode == mode && p.percentile == percentile;
                    let raster = p.raster.clone();
                    s.previews.push(p);
                    if ready {
                        return Ok(raster);
                    }
                    Some(raster)
                } else {
                    None
                }
            };
        let raster = if let Some(raster) = cached {
            raster.relevel_correction(&values, shape, mode, percentile)
        } else {
            if values.iter().any(|v| !v.is_finite() || *v <= 0.) {
                return Err(
                    "Correction preview is not finite and positive across this detector.".into(),
                );
            }
            Raster::correction(&values, shape, mode, percentile)
        };
        control.check()?;
        Self::retain_preview(
            &mut self.0.state.lock().unwrap(),
            Preview {
                kind: kind.into(),
                key,
                values,
                shape,
                mode: mode.into(),
                percentile,
                raster: raster.clone(),
            },
        );
        Ok(raster)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn preparation_is_queued_coalesced_and_discards_obsolete_and_cancelled_jobs() {
        let maps = Maps::default();
        maps.0.state.lock().unwrap().defer_workers = true;
        let control = Control::default();
        let first = Arc::new(vec![1., 2., 3., 4.]);
        let first_key = Key::References(first.clone(), None, [2, 2], vec![]);
        maps.get("flat", first_key.clone(), &control, || Ok(first))
            .unwrap();
        let old = {
            let s = maps.0.state.lock().unwrap();
            assert!(s.previews.is_empty());
            assert_eq!(s.queued.len(), 1);
            s.queued[0].clone()
        };
        let second = Arc::new(vec![2., 4., 6., 8.]);
        let second_key = Key::References(second.clone(), None, [2, 2], vec![]);
        maps.get("flat", second_key.clone(), &control, || Ok(second.clone()))
            .unwrap();
        assert_eq!(maps.0.state.lock().unwrap().queued.len(), 1);
        Maps::run_job(&maps.0, old);
        assert!(maps.0.state.lock().unwrap().previews.is_empty());
        let job = {
            let mut s = maps.0.state.lock().unwrap();
            let j = s.queued.remove(0);
            s.running = Some(j.clone());
            j
        };
        let waiting = maps.clone();
        let (sender, receiver) = std::sync::mpsc::channel();
        let request = std::thread::spawn(move || {
            sender
                .send(waiting.preview(
                    "flat",
                    second,
                    [2, 2],
                    "percentile",
                    2.5,
                    &Control::default(),
                ))
                .unwrap()
        });
        Maps::run_job(&maps.0, job);
        let plotted = receiver
            .recv_timeout(Duration::from_secs(2))
            .unwrap()
            .unwrap();
        request.join().unwrap();
        let (ready, pending) = maps.prepared(&[("flat".into(), second_key)]);
        assert!(!pending);
        assert!(Arc::ptr_eq(&plotted.buffer.bytes, &ready[0].buffer.bytes));
        assert!(maps.prepared(&[("flat".into(), first_key)]).0.is_empty());
        let third = Arc::new(vec![3., 6., 9., 12.]);
        let third_key = Key::References(third.clone(), None, [2, 2], vec![]);
        maps.get("flat", third_key.clone(), &control, || Ok(third))
            .unwrap();
        let cancelled = maps.0.state.lock().unwrap().queued[0].clone();
        maps.cancel_preparation();
        Maps::run_job(&maps.0, cancelled);
        let (ready, pending) = maps.prepared(&[("flat".into(), third_key.clone())]);
        assert!(!pending && ready.is_empty());
        maps.get("flat", third_key, &control, || {
            panic!("Recomputed scientific map after display cancellation")
        })
        .unwrap();
        assert_eq!(maps.0.state.lock().unwrap().queued.len(), 1);
    }

    #[test]
    fn replot_and_auto_reuse_display_bytes_but_new_maps_replace_them() {
        let maps = Maps::default();
        let control = Control::default();
        let values = Arc::new(vec![1., 2., 3., 4.]);
        let first = maps
            .preview("test", values.clone(), [2, 2], "percentile", 2.5, &control)
            .unwrap();
        let second = maps
            .preview("test", values.clone(), [2, 2], "percentile", 2.5, &control)
            .unwrap();
        assert!(Arc::ptr_eq(&first.buffer.bytes, &second.buffer.bytes));
        assert_eq!(first.metadata, second.metadata);
        let auto = maps
            .preview("test", values, [2, 2], "minmax", 2.5, &control)
            .unwrap();
        assert!(Arc::ptr_eq(&first.buffer.bytes, &auto.buffer.bytes));
        assert_eq!(first.metadata["histogram"], auto.metadata["histogram"]);
        assert_ne!(first.metadata["limits"], auto.metadata["limits"]);
        let changed = maps
            .preview(
                "test",
                Arc::new(vec![2., 4., 6., 8.]),
                [2, 2],
                "minmax",
                2.5,
                &control,
            )
            .unwrap();
        assert!(!Arc::ptr_eq(&first.buffer.bytes, &changed.buffer.bytes));
    }
    #[test]
    fn source_identity_transforms_and_cancelled_builds_cannot_reuse_stale_references() {
        let maps = Maps::default();
        let control = Control::default();
        let source = Arc::new(vec![1., 2., 3., 4.]);
        let key = Key::References(source.clone(), None, [2, 2], vec![]);
        let first = maps
            .get("flat", key.clone(), &control, || Ok(source.clone()))
            .unwrap();
        let again = maps
            .clone()
            .get("flat", key, &control, || panic!("Rebuilt unchanged map"))
            .unwrap();
        assert!(Arc::ptr_eq(&first, &again));
        let replacement = Arc::new(source.as_ref().clone());
        let key = Key::References(replacement.clone(), None, [2, 2], vec![]);
        let changed = maps
            .get("flat", key.clone(), &control, || Ok(replacement))
            .unwrap();
        assert!(!Arc::ptr_eq(&first, &changed));
        let transformed =
            Key::References(source.clone(), None, [2, 2], vec![Transform::Horizontal]);
        let values = maps
            .get("flat", transformed, &control, || {
                Ok(Arc::new(vec![2., 1., 4., 3.]))
            })
            .unwrap();
        assert_ne!(*first, *values);
        let failed = maps.get("flat", key.clone(), &control, || {
            Err("Invalid reference".into())
        });
        assert!(failed.is_err());
        control.cancel();
        assert!(maps.get("flat", key, &control, || Ok(source)).is_err());
        maps.clear("flat");
        let start = std::time::Instant::now();
        let mut state = maps.0.state.lock().unwrap();
        while state.running.as_ref().is_some_and(|j| j.kind == "flat") {
            assert!(start.elapsed() < Duration::from_secs(2));
            state = maps
                .0
                .changed
                .wait_timeout(state, Duration::from_millis(10))
                .unwrap()
                .0;
        }
        drop(state);
        assert_eq!(maps.bytes(), 0);
    }
}
