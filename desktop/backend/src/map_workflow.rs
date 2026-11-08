//! Map shares the native series owner, immutable profiles and source selections.
use super::*;
use crate::{map_math, scan::Scan, series::Series};
impl Session {
    fn map_preview(&self, args: &Value) -> Result<Reply, String> {
        let scan = self.scan.as_ref().ok_or("Load a map first.")?;
        let smooth = args
            .get("smooth")
            .map_or(Ok(1), |v| integer(v, "Smoothing", 1, 10))?;
        let contours = args
            .get("contours")
            .map_or(Ok(0), |v| integer(v, "Contours", 0, 20))?;
        if scan
            .values
            .len()
            .checked_mul((smooth * smooth).max(if contours > 0 { 9 } else { 1 }))
            .is_none_or(|n| n > 4_000_000)
        {
            return Err("Display interpolation would exceed four million cells.".into());
        }
        let [rows, cols] = scan.shape();
        let data: Vec<_> = scan
            .values
            .chunks_exact(cols)
            .rev()
            .flatten()
            .copied()
            .collect();
        let pixels = crate::map_preview::zoom(&data, [rows, cols], smooth, true);
        let mut raster = Raster::image(&pixels, [rows * smooth, cols * smooth]);
        raster.metadata["fullWidth"] = json!(cols);
        raster.metadata["fullHeight"] = json!(rows);
        raster.metadata["step"] = json!(1.0 / smooth as f64);
        let mut paths = vec![];
        if contours > 0 && rows > 1 && cols > 1 {
            let upsampled = crate::map_preview::zoom(&data, [rows, cols], 3, false);
            let low = upsampled.iter().copied().fold(f64::INFINITY, f64::min);
            let high = upsampled.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            if low < high {
                let levels: Vec<_> = (1..=contours)
                    .map(|i| (i, low + (high - low) * i as f64 / (contours + 1) as f64))
                    .collect();
                let contours =
                    crate::contours::contours_at_step(&upsampled, [rows * 3, cols * 3], &levels, 1);
                for path in contours.as_array().unwrap() {
                    let points: Vec<_> = path["points"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .map(|p| {
                            json!([p[0].as_f64().unwrap() / 3.0, p[1].as_f64().unwrap() / 3.0])
                        })
                        .collect();
                    paths.push(json!(points));
                }
            }
        }
        let mut r =
            Reply::metadata(json!({"ok":true,"mapPreview":raster.metadata,"mapContours":paths}));
        r.buffers.push(raster.buffer);
        Ok(r)
    }
    pub(super) fn attach_map(&self, reply: &mut Reply) {
        if let Some(scan) = &self.scan {
            reply.result["map"] = scan.metadata();
            reply.buffers.push(scan.raster.buffer.clone());
        } else {
            reply.result["map"] = Value::Null;
        }
    }
    fn map_response(&mut self) -> Reply {
        self.revision += 1;
        let mut reply = self.snapshot(false);
        reply.buffers.clear();
        for key in [
            "image", "rawImage", "mask", "cake", "rings", "linked", "batch",
        ] {
            reply.result.as_object_mut().unwrap().remove(key);
        }
        self.attach_map(&mut reply);
        reply
    }
    fn map_selection(&mut self, args: &Value) -> Result<Reply, String> {
        let scan = self
            .scan
            .as_ref()
            .ok_or("Load map image data or a processed batch first.")?;
        let index = if let Some(i) = args.get("index").filter(|v| !v.is_null()) {
            Some(integer(i, "Scan point", 0, scan.series.count() - 1)?)
        } else if let Some(slot) = args.get("slot").filter(|v| !v.is_null()) {
            let slot = integer(
                slot,
                "Arrangement cell",
                0,
                scan.dimension[0] * scan.dimension[1] - 1,
            )?;
            scan.fitted_slots(false)[slot]
        } else if args.get("row").is_some() || args.get("column").is_some() {
            let [rows, cols] = scan.shape();
            let row = integer(&args["row"], "Map row", 0, rows - 1)?;
            let col = integer(&args["column"], "Map column", 0, cols - 1)?;
            let i = scan.indices[row * cols + col];
            (i >= 0).then_some(i as usize)
        } else {
            None
        };
        let integration = args
            .get("integration_view")
            .map_or(Ok(false), |v| boolean(v, "Integration view"))?;
        let reintegrate = args
            .get("reintegrate")
            .map_or(Ok(false), |v| boolean(v, "Reintegrate"))?;
        self.scan.as_mut().unwrap().selected = index;
        let mut reply = if let Some(index) = index {
            let series = self.scan.as_ref().unwrap().series.clone();
            // Rebuild on the Map's actual radial grid. Converting the axis of
            // a Q-binned curve afterward does not reproduce 2theta-bin counts.
            let integration_unit = self.settings.unit.clone();
            if reintegrate && !integration {
                self.settings.unit = series.unit.clone();
            }
            let selection = self.select_series_mode(
                &series,
                index,
                !integration && !reintegrate,
                !integration && !reintegrate,
                Some(&series.unit),
                !integration,
            );
            self.settings.unit = integration_unit;
            let mut reply = selection?;
            reply.result["state"]["unit"] = json!(self.settings.unit);
            reply.result["linked"] = self.linked_snapshot();
            if reintegrate && !integration {
                if self.image.is_none() {
                    return Err(
                        "Reintegration needs the original image and a loaded calibration.".into(),
                    );
                }
                self.cake = None;
                self.cake_values = None;
            }
            reply
        } else {
            self.image = None;
            self.image_raster = None;
            self.processed_raster = None;
            self.processed_values = None;
            self.patterns.raw = None;
            self.pattern = None;
            self.cake = None;
            self.cake_values = None;
            self.inspection = None;
            let mut r = self.snapshot(false);
            r.result["clearImage"] = json!(true);
            r
        };
        if !integration {
            self.cake = None;
            self.cake_values = None;
            reply.result["cake"] = Value::Null;
            reply.result["rings"] = json!([]);
        }
        reply.result["mapWarning"] = reply.result["batchWarning"].clone();
        // Both selection branches already produced a snapshot of this scan.
        Ok(reply)
    }
    pub(super) fn map_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        match action {
            "map_snapshot" => {
                let mut r = Reply::metadata(json!({"ok":true}));
                self.attach_map(&mut r);
                return Ok(Some(r));
            }
            "map_load" | "map_folder" => {
                let paths = if action == "map_folder" {
                    batch_workflow::folder_paths(path(args)?)?
                } else if args["reintegrate"] == true {
                    self.scan
                        .as_ref()
                        .ok_or("Load scan files first.")?
                        .series
                        .paths
                        .clone()
                } else {
                    batch_workflow::source_paths(args)?
                };
                let series = self.integrate_series(paths, &json!({"preview_map":true}))?;
                self.scan = Some(Scan::new_with_analysis(
                    series,
                    &self.patterns,
                    self.scan.as_ref(),
                )?);
                return self.map_selection(&json!({"index":0})).map(Some);
            }
            "map_batch" => {
                let series = Series::load(path(args)?)?;
                self.scan = Some(Scan::new_with_analysis(
                    series,
                    &self.patterns,
                    self.scan.as_ref(),
                )?);
                return self.map_selection(&json!({"index":0})).map(Some);
            }
            "map_select" => return self.map_selection(args).map(Some),
            "map_poll" => return self.map_poll(args).map(Some),
            "map_display" => return self.map_preview(args).map(Some),
            "map_export" => return self.map_export(args).map(Some),
            "map_mask" => {
                let mut settings = json!({});
                for key in ["use_mask", "transparent_mask"] {
                    if let Some(v) = args.get(key) {
                        settings[key] = v.clone();
                    }
                }
                settings["defer_integration"] = json!(true);
                self.dispatch("integration_settings", &settings)?;
                if args["reintegrate"] == true {
                    return self.map_command("map_load", &json!({"reintegrate":true}));
                }
                let r = self.map_response();
                return Ok(Some(r));
            }
            "map_levels" => {
                let s = self.scan.as_ref().ok_or("Load a map first.")?;
                return Ok(Some(Reply::metadata(
                    json!({"ok":true,"mapLevels":batch_workflow::series_levels(&s.values,s.shape(),args)?}),
                )));
            }
            "map_grid" | "map_roi" | "map_expression" | "map_layer" | "map_arrange"
            | "map_normalize" => {}
            _ => return Ok(None),
        }
        let s = self
            .scan
            .as_mut()
            .ok_or("Load map image data or a processed batch first.")?;
        let mut reduce = false;
        match action {
            "map_grid" => {
                for (i, key) in ["rows", "columns"].iter().enumerate() {
                    if let Some(v) = args.get(key).filter(|v| !v.is_null()) {
                        s.dimension[i] = integer(v, key, 1, 4_000_000)?;
                    }
                }
                for (key, target) in [
                    ("snake", &mut s.snake),
                    ("transpose", &mut s.transpose),
                    ("flip_horizontal", &mut s.flip_horizontal),
                    ("flip_vertical", &mut s.flip_vertical),
                ] {
                    if let Some(v) = args.get(key).filter(|v| !v.is_null()) {
                        *target = boolean(v, key)?;
                    }
                }
            }
            "map_roi" => {
                let name = args["name"].as_str().unwrap_or("");
                match args["op"].as_str().unwrap_or("update") {
                    "add" => {
                        let mut n = 0;
                        let name = loop {
                            let name = if n < 26 {
                                ((b'A' + n as u8) as char).to_string()
                            } else {
                                format!("W{}", n + 1)
                            };
                            if s.name_available(&name) {
                                break name;
                            }
                            n += 1;
                        };
                        if s.rois.len() >= 128 {
                            return Err("A map supports at most 128 windows.".into());
                        }
                        let mut roi = s.rois.last().unwrap().clone();
                        roi.name = name.clone();
                        roi.color =
                            ["#ff9800", "#00bcd4", "#e91e63", "#8bc34a"][s.rois.len() % 4].into();
                        s.rois.push(roi);
                        s.active = name;
                    }
                    "remove" => {
                        if s.rois.len() == 1 || !s.rois.iter().any(|r| r.name == name) {
                            return Err("Keep at least one map window.".into());
                        }
                        s.rois.retain(|r| r.name != name);
                        s.expressions.retain(|(_, e)| {
                            !map_math::Expression::parse(e).is_ok_and(|e| e.names().contains(name))
                        });
                        if s.active == name
                            || !s.rois.iter().any(|r| r.name == s.active)
                                && !s.expressions.iter().any(|(n, _)| *n == s.active)
                        {
                            s.active = s.rois[0].name.clone();
                        }
                    }
                    "update" => {
                        let index = s
                            .rois
                            .iter()
                            .position(|r| r.name == name)
                            .ok_or("Unknown map window.")?;
                        let mut roi = s.rois[index].clone();
                        for (key, target) in [("minimum", &mut roi.min), ("maximum", &mut roi.max)]
                        {
                            if let Some(v) = args.get(key).filter(|v| !v.is_null()) {
                                *target = finite(v, key, -1e12, 1e12)?;
                            }
                        }
                        if roi.min >= roi.max {
                            return Err("Window limits must be finite and increasing.".into());
                        }
                        if let Some(kind) = args.get("reduction").filter(|v| !v.is_null()) {
                            roi.reduction = kind
                                .as_str()
                                .filter(|k| map_math::REDUCTIONS.contains(k))
                                .ok_or("Unknown map reduction.")?
                                .into();
                        }
                        if let Some(v) = args.get("background").filter(|v| !v.is_null()) {
                            roi.background = boolean(v, "Subtract background")?;
                        }
                        if let Some(v) = args.get("color").filter(|v| !v.is_null()) {
                            roi.color = crate::pattern::color(v)?;
                        }
                        if let Some(new) = args["new_name"].as_str().filter(|n| *n != name) {
                            if !map_math::identifier(new) || !s.name_available(new) {
                                return Err("Choose a unique window identifier.".into());
                            }
                            for (_, e) in &mut s.expressions {
                                *e = map_math::Expression::parse(e)?.rename(name, new);
                            }
                            if s.active == name {
                                s.active = new.into();
                            }
                            roi.name = new.into();
                        }
                        if args["activate"] == true {
                            s.active = roi.name.clone();
                        }
                        s.rois[index] = roi;
                    }
                    _ => return Err("Unknown window action.".into()),
                }
                reduce = true;
            }
            "map_expression" => {
                let name = args["name"].as_str().ok_or("Name the expression layer.")?;
                if args["remove"] == true {
                    s.expressions.retain(|(n, _)| n != name);
                    if s.active == name {
                        s.active = s.rois[0].name.clone();
                    }
                } else {
                    let text = args["expression"]
                        .as_str()
                        .ok_or("Enter a map expression.")?;
                    map_math::Expression::parse(text)?;
                    let target = args["new_name"].as_str().unwrap_or(name).trim();
                    if target.is_empty()
                        || target.len() > 250
                        || s.rois.iter().any(|r| r.name == target)
                        || target != name && !s.name_available(target)
                    {
                        return Err("Choose a unique expression layer name.".into());
                    }
                    let old = s.expressions.iter().position(|(n, _)| n == name);
                    if let Some(i) = old {
                        s.expressions[i] = (target.into(), text.into());
                    } else {
                        if s.expressions.len() >= 128 {
                            return Err("A map supports at most 128 expression layers.".into());
                        }
                        s.expressions.push((target.into(), text.into()));
                    }
                    let values = s.layer_values(target, &self.patterns)?;
                    if !values.iter().any(|v| v.is_finite()) {
                        return Err(
                            "Expression must use existing window names and produce finite values."
                                .into(),
                        );
                    }
                    s.active = target.into();
                }
            }
            "map_layer" => {
                let name = args["name"].as_str().ok_or("Choose a map layer.")?;
                if !s.rois.iter().any(|r| r.name == name)
                    && !s.expressions.iter().any(|(n, _)| n == name)
                {
                    return Err("Unknown map layer.".into());
                }
                s.active = name.into();
            }
            "map_arrange" => {
                let op = args["op"].as_str().ok_or("Choose an arrangement action.")?;
                let mut slots = s.fitted_slots(false);
                match op {
                    "exclude" => {
                        let i = integer(&args["index"], "Scan point", 0, s.series.count() - 1)?;
                        if !s.excluded.remove(&i) {
                            s.excluded.insert(i);
                        }
                    }
                    "insert" | "remove" | "move" => {
                        let slot = integer(&args["slot"], "Arrangement cell", 0, slots.len() - 1)?;
                        match op {
                            "insert" => {
                                slots.insert(slot, None);
                                s.dimension[0] = slots.len().div_ceil(s.dimension[1]);
                            }
                            "remove" => {
                                if slots[slot].is_some() {
                                    return Err("Only blank cells can be removed.".into());
                                }
                                slots.remove(slot);
                            }
                            "move" => {
                                let offset = args["offset"]
                                    .as_i64()
                                    .ok_or("Cell offset must be an integer.")?;
                                let target = (slot as i128) + (offset as i128);
                                if target < 0 || target >= slots.len() as i128 {
                                    return Err("The cell cannot move outside the grid.".into());
                                }
                                let item = slots.remove(slot);
                                slots.insert(target as usize, item);
                                s.selected_slot = Some(target as usize);
                            }
                            _ => unreachable!(),
                        }
                        s.slots = slots;
                    }
                    "gaps" => {
                        let mut numbers = vec![];
                        let mut unique = std::collections::BTreeSet::new();
                        for e in s.series.entries.iter() {
                            if e.frame != 0 || !unique.insert(&e.path) {
                                return Err(
                                    "Filename gaps require one frame per numbered source.".into()
                                );
                            }
                            numbers.push(
                                filename_number(Path::new(&e.path))
                                    .ok_or("No unambiguous filename numbering.")?,
                            );
                        }
                        let min = *numbers.iter().min().unwrap();
                        let max = *numbers.iter().max().unwrap();
                        let span = max
                            .checked_sub(min)
                            .and_then(|n| n.checked_add(1))
                            .filter(|n| *n <= 4 * s.series.count() as u64 && *n <= 4_000_000)
                            .ok_or("Filename span is too large for an unambiguous numbering gap.")?
                            as usize;
                        let mut slots = vec![None; span];
                        for (i, &number) in numbers.iter().enumerate() {
                            let slot = (number - min) as usize;
                            if slots[slot].is_some() {
                                return Err("Filename numbering is ambiguous.".into());
                            }
                            slots[slot] = Some(i);
                        }
                        s.dimension[0] = slots.len().div_ceil(s.dimension[1]);
                        s.slots = slots;
                    }
                    _ => return Err("Unknown arrangement action.".into()),
                }
            }
            "map_normalize" => {
                let enabled = args
                    .get("enabled")
                    .map_or(Ok(true), |v| boolean(v, "Normalize"))?;
                let reference = args.get("reference").map_or(Ok(0), |v| {
                    integer(v, "Reference frame", 0, s.series.count() - 1)
                })?;
                let mut start = args
                    .get("start")
                    .map_or(Ok(0), |v| integer(v, "First bin", 0, s.series.x.len() - 1))?;
                let mut stop = args
                    .get("stop")
                    .filter(|v| !v.is_null())
                    .map_or(Ok(s.series.x.len()), |v| {
                        integer(v, "Last bin", 1, s.series.x.len())
                    })?;
                let window = args["window"]
                    .as_str()
                    .map(|n| {
                        s.rois
                            .iter()
                            .find(|r| r.name == n)
                            .cloned()
                            .ok_or("Choose an existing window for normalization.")
                    })
                    .transpose()?;
                if enabled
                    && (window.is_some()
                        || args.get("minimum").is_some()
                        || args.get("maximum").is_some()
                        || args.get("unit").is_some())
                {
                    let (min, max, unit) = if let Some(r) = &window {
                        (r.min, r.max, s.series.unit.as_str())
                    } else {
                        (
                            finite(&args["minimum"], "Minimum", 0.0, 1e12)?,
                            finite(&args["maximum"], "Maximum", 0.0, 1e12)?,
                            args["unit"]
                                .as_str()
                                .filter(|u| ["2th_deg", "q_A^-1", "d_A"].contains(u))
                                .ok_or("Choose a radial unit and both normalization limits.")?,
                        )
                    };
                    if min >= max || unit == "d_A" && min <= 0.0 || unit == "2th_deg" && max > 180.0
                    {
                        return Err("Choose a physical, increasing normalization range.".into());
                    }
                    if unit != s.series.unit
                        && [unit, s.series.unit.as_str()].contains(&"2th_deg")
                        && s.series.wavelength.is_none()
                    {
                        return Err(
                            "Angular normalization conversion needs a recorded wavelength.".into(),
                        );
                    }
                    let mut bounds = [
                        linked::convert(
                            min,
                            unit,
                            &s.series.unit,
                            s.series.wavelength.unwrap_or(1e-10),
                        ),
                        linked::convert(
                            max,
                            unit,
                            &s.series.unit,
                            s.series.wavelength.unwrap_or(1e-10),
                        ),
                    ];
                    if bounds.iter().any(|b| !b.is_finite()) {
                        return Err("The normalization range cannot be converted to the stored radial unit.".into());
                    }
                    bounds.sort_by(f64::total_cmp);
                    let indices: Vec<_> = s
                        .series
                        .x
                        .iter()
                        .enumerate()
                        .filter_map(|(i, &x)| (x > bounds[0] && x < bounds[1]).then_some(i))
                        .collect();
                    if indices.is_empty() || indices.windows(2).any(|i| i[1] != i[0] + 1) {
                        return Err("Normalization must select a nonempty contiguous range of stored samples.".into());
                    }
                    start = indices[0];
                    stop = indices.last().unwrap() + 1;
                    s.normalization_coordinates = json!({"minimum":min,"maximum":max,"unit":unit});
                    if let Some(w) = window {
                        s.normalization_coordinates["window"] = json!(w.name);
                    }
                } else {
                    s.normalization_coordinates = Value::Null;
                }
                s.series.normalize(enabled, [start, stop], reference)?;
                reduce = true;
            }
            _ => unreachable!(),
        }
        s.rebuild(reduce, &self.patterns)?;
        if action == "map_normalize"
            && let Some(i) = self.scan.as_ref().unwrap().selected
        {
            return self.map_selection(&json!({"index":i})).map(Some);
        }
        Ok(Some(self.map_response()))
    }
    fn map_export(&self, args: &Value) -> Result<Reply, String> {
        let s = self.scan.as_ref().ok_or("Load a map first.")?;
        let file = path(args)?;
        let file = if file.extension().is_none() {
            file.with_extension(if args.get("png_data").is_some() {
                "png"
            } else {
                "txt"
            })
        } else {
            file.to_path_buf()
        };
        match file
            .extension()
            .unwrap_or_default()
            .to_string_lossy()
            .to_lowercase()
            .as_str()
        {
            "txt" => {
                let cols = s.shape()[1];
                let text = s
                    .values
                    .chunks_exact(cols)
                    .map(|r| {
                        r.iter()
                            .map(|v| {
                                if v.is_nan() {
                                    "nan".into()
                                } else {
                                    format!("{v:.17e}")
                                }
                            })
                            .collect::<Vec<_>>()
                            .join(" ")
                    })
                    .collect::<Vec<_>>()
                    .join("\n")
                    + "\n";
                atomic_write(&file, text.as_bytes())?;
            }
            "png" => file_workflow::save_png(&file, &args["png_data"])?,
            "tif" | "tiff" => {
                let min = s
                    .values
                    .iter()
                    .filter(|v| v.is_finite())
                    .copied()
                    .fold(f64::INFINITY, f64::min);
                let max = s
                    .values
                    .iter()
                    .filter(|v| v.is_finite())
                    .copied()
                    .fold(f64::NEG_INFINITY, f64::max);
                let values: Vec<u32> = s
                    .values
                    .iter()
                    .map(|v| {
                        if v.is_finite() && max > min {
                            ((v - min) / (max - min) * u32::MAX as f64) as u32
                        } else {
                            0
                        }
                    })
                    .collect();
                file_workflow::atomic_render(&file, |out| {
                    let mut t = tiff::encoder::TiffEncoder::new(out).map_err(|e| e.to_string())?;
                    t.write_image::<tiff::encoder::colortype::Gray32>(
                        s.shape()[1] as u32,
                        s.shape()[0] as u32,
                        &values,
                    )
                    .map_err(|e| e.to_string())
                })?;
            }
            _ => return Err("Save tabular text, normalized TIFF, or a rendered PNG.".into()),
        }
        Ok(Reply::metadata(json!({"ok":true,"savedPath":file})))
    }
    fn map_poll(&mut self, args: &Value) -> Result<Reply, String> {
        let s = self
            .scan
            .as_mut()
            .ok_or("Load calibrated scan images before starting Live.")?;
        if s.series.normalized {
            return Err("Restore original patterns before appending live images.".into());
        }
        let last = s.series.paths.last().ok_or("Load raw scan images first.")?;
        let folder = Path::new(last)
            .parent()
            .ok_or("The live scan folder is unavailable.")?;
        let last_path = Path::new(last);
        let stem = last_path
            .file_stem()
            .and_then(|s| s.to_str())
            .ok_or("Live needs numbered scan files.")?;
        let prefix = stem
            .trim_end_matches(|c: char| c.is_ascii_digit())
            .to_string();
        let extension = last_path.extension().map(|e| e.to_os_string());
        let highest = s
            .series
            .paths
            .iter()
            .filter_map(|p| filename_number(Path::new(p)))
            .max()
            .ok_or("Live needs numbered scan files.")?;
        let mut signatures = std::collections::BTreeMap::new();
        let mut ready = vec![];
        for p in batch_workflow::folder_paths(folder)? {
            let candidate = Path::new(&p);
            let matches_sequence = candidate.extension().map(|e| e.to_os_string()) == extension
                && candidate
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .is_some_and(|s| s.trim_end_matches(|c: char| c.is_ascii_digit()) == prefix);
            if !matches_sequence
                || s.series.paths.contains(&p)
                || filename_number(Path::new(&p))
                    .is_none_or(|n| n <= highest && !s.pending.contains_key(&p))
            {
                continue;
            }
            let meta = std::fs::metadata(&p).map_err(|e| e.to_string())?;
            let signature = (meta.len(), meta.modified().map_err(|e| e.to_string())?);
            if signature.0 > 0 && s.pending.get(&p) == Some(&signature) {
                ready.push(p.clone());
            }
            signatures.insert(p, signature);
        }
        s.pending = signatures;
        if args["check_only"] == true {
            return Ok(Reply::metadata(json!({"ok":true,"mapPending":ready.len()})));
        }
        if ready.is_empty() {
            return Ok(Reply::metadata(json!({"ok":true})));
        }
        ready.sort_by_key(|p| filename_number(Path::new(p)));
        ready.truncate(2);
        let mut appended = s.series.clone();
        let mut failed = 0;
        let mut added = false;
        for path in ready {
            match self
                .integrate_series(vec![path], &json!({}))
                .and_then(|incoming| appended.append(&incoming))
            {
                Ok(series) => {
                    appended = series;
                    added = true;
                }
                Err(_) => {
                    self.control.check()?;
                    failed += 1;
                }
            }
        }
        if !added {
            return Ok(Reply::metadata(
                json!({"ok":true,"mapWarning":"Live: waiting for readable scan files."}),
            ));
        }
        let s = self.scan.as_mut().unwrap();
        let old = s.series.count();
        let previous = s.selected;
        s.series = appended;
        let append: Vec<_> = (old..s.series.count()).map(Some).collect();
        s.slots.extend(append);
        s.dimension[0] = s.slots.len().max(s.series.count()).div_ceil(s.dimension[1]);
        s.rebuild(true, &self.patterns)?;
        let index = if args
            .get("follow")
            .map_or(Ok(true), |v| boolean(v, "Follow live"))?
        {
            Some(s.series.count() - 1)
        } else {
            previous
        };
        let mut reply = self.map_selection(&json!({"index":index}))?;
        if failed > 0 {
            reply.result["mapWarning"] = json!(format!(
                "Live: {failed} scan file(s) could not be read; retrying."
            ));
        }
        Ok(reply)
    }
}
fn filename_number(path: &Path) -> Option<u64> {
    let stem = path.file_stem()?.to_str()?;
    let end = stem.len();
    let start = stem
        .as_bytes()
        .iter()
        .rposition(|c| !c.is_ascii_digit())
        .map_or(0, |i| i + 1);
    (start < end).then(|| stem[start..].parse().ok()).flatten()
}
