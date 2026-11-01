#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod processor;

use processor::Processor;
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

fn file_choice(action: &str, payload: &Value) -> Option<FileChoice> {
    if payload.get("path").is_some_and(|v| !v.is_null()) || payload["reset"] == true {
        return None;
    }
    let (label, extensions, name, save): (_, &[&str], _, _) = match action {
        "open_image" => (
            "Detector images",
            &["tif", "tiff", "edf", "cbf", "h5", "hdf5", "nxs", "mar3450"],
            "",
            false,
        ),
        "open_calibration" => ("PONI calibration", &["poni"], "", false),
        "save_calibration" => ("PONI calibration", &["poni"], "calibration.poni", true),
        "open_project" => ("Dioptas project", &["dio"], "", false),
        "save_project" => ("Dioptas project", &["dio"], "experiment.dio", true),
        "export_pattern" => ("XY pattern", &["xy"], "pattern.xy", true),
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
) -> Result<Value, String> {
    if window.label() != "main" {
        return Err("Unknown desktop window.".into());
    }
    let processor = host.processor.clone()?;
    let mut payload = payload.unwrap_or_else(|| json!({}));
    if !payload.is_object() {
        return Err("Command arguments must be an object.".into());
    }
    tauri::async_runtime::spawn_blocking(move || {
        if let Some(choice) = file_choice(&action, &payload) {
            let dialog = app
                .dialog()
                .file()
                .add_filter(choice.label, choice.extensions)
                .add_filter("All files", &["*"]);
            let selected = if choice.save {
                dialog.set_file_name(choice.name).blocking_save_file()
            } else {
                dialog.blocking_pick_file()
            };
            let Some(selected) = selected else {
                return Ok(json!({"ok": true, "cancelled": true}));
            };
            let path = selected.into_path().map_err(|e| e.to_string())?;
            payload["path"] = Value::String(path.to_string_lossy().into_owned());
        }
        processor.request(&action, payload)
    })
    .await
    .map_err(|e| e.to_string())?
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
    let smoke = args.iter().any(|a| a == "--smoke");
    let example = args.iter().any(|a| a == "--example");
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Host {
            processor: Processor::start(example).map(Arc::new),
            smoke,
        })
        .invoke_handler(tauri::generate_handler![
            desktop_invoke,
            native_smoke_report
        ])
        .setup(move |app| {
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
            if smoke && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/mask_native_smoke.js"));
                let _ = webview.eval(include_str!("../../scripts/tauri_smoke.js"));
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
    fn dialogs_only_for_file_commands_without_explicit_paths_or_reset() {
        assert!(file_choice("open_image", &json!({})).is_some());
        assert!(file_choice("open_image", &json!({"path": "/tmp/image.tif"})).is_none());
        assert!(file_choice("distortion_file", &json!({"reset": true})).is_none());
        assert!(file_choice("detector_file", &json!({"reset": true})).is_none());
        assert!(
            file_choice("mask_file", &json!({"save": true}))
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
    }
}
