//! Format-2 .dio compatibility and per-configuration scientific ownership.
//! Unknown state/objects stay in an owned archive; saves publish a sibling file.
use super::*;
use checkpoint::Checkpoint;
#[path = "project/compact.rs"]
mod compact;
#[path = "project_config.rs"]
mod config;
#[cfg(debug_assertions)]
#[path = "project/development.rs"]
mod development;
#[path = "project_io.rs"]
mod io;
#[path = "project/navigation.rs"]
mod navigation;
#[cfg(test)]
#[path = "project/persistence_tests.rs"]
mod persistence_tests;
#[path = "project_phases.rs"]
mod phase;
#[path = "project_series.rs"]
mod series;
use io::*;
use std::rc::Rc;
static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(1);
fn next_id() -> u64 {
    NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
}
#[derive(Clone)]
pub(super) struct Configuration {
    id: u64,
    pub(super) state: Checkpoint,
    document: Arc<Value>,
    source_index: Option<usize>,
    label: String,
}
#[derive(Clone)]
pub(super) struct Project {
    pub path: Option<PathBuf>,
    pub configurations: Vec<Option<Rc<Configuration>>>,
    pub selected: usize,
    document: Arc<Value>,
    active_document: Arc<Value>,
    active_source: Option<usize>,
    active_label: String,
    pub active_id: u64,
    archive: Option<Arc<Archive>>,
    #[cfg(debug_assertions)]
    omit_development_session: bool,
}
impl Default for Project {
    fn default() -> Self {
        Self {
            path: None,
            configurations: vec![None],
            selected: 0,
            document: Arc::new(json!({})),
            active_document: Arc::new(json!({})),
            active_source: None,
            active_label: "Configuration 1".into(),
            active_id: next_id(),
            archive: None,
            #[cfg(debug_assertions)]
            omit_development_session: false,
        }
    }
}
impl Project {
    pub fn labels(&self) -> Vec<String> {
        self.configurations
            .iter()
            .enumerate()
            .map(|(i, c)| {
                if i == self.selected {
                    self.active_label.clone()
                } else {
                    c.as_ref().unwrap().label.clone()
                }
            })
            .collect()
    }
}
impl Session {
    pub(super) fn forget_other_shared_history(&mut self) {
        for c in self.project.configurations.iter_mut().flatten() {
            Rc::make_mut(c)
                .state
                .integration_history
                .forget_shared_edits();
        }
    }
    fn capture_configuration(&self) -> Configuration {
        Configuration {
            id: self.project.active_id,
            state: self.checkpoint(),
            document: self.project.active_document.clone(),
            source_index: self.project.active_source,
            label: self.project.active_label.clone(),
        }
    }
    fn select_configuration(&mut self, index: usize) -> Result<(), String> {
        if index >= self.project.configurations.len() {
            return Err("Choose an existing configuration.".into());
        }
        if index == self.project.selected {
            return Ok(());
        }
        let current = self.capture_configuration();
        let target = self.project.configurations[index]
            .as_ref()
            .ok_or("Configuration is unavailable.")?
            .clone();
        self.project.configurations[self.project.selected] = Some(Rc::new(current));
        let phases = self.phases.clone();
        let global_patterns = self.patterns.clone();
        let revision = self.revision;
        let shared_overlays_changed = target.state.patterns.overlays != global_patterns.overlays;
        let combination = self.combination.clone();
        self.restore_checkpoint(target.state.clone());
        self.combination = combination;
        self.phases = phases;
        self.patterns.restore_global(&global_patterns);
        self.project.selected = index;
        self.project.active_id = target.id;
        self.project.active_document = target.document.clone();
        self.project.active_source = target.source_index;
        self.project.active_label = target.label.clone();
        self.project.configurations[index] = None;
        self.revision = revision;
        // Inspection belongs to the restored configuration, including its
        // geometry and image generation; keep valid clicks when switching.
        if let Some(image) = &self.image {
            self.retain_inspection(image.shape);
        } else {
            self.inspection = None;
        }
        self.rebuild_pattern()?;
        if shared_overlays_changed
            && let Some(scan) = self
                .scan
                .as_mut()
                .filter(|s| s.expressions.iter().any(|(_, e)| e.contains("ovl")))
        {
            scan.rebuild(false, &self.patterns)?;
        }
        Ok(())
    }
    fn configuration_reply(&mut self) -> Reply {
        self.revision += 1;
        let mut reply = self.snapshot(true);
        reply.result["clearImage"] = json!(self.image.is_none());
        reply
    }
    pub(super) fn project_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        match action {
            #[cfg(debug_assertions)]
            "development_checkpoint" => self.save_development_checkpoint(args).map(Some),
            #[cfg(debug_assertions)]
            "development_restore" => self.restore_development_checkpoint(args).map(Some),
            "configuration_navigation" => self.navigate_configurations(args).map(Some),
            "save_project" => {
                check_keys(args, &["path"])?;
                let mut file = path(args)?.to_path_buf();
                if !file
                    .extension()
                    .is_some_and(|e| e.eq_ignore_ascii_case("dio"))
                {
                    file = PathBuf::from(format!("{}.dio", file.display()));
                }
                self.save_native_project(&file)?;
                self.project.path = Some(file.clone());
                self.revision += 1;
                let mut reply = self.snapshot(false);
                reply.result["savedPath"] = json!(file);
                Ok(Some(reply))
            }
            "open_project" => {
                check_keys(args, &["path"])?;
                self.open_native_project(path(args)?)?;
                let legacy = self.project.document["configurations"]
                    .as_array()
                    .is_some_and(|docs| {
                        docs.iter().any(|doc| {
                            doc["native_desktop"]["sample_absorption"].is_null()
                                && ["cylinder", "sphere"]
                                    .iter()
                                    .any(|kind| doc["img"]["corrections"].get(kind).is_some())
                        })
                    });
                let mut reply = self.configuration_reply();
                let legacy_detector = self.project.document["configurations"]
                    .as_array()
                    .is_some_and(|docs| {
                        docs.iter().any(|doc| {
                            doc["native_desktop"]["detector_absorption"]["model"]
                                != "calibrated-pixel-incidence-v1"
                                && doc["img"]["corrections"].get("oiadac").is_some()
                        })
                    });
                if legacy_detector {
                    reply.result["correctionNotice"] = json!(if legacy {
                        "Recalculated legacy sample and detector absorption using calibrated geometry"
                    } else {
                        "Recalculated detector absorption using calibrated geometry; legacy detector tilt/rotation overrides were discarded"
                    });
                } else if legacy {
                    reply.result["correctionNotice"] =
                        json!("Recalculated legacy sample absorption using corrected geometry");
                }
                Ok(Some(reply))
            }
            "configuration" => {
                check_keys(args, &["operation", "index", "name"])?;
                match args["operation"].as_str().unwrap_or("select") {
                    "select" => {
                        let index = integer(
                            &args["index"],
                            "Configuration",
                            0,
                            self.project.configurations.len() - 1,
                        )?;
                        self.select_configuration(index)?;
                    }
                    "add" | "duplicate" => {
                        if self.project.configurations.len() >= 64 {
                            return Err(
                                "A native project supports at most 64 configurations.".into()
                            );
                        }
                        let current = self.capture_configuration();
                        let mut target = if args["operation"] == "duplicate" {
                            current.clone()
                        } else {
                            let mut fresh = Session::new(self.root.clone());
                            fresh.settings.geometry = self.settings.geometry.clone();
                            fresh.settings.calibrated = self.settings.calibrated;
                            fresh.settings.calibration_name =
                                self.settings.calibration_name.clone();
                            fresh.settings.calibration_path =
                                self.settings.calibration_path.clone();
                            fresh.calibration.start = self.calibration.start;
                            fresh.calibration.reference = self.calibration.reference.clone();
                            fresh.calibration.custom = self.calibration.custom.clone();
                            fresh.calibration.reference_wavelength =
                                self.calibration.reference_wavelength;
                            fresh.settings.automatic_binning = true;
                            fresh.settings.trim_zeros = true;
                            fresh.settings.use_mask = false;
                            fresh.patterns.background.iterations =
                                defaults()["pattern"]["auto_bkg_iterations"]
                                    .as_u64()
                                    .unwrap() as usize;
                            fresh.calibration.confirmed = self.calibration.confirmed;
                            fresh.calibration.source = self.calibration.source.clone();
                            fresh.files.image_directory = self.files.image_directory.clone();
                            fresh.files.output_directory = self.files.output_directory.clone();
                            if let Some(image) = &self.image {
                                fresh.publish_image(Image::from_cached(
                                    PathBuf::new(),
                                    0,
                                    1,
                                    image.shape,
                                    self.scientific_values().as_ref().clone(),
                                    json!({}),
                                )?)?;
                                fresh.control = self.control.clone();
                                fresh.calculate(false)?;
                            }
                            fresh.files.image_directory = self.files.image_directory.clone();
                            fresh.files.output_directory = self.files.output_directory.clone();
                            fresh.capture_configuration()
                        };
                        if args["operation"] == "add" {
                            target.source_index = None;
                            target.document = Arc::new(json!({}));
                        }
                        target.label =
                            format!("Configuration {}", self.project.configurations.len() + 1);
                        target.id = next_id();
                        self.project.configurations.push(Some(Rc::new(target)));
                        self.select_configuration(self.project.configurations.len() - 1)?;
                    }
                    "remove" => {
                        if self.project.configurations.len() > 1 {
                            let index = self.project.selected;
                            let target = if index + 1 == self.project.configurations.len() {
                                index - 1
                            } else {
                                index + 1
                            };
                            self.select_configuration(target)?;
                            self.project.configurations.remove(index);
                            if self.project.selected > index {
                                self.project.selected -= 1;
                            }
                        }
                    }
                    "rename" => {
                        let name = args["name"]
                            .as_str()
                            .filter(|s| {
                                !s.trim().is_empty()
                                    && s.len() <= 250
                                    && !s.chars().any(char::is_control)
                            })
                            .ok_or("Use a printable configuration name, at most 250 characters.")?;
                        self.project.active_label = name.trim().into();
                    }
                    _ => return Err("Choose select, add, duplicate, remove or rename.".into()),
                }
                Ok(Some(self.configuration_reply()))
            }
            _ => Ok(None),
        }
    }
    fn open_native_project(&mut self, path: &Path) -> Result<(), String> {
        let path = path.canonicalize().map_err(|e| e.to_string())?;
        let source_identity = crate::image::FileIdentity::read(&path)?;
        let archive = snapshot_file(&path, &self.control)?;
        let file = archive.file.clone();
        let version = file
            .attr("format_version")
            .ok()
            .and_then(|a| a.read_scalar::<u32>().ok())
            .unwrap_or(0);
        if version != 2 {
            return Err(if version < 2 {
                "This project predates format 2. Open it with the Dioptas version that wrote it and re-export the needed data.".into()
            } else {
                format!("Project format {version} is newer than the supported format 2.")
            });
        }
        let document = read_json_dataset(&file, "state")?;
        let docs = document["configurations"]
            .as_array()
            .filter(|a| !a.is_empty() && a.len() <= 64)
            .ok_or("A project needs 1–64 configurations.")?;
        let selected = integer(
            document.get("selected_configuration").unwrap_or(&json!(0)),
            "Selected configuration",
            0,
            docs.len() - 1,
        )?;
        validate_sample_budget(&file, &document)?;
        let mut candidate = Session::new(self.root.clone());
        candidate.control = self.control.clone();
        phase::load(&mut candidate, &document)?;
        config::load_overlays(&mut candidate, &file, &document)?;
        let phases = candidate.phases.clone();
        let global_patterns = candidate.patterns.clone();
        let desktop = read_json_attr(&file, "react_desktop")?.unwrap_or(json!({}));
        let mut configurations = Vec::new();
        for (i, doc) in docs.iter().enumerate() {
            self.control.check()?;
            self.control.publish(json!({"running":true,"current":i,"total":docs.len(),"label":"Restoring project configurations"}));
            let mut owner = Session::new(self.root.clone());
            owner.control = self.control.clone();
            owner.phases = phases.clone();
            owner.patterns.restore_global(&global_patterns);
            config::load(&mut owner, &file, doc, &desktop, i, selected)?;
            let mut c = owner.capture_configuration();
            c.document = Arc::new(doc.clone());
            c.source_index = Some(i);
            c.label = doc["native_desktop"]["label"]
                .as_str()
                .unwrap_or("")
                .to_string();
            if c.label.is_empty() {
                c.label = format!("Configuration {}", i + 1);
            }
            #[cfg(feature = "dioptrin")]
            if i == selected {
                std::mem::swap(&mut candidate.engine, &mut owner.engine);
            }
            configurations.push(Some(Rc::new(c)));
        }
        let active = configurations[selected].take().unwrap();
        candidate.restore_checkpoint(active.state.clone());
        candidate.phases = phases;
        candidate.patterns.restore_global(&global_patterns);
        candidate.project = Project {
            path: Some(path.clone()),
            configurations,
            selected,
            document: Arc::new(document.clone()),
            active_document: active.document.clone(),
            active_source: Some(selected),
            active_label: active.label.clone(),
            active_id: active.id,
            archive: Some(Arc::new(archive)),
            #[cfg(debug_assertions)]
            omit_development_session: false,
        };
        candidate.combination.patterns = desktop["combination"]["patterns"]
            .as_bool()
            .unwrap_or(false);
        candidate.combination.cakes = desktop["combination"]["cakes"].as_bool().unwrap_or(false);
        candidate.combination.cake_source_unit = desktop["combination"]["cake_source_unit"]
            .as_str()
            .filter(|unit| ["2th_deg", "q_A^-1"].contains(unit))
            .map(str::to_owned);
        candidate.revision = self.revision;
        self.control.check()?;
        if source_identity != crate::image::FileIdentity::read(&path)? {
            return Err("Project changed while its snapshot was being restored.".into());
        }
        // No automatic saves or incoming-file watchers are armed by opening data.
        std::mem::swap(&mut self.project, &mut candidate.project);
        self.restore_checkpoint(candidate.checkpoint());
        #[cfg(feature = "dioptrin")]
        std::mem::swap(&mut self.engine, &mut candidate.engine);
        Ok(())
    }
    fn save_native_project(&self, path: &Path) -> Result<(), String> {
        let temp = crate::output::StagedOutput::new(path)?;
        let working = tempfile::NamedTempFile::new().map_err(|e| e.to_string())?;
        if let Some(source) = &self.project.archive {
            copy_handle(source.snapshot.as_file(), working.path(), &self.control)?;
        }
        let file = if self.project.archive.is_some() {
            hdf5::File::open_rw(working.path())
        } else {
            hdf5::File::create(working.path())
        }
        .native()?;
        #[cfg(debug_assertions)]
        if self.project.omit_development_session {
            replace(&file, "development_session")?;
        }
        let compact = compact::can_compact(&file, &self.control)?;
        if !compact {
            compact::retain_opaque_objects(&file, &self.control)?;
        }
        write_scalar_attr(&file, "format_version", 2_u32)?;
        write_text_attr(&file, "__version__", env!("CARGO_PKG_VERSION"))?;
        let payloads = ensure_group(&file, "payloads")?;
        let cache = ensure_group(&file, "cache")?;
        let mut document = self.project.document.as_ref().clone();
        if !document.is_object() {
            document = json!({});
        }
        let mut configs = self.project.configurations.clone();
        configs[self.project.selected] = Some(Rc::new(self.capture_configuration()));
        // Reindex complete configuration groups so unknown extensions follow the
        // configuration through deletion/reordering instead of another index.
        let previous = "__native_previous_configurations";
        if file.link_exists(previous) {
            return Err("Reserved project staging group already exists.".into());
        }
        // Keep the container's own attributes, aliases and unknown children.
        // Stage only the numeric groups owned by the previous document.
        let groups = ensure_group(&file, "configurations")?;
        let staged = file.create_group(previous).native()?;
        for i in 0..self.project.document["configurations"]
            .as_array()
            .map_or(0, Vec::len)
        {
            let name = i.to_string();
            if groups.link_exists(&name) {
                file.relink(
                    &format!("configurations/{name}"),
                    &format!("{previous}/{name}"),
                )
                .native()?;
            }
        }
        let mut used = std::collections::BTreeSet::new();
        let mut config_documents = vec![];
        for (i, c) in configs.iter().enumerate() {
            self.control.check()?;
            self.control.publish(json!({"running":true,"current":i,"total":configs.len(),"label":"Saving project configurations"}));
            let mut c = c.as_ref().unwrap().as_ref().clone();
            c.state.patterns.restore_global(&self.patterns);
            let name = i.to_string();
            if groups.link_exists(&name) {
                return Err("A configuration would overwrite an unknown project extension.".into());
            }
            let old = c.source_index.map(|i| format!("{previous}/{i}"));
            if let Some(old) = old.filter(|p| file.link_exists(p)) {
                if used.insert(old.clone()) {
                    groups.link_hard(&format!("/{old}"), &name).native()?;
                } else if compact {
                    file.group(&old)
                        .native()?
                        .copy_to(&groups, &name)
                        .native()?;
                } else {
                    return Err("Cannot duplicate a configuration with opaque HDF5 references without rewriting its extension addresses.".into());
                }
            }
            let group = ensure_group(&groups, &name)?;
            config_documents.push(config::save(&c, &group, &payloads, &cache)?);
        }
        drop(staged);
        file.unlink(previous).native()?;
        document["configurations"] = json!(config_documents);
        document["selected_configuration"] = json!(self.project.selected);
        config::save_overlays(self, &payloads, &mut document)?;
        phase::save(self, &mut document)?;
        validate_sample_budget(&file, &document)?;
        write_json_dataset(&file, "state", &document)?;
        let mut metadata = read_json_attr(&file, "react_desktop")?.unwrap_or(json!({}));
        merge(&mut metadata, &config::desktop_metadata(self));
        write_text_attr(&file, "react_desktop", &metadata.to_string())?;
        series::save_active_extensions(self, &file)?;
        if compact {
            compact::prune_pools(&file, &document, &self.control)?;
        }
        file.flush().native()?;
        drop(payloads);
        drop(cache);
        drop(groups);
        if compact {
            compact::write_fresh(&file, temp.path(), &self.control)?;
            drop(file);
        } else {
            drop(file);
            copy_file(working.path(), temp.path(), &self.control)?;
        }
        finish_project(temp, path, &self.control, MAX_PROJECT_BYTES)
    }
}
