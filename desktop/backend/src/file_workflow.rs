//! Source-local navigation, stable incoming-file polling, and atomic exports.
use super::*;
use crate::pattern::Curve;
use std::{
    collections::{BTreeMap, BTreeSet, VecDeque},
    time::SystemTime,
};

#[derive(Clone, serde::Serialize, serde::Deserialize)]
pub(super) struct Files {
    pub image_directory: String,
    pub output_directory: String,
    pub image_mode: String,
    pub auto_process: bool,
    pub auto_error: String,
    known: BTreeSet<PathBuf>,
    pending: BTreeMap<PathBuf, (u64, SystemTime)>,
    queue: VecDeque<PathBuf>,
}
impl Default for Files {
    fn default() -> Self {
        Self {
            image_directory: String::new(),
            output_directory: String::new(),
            image_mode: "number".into(),
            auto_process: false,
            auto_error: String::new(),
            known: BTreeSet::new(),
            pending: BTreeMap::new(),
            queue: VecDeque::new(),
        }
    }
}
impl Files {
    pub(super) fn stop_autoprocess(&mut self) {
        self.auto_process = false;
        self.auto_error.clear();
        self.queue.clear();
        self.pending.clear();
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
    fn scan(&self) -> Result<BTreeSet<PathBuf>, String> {
        let mut paths = BTreeSet::new();
        for entry in std::fs::read_dir(&self.image_directory).map_err(|e| e.to_string())? {
            let p = entry.map_err(|e| e.to_string())?.path();
            if image_file(&p) && p.is_file() {
                paths.insert(p);
            }
            if paths.len() > 1_000_000 {
                return Err("Incoming directory exceeds one million image names.".into());
            }
        }
        Ok(paths)
    }
    pub fn baseline(&mut self) -> Result<(), String> {
        self.known = self.scan()?;
        self.pending.clear();
        self.queue.clear();
        Ok(())
    }
    pub fn poll(&mut self) -> Result<Option<PathBuf>, String> {
        let paths = self.scan()?;
        self.known.retain(|p| paths.contains(p));
        self.pending.retain(|p, _| paths.contains(p));
        let mut ready = Vec::new();
        for path in paths.difference(&self.known) {
            let m = std::fs::metadata(path).map_err(|e| e.to_string())?;
            let stamp = (m.len(), m.modified().map_err(|e| e.to_string())?);
            if stamp.0 > 0 && self.pending.get(path) == Some(&stamp) {
                ready.push((stamp.1, path.clone()));
            } else {
                self.pending.insert(path.clone(), stamp);
            }
        }
        ready.sort();
        for (_, path) in ready {
            self.known.insert(path.clone());
            self.pending.remove(&path);
            self.queue.push_back(path);
        }
        Ok(self.queue.pop_front())
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
    let mut text = if extension == "chi" {
        format!("{}\n{unit}\n\n       {}\n", path.display(), curve.x.len())
    } else {
        format!(
            "# Dioptas native backend\n# wavelength_m: {wavelength:.17e}\n# {unit}\tI{}\n",
            if curve.sigma.is_some() { "\tsigma" } else { "" }
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
    atomic_write(path, text.as_bytes())
}
pub(super) fn atomic_render(
    path: &Path,
    write: impl FnOnce(&mut std::fs::File) -> Result<(), String>,
) -> Result<(), String> {
    let mut temporary = tempfile::NamedTempFile::new_in(
        path.parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new(".")),
    )
    .map_err(|e| e.to_string())?;
    write(temporary.as_file_mut())?;
    temporary.as_file().sync_all().map_err(|e| e.to_string())?;
    temporary.persist(path).map_err(|e| e.to_string())?;
    Ok(())
}
impl Session {
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
                if let Some(dir) = args.get("directory") {
                    self.files.image_directory = directory(&json!({"path":dir}))?;
                }
                if enabled && !self.files.auto_process {
                    self.files.baseline()?;
                }
                self.files.auto_process = enabled;
                self.files.auto_error.clear();
            }
            "integration_autoprocess_poll" => {
                if !self.files.auto_process {
                    return Ok(Some(Reply::metadata(json!({"ok":true}))));
                }
                let Some(path) = self.files.poll()? else {
                    return Ok(Some(Reply::metadata(json!({"ok":true}))));
                };
                // A corrupt incoming file must not discard the prior session or
                // stall the queue. Restore all scientific state, retain its error.
                let checkpoint = self.checkpoint();
                let mut options = self
                    .image
                    .as_ref()
                    .map(|i| i.options.clone())
                    .unwrap_or(json!({}));
                options["path"] = json!(path);
                options["frame"] = json!(0);
                match self.dispatch("open_image", &options) {
                    Ok(reply) if reply.result["imageChange"].is_object() => {
                        self.restore_checkpoint(checkpoint);
                        self.files.stop_autoprocess();
                        self.files.auto_error = format!(
                            "{}: detector dimensions changed. Autoprocess stopped; open the image manually to reset calibration.",
                            path.file_name().unwrap_or_default().to_string_lossy()
                        );
                        return Ok(Some(self.snapshot(false)));
                    }
                    Ok(reply) => {
                        self.files.auto_error.clear();
                        return Ok(Some(reply));
                    }
                    Err(e) => {
                        self.restore_checkpoint(checkpoint);
                        self.files.auto_error = format!(
                            "{}: {e}",
                            path.file_name().unwrap_or_default().to_string_lossy()
                        );
                        return Ok(Some(self.snapshot(true)));
                    }
                }
            }
            "integration_autocreate" => {
                self.settings.auto_save = boolean(&args["enabled"], "Auto save")?;
                if let Some(dir) = args.get("directory") {
                    self.files.output_directory = directory(&json!({"path":dir}))?;
                }
            }
            "integration_navigation" => {
                if let Some(mode) = args.get("mode") {
                    self.files.image_mode = mode
                        .as_str()
                        .filter(|s| ["number", "time"].contains(s))
                        .ok_or("Choose filename number or creation time navigation.")?
                        .into();
                }
                if let Some(frame) = args.get("frame") {
                    let image = self.image.as_ref().ok_or("Open an image first.")?;
                    let frame = integer(frame, "Frame", 1, image.frames)?;
                    let direction = frame as i64 - 1 - image.frame as i64;
                    return Ok(Some(self.dispatch(
                        "next_image",
                        &json!({"direction":direction,"step":1}),
                    )?));
                }
            }
            "integration_save_pattern" | "export_pattern" | "integration_save_background" => {
                let mut file = path(args)?.to_path_buf();
                if file.extension().is_none() {
                    file.set_extension("xy");
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
    pub(super) fn auto_save(&self) -> Result<(), String> {
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
        } else {
            Path::new(&self.files.output_directory)
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
            if self.image.as_ref().is_some_and(|i| i.path == file) {
                return Err("Automatic output would replace the detector source; choose another output directory.".into());
            }
            export_curve(
                &file,
                raw,
                &self.patterns.unit,
                self.settings.geometry.wavelength,
            )?;
            if self.patterns.background.enabled || self.patterns.background_uid.is_some() {
                let sub = directory.join("bkg_subtracted");
                std::fs::create_dir_all(&sub).map_err(|e| e.to_string())?;
                let displayed = Curve::from_json(self.pattern.as_deref().unwrap())?;
                export_curve(
                    &sub.join(format!("{}{}", self.patterns.name, format)),
                    &displayed,
                    &self.patterns.unit,
                    self.settings.geometry.wavelength,
                )?;
            }
        }
        Ok(())
    }
}

pub(super) fn save_png(file: &Path, value: &Value) -> Result<(), String> {
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
    reader.next_frame(&mut output).map_err(|e| e.to_string())?;
    reader.finish().map_err(|e| e.to_string())?;
    atomic_write(file, &bytes)
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
