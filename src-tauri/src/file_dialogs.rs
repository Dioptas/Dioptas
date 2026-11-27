//! Native file and folder chooser routing for Tauri desktop commands.

use crate::batch_export;
use crate::processor::Packet;
use dioptas_contract::image_formats::{COMPRESSED_IMAGE_EXTENSIONS, DETECTOR_IMAGE_EXTENSIONS};
use serde_json::{Value, json};
use tauri_plugin_dialog::DialogExt;

struct FileChoice {
    label: &'static str,
    extensions: &'static [&'static str],
    /// Second filter shown after the main one. Detector images use it for
    /// gzip/bzip2 files: native filters match only the final suffix, so `gz`
    /// in the main filter would show every tarball.
    compressed: Option<(&'static str, &'static [&'static str])>,
    name: &'static str,
    save: bool,
}

fn folder_choice(action: &str, payload: &Value) -> bool {
    matches!(
        action,
        "integration_output_directory"
            | "integration_image_directory"
            | "integration_batch"
            | "map_folder"
            | "batch_folder"
    ) && payload["path"].is_null()
}

fn batch_image_output_choice(action: &str, payload: &Value) -> bool {
    action == "open_image"
        && payload["batch_mode"] == "save"
        && payload["paths"]
            .as_array()
            .is_some_and(|paths| paths.len() > 1)
        && payload["output_directory"].is_null()
}

fn choose_batch_image_output(
    app: &tauri::AppHandle,
    action: &str,
    payload: &mut Value,
) -> Result<bool, String> {
    if batch_image_output_choice(action, payload) {
        let Some(folder) = app.dialog().file().blocking_pick_folder() else {
            return Ok(false);
        };
        payload["output_directory"] = json!(
            folder
                .into_path()
                .map_err(|e| e.to_string())?
                .to_string_lossy()
        );
    }
    Ok(true)
}

fn file_choice(action: &str, payload: &Value) -> Option<FileChoice> {
    if matches!(action, "integration_phase_files" | "integration_phase")
        && payload.get("paths").is_some_and(|v| !v.is_null())
    {
        return None;
    }
    if matches!(
        action,
        "scxrd_load" | "map_load" | "batch_load" | "batch_load_data" | "open_image"
    ) && (payload.get("paths").is_some_and(|v| !v.is_null()) || payload["reintegrate"] == true)
    {
        return None;
    }
    if action == "integration_overlay" && payload.get("paths").is_some_and(|v| !v.is_null()) {
        return None;
    }
    if action == "integration_phase_export" && payload["save_current"] == true {
        return None;
    }
    if payload.get("path").is_some_and(|v| !v.is_null()) || payload["reset"] == true {
        return None;
    }
    if action == "integration_overlay" && payload["operation"] != "load" {
        return None;
    }
    if action == "integration_phase" && payload["operation"] != "load" {
        return None;
    }
    if action == "integration_open_pattern" && !payload["direction"].is_null() {
        return None;
    }
    if action == "integration_image_background"
        && (!payload["scale"].is_null()
            || !payload["offset"].is_null()
            || !payload["poisson"].is_null())
    {
        return None;
    }
    if ["integration_flat_field", "integration_transfer"].contains(&action)
        && !payload["enabled"].is_null()
    {
        return None;
    }
    if action == "scxrd_file" {
        let (label, extensions, name, save): (_, &[&str], _, _) =
            match payload["operation"].as_str()? {
                "use_calibration" | "protocol_builtin" => return None,
                "protocol" => ("PhaseSmith analysis protocol", &["json"], "", false),
                "audit" => (
                    "Lossless stage audit",
                    &["npz"],
                    "single-crystal-stages.npz",
                    true,
                ),
                "protocol_save" => (
                    "Effective PhaseSmith protocol",
                    &["json"],
                    "analysis-protocol.json",
                    true,
                ),
                "calibration" => ("PONI calibration", &["poni"], "", false),
                "open" | "preset" => ("Single-crystal recipe", &["json"], "", false),
                "save" => (
                    "Single-crystal recipe",
                    &["json"],
                    "single-crystal.scxrd.json",
                    true,
                ),
                "reflections" => (
                    "Unmerged reflection table",
                    &["txt"],
                    "reflections.txt",
                    true,
                ),
                "hkl" => ("HKLF4 intensities", &["hkl"], "reflections.hkl", true),
                "cif" => ("Structure candidate", &["cif"], "candidate.cif", true),
                _ => return None,
            };
        return Some(FileChoice {
            label,
            extensions,
            compressed: None,
            name,
            save,
        });
    }
    let (label, extensions, name, save): (_, &[&str], _, _) = match action {
        "open_image" => ("Detector images", DETECTOR_IMAGE_EXTENSIONS, "", false),
        "scxrd_load" | "map_load" | "batch_load" | "batch_load_data" => {
            ("Detector images", DETECTOR_IMAGE_EXTENSIONS, "", false)
        }
        "batch_open" | "map_batch" => ("Processed batch", &["h5", "hdf5", "nxs"], "", false),
        "map_export" => (
            "Map data",
            &["txt", "tiff", "png"],
            if payload.get("png_data").is_some() {
                "map.png"
            } else {
                "map.txt"
            },
            true,
        ),
        "open_calibration" => ("PONI calibration", &["poni"], "", false),
        "save_calibration" => ("PONI calibration", &["poni"], "calibration.poni", true),
        "load_peaks" => ("Dioptas calibration peaks", &["json"], "", false),
        "save_peaks" => (
            "Dioptas calibration peaks",
            &["json"],
            "calibration-peaks.json",
            true,
        ),
        "open_project" => ("Dioptas project", &["dio"], "", false),
        "save_project" => ("Dioptas project", &["dio"], "experiment.dio", true),
        "save_cake_profile" => (
            "Azimuthal profile (degrees, intensity)",
            &["xy", "dat", "txt", "csv"],
            "azimuthal-profile.xy",
            true,
        ),
        "export_pattern" => ("XY pattern", &["xy"], "pattern.xy", true),
        "integration_save_image" => (
            "Image or data",
            if payload["source"] == "cake" {
                &["png", "tif", "tiff", "txt", "csv"]
            } else {
                &["png", "tif", "tiff"]
            },
            if payload["source"] == "cake" {
                "cake.png"
            } else {
                "image.png"
            },
            true,
        ),
        "save_combined_pattern" => (
            "Combined diffraction pattern",
            &["xy", "chi", "dat", "fxye"],
            "combined.xy",
            true,
        ),
        "integration_save_pattern" if payload["format"] == "png" => {
            ("PNG pattern figure", &["png"], "pattern.png", true)
        }
        "integration_save_pattern" if payload["format"] == "svg" => {
            ("SVG vector pattern figure", &["svg"], "pattern.svg", true)
        }
        "integration_save_pattern" => (
            "Diffraction pattern",
            &["xy", "xye", "chi", "dat", "fxye"],
            "pattern.xy",
            true,
        ),
        "integration_save_spottiness" => ("Spottiness", &["csv"], "pattern_spottiness.csv", true),
        "integration_save_background" => (
            "Background pattern",
            &["xy", "chi", "dat"],
            "background.xy",
            true,
        ),
        "integration_open_pattern" | "integration_overlay" => (
            "Diffraction pattern",
            &["xy", "xye", "chi", "dat", "fxye"],
            "",
            false,
        ),
        "integration_phase_list" => (
            "Phase List",
            &["txt"],
            "phase_list.txt",
            payload["save"] == true,
        ),
        "integration_phase_export" if payload["format"] == "eosmat" => {
            ("Material", &["eosmat"], "material.eosmat", true)
        }
        "integration_phase_export" if payload["format"] == "txt" => {
            ("Reflection table", &["txt"], "reflections.txt", true)
        }
        "integration_phase_export" => (
            "Phase or material",
            &["eosmat", "jcpds", "txt"],
            "phase.eosmat",
            true,
        ),
        "integration_phase" | "integration_phase_files" => (
            "Diffraction phase",
            &["jcpds", "cif", "eosmat", "json"],
            "",
            false,
        ),
        "integration_image_background" | "integration_flat_field" | "integration_transfer" => {
            ("Detector image", DETECTOR_IMAGE_EXTENSIONS, "", false)
        }
        "integration_save_batch" => batch_export::file_choice(payload),
        "mask_file" => (
            "Detector mask",
            if payload["flipud"] == true {
                &["npy", "edf"]
            } else {
                &["mask", "npy", "tif", "tiff", "edf"]
            },
            if payload["flipud"] == true {
                "mask.npy"
            } else {
                "mask.mask"
            },
            payload["save"] == true,
        ),
        "detector_file" => ("Detector definition", &["h5", "hdf5", "nxs"], "", false),
        "distortion_file" => ("Distortion spline", &["spline"], "", false),
        "open_calibrant" => (
            "Calibrant files (.D, .cif)",
            &["D", "d", "cif", "CIF"],
            "",
            false,
        ),
        _ => return None,
    };
    let compressed = (extensions == DETECTOR_IMAGE_EXTENSIONS)
        .then_some(("Compressed detector images", COMPRESSED_IMAGE_EXTENSIONS));
    Some(FileChoice {
        label,
        extensions,
        compressed,
        name,
        save,
    })
}

/// Present any required native file or folder chooser for `action`, mutating
/// `payload` with the selected path(s). Returns `Ok(Some(packet))` when the
/// dialog was cancelled or handled locally without calling the processor.
pub fn resolve(
    app: &tauri::AppHandle,
    action: &str,
    payload: &mut Value,
) -> Result<Option<Packet>, String> {
    if action == "choose_hdf5_companion" {
        let mut dialog = app
            .dialog()
            .file()
            .set_title("Choose the declared HDF5 source file");
        if let Some(directory) = payload["directory"].as_str() {
            dialog = dialog.set_directory(directory);
        }
        let Some(selected) = dialog.blocking_pick_file() else {
            return Ok(Some(Packet::cancelled()));
        };
        let selected = selected.into_path().map_err(|e| e.to_string())?;
        return Ok(Some(Packet::metadata(
            json!({"ok":true,"chosenPath":selected.to_string_lossy()}),
        )));
    }
    if folder_choice(action, payload) {
        let Some(selected) = app.dialog().file().blocking_pick_folder() else {
            return Ok(Some(Packet::cancelled()));
        };
        payload["path"] = Value::String(
            selected
                .into_path()
                .map_err(|e| e.to_string())?
                .to_string_lossy()
                .into_owned(),
        );
    }
    if let Some(choice) = file_choice(action, payload) {
        let mut dialog = app
            .dialog()
            .file()
            .add_filter(choice.label, choice.extensions);
        if let Some((label, extensions)) = choice.compressed {
            dialog = dialog.add_filter(label, extensions);
        }
        dialog = dialog.add_filter("All files", &["*"]);
        if action == "integration_save_batch" {
            dialog = dialog.set_title(if batch_export::multifile(payload) {
                "Choose Batch export basename"
            } else {
                "Save Batch data"
            });
        }
        if let Some(directory) = payload["directory"].as_str() {
            dialog = dialog.set_directory(directory);
        }
        if matches!(
            action,
            "scxrd_load"
                | "map_load"
                | "batch_load"
                | "batch_load_data"
                | "integration_overlay"
                | "integration_phase_files"
        ) || (action == "open_image" && payload["multiple"] == true)
        {
            let Some(selected) = dialog.blocking_pick_files() else {
                return Ok(Some(Packet::cancelled()));
            };
            let mut paths = Vec::new();
            for file in selected {
                paths.push(
                    file.into_path()
                        .map_err(|e| e.to_string())?
                        .to_string_lossy()
                        .into_owned(),
                );
            }
            payload["paths"] = json!(paths);
            if !choose_batch_image_output(app, action, payload)? {
                return Ok(Some(Packet::cancelled()));
            }
            return Ok(None);
        }
        let selected = if choice.save {
            let name = if action == "integration_save_batch" {
                batch_export::suggested_name(payload, choice.name)
            } else if matches!(
                action,
                "integration_save_image"
                    | "integration_phase_export"
                    | "save_cake_profile"
                    | "integration_save_spottiness"
                    | "integration_save_pattern"
            ) {
                payload["suggested_name"].as_str().unwrap_or(choice.name)
            } else {
                choice.name
            };
            dialog.set_file_name(name).blocking_save_file()
        } else {
            dialog.blocking_pick_file()
        };
        let Some(selected) = selected else {
            return Ok(Some(Packet::cancelled()));
        };
        let path = selected.into_path().map_err(|e| e.to_string())?;
        payload["path"] = Value::String(path.to_string_lossy().into_owned());
    }
    if !choose_batch_image_output(app, action, payload)? {
        return Ok(Some(Packet::cancelled()));
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn supported_formats_are_selectable_in_every_detector_image_chooser() {
        for action in [
            "open_image",
            "scxrd_load",
            "map_load",
            "batch_load",
            "batch_load_data",
            "integration_image_background",
            "integration_flat_field",
            "integration_transfer",
        ] {
            let choice = file_choice(action, &json!({})).unwrap();
            assert!(!choice.save, "{action}");
            assert_eq!(choice.extensions, DETECTOR_IMAGE_EXTENSIONS, "{action}");
            assert!(
                !choice
                    .extensions
                    .iter()
                    .any(|e| COMPRESSED_IMAGE_EXTENSIONS.contains(e)),
                "{action}"
            );
            assert_eq!(
                choice.compressed,
                Some(("Compressed detector images", COMPRESSED_IMAGE_EXTENSIONS)),
                "{action}"
            );
        }
        // Other choosers never offer the compressed filter.
        assert_eq!(
            file_choice("detector_file", &json!({})).unwrap().compressed,
            None
        );
        assert_eq!(
            file_choice("scxrd_file", &json!({"operation":"calibration"}))
                .unwrap()
                .compressed,
            None
        );
    }

    #[test]
    fn scxrd_choosers_keep_sources_and_exports_explicit() {
        assert!(file_choice("scxrd_load", &json!({})).is_some());
        assert!(file_choice("scxrd_load", &json!({"paths":["frame.tif"]})).is_none());
        assert!(file_choice("scxrd_file", &json!({"operation":"use_calibration"})).is_none());
        assert!(
            !file_choice("scxrd_file", &json!({"operation":"calibration"}))
                .unwrap()
                .save
        );
        for op in ["save", "reflections", "hkl", "cif"] {
            assert!(
                file_choice("scxrd_file", &json!({"operation":op}))
                    .unwrap()
                    .save
            );
        }
    }

    #[test]
    fn pattern_save_chooser_separates_data_and_editor_figures() {
        let choice = file_choice(
            "integration_save_pattern",
            &json!({"png_data":"png", "svg_data":"svg"}),
        )
        .unwrap();
        assert_eq!(choice.extensions, &["xy", "xye", "chi", "dat", "fxye"]);
        assert_eq!(choice.name, "pattern.xy");
        for format in ["png", "svg"] {
            let figure =
                file_choice("integration_save_pattern", &json!({"format":format})).unwrap();
            assert_eq!(figure.extensions, &[format]);
            assert_eq!(figure.name, format!("pattern.{format}"));
        }
        assert!(choice.save);
        for extension in choice.extensions {
            assert!(
                file_choice(
                    "integration_save_pattern",
                    &json!({"path":format!("/tmp/pattern.{extension}")})
                )
                .is_none()
            );
        }
        assert!(
            !file_choice("integration_open_pattern", &json!({}))
                .unwrap()
                .extensions
                .contains(&"svg")
        );
    }

    #[test]
    fn spottiness_save_uses_csv_dialog() {
        let choice = file_choice("integration_save_spottiness", &json!({})).unwrap();
        assert!(choice.save);
        assert_eq!(choice.extensions, &["csv"]);
        assert_eq!(choice.name, "pattern_spottiness.csv");
        assert!(
            file_choice(
                "integration_save_spottiness",
                &json!({"path":"/tmp/spread.csv"})
            )
            .is_none()
        );
    }

    #[test]
    fn batch_dialogs_distinguish_sources_and_explicit_payloads() {
        assert!(batch_image_output_choice(
            "open_image",
            &json!({"batch_mode": "save", "paths": ["one.tif", "two.tif"]})
        ));
        assert!(!batch_image_output_choice(
            "open_image",
            &json!({"batch_mode": "save", "paths": ["one.tif"]})
        ));
        assert!(!batch_image_output_choice(
            "open_image",
            &json!({"batch_mode": "integrate", "paths": ["one.tif", "two.tif"]})
        ));
        assert!(!batch_image_output_choice(
            "open_image",
            &json!({"batch_mode": "save", "paths": ["one.tif", "two.tif"], "output_directory": "/tmp"})
        ));
        assert!(file_choice("batch_load", &json!({})).is_some());
        assert!(file_choice("batch_load_data", &json!({})).is_some());
        assert!(file_choice("batch_load_data", &json!({"paths": ["series.h5"]})).is_none());
        assert!(file_choice("batch_load", &json!({"paths": ["one.tif", "two.tif"]})).is_none());
        assert!(file_choice("batch_load", &json!({"reintegrate": true})).is_none());
        assert!(file_choice("open_image", &json!({"paths": ["one.tif"]})).is_none());
        assert!(file_choice("open_image", &json!({"multiple": true})).is_some());
        assert!(file_choice("batch_open", &json!({})).is_some());
        assert!(folder_choice("batch_folder", &json!({})));
        assert!(!folder_choice("batch_folder", &json!({"path": "/tmp"})));
    }

    #[test]
    fn image_directory_uses_folder_dialog_only_without_explicit_path() {
        assert!(folder_choice("integration_image_directory", &json!({})));
        assert!(!folder_choice(
            "integration_image_directory",
            &json!({"path": "/tmp/images"})
        ));
        assert!(!folder_choice("open_image", &json!({})));
        assert!(file_choice("open_image", &json!({"directory": "/tmp/images"})).is_some());
    }

    #[test]
    fn combined_pattern_save_uses_native_pattern_dialog() {
        let choice = file_choice("save_combined_pattern", &json!({})).unwrap();
        assert!(choice.save);
        assert_eq!(choice.extensions, &["xy", "chi", "dat", "fxye"]);
        assert!(
            file_choice(
                "save_combined_pattern",
                &json!({"path": "/tmp/combined.xy"})
            )
            .is_none()
        );
    }

    #[test]
    fn dialogs_only_for_file_commands_without_explicit_paths_or_reset() {
        assert!(file_choice("open_image", &json!({})).is_some());
        assert!(!file_choice("load_peaks", &json!({})).unwrap().save);
        assert!(file_choice("save_peaks", &json!({})).unwrap().save);
        assert!(file_choice("load_peaks", &json!({"path": "/tmp/peaks.json"})).is_none());
        assert!(file_choice("open_image", &json!({"path": "/tmp/image.tif"})).is_none());
        assert!(file_choice("distortion_file", &json!({"reset": true})).is_none());
        assert!(file_choice("detector_file", &json!({"reset": true})).is_none());
        assert!(
            file_choice("mask_file", &json!({"save": true}))
                .unwrap()
                .save
        );
        let profile = file_choice("save_cake_profile", &json!({})).unwrap();
        assert!(profile.save);
        assert_eq!(profile.name, "azimuthal-profile.xy");
        assert_eq!(profile.extensions, &["xy", "dat", "txt", "csv"]);
        assert!(file_choice("save_cake_profile", &json!({"path":"/tmp/profile.xy"})).is_none());
        let image = file_choice("integration_save_image", &json!({"source": "image"})).unwrap();
        assert!(image.save);
        assert_eq!(image.name, "image.png");
        assert_eq!(image.extensions, &["png", "tif", "tiff"]);
        let cake = file_choice("integration_save_image", &json!({"source": "cake"})).unwrap();
        assert!(cake.save);
        assert_eq!(cake.name, "cake.png");
        assert_eq!(cake.extensions, &["png", "tif", "tiff", "txt", "csv"]);
        assert!(
            file_choice("integration_save_image", &json!({"path": "/tmp/image.png"})).is_none()
        );
        assert!(file_choice("integration_open_pattern", &json!({})).is_some());
        assert!(file_choice("integration_open_pattern", &json!({"direction": 1})).is_none());
        assert!(file_choice("integration_overlay", &json!({"operation": "load"})).is_some());
        assert!(file_choice("integration_overlay", &json!({"operation": "capture"})).is_none());
        assert!(
            file_choice(
                "integration_overlay",
                &json!({"operation": "load", "paths": ["a.xy", "b.xy"]})
            )
            .is_none()
        );
        assert!(file_choice("integration_phase", &json!({"operation": "update"})).is_none());
        assert!(file_choice("integration_phase", &json!({"operation": "load"})).is_some());
        assert!(
            file_choice(
                "integration_phase",
                &json!({"operation": "load", "paths": ["/tmp/phase.cif"]})
            )
            .is_none()
        );
        assert!(file_choice("integration_phase_files", &json!({})).is_some());
        assert!(
            file_choice(
                "integration_phase_files",
                &json!({"paths": ["/tmp/phase.cif"]})
            )
            .is_none()
        );
        assert!(
            file_choice("integration_phase_list", &json!({"save": true}))
                .unwrap()
                .save
        );
        assert!(
            !file_choice("integration_phase_list", &json!({"save": false}))
                .unwrap()
                .save
        );
        assert!(
            file_choice("integration_phase_export", &json!({"index": 0}))
                .unwrap()
                .save
        );
        assert!(file_choice("integration_image_background", &json!({"scale": 2})).is_none());
        assert!(file_choice("integration_image_background", &json!({})).is_some());
        assert!(file_choice("integration_flat_field", &json!({"enabled": true})).is_none());
        assert!(file_choice("integration_flat_field", &json!({})).is_some());
        assert!(file_choice("integration_transfer", &json!({"source":"original"})).is_some());
        assert!(file_choice("integration_transfer", &json!({"source":"response"})).is_some());
        assert!(file_choice("integration_transfer", &json!({"enabled":true})).is_none());
        assert!(
            file_choice(
                "integration_transfer",
                &json!({"source":"original","reset":true})
            )
            .is_none()
        );
        assert!(file_choice("integration_image_background", &json!({"poisson":true})).is_none());
        assert!(
            file_choice("integration_save_pattern", &json!({}))
                .unwrap()
                .save
        );
        assert!(
            file_choice("integration_save_batch", &json!({}))
                .unwrap()
                .save
        );
        assert!(
            !file_choice("mask_file", &json!({"add": true}))
                .unwrap()
                .save
        );
        let flipped = file_choice("mask_file", &json!({"save": true, "flipud": true})).unwrap();
        assert_eq!(flipped.name, "mask.npy");
        assert_eq!(flipped.extensions, &["npy", "edf"]);
        assert!(file_choice("state", &json!({})).is_none());
        assert!(file_choice("map_load", &json!({})).is_some());
        assert!(file_choice("map_load", &json!({"paths": ["a.tif"]})).is_none());
        assert!(file_choice("map_load", &json!({"reintegrate": true})).is_none());
        assert!(file_choice("map_batch", &json!({})).is_some());
        assert!(file_choice("map_export", &json!({})).unwrap().save);
        assert_eq!(
            file_choice("map_export", &json!({"png_data": "png"}))
                .unwrap()
                .name,
            "map.png"
        );
    }
}
