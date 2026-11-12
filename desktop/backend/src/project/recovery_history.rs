//! Bounded undo/redo companions referenced by an atomic recovery checkpoint.
use super::*;
use serde::{Deserialize, Serialize};

pub(super) const MAX_BYTES: usize = 128 * 1024 * 1024;
const PREFIX: &str = ".dioptas-recovery-history-";
#[derive(Serialize, Deserialize)]
struct ConfigurationHistory {
    revision: u64,
    settings: Settings,
    processing: crate::processing::Processing,
    patterns: crate::pattern::Patterns,
    phases: crate::phases::Phases,
    calibration: Calibration,
    workflow: Workflow,
    undo: Vec<MaskSnapshot>,
    redo: Vec<MaskSnapshot>,
    calibration_history: History,
    integration_history: integration_history::IntegrationHistory,
}
impl ConfigurationHistory {
    fn capture(c: &Configuration) -> Self {
        let s = &c.state;
        Self {
            revision: s.revision,
            settings: s.settings.clone(),
            processing: s.processing.clone(),
            patterns: s.patterns.clone(),
            phases: s.phases.clone(),
            calibration: s.calibration.clone(),
            workflow: s.workflow.clone(),
            undo: s.undo.clone(),
            redo: s.redo.clone(),
            calibration_history: s.calibration_history.clone(),
            integration_history: s.integration_history.clone(),
        }
    }
    fn count(&self) -> usize {
        self.undo.len()
            + self.redo.len()
            + self.calibration_history.undo.len()
            + self.calibration_history.redo.len()
            + self.integration_history.recovery_count()
    }
    fn trim(&mut self) {
        self.undo.drain(..self.undo.len().div_ceil(2));
        self.redo.drain(..self.redo.len().div_ceil(2));
        self.integration_history
            .trim_recovery(&mut self.calibration_history);
    }
    fn restore(mut self, c: &mut Configuration) -> Result<(), String> {
        let s = &mut c.state;
        if self.revision == u64::MAX
            || self.undo.len() + self.redo.len() > 256
            || self
                .undo
                .iter()
                .chain(&self.redo)
                .any(|m| m.user.len() != s.mask.len())
            || self.calibration_history.undo.len() + self.calibration_history.redo.len() > 256
            || self
                .calibration_history
                .undo
                .iter()
                .chain(&self.calibration_history.redo)
                .any(|e| e.3 > self.revision)
        {
            return Err("Invalid recovered edit history.".into());
        }
        self.settings.auto_save = false;
        self.integration_history.disarm_recovery(self.revision)?;
        s.settings = self.settings;
        s.processing = self.processing;
        s.patterns = self.patterns;
        s.phases = self.phases;
        s.calibration = self.calibration;
        s.workflow = self.workflow;
        s.undo = self.undo;
        s.redo = self.redo;
        s.calibration_history = self.calibration_history;
        s.integration_history = self.integration_history;
        s.revision = self.revision;
        Ok(())
    }
}
#[derive(Serialize, Deserialize)]
struct Histories {
    version: u32,
    generation: String,
    revision: u64,
    configurations: Vec<Option<ConfigurationHistory>>,
}

impl Histories {
    fn trim(&mut self) {
        for entry in &mut self.configurations {
            if let Some(history) = entry {
                history.trim();
                if history.count() == 0 {
                    *entry = None;
                }
            }
        }
    }
}
pub(super) fn companion_path(checkpoint: &Path, metadata: &Value) -> Option<PathBuf> {
    let name = metadata["history"]["file"].as_str()?;
    // Only our generated sibling filenames are eligible for loading/cleanup.
    if !name.starts_with(PREFIX)
        || !name.ends_with(".h5")
        || name.contains(['/', '\\'])
        || !name
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b".-_".contains(&c))
        || Path::new(name).components().count() != 1
    {
        return None;
    }
    Some(checkpoint.parent().unwrap_or(Path::new(".")).join(name))
}
pub(super) fn previous_companion(checkpoint: &Path) -> Option<PathBuf> {
    if !checkpoint.is_file() {
        return None;
    }
    let file = hdf5::File::open(checkpoint).ok()?;
    companion_path(
        checkpoint,
        &read_json_dataset(&file, "native_recovery").ok()?,
    )
}

/// The TempPath removes an unpublished generation on every failure. It is kept
/// only after the core .dio is committed, so the old pair remains valid until then.
pub(super) fn save(
    s: &Session,
    checkpoint: &Path,
    maximum: usize,
) -> Result<(Option<tempfile::TempPath>, Value), String> {
    let active = s.capture_configuration();
    let mut histories = Histories {
        version: 1,
        revision: s.revision,
        generation: String::new(),
        configurations: s
            .project
            .configurations
            .iter()
            .enumerate()
            .map(|(i, c)| {
                let history = ConfigurationHistory::capture(if i == s.project.selected {
                    &active
                } else {
                    c.as_ref().unwrap()
                });
                (history.count() > 0).then_some(history)
            })
            .collect(),
    };
    let original: usize = histories
        .configurations
        .iter()
        .flatten()
        .map(ConfigurationHistory::count)
        .sum();
    if original == 0 {
        return Ok((None, json!({"kept":0,"dropped":0})));
    }
    let parent = checkpoint
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let destination = crate::output::resource_path(parent, PREFIX, ".h5")?;
    let name = destination
        .file_name()
        .unwrap()
        .to_string_lossy()
        .into_owned();
    histories.generation = name.clone();
    let staged = crate::output::StagedOutput::new(&destination)?;
    loop {
        s.control.check()?;
        let count: usize = histories
            .configurations
            .iter()
            .flatten()
            .map(ConfigurationHistory::count)
            .sum();
        if count == 0 {
            return Ok((None, json!({"kept":0,"dropped":original})));
        }
        // Truncate on each retry; discarded graph objects cannot accumulate.
        let file = hdf5::File::create(staged.path()).native()?;
        let result = crate::history_transfer::save_named(
            &file,
            "recovery_history",
            &histories,
            maximum,
            s.control.clone(),
        );
        match result {
            Ok(()) => {
                file.flush().native()?;
                file.close().native()?;
                if staged
                    .as_file()
                    .metadata()
                    .map_err(|e| e.to_string())?
                    .len()
                    > (maximum + 16 * 1024 * 1024) as u64
                {
                    histories.trim();
                    continue;
                }
                staged.commit_checked(&destination, || s.control.check())?;
                return Ok((
                    Some(destination),
                    json!({"file":name,"generation":histories.generation,"kept":count,"dropped":original-count}),
                ));
            }
            Err(error) if crate::history_transfer::is_limit(&error) => {
                file.close().native()?;
                histories.trim();
            }
            Err(error) => return Err(error),
        }
    }
}
pub(super) fn restore(
    s: &mut Session,
    checkpoint: &Path,
    metadata: &Value,
) -> Result<Option<String>, String> {
    if metadata["version"] == 1 {
        return Ok(None);
    }
    let history = &metadata["history"];
    let kept = history["kept"]
        .as_u64()
        .ok_or("Missing recovered history count.")?;
    let dropped = history["dropped"]
        .as_u64()
        .ok_or("Missing recovered history limit information.")?;
    if kept > 64 * 768 || dropped > 64 * 768 {
        return Err("Invalid recovered history count.".into());
    }
    if kept > 0 {
        let path = companion_path(checkpoint, metadata)
            .ok_or("Invalid recovery history companion filename.")?;
        if std::fs::metadata(&path)
            .map_err(|e| format!("Recovery history is unavailable at {}: {e}", path.display()))?
            .len()
            > (MAX_BYTES + 16 * 1024 * 1024) as u64
        {
            return Err("Recovery history exceeds its file size bound.".into());
        }
        let file = hdf5::File::open(&path).native()?;
        let histories: Histories = crate::history_transfer::load_named(
            &file,
            "recovery_history",
            MAX_BYTES,
            s.control.clone(),
        )?;
        if histories.version != 1
            || histories.revision == u64::MAX
            || histories
                .configurations
                .iter()
                .flatten()
                .any(|c| c.revision > histories.revision)
            || json!(histories.generation) != history["generation"]
            || histories.generation != path.file_name().unwrap().to_string_lossy()
            || histories.configurations.len() != s.project.configurations.len()
            || histories
                .configurations
                .iter()
                .flatten()
                .map(ConfigurationHistory::count)
                .sum::<usize>() as u64
                != kept
        {
            return Err("Recovery history does not match this checkpoint.".into());
        }
        let selected = s.project.selected;
        let mut revision = s.revision.max(histories.revision);
        for (i, history) in histories.configurations.into_iter().enumerate() {
            let Some(history) = history else {
                continue;
            };
            s.control.check()?;
            revision = revision.max(history.revision);
            let mut c = if i == selected {
                s.capture_configuration()
            } else {
                s.project.configurations[i]
                    .as_ref()
                    .unwrap()
                    .as_ref()
                    .clone()
            };
            history.restore(&mut c)?;
            if i == selected {
                s.restore_checkpoint(c.state);
            } else {
                s.project.configurations[i] = Some(Rc::new(c));
            }
        }
        s.revision = revision;
    }
    Ok((dropped > 0).then(||format!("Recovery retained {kept} undo/redo steps. {dropped} older or oversized steps were omitted to keep recovery history within 128 MiB.")))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn session() -> Session {
        Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
    }
    fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
        let r = s.invoke(&crate::protocol::Request {
            id: 1,
            action: action.into(),
            payload,
            cached_buffers: vec![],
        });
        assert_eq!(r.result["ok"], true, "{}", r.result);
        r
    }
    #[test]
    fn bounded_history_keeps_nearest_edits_and_reports_when_none_fit() {
        let directory = tempfile::tempdir().unwrap();
        let checkpoint = directory.path().join("core.dio");
        let mut s = session();
        for bins in 100..116 {
            call(&mut s, "integration_settings", json!({"bins":bins}));
        }
        let (full_file, full) = save(&s, &checkpoint, MAX_BYTES).unwrap();
        assert_eq!(full["kept"], 16);
        let file = hdf5::File::open(full_file.as_ref().unwrap()).unwrap();
        let graph = file.group("recovery_history").unwrap();
        let objects = graph.group("objects").unwrap();
        let size = graph.dataset("root").unwrap().size()
            + objects
                .member_names()
                .unwrap()
                .iter()
                .map(|name| {
                    let object = objects.group(name).unwrap();
                    object.dataset("kind").unwrap().size() + object.dataset("data").unwrap().size()
                })
                .sum::<usize>();
        let (small, record) = save(&s, &checkpoint, size - 1).unwrap();
        assert!(record["dropped"].as_u64().unwrap() > 0, "{record}");
        assert!(record["kept"].as_u64().unwrap() > 0, "{record}");
        s.save_native_project(&checkpoint).unwrap();
        let mut recovered = session();
        recovered.open_native_project(&checkpoint).unwrap();
        let metadata = json!({"version":2,"history":record});
        assert!(
            restore(&mut recovered, &checkpoint, &metadata)
                .unwrap()
                .is_some()
        );
        assert_eq!(
            call(&mut recovered, "undo_calibration", json!({})).result["state"]["bins"],
            114
        );
        drop(small);
        let (none, record) = save(&s, &checkpoint, 1).unwrap();
        assert!(none.is_none());
        assert_eq!(record["kept"], 0);
        assert_eq!(record["dropped"], 16);
    }
    #[test]
    fn failed_core_publication_preserves_previous_history_and_cleans_unpublished_generation() {
        let directory = tempfile::tempdir().unwrap();
        let checkpoint = directory.path().join("core.dio");
        let mut s = session();
        call(&mut s, "integration_settings", json!({"bins":123}));
        call(&mut s, "recovery_checkpoint", json!({"path":checkpoint}));
        let previous = previous_companion(&checkpoint).unwrap();
        let core = std::fs::read(&checkpoint).unwrap();
        let history = std::fs::read(&previous).unwrap();
        let bad = directory.path().join("reserved.dio");
        s.save_native_project(&bad).unwrap();
        hdf5::File::open_rw(&bad)
            .unwrap()
            .create_group("__native_previous_configurations")
            .unwrap();
        s.open_native_project(&bad).unwrap();
        call(&mut s, "integration_settings", json!({"bins":124}));
        assert!(
            s.save_recovery_checkpoint(&json!({"path":checkpoint}))
                .is_err()
        );
        assert_eq!(std::fs::read(&checkpoint).unwrap(), core);
        assert_eq!(std::fs::read(&previous).unwrap(), history);
        assert_eq!(
            std::fs::read_dir(directory.path())
                .unwrap()
                .filter_map(Result::ok)
                .filter(|e| e.file_name().to_string_lossy().starts_with(PREFIX))
                .count(),
            1
        );
        s.restore_recovery_checkpoint(&json!({"path":checkpoint}))
            .unwrap();
        call(&mut s, "integration_settings", json!({"bins":124}));
        call(&mut s, "recovery_checkpoint", json!({"path":checkpoint}));
        assert!(!previous.exists());
        assert!(previous_companion(&checkpoint).unwrap().is_file());
    }
    #[test]
    fn recovery_undo_and_redo_cannot_rearm_automatic_exports_or_acquisition() {
        let directory = tempfile::tempdir().unwrap();
        let checkpoint = directory.path().join("core.dio");
        let mut s = session();
        s.settings.auto_save = true;
        s.files.auto_process = true;
        call(&mut s, "integration_settings", json!({"bins":123}));
        call(&mut s, "integration_settings", json!({"bins":124}));
        call(&mut s, "undo_calibration", json!({}));
        call(&mut s, "recovery_checkpoint", json!({"path":checkpoint}));
        let mut recovered = session();
        for action in ["recovery_restore", "redo_calibration", "undo_calibration"] {
            let r = call(
                &mut recovered,
                action,
                if action == "recovery_restore" {
                    json!({"path":checkpoint})
                } else {
                    json!({})
                },
            );
            assert_eq!(r.result["state"]["integration"]["autoSave"], false);
            assert_eq!(r.result["state"]["integration"]["autoProcess"], false);
        }
    }
    #[test]
    fn version_one_remains_readable_and_missing_or_corrupt_companions_roll_back() {
        let directory = tempfile::tempdir().unwrap();
        let checkpoint = directory.path().join("core.dio");
        let mut s = session();
        call(&mut s, "integration_settings", json!({"bins":123}));
        call(&mut s, "recovery_checkpoint", json!({"path":checkpoint}));
        let history = previous_companion(&checkpoint).unwrap();
        let core = std::fs::read(&checkpoint).unwrap();
        let original_history = std::fs::read(&history).unwrap();
        let mut recovered = session();
        let before = recovered.snapshot(false).result["state"].clone();
        std::fs::remove_file(&history).unwrap();
        assert!(
            recovered
                .restore_recovery_checkpoint(&json!({"path":checkpoint}))
                .is_err()
        );
        assert_eq!(recovered.snapshot(false).result["state"], before);
        std::fs::write(&history, b"corrupt graph").unwrap();
        assert!(
            recovered
                .restore_recovery_checkpoint(&json!({"path":checkpoint}))
                .is_err()
        );
        assert_eq!(recovered.snapshot(false).result["state"], before);
        assert_eq!(std::fs::read(&checkpoint).unwrap(), core);
        std::fs::write(&history, original_history).unwrap();
        let file = hdf5::File::open_rw(&checkpoint).unwrap();
        write_json_dataset(
            &file,
            "native_recovery",
            &json!({"version":1,"project_path":null,"ui":{}}),
        )
        .unwrap();
        drop(file);
        let r = recovered
            .restore_recovery_checkpoint(&json!({"path":checkpoint}))
            .unwrap();
        assert_eq!(r.result["state"]["bins"], 123);
        assert_eq!(r.result["state"]["calibration"]["canUndo"], false);
    }
}
