//! Qt-style grouped file/folder browsing; all processing stays native.
use super::*;

fn spans(text: &str) -> Vec<(usize, usize)> {
    let bytes = text.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i].is_ascii_digit() {
            let start = i;
            while i < bytes.len() && bytes[i].is_ascii_digit() {
                i += 1;
            }
            out.push((start, i));
        } else {
            i += 1;
        }
    }
    out
}
fn increment(text: &str, span: (usize, usize), step: i64, padded: bool) -> Option<String> {
    let (start, end) = span;
    let value = text[start..end]
        .parse::<i128>()
        .ok()?
        .checked_add(step as i128)?;
    if value < 0 {
        return None;
    }
    let number = if padded {
        format!("{value:0width$}", width = end - start)
    } else {
        value.to_string()
    };
    Some(format!("{}{}{}", &text[..start], number, &text[end..]))
}
fn next_file(path: &Path, step: i64, position: usize) -> Option<PathBuf> {
    let name = path.file_name()?.to_str()?;
    for (index, span) in spans(name).into_iter().rev().enumerate() {
        if position != 0 && index + 1 != position {
            continue;
        }
        for padded in [true, false] {
            if let Some(name) = increment(name, span, step, padded) {
                let candidate = path.with_file_name(name);
                if candidate.is_file() {
                    return Some(candidate);
                }
            }
        }
    }
    None
}
fn next_folder(
    path: &Path,
    step: i64,
    position: usize,
    filename_position: usize,
    filename_step: i64,
) -> Option<PathBuf> {
    let directory = path.parent()?.to_str()?;
    let filename = path.file_name()?.to_str()?;
    let filename = if filename_position > 0 {
        increment(
            filename,
            *spans(filename).iter().rev().nth(filename_position - 1)?,
            filename_step,
            true,
        )?
    } else {
        filename.to_string()
    };
    for (index, span) in spans(directory).into_iter().rev().enumerate() {
        if position != 0 && index + 1 != position {
            continue;
        }
        if let Some(directory) = increment(directory, span, step, true) {
            let candidate = Path::new(&directory).join(&filename);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}
impl Session {
    pub(super) fn navigate_configurations(&mut self, args: &Value) -> Result<Reply, String> {
        check_keys(
            args,
            &[
                "target",
                "direction",
                "number_position",
                "mec",
                "scope",
                "step",
                "folder_number_position",
                "folder_filename_position",
                "folder_filename_step",
            ],
        )?;
        let target = args["target"]
            .as_str()
            .filter(|v| ["file", "folder"].contains(v))
            .ok_or("Choose file or folder browsing.")?;
        let direction = args["direction"]
            .as_i64()
            .filter(|v| [-1, 1].contains(v))
            .ok_or("Browsing direction must be -1 or 1.")?;
        let position = args
            .get("number_position")
            .map(|v| integer(v, "Number position", 0, 100))
            .transpose()?
            .unwrap_or(0);
        let mec = args
            .get("mec")
            .map(|v| boolean(v, "MEC mode"))
            .transpose()?
            .unwrap_or(false);
        let selected = self.project.selected;
        let scope = args
            .get("scope")
            .map(|value| {
                value
                    .as_str()
                    .filter(|v| ["active", "all"].contains(v))
                    .ok_or("Choose active or all configuration browsing.")
            })
            .transpose()?
            .unwrap_or("all");
        let number = |key: &str, fallback: usize, min, max| -> Result<usize, String> {
            args.get(key)
                .map(|v| integer(v, key, min, max))
                .transpose()
                .map(|v| v.unwrap_or(fallback))
        };
        let step = direction * number("step", 1, 1, 1_000_000)? as i64;
        let folder_position = number("folder_number_position", 0, 0, 100)?;
        let filename_position =
            number("folder_filename_position", if mec { 3 } else { 0 }, 0, 100)?;
        let filename_step = direction * number("folder_filename_step", 1, 1, 1_000_000)? as i64;
        let mut candidates = vec![];
        let mut skipped = vec![];
        for (index, configuration) in self.project.configurations.iter().enumerate() {
            if scope == "active" && index != selected {
                continue;
            }
            self.control.check()?;
            let state = if index == selected {
                self.checkpoint()
            } else {
                configuration
                    .as_ref()
                    .ok_or("Configuration is unavailable.")?
                    .state
                    .clone()
            };
            let Some(image) = state.image else {
                skipped.push(index);
                continue;
            };
            let candidate = if target == "folder" {
                next_folder(
                    &image.path,
                    step,
                    folder_position,
                    filename_position,
                    filename_step,
                )
            } else if state.files.image_mode == "time" {
                match file_workflow::neighbor(&image.path, "time", step) {
                    Ok(file) => Some(file),
                    Err(error) if error == "No further file in time order." => None,
                    Err(error) => return Err(error),
                }
            } else {
                next_file(&image.path, step, position)
            };
            if let Some(file) = candidate {
                let mut options = image.options.clone();
                options["path"] = json!(file);
                options["frame"] = json!(0);
                options["defer_integration"] = json!(false);
                options.as_object_mut().unwrap().remove("reset_calibration");
                candidates.push((index, options));
            } else {
                skipped.push(index);
            }
        }
        let advanced: Vec<_> = candidates.iter().map(|(i, _)| *i).collect();
        for (index, options) in candidates {
            self.control.check()?;
            self.select_configuration(index)?;
            let reply = self.dispatch("open_image", &options)?;
            if reply.result.get("imageChange").is_some() {
                return Err(format!(
                    "Configuration {} changes detector dimensions. Open and reset that detector explicitly before grouped browsing; no configurations were advanced.",
                    index + 1
                ));
            }
        }
        self.select_configuration(selected)?;
        let mut reply = if advanced.is_empty() {
            self.snapshot(false)
        } else {
            self.configuration_reply()
        };
        reply.result["configurationNavigation"] = json!({"advanced":advanced,"skipped":skipped});
        Ok(reply)
    }
}
