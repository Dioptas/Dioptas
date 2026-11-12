//! Native automatic recovery. No legacy ~/.Dioptas files are read or written.
use crate::processor_reload::ProcessorHost;
use serde_json::{json, Value};
use std::{
    path::{Path, PathBuf},
    sync::{Arc, Condvar, Mutex},
};

/// Count admitted IPC work before dispatching it to a blocking worker. Close
/// must drain even calls that have not yet acquired the processor's gate.
#[derive(Default)]
pub struct ActiveCommands {
    state: Mutex<(bool, usize)>,
    changed: Condvar,
}
pub struct ActiveCommand(Arc<ActiveCommands>);
impl ActiveCommands {
    pub fn enter(self: &Arc<Self>) -> Result<ActiveCommand, String> {
        let mut state = self.state.lock().unwrap();
        if state.0 {
            return Err("Saving the session before closing…".into());
        }
        state.1 += 1;
        Ok(ActiveCommand(self.clone()))
    }
    pub fn stop(&self) {
        self.state.lock().unwrap().0 = true;
    }
    pub fn wait(&self) {
        let mut state = self.state.lock().unwrap();
        while state.1 != 0 {
            state = self.changed.wait(state).unwrap();
        }
    }
}
impl Drop for ActiveCommand {
    fn drop(&mut self) {
        self.0.state.lock().unwrap().1 -= 1;
        self.0.changed.notify_all();
    }
}

pub struct Recovery {
    path: Option<PathBuf>,
    state: Mutex<RecoveryState>,
    operations: Mutex<()>,
}
#[derive(Default)]
struct RecoveryState {
    ready: bool,
    protected_revision: Option<u64>,
    revision: u64,
    saved_revision: Option<u64>,
    ui: Value,
    saved_ui: Value,
    ui_initialized: bool,
    startup: Vec<Value>,
    explicit_startup: bool,
}

pub fn startup_files(args: &[String]) -> Vec<Value> {
    let mut files = Vec::new();
    let mut args = args.iter().skip(1);
    while let Some(arg) = args.next() {
        let explicit = ["--project", "--image", "--calibration"]
            .into_iter()
            .find_map(|flag| {
                arg.strip_prefix(&format!("{flag}="))
                    .map(|p| (flag, p.to_owned()))
            });
        let pair = explicit.or_else(|| match arg.as_str() {
            "--project" | "--image" | "--calibration" => {
                args.next().map(|p| (arg.as_str(), p.clone()))
            }
            _ if !arg.starts_with('-') => Some(("", arg.clone())),
            _ => None,
        });
        if let Some((flag, path)) = pair {
            let extension = Path::new(&path)
                .extension()
                .unwrap_or_default()
                .to_string_lossy()
                .to_lowercase();
            let action = match (flag, extension.as_str()) {
                ("--project", _) | ("", "dio") => "open_project",
                ("--calibration", _) | ("", "poni") => "open_calibration",
                _ => "open_image",
            };
            files.push(json!({"action":action,"path":path}));
        }
    }
    files
}

impl Recovery {
    pub fn new(directory: Option<PathBuf>, startup: Vec<Value>) -> Self {
        let explicit_startup = !startup.is_empty();
        Self {
            path: directory.map(|p| p.join("native-session-v1.dio")),
            state: Mutex::new(RecoveryState {
                ui: json!({}),
                saved_ui: json!({}),
                startup,
                explicit_startup,
                ..Default::default()
            }),
            operations: Mutex::new(()),
        }
    }
    #[cfg(any(target_os = "macos", target_os = "ios"))]
    pub fn opened_files(&self, files: Vec<String>) {
        let mut args = vec!["dioptas".to_owned()];
        args.extend(files);
        let mut state = self.state.lock().unwrap();
        state.startup.extend(startup_files(&args));
        state.explicit_startup = true;
    }
    fn revision(processor: &ProcessorHost) -> Result<u64, String> {
        let status = processor
            .request_packet("recovery_status", json!({}), vec![])?
            .result_value()?;
        if status["ok"] != true {
            return Err("Could not inspect the session for recovery.".into());
        }
        status["revision"]
            .as_u64()
            .ok_or_else(|| "Missing session revision.".into())
    }
    pub fn command(
        &self,
        processor: &ProcessorHost,
        operation: &str,
        ui: Option<Value>,
    ) -> Result<Value, String> {
        let _operation = self.operations.lock().map_err(|e| e.to_string())?;
        match operation {
            "status" => {
                let revision = if self.path.is_some() {
                    Self::revision(processor)?
                } else {
                    0
                };
                let mut state = self.state.lock().unwrap();
                state.revision = revision;
                if state.saved_revision.is_none() {
                    state.saved_revision = Some(revision);
                }
                let startup = std::mem::take(&mut state.startup);
                let available = self.path.as_ref().is_some_and(|p| p.exists());
                // Explicit startup work takes priority and must succeed before
                // it can replace a retained checkpoint on close.
                if !startup.is_empty() {
                    state.ready = true;
                    state.protected_revision = Some(state.revision);
                    return Ok(json!({"available":false,"startup":startup}));
                }
                if !available {
                    state.ready = true;
                }
                Ok(json!({"available":available && !state.ready,"path":self.path}))
            }
            "ui" => {
                let ui = ui.ok_or("Missing recovery display settings.")?;
                if !ui.is_object() || ui.to_string().len() > 256 * 1024 {
                    return Err("Invalid recovery display settings.".into());
                }
                let mut state = self.state.lock().unwrap();
                if !state.ui_initialized {
                    state.saved_ui = ui.clone();
                    state.ui_initialized = true;
                }
                state.ui = ui;
                Ok(json!({"ok":true}))
            }
            "fresh" => {
                self.state.lock().unwrap().ready = true;
                Ok(json!({"ok":true}))
            }
            "restore" => {
                if self.state.lock().unwrap().explicit_startup {
                    return Err("Opening explicitly requested files takes priority over automatic recovery.".into());
                }
                let path = self.path.as_ref().ok_or("Session recovery is disabled.")?;
                let revision = Self::revision(processor)?;
                let result = processor
                    .request_packet("recovery_restore", json!({"path":path}), vec![])
                    .and_then(|p| p.result_value());
                let mut state = self.state.lock().unwrap();
                state.revision = revision;
                // Protection also applies to transport/child failures.
                state.protected_revision = Some(state.revision);
                let result = result?;
                if result["ok"] != true {
                    return Err(result["error"]
                        .as_str()
                        .unwrap_or("Recovery failed.")
                        .into());
                }
                state.ready = true;
                state.revision = result["state"]["revision"]
                    .as_u64()
                    .unwrap_or(state.revision);
                state.protected_revision = None;
                state.saved_revision = Some(state.revision);
                state.ui = result["recoveryUi"].clone();
                state.saved_ui = state.ui.clone();
                state.ui_initialized = true;
                Ok(
                    json!({"ok":true,"ui":result["recoveryUi"],"missingSources":result["missingSources"]}),
                )
            }
            _ => Err("Unknown recovery operation.".into()),
        }
    }
    pub fn checkpoint(&self, processor: &ProcessorHost, closing: bool) -> Result<(), String> {
        let _operation = self.operations.lock().map_err(|e| e.to_string())?;
        let Some(path) = &self.path else {
            return Ok(());
        };
        // Query metadata after queued scientific work; never serialize image
        // display buffers just to decide whether an idle backup is necessary.
        let revision = Self::revision(processor)?;
        let (revision, ui) = {
            let mut state = self.state.lock().unwrap();
            state.revision = revision;
            if !state.ready
                || state.protected_revision == Some(state.revision)
                || (!closing
                    && state.saved_revision == Some(state.revision)
                    && state.saved_ui == state.ui)
            {
                return Ok(());
            }
            (state.revision, state.ui.clone())
        };
        std::fs::create_dir_all(path.parent().unwrap()).map_err(|e| e.to_string())?;
        let result = processor
            .request_packet("recovery_checkpoint", json!({"path":path,"ui":ui}), vec![])?
            .result_value()?;
        if result["ok"] != true {
            return Err(result["error"]
                .as_str()
                .unwrap_or("Could not save session recovery.")
                .into());
        }
        let mut state = self.state.lock().unwrap();
        state.saved_revision = Some(result["revision"].as_u64().unwrap_or(revision));
        state.saved_ui = ui;
        Ok(())
    }
}

#[tauri::command]
pub async fn session_recovery(
    window: tauri::WebviewWindow,
    host: tauri::State<'_, crate::Host>,
    operation: String,
    ui: Option<Value>,
) -> Result<Value, String> {
    if window.label() != "main" {
        return Err("Recovery belongs to the main window.".into());
    }
    let _admitted = host.active_commands.enter()?;
    let processor = host.processor.clone()?;
    let recovery = host.recovery.clone();
    tauri::async_runtime::spawn_blocking(move || recovery.command(&processor, &operation, ui))
        .await
        .map_err(|e| e.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::processor::Backend;
    #[test]
    fn close_drains_admitted_work_and_rejects_later_commands() {
        let commands = Arc::new(ActiveCommands::default());
        let admitted = commands.enter().unwrap();
        commands.stop();
        assert!(commands.enter().is_err());
        let waiting = commands.clone();
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            waiting.wait();
            tx.send(()).unwrap();
        });
        assert!(rx
            .recv_timeout(std::time::Duration::from_millis(30))
            .is_err());
        drop(admitted);
        rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap();
    }
    fn new_host() -> std::sync::Arc<ProcessorHost> {
        ProcessorHost::start(false, Backend::Rust, None).unwrap()
    }
    fn edit(host: &ProcessorHost, bins: usize) {
        let result = host
            .request_packet("integration_settings", json!({"bins":bins}), vec![])
            .unwrap()
            .result_value()
            .unwrap();
        assert_eq!(result["ok"], true, "{result}");
    }
    #[test]
    fn normal_close_checkpoint_restart_restore_and_idle_backup() {
        let directory = tempfile::tempdir().unwrap();
        let recovery = Recovery::new(Some(directory.path().to_owned()), vec![]);
        let host = new_host();
        assert_eq!(
            recovery.command(&host, "status", None).unwrap()["available"],
            false
        );
        edit(&host, 137);
        recovery
            .command(&host, "ui", Some(json!({"mode":"mask"})))
            .unwrap();
        recovery.checkpoint(&host, true).unwrap();
        host.shutdown();
        let path = directory.path().join("native-session-v1.dio");
        let bytes = std::fs::read(&path).unwrap();
        let restarted = new_host();
        let recovery = Recovery::new(Some(directory.path().to_owned()), vec![]);
        assert_eq!(
            recovery.command(&restarted, "status", None).unwrap()["available"],
            true
        );
        // Closing before choosing must leave the checkpoint alone.
        recovery.checkpoint(&restarted, true).unwrap();
        assert_eq!(std::fs::read(&path).unwrap(), bytes);
        assert_eq!(
            recovery.command(&restarted, "restore", None).unwrap()["ui"],
            json!({"mode":"mask"})
        );
        let state = restarted
            .request_packet("state", json!({}), vec![])
            .unwrap()
            .result_value()
            .unwrap();
        assert_eq!(state["state"]["bins"], 137);
        let modified = std::fs::metadata(&path).unwrap().modified().unwrap();
        recovery.checkpoint(&restarted, false).unwrap();
        assert_eq!(
            std::fs::metadata(&path).unwrap().modified().unwrap(),
            modified
        );
        restarted.shutdown();
    }
    #[test]
    fn decline_starts_fresh_and_failed_recovery_stays_protected_until_work_changes() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("native-session-v1.dio");
        std::fs::write(&path, b"corrupt snapshot retained for inspection").unwrap();
        let host = new_host();
        let recovery = Recovery::new(Some(directory.path().to_owned()), vec![]);
        assert_eq!(
            recovery.command(&host, "status", None).unwrap()["available"],
            true
        );
        assert!(recovery.command(&host, "restore", None).is_err());
        recovery.command(&host, "fresh", None).unwrap();
        recovery.checkpoint(&host, true).unwrap();
        assert_eq!(
            std::fs::read(&path).unwrap(),
            b"corrupt snapshot retained for inspection"
        );
        edit(&host, 227);
        recovery.checkpoint(&host, true).unwrap();
        host.shutdown();
        let restarted = new_host();
        let recovery = Recovery::new(Some(directory.path().to_owned()), vec![]);
        recovery.command(&restarted, "status", None).unwrap();
        recovery.command(&restarted, "fresh", None).unwrap();
        let state = restarted
            .request_packet("state", json!({}), vec![])
            .unwrap()
            .result_value()
            .unwrap();
        assert_eq!(state["state"]["bins"], json!(1000));
        recovery.checkpoint(&restarted, true).unwrap();
        restarted.shutdown();
        let next = new_host();
        let recovery = Recovery::new(Some(directory.path().to_owned()), vec![]);
        recovery.command(&next, "restore", None).unwrap();
        let state = next
            .request_packet("state", json!({}), vec![])
            .unwrap()
            .result_value()
            .unwrap();
        assert_eq!(state["state"]["bins"], json!(1000));
        next.shutdown();
    }
    #[test]
    fn explicit_startup_suppresses_prompt_and_protects_previous_file_on_failure() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("native-session-v1.dio");
        std::fs::write(&path, b"previous").unwrap();
        let startup = startup_files(&["app".into(), "missing.dio".into()]);
        let recovery = Recovery::new(Some(directory.path().to_owned()), startup.clone());
        let host = new_host();
        let status = recovery.command(&host, "status", None).unwrap();
        assert_eq!(status["available"], false);
        assert_eq!(status["startup"], json!(startup));
        assert!(recovery.command(&host, "restore", None).is_err());
        recovery.checkpoint(&host, true).unwrap();
        assert_eq!(std::fs::read(&path).unwrap(), b"previous");
        host.shutdown();
    }
    #[test]
    fn explicit_startup_paths_preserve_order_and_types() {
        let args = [
            "app",
            "--backend=rust",
            "--project=a.dio",
            "b.tif",
            "--calibration",
            "c.poni",
        ]
        .map(str::to_owned);
        assert_eq!(
            startup_files(&args),
            vec![
                json!({"action":"open_project","path":"a.dio"}),
                json!({"action":"open_image","path":"b.tif"}),
                json!({"action":"open_calibration","path":"c.poni"})
            ]
        );
        assert!(startup_files(&["app".into(), "--smoke".into()]).is_empty());
    }
}
