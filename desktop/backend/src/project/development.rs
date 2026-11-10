//! Private development handoff. Scientific arrays use the owned format-2 project;
//! runtime settings/identities supplement it without saving the user's project.
use super::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Serialize, Deserialize)]
struct RuntimeConfiguration {
    id: u64,
    settings: Settings,
    files: file_workflow::Files,
    calibration: Calibration,
    workflow: Workflow,
    inspection: Option<linked::Inspection>,
    image_generation: u64,
    revision: u64,
    elapsed_ms: Option<f64>,
}
#[derive(Serialize, Deserialize)]
struct Handoff {
    version: u32,
    #[serde(default)]
    worker_count: Option<usize>,
    project_path: Option<PathBuf>,
    configurations: Vec<RuntimeConfiguration>,
}
#[derive(Serialize, Deserialize)]
struct ConfigurationHistory {
    runtime: RuntimeConfiguration,
    processing: crate::processing::Processing,
    patterns: crate::pattern::Patterns,
    phases: crate::phases::Phases,
    mask: MaskSnapshot,
    undo: Vec<MaskSnapshot>,
    redo: Vec<MaskSnapshot>,
    calibration_history: History,
    integration_history: integration_history::IntegrationHistory,
}
impl ConfigurationHistory {
    fn capture(c: &Configuration) -> Self {
        let s = &c.state;
        Self {
            runtime: RuntimeConfiguration::capture(c),
            processing: s.processing.clone(),
            patterns: s.patterns.clone(),
            phases: s.phases.clone(),
            mask: MaskSnapshot {
                mode: s.mask_mode,
                user: s.mask.clone(),
                plugins: s.plugins.states.clone(),
            },
            undo: s.undo.clone(),
            redo: s.redo.clone(),
            calibration_history: s.calibration_history.clone(),
            integration_history: s.integration_history.clone(),
        }
    }
    fn restore(self, c: &mut Configuration) {
        self.runtime.restore(c);
        let s = &mut c.state;
        s.processing = self.processing;
        s.patterns = self.patterns;
        s.phases = self.phases;
        s.mask_mode = self.mask.mode;
        s.mask = self.mask.user;
        s.plugins.states = self.mask.plugins;
        s.undo = self.undo;
        s.redo = self.redo;
        s.calibration_history = self.calibration_history;
        s.integration_history = self.integration_history;
    }
}
fn history_path(path: &Path) -> PathBuf {
    path.with_extension("history.h5")
}
impl RuntimeConfiguration {
    fn capture(c: &Configuration) -> Self {
        let s = &c.state;
        Self {
            id: c.id,
            settings: s.settings.clone(),
            files: s.files.clone(),
            calibration: s.calibration.clone(),
            workflow: s.workflow.clone(),
            inspection: s.inspection.clone(),
            image_generation: s.image_generation,
            revision: s.revision,
            elapsed_ms: s.elapsed_ms,
        }
    }
    fn restore(self, c: &mut Configuration) {
        c.id = self.id;
        let s = &mut c.state;
        s.settings = self.settings;
        s.files = self.files;
        s.calibration = self.calibration;
        s.workflow = self.workflow;
        s.inspection = self.inspection;
        s.image_generation = self.image_generation;
        s.revision = self.revision;
        s.elapsed_ms = self.elapsed_ms;
    }
}
impl Session {
    pub(super) fn save_development_checkpoint(&self, args: &Value) -> Result<Reply, String> {
        check_keys(args, &["path"])?;
        let active = self.capture_configuration();
        let configurations: Vec<_> = self
            .project
            .configurations
            .iter()
            .enumerate()
            .map(|(i, c)| {
                ConfigurationHistory::capture(if i == self.project.selected {
                    &active
                } else {
                    c.as_ref().unwrap()
                })
            })
            .collect();
        // Keep history out of the .dio archive: normal user project saves must
        // not copy hidden undo planes or accumulate discarded-history blocks.
        let destination = history_path(path(args)?);
        let pending = tempfile::NamedTempFile::new_in(
            destination
                .parent()
                .filter(|p| !p.as_os_str().is_empty())
                .unwrap_or(Path::new(".")),
        )
        .map_err(|e| e.to_string())?;
        let history = hdf5::File::create(pending.path()).native()?;
        static GENERATION: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(1);
        let generation = format!(
            "{}-{}",
            std::process::id(),
            GENERATION.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
        );
        write_json_dataset(&history, "development_generation", &json!(generation))?;
        crate::history_transfer::save(&history, &configurations)?;
        history.flush().native()?;
        drop(history);
        pending.as_file().sync_all().map_err(|e| e.to_string())?;
        pending.persist(destination).map_err(|e| e.to_string())?;
        self.save_native_project(path(args)?)?;
        let file = hdf5::File::open_rw(path(args)?).native()?;
        write_json_dataset(
            &file,
            "development_session",
            &json!({"version":2,"worker_count":self.worker_count,"project_path":self.project.path,"history_generation":generation,"configuration_ids":configurations.iter().map(|c|c.runtime.id).collect::<Vec<_>>()}),
        )?;
        file.flush().native()?;
        Ok(Reply::metadata(json!({"ok":true})))
    }
    pub(super) fn restore_development_checkpoint(&mut self, args: &Value) -> Result<Reply, String> {
        check_keys(args, &["path", "project_only"])?;
        // One-time upgrade of an older live host, which can save projects but
        // does not yet have the private development checkpoint command.
        if args
            .get("project_only")
            .map(|v| boolean(v, "Project-only recovery"))
            .transpose()?
            .unwrap_or(false)
        {
            self.open_native_project(path(args)?)?;
            // Preserve automation preferences without replaying old inputs or
            // writing outputs while restoring this older project checkpoint.
            let selected = self.project.selected;
            let docs = self.project.document["configurations"]
                .as_array()
                .unwrap()
                .clone();
            for (i, doc) in docs.iter().enumerate() {
                let mut c = if i == selected {
                    self.capture_configuration()
                } else {
                    self.project.configurations[i]
                        .as_ref()
                        .unwrap()
                        .as_ref()
                        .clone()
                };
                c.state.settings.auto_save = doc["params"]["auto_save_integrated_pattern"]
                    .as_bool()
                    .unwrap_or(false);
                c.state.files.auto_process = doc["img"]["autoprocess"].as_bool().unwrap_or(false);
                if c.state.files.auto_process {
                    c.state.files.baseline()?;
                }
                if i == selected {
                    self.restore_checkpoint(c.state);
                } else {
                    self.project.configurations[i] = Some(Rc::new(c));
                }
            }
            self.project.path = None;
            return Ok(self.configuration_reply());
        }
        let file = hdf5::File::open(path(args)?).native()?;
        let metadata = read_json_dataset(&file, "development_session")?;
        drop(file);
        let histories: Option<Vec<ConfigurationHistory>> = match metadata["version"].as_u64() {
            Some(1) => None,
            Some(2) => {
                let history = hdf5::File::open(history_path(path(args)?)).native()?;
                if read_json_dataset(&history, "development_generation")?
                    != metadata["history_generation"]
                {
                    return Err("History checkpoint generation differs from the session.".into());
                }
                Some(crate::history_transfer::load(&history)?)
            }
            _ => return Err("Unsupported development session checkpoint.".into()),
        };
        let handoff: Handoff = if let Some(histories) = &histories {
            let ids = histories.iter().map(|h| h.runtime.id).collect::<Vec<_>>();
            if json!(ids) != metadata["configuration_ids"] {
                return Err("History checkpoint configuration identities differ.".into());
            }
            Handoff {
                version: 2,
                worker_count: metadata["worker_count"].as_u64().map(|n| n as usize),
                project_path: serde_json::from_value(metadata["project_path"].clone())
                    .map_err(|e| e.to_string())?,
                configurations: histories.iter().map(|h| h.runtime.clone()).collect(),
            }
        } else {
            serde_json::from_value(metadata).map_err(|e| e.to_string())?
        };
        if handoff.configurations.is_empty() || handoff.configurations.len() > 64 {
            return Err("Unsupported development session checkpoint.".into());
        }
        let mut ids = std::collections::BTreeSet::new();
        for c in &handoff.configurations {
            if c.id == 0 || c.id == u64::MAX || !ids.insert(c.id) {
                return Err("Invalid checkpoint configuration identity.".into());
            }
        }
        let worker_count = handoff
            .worker_count
            .map(|n| n.clamp(1, crate::worker_pool::available()));
        let worker_pool = crate::worker_pool::pool(worker_count)?;
        self.open_native_project(path(args)?)?;
        if self.project.configurations.len() != handoff.configurations.len() {
            return Err("Checkpoint configuration counts differ.".into());
        }
        self.worker_count = worker_count;
        self.worker_pool = Some(worker_pool);
        let selected = self.project.selected;
        for (i, runtime) in handoff.configurations.into_iter().enumerate() {
            let mut configuration = if i == selected {
                self.capture_configuration()
            } else {
                self.project.configurations[i]
                    .as_ref()
                    .unwrap()
                    .as_ref()
                    .clone()
            };
            runtime.restore(&mut configuration);
            if i == selected {
                self.project.active_id = configuration.id;
                self.restore_checkpoint(configuration.state);
            } else {
                self.project.configurations[i] = Some(Rc::new(configuration));
            }
        }
        if let Some(histories) = histories {
            for (i, history) in histories.into_iter().enumerate() {
                let mut c = if i == selected {
                    self.capture_configuration()
                } else {
                    self.project.configurations[i]
                        .as_ref()
                        .unwrap()
                        .as_ref()
                        .clone()
                };
                history.restore(&mut c);
                if i == selected {
                    self.restore_checkpoint(c.state);
                } else {
                    self.project.configurations[i] = Some(Rc::new(c));
                }
            }
        }
        NEXT.fetch_max(
            ids.last().unwrap() + 1,
            std::sync::atomic::Ordering::Relaxed,
        );
        self.project.path = handoff.project_path;
        // The internal handoff is not an extension to subsequent user saves.
        if let Some(archive) = &self.project.archive {
            hdf5::File::open_rw(archive.path())
                .native()?
                .unlink("development_session")
                .native()?;
        }
        // A new worker has new kernels/plans; preserve settings, not stale results.
        #[cfg(feature = "dioptrin")]
        {
            self.prepared = None;
            self.combination_plans = None;
        }
        let auto_save = self.settings.auto_save;
        self.settings.auto_save = false;
        let result = if self.patterns.imported {
            self.rebuild_pattern()
        } else {
            self.calculate(false)
        };
        self.settings.auto_save = auto_save;
        result?;
        self.revision += 1;
        Ok(self.snapshot(true))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn version_one_checkpoints_remain_readable_during_the_one_time_worker_upgrade() {
        let t = tempfile::tempdir().unwrap();
        let p = t.path().join("legacy.dio");
        let mut old = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."));
        old.settings.bins = 777;
        old.settings.automatic_binning = false;
        old.save_native_project(&p).unwrap();
        let legacy = Handoff {
            version: 1,
            worker_count: None,
            project_path: None,
            configurations: vec![RuntimeConfiguration::capture(&old.capture_configuration())],
        };
        let file = hdf5::File::open_rw(&p).unwrap();
        write_json_dataset(
            &file,
            "development_session",
            &serde_json::to_value(legacy).unwrap(),
        )
        .unwrap();
        drop(file);
        let mut new = Session::new(old.root.clone());
        new.restore_development_checkpoint(&json!({"path":p}))
            .unwrap();
        assert_eq!(new.settings.bins, 777);
        assert!(new.calibration_history.undo.is_empty());
        assert!(!new.integration_history.can_undo());
    }
}
