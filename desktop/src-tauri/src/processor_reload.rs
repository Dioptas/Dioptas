//! Development replaces only the scientific child, after a validated handoff.
//! Ordinary commands are serialized; progress/cancel bypass the swap gate.
use crate::processor::{Backend, Packet, Processor};
use serde_json::{json, Value};
use std::{
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex, RwLock,
    },
};

struct Running {
    processor: Processor,
    _executable: Option<tempfile::TempDir>,
}
pub struct ProcessorHost {
    current: RwLock<Running>,
    operations: Mutex<()>,
    closed: AtomicBool,
    #[cfg(debug_assertions)]
    build: Mutex<Option<std::process::Child>>,
}
impl ProcessorHost {
    pub fn start(
        example: bool,
        backend: Backend,
        resources: Option<&Path>,
    ) -> Result<Arc<Self>, String> {
        Ok(Arc::new(Self {
            current: RwLock::new(Running {
                processor: Processor::start_backend_at(example, backend, resources)?,
                _executable: None,
            }),
            operations: Mutex::new(()),
            closed: AtomicBool::new(false),
            #[cfg(debug_assertions)]
            build: Mutex::new(None),
        }))
    }
    pub fn request_packet(
        &self,
        action: &str,
        payload: Value,
        cached: Vec<String>,
    ) -> Result<Packet, String> {
        // A queued restart must never prevent cancellation of the operation it
        // is waiting for. Do not hold a writer lock until operations are idle.
        let _operation = if matches!(action, "progress" | "cancel_refinement") {
            None
        } else {
            Some(self.operations.lock().map_err(|e| e.to_string())?)
        };
        if self.closed.load(Ordering::Acquire) {
            return Err("The desktop session is closed.".into());
        }
        self.current
            .read()
            .map_err(|e| e.to_string())?
            .processor
            .request_packet(action, payload, cached)
    }
    pub fn shutdown(&self) {
        self.closed.store(true, Ordering::Release);
        #[cfg(debug_assertions)]
        if let Some(child) = self.build.lock().unwrap().as_mut() {
            let _ = child.kill();
        }
        self.current.read().unwrap().processor.shutdown();
    }
    #[cfg(debug_assertions)]
    fn restart(&self, binary: &Path) -> Result<(), String> {
        let executable = tempfile::tempdir().map_err(|e| e.to_string())?;
        let copy = executable.path().join(if cfg!(windows) {
            "dioptas-processor.exe"
        } else {
            "dioptas-processor"
        });
        std::fs::copy(binary, &copy).map_err(|e| e.to_string())?;
        // Start/check the candidate before pausing commands or writing a checkpoint.
        let candidate = Processor::start_backend_binary(
            false,
            Backend::Rust,
            None, // Live updates use the checkout's current scientific resources.
            Some(&copy),
        )?;
        let identity = candidate
            .request_packet("__host__", json!({}), vec![])?
            .result_value()?;
        if identity["ok"] != true
            || identity["runtime"] != "rust"
            || identity["engine"] != "dioptrin"
        {
            return Err("The new worker is not the native Rust/Dioptrin backend.".into());
        }
        let _operation = self.operations.lock().map_err(|e| e.to_string())?;
        if self.closed.load(Ordering::Acquire) {
            return Err("The desktop session is closed.".into());
        }
        let running = self.current.read().map_err(|e| e.to_string())?;
        let checkpoint = executable.path().join("session.dio");
        for (processor, action) in [
            (&running.processor, "development_checkpoint"),
            (&candidate, "development_restore"),
        ] {
            let result = processor
                .request_packet(action, json!({"path":checkpoint}), vec![])?
                .result_value()?;
            if result["ok"] != true {
                return Err(result["error"]
                    .as_str()
                    .unwrap_or("Cannot restore the development session.")
                    .into());
            }
        }
        drop(running);
        let mut running = self.current.write().map_err(|e| e.to_string())?;
        if self.closed.load(Ordering::Acquire) {
            return Err("The desktop session is closed.".into());
        }
        let previous = std::mem::replace(
            &mut *running,
            Running {
                processor: candidate,
                _executable: Some(executable),
            },
        );
        drop(running);
        drop(_operation);
        // The old process/backup remains available until the handoff succeeds.
        previous.processor.shutdown();
        Ok(())
    }
    #[cfg(debug_assertions)]
    pub fn watch(self: &Arc<Self>, notify: impl Fn(Value) + Send + Sync + 'static) {
        if std::env::var("DIOPTAS_DEV_RELOAD").as_deref() == Ok("0") {
            return;
        }
        self.watch_at(Processor::source_root().join("desktop/backend"), notify);
    }
    #[cfg(debug_assertions)]
    fn watch_at(self: &Arc<Self>, root: PathBuf, notify: impl Fn(Value) + Send + Sync + 'static) {
        let weak = Arc::downgrade(self);
        std::thread::spawn(move || {
            let mut observed = source_stamp(&root);
            let mut pending = None;
            loop {
                std::thread::sleep(std::time::Duration::from_millis(350));
                let Some(host) = weak.upgrade() else {
                    break;
                };
                if host.closed.load(Ordering::Acquire) {
                    break;
                }
                let stamp = source_stamp(&root);
                if stamp != observed {
                    observed = stamp;
                    pending = Some(std::time::Instant::now());
                }
                if !pending
                    .is_some_and(|since| since.elapsed() >= std::time::Duration::from_millis(700))
                {
                    continue;
                }
                pending = None;
                notify(json!({"phase":"building","message":"Rebuilding Rust backend…"}));
                let result = host.build_backend(&root).and_then(|binary| {
                    // Never publish an obsolete build if another edit arrived during compilation.
                    if source_stamp(&root) != observed { return Ok(false); }
                    notify(json!({"phase":"restoring","message":"Restoring session in updated Rust backend…"}));
                    host.restart(&binary).map(|_|true)
                });
                match result {
                    Ok(true) => notify(
                        json!({"phase":"ready","message":"Rust backend updated · session restored"}),
                    ),
                    Ok(false) => {
                        observed = source_stamp(&root);
                        pending = Some(std::time::Instant::now());
                    }
                    Err(error) => notify(
                        json!({"phase":"error","message":format!("Backend update failed; current session retained. {error}")}),
                    ),
                }
            }
        });
    }
    #[cfg(debug_assertions)]
    fn build_backend(&self, root: &Path) -> Result<PathBuf, String> {
        let directory = tempfile::tempdir().map_err(|e| e.to_string())?;
        let log = directory.path().join("build.log");
        let stdout = std::fs::File::create(&log).map_err(|e| e.to_string())?;
        let stderr = stdout.try_clone().map_err(|e| e.to_string())?;
        let mut command =
            std::process::Command::new(std::env::var_os("CARGO").unwrap_or_else(|| "cargo".into()));
        command
            .args(["build", "--locked", "--manifest-path"])
            .arg(root.join("Cargo.toml"))
            .args(["--bin", "dioptas-processor"])
            .stdout(stdout)
            .stderr(stderr);
        if cfg!(target_os = "macos") {
            command.env("MACOSX_DEPLOYMENT_TARGET", "14.0");
        }
        *self.build.lock().unwrap() = Some(command.spawn().map_err(|e| e.to_string())?);
        let status = loop {
            if self.closed.load(Ordering::Acquire) {
                if let Some(child) = self.build.lock().unwrap().as_mut() {
                    let _ = child.kill();
                }
            }
            let status = self
                .build
                .lock()
                .unwrap()
                .as_mut()
                .unwrap()
                .try_wait()
                .map_err(|e| e.to_string())?;
            if let Some(status) = status {
                self.build.lock().unwrap().take();
                break status;
            }
            std::thread::sleep(std::time::Duration::from_millis(200));
        };
        if !status.success() {
            let text = std::fs::read_to_string(log).unwrap_or_default();
            let tail = text
                .lines()
                .rev()
                .take(18)
                .collect::<Vec<_>>()
                .into_iter()
                .rev()
                .collect::<Vec<_>>()
                .join("\n");
            return Err(tail);
        }
        Ok(root.join("target/debug").join(if cfg!(windows) {
            "dioptas-processor.exe"
        } else {
            "dioptas-processor"
        }))
    }
}
#[cfg(debug_assertions)]
fn source_stamp(root: &Path) -> u64 {
    use std::hash::{Hash, Hasher};
    fn visit(path: &Path, hash: &mut impl Hasher) {
        let Ok(metadata) = std::fs::metadata(path) else {
            return;
        };
        if metadata.is_dir() {
            let Ok(entries) = std::fs::read_dir(path) else {
                return;
            };
            let mut paths = entries
                .filter_map(Result::ok)
                .map(|v| v.path())
                .collect::<Vec<_>>();
            paths.sort();
            for path in paths {
                visit(&path, hash);
            }
        } else {
            path.hash(hash);
            metadata.len().hash(hash);
            metadata.modified().ok().hash(hash);
        }
    }
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    for name in [
        "src",
        "data",
        "resources",
        "Cargo.toml",
        "Cargo.lock",
        "build.rs",
    ] {
        visit(&root.join(name), &mut hash);
    }
    hash.finish()
}

#[cfg(all(test, debug_assertions))]
mod tests {
    use super::*;
    use std::{
        process::{Command, Stdio},
        sync::mpsc,
        time::Duration,
    };
    fn call(host: &ProcessorHost, action: &str, payload: Value) -> Value {
        let result = host
            .request_packet(action, payload, vec![])
            .unwrap()
            .result_value()
            .unwrap();
        assert_eq!(result["ok"], true, "{action}: {result}");
        result
    }
    fn binary() -> PathBuf {
        Processor::source_root().join("desktop/backend/target/debug/dioptas-processor")
    }
    fn phase(rx: &mpsc::Receiver<Value>, wanted: &str) {
        let started = std::time::Instant::now();
        loop {
            let status = rx.recv_timeout(Duration::from_secs(60)).unwrap();
            if status["phase"] == wanted {
                return;
            }
            assert!(started.elapsed() < Duration::from_secs(60), "{status}");
            if wanted != "error" {
                assert_ne!(status["phase"], "error", "{status}");
            }
        }
    }
    #[test]
    fn automatic_rebuild_restores_session_and_keeps_it_running_through_failed_builds() {
        let host = ProcessorHost::start(false, Backend::Rust, None).unwrap();
        let fixture =
            Processor::source_root().join("desktop/backend/tests/fixtures/combined-counts.h5");
        call(
            &host,
            "open_image",
            json!({"path":fixture,"dataset":"/counts"}),
        );
        call(
            &host,
            "manual_geometry",
            json!({"convention":"pyfai","values":{"dist":0.2,"poni1":0.0032,"poni2":0.004,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":4e-11,"polarization_factor":0.}}),
        );
        call(
            &host,
            "integration_settings",
            json!({"bins":48,"cake_bins":12}),
        );
        call(&host, "configuration", json!({"operation":"duplicate"}));
        call(
            &host,
            "combination_settings",
            json!({"patterns":true,"cakes":true,"factor":2}),
        );
        let before = call(&host, "state", json!({}));
        let original_pid = call(&host, "__host__", json!({}))["pid"].clone();
        // Compile a tiny Rust launcher around the real numerical worker. This
        // exercises source watching/Cargo/replacement without a full clean build.
        let workspace = tempfile::tempdir().unwrap();
        let root = workspace.path();
        std::fs::create_dir(root.join("src")).unwrap();
        std::fs::write(
            root.join("Cargo.toml"),
            "[package]\nname='dioptas-processor'\nversion='0.0.0'\nedition='2021'\n[workspace]\n",
        )
        .unwrap();
        let source=format!("fn main() {{ std::process::exit(std::process::Command::new({:?}).args(std::env::args().skip(1)).status().unwrap().code().unwrap_or(1)); }}",binary().to_str().unwrap());
        let file = root.join("src/main.rs");
        std::fs::write(&file, &source).unwrap();
        assert!(Command::new("cargo")
            .args(["generate-lockfile", "--offline", "--manifest-path"])
            .arg(root.join("Cargo.toml"))
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .unwrap()
            .success());
        let (tx, rx) = mpsc::channel();
        host.watch_at(root.to_path_buf(), move |status| {
            let _ = tx.send(status);
        });
        std::thread::sleep(Duration::from_millis(500));
        std::fs::write(&file, format!("{source}\n// first edit")).unwrap();
        phase(&rx, "ready");
        let first_pid = call(&host, "__host__", json!({}))["pid"].clone();
        assert_ne!(first_pid, original_pid);
        let after = call(&host, "state", json!({}));
        for key in [
            "configurationContext",
            "configurationIndex",
            "configurationLabels",
            "shape",
            "imagePath",
            "geometry",
            "unit",
            "bins",
            "combination",
            "projectName",
            "projectPath",
        ] {
            assert_eq!(after["state"][key], before["state"][key], "{key}");
        }
        assert_eq!(after["pattern"], before["pattern"]);
        std::fs::write(&file, "not valid Rust").unwrap();
        phase(&rx, "error");
        assert_eq!(call(&host, "__host__", json!({}))["pid"], first_pid);
        assert_eq!(call(&host, "state", json!({})), after);
        std::fs::write(&file, format!("{source}\n// fixed edit")).unwrap();
        phase(&rx, "ready");
        assert_ne!(call(&host, "__host__", json!({}))["pid"], first_pid);
        assert_eq!(
            call(&host, "state", json!({}))["state"]["configurationContext"],
            before["state"]["configurationContext"]
        );
        host.shutdown();
    }
    #[test]
    fn queued_restart_allows_progress_and_cancel_and_failed_candidate_keeps_the_old_worker() {
        let host = ProcessorHost::start(false, Backend::Rust, None).unwrap();
        let before = call(&host, "state", json!({}));
        let pid = call(&host, "__host__", json!({}))["pid"].clone();
        let queued = host.operations.lock().unwrap();
        let other = host.clone();
        let thread = std::thread::spawn(move || other.restart(&binary()));
        std::thread::sleep(Duration::from_millis(200));
        call(&host, "progress", json!({}));
        call(&host, "cancel_refinement", json!({}));
        drop(queued);
        thread.join().unwrap().unwrap();
        assert_ne!(call(&host, "__host__", json!({}))["pid"], pid);
        let current = call(&host, "__host__", json!({}))["pid"].clone();
        let dir = tempfile::tempdir().unwrap();
        let bad = dir.path().join("not-an-executable");
        std::fs::write(&bad, b"bad executable").unwrap();
        assert!(host.restart(&bad).is_err());
        assert_eq!(call(&host, "__host__", json!({}))["pid"], current);
        let after = call(&host, "state", json!({}));
        assert_eq!(
            after["state"]["configurationContext"],
            before["state"]["configurationContext"]
        );
        host.shutdown();
    }
    #[test]
    fn build_products_do_not_count_as_source_edits() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path();
        std::fs::create_dir(root.join("src")).unwrap();
        std::fs::write(root.join("src/main.rs"), "initial").unwrap();
        let before = source_stamp(root);
        std::fs::create_dir(root.join("target")).unwrap();
        std::fs::write(root.join("target/executable"), "binary").unwrap();
        assert_eq!(source_stamp(root), before);
        std::fs::write(root.join("src/main.rs"), "changed source").unwrap();
        assert_ne!(source_stamp(root), before);
    }
}
