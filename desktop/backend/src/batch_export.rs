//! Batch export is read-only: use owned f64 series, never display rasters or live patterns.
use super::*;
use crate::{pattern::Curve, series::Series};
use std::io::Write;

impl Session {
    pub(super) fn save_batch_export(&self, args: &Value) -> Result<Reply, String> {
        let batch = self
            .batch
            .as_ref()
            .ok_or("Integrate or open a batch first.")?;
        let file = path(args)?;
        let file = if file.extension().is_none() {
            file.with_extension(args["format"].as_str().unwrap_or("h5"))
        } else {
            file.to_path_buf()
        };
        self.control.check()?;
        match extension(&file).as_str() {
            "h5" | "hdf5" | "nxs" | "csv" => {
                batch.save(&file)?;
                Ok(Reply::metadata(json!({"ok":true,"savedPath":file})))
            }
            "png" => {
                if args["png_data"].as_str().is_none() {
                    return Err(
                        "PNG export needs the active Batch plot. Open a plot and use Batch Save."
                            .into(),
                    );
                }
                file_workflow::save_png(&file, &args["png_data"])?;
                Ok(Reply::metadata(json!({"ok":true,"savedPath":file})))
            }
            "xy" | "chi" | "dat" | "fxye" => {
                let default_unit = if batch.wavelength.is_none()
                    && batch.unit != self.settings.unit
                    && [batch.unit.as_str(), self.settings.unit.as_str()].contains(&"2th_deg")
                {
                    if batch.unit == "q_nm^-1" {
                        "q_A^-1"
                    } else {
                        &batch.unit
                    }
                } else {
                    &self.settings.unit
                };
                let unit = args["unit"].as_str().unwrap_or(default_unit);
                if !["2th_deg", "q_A^-1", "d_A"].contains(&unit) {
                    return Err("Choose 2theta, Q or d for batch pattern export.".into());
                }
                let files = export_patterns(batch, &file, unit, |current, total| {
                    self.control.check()?;
                    self.control.publish(json!({"running":true,"current":current,"total":total,"label":"Saving batch patterns"}));
                    Ok(())
                })?;
                Ok(Reply::metadata(
                    json!({"ok":true,"savedPaths":files,"exportedFrames":batch.count()}),
                ))
            }
            _ => Err(
                "Save a batch as HDF5/NXS, CSV, XY, CHI, DAT, FXYE or a captured PNG overview."
                    .into(),
            ),
        }
    }
}
fn extension(path: &Path) -> String {
    path.extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_ascii_lowercase()
}
fn parent(path: &Path) -> &Path {
    path.parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."))
}

/// Stage every byte before publication. Hard links publish without clobbering;
/// failed/cancelled publication rolls back only the files created by this call.
/// An interrupted process can leave a subset on disk, but can never report success.
fn export_patterns(
    series: &Series,
    template: &Path,
    unit: &str,
    mut check: impl FnMut(usize, usize) -> Result<(), String>,
) -> Result<Vec<PathBuf>, String> {
    let root = parent(template);
    let stem = template
        .file_stem()
        .filter(|s| !s.is_empty())
        .ok_or("Choose an output basename.")?
        .to_string_lossy();
    let ext = extension(template);
    let requested_unit = unit;
    // GSAS CONS encodes 2theta in centidegrees. Qt's legacy d/CONS path
    // labels d spacings as angles; do not produce that ambiguous file here.
    let unit = file_workflow::export_unit(&ext, unit);
    let size = series.data.len();
    for (label, array) in [
        ("counting errors", &series.sigma),
        ("azimuthal std", &series.spread),
        ("background", &series.background),
    ] {
        if array.as_ref().is_some_and(|a| a.len() != size) {
            return Err(format!(
                "Batch {label} matrix does not match the intensity matrix."
            ));
        }
    }
    if ext == "fxye" && series.sigma.is_none() {
        return Err("This batch has no stored counting errors. Reintegrate with Calculate Poisson errors for FXYE; XY, CHI and DAT remain available.".into());
    }
    // Validate the requested conversion before staging anything, including stored-only series.
    series.profile(0, unit)?;
    let background_dir = root.join("bkg_subtracted");
    if series.background.is_some()
        && let Ok(meta) = std::fs::symlink_metadata(&background_dir)
        && (!meta.is_dir() || meta.file_type().is_symlink())
    {
        return Err("bkg_subtracted must be an ordinary directory.".into());
    }
    let mut destinations = vec![];
    for row in 0..series.count() {
        destinations.push(root.join(format!("{stem}_{row:03}.{ext}")));
        if series.spread.is_some() {
            destinations.push(root.join(format!("{stem}_{row:03}_spottiness.csv")));
        }
        if series.background.is_some() {
            destinations.push(background_dir.join(format!("{stem}_{row:03}.{ext}")));
        }
    }
    for target in &destinations {
        match std::fs::symlink_metadata(target) {
            Ok(_) => {
                return Err(format!(
                    "Batch output already exists: {}. Choose another basename; no files were replaced.",
                    target.display()
                ));
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.to_string()),
        }
    }
    let stage = tempfile::tempdir_in(root).map_err(|e| e.to_string())?;
    let mut staged = vec![];
    let total = series.count() + destinations.len();
    for row in 0..series.count() {
        check(row, total)?;
        let curve = series.profile(row, unit)?;
        let metadata = json!({"series_row":row,"source":series.entries[row].path,
            "source_frame":series.entries[row].frame,"processed_source_stem":series.export_name,"radial_unit":unit,"requested_radial_unit":requested_unit,"source_radial_unit":series.unit,
            "wavelength_m":series.wavelength,"normalized":series.normalized,
            "normalization_bins":series.normalization,"normalization_reference":series.reference,
            "calibration":series.calibration,"mask":series.mask,"background_available":series.background.is_some(),
            "background":series.background_metadata(),"counting_errors":series.sigma.is_some(),"azimuthal_std":series.spread.is_some()});
        let mut write = |bytes: Vec<u8>| -> Result<(), String> {
            let p = stage.path().join(staged.len().to_string());
            let mut f = std::fs::File::create(&p).map_err(|e| e.to_string())?;
            f.write_all(&bytes)
                .and_then(|_| f.sync_all())
                .map_err(|e| e.to_string())?;
            staged.push(p);
            Ok(())
        };
        let target = root.join(format!("{stem}_{row:03}.{ext}"));
        write(pattern_bytes(
            &target,
            &curve,
            unit,
            series.wavelength,
            &metadata,
            false,
        )?)?;
        if let Some(spread) = &curve.spread {
            let threshold = curve
                .y
                .iter()
                .filter(|v| v.is_finite())
                .map(|v| v.abs())
                .fold(1.0, f64::max)
                * 1e-12;
            let mut text = format!(
                "# radial [{unit}],integrated_mean,azimuthal_std,relative_spread\n# {metadata}\n"
            );
            for ((&x, &mean), &std) in curve.x.iter().zip(curve.y.iter()).zip(spread.iter()) {
                let ratio = if mean.is_finite() && std.is_finite() && mean > threshold {
                    std / mean
                } else {
                    f64::NAN
                };
                let ratio = if ratio.is_finite() { ratio } else { f64::NAN };
                text.push_str(&format!("{x:.17e},{mean:.17e},{std:.17e},{ratio:.17e}\n"));
            }
            write(text.into_bytes())?;
        }
        if let Some(background) = &series.background {
            let n = series.x.len();
            let subtracted = Curve {
                y: Arc::new(
                    curve
                        .y
                        .iter()
                        .zip(&background[row * n..(row + 1) * n])
                        .map(|(y, b)| y - b)
                        .collect(),
                ),
                ..curve
            };
            write(pattern_bytes(
                &background_dir.join(format!("{stem}_{row:03}.{ext}")),
                &subtracted,
                unit,
                series.wavelength,
                &metadata,
                true,
            )?)?;
        }
    }
    check(series.count(), total)?;
    let mut created_dir = false;
    let mut published = vec![];
    let outcome = (|| {
        if series.background.is_some() {
            match std::fs::create_dir(&background_dir) {
                Ok(()) => created_dir = true,
                Err(e)
                    if e.kind() == std::io::ErrorKind::AlreadyExists && background_dir.is_dir() => {
                }
                Err(e) => return Err(e.to_string()),
            }
        }
        for (i, (source, target)) in staged.iter().zip(&destinations).enumerate() {
            check(series.count() + i, total)?;
            std::fs::hard_link(source, target)
                .map_err(|e| format!("Could not publish {}: {e}", target.display()))?;
            published.push(target.clone());
        }
        check(total, total)?;
        Ok(())
    })();
    if let Err(error) = outcome {
        let remaining: Vec<_> = published
            .iter()
            .filter(|p| std::fs::remove_file(p).is_err())
            .map(|p| p.display().to_string())
            .collect();
        if created_dir {
            let _ = std::fs::remove_dir(&background_dir);
        }
        return Err(if remaining.is_empty() {
            format!("{error} Batch export was not completed; newly published files were removed.")
        } else {
            format!(
                "{error} Batch export is incomplete. Could not remove: {}",
                remaining.join(", ")
            )
        });
    }
    Ok(destinations)
}
fn pattern_bytes(
    path: &Path,
    curve: &Curve,
    unit: &str,
    wavelength: Option<f64>,
    metadata: &Value,
    subtracted: bool,
) -> Result<Vec<u8>, String> {
    let bytes = file_workflow::curve_bytes(path, curve, unit, wavelength.unwrap_or(0.0))?;
    let text = String::from_utf8(bytes).map_err(|e| e.to_string())?;
    let comment = format!(
        "# batch: {metadata}\n# background_subtracted: {subtracted}\n# fitted_background_uncertainty: not_estimated\n"
    );
    // CHI keeps its four-line header; FXYE keeps BANK immediately before samples.
    let position = match extension(path).as_str() {
        "chi" => text
            .match_indices('\n')
            .nth(3)
            .map(|(i, _)| i + 1)
            .unwrap_or(0),
        "fxye" => text.find("BANK ").unwrap_or(0),
        _ => 0,
    };
    Ok(format!("{}{}{}", &text[..position], comment, &text[position..]).into_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::series::Entry;
    fn fixture() -> Series {
        let mut s = Series::new(
            vec![1.0000000000000002, 2., 3.],
            vec![1.0000000000000002, 4., 9., 8., 12., 16.],
            "q_A^-1".into(),
            None,
            vec![
                Entry {
                    path: "missing/source.h5".into(),
                    frame: 2,
                },
                Entry {
                    path: "missing/source.h5".into(),
                    frame: 5,
                },
            ],
            vec!["missing/source.h5".into()],
            8,
        )
        .unwrap();
        s.sigma = Some(Arc::new(vec![0.125, 0.25, 0.5, 1., 2., 3.]));
        s.raw_sigma = s.sigma.clone();
        s.spread = Some(Arc::new(vec![0.5, f64::NAN, 1.5, 2., 3., 4.]));
        s.raw_spread = s.spread.clone();
        s.background = Some(Arc::new(vec![0.25; 6]));
        s.raw_background = s.background.clone();
        s.calibration = "source.poni".into();
        s.mask = "source.mask".into();
        s
    }
    // Read rows independently, without the production pattern parser/writer.
    fn rows(path: &Path, skip: usize) -> Vec<Vec<f64>> {
        std::fs::read_to_string(path)
            .unwrap()
            .lines()
            .skip(skip)
            .filter(|s| !s.starts_with('#') && !s.is_empty())
            .map(|s| {
                s.split(|c: char| c.is_whitespace() || c == ',')
                    .filter(|s| !s.is_empty())
                    .map(|s| s.parse().unwrap())
                    .collect()
            })
            .collect()
    }
    #[test]
    fn qt_names_units_errors_spread_background_and_f64_readback() {
        for unit in ["q_A^-1", "d_A", "2th_deg"] {
            for ext in ["xy", "chi", "dat", "fxye"] {
                let temp = tempfile::tempdir().unwrap();
                let mut s = fixture();
                s.wavelength = Some(0.5e-10);
                let saved = export_patterns(
                    &s,
                    &temp.path().join(format!("test.{ext}")),
                    unit,
                    |_, _| Ok(()),
                )
                .unwrap();
                assert_eq!(saved.len(), 6);
                assert!(!temp.path().join(format!("test.{ext}")).exists());
                for row in 0..2 {
                    let p = temp.path().join(format!("test_{row:03}.{ext}"));
                    let skip = if ext == "chi" {
                        4
                    } else if ext == "fxye" {
                        std::fs::read_to_string(&p)
                            .unwrap()
                            .lines()
                            .position(|l| l.starts_with("BANK "))
                            .unwrap()
                            + 1
                    } else {
                        0
                    };
                    let data = rows(&p, skip);
                    let bg = rows(
                        &temp
                            .path()
                            .join(format!("bkg_subtracted/test_{row:03}.{ext}")),
                        skip,
                    );
                    let spread = rows(
                        &temp.path().join(format!("test_{row:03}_spottiness.csv")),
                        0,
                    );
                    for j in 0..3 {
                        let q = s.x[j];
                        let exported_unit = if ext == "fxye" && unit == "d_A" {
                            "2th_deg"
                        } else {
                            unit
                        };
                        let radial = match exported_unit {
                            "q_A^-1" => q,
                            "d_A" => std::f64::consts::TAU / q,
                            _ => 2. * (q * 0.5 / (4. * std::f64::consts::PI)).asin().to_degrees(),
                        };
                        let factor = if ext == "fxye" && exported_unit != "q_A^-1" {
                            100.
                        } else {
                            1.
                        };
                        assert!((data[j][0] - factor * radial).abs() <= 1e-12 * radial.abs());
                        assert_eq!(data[j][1], s.data[row * 3 + j]);
                        assert_eq!(bg[j][1], s.data[row * 3 + j] - 0.25);
                        if ext == "fxye" {
                            assert_eq!(data[j][2], s.sigma.as_ref().unwrap()[row * 3 + j]);
                            assert_eq!(bg[j][2], data[j][2]);
                        }
                        assert_eq!(spread[j][1], data[j][1]);
                        let expected = s.spread.as_ref().unwrap()[row * 3 + j];
                        assert!(
                            spread[j][2] == expected
                                || (spread[j][2].is_nan() && expected.is_nan())
                        );
                        assert!(
                            spread[j][3] == expected / data[j][1]
                                || (spread[j][3].is_nan() && expected.is_nan())
                        );
                    }
                    let text = std::fs::read_to_string(p).unwrap();
                    assert!(text.contains(&format!("\"source_frame\":{}", s.entries[row].frame)));
                    assert!(text.contains("\"mask\":\"source.mask\""));
                }
                assert_eq!(s.selected, 0);
                assert_eq!(s.data[0], 1.0000000000000002);
            }
        }
    }
    #[test]
    fn normalized_export_and_processed_formats_keep_metadata_and_originals() {
        let mut s = fixture();
        s.normalize(true, [0, 3], 0).unwrap();
        let temp = tempfile::tempdir().unwrap();
        export_patterns(&s, &temp.path().join("normalized.xy"), "q_A^-1", |_, _| {
            Ok(())
        })
        .unwrap();
        let data = rows(&temp.path().join("normalized_001.xy"), 0);
        let sigma = s.sigma.as_ref().unwrap();
        assert_eq!(data[0][1], s.data[3]);
        assert!(
            std::fs::read_to_string(temp.path().join("normalized_001.xy"))
                .unwrap()
                .contains("\"normalized\":true")
        );
        assert_ne!(sigma[3], 1.);
        for ext in ["h5", "nxs"] {
            let p = temp.path().join(format!("stored.{ext}"));
            s.save(&p).unwrap();
            let loaded = Series::load(&p).unwrap();
            assert_eq!(loaded.data, s.data);
            assert_eq!(loaded.sigma, s.sigma);
            assert_eq!(loaded.background, s.background);
            assert_eq!(loaded.wavelength, None);
            assert_eq!(loaded.unit, "q_A^-1");
        }
        s.normalize(false, [0, 3], 0).unwrap();
        assert_eq!(s.data, s.raw);
        assert_eq!(s.sigma, s.raw_sigma);
    }
    #[test]
    fn stored_only_missing_errors_and_invalid_data_fail_without_outputs() {
        let temp = tempfile::tempdir().unwrap();
        let mut s = fixture();
        s.sigma = None;
        assert!(
            export_patterns(&s, &temp.path().join("test.fxye"), "q_A^-1", |_, _| Ok(()))
                .unwrap_err()
                .contains("no stored counting errors")
        );
        assert!(
            export_patterns(&s, &temp.path().join("test.xy"), "2th_deg", |_, _| Ok(()))
                .unwrap_err()
                .contains("no recorded wavelength")
        );
        s.data = Arc::new(vec![1., 2., 3., 4., f64::NAN, 6.]);
        assert!(export_patterns(&s, &temp.path().join("test.xy"), "d_A", |_, _| Ok(())).is_err());
        assert_eq!(std::fs::read_dir(temp.path()).unwrap().count(), 0);
    }
    #[test]
    fn cancellation_at_every_stage_rolls_back_outputs() {
        let s = fixture();
        for cancel_at in 0..=8 {
            let temp = tempfile::tempdir().unwrap();
            let result = export_patterns(&s, &temp.path().join("test.xy"), "q_A^-1", |at, _| {
                if at >= cancel_at {
                    Err("Cancelled".into())
                } else {
                    Ok(())
                }
            });
            assert!(result.is_err(), "cancel at {cancel_at}");
            assert_eq!(
                std::fs::read_dir(temp.path()).unwrap().count(),
                0,
                "cancel at {cancel_at}"
            );
        }
    }
    #[test]
    fn collision_before_and_during_publication_preserves_existing_files() {
        let s = fixture();
        let temp = tempfile::tempdir().unwrap();
        let target = temp.path().join("test_000_spottiness.csv");
        std::fs::write(&target, b"keep").unwrap();
        assert!(
            export_patterns(&s, &temp.path().join("test.xy"), "q_A^-1", |_, _| Ok(())).is_err()
        );
        assert_eq!(std::fs::read(&target).unwrap(), b"keep");
        std::fs::remove_file(&target).unwrap();
        let result = export_patterns(&s, &temp.path().join("test.xy"), "q_A^-1", |at, _| {
            if at == 3 {
                std::fs::write(&target, b"concurrent output").unwrap();
            }
            Ok(())
        });
        assert!(result.unwrap_err().contains("not completed"));
        assert_eq!(std::fs::read(&target).unwrap(), b"concurrent output");
        assert_eq!(std::fs::read_dir(temp.path()).unwrap().count(), 1);
    }
    #[test]
    fn absent_statistics_are_not_fabricated_and_spread_ratios_follow_qt_cutoff() {
        let temp = tempfile::tempdir().unwrap();
        let mut s = fixture();
        s.sigma = None;
        s.spread = None;
        s.background = None;
        let files =
            export_patterns(&s, &temp.path().join("plain.xy"), "d_A", |_, _| Ok(())).unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(rows(&files[0], 0)[0].len(), 2);
        assert!(
            export_patterns(&s, &temp.path().join("unknown.fxye"), "d_A", |_, _| Ok(())).is_err()
        );
        s.data = Arc::new(vec![0., -1., 1e-13, 1e-10, 2., 4.]);
        s.spread = Some(Arc::new(vec![1., 1., 1., 1e308, 0.5, f64::NAN]));
        export_patterns(&s, &temp.path().join("spread.xy"), "q_A^-1", |_, _| Ok(())).unwrap();
        let first = rows(&temp.path().join("spread_000_spottiness.csv"), 0);
        assert!(first.iter().all(|row| row[3].is_nan()));
        let second = rows(&temp.path().join("spread_001_spottiness.csv"), 0);
        assert!(second[0][3].is_nan());
        assert_eq!(second[1][3], 0.25);
        assert!(second[2][3].is_nan());
    }
    #[test]
    fn session_success_is_reported_only_for_complete_exports() {
        let temp = tempfile::tempdir().unwrap();
        let mut session = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."));
        session.batch = Some(fixture());
        let args = json!({"path":temp.path().join("test.xy")});
        let reply = session.save_batch_export(&args).unwrap();
        assert_eq!(reply.result["savedPaths"].as_array().unwrap().len(), 6);
        assert_eq!(reply.result["exportedFrames"], 2);
        assert!(session.save_batch_export(&args).is_err());
        assert!(
            session
                .save_batch_export(&json!({"path":temp.path().join("invalid.png")}))
                .is_err()
        );
        assert!(!temp.path().join("invalid.png").exists());
    }
}
