//! Private development handoff. Scientific arrays use the owned format-2 project;
//! runtime settings/identities supplement it without saving the user's project.
use super::*;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
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
    project_path: Option<PathBuf>,
    configurations: Vec<RuntimeConfiguration>,
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
        let configurations = self
            .project
            .configurations
            .iter()
            .enumerate()
            .map(|(i, c)| {
                RuntimeConfiguration::capture(if i == self.project.selected {
                    &active
                } else {
                    c.as_ref().unwrap()
                })
            })
            .collect();
        let handoff = Handoff {
            version: 1,
            project_path: self.project.path.clone(),
            configurations,
        };
        self.save_native_project(path(args)?)?;
        let file = hdf5::File::open_rw(path(args)?).native()?;
        write_json_dataset(
            &file,
            "development_session",
            &serde_json::to_value(handoff).map_err(|e| e.to_string())?,
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
        let handoff: Handoff =
            serde_json::from_value(read_json_dataset(&file, "development_session")?)
                .map_err(|e| e.to_string())?;
        drop(file);
        if handoff.version != 1
            || handoff.configurations.is_empty()
            || handoff.configurations.len() > 64
        {
            return Err("Unsupported development session checkpoint.".into());
        }
        let mut ids = std::collections::BTreeSet::new();
        for c in &handoff.configurations {
            if c.id == 0 || c.id == u64::MAX || !ids.insert(c.id) {
                return Err("Invalid checkpoint configuration identity.".into());
            }
        }
        self.open_native_project(path(args)?)?;
        if self.project.configurations.len() != handoff.configurations.len() {
            return Err("Checkpoint configuration counts differ.".into());
        }
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
