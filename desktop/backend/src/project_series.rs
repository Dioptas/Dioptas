//! Existing Qt map layout and optional React Batch/normalization extensions.
use super::*;
use crate::{
    scan::{Roi, Scan},
    series::{Entry, Series},
};
fn save_embedded(s: &Series, group: &hdf5::Group, name: &str) -> Result<(), String> {
    let temp = tempfile::NamedTempFile::new().map_err(|e| e.to_string())?;
    s.save(temp.path())?;
    let f = hdf5::File::open(temp.path()).native()?;
    replace(group, name)?;
    f.group("processed").native()?.copy_to(group, name).native()
}
fn load_embedded(group: &hdf5::Group) -> Result<Series, String> {
    let temp = tempfile::NamedTempFile::new().map_err(|e| e.to_string())?;
    {
        let f = hdf5::File::create(temp.path()).native()?;
        group.copy_to(&f, "processed").native()?;
        f.flush().native()?;
    }
    Series::load(temp.path())
}
fn map_params(s: &Scan, previous: &Value) -> Value {
    let mut p = with_defaults("map", previous);
    merge(
        &mut p,
        &json!({"dimension":s.dimension,"slots":s.slots,"snake":s.snake,"transpose":s.transpose,
        "flip_horizontal":s.flip_horizontal,"flip_vertical":s.flip_vertical,"excluded_points":s.excluded,
        "active_layer":s.active,"expressions":s.expressions.iter().map(|(k,v)|(k.clone(),json!(v))).collect::<serde_json::Map<String,Value>>(),
        "rois":s.rois.iter().map(|r|json!({"name":r.name,"x_min":r.min,"x_max":r.max,"reduction":r.reduction,"subtract_background":r.background,"color":r.color})).collect::<Vec<_>>()}),
    );
    p
}
pub(super) fn save_configuration(
    s: &Checkpoint,
    group: &hdf5::Group,
    doc: &mut Value,
) -> Result<(), String> {
    if let Some(batch) = &s.batch {
        save_embedded(batch, group, "native_batch")?;
    } else {
        replace(group, "native_batch")?;
    }
    if let Some(scan) = &s.scan {
        let g = ensure_group(group, "map")?;
        let p = map_params(scan, &doc["map"]);
        doc["map"] = p.clone();
        let params = ensure_group(&g, "params")?;
        write_scalar_attr(&params, "schema_version", 1_u32)?;
        write_text_attr(&params, "class", "MapParams")?;
        write_text_attr(&params, "data", &p.to_string())?;
        write_array(&g, "pattern_x", &[scan.series.x.len()], &scan.series.x)?;
        write_array(
            &g,
            "pattern_intensities",
            &[scan.series.count(), scan.series.x.len()],
            &scan.series.data,
        )?;
        write_text_attr(&g, "pattern_unit", &scan.series.unit)?;
        let roi = scan
            .rois
            .iter()
            .find(|r| r.name == scan.active)
            .unwrap_or(&scan.rois[0]);
        write_array(&g, "window", &[2], &[roi.min, roi.max])?;
        write_array(&g, "dimension", &[2], &scan.dimension.map(|v| v as i64))?;
        write_strings(&g, "filepaths", &scan.series.paths)?;
        let points = ensure_group(&g, "point_infos")?;
        write_strings(
            &points,
            "filepaths",
            &scan
                .series
                .entries
                .iter()
                .map(|e| e.path.clone())
                .collect::<Vec<_>>(),
        )?;
        write_array(
            &points,
            "frame_indices",
            &[scan.series.count()],
            &scan
                .series
                .entries
                .iter()
                .map(|e| e.frame as i64)
                .collect::<Vec<_>>(),
        )?;
        save_embedded(&scan.series, &g, "native_series")?;
        write_text_attr(&g,"native_selection",&json!({"index":scan.selected,"slot":scan.selected_slot,"normalization_coordinates":scan.normalization_coordinates}).to_string())?;
    } else {
        replace(group, "map")?;
    }
    Ok(())
}
fn read_map(
    s: &Session,
    g: &hdf5::Group,
    p: &Value,
    normalization: Option<&hdf5::Group>,
) -> Result<Scan, String> {
    let series = if g.link_exists("native_series") {
        load_embedded(&g.group("native_series").native()?)?
    } else {
        let x = g.dataset("pattern_x").native()?;
        let data = g.dataset("pattern_intensities").native()?;
        let shape = data.shape();
        if x.ndim() != 1
            || shape.len() != 2
            || shape[1] != x.size()
            || shape[0] == 0
            || shape[0] > 1_000_000
        {
            return Err("Invalid project map matrix.".into());
        }
        let paths = string_array(g, "filepaths")?;
        let points = g.group("point_infos").native()?;
        let filenames = string_array(&points, "filepaths")?;
        let frames = points
            .dataset("frame_indices")
            .native()?
            .read_raw::<i64>()
            .native()?;
        if filenames.len() != shape[0] || frames.len() != shape[0] || frames.iter().any(|f| *f < 0)
        {
            return Err("Invalid project map source positions.".into());
        }
        let entries = filenames
            .into_iter()
            .zip(frames)
            .map(|(path, frame)| Entry {
                path,
                frame: frame as usize,
            })
            .collect();
        let unit = read_text_attr(g, "pattern_unit")?.unwrap_or_else(|| s.settings.unit.clone());
        let mut series = Series::new(
            read_array(&x)?,
            read_array(&data)?,
            unit,
            s.settings
                .calibrated
                .then_some(s.settings.geometry.wavelength),
            entries,
            paths,
            shape[0],
        )?;
        if let Some(norm) = normalization {
            let original = norm.dataset("original").native()?;
            if original.shape() != shape {
                return Err("Map normalization source dimensions differ.".into());
            }
            let range = norm.attr("range").native()?.read_raw::<u64>().native()?;
            if range.len() != 2 {
                return Err("Invalid map normalization range.".into());
            }
            let reference = norm
                .attr("reference")
                .native()?
                .read_scalar::<u64>()
                .native()? as usize;
            series.raw = Arc::new(read_array(&original)?);
            series.normalize(true, [range[0] as usize, range[1] as usize], reference)?;
        }
        series
    };
    let mut scan = Scan::new(series, &s.patterns)?;
    let mut p = with_defaults("map", p);
    if let Ok(group) = g.group("params")
        && let Some(params) = read_json_attr(&group, "data")?
    {
        merge(&mut p, &params);
    }
    if let Some(dims) = p["dimension"].as_array() {
        if dims.len() != 2 {
            return Err("Invalid map dimensions.".into());
        }
        scan.dimension = [
            integer(&dims[0], "Map rows", 1, 4_000_000)?,
            integer(&dims[1], "Map columns", 1, 4_000_000)?,
        ];
    } else {
        let dims = g
            .dataset("dimension")
            .native()?
            .read_raw::<u64>()
            .native()?;
        if dims.len() != 2 {
            return Err("Invalid map dimensions.".into());
        }
        scan.dimension = [dims[0] as usize, dims[1] as usize];
    }
    if let Some(slots) = p["slots"].as_array() {
        if slots.len() > 4_000_000 {
            return Err("Map slots exceed four million cells.".into());
        }
        scan.slots = slots
            .iter()
            .map(|v| {
                if v.is_null() {
                    Ok(None)
                } else {
                    integer(v, "Map point", 0, scan.series.count() - 1).map(Some)
                }
            })
            .collect::<Result<_, _>>()?;
    }
    for (key, target) in [
        ("snake", &mut scan.snake),
        ("transpose", &mut scan.transpose),
        ("flip_horizontal", &mut scan.flip_horizontal),
        ("flip_vertical", &mut scan.flip_vertical),
    ] {
        *target = boolean(&p[key], key)?;
    }
    scan.active = text(&p["active_layer"]);
    if let Some(rois) = p["rois"].as_array().filter(|a| !a.is_empty()) {
        if rois.len() > 128 {
            return Err("Project has more than 128 map windows.".into());
        }
        scan.rois = rois
            .iter()
            .map(|r| {
                let name = r["name"]
                    .as_str()
                    .filter(|s| !s.is_empty() && s.len() <= 100)
                    .ok_or("Invalid map window name.")?
                    .to_string();
                let min = finite(&r["x_min"], "ROI minimum", -1e12, 1e12)?;
                let max = finite(&r["x_max"], "ROI maximum", -1e12, 1e12)?;
                let reduction = r["reduction"]
                    .as_str()
                    .filter(|r| ["sum", "mean", "max", "area", "center", "width"].contains(r))
                    .ok_or("Invalid map reduction.")?
                    .to_string();
                if min >= max {
                    return Err("Invalid map ROI bounds.".into());
                }
                Ok(Roi {
                    name,
                    min,
                    max,
                    reduction,
                    background: r["subtract_background"].as_bool().unwrap_or(false),
                    color: crate::pattern::color(&r["color"])?,
                })
            })
            .collect::<Result<_, String>>()?;
    } else {
        let range = read_array(&g.dataset("window").native()?)?;
        if range.len() != 2 {
            return Err("Invalid project map window.".into());
        }
        scan.rois[0].min = range[0];
        scan.rois[0].max = range[1];
    }
    if let Some(expressions) = p["expressions"].as_object() {
        if expressions.len() > 128 {
            return Err("Project has more than 128 expression layers.".into());
        }
        scan.expressions = expressions
            .iter()
            .map(|(key, v)| {
                Ok((
                    key.clone(),
                    v.as_str().ok_or("Invalid map expression.")?.into(),
                ))
            })
            .collect::<Result<_, String>>()?;
    }
    if let Some(excluded) = p["excluded_points"].as_array() {
        scan.excluded = excluded
            .iter()
            .map(|v| integer(v, "Excluded point", 0, scan.series.count() - 1))
            .collect::<Result<_, _>>()?;
    }
    let mut names = std::collections::BTreeSet::new();
    if scan
        .rois
        .iter()
        .map(|r| &r.name)
        .chain(scan.expressions.iter().map(|r| &r.0))
        .any(|n| !names.insert(n))
    {
        return Err("Map layer names must be unique.".into());
    }
    if let Some(meta) = read_json_attr(g, "native_selection")? {
        scan.selected = meta["index"].as_u64().map(|i| i as usize);
        scan.selected_slot = meta["slot"].as_u64().map(|i| i as usize);
        if scan.selected.is_some_and(|i| i >= scan.series.count()) {
            return Err("Invalid selected map point.".into());
        }
        scan.normalization_coordinates = meta["normalization_coordinates"].clone();
    }
    if let Some(norm) = normalization
        && let Some(coords) = read_json_attr(norm, "coordinates")?
    {
        scan.normalization_coordinates = coords;
    }
    scan.pending.clear();
    scan.rebuild(true, &s.patterns)?;
    Ok(scan)
}
pub(super) fn load_configuration(
    s: &mut Session,
    file: &hdf5::File,
    doc: &Value,
    index: usize,
    selected: usize,
) -> Result<(), String> {
    let base = format!("configurations/{index}");
    if file.link_exists(&format!("{base}/native_batch")) {
        s.batch = Some(load_embedded(
            &file.group(&format!("{base}/native_batch")).native()?,
        )?);
    } else if index == selected && file.link_exists("react_desktop_batch") {
        s.batch = Some(load_react_batch(
            &file.group("react_desktop_batch").native()?,
        )?);
    }
    if file.link_exists(&format!("{base}/map")) {
        let g = file.group(&format!("{base}/map")).native()?;
        let norm = if index == selected && file.link_exists("react_map_normalization") {
            Some(file.group("react_map_normalization").native()?)
        } else {
            None
        };
        s.scan = Some(read_map(s, &g, &doc["map"], norm.as_ref())?);
    }
    Ok(())
}
fn load_react_batch(g: &hdf5::Group) -> Result<Series, String> {
    let meta = read_json_attr(g, "metadata")?.ok_or("Missing desktop Batch metadata.")?;
    let x = g.dataset("binning").native()?;
    let data = g.dataset("data").native()?;
    let shape = data.shape();
    if x.ndim() != 1
        || shape.len() != 2
        || shape[1] != x.size()
        || shape[0] == 0
        || shape[0] > 1_000_000
    {
        return Err("Invalid desktop Batch matrix.".into());
    }
    let paths = if g.link_exists("files") {
        string_array(g, "files")?
    } else {
        vec![]
    };
    let mut entries = vec![
        Entry {
            path: String::new(),
            frame: 0
        };
        shape[0]
    ];
    for (i, e) in entries.iter_mut().enumerate() {
        e.frame = i;
    }
    if g.link_exists("pos_map") {
        let d = g.dataset("pos_map").native()?;
        if d.shape() != [shape[0], 2] {
            return Err("Invalid Batch source positions.".into());
        }
        let values = d.read_raw::<i64>().native()?;
        for (entry, row) in entries.iter_mut().zip(values.as_chunks::<2>().0) {
            if row[0] < 0 || row[1] < 0 {
                return Err("Invalid Batch source position.".into());
            }
            entry.path = paths
                .get(row[0] as usize)
                .ok_or("Batch source index is unavailable.")?
                .clone();
            entry.frame = row[1] as usize;
        }
    }
    let mut s = Series::new(
        read_array(&x)?,
        read_array(&data)?,
        text(&meta["unit"]),
        meta["wavelength"].as_f64(),
        entries,
        paths,
        meta["total"].as_u64().unwrap_or(shape[0] as u64) as usize,
    )?;
    if g.link_exists("file_map") {
        let counts = g.dataset("file_map").native()?.read_raw::<u64>().native()?;
        if counts.len() != s.paths.len() + 1
            || counts.first() != Some(&0)
            || counts.windows(2).any(|w| w[0] > w[1])
            || counts.last().copied().unwrap_or(0) > 1_000_000
        {
            return Err("Invalid stored Batch file map.".into());
        }
        s.file_counts = counts.windows(2).map(|w| (w[1] - w[0]) as usize).collect();
    }
    if g.link_exists("bkg") {
        let bg = g.dataset("bkg").native()?;
        if bg.shape() != shape {
            return Err("Batch background dimensions differ.".into());
        }
        s.background = Some(Arc::new(read_array(&bg)?));
        s.raw_background = s.background.clone();
    }
    s.selected = meta["selected"].as_u64().unwrap_or(0) as usize;
    if s.selected >= s.count() {
        return Err("Invalid Batch selection.".into());
    }
    s.calibration = text(&meta["calibration"]);
    s.mask = text(&meta["mask"]);
    if g.link_exists("counting_std") {
        s.sigma = Some(Arc::new(crate::series::read_std(
            &g.dataset("counting_std").native()?,
            &shape,
        )?));
        s.raw_sigma = s.sigma.clone();
    }
    if g.link_exists("azimuthal_std") {
        let d = g.dataset("azimuthal_std").native()?;
        if d.shape() != shape {
            return Err("Batch spread dimensions differ.".into());
        }
        s.spread = Some(Arc::new(read_array(&d)?));
        s.raw_spread = s.spread.clone();
    }
    if meta["normalized"] == true {
        let original = g.dataset("normalization_source/data").native()?;
        if original.shape() != shape {
            return Err("Batch normalization source dimensions differ.".into());
        }
        s.raw = Arc::new(read_array(&original)?);
        if s.sigma.is_some() {
            s.raw_sigma = Some(Arc::new(crate::series::read_std(
                &g.dataset("normalization_source/counting_std").native()?,
                &shape,
            )?));
        }
        if g.link_exists("normalization_source/spread") {
            let d = g.dataset("normalization_source/spread").native()?;
            if d.shape() != shape {
                return Err("Batch original spread dimensions differ.".into());
            }
            s.raw_spread = Some(Arc::new(read_array(&d)?));
        }
        let range = meta["normalization_range"]
            .as_array()
            .filter(|a| a.len() == 2)
            .ok_or("Invalid Batch normalization range.")?;
        let reference = integer(
            &meta["normalization_reference"],
            "Normalization reference",
            0,
            s.count() - 1,
        )?;
        let range = [
            integer(&range[0], "First normalization bin", 0, s.x.len() - 1)?,
            integer(&range[1], "Last normalization bin", 1, s.x.len())?,
        ];
        if range[0] >= range[1] {
            return Err("Invalid Batch normalization interval.".into());
        }
        if g.link_exists("normalization_source/background") {
            let bg = g.dataset("normalization_source/background").native()?;
            if bg.shape() != shape {
                return Err("Original Batch background dimensions differ.".into());
            }
            s.raw_background = Some(Arc::new(read_array(&bg)?));
        } else if let Some(bg) = &s.background {
            let means = s
                .raw
                .chunks_exact(s.x.len())
                .map(|row| {
                    row[range[0]..range[1]].iter().sum::<f64>() / (range[1] - range[0]) as f64
                })
                .collect::<Vec<_>>();
            s.raw_background = Some(Arc::new(
                bg.iter()
                    .enumerate()
                    .map(|(i, v)| v / (means[reference] / means[i / s.x.len()]))
                    .collect(),
            ));
        }
        s.normalize(true, range, reference)?;
    }
    Ok(s)
}
pub(super) fn save_active_extensions(s: &Session, file: &hdf5::File) -> Result<(), String> {
    replace(file, "react_desktop_batch")?;
    replace(file, "react_map_normalization")?;
    if let Some(b) = &s.batch {
        let g = file.create_group("react_desktop_batch").native()?;
        write_scalar_attr(&g, "version", 1_u32)?;
        write_array(&g, "data", &[b.count(), b.x.len()], &b.data)?;
        write_array(&g, "binning", &[b.x.len()], &b.x)?;
        if let Some(bg) = &b.background {
            write_array(&g, "bkg", &[b.count(), b.x.len()], bg)?;
        }
        if let Some(sigma) = &b.sigma {
            write_array(&g, "counting_std", &[b.count(), b.x.len()], sigma)?;
        }
        if let Some(spread) = &b.spread {
            write_array(&g, "azimuthal_std", &[b.count(), b.x.len()], spread)?;
        }
        let mut paths = b.paths.clone();
        for e in b.entries.iter() {
            if !paths.contains(&e.path) {
                paths.push(e.path.clone());
            }
        }
        write_strings(&g, "files", &paths)?;
        let positions = b
            .entries
            .iter()
            .flat_map(|e| {
                [
                    paths.iter().position(|p| *p == e.path).unwrap() as i64,
                    e.frame as i64,
                ]
            })
            .collect::<Vec<_>>();
        write_array(&g, "pos_map", &[b.count(), 2], &positions)?;
        let all_positions: Vec<i64> = paths
            .iter()
            .enumerate()
            .flat_map(|(i, p)| {
                (0..b
                    .file_counts
                    .get(i)
                    .copied()
                    .unwrap_or_else(|| b.entries.iter().filter(|e| e.path == *p).count()))
                    .flat_map(move |f| [i as i64, f as i64])
            })
            .collect();
        write_array(
            &g,
            "pos_map_all",
            &[all_positions.len() / 2, 2],
            &all_positions,
        )?;
        let mut map = vec![0_i64];
        for (i, p) in paths.iter().enumerate() {
            map.push(
                map.last().unwrap()
                    + b.file_counts
                        .get(i)
                        .copied()
                        .unwrap_or_else(|| b.entries.iter().filter(|e| e.path == *p).count())
                        as i64,
            );
        }
        write_array(&g, "file_map", &[map.len()], &map)?;
        let meta = json!({"unit":b.unit,"wavelength":b.wavelength,"selected":b.selected,"total":b.total,"raw":b.entries.iter().any(|e|Path::new(&e.path).is_file()),
            "calibration":b.calibration,"mask":b.mask,"mask_shape":s.image.as_ref().map(|i|i.shape),"normalized":b.normalized,"normalization_range":b.normalization,"normalization_reference":b.reference});
        write_text_attr(&g, "metadata", &meta.to_string())?;
        if b.normalized {
            let source = g.create_group("normalization_source").native()?;
            write_array(&source, "data", &[b.count(), b.x.len()], &b.raw)?;
            if let Some(bg) = &b.raw_background {
                write_array(&source, "background", &[b.count(), b.x.len()], bg)?;
            }
            if let Some(sigma) = &b.raw_sigma {
                write_array(&source, "counting_std", &[b.count(), b.x.len()], sigma)?;
            }
            if let Some(spread) = &b.raw_spread {
                write_array(&source, "spread", &[b.count(), b.x.len()], spread)?;
            }
            let means = b
                .raw
                .chunks_exact(b.x.len())
                .map(|row| {
                    row[b.normalization[0]..b.normalization[1]]
                        .iter()
                        .sum::<f64>()
                        / (b.normalization[1] - b.normalization[0]) as f64
                })
                .collect::<Vec<_>>();
            write_array(
                &source,
                "factors",
                &[b.count()],
                &means
                    .iter()
                    .map(|v| means[b.reference] / v)
                    .collect::<Vec<_>>(),
            )?;
        }
    }
    if let Some(map) = s.scan.as_ref().filter(|m| m.series.normalized) {
        let g = file.create_group("react_map_normalization").native()?;
        let b = &map.series;
        write_array(&g, "original", &[b.count(), b.x.len()], &b.raw)?;
        g.new_attr_builder()
            .with_data(&b.normalization.map(|n| n as u64))
            .create("range")
            .native()?;
        write_scalar_attr(&g, "reference", b.reference as u64)?;
        if !map.normalization_coordinates.is_null() {
            write_text_attr(
                &g,
                "coordinates",
                &map.normalization_coordinates.to_string(),
            )?;
        }
    }
    Ok(())
}
