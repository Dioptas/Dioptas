//! Automatic recovery is an owned native project, never the user's project.
use super::*;

impl Session {
    pub(super) fn save_recovery_checkpoint(&self, args: &Value) -> Result<Reply, String> {
        check_keys(args, &["path", "ui"])?;
        let ui = args.get("ui").cloned().unwrap_or(json!({}));
        if !ui.is_object() || ui.to_string().len() > 256 * 1024 {
            return Err("Recovery display settings must be an object smaller than 256 KiB.".into());
        }
        let metadata = json!({"version":1,"project_path":self.project.path,"ui":ui});
        // Metadata and science publish together through the same atomic writer.
        self.save_native_project_with_recovery(path(args)?, Some(&metadata))?;
        Ok(Reply::metadata(json!({"ok":true,"revision":self.revision})))
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
        if metadata["version"] != 1
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
        candidate.project.path = project_path;
        // The normal project loader leaves file watchers and automatic exports
        // disarmed. Restoring a checkpoint must not replay old acquisitions.
        self.control.check()?;
        std::mem::swap(&mut self.project, &mut candidate.project);
        self.restore_checkpoint(candidate.checkpoint());
        #[cfg(feature = "dioptrin")]
        std::mem::swap(&mut self.engine, &mut candidate.engine);
        let mut reply = self.configuration_reply();
        reply.result["recoveryUi"] = metadata["ui"].clone();
        reply.result["missingSources"] = json!(missing);
        Ok(reply)
    }
}
