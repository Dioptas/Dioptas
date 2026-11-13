//! Format-2 configuration params, owned arrays and React calibration metadata.
use super::*;
use crate::pattern::{Background, Curve, Overlay};
const GEOMETRY_KEYS: [&str; 7] = [
    "dist",
    "poni1",
    "poni2",
    "rot1",
    "rot2",
    "rot3",
    "wavelength",
];
fn optional_string(v: &Value) -> Option<String> {
    v.as_str().filter(|s| !s.is_empty()).map(str::to_string)
}
fn curve(file: &hdf5::File, x: &Value, y: &Value) -> Result<Option<Curve>, String> {
    let a = array(file, "payloads", x)?;
    let b = array(file, "payloads", y)?;
    match (a, b) {
        (None, None) => Ok(None),
        (Some((sx, x)), Some((sy, y))) if sx.len() == 1 && sy == sx => Ok(Some(Curve {
            x: Arc::new(x),
            y: Arc::new(y),
            sigma: None,
            spread: None,
        })),
        _ => Err("Project pattern arrays differ in shape or are missing.".into()),
    }
}
fn overlay_samples(
    file: &hdf5::File,
    key: &Value,
    count: usize,
) -> Result<Option<Arc<Vec<f64>>>, String> {
    array(file, "payloads", key)?
        .map(|(shape, values)| {
            if shape != [count] {
                return Err("Project overlay auxiliary arrays differ in shape.".into());
            }
            Ok(Arc::new(values))
        })
        .transpose()
}
pub(super) fn load_overlays(s: &mut Session, file: &hdf5::File, doc: &Value) -> Result<(), String> {
    let rows = doc["overlays"].as_array().cloned().unwrap_or_default();
    if rows.len() > 1000 {
        return Err("Project contains more than 1000 overlays.".into());
    }
    let mut ids = std::collections::BTreeSet::new();
    for (i, row) in rows.iter().enumerate() {
        let p = &row["params"];
        let data = curve(file, &row["x"], &row["y"])?.ok_or("Project overlay data is missing.")?;
        let source: Option<crate::batch_waterfall::Source> = p
            .get("desktop_batch_source")
            .filter(|v| !v.is_null())
            .map(|v| serde_json::from_value(v.clone()).map_err(|e| e.to_string()))
            .transpose()?;
        let n = data.x.len();
        let canonical = overlay_samples(file, &row["desktop_source_x"], n)?;
        if let Some(source) = &source {
            source.coordinates(canonical.as_deref().unwrap_or(&data.x), &s.patterns.unit)?;
        }
        let uid = p["uid"]
            .as_str()
            .map(str::to_string)
            .unwrap_or_else(|| format!("project-overlay-{i}"));
        if uid.is_empty() || !ids.insert(uid.clone()) {
            return Err("Project overlay IDs must be unique.".into());
        }
        let color = if p["color"].as_str().unwrap_or("").is_empty() {
            "#ffffff".into()
        } else {
            crate::pattern::color(&p["color"])?
        };
        s.patterns.overlays.push(Overlay {
            uid,
            name: text(&p["name"]),
            visible: p["visible"].as_bool().unwrap_or(true),
            color,
            scale: finite(
                p.get("scaling").unwrap_or(&json!(1)),
                "Overlay scale",
                -1e12,
                1e12,
            )?,
            offset: finite(
                p.get("offset").unwrap_or(&json!(0)),
                "Overlay offset",
                -1e12,
                1e12,
            )?,
            data: Arc::new(Curve {
                sigma: overlay_samples(file, &row["desktop_sigma"], n)?,
                spread: overlay_samples(file, &row["desktop_spread"], n)?,
                x: canonical.unwrap_or_else(|| data.x.clone()),
                ..data
            }),
            batch_source: source,
        });
    }
    s.patterns.project_overlay_ids();
    s.patterns.separation = doc["view"]["waterfall_separation"]
        .as_f64()
        .unwrap_or(crate::waterfall_spacing::DEFAULT_SPACING);
    Ok(())
}
pub(super) fn save_overlays(
    s: &Session,
    payloads: &hdf5::Group,
    document: &mut Value,
) -> Result<(), String> {
    let old = document["overlays"].as_array().cloned().unwrap_or_default();
    let mut rows = vec![];
    for o in &s.patterns.overlays {
        let mut row = old
            .iter()
            .find(|r| r["params"]["uid"] == o.uid)
            .cloned()
            .unwrap_or(json!({}));
        if !row["params"].is_object() {
            row["params"] = json!({});
        }
        merge(
            &mut row["params"],
            &json!({"uid":o.uid,"name":o.name,"color":o.color,"visible":o.visible,"scaling":o.scale,"offset":o.offset,"desktop_batch_source":o.batch_source}),
        );
        let displayed = o.curve(&s.patterns.unit)?;
        row["x"] = put(payloads, &[displayed.x.len()], &displayed.x)?;
        if o.batch_source.is_some() {
            row["desktop_source_x"] = put(payloads, &[o.data.x.len()], &o.data.x)?;
        }
        row["y"] = put(payloads, &[o.data.y.len()], &o.data.y)?;
        if let Some(v) = &o.data.sigma {
            row["desktop_sigma"] = put(payloads, &[v.len()], v)?;
        }
        if let Some(v) = &o.data.spread {
            row["desktop_spread"] = put(payloads, &[v.len()], v)?;
        }
        rows.push(row);
    }
    document["overlays"] = json!(rows);
    document["view"] = with_defaults("view", &document["view"]);
    document["view"]["waterfall_separation"] = json!(s.patterns.separation);
    Ok(())
}
pub(super) fn desktop_metadata(s: &Session) -> Value {
    json!({"version":1,"combination":{"patterns":s.combination.patterns,"cakes":s.combination.cakes,"cake_source_unit":s.combination.cake.as_ref().and_then(|c|c.metadata["unit"].as_str()).or(s.combination.cake_source_unit.as_deref())},"calibrant":s.calibration.reference.name,"fit_dirty":s.calibration.dirty,"rms_degrees":s.calibration.rms,
        "custom_calibrant":s.calibration.custom.as_ref().map(|r|json!({"name":r.name,"content":r.content})),"setup_confirmed":s.calibration.confirmed,"calibrant_chosen":s.calibration.reference_chosen,
        "workflow":s.workflow,"geometry_source":s.calibration.source})
}
fn geometry(p: &Value) -> Result<Geometry, String> {
    let g = &p["geometry"];
    let config = &g["detector_config"];
    if let Some(version) = g.get("poni_version")
        && !version.as_f64().is_some_and(|v| [1., 2., 2.1].contains(&v))
    {
        return Err("Unsupported project PONI geometry version.".into());
    }

    let mut v = json!({});
    let fallback = Geometry::default();
    let fallback = serde_json::to_value(fallback).map_err(|e| e.to_string())?;
    for key in GEOMETRY_KEYS {
        v[key] = g
            .get(key)
            .or_else(|| p["start_values"].get(key))
            .cloned()
            .unwrap_or_else(|| fallback[key].clone());
    }
    for key in ["pixel1", "pixel2"] {
        v[key] = config
            .get(key)
            .cloned()
            .unwrap_or_else(|| fallback[key].clone());
    }
    v["polarization_factor"] = p["polarization_factor"].clone();
    let (mut geometry, _) = Geometry::manual(&v)?;
    let name = optional_string(&p["detector_name"])
        .or_else(|| optional_string(&g["detector"]))
        .unwrap_or("Detector".into());
    if name != "Detector" && name != "Custom" && name != "NexusDetector" {
        geometry.select_detector(&name)?;
    }
    let detector_path =
        optional_string(&p["detector_filename"]).or_else(|| optional_string(&config["filename"]));
    if name == "NexusDetector" && detector_path.is_none() {
        return Err("Project NeXus detector filename is missing.".into());
    }
    if let Some(path) = detector_path {
        geometry.load_detector_file(Path::new(&path))?;
    }
    if let Some(path) = optional_string(&p["distortion_spline_filename"])
        .or_else(|| optional_string(&config["splineFile"]))
        .or_else(|| optional_string(&config["splinefile"]))
    {
        geometry.load_spline(Path::new(&path))?;
    }
    if config
        .get("orientation")
        .is_some_and(|v| v.as_u64() != Some(3))
        || geometry.detector.is_some()
    {
        let d = geometry.detector.get_or_insert_with(|| {
            Arc::new(dioptrin::detector::Detector::custom(
                geometry.pixel1,
                geometry.pixel2,
            ))
        });
        let d = Arc::make_mut(d);
        d.orientation = match config.get("orientation") {
            None => 3,
            Some(value) => value
                .as_u64()
                .filter(|v| *v <= 4)
                .ok_or("Invalid detector orientation.")? as u8,
        };
    }
    if let Some(fields) = config.as_object() {
        for (key, value) in fields {
            if [
                "pixel1",
                "pixel2",
                "orientation",
                "max_shape",
                "filename",
                "splineFile",
                "splinefile",
            ]
            .contains(&key.as_str())
                || (key == "sensor" && value.is_null())
            {
                continue;
            }
            if !geometry
                .detector
                .as_ref()
                .is_some_and(|d| d.config.get(key) == Some(value))
            {
                return Err(format!(
                    "Project detector option {key} is not a supported factory value; its geometry must not be discarded."
                ));
            }
        }
    }
    if let Some(fields) = g.as_object() {
        for (key, value) in fields {
            if [
                "poni_version",
                "dist",
                "poni1",
                "poni2",
                "rot1",
                "rot2",
                "rot3",
                "wavelength",
                "detector",
                "detector_config",
            ]
            .contains(&key.as_str())
                || (key == "parallax" && value.is_null())
            {
                continue;
            }
            return Err(format!(
                "Project geometry option {key} is unsupported; its geometry must not be discarded."
            ));
        }
    }
    if let (Some(d), Some(shape)) = (
        &geometry.detector,
        config.get("max_shape").filter(|v| !v.is_null()),
    ) {
        let shape: [usize; 2] =
            serde_json::from_value(shape.clone()).map_err(|_| "Invalid project detector shape.")?;
        if d.name != "Detector" && d.max_shape != Some(shape) {
            return Err("Project shape differs from its detector definition.".into());
        }
    }
    let declared = [
        config.get("pixel1").and_then(Value::as_f64),
        config.get("pixel2").and_then(Value::as_f64),
    ];
    if declared.iter().any(Option::is_some) {
        geometry.frame_pixels = Some(declared);
    }
    geometry.validate()?;
    Ok(geometry)
}
pub(super) fn load(
    s: &mut Session,
    file: &hdf5::File,
    doc: &Value,
    desktop: &Value,
    index: usize,
    selected: usize,
    origins: &mut super::series_arrays::Origins,
) -> Result<(), String> {
    let p = with_defaults("params", &doc["params"]);
    let img = with_defaults("img", &doc["img"]);
    let cal = with_defaults("calibration", &doc["calibration"]);
    let pat = with_defaults("pattern", &doc["pattern"]);
    let mask = with_defaults("mask", &doc["mask"]);
    s.settings.transformations = crate::transform::parse(&img["transformations"])?;
    s.processing.factor = finite(&img["factor"], "Image scale factor", -1e12, 1e12)?;
    s.settings.geometry = if let Some(saved) = doc["native_desktop"].get("physical_geometry") {
        let mut saved = saved.clone();
        let detector = saved
            .get_mut("detector")
            .map(Value::take)
            .unwrap_or(Value::Null);
        let mut g: Geometry = serde_json::from_value(saved).map_err(|e| e.to_string())?;
        g.detector = decode_detector(file, &detector)?;
        g.validate()?;
        g
    } else {
        geometry(&cal)?
    };
    if doc["native_desktop"].get("physical_geometry").is_none()
        && !s.settings.transformations.is_empty()
        && s.settings.geometry.detector.is_some()
    {
        return Err("This legacy Qt project has a transformed detector without an owned physical model. Export its detector geometry to NeXus or use the Qt project until that compatibility case is qualified.".into());
    }
    s.settings.original_detector =
        decode_detector(file, &doc["native_desktop"]["original_detector"])?;
    s.settings.original_pixels = if doc["native_desktop"]
        .get("original_pixel_sizes")
        .is_some_and(Value::is_null)
    {
        None
    } else if let Some(p) = doc["native_desktop"]["original_pixel_sizes"].as_array() {
        if p.len() != 2 {
            return Err("Invalid original detector pixel sizes.".into());
        }
        let pixels = [
            finite(&p[0], "Pixel size", 0., f64::MAX)?,
            finite(&p[1], "Pixel size", 0., f64::MAX)?,
        ];
        if pixels.iter().any(|v| *v <= 0.) {
            return Err("Original detector pixel sizes must be positive.".into());
        }
        Some(pixels)
    } else {
        // Older writers do not store the detector's reset snapshot. Keep
        // their saved geometry authoritative, as the existing reader does.
        None
    };
    s.mask_mode = boolean(&mask["mode"], "Mask mode")?;
    s.settings.calibrated = boolean(&cal["is_calibrated"], "Calibrated")?;
    s.settings.calibration_name = optional_string(&cal["calibration_name"]);
    s.settings.calibration_path = optional_string(&cal["poni_filename"]);
    let options = doc["native_desktop"]["reader_options"]
        .as_object()
        .map(|v| Value::Object(v.clone()))
        .unwrap_or(json!({}));
    let frame = integer(&img["series_pos"], "Project frame", 1, 1_000_000)? - 1;
    let frames = integer(
        doc.get("series_max").unwrap_or(&json!(1)),
        "Project frame count",
        1,
        1_000_000,
    )?;
    if let Some((shape, values)) = array(file, "cache", &doc["image_data"])? {
        let shape = <[usize; 2]>::try_from(shape)
            .map_err(|_| "Project detector cache must be two dimensional.")?;
        s.publish_image(Image::from_cached(
            PathBuf::from(text(&img["filename"])),
            frame,
            frames,
            shape,
            values,
            options,
        )?)?;
    } else if !text(&img["filename"]).is_empty() {
        let mut options = options;
        options["frame"] = json!(frame);
        s.publish_image(Image::open(
            Path::new(img["filename"].as_str().unwrap()),
            &options,
        )?)?;
    }
    if let Some(image) = s.image.as_mut() {
        if let Some(sources) = doc["native_desktop"].get("image_sources") {
            image.sources = serde_json::from_value(sources.clone()).map_err(|e| e.to_string())?;
        }
        image.automatic_source = doc["native_desktop"]["automatic_image_source"]
            .as_bool()
            .unwrap_or(false);
        image.source_discovery_error =
            optional_string(&doc["native_desktop"]["image_source_error"]);
    }
    if let Some((dims, values)) = array(file, "cache", &doc["native_desktop"]["source_variance"])? {
        let image = s
            .image
            .as_mut()
            .ok_or("Project variances require an image.")?;
        if dims != image.source_shape || values.iter().any(|v| !v.is_finite() || *v < 0.0) {
            return Err("Invalid project source variances.".into());
        }
        image.source_variance = Some(Arc::new(values));
    }
    let shape = s.image.as_ref().map(|i| i.shape);
    let mut settings = json!({"unit":p["integration_unit"],"bins":p["integration_rad_points"],"cake_bins":p["cake_azimuth_points"],
        "use_mask":p["use_mask"],"transparent_mask":p["transparent_mask"],"polarization":cal["polarization_factor"],"poisson_errors":p["calculate_poisson_errors"],
        "solid_angle":cal["correct_solid_angle"],"supersampling":cal["supersampling_factor"],"trim_zeros":p["trim_trailing_zeros"],
        "azimuthal_std":p["calculate_azimuthal_std"],"spottiness_relative":p["spottiness_relative"].as_bool().unwrap_or(false),"azimuth_range":p["oned_azimuth_range"],"cake_azimuth_range":p["cake_azimuth_range"],
        "formats":p["integrated_patterns_file_formats"],"defer_integration":true});
    if let Some(method) = doc["native_desktop"].get("integration_method") {
        settings["method"] = method.clone();
    }
    settings["sparse_layout"] = doc["native_desktop"]
        .get("sparse_layout")
        .cloned()
        .unwrap_or_else(|| json!("csr"));
    s.dispatch("integration_settings", &settings)?;
    s.processing.factor = finite(&img["factor"], "Image scale factor", -1e12, 1e12)?;
    if let Some(shape) = shape {
        if let Some(drafts) = doc["native_desktop"]["correction_drafts"].as_object() {
            for kind in ["cbn", "oiadac", "plate", "slab", "cylinder", "sphere"] {
                if let Some(draft) = drafts.get(kind) {
                    let mut args = json!({"kind":kind,"enabled":draft["enabled"],"parameters":draft["parameters"]});
                    if let Some(material) = draft.get("material") {
                        args["material"] = material.clone();
                    }
                    if let Some(container) = draft.get("container") {
                        args["container"] = container.clone();
                    }
                    s.processing.correction(&args, s.settings.calibrated)?;
                }
            }
        }
        if let Some((dims, values)) = array(file, "payloads", &doc["mask_data"])? {
            if dims != shape {
                return Err("Project mask dimensions differ from the image.".into());
            }
            s.mask = Arc::new(values.iter().map(|v| u8::from(*v != 0.0)).collect());
        }
        if !mask["roi"].is_null() {
            let a = mask["roi"]
                .as_array()
                .filter(|v| v.len() == 4)
                .ok_or("Invalid project ROI.")?;
            let mut roi = [0; 4];
            for i in 0..4 {
                roi[i] = integer(&a[i], "Project ROI", 0, shape[if i < 2 { 0 } else { 1 }])?;
            }
            if roi[0] >= roi[1] || roi[2] >= roi[3] {
                return Err("Invalid project ROI bounds.".into());
            }
            s.settings.roi = Some(roi);
        }
        let source_shape = s.image.as_ref().unwrap().source_shape;
        if let Some((dims, values)) = array(file, "cache", &doc["background_data"])? {
            if dims != source_shape {
                return Err("Project background dimensions differ from the image.".into());
            }
            s.processing.restore_background(
                text(&img["background_filename"]),
                source_shape,
                values,
            );
        } else if !text(&img["background_filename"]).is_empty() {
            s.processing
                .background(&json!({"path":img["background_filename"]}), source_shape)?;
        }
        s.processing.scale = finite(&img["background_scaling"], "Background scale", -1e12, 1e12)?;
        s.processing.offset = finite(&img["background_offset"], "Background offset", -1e12, 1e12)?;
        if let Some(poisson) = doc["native_desktop"].get("background_poisson") {
            s.processing
                .background(&json!({"poisson":poisson}), source_shape)?;
        }
        let transfer = &doc["native_desktop"]["transfer"];
        // Native projects retain disabled and partially loaded reference pairs.
        // Legacy active transfer corrections own the same source planes in cache.
        let legacy = &img["corrections"]["transfer"];
        let matching_cache = transfer.is_object()
            && (!legacy.is_object()
                || ["original_filename", "response_filename"]
                    .iter()
                    .all(|key| legacy[key] == transfer[key]));
        let saved = if matching_cache { transfer } else { legacy };
        if saved.is_object() {
            for source in ["original", "response"] {
                let data_key = format!("{source}_data");
                let path_key = format!("{source}_filename");
                if let Some((dims, values)) = array(file, "cache", &saved[&data_key])? {
                    if dims != source_shape {
                        return Err(
                            "Project transfer reference dimensions differ from the image.".into(),
                        );
                    }
                    s.processing.restore_transfer(
                        source,
                        text(&saved[&path_key]),
                        source_shape,
                        values,
                    )?;
                } else if let Some(path) = saved[&path_key].as_str().filter(|p| !p.is_empty()) {
                    s.processing
                        .transfer(&json!({"source":source,"path":path}), source_shape)?;
                }
            }
            s.processing
                .transfer(&json!({"enabled":legacy.is_object()}), source_shape)?;
        }
        if let Some(corrections) = img["corrections"].as_object() {
            for (name, parameters) in corrections {
                match name.as_str() {
                    "cbn" | "oiadac" | "plate" | "slab" | "cylinder" | "sphere" => {
                        let mut parameters = parameters.clone();
                        if name == "cbn"
                            && let Some(value) = parameters
                                .as_object_mut()
                                .unwrap()
                                .remove("seat_abs_length")
                        {
                            parameters["cbn_abs_length"] = value;
                        }
                        let mut args = json!({"kind":name,"enabled":true,"parameters":parameters});
                        if name == "cylinder"
                            && doc["native_desktop"]["correction_drafts"]["cylinder"]["container"]["enabled"]
                                == false
                            && parameters["container_absorption_coefficient"] == 0.0
                        {
                            // The legacy active correction stores zero when the wall is
                            // disabled. Retain its native manual coefficient for re-enable.
                            args["parameters"]["container_absorption_coefficient"] = doc["native_desktop"]["correction_drafts"]["cylinder"]["parameters"]["container_absorption_coefficient"].clone();
                        }

                        if name == "cylinder"
                            && doc["native_desktop"]["correction_drafts"]["cylinder"]
                                .get("container")
                                .is_none()
                        {
                            args["container"] = json!({"enabled":parameters["container_absorption_coefficient"].as_f64().unwrap_or(0.)>0. && parameters["wall_thickness"].as_f64().unwrap_or(0.)>0.});
                        }
                        s.processing.correction(&args, s.settings.calibrated)?;
                    }
                    "transfer" => {} // Restored above, including its owned reference images.
                    "flat_field" => {
                        let flat = array(file, "cache", &doc["native_desktop"]["flat_response"])?;
                        if let Some((dims, values)) = flat {
                            if dims != source_shape {
                                return Err(
                                    "Project flat-field dimensions differ from the image.".into()
                                );
                            }
                            s.processing.restore_flat(
                                text(&parameters["filename"]),
                                source_shape,
                                values,
                                true,
                            )?;
                        } else {
                            s.processing.flat_field(
                                &json!({"path":parameters["filename"]}),
                                source_shape,
                            )?;
                        }
                    }
                    _ => {
                        return Err(format!(
                            "Project image correction {name} is not migrated; it must not be ignored."
                        ));
                    }
                }
            }
        }
        if img["corrections"].get("flat_field").is_none()
            && let Some((dims, values)) =
                array(file, "cache", &doc["native_desktop"]["flat_response"])?
        {
            if dims != source_shape {
                return Err("Project flat-field dimensions differ from the image.".into());
            }
            s.processing.restore_flat(
                text(&doc["native_desktop"]["flat_filename"]),
                source_shape,
                values,
                false,
            )?;
        }
        if let Some(plugins) = doc["plugins"].as_object() {
            for (name, p) in plugins {
                if !s
                    .plugins
                    .details()
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|p| p["name"] == *name)
                {
                    if p["enabled"] == true {
                        return Err(format!("Project plugin {name} is not migrated."));
                    } else {
                        continue;
                    }
                }
                if p["enabled"] == true || p["settings"].as_object().is_some_and(|v| !v.is_empty())
                {
                    s.plugins
                        .edit(name, Some(&p["enabled"]), Some(&p["settings"]))?;
                }
            }
        }
    } else if !doc["mask_data"].is_null() {
        // An empty configuration may carry the default 2048² blank mask. Its
        // original dataset is retained in the archive until an image is loaded.
        let _ = array(file, "payloads", &doc["mask_data"])?;
    }
    s.files.image_mode = text(&img["file_iteration_mode"]);
    for (key, target) in [
        ("image", &mut s.files.image_directory),
        ("pattern", &mut s.files.output_directory),
    ] {
        let path = text(&p["working_directories"][key]);
        if Path::new(&path).is_dir() {
            *target = path;
        }
    }
    s.patterns.directory = text(&p["working_directories"]["overlay"]);
    s.settings.auto_save = false;
    s.files.auto_process = false;
    s.patterns.name = Path::new(img["filename"].as_str().unwrap_or(""))
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy()
        .into_owned();
    s.patterns.color = crate::pattern::color(&pat["color"])?;
    s.patterns.visible = boolean(&pat["visible"], "Pattern visible")?;
    s.patterns.unit = if pat["unit"].as_str().is_none_or(str::is_empty) {
        s.settings.unit.clone()
    } else {
        text(&pat["unit"])
    };
    s.patterns.imported = pat["pattern_source"] == "file";
    s.patterns.path = optional_string(&pat["pattern_filename"]);
    s.patterns.file_mode = text(&pat["file_iteration_mode"]);
    if s.patterns.imported {
        s.patterns.name = Path::new(s.patterns.path.as_deref().unwrap_or(""))
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned();
    }
    s.patterns.background = Background::from_value(json!({
        "enabled":pat["auto_bkg_enabled"],
        "smoothing":pat["auto_bkg_smoothing"],
        "iterations":pat["auto_bkg_iterations"],
        "order":pat["auto_bkg_poly_order"],
        "range":pat["auto_bkg_roi"],
    }))?;
    s.patterns.background_uid = optional_string(&pat["background_overlay_uid"]);
    if let Some(uid) = &s.patterns.background_uid
        && !s.patterns.overlays.iter().any(|o| o.uid == *uid)
    {
        return Err("Project background refers to a missing overlay.".into());
    }
    if !doc["anonymous_background"].is_null() {
        let a = &doc["anonymous_background"];
        let data = curve(file, &a["x"], &a["y"])?.ok_or("Anonymous background data is missing.")?;
        s.patterns.anonymous_background = Some(Arc::new(data));
        s.patterns.background_uid = None;
    }
    if let Some(mut raw) = curve(file, &doc["pattern_x"], &doc["pattern_y"])? {
        for (name, target) in [
            ("pattern_errors", &mut raw.sigma),
            ("pattern_azimuthal_std", &mut raw.spread),
        ] {
            if let Some((shape, data)) = array(file, "payloads", &doc[name])? {
                if shape != [raw.x.len()] {
                    return Err("Project uncertainty arrays differ from pattern samples.".into());
                }
                *target = Some(Arc::new(data));
            }
        }
        s.patterns.raw = Some(Arc::new(raw));
    }
    let local = &doc["native_desktop"];
    let metadata = if local["calibration"].is_object() {
        &local["calibration"]
    } else if index == selected {
        desktop
    } else {
        &Value::Null
    };
    restore_calibration(s, &cal, metadata)?;
    if let Some(mode) = local["image_batch_mode"]
        .as_str()
        .filter(|m| ["integrate", "add", "average", "save"].contains(m))
    {
        s.image_batch_mode = mode.into();
    }
    s.mask_filename = optional_string(&local["mask_filename"]);
    series::load_configuration(s, file, doc, index, selected, origins)?;
    if let Some(image) = &s.image {
        s.settings.geometry.sync_shape(image.shape)?;
    }
    s.prepare_processing()?;
    s.refresh_masks(&s.control.clone())?;
    let stored = s.patterns.raw.clone();
    let stored_unit = s.patterns.unit.clone();
    let stored_name = s.patterns.name.clone();
    #[cfg(feature = "dioptrin")]
    if s.image.is_some() && s.settings.calibrated && !s.patterns.imported {
        s.calculate(false)?;
    } else {
        s.rebuild_pattern()?;
    }
    #[cfg(not(feature = "dioptrin"))]
    s.rebuild_pattern()?;
    if doc["native_desktop"]["version"] == 1 && stored.is_some() {
        s.patterns.raw = stored;
        s.patterns.unit = stored_unit;
        s.patterns.name = local["pattern_name"]
            .as_str()
            .unwrap_or(&stored_name)
            .into();
        s.rebuild_pattern()?;
    }
    Ok(())
}
fn restore_calibration(s: &mut Session, cal: &Value, meta: &Value) -> Result<(), String> {
    let c = &mut s.calibration;
    if let Some(custom) = meta.get("custom_calibrant").filter(|v| !v.is_null()) {
        c.custom = Some(calibration::Reference::parse(
            custom["name"]
                .as_str()
                .ok_or("Custom calibrant name is missing.")?,
            custom["content"]
                .as_str()
                .ok_or("Custom calibrant content is missing.")?,
        )?);
    }
    if let Some(name) = meta["calibrant"].as_str() {
        c.reference = c.choose(name)?;
    }
    c.reference_chosen = meta["calibrant_chosen"].as_bool().unwrap_or(false);
    for (i, key) in GEOMETRY_KEYS.iter().enumerate() {
        let live = s.settings.geometry.manual_values(s.settings.polarization);
        c.start[i] = cal["fixed_values"]
            .get(key)
            .or_else(|| cal["start_values"].get(key))
            .unwrap_or(&live[key])
            .as_f64()
            .filter(|v| v.is_finite())
            .ok_or("Invalid project fit start values.")?;
        c.free[i] = cal["fixed_values"].get(key).is_none();
    }
    c.free[6] = cal["fit_wavelength"].as_bool().unwrap_or(false);
    c.reference_wavelength = s.settings.geometry.wavelength;
    c.confirmed = meta["setup_confirmed"]
        .as_bool()
        .unwrap_or(s.settings.calibrated);
    c.dirty = meta["fit_dirty"].as_bool().unwrap_or(false);
    c.rms = meta["rms_degrees"]
        .as_f64()
        .filter(|v| v.is_finite() && *v >= 0.0);
    c.source = meta["geometry_source"]
        .as_str()
        .unwrap_or(if s.settings.calibrated {
            "loaded"
        } else {
            "none"
        })
        .into();
    c.saved = !c.dirty && s.settings.calibration_path.is_some();
    if let Some(picks) = cal["peak_selections"].as_array() {
        if picks.len() > 100_000 {
            return Err("Project contains too many picked groups.".into());
        }
        let mut total = 0;
        for group in picks {
            let a = group
                .as_array()
                .filter(|a| a.len() == 2)
                .ok_or("Invalid project peak group.")?;
            let ring = integer(
                &a[0],
                "Picked ring",
                0,
                c.reference.spacings.len().saturating_sub(1),
            )? + 1;
            let points = a[1].as_array().ok_or("Invalid project peak points.")?;
            total += points.len();
            if total > 100_000 {
                return Err("Project contains too many picked points.".into());
            }
            let mut positions = vec![];
            for point in points {
                let p = point
                    .as_array()
                    .filter(|p| p.len() == 2)
                    .ok_or("Invalid picked point.")?;
                let (y, x) = (
                    finite(&p[0], "Peak row", 0.0, 1e6)?,
                    finite(&p[1], "Peak column", 0.0, 1e6)?,
                );
                if let Some(image) = &s.image
                    && (x >= image.shape[1] as f64 || y >= image.shape[0] as f64)
                {
                    return Err("Picked point lies outside the project detector.".into());
                }
                positions.push([y, x]);
            }
            c.picks.push(calibration::Group {
                ring,
                points: positions,
            });
        }
    }
    if meta["workflow"].is_object() {
        let mut workflow = serde_json::to_value(&s.workflow).map_err(|e| e.to_string())?;
        merge(&mut workflow, &meta["workflow"]);
        s.workflow = serde_json::from_value(workflow).map_err(|e| e.to_string())?;
        if !["Massif", "Blob"].contains(&s.workflow.algorithm.as_str())
            || s.workflow.search_size == 0
            || s.workflow.search_size > 1000
            || s.workflow.number_of_rings > 10000
            || !s.workflow.delta_tth.is_finite()
            || s.workflow.delta_tth <= 0.0
            || !s.workflow.mean_factor.is_finite()
            || !s.workflow.intensity_limit.is_finite()
        {
            return Err("Invalid project calibration workflow.".into());
        }
    }
    Ok(())
}
pub(super) fn save(
    c: &Configuration,
    group: &hdf5::Group,
    payloads: &hdf5::Group,
    cache: &hdf5::Group,
    arrays: &mut super::series_arrays::Writer,
) -> Result<Value, String> {
    let s = &c.state;
    let settings = &s.settings;
    let mut doc = c.document.as_ref().clone();
    if !doc.is_object() {
        doc = json!({});
    }
    for kind in ["params", "img", "calibration", "pattern", "mask", "map"] {
        doc[kind] = with_defaults(kind, &doc[kind]);
    }
    let p = &mut doc["params"];
    merge(
        p,
        &json!({"use_mask":settings.use_mask,"transparent_mask":settings.transparent_mask,"integration_unit":settings.unit,
        "integration_rad_points":if settings.automatic_binning{Value::Null}else{json!(settings.bins)},"oned_azimuth_range":settings.azimuth,
        "cake_azimuth_range":settings.cake_azimuth,"cake_azimuth_points":settings.cake_bins,"trim_trailing_zeros":settings.trim_zeros,
        "calculate_poisson_errors":settings.errors,"calculate_azimuthal_std":settings.spread,"spottiness_relative":settings.spottiness_relative,"auto_save_integrated_pattern":settings.auto_save,
        "integrated_patterns_file_formats":settings.formats}),
    );
    for (key, value) in [
        ("image", &s.files.image_directory),
        ("pattern", &s.files.output_directory),
        ("overlay", &s.patterns.directory),
    ] {
        p["working_directories"][key] = json!(value);
    }
    let image = s.image.as_ref();
    merge(
        &mut doc["img"],
        &json!({"filename":image.map(|i|&i.path).unwrap_or(&PathBuf::new()),"series_pos":image.map_or(1,|i|i.frame+1),
        "autoprocess":s.files.auto_process,"file_iteration_mode":s.files.image_mode,"factor":s.processing.factor,"transformations":settings.transformations,
        "background_scaling":s.processing.scale,"background_offset":s.processing.offset}),
    );
    doc["series_max"] = json!(image.map_or(1, |i| i.frames));
    doc["image_data"] = if let Some(image) = image {
        put(cache, &image.source_shape, &image.source_values)?
    } else {
        Value::Null
    };
    if let Some((path, shape, values)) = s.processing.project_background() {
        doc["background_data"] = put(cache, &shape, values)?;
        doc["img"]["background_filename"] = json!(path);
    } else {
        doc["background_data"] = Value::Null;
        doc["img"]["background_filename"] = json!("");
    }
    doc["mask_data"] = if let Some(image) = image {
        put(
            payloads,
            &image.shape,
            &s.mask.iter().map(|v| f64::from(*v)).collect::<Vec<_>>(),
        )?
    } else {
        doc.get("mask_data").cloned().unwrap_or(Value::Null)
    };
    doc["mask"]["roi"] = json!(settings.roi);
    doc["mask"]["mode"] = json!(s.mask_mode);
    let g = &settings.geometry;
    let geometry = json!({"poni_version":2.1,"dist":g.dist,"poni1":g.poni1,"poni2":g.poni2,"rot1":g.rot1,"rot2":g.rot2,"rot3":g.rot3,
        "wavelength":g.wavelength,"detector":g.detector.as_ref().map(|d|d.name.as_str()).unwrap_or("Detector"),"detector_config":{"pixel1":g.pixel1,"pixel2":g.pixel2,"orientation":g.detector.as_ref().map(|d|d.orientation).unwrap_or(3),"max_shape":g.detector.as_ref().and_then(|d|d.max_shape)}});
    let mut start = json!({"polarization_factor":settings.polarization});
    let mut fixed = json!({});
    for (i, key) in GEOMETRY_KEYS.iter().enumerate() {
        start[key] = json!(s.calibration.start[i]);
        if !s.calibration.free[i] {
            fixed[key] = json!(s.calibration.start[i]);
        }
    }
    merge(
        &mut doc["calibration"],
        &json!({"start_values":start,"fixed_values":fixed,"fit_wavelength":s.calibration.free[6],"use_mask":settings.use_mask,
        "polarization_factor":settings.polarization,"supersampling_factor":settings.supersampling,"correct_solid_angle":settings.solid_angle,
        "detector_mode":if g.detector_file.is_some(){2}else if g.detector.as_ref().is_some_and(|d|d.name!="Detector"){3}else{1},"detector_name":g.detector.as_ref().map(|d|d.name.as_str()).unwrap_or(""),"detector_filename":g.detector_file.as_deref().unwrap_or(""),"distortion_spline_filename":g.distortion_file,"geometry":geometry,"is_calibrated":settings.calibrated,"poni_filename":settings.calibration_path.as_deref().unwrap_or(""),
        "calibration_name":settings.calibration_name.as_deref().unwrap_or(""),"peak_selections":s.calibration.picks.iter().map(|p|json!([p.ring-1,p.points])).collect::<Vec<_>>()}),
    );
    let processing = s.processing.details();
    let mut corrections = json!({});
    for kind in ["cbn", "oiadac", "plate", "slab", "cylinder", "sphere"] {
        if processing["corrections"][kind]["enabled"] == true {
            let mut parameters = processing["corrections"][kind]["parameters"].clone();
            if kind == "oiadac" {
                // The Qt format requires these keys. Export calibration-derived
                // values for its older approximate model; native readers use
                // physical geometry and never restore them as overrides.
                let fit2d = dioptrin::fit2d::Fit2d::from_poni(&g.native_poni());
                parameters["tilt"] = json!(fit2d.tilt);
                parameters["rotation"] = json!(fit2d.tilt_plane_rotation);
            }
            if kind == "cbn"
                && let Some(value) = parameters.as_object_mut().unwrap().remove("cbn_abs_length")
            {
                parameters["seat_abs_length"] = value;
            }
            if kind == "cylinder" && processing["corrections"][kind]["container"]["enabled"] != true
            {
                parameters["container_absorption_coefficient"] = json!(0.);
            }
            corrections[kind] = parameters;
        }
    }
    let mut native = doc["native_desktop"].clone();
    if !native.is_object() {
        native = json!({});
    }
    merge(
        &mut native,
        &json!({"version":1,"sparse_layout":if settings.auto_layout {"auto"}else if settings.csc {"csc"}else{"csr"},"integration_method":if settings.pyfai_splitting {"pyfai_full"} else if settings.supersampling>1 {"subpixel"} else {"polygon"},"original_pixel_sizes":settings.original_pixels,"pattern_name":s.patterns.name,"correction_drafts":processing["corrections"],"label":c.label,"reader_options":image.map(|i|&i.options),"image_sources":image.map(|i|&i.sources).cloned().unwrap_or_default(),"automatic_image_source":image.is_some_and(|i|i.automatic_source),"image_source_error":image.and_then(|i|i.source_discovery_error.as_ref()),"mask_filename":s.mask_filename,"image_batch_mode":s.image_batch_mode,
        "calibration":{"version":1,"calibrant":s.calibration.reference.name,"fit_dirty":s.calibration.dirty,"rms_degrees":s.calibration.rms,
        "custom_calibrant":s.calibration.custom.as_ref().map(|r|json!({"name":r.name,"content":r.content})),"setup_confirmed":s.calibration.confirmed,"calibrant_chosen":s.calibration.reference_chosen,
        "workflow":s.workflow,"geometry_source":s.calibration.source}}),
    );
    let mut owned = g.clone();
    owned.detector = None;
    let mut physical = serde_json::to_value(owned).map_err(|e| e.to_string())?;
    physical["detector"] = encode_detector(g.detector.as_deref(), payloads)?;
    native["physical_geometry"] = physical;
    #[cfg(feature = "dioptrin")]
    {
        native["sample_absorption"] = crate::sample_absorption::provenance();
        native["detector_absorption"] = json!({"model":"calibrated-pixel-incidence-v1"});
    }
    native["attenuation_data"] = serde_json::from_str(include_str!("../data/attenuation.json"))
        .map_err(|e| e.to_string())?;
    native["original_detector"] = encode_detector(settings.original_detector.as_deref(), payloads)?;
    doc["native_desktop"] = native;
    if let Some((path, shape, values, enabled)) = s.processing.project_flat() {
        doc["native_desktop"]["flat_response"] = put(cache, &shape, values)?;
        doc["native_desktop"]["flat_filename"] = json!(path);
        doc["native_desktop"]["flat_enabled"] = json!(enabled);
        if enabled {
            corrections["flat_field"] = json!({"filename":path});
        }
    } else {
        // The source document belongs to the last project load. Absence is an
        // authored edit too: never resurrect an old reference on the next load.
        doc["native_desktop"]["flat_response"] = Value::Null;
        doc["native_desktop"]["flat_filename"] = Value::Null;
        doc["native_desktop"]["flat_enabled"] = json!(false);
    }
    doc["native_desktop"]["source_variance"] = if let Some(image) = image {
        if let Some(v) = &image.source_variance {
            put(cache, &image.source_shape, v)?
        } else {
            Value::Null
        }
    } else {
        Value::Null
    };
    doc["native_desktop"]["background_poisson"] = json!(s.processing.background_poisson);
    let mut transfer = json!({"enabled":processing["transfer"]["enabled"]});
    for source in ["original", "response"] {
        if let Some((path, shape, values)) = s.processing.project_transfer(source) {
            transfer[format!("{source}_filename")] = json!(path);
            transfer[format!("{source}_data")] = put(cache, &shape, values)?;
        }
    }
    doc["native_desktop"]["transfer"] = transfer.clone();
    if processing["transfer"]["enabled"] == true {
        // The original format-2 reader expects scalar filenames here, not
        // cache keys masquerading as in-memory NumPy arrays. Native owned
        // references live in native_desktop.transfer and remain usable offline.
        corrections["transfer"] = json!({"original_filename":transfer["original_filename"],"response_filename":transfer["response_filename"]});
    }
    doc["img"]["corrections"] = corrections;
    let pat = &s.patterns;
    merge(
        &mut doc["pattern"],
        &json!({"unit":pat.unit,"color":pat.color,"visible":pat.visible,"pattern_source":if pat.imported{"file"}else{"integrated"},
        "pattern_filename":pat.path.as_deref().unwrap_or(""),"background_overlay_uid":if pat.anonymous_background.is_some(){Value::Null}else{json!(pat.background_uid.as_deref().unwrap_or(""))},
        "file_iteration_mode":pat.file_mode,"auto_bkg_enabled":pat.background.enabled,"auto_bkg_smoothing":pat.background.smoothing,
        "auto_bkg_iterations":pat.background.iterations,"auto_bkg_poly_order":pat.background.order,"auto_bkg_roi":pat.background.range}),
    );
    if let Some(raw) = &pat.raw {
        doc["pattern_x"] = put(payloads, &[raw.x.len()], &raw.x)?;
        doc["pattern_y"] = put(payloads, &[raw.y.len()], &raw.y)?;
        doc["pattern_errors"] = raw
            .sigma
            .as_ref()
            .map(|a| put(payloads, &[a.len()], a))
            .transpose()?
            .unwrap_or(Value::Null);
        doc["pattern_azimuthal_std"] = raw
            .spread
            .as_ref()
            .map(|a| put(payloads, &[a.len()], a))
            .transpose()?
            .unwrap_or(Value::Null);
    } else {
        for name in [
            "pattern_x",
            "pattern_y",
            "pattern_errors",
            "pattern_azimuthal_std",
        ] {
            doc[name] = Value::Null;
        }
    }
    doc["anonymous_background"] = if let Some(bg) = &pat.anonymous_background {
        json!({"x":put(payloads,&[bg.x.len()],&bg.x)?,"y":put(payloads,&[bg.y.len()],&bg.y)?})
    } else {
        Value::Null
    };
    let mut plugins = doc["plugins"].as_object().cloned().unwrap_or_default();
    for p in s.plugins.details().as_array().unwrap() {
        plugins.insert(
            p["name"].as_str().unwrap().into(),
            json!({"enabled":p["enabled"],"settings":p["settings"]}),
        );
    }
    doc["plugins"] = json!(plugins);
    series::save_configuration(s, group, &mut doc, arrays)?;
    Ok(doc)
}

fn encode_detector(
    d: Option<&dioptrin::detector::Detector>,
    payloads: &hdf5::Group,
) -> Result<Value, String> {
    use dioptrin::detector::PixelMap;
    let Some(d) = d else { return Ok(Value::Null) };
    let mut header = d.clone();
    header.map = PixelMap::Uniform;
    let mut value = serde_json::to_value(header).map_err(|e| e.to_string())?;
    value["map"] = match &d.map {
        PixelMap::Corners { shape, values } => {
            let raw: Vec<_> = values.iter().flatten().flatten().copied().collect();
            json!({"native_corners":put(payloads,&[shape[0],shape[1],4,3],&raw)?})
        }
        PixelMap::Transformed { base, operation } => {
            json!({"native_transform":{"base":encode_detector(Some(base),payloads)?,"operation":operation}})
        }
        map => serde_json::to_value(map).map_err(|e| e.to_string())?,
    };
    Ok(value)
}
fn decode_detector(
    file: &hdf5::File,
    value: &Value,
) -> Result<Option<Arc<dioptrin::detector::Detector>>, String> {
    use dioptrin::detector::{Detector, PixelMap};
    if value.is_null() {
        return Ok(None);
    }
    let mut header = value.clone();
    let map = header["map"].take();
    header["map"] = json!("Uniform");
    let mut d: Detector = serde_json::from_value(header).map_err(|e| e.to_string())?;
    d.map = if let Some(reference) = map.get("native_corners") {
        let (shape, data) =
            array(file, "payloads", reference)?.ok_or("Missing project detector corners.")?;
        if shape.len() != 4 || shape[2..] != [4, 3] {
            return Err("Invalid project detector corners.".into());
        }
        let values = data
            .as_chunks::<12>()
            .0
            .iter()
            .map(|p| std::array::from_fn(|i| [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]]))
            .collect();
        PixelMap::Corners {
            shape: [shape[0], shape[1]],
            values: Arc::new(values),
        }
    } else if let Some(transform) = map.get("native_transform") {
        PixelMap::Transformed {
            base: decode_detector(file, &transform["base"])?
                .ok_or("Missing detector transform base.")?,
            operation: serde_json::from_value(transform["operation"].clone())
                .map_err(|e| e.to_string())?,
        }
    } else {
        serde_json::from_value(map).map_err(|e| e.to_string())?
    };
    d.validate()?;
    Ok(Some(Arc::new(d)))
}

#[cfg(test)]
mod detector_options_tests {
    use super::*;
    #[test]
    fn legacy_factory_options_are_retained_or_rejected_explicitly() {
        let mut p = json!({"polarization_factor":0.,"detector_name":"Aarhus","geometry":{"detector":"Aarhus","detector_config":{"radius":0.29989}}});
        let g = geometry(&p).unwrap();
        assert_eq!(g.detector.as_ref().unwrap().config["radius"], 0.29989);
        p["geometry"]["detector_config"]["radius"] = json!(0.4);
        assert!(geometry(&p).is_err());
        p["geometry"]["detector_config"]["radius"] = json!(0.29989);
        p["geometry"]["parallax"] = json!({"material":"Si"});
        assert!(geometry(&p).is_err());
    }
}
