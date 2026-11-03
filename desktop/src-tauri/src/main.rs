#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod calibration_tooltip;
mod color_picker;
mod processor;
mod phase_editor;

use calibration_tooltip::{
    calibration_tooltip_ready, hide_calibration_tooltip, present_calibration_tooltip,
    show_calibration_tooltip, TooltipState,
};

use processor::{Packet, Processor};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{Manager, State};
use tauri_plugin_dialog::DialogExt;

struct Host {
    processor: Result<Arc<Processor>, String>,
    smoke: bool,
}

struct FileChoice {
    label: &'static str,
    extensions: &'static [&'static str],
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
    ) && payload["path"].is_null()
}

fn file_choice(action: &str, payload: &Value) -> Option<FileChoice> {
    if matches!(action, "integration_phase_files" | "integration_phase") && payload.get("paths").is_some_and(|v| !v.is_null()) {
        return None;
    }
    if action == "map_load"
        && (payload.get("paths").is_some_and(|v| !v.is_null()) || payload["reintegrate"] == true)
    {
        return None;
    }
    if action == "integration_overlay" && payload.get("paths").is_some_and(|v| !v.is_null()) {
        return None;
    }
    if action == "integration_phase_export" && payload["save_current"] == true { return None; }
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
        && (!payload["scale"].is_null() || !payload["offset"].is_null())
    {
        return None;
    }
    if action == "integration_flat_field" && !payload["enabled"].is_null() {
        return None;
    }
    let (label, extensions, name, save): (_, &[&str], _, _) = match action {
        "open_image" => (
            "Detector images",
            &["tif", "tiff", "edf", "cbf", "h5", "hdf5", "nxs", "mar3450"],
            "",
            false,
        ),
        "map_load" => (
            "Scan detector images",
            &["tif", "tiff", "edf", "cbf", "h5", "hdf5", "nxs", "mar3450"],
            "",
            false,
        ),
        "map_batch" => ("Processed batch", &["h5", "hdf5", "nxs"], "", false),
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
        "integration_save_pattern" => (
            "Diffraction pattern",
            &["xy", "xye", "chi", "dat", "fxye"],
            "pattern.xy",
            true,
        ),
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
        "integration_phase_list" => ("Phase List", &["txt"], "phase_list.txt", payload["save"] == true),
        "integration_phase_export" if payload["format"] == "eosmat" => ("Material", &["eosmat"], "material.eosmat", true),
        "integration_phase_export" if payload["format"] == "txt" => ("Reflection table", &["txt"], "reflections.txt", true),
        "integration_phase_export" => ("Phase or material", &["eosmat", "jcpds", "txt"], "phase.eosmat", true),
        "integration_phase" | "integration_phase_files" => (
            "Diffraction phase",
            &["jcpds", "cif", "eosmat", "json"],
            "",
            false,
        ),
        "integration_image_background" | "integration_flat_field" => (
            "Detector image",
            &["tif", "tiff", "edf", "cbf", "h5", "hdf5"],
            "",
            false,
        ),
        "integration_save_batch" => ("Integrated batch", &["h5", "csv"], "integrated.h5", true),
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
        "open_calibrant" => ("Calibrant d spacings", &["D", "d"], "", false),
        _ => return None,
    };
    Some(FileChoice {
        label,
        extensions,
        name,
        save,
    })
}

#[tauri::command]
async fn desktop_invoke(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
    host: State<'_, Host>,
    action: String,
    payload: Option<Value>,
    cached_buffers: Option<Vec<String>>,
) -> Result<tauri::ipc::Response, String> {
    if window.label() != "main" && window.label() != "phase-editor" {
        return Err("Unknown desktop window.".into());
    }
    if window.label() == "phase-editor" && !matches!(action.as_str(), "integration_phase_editor" | "integration_phase" | "integration_phase_export") {
        return Err("This command is not available to the phase editor.".into());
    }
    let processor = host.processor.clone()?;
    let cached = cached_buffers.unwrap_or_default();
    let mut payload = payload.unwrap_or_else(|| json!({}));
    if !payload.is_object() {
        return Err("Command arguments must be an object.".into());
    }
    if window.label() == "phase-editor" && action != "integration_phase_editor" {
        payload["editor_only"] = json!(true);
    }
    tauri::async_runtime::spawn_blocking(move || {
        if folder_choice(&action, &payload) {
            let Some(selected) = app.dialog().file().blocking_pick_folder() else {
                return Ok(Packet::metadata(json!({"ok": true, "cancelled": true})));
            };
            payload["path"] = Value::String(
                selected
                    .into_path()
                    .map_err(|e| e.to_string())?
                    .to_string_lossy()
                    .into_owned(),
            );
        }
        if let Some(choice) = file_choice(&action, &payload) {
            let mut dialog = app
                .dialog()
                .file()
                .add_filter(choice.label, choice.extensions)
                .add_filter("All files", &["*"]);
            if let Some(directory) = payload["directory"].as_str() {
                dialog = dialog.set_directory(directory);
            }
            if action == "map_load" || action == "integration_overlay" || action == "integration_phase_files" {
                let Some(selected) = dialog.blocking_pick_files() else {
                    return Ok(Packet::metadata(json!({"ok": true, "cancelled": true})));
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
                return processor.request_packet(&action, payload, cached);
            }
            let selected = if choice.save {
                let name = if action == "integration_save_image" || action == "integration_phase_export" {
                    payload["suggested_name"].as_str().unwrap_or(choice.name)
                } else {
                    choice.name
                };
                dialog.set_file_name(name).blocking_save_file()
            } else {
                dialog.blocking_pick_file()
            };
            let Some(selected) = selected else {
                return Ok(Packet::metadata(json!({"ok": true, "cancelled": true})));
            };
            let path = selected.into_path().map_err(|e| e.to_string())?;
            payload["path"] = Value::String(path.to_string_lossy().into_owned());
        }
        processor.request_packet(&action, payload, cached)
    })
    .await
    .map_err(|e| e.to_string())?
    .map(|packet| tauri::ipc::Response::new(packet.bytes))
}

#[tauri::command]
fn native_smoke_report(
    app: tauri::AppHandle,
    host: State<'_, Host>,
    report: Value,
) -> Result<(), String> {
    if !host.smoke {
        return Err("Native smoke mode is disabled.".into());
    }
    println!("{}", json!({"tauriSmoke": report}));
    if report["stage"] == "hmr" {
        return Ok(());
    }
    app.exit(if report["ok"] == true { 0 } else { 1 });
    Ok(())
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let tooltip_smoke = args.iter().any(|a| a == "--tooltip-smoke");
    let smoke = tooltip_smoke || args.iter().any(|a| a == "--smoke");
    let map_smoke = args.iter().any(|a| a == "--map-smoke");
    let example = args.iter().any(|a| a == "--example");
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(TooltipState::default())
        .manage(Host {
            processor: Processor::start(example).map(Arc::new),
            smoke,
        })
        .invoke_handler(tauri::generate_handler![
            color_picker::prepare_color_picker,
            desktop_invoke,
            phase_editor::open_phase_editor,
            native_smoke_report,
            show_calibration_tooltip,
            hide_calibration_tooltip,
            calibration_tooltip_ready,
            present_calibration_tooltip
        ])
        .setup(move |app| {
            color_picker::install()?;
            let window = app.get_webview_window("main").unwrap();
            if tauri::is_dev() {
                window.set_title("Dioptas · Tauri live preview")?;
            }
            if smoke {
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_secs(120));
                    eprintln!("Native smoke timed out before receiving a report.");
                    handle.exit(1);
                });
            }
            Ok(())
        })
        .on_page_load(move |webview, payload| {
            if smoke && webview.label() == "phase-editor" && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                let _ = webview.eval(include_str!("../../scripts/phase_editor_native_smoke.js"));
            }
            if smoke
                && webview.label() == "main"
                && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished)
            {
                if !tooltip_smoke {
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(include_str!("../../scripts/binary_native_smoke.js"));
                    let _ = webview.eval(include_str!("../../scripts/mask_native_smoke.js"));
                    let _ = webview.eval(include_str!("../../scripts/phase_native_smoke.js"));
                }
                let _ = webview.eval(if tooltip_smoke {
                    include_str!("../../scripts/calibration_tooltip_native_smoke.js")
                } else if map_smoke {
                    include_str!("../../scripts/tauri_map_smoke.js")
                } else {
                    include_str!("../../scripts/tauri_smoke.js")
                });
            }
        })
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            if matches!(
                event,
                tauri::WindowEvent::Focused(false)
                    | tauri::WindowEvent::Moved(_)
                    | tauri::WindowEvent::Resized(_)
            ) {
                let _ = calibration_tooltip::dismiss(window.app_handle(), None);
            }
            if matches!(event, tauri::WindowEvent::Destroyed) {
                if let Some(editor) = window.app_handle().get_webview_window("phase-editor") { let _ = editor.destroy(); }
                if let Some(popup) = window
                    .app_handle()
                    .get_webview_window("calibration-tooltip")
                {
                    let _ = popup.destroy();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Could not build the Dioptas native window");
    app.run(|handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            if let Ok(processor) = &handle.state::<Host>().processor {
                processor.shutdown();
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
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
        assert!(file_choice("integration_overlay", &json!({"operation": "load", "paths": ["a.xy", "b.xy"]})).is_none());
        assert!(file_choice("integration_phase", &json!({"operation": "update"})).is_none());
        assert!(file_choice("integration_phase", &json!({"operation": "load"})).is_some());
        assert!(file_choice("integration_phase", &json!({"operation": "load", "paths": ["/tmp/phase.cif"]})).is_none());
        assert!(file_choice("integration_phase_files", &json!({})).is_some());
        assert!(file_choice("integration_phase_files", &json!({"paths": ["/tmp/phase.cif"]})).is_none());
        assert!(file_choice("integration_phase_list", &json!({"save": true})).unwrap().save);
        assert!(!file_choice("integration_phase_list", &json!({"save": false})).unwrap().save);
        assert!(file_choice("integration_phase_export", &json!({"index": 0})).unwrap().save);
        assert!(file_choice("integration_image_background", &json!({"scale": 2})).is_none());
        assert!(file_choice("integration_image_background", &json!({})).is_some());
        assert!(file_choice("integration_flat_field", &json!({"enabled": true})).is_none());
        assert!(file_choice("integration_flat_field", &json!({})).is_some());
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
