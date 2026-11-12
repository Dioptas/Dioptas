//! Source-local navigation, stable incoming-file polling, and atomic exports.
use super::*;
use crate::pattern::Curve;
use std::{
    collections::{BTreeMap, BTreeSet, VecDeque},
    time::{Duration, SystemTime},
};
type FileStamp = (u64, SystemTime);
const POLL_MAX_IMAGES: usize = 8;
// Checked between frames: one decoder/integration call remains cooperative.
const POLL_TIME_BUDGET: Duration = Duration::from_millis(50);

struct IncomingImage {
    path: PathBuf,
    stamp: Option<FileStamp>,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
pub(super) struct Files {
    pub image_directory: String,
    pub output_directory: String,
    pub image_mode: String,
    pub auto_process: bool,
    pub auto_error: String,
    known: Arc<BTreeSet<PathBuf>>,
    pending: Arc<BTreeMap<PathBuf, FileStamp>>,
    queue: Arc<VecDeque<PathBuf>>,
    // A failed acquisition is retried only after its source changes. Older
    // development checkpoints predate this field.
    #[serde(default)]
    failed: Arc<BTreeMap<PathBuf, FileStamp>>,
    #[serde(default)]
    retry: Arc<BTreeMap<PathBuf, Retry>>,
    #[serde(default)]
    generated: Arc<BTreeMap<PathBuf, crate::image::FileIdentity>>,
    #[cfg(test)]
    #[serde(skip)]
    stamp_reads: std::cell::Cell<usize>,
    #[cfg(test)]
    #[serde(skip)]
    before_combination: Option<fn(&Control, &Path)>,
}
#[derive(Clone, serde::Serialize, serde::Deserialize)]
enum RetryReason {
    WaitingSource,
    Output,
}
#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Retry {
    stamp: Option<FileStamp>,
    reason: RetryReason,
    message: String,
}
impl Default for Files {
    fn default() -> Self {
        Self {
            image_directory: String::new(),
            output_directory: String::new(),
            image_mode: "number".into(),
            auto_process: false,
            auto_error: String::new(),
            known: Arc::default(),
            pending: Arc::default(),
            queue: Arc::default(),
            failed: Arc::default(),
            retry: Arc::default(),
            generated: Arc::default(),
            #[cfg(test)]
            stamp_reads: Default::default(),
            #[cfg(test)]
            before_combination: None,
        }
    }
}
impl Files {
    pub(super) fn stop_autoprocess(&mut self) {
        self.auto_process = false;
        self.auto_error.clear();
        self.queue = Arc::default();
        self.pending = Arc::default();
        self.failed = Arc::default();
        self.retry = Arc::default();
    }
}
pub(super) fn image_file(path: &Path) -> bool {
    let name = path
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();
    !name.starts_with('.')
        && [
            "tif",
            "tiff",
            "edf",
            "edf.gz",
            "cbf",
            "cbf.gz",
            "h5",
            "hdf5",
            "nxs",
            "npy",
            "npz",
            "img",
            "mccd",
            "mar3450",
            "mar345",
            "kcd",
            "mpa",
            "sfrm",
            "osc",
            "gfrm",
            "cor",
            "spe",
            "dat",
            "esperanto",
        ]
        .iter()
        .any(|e| name.ends_with(&format!(".{e}")))
}
pub(super) fn numbered(path: &Path, step: i64) -> Option<PathBuf> {
    let name = path.file_name()?.to_str()?;
    let bytes = name.as_bytes();
    let mut end = bytes.len();
    while end > 0 {
        while end > 0 && !bytes[end - 1].is_ascii_digit() {
            end -= 1;
        }
        if end == 0 {
            break;
        }
        let mut start = end;
        while start > 0 && bytes[start - 1].is_ascii_digit() {
            start -= 1;
        }
        if let Ok(number) = name[start..end].parse::<i128>() {
            let number = number + step as i128;
            if number >= 0 {
                for digits in [
                    format!("{number:0width$}", width = end - start),
                    number.to_string(),
                ] {
                    let target = path.with_file_name(format!(
                        "{}{}{}",
                        &name[..start],
                        digits,
                        &name[end..]
                    ));
                    if target.is_file() {
                        return Some(target);
                    }
                }
            }
        }
        end = start;
    }
    None
}
pub(super) fn neighbor(path: &Path, mode: &str, step: i64) -> Result<Option<PathBuf>, String> {
    if mode != "time" {
        return Ok(numbered(path, step));
    }
    let mut entries = Vec::new();
    // Resolve the directory once. Regular entries then already have canonical
    // parents; resolving every earlier filename made late-acquisition browsing
    // pay thousands of redundant filesystem lookups on each click.
    let directory = path
        .parent()
        .unwrap_or(Path::new("."))
        .canonicalize()
        .map_err(|e| e.to_string())?;
    for entry in std::fs::read_dir(directory).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let p = entry.path();
        if !p
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .starts_with('.')
            && p.extension() == path.extension()
        {
            let Ok(m) = std::fs::metadata(&p) else {
                continue;
            };
            if !m.is_file() {
                continue;
            }
            entries.push((
                m.created()
                    .or_else(|_| m.modified())
                    .map_err(|e| e.to_string())?,
                p,
                entry.file_type().map_err(|e| e.to_string())?.is_symlink(),
            ));
        }
    }
    entries.sort();
    let current = path.canonicalize().map_err(|e| e.to_string())?;
    let i = entries
        .iter()
        .position(|(_, p, symlink)| {
            p == &current || (*symlink && p.canonicalize().ok().as_ref() == Some(&current))
        })
        .ok_or("Current file is not in its source directory.")?;
    let target = i as i64 + step;
    if target < 0 || target >= entries.len() as i64 {
        return Ok(None);
    }
    Ok(Some(entries[target as usize].1.clone()))
}

impl Files {
    fn stamp(&self, path: &Path) -> Option<FileStamp> {
        #[cfg(test)]
        self.stamp_reads.set(self.stamp_reads.get() + 1);
        let m = std::fs::metadata(path).ok()?;
        if !m.is_file() {
            return None;
        }
        Some((m.len(), m.modified().ok()?))
    }
    fn scan(&self) -> Result<BTreeSet<PathBuf>, String> {
        let mut paths = BTreeSet::new();
        for entry in std::fs::read_dir(&self.image_directory).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let p = entry.path();
            if !image_file(&p) {
                continue;
            }
            if self.generated.get(&p).is_some_and(|identity| {
                crate::image::FileIdentity::read(&p).ok().as_ref() == Some(identity)
            }) {
                continue;
            }
            // Known names are already admitted; avoid even file_type(), which
            // can stat on network filesystems without directory-entry types.
            if self.known.contains(&p)
                && !self.failed.contains_key(&p)
                && !self.retry.contains_key(&p)
            {
                paths.insert(p);
            } else {
                let kind = entry.file_type().map_err(|e| e.to_string())?;
                if kind.is_file() || (kind.is_symlink() && self.stamp(&p).is_some()) {
                    paths.insert(p);
                }
            }
            if paths.len() > 1_000_000 {
                return Err("Incoming directory exceeds one million image names.".into());
            }
        }
        Ok(paths)
    }
    pub fn baseline(&mut self) -> Result<(), String> {
        self.known = Arc::new(self.scan()?);
        self.pending = Arc::default();
        self.queue = Arc::default();
        self.failed = Arc::default();
        self.retry = Arc::default();
        Ok(())
    }
    fn poll(&mut self) -> Result<(), String> {
        let paths = self.scan()?;
        // A detector may replace a previously generated .dat pathname. Only
        // the file identity we wrote is excluded, never the extension.
        let replaced_outputs: Vec<_> = self
            .generated
            .keys()
            .filter(|p| paths.contains(*p))
            .cloned()
            .collect();
        for path in replaced_outputs {
            Arc::make_mut(&mut self.generated).remove(&path);
            Arc::make_mut(&mut self.known).remove(&path);
        }
        // Do not detach a shared checkpoint collection if it has not changed.
        if self.known.iter().any(|p| !paths.contains(p)) {
            Arc::make_mut(&mut self.known).retain(|p| paths.contains(p));
        }
        if self.pending.keys().any(|p| !paths.contains(p)) {
            Arc::make_mut(&mut self.pending).retain(|p, _| paths.contains(p));
        }
        if self.failed.keys().any(|p| !paths.contains(p)) {
            Arc::make_mut(&mut self.failed).retain(|p, _| paths.contains(p));
        }
        if self.retry.keys().any(|p| !paths.contains(p)) {
            Arc::make_mut(&mut self.retry).retain(|p, _| paths.contains(p));
        }
        let changed: Vec<_> = self
            .failed
            .iter()
            .filter(|(p, previous)| self.stamp(p).as_ref() != Some(previous))
            .map(|(p, _)| p.clone())
            .collect();
        for path in changed {
            Arc::make_mut(&mut self.failed).remove(&path);
            Arc::make_mut(&mut self.known).remove(&path);
            Arc::make_mut(&mut self.pending).remove(&path);
        }
        let mut ready = Vec::new();
        for path in paths.difference(&self.known) {
            let Some(stamp) = self.stamp(path) else {
                continue;
            };
            if stamp.0 > 0 && self.pending.get(path) == Some(&stamp) {
                ready.push((stamp.1, path.clone()));
            } else if self.pending.get(path) != Some(&stamp) {
                Arc::make_mut(&mut self.pending).insert(path.clone(), stamp);
            }
        }
        // A repaired output or newly available HDF5 companion does not have to
        // modify the master/source. Retry at most once per bounded poll, without
        // blocking later acquisitions. Opaque corrupt sources still require a
        // changed source fingerprint before readmission.
        for (path, retry) in self.retry.iter() {
            if !self.queue.contains(path)
                && let Some(stamp) = self.stamp(path)
            {
                Arc::make_mut(&mut self.pending).insert(path.clone(), stamp);
                ready.push((retry.stamp.unwrap_or(stamp).1, path.clone()));
            }
        }
        ready.sort();
        for (_, path) in ready {
            Arc::make_mut(&mut self.known).insert(path.clone());
            Arc::make_mut(&mut self.queue).push_back(path);
        }
        Ok(())
    }
    fn next(&mut self) -> Option<IncomingImage> {
        let path = Arc::make_mut(&mut self.queue).pop_front()?;
        let stamp = Arc::make_mut(&mut self.pending)
            .remove(&path)
            .or_else(|| self.stamp(&path));
        Some(IncomingImage { path, stamp })
    }
    fn retry(&mut self, incoming: &IncomingImage, reason: RetryReason, error: String) {
        let message = format!(
            "{}: {error}",
            incoming
                .path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
        );
        self.auto_error = message.clone();
        Arc::make_mut(&mut self.retry).insert(
            incoming.path.clone(),
            Retry {
                stamp: incoming.stamp,
                reason,
                message,
            },
        );
    }
    fn output_written(&mut self, path: &Path) {
        // Only acquisition-compatible names can be rediscovered by this scanner.
        if !image_file(path) {
            return;
        }
        if let Ok(path) = path.canonicalize()
            && let Ok(identity) = crate::image::FileIdentity::read(&path)
        {
            Arc::make_mut(&mut self.generated).insert(path, identity);
        }
    }
}

fn directory(args: &Value) -> Result<String, String> {
    let p = path(args)?.canonicalize().map_err(|e| e.to_string())?;
    if !p.is_dir() {
        return Err("Choose an existing directory.".into());
    }
    Ok(p.to_string_lossy().into_owned())
}
pub(super) fn export_curve(
    path: &Path,
    curve: &Curve,
    unit: &str,
    wavelength: f64,
) -> Result<(), String> {
    atomic_write(path, &curve_bytes(path, curve, unit, wavelength)?)
}
/// GSAS CONS stores angular coordinates in centidegrees. Keep every exporter
/// on the same physical unit contract, including Batch and automatic saves.
pub(super) fn export_unit<'a>(extension: &str, unit: &'a str) -> &'a str {
    if extension == "fxye" && unit == "d_A" {
        "2th_deg"
    } else {
        unit
    }
}
pub(super) fn curve_bytes(
    path: &Path,
    curve: &Curve,
    unit: &str,
    wavelength: f64,
) -> Result<Vec<u8>, String> {
    let extension = path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("xy")
        .to_ascii_lowercase();
    if !["xy", "xye", "chi", "dat", "fxye"].contains(&extension.as_str()) {
        return Err("Use XY, XYE, CHI, DAT or FXYE format.".into());
    }
    if ["xye", "fxye"].contains(&extension.as_str()) && curve.sigma.is_none() {
        return Err("Enable Calculate Poisson errors and integrate before saving errors.".into());
    }
    if curve.x.is_empty()
        || curve.x.len() != curve.y.len()
        || curve
            .sigma
            .as_ref()
            .is_some_and(|s| s.len() != curve.x.len())
    {
        return Err("Pattern export needs matching, non-empty sample arrays.".into());
    }
    let requested_unit = unit;
    let unit = export_unit(&extension, unit);
    let curve = if unit != requested_unit {
        if !wavelength.is_finite() || wavelength <= 0.0 {
            return Err("Angular FXYE export needs a positive, finite wavelength.".into());
        }
        let x: Vec<_> = curve
            .x
            .iter()
            .map(|&x| crate::pattern::convert_coordinate(x, requested_unit, unit, wavelength))
            .collect();
        if x.iter().any(|x| !x.is_finite()) {
            return Err(
                "Pattern coordinates cannot be converted for FXYE at this wavelength.".into(),
            );
        }
        std::borrow::Cow::Owned(Curve {
            x: Arc::new(x),
            ..curve.clone()
        })
    } else {
        std::borrow::Cow::Borrowed(curve)
    };
    let mut text = if extension == "chi" {
        format!("{}\n{unit}\n\n       {}\n", path.display(), curve.x.len())
    } else {
        format!(
            "# Dioptas native backend\n# wavelength_m: {wavelength:.17e}\n# {unit}\tI{}\n",
            if ["xye", "fxye"].contains(&extension.as_str()) {
                "\tsigma"
            } else {
                ""
            }
        )
    };
    let factor = if extension == "fxye" && unit != "q_A^-1" {
        100.0
    } else {
        1.0
    };
    if extension == "fxye" {
        let step = if curve.x.len() > 1 {
            curve.x[1] - curve.x[0]
        } else {
            0.0
        };
        text = format!(
            "Generated file {} using DIOPTAS\n{}BANK 1 {} {} {} {:.7e} {:.7e} {:.7e} 0.0 FXYE\n",
            path.display(),
            text,
            curve.x.len(),
            curve.x.len(),
            if unit == "q_A^-1" { "CONQ" } else { "CONS" },
            factor * curve.x[0],
            factor * step,
            wavelength * 1e10
        );
    }
    for (i, (&x, &y)) in curve.x.iter().zip(curve.y.iter()).enumerate() {
        if !x.is_finite() || !y.is_finite() {
            return Err("Pattern contains nonfinite samples; export was not replaced.".into());
        }
        if ["xye", "fxye"].contains(&extension.as_str()) {
            let sigma = curve.sigma.as_ref().unwrap()[i];
            if !sigma.is_finite() {
                return Err("Pattern errors are not finite.".into());
            }
            text.push_str(&format!("{:.17e}\t{y:.17e}\t{sigma:.17e}\n", factor * x));
        } else {
            text.push_str(&format!("{x:.17e}\t{y:.17e}\n"));
        }
    }
    Ok(text.into_bytes())
}
pub(crate) fn atomic_render(
    path: &Path,
    write: impl FnOnce(&mut std::fs::File) -> Result<(), String>,
) -> Result<(), String> {
    let mut temporary = crate::output::StagedOutput::new(path)?;
    write(temporary.as_file_mut())?;
    temporary.commit(path)
}
impl Session {
    fn poll_acquisition(&mut self) -> Result<Reply, String> {
        if !self.files.auto_process {
            return Ok(Reply::success());
        }
        self.files.poll()?;
        let started = std::time::Instant::now();
        let mut changed = false;
        let mut cancelled = false;
        for attempted in 0..POLL_MAX_IMAGES {
            if attempted > 0 && started.elapsed() >= POLL_TIME_BUDGET {
                break;
            }
            if self.control.check().is_err() {
                cancelled = true;
                break;
            }
            let Some(incoming) = self.files.next() else {
                break;
            };
            let checkpoint = self.checkpoint();
            self.control.publish(json!({"running":true,"current":attempted,"total":(attempted + 1 + self.files.queue.len()).min(POLL_MAX_IMAGES),"label":"Processing incoming images"}));
            let mut options = self
                .image
                .as_ref()
                .map(|i| i.options.clone())
                .unwrap_or(json!({}));
            options["path"] = json!(incoming.path);
            options["frame"] = json!(0);
            // Avoid treating output-volume failures as unreadable source data.
            let auto = self.settings.auto_save;
            self.settings.auto_save = false;
            let opened = self.dispatch("open_image", &options).and_then(|mut reply| {
                #[cfg(test)]
                if let Some(observer) = self.files.before_combination {
                    observer(&self.control, &incoming.path);
                }
                self.control.check()?;
                // Finish combined products before this source/output transaction
                // commits, so cancellation can retain a complete earlier prefix.
                self.update_combination_reply(&mut reply, "open_image", &options)?;
                Ok(reply)
            });
            self.settings.auto_save = auto;
            match opened {
                Ok(reply)
                    if reply.result["imageChange"].is_object()
                        || reply.result["calibrationChange"].is_object() =>
                {
                    self.restore_checkpoint(checkpoint);
                    self.files.stop_autoprocess();
                    self.files.auto_error = format!(
                        "{}: detector dimensions changed. Autoprocess stopped; open the image manually to reset calibration.",
                        incoming
                            .path
                            .file_name()
                            .unwrap_or_default()
                            .to_string_lossy()
                    );
                    return Ok(self.snapshot(false));
                }
                Ok(reply) if reply.result["hdf5SourceRequest"].is_object() => {
                    self.restore_checkpoint(checkpoint);
                    self.files.retry(
                        &incoming,
                        RetryReason::WaitingSource,
                        "Waiting for declared HDF5 companion sources; retrying automatically."
                            .into(),
                    );
                    changed = true;
                }
                Ok(_) => {
                    #[cfg(feature = "dioptrin")]
                    if let Err(error) = self.auto_save() {
                        // A previous format may already have been written. Its
                        // exact output fingerprint must survive source rollback.
                        let generated = self.files.generated.clone();
                        self.restore_checkpoint(checkpoint);
                        self.files.generated = generated;
                        self.files.retry(
                            &incoming,
                            RetryReason::Output,
                            format!("Automatic output failed; retrying: {error}"),
                        );
                        changed = true;
                        continue;
                    }
                    Arc::make_mut(&mut self.files.retry).remove(&incoming.path);
                    Arc::make_mut(&mut self.files.failed).remove(&incoming.path);
                    self.files.auto_error = self
                        .files
                        .retry
                        .values()
                        .next()
                        .map(|r| r.message.clone())
                        .unwrap_or_default();
                    changed = true;
                }
                Err(error) => {
                    self.restore_checkpoint(checkpoint);
                    if self.control.check().is_err() {
                        Arc::make_mut(&mut self.files.queue).push_front(incoming.path.clone());
                        if let Some(stamp) = incoming.stamp {
                            Arc::make_mut(&mut self.files.pending).insert(incoming.path, stamp);
                        }
                        cancelled = true;
                        break;
                    }
                    // A readable HDF5 container can still reference an absent or
                    // incomplete external file. Its master need never change.
                    if hdf5::File::open(&incoming.path).is_ok()
                        && Image::open(&incoming.path, &options).is_err()
                    {
                        self.files.retry(
                            &incoming,
                            RetryReason::WaitingSource,
                            format!("Waiting for source data; retrying: {error}"),
                        );
                    } else {
                        if let Some(stamp) = incoming.stamp {
                            Arc::make_mut(&mut self.files.failed)
                                .insert(incoming.path.clone(), stamp);
                        }
                        self.files.auto_error = format!(
                            "{}: {error}",
                            incoming
                                .path
                                .file_name()
                                .unwrap_or_default()
                                .to_string_lossy()
                        );
                    }
                    changed = true;
                }
            }
        }
        if !changed && !cancelled {
            return Ok(Reply::success());
        }
        let mut reply = self.snapshot(true);
        if cancelled {
            reply.result["cancelled"] = json!(true);
        }
        Ok(reply)
    }
    pub(super) fn file_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        match action {
            "integration_output_directory" => self.files.output_directory = directory(args)?,
            "integration_image_directory" => {
                let target = directory(args)?;
                if self.files.image_directory != target {
                    self.files.image_directory = target;
                    if self.files.auto_process {
                        self.files.baseline()?;
                    }
                }
            }
            "integration_autoprocess" => {
                let enabled = boolean(&args["enabled"], "Autoprocess")?;
                let mut directory_changed = false;
                if let Some(dir) = args.get("directory") {
                    let target = directory(&json!({"path":dir}))?;
                    directory_changed = target != self.files.image_directory;
                    self.files.image_directory = target;
                }
                if enabled && (!self.files.auto_process || directory_changed) {
                    self.files.baseline()?;
                }
                self.files.auto_process = enabled;
                self.files.auto_error.clear();
            }
            "integration_autoprocess_poll" => return self.poll_acquisition().map(Some),
            "integration_autocreate" => {
                self.settings.auto_save = boolean(&args["enabled"], "Auto save")?;
                if let Some(dir) = args.get("directory") {
                    self.files.output_directory = directory(&json!({"path":dir}))?;
                }
            }
            "integration_navigation" => {
                if args.get("step").is_some() && args.get("direction").is_none() {
                    return Err("Choose a relative frame direction for the step.".into());
                }
                if let Some(mode) = args.get("mode") {
                    self.files.image_mode = mode
                        .as_str()
                        .filter(|s| ["number", "time"].contains(s))
                        .ok_or("Choose filename number or creation time navigation.")?
                        .into();
                }
                if args.get("frame").is_some() || args.get("direction").is_some() {
                    let image = self.image.as_ref().ok_or("Open an image first.")?;
                    let frame = if let Some(frame) = args.get("frame") {
                        if args.get("direction").is_some() || args.get("step").is_some() {
                            return Err("Choose a frame position or a relative frame step.".into());
                        }
                        integer(frame, "Frame", 1, image.frames)?
                    } else {
                        let direction = args["direction"]
                            .as_i64()
                            .filter(|v| [-1, 1].contains(v))
                            .ok_or("Frame direction must be -1 or 1.")?;
                        let step = args
                            .get("step")
                            .map(|v| integer(v, "Frame step", 1, 100_000))
                            .transpose()?
                            .unwrap_or(1);
                        // Resolve against the worker's current frame so queued clicks
                        // accumulate. Frame browsing never crosses into another file.
                        (image.frame as i64 + 1 + direction * step as i64)
                            .clamp(1, image.frames as i64) as usize
                    };
                    let direction = frame as i64 - 1 - image.frame as i64;
                    if direction == 0 {
                        return Ok(Some(self.snapshot(false)));
                    }
                    return Ok(Some(self.dispatch(
                        "next_image",
                        &json!({"direction":direction,"step":1,"defer_integration":args["defer_integration"].as_bool().unwrap_or(false)}),
                    )?));
                }
            }
            "integration_save_spottiness" => {
                if self.combination.patterns {
                    return Err("Azimuthal std is unavailable for combined patterns; disable Combine patterns first.".into());
                }
                let mut file = path(args)?.to_path_buf();
                if file.extension().is_none() {
                    file.set_extension("csv");
                }
                if !file
                    .extension()
                    .is_some_and(|e| e.eq_ignore_ascii_case("csv"))
                {
                    return Err("Save Spottiness requires a .csv file.".into());
                }
                let curve = self
                    .patterns
                    .raw
                    .as_ref()
                    .ok_or("Load or integrate a pattern first.")?;
                crate::spottiness::export(&file, curve, &self.patterns.unit, &self.control)?;
                return Ok(Some(Reply::metadata(json!({"ok":true,"savedPath":file}))));
            }
            "integration_save_pattern" | "export_pattern" | "integration_save_background" => {
                let mut file = path(args)?.to_path_buf();
                let figure_format = args["format"]
                    .as_str()
                    .filter(|format| ["png", "svg"].contains(format));
                if file.extension().is_none() {
                    file.set_extension(figure_format.unwrap_or("xy"));
                }
                if let Some(format) = figure_format
                    && file
                        .extension()
                        .and_then(|extension| extension.to_str())
                        .is_none_or(|extension| !extension.eq_ignore_ascii_case(format))
                {
                    return Err(format!(
                        "Choose a .{format} destination for this figure format."
                    ));
                }
                if action == "integration_save_pattern" {
                    match file
                        .extension()
                        .and_then(|s| s.to_str())
                        .map(str::to_ascii_lowercase)
                        .as_deref()
                    {
                        Some("png") => {
                            let dpi = args
                                .get("png_dpi")
                                .map(|value| {
                                    value
                                        .as_u64()
                                        .filter(|dpi| [150, 300, 600].contains(dpi))
                                        .ok_or("Choose 150, 300 or 600 dpi.")
                                })
                                .transpose()?;
                            save_png_with_resolution(&file, &args["png_data"], dpi)?;
                            return Ok(Some(Reply::metadata(json!({"ok":true,"savedPath":file}))));
                        }
                        Some("svg") => {
                            save_svg(&file, &args["svg_data"])?;
                            return Ok(Some(Reply::metadata(json!({"ok":true,"savedPath":file}))));
                        }
                        _ => {}
                    }
                }
                let curve = if action == "integration_save_background" {
                    self.patterns
                        .extracted
                        .clone()
                        .filter(|_| self.patterns.background.enabled)
                        .ok_or("Enable pattern background first.")?
                } else if self.combination.patterns {
                    Arc::new(Curve::from_json(
                        self.combination.pattern.as_deref().ok_or(
                            "Integrate the combined detectors before saving their pattern.",
                        )?,
                    )?)
                } else if args
                    .get("subtract_background")
                    .map(|v| boolean(v, "Subtract background"))
                    .transpose()?
                    .unwrap_or(false)
                {
                    Arc::new(Curve::from_json(
                        self.pattern
                            .as_deref()
                            .ok_or("Load or integrate a pattern first.")?,
                    )?)
                } else {
                    self.patterns
                        .raw
                        .clone()
                        .ok_or("Load or integrate a pattern first.")?
                };
                if action == "integration_save_background"
                    && file.extension().is_some_and(|s| s == "xye" || s == "fxye")
                {
                    return Err(
                        "Save background as XY, CHI or DAT; it has no propagated Poisson errors."
                            .into(),
                    );
                }
                export_curve(
                    &file,
                    &curve,
                    if self.combination.patterns && action != "integration_save_background" {
                        &self.settings.unit
                    } else {
                        &self.patterns.unit
                    },
                    self.settings.geometry.wavelength,
                )?;
                return Ok(Some(Reply::metadata(json!({"ok":true,"savedPath":file}))));
            }
            "integration_save_image" => {
                self.require_image()?;
                let source = args
                    .get("source")
                    .and_then(Value::as_str)
                    .unwrap_or("image");
                if source != "image" && source != "cake" {
                    return Err("Choose the detector image or cake to save.".into());
                }
                if source == "cake" {
                    self.ensure_cake()?;
                }
                let mut file = path(args)?.to_path_buf();
                if file.extension().is_none() {
                    file.set_extension("png");
                }
                let extension = file.extension().unwrap().to_string_lossy().to_lowercase();
                match extension.as_str() {
                    "png" => {
                        save_png(&file, &args["png_data"])?;
                    }
                    "tif" | "tiff" => {
                        let (data, shape) = if source == "image" {
                            (self.scientific_values(), self.image.as_ref().unwrap().shape)
                        } else {
                            (
                                self.displayed_cake_values().cloned().ok_or(
                                    "Integrate a calibrated image before saving its cake.",
                                )?,
                                [
                                    self.displayed_cake().unwrap().metadata["height"]
                                        .as_u64()
                                        .unwrap() as usize,
                                    self.displayed_cake().unwrap().metadata["width"]
                                        .as_u64()
                                        .unwrap() as usize,
                                ],
                            )
                        };
                        let pixels: Vec<i32> = (0..shape[0])
                            .rev()
                            .flat_map(|r| {
                                data[r * shape[1]..(r + 1) * shape[1]].iter().map(|&v| {
                                    if !v.is_finite() || !(-2147483648.0..2147483648.0).contains(&v)
                                    {
                                        i32::MIN
                                    } else {
                                        v as i32
                                    }
                                })
                            })
                            .collect();
                        atomic_render(&file, |out| {
                            let mut writer =
                                tiff::encoder::TiffEncoder::new(out).map_err(|e| e.to_string())?;
                            writer
                                .write_image::<tiff::encoder::colortype::GrayI32>(
                                    shape[1] as u32,
                                    shape[0] as u32,
                                    &pixels,
                                )
                                .map_err(|e| e.to_string())
                        })?;
                    }
                    "csv" | "txt" if source == "cake" => {
                        let cake = self
                            .displayed_cake()
                            .ok_or("Integrate a calibrated image before saving its cake.")?;
                        let data = self.displayed_cake_values().unwrap();
                        let w = cake.metadata["width"].as_u64().unwrap() as usize;
                        let h = cake.metadata["height"].as_u64().unwrap() as usize;
                        let rr = &cake.metadata["radialRange"];
                        let aa = &cake.metadata["azimuthRange"];
                        let point = |r: &Value, i: usize, n: usize| {
                            r[0].as_f64().unwrap()
                                + if n > 1 {
                                    i as f64 * (r[1].as_f64().unwrap() - r[0].as_f64().unwrap())
                                        / (n - 1) as f64
                                } else {
                                    0.0
                                }
                        };
                        let delimiter = if extension == "csv" { "," } else { " " };
                        let mut text = String::from("0");
                        for i in 0..w {
                            text.push_str(&format!("{delimiter}{:.3}", point(rr, i, w)));
                        }
                        text.push('\n');
                        for r in 0..h {
                            text.push_str(&format!("{:.2}", point(aa, r, h)));
                            for c in 0..w {
                                text.push_str(&format!("{delimiter}{:.0}", data[r * w + c]));
                            }
                            text.push('\n');
                        }
                        atomic_write(&file, text.as_bytes())?;
                    }
                    _ => {
                        return Err(
                            "Save an image as PNG or TIFF; cake data also supports TXT and CSV."
                                .into(),
                        );
                    }
                }
                return Ok(Some(Reply::metadata(json!({"ok":true,"savedPath":file}))));
            }
            _ => return Ok(None),
        }
        self.revision += 1;
        Ok(Some(self.snapshot(false)))
    }
    #[cfg(feature = "dioptrin")]
    pub(super) fn auto_save(&mut self) -> Result<(), String> {
        if !self.settings.auto_save || self.patterns.imported {
            return Ok(());
        }
        let Some(raw) = &self.patterns.raw else {
            return Ok(());
        };
        let directory = if self.files.output_directory.is_empty() {
            self.image
                .as_ref()
                .and_then(|i| i.path.parent())
                .unwrap_or(Path::new("."))
                .to_path_buf()
        } else {
            PathBuf::from(&self.files.output_directory)
        };
        if self.root.join("RESOURCE_MANIFEST.json").is_file()
            && directory
                .canonicalize()
                .map_err(|e| e.to_string())?
                .starts_with(self.root.canonicalize().map_err(|e| e.to_string())?)
        {
            return Err("Choose an output folder outside the application before automatically saving patterns from its bundled examples.".into());
        }
        for format in &self.settings.formats {
            let file = directory.join(format!("{}{}", self.patterns.name, format));
            let normalized = directory
                .canonicalize()
                .map_err(|e| e.to_string())?
                .join(file.file_name().unwrap());
            if self.image.as_ref().is_some_and(|i| {
                i.path == normalized || file.canonicalize().ok().as_ref() == Some(&i.path)
            }) || (self.files.known.contains(&normalized)
                && !self.files.generated.contains_key(&normalized))
            {
                return Err("Automatic output would replace the detector source; choose another output directory.".into());
            }
            export_curve(
                &file,
                raw,
                &self.patterns.unit,
                self.settings.geometry.wavelength,
            )?;
            self.files.output_written(&file);
            if self.patterns.background.enabled || self.patterns.background_uid.is_some() {
                let sub = directory.join("bkg_subtracted");
                std::fs::create_dir_all(&sub).map_err(|e| e.to_string())?;
                let displayed = Curve::from_json(self.pattern.as_deref().unwrap())?;
                let sub_file = sub.join(format!("{}{}", self.patterns.name, format));
                export_curve(
                    &sub_file,
                    &displayed,
                    &self.patterns.unit,
                    self.settings.geometry.wavelength,
                )?;
                self.files.output_written(&sub_file);
            }
        }
        Ok(())
    }
}

pub(super) fn save_png(file: &Path, value: &Value) -> Result<(), String> {
    save_png_with_resolution(file, value, None)
}

fn save_png_with_resolution(file: &Path, value: &Value, dpi: Option<u64>) -> Result<(), String> {
    use base64::Engine;
    let encoded = value
        .as_str()
        .ok_or("Save PNG from the image toolbar to include its display settings.")?;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(encoded)
        .map_err(|e| e.to_string())?;
    let mut decoder = png::Decoder::new(std::io::Cursor::new(&bytes));
    decoder.set_limits(png::Limits {
        bytes: 256 * 1024 * 1024,
    });
    let mut reader = decoder.read_info().map_err(|e| e.to_string())?;
    let length = reader
        .output_buffer_size()
        .filter(|&n| n <= 256 * 1024 * 1024)
        .ok_or("PNG exceeds the bounded image size.")?;
    let mut output = vec![0; length];
    let frame = reader.next_frame(&mut output).map_err(|e| e.to_string())?;
    reader.finish().map_err(|e| e.to_string())?;
    if let Some(dpi) = dpi {
        let mut figure = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut figure, frame.width, frame.height);
            encoder.set_color(frame.color_type);
            encoder.set_depth(frame.bit_depth);
            let pixels_per_meter = (dpi as f64 / 0.0254).round() as u32;
            encoder.set_pixel_dims(Some(png::PixelDimensions {
                xppu: pixels_per_meter,
                yppu: pixels_per_meter,
                unit: png::Unit::Meter,
            }));
            encoder
                .write_header()
                .and_then(|mut writer| writer.write_image_data(&output[..frame.buffer_size()]))
                .map_err(|e| e.to_string())?;
        }
        return atomic_write(file, &figure);
    }
    atomic_write(file, &bytes)
}

/// Publish only a complete SVG generated by the display renderer.
fn save_svg(file: &Path, value: &Value) -> Result<(), String> {
    let svg = value
        .as_str()
        .ok_or("Save SVG from the pattern toolbar to include its display settings.")?;
    if svg.len() > 64 * 1024 * 1024 {
        return Err("SVG exceeds the bounded figure size.".into());
    }
    let document =
        roxmltree::Document::parse(svg).map_err(|error| format!("Invalid SVG figure: {error}"))?;
    let root = document.root_element();
    if !root.has_tag_name(("http://www.w3.org/2000/svg", "svg")) {
        return Err("The figure must be an SVG document.".into());
    }
    atomic_write(file, svg.as_bytes())
}

#[cfg(test)]
mod navigation_tests {
    use super::*;
    #[test]
    fn time_order_filters_entries_preserves_steps_and_finds_new_arrivals() {
        let temp = tempfile::tempdir().unwrap();
        let directory = temp.path().canonicalize().unwrap();
        let first = directory.join("a.tif");
        let second = directory.join("b.tif");
        std::fs::write(&first, b"first").unwrap();
        std::fs::write(directory.join(".hidden.tif"), b"hidden").unwrap();
        std::fs::write(directory.join("other.edf"), b"other").unwrap();
        std::fs::create_dir(directory.join("subfolder.tif")).unwrap();
        assert_eq!(neighbor(&first, "time", 1).unwrap(), None);
        std::fs::write(&second, b"second").unwrap();
        assert_eq!(neighbor(&first, "time", 1).unwrap(), Some(second.clone()));
        assert_eq!(neighbor(&second, "time", -1).unwrap(), Some(first.clone()));
        assert_eq!(neighbor(&first, "time", 2).unwrap(), None);
        assert_eq!(neighbor(&first, "time", -1).unwrap(), None);
    }
    #[test]
    #[cfg(unix)]
    fn time_order_resolves_directory_and_file_symlinks() {
        use std::os::unix::fs::symlink;
        let temp = tempfile::tempdir().unwrap();
        let directory = temp.path().canonicalize().unwrap();
        let source = directory.join("source");
        std::fs::create_dir(&source).unwrap();
        let target = directory.join("outside.tif");
        std::fs::write(&target, b"target").unwrap();
        let first = source.join("a.tif");
        symlink(&target, &first).unwrap();
        let second = source.join("b.tif");
        std::fs::write(&second, b"next").unwrap();
        symlink(source, directory.join("alias")).unwrap();
        symlink(directory.join("absent"), directory.join("alias/broken.tif")).unwrap();
        assert_eq!(
            neighbor(&directory.join("alias/a.tif"), "time", 1).unwrap(),
            Some(second)
        );
    }
}

#[cfg(test)]
mod export_unit_tests {
    use super::*;
    #[test]
    fn angular_fxye_rejects_unphysical_conversion_without_replacing_destination() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("output.fxye");
        std::fs::write(&path, "keep old export").unwrap();
        let curve = Curve {
            x: Arc::new(vec![0.1, 0.2]),
            y: Arc::new(vec![10., 20.]),
            sigma: Some(Arc::new(vec![1., 2.])),
            spread: None,
        };
        for wavelength in [0., f64::NAN, 5e-10] {
            assert!(export_curve(&path, &curve, "d_A", wavelength).is_err());
            assert_eq!(std::fs::read_to_string(&path).unwrap(), "keep old export");
        }
        let q = curve_bytes(&path, &curve, "q_A^-1", 5e-10).unwrap();
        let q = String::from_utf8(q).unwrap();
        assert!(q.contains(" CONQ "));
        assert!(
            q.lines()
                .any(|line| line.starts_with("1.00000000000000006e-1\t"))
        );
        let xy = String::from_utf8(
            curve_bytes(&dir.path().join("data.xy"), &curve, "d_A", 5e-10).unwrap(),
        )
        .unwrap();
        assert!(xy.contains("# d_A\tI"));
        assert!(
            xy.lines()
                .any(|line| line.starts_with("1.00000000000000006e-1\t"))
        );
    }
}

#[cfg(all(test, feature = "dioptrin"))]
#[path = "acquisition_tests.rs"]
mod acquisition_tests;
