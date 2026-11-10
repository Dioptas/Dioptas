//! Image-tab add/average/staged-save actions, with original sources unchanged.
use super::*;
impl Session {
    pub(super) fn image_batch(
        &mut self,
        paths: Vec<String>,
        args: &Value,
    ) -> Result<Reply, String> {
        let mode = args["batch_mode"]
            .as_str()
            .unwrap_or(&self.image_batch_mode)
            .to_string();
        if mode == "integrate" {
            let mut payload = args.clone();
            payload["paths"] = json!(paths);
            return self.dispatch("batch_load", &payload);
        }
        if !["add", "average", "save"].contains(&mode.as_str()) {
            return Err("Choose integrate, add, average or save.".into());
        }
        let options = self
            .image
            .as_ref()
            .map(|i| i.options.clone())
            .unwrap_or(json!({}));
        let mut first = Image::open(Path::new(&paths[0]), &options)?;
        if mode != "save" && self.image_change(&first, &json!({}))?.is_some() {
            return Err("Combined images must match the current detector dimensions. Open one image first to change the detector setup and reset calibration.".into());
        }
        if mode != "save"
            && self
                .image
                .as_ref()
                .is_some_and(|old| old.source_shape != first.source_shape)
        {
            self.reset_image_coordinates(first.source_shape);
        }
        self.assign_image_detector(&first)?;
        let shape = first.shape;
        let output = if mode == "save" {
            let p = PathBuf::from(
                args["output_directory"]
                    .as_str()
                    .ok_or("Choose an existing output folder.")?,
            );
            if !p.is_dir() {
                return Err("Choose an existing output folder.".into());
            }
            Some(p)
        } else {
            None
        };
        let names: Vec<_> = paths
            .iter()
            .map(|p| {
                format!(
                    "batch_{}.tiff",
                    Path::new(p)
                        .file_stem()
                        .unwrap_or_default()
                        .to_string_lossy()
                )
            })
            .collect();
        if let Some(output) = &output {
            let mut unique = std::collections::BTreeSet::new();
            if names
                .iter()
                .any(|n| !unique.insert(n) || output.join(n).exists())
            {
                return Err(
                    "Batch output filenames must be unique and must not already exist.".into(),
                );
            }
        }
        let staging = if let Some(output) = &output {
            Some(tempfile::tempdir_in(output).map_err(|e| e.to_string())?)
        } else {
            None
        };
        let mut sum = vec![0.0; first.values.len()];
        let mut variance = vec![0.0; sum.len()];
        let mut invalid = vec![0u8; sum.len()];
        let mut processing = self.processing.clone();
        for (i, p) in paths.iter().enumerate() {
            self.control.check()?;
            self.control.publish(json!({"running":true,"current":i,"total":paths.len(),"label":if output.is_some(){"Saving batch images"}else{"Combining batch images"}}));
            let mut image = if i == 0 {
                first.clone()
            } else {
                Image::open(Path::new(p), &options)?
            };
            if image.shape != shape {
                return Err("Batch images must have matching detector shapes.".into());
            }
            if let Some(staging) = &staging {
                image.orient(&self.settings.transformations, &self.control)?;
                let values = processing.values(
                    &image,
                    self.image_generation + i as u64 + 1,
                    &self.settings.geometry,
                    &self.control,
                )?;
                let invalid = self.physical_mask_for(image.shape, Some(&image))?;
                save_image_tiff(
                    &staging.path().join(&names[i]),
                    &values,
                    image.shape,
                    invalid.as_deref().map(Vec::as_slice),
                )?;
            } else {
                // Infer acquisition invalidity from each original input before
                // arithmetic can turn its dummy code into a valid number.
                let mut oriented = image.clone();
                oriented.orient(&self.settings.transformations, &self.control)?;
                if let Some(mask) = self.physical_mask_for(oriented.shape, Some(&oriented))? {
                    let source_mask = crate::transform::apply(
                        &mask,
                        oriented.shape,
                        &crate::transform::inverse(&self.settings.transformations),
                        &self.control,
                    )?;
                    for (out, value) in invalid.iter_mut().zip(source_mask.iter()) {
                        *out |= *value;
                    }
                }
                for ((sum, variance), value) in
                    sum.iter_mut().zip(&mut variance).zip(image.values.iter())
                {
                    *sum += value;
                    *variance += value.max(0.0);
                }
            }
            image.check_sources()?;
        }
        self.control.check()?;
        if let Some(output) = &output {
            use std::io::Write;
            let mut published = vec![];
            let outcome = (|| {
                for name in &names {
                    let target = output.join(name);
                    let mut out = std::fs::OpenOptions::new()
                        .write(true)
                        .create_new(true)
                        .open(&target)
                        .map_err(|e| e.to_string())?;
                    published.push(target);
                    let bytes = std::fs::read(staging.as_ref().unwrap().path().join(name))
                        .map_err(|e| e.to_string())?;
                    out.write_all(&bytes)
                        .and_then(|_| out.sync_all())
                        .map_err(|e| e.to_string())?;
                }
                Ok::<_, String>(())
            })();
            if let Err(error) = outcome {
                for p in published {
                    let _ = std::fs::remove_file(p);
                }
                return Err(error);
            }
            return Ok(Reply::metadata(
                json!({"ok":true,"savedPaths":published,"imageBatchSaved":true}),
            ));
        }
        if mode == "average" {
            for (value, variance) in sum.iter_mut().zip(&mut variance) {
                *value /= paths.len() as f64;
                *variance /= (paths.len() as f64).powi(2);
            }
        }
        // Invalid detector samples have no arithmetic meaning. Retain a known
        // dummy code in the derived plane, including its offline project cache.
        for (value, invalid) in sum.iter_mut().zip(invalid) {
            if invalid != 0 {
                *value = i32::MAX as f64;
            }
        }
        first.set_derived(
            sum,
            variance,
            &format!(
                "Derived {mode} of {} input files; source files are unchanged.",
                paths.len()
            ),
        )?;
        self.publish_image(first)?;
        self.calculate(false)?;
        self.revision += 1;
        Ok(self.snapshot(true))
    }
}
fn save_image_tiff(
    path: &Path,
    values: &[f64],
    shape: [usize; 2],
    invalid: Option<&[u8]>,
) -> Result<(), String> {
    let data: Vec<i32> = values
        .chunks_exact(shape[1])
        .enumerate()
        .rev()
        .flat_map(|(row, values)| {
            values.iter().enumerate().map(move |(col, &v)| {
                if invalid.is_some_and(|m| m[row * shape[1] + col] != 0) {
                    i32::MAX
                } else if v.is_finite() && v > i32::MIN as f64 && v < (i32::MAX as f64 + 1.0) {
                    v as i32
                } else {
                    i32::MIN
                }
            })
        })
        .collect();
    file_workflow::atomic_render(path, |out| {
        let mut encoder = tiff::encoder::TiffEncoder::new(out).map_err(|e| e.to_string())?;
        encoder
            .write_image::<tiff::encoder::colortype::GrayI32>(
                shape[1] as u32,
                shape[0] as u32,
                &data,
            )
            .map_err(|e| e.to_string())
    })
}

#[cfg(all(test, feature = "dioptrin"))]
mod tests {
    use super::*;

    #[test]
    fn derived_images_keep_input_gap_union_and_do_not_pollute_original_source_cache() {
        let temp = tempfile::tempdir().unwrap();
        let [h, w] = [256, 514];
        for marker in [-1., i32::MAX as f64, u32::MAX as f64] {
            let mut paths = vec![];
            for i in 0..2 {
                let path = temp.path().join(format!("source_{i}.h5"));
                let mut values = vec![100. * (i + 1) as f64; h * w];
                for row in 0..h {
                    for col in 254..260 {
                        values[row * w + col] = marker;
                    }
                }
                values[(20 + i) * w + 40] = marker;
                values[100 * w + 100] = if i == 0 { 0.5 } else { -1.5 };
                let file = hdf5::File::create(&path).unwrap();
                file.new_dataset::<f64>()
                    .shape([h, w])
                    .create("counts")
                    .unwrap()
                    .write_raw(&values)
                    .unwrap();
                paths.push(path.to_string_lossy().into_owned());
            }
            let mut session = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."));
            session
                .settings
                .geometry
                .select_detector("Eiger2 CdTe 500k")
                .unwrap();
            session.settings.calibrated = true;
            session.settings.bins = 64;
            session.settings.cake_bins = 16;
            session.settings.trim_zeros = false;
            session.settings.solid_angle = false;
            session.settings.polarization = 0.;
            // Start with an original F64 source to exercise the formerly
            // identical file/dtype cache key of its derived sum.
            session
                .dispatch("open_image", &json!({"path":paths[0],"dataset":"/counts"}))
                .unwrap();
            for (mode, expected) in [("add", 300.), ("average", 150.)] {
                for rotate in [false, true] {
                    if rotate {
                        session
                            .dispatch("image_transform", &json!({"operation":"rotate_right"}))
                            .unwrap();
                    }
                    let reply = session
                        .dispatch("open_image", &json!({"paths":paths,"batch_mode":mode}))
                        .unwrap();
                    assert_eq!(reply.result["state"]["maskedPixels"], h * 6 + 2);
                    if !rotate {
                        let index = (h - 1 - 100) * w + 100;
                        assert_eq!(session.effective_mask[index], 0);
                        assert_eq!(
                            session.image.as_ref().unwrap().values[index],
                            if mode == "add" { -1. } else { -0.5 }
                        );
                    }
                    for value in reply.result["pattern"]["y"].as_array().unwrap() {
                        let value = value.as_f64().unwrap();
                        assert!(
                            // Unpolarized radiation still has an angle-dependent
                            // normalization; dummy samples must never dominate.
                            value == 0. || (expected * 0.9..expected * 1.1).contains(&value),
                            "{mode}: {value}"
                        );
                    }
                    if rotate {
                        session
                            .dispatch("image_transform", &json!({"operation":"reset"}))
                            .unwrap();
                    }
                    let project = temp.path().join("derived.dio");
                    session
                        .dispatch("save_project", &json!({"path":project}))
                        .unwrap();
                    session
                        .dispatch("open_project", &json!({"path":project}))
                        .unwrap();
                    let restored = session.dispatch("integrate", &json!({})).unwrap();
                    assert_eq!(restored.result["state"]["maskedPixels"], h * 6 + 2);
                    let original = session
                        .dispatch("open_image", &json!({"path":paths[0],"dataset":"/counts"}))
                        .unwrap();
                    assert_eq!(original.result["state"]["maskedPixels"], h * 6 + 1);
                }
            }
            let output = temp.path().join(format!("saved-{marker}"));
            std::fs::create_dir(&output).unwrap();
            session
                .dispatch(
                    "open_image",
                    &json!({"paths":paths,"batch_mode":"save","output_directory":output}),
                )
                .unwrap();
            let saved = session
                .dispatch(
                    "open_image",
                    &json!({"path":output.join("batch_source_0.tiff")}),
                )
                .unwrap();
            assert_eq!(saved.result["state"]["maskedPixels"], h * 6 + 1);
            let saved = session
                .dispatch(
                    "open_image",
                    &json!({"path":output.join("batch_source_1.tiff")}),
                )
                .unwrap();
            assert_eq!(saved.result["state"]["maskedPixels"], h * 6 + 1);
            let index = (h - 1 - 100) * w + 100;
            assert_eq!(session.effective_mask[index], 0);
            assert_eq!(session.image.as_ref().unwrap().values[index], -1.);
        }
    }
}
