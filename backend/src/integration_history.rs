//! Current-image integration edits share chronological Undo/Redo with fits.
use super::*;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
pub(super) struct Snapshot {
    phase_bytes: usize,
    settings: Settings,
    processing: crate::processing::Processing,
    patterns: crate::pattern::Patterns,
    phases: crate::phases::Phases,
}
impl Snapshot {
    fn estimated_bytes(&self) -> usize {
        self.processing.estimated_bytes()
            + self.phase_bytes
            + self
                .patterns
                .overlays
                .iter()
                .map(|o| o.data.x.len() * 16)
                .sum::<usize>()
            + 4096
    }
    fn same(&self, other: &Self) -> bool {
        self.settings == other.settings
            && self.processing == other.processing
            && self.patterns == other.patterns
            && self.phases == other.phases
    }
}
#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Entry {
    before: Snapshot,
    after: Snapshot,
    sequence: u64,
    group: Option<String>,
    calculate: bool,
    phases_changed: bool,
    overlays_changed: bool,
}
#[derive(Default, Clone, serde::Serialize, serde::Deserialize)]
pub(super) struct IntegrationHistory {
    #[serde(with = "crate::history_transfer::vec_arc")]
    undo: Vec<Arc<Entry>>,
    #[serde(with = "crate::history_transfer::vec_arc")]
    redo: Vec<Arc<Entry>>,
}
pub(super) fn is_edit(action: &str) -> bool {
    matches!(
        action,
        "integration_overlay"
            | "batch_waterfall"
            | "integration_phase"
            | "integration_phase_list"
            | "integration_background"
            | "integration_clear_background"
            | "integration_settings"
            | "integration_roi"
            | "integration_image_background"
            | "integration_transfer"
            | "integration_flat_field"
            | "integration_correction"
            | "settings"
    )
}
impl IntegrationHistory {
    pub(super) fn recovery_count(&self) -> usize {
        self.undo.len() + self.redo.len()
    }
    pub(super) fn disarm_recovery(&mut self, revision: u64) -> Result<(), String> {
        if self.recovery_count() > 256
            || self
                .undo
                .iter()
                .chain(&self.redo)
                .any(|e| e.sequence > revision)
        {
            return Err("Invalid recovered integration history sequence.".into());
        }
        for entry in self.undo.iter_mut().chain(&mut self.redo) {
            let entry = Arc::make_mut(entry);
            entry.before.settings.auto_save = false;
            entry.after.settings.auto_save = false;
        }
        self.break_group();
        Ok(())
    }
    pub(super) fn trim_recovery(&mut self, calibration: &mut History) {
        // Preserve contiguous nearest Undo/Redo operations in the common
        // calibration/integration timeline rather than leaving sequence gaps.
        for _ in 0..(self.undo.len() + calibration.undo.len()).div_ceil(2) {
            if self
                .undo
                .first()
                .is_some_and(|e| calibration.undo.first().is_none_or(|c| e.sequence <= c.3))
            {
                self.undo.remove(0);
            } else {
                calibration.undo.remove(0);
            }
        }
        for _ in 0..(self.redo.len() + calibration.redo.len()).div_ceil(2) {
            if self
                .redo
                .first()
                .is_some_and(|e| calibration.redo.first().is_none_or(|c| e.sequence >= c.3))
            {
                self.redo.remove(0);
            } else {
                calibration.redo.remove(0);
            }
        }
    }
    pub fn forget_shared_edits(&mut self) {
        self.undo
            .retain(|e| !e.phases_changed && !e.overlays_changed);
        self.redo
            .retain(|e| !e.phases_changed && !e.overlays_changed);
    }
    pub fn can_undo(&self) -> bool {
        !self.undo.is_empty()
    }
    pub fn can_redo(&self) -> bool {
        !self.redo.is_empty()
    }
    pub fn clear_redo(&mut self) {
        self.redo.clear();
    }
    pub fn break_group(&mut self) {
        if let Some(last) = self.undo.last_mut() {
            let mut entry = (**last).clone();
            entry.group = None;
            *last = Arc::new(entry);
        }
    }
    pub fn record(
        &mut self,
        before: Snapshot,
        after: Snapshot,
        action: &str,
        args: &Value,
        sequence: u64,
        calibration_sequence: u64,
    ) -> bool {
        if before.same(&after) {
            return false;
        }
        let group = if action == "integration_overlay"
            && args["operation"] == "update"
            && args.as_object().is_some_and(|a| a.len() == 3)
        {
            args.as_object()
                .unwrap()
                .keys()
                .find(|k| *k == "scale" || *k == "offset")
                .map(|field| {
                    let identity = args.get("uid").unwrap_or(&args["index"]);
                    format!("overlay:{identity}:{field}")
                })
        } else {
            None
        };
        let calculate = matches!(
            action,
            "settings"
                | "integration_settings"
                | "integration_roi"
                | "integration_image_background"
                | "integration_transfer"
                | "integration_flat_field"
                | "integration_correction"
        );
        let before = if group.is_some()
            && self.redo.is_empty()
            && self
                .undo
                .last()
                .is_some_and(|e| e.group == group && e.sequence > calibration_sequence)
        {
            self.undo.pop().unwrap().before.clone()
        } else {
            before
        };
        self.redo.clear();
        let phases_changed = before.phases != after.phases;
        let overlays_changed = before.patterns.overlays != after.patterns.overlays
            || before.patterns.separation != after.patterns.separation;
        self.undo.push(Arc::new(Entry {
            phases_changed,
            overlays_changed,
            before,
            after,
            sequence,
            group,
            calculate,
        }));
        while self.undo.len() > 1
            && (self.undo.len() > 128
                || self
                    .undo
                    .iter()
                    .map(|e| e.before.estimated_bytes() + e.after.estimated_bytes())
                    .sum::<usize>()
                    > 128 * 1024 * 1024)
        {
            self.undo.remove(0);
        }
        true
    }
}
impl Session {
    pub(super) fn integration_snapshot(&self) -> Snapshot {
        let mut patterns = self.patterns.clone();
        patterns.raw = None;
        patterns.extracted = None;
        Snapshot {
            phase_bytes: self
                .phases
                .items
                .iter()
                .map(|p| p.document.to_string().len() + p.reflections.len() * 40 + 4096)
                .sum(),
            settings: self.settings.clone(),
            processing: self.processing.clone(),
            patterns,
            phases: self.phases.clone(),
        }
    }
    pub(super) fn integration_history_command(
        &mut self,
        action: &str,
    ) -> Result<Option<Reply>, String> {
        let redo = match action {
            "undo_calibration" => false,
            "redo_calibration" => true,
            _ => return Ok(None),
        };
        let integration = if redo {
            self.integration_history.redo.last()
        } else {
            self.integration_history.undo.last()
        };
        let Some(entry) = integration else {
            return Ok(None);
        };
        let calibration = if redo {
            self.calibration_history.redo.last()
        } else {
            self.calibration_history.undo.last()
        };
        if calibration.is_some_and(|c| {
            if redo {
                c.3 < entry.sequence
            } else {
                c.3 > entry.sequence
            }
        }) {
            return Ok(None);
        }
        let entry = if redo {
            let e = self.integration_history.redo.pop().unwrap();
            self.integration_history.undo.push(e.clone());
            e
        } else {
            let e = self.integration_history.undo.pop().unwrap();
            self.integration_history.redo.push(e.clone());
            e
        };
        let mut unit_only_settings = entry.before.settings.clone();
        unit_only_settings.unit = entry.after.settings.unit.clone();
        let unit_only = unit_only_settings == entry.after.settings
            && entry.before.processing == entry.after.processing;
        let snap = if redo {
            entry.after.clone()
        } else {
            entry.before.clone()
        };
        let raw = self.patterns.raw.clone();
        let name = self.patterns.name.clone();
        let path = self.patterns.path.clone();
        let unit = self.patterns.unit.clone();
        let imported = self.patterns.imported;
        if entry.calculate {
            self.settings = snap.settings;
            self.processing = snap.processing;
        }
        let global_patterns = self.patterns.clone();
        self.patterns = snap.patterns;
        if !entry.overlays_changed {
            self.patterns.restore_global(&global_patterns);
        } else {
            self.patterns.retain_counter(&global_patterns);
        }
        if entry.phases_changed {
            let next_uid = self.phases.next_uid.max(snap.phases.next_uid);
            self.phases = snap.phases;
            self.phases.next_uid = next_uid;
        }
        self.patterns.raw = raw;
        self.patterns.name = name;
        self.patterns.path = path;
        self.patterns.unit = unit;
        self.patterns.imported = imported;
        if entry.calculate && self.image.is_some() {
            if unit_only {
                self.calculate_preserving_cake()?;
            } else {
                self.calculate(false)?;
            }
        } else {
            self.rebuild_pattern()?;
        }
        self.revision += 1;
        let mut reply = self.snapshot(false);
        if !entry.calculate {
            reply.buffers.clear();
            for key in ["mask", "cake", "rings", "linked", "batch", "map"] {
                reply.result.as_object_mut().unwrap().remove(key);
            }
            reply.result["patternOnly"] = json!(true);
        }
        Ok(Some(reply))
    }
}
