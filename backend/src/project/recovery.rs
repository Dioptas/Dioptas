//! Automatic recovery is an owned native project, never the user's project.
use super::*;

/// Single-crystal session in the recovery checkpoint (see `single_crystal_development.rs`).
pub(super) const SCXRD_ESSENTIALS: &str = "single_crystal_recovery";
pub(super) const SCXRD_PRODUCTS: &str = "single_crystal_recovery_products";
pub(super) const SCXRD_GENERATION: &str = "recovery";

fn scxrd_bytes(file: &hdf5::File, name: &str) -> Result<Vec<u8>, String> {
    file.dataset(name)
        .and_then(|d| d.read_raw::<u8>())
        .map_err(|e| e.to_string())
}

impl Session {
    /// Changes the recovery timer must save: powder state and SC commands.
    pub(super) fn recovery_revision(&self) -> u64 {
        self.revision.wrapping_add(self.scxrd_changes)
    }
}

impl Session {
    pub(super) fn save_recovery_checkpoint(&self, args: &Value) -> Result<Reply, String> {
        check_keys(args, &["path", "ui"])?;
        let ui = args.get("ui").cloned().unwrap_or(json!({}));
        if !ui.is_object() || ui.to_string().len() > 256 * 1024 {
            return Err("Recovery display settings must be an object smaller than 256 KiB.".into());
        }
        let checkpoint = path(args)?;
        let previous = recovery_history::previous_companion(checkpoint);
        let (mut history, record) =
            recovery_history::save(self, checkpoint, recovery_history::MAX_BYTES)?;
        let metadata =
            json!({"version":2,"project_path":self.project.path,"ui":ui,"history":record});
        // Publish a new history generation first, then atomically point the core
        // checkpoint at it. A failed core save deletes only that new generation.
        self.save_native_project_with_recovery(checkpoint, Some(&metadata))?;
        if let Some(history) = history.as_mut() {
            history.disable_cleanup(true);
        }
        if let Some(previous) =
            previous.filter(|old| history.as_ref().is_none_or(|new| old.as_path() != &**new))
            && let Err(error) = std::fs::remove_file(&previous)
        {
            eprintln!(
                "Could not remove obsolete recovery history {}: {error}",
                previous.display()
            );
        }
        Ok(Reply::metadata(
            json!({"ok":true,"revision":self.recovery_revision()}),
        ))
    }

    pub(super) fn restore_recovery_checkpoint(&mut self, args: &Value) -> Result<Reply, String> {
        check_keys(args, &["path"])?;
        // Validate everything in a candidate first. A corrupt checkpoint cannot
        // partially replace the live session or modify the recovery file.
        let mut candidate = Session::new(self.root.clone());
        candidate.control = self.control.clone();
        candidate.revision = self.revision;
        candidate.open_native_project(path(args)?)?;
        let file = &candidate.project.archive.as_ref().unwrap().file;
        let metadata = read_json_dataset(file, "native_recovery")?;
        if ![json!(1), json!(2)].contains(&metadata["version"])
            || !metadata["ui"].is_object()
            || metadata["ui"].to_string().len() > 256 * 1024
        {
            return Err("Unsupported or corrupt native recovery metadata.".into());
        }
        let project_path: Option<PathBuf> =
            serde_json::from_value(metadata["project_path"].clone())
                .map_err(|e| format!("Invalid recovered project identity: {e}"))?;
        let mut missing = std::collections::BTreeSet::new();
        for doc in candidate.project.document["configurations"]
            .as_array()
            .unwrap()
        {
            if let Some(source) = doc["img"]["filename"].as_str().filter(|p| !p.is_empty())
                && !Path::new(source).is_file()
            {
                missing.insert(source.to_owned());
            }
        }
        // Read the SC session before the swap; restoring it never fails.
        let scxrd = file.link_exists(SCXRD_ESSENTIALS).then(|| {
            (
                scxrd_bytes(file, SCXRD_ESSENTIALS),
                scxrd_bytes(file, SCXRD_PRODUCTS),
            )
        });
        candidate.project.path = project_path;
        let history_notice = recovery_history::restore(&mut candidate, path(args)?, &metadata)?;
        // The normal project loader leaves file watchers and automatic exports
        // disarmed. Restoring a checkpoint must not replay old acquisitions.
        self.control.check()?;
        std::mem::swap(&mut self.project, &mut candidate.project);
        self.restore_checkpoint(candidate.checkpoint());
        #[cfg(feature = "dioptrin")]
        std::mem::swap(&mut self.engine, &mut candidate.engine);
        self.scxrd_undo.clear();
        self.scxrd_redo.clear();
        let mut scxrd_notice = None;
        self.scxrd = match scxrd {
            Some((essentials, products)) => {
                let (crystal, summary) = single_crystal::Crystal::restore(
                    essentials,
                    products,
                    SCXRD_GENERATION,
                    single_crystal::Transfer::Recovery,
                    &self.control,
                );
                scxrd_notice = summary;
                crystal
            }
            None => Default::default(),
        };
        let mut reply = self.configuration_reply();
        reply.result["recoveryUi"] = metadata["ui"].clone();
        reply.result["missingSources"] = json!(missing);
        let notices: Vec<_> = history_notice.into_iter().chain(scxrd_notice).collect();
        reply.result["recoveryNotice"] = json!((!notices.is_empty()).then(|| notices.join("\n\n")));
        Ok(reply)
    }
}
