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
        let mut processing = self.processing.clone();
        for (i, p) in paths.iter().enumerate() {
            self.control.check()?;
            self.control.publish(json!({"running":true,"current":i,"total":paths.len(),"label":if output.is_some(){"Saving batch images"}else{"Combining batch images"}}));
            let image = if i == 0 {
                first.clone()
            } else {
                Image::open(Path::new(p), &options)?
            };
            if image.shape != shape {
                return Err("Batch images must have matching detector shapes.".into());
            }
            if let Some(staging) = &staging {
                let values = processing.values(
                    &image,
                    self.image_generation + i as u64 + 1,
                    &self.settings.geometry,
                )?;
                save_image_tiff(&staging.path().join(&names[i]), &values, shape)?;
            } else {
                for (sum, value) in sum.iter_mut().zip(image.values.iter()) {
                    *sum += value;
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
            for value in &mut sum {
                *value /= paths.len() as f64;
            }
        }
        first.set_derived(
            sum,
            &format!(
                "Derived {mode} of {} input files; source files are unchanged.",
                paths.len()
            ),
        )?;
        self.publish_image(first);
        self.calculate(false)?;
        self.revision += 1;
        Ok(self.snapshot(true))
    }
}
fn save_image_tiff(path: &Path, values: &[f64], shape: [usize; 2]) -> Result<(), String> {
    let data: Vec<i32> = values
        .chunks_exact(shape[1])
        .rev()
        .flatten()
        .map(|&v| {
            if v.is_finite() && v > i32::MIN as f64 && v < (i32::MAX as f64 + 1.0) {
                v as i32
            } else {
                i32::MIN
            }
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
