#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod calibration_tooltip;
mod color_picker;
mod processor;
mod processor_reload;
mod phase_editor;
mod map_window;
mod smoke_storage;
mod smoke_dialog;

use calibration_tooltip::{
    calibration_tooltip_ready, hide_calibration_tooltip, present_calibration_tooltip,
    show_calibration_tooltip, TooltipState,
};

use processor::{Backend, Packet};
use processor_reload::ProcessorHost;
use serde_json::{json, Value};
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use tauri::{Manager, State};
use tauri_plugin_dialog::DialogExt;

struct Host {
    processor: Result<Arc<ProcessorHost>, String>,
    smoke: bool,
    closing: AtomicBool,
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
            | "batch_folder"
    ) && payload["path"].is_null()
}

fn batch_image_output_choice(action: &str, payload: &Value) -> bool {
    action == "open_image" && payload["batch_mode"] == "save"
        && payload["paths"].as_array().is_some_and(|paths| paths.len() > 1)
        && payload["output_directory"].is_null()
}

fn choose_batch_image_output(app: &tauri::AppHandle, action: &str, payload: &mut Value) -> Result<bool, String> {
    if batch_image_output_choice(action, payload) {
        let Some(folder) = app.dialog().file().blocking_pick_folder() else { return Ok(false); };
        payload["output_directory"] = json!(folder.into_path().map_err(|e| e.to_string())?.to_string_lossy());
    }
    Ok(true)
}

fn file_choice(action: &str, payload: &Value) -> Option<FileChoice> {
    if matches!(action, "integration_phase_files" | "integration_phase") && payload.get("paths").is_some_and(|v| !v.is_null()) {
        return None;
    }
    if matches!(action, "map_load" | "batch_load" | "batch_load_data" | "open_image")
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
        && (!payload["scale"].is_null() || !payload["offset"].is_null() || !payload["poisson"].is_null())
    {
        return None;
    }
    if ["integration_flat_field", "integration_transfer"].contains(&action) && !payload["enabled"].is_null() {
        return None;
    }
    let (label, extensions, name, save): (_, &[&str], _, _) = match action {
        "open_image" => (
            "Detector images",
            &["tif", "tiff", "edf", "cbf", "h5", "hdf5", "nxs", "mar3450"],
            "",
            false,
        ),
        "map_load" | "batch_load" | "batch_load_data" => (
            "Detector images",
            &["tif", "tiff", "edf", "cbf", "h5", "hdf5", "nxs", "mar3450"],
            "",
            false,
        ),
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
        "integration_image_background" | "integration_flat_field" | "integration_transfer" => (
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

fn window_action_allowed(window: &str, action: &str) -> bool {
    match window {
        "main" => true,
        "phase-editor" => matches!(action, "integration_phase_editor" | "integration_phase" | "integration_phase_export"),
        "map-window" => matches!(action, "map_snapshot" | "map_display" | "map_levels" | "progress"),
        "batch-window" => matches!(action, "batch_snapshot" | "batch_levels"),
        _ => false,
    }
}

// Documentation navigation is an explicit UI action; numerical workers never launch a browser.
fn finish_packet(packet: Result<Packet, String>, action: &str) -> Result<Packet, String> {
    let packet = packet?;
    if action == "integration_phase_documentation" {
        let result = packet.result_value()?;
        if let Some(url) = result["documentationUrl"]
            .as_str()
            .filter(|_| result["ok"] == true)
        {
            if !(url.starts_with("https://") || url.starts_with("http://"))
                || url.contains(['\n', '\r', '\0'])
            {
                return Err("Invalid record documentation URL.".into());
            }
            #[cfg(target_os = "macos")]
            let mut command = std::process::Command::new("open");
            #[cfg(target_os = "linux")]
            let mut command = std::process::Command::new("xdg-open");
            #[cfg(target_os = "windows")]
            let mut command = {
                let mut c = std::process::Command::new("rundll32");
                c.arg("url.dll,FileProtocolHandler");
                c
            };
            command
                .arg(url)
                .stdin(std::process::Stdio::null())
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .spawn()
                .map_err(|e| format!("The system browser could not open the documentation: {e}"))?;
        }
    }
    Ok(packet)
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
    if !window_action_allowed(window.label(), &action) {
        return Err("This command is not available to this desktop window.".into());
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
            if matches!(action.as_str(), "map_load" | "batch_load" | "batch_load_data" | "integration_overlay" | "integration_phase_files") || (action == "open_image" && payload["multiple"] == true) {
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
                if !choose_batch_image_output(&app, &action, &mut payload)? {
                    return Ok(Packet::metadata(json!({"ok": true, "cancelled": true})));
                }
                return finish_packet(processor.request_packet(&action, payload, cached), &action);
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
        if !choose_batch_image_output(&app, &action, &mut payload)? {
            return Ok(Packet::metadata(json!({"ok": true, "cancelled": true})));
        }
        finish_packet(processor.request_packet(&action, payload, cached), &action)
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
    if report["stage"] == "cancel-file-dialog" {
        return smoke_dialog::cancel_file_panel();
    }
    println!("{}", json!({"tauriSmoke": report}));
    if matches!(report["stage"].as_str(), Some("hmr" | "diagnostic")) {
        return Ok(());
    }
    app.exit(if report["ok"] == true { 0 } else { 1 });
    Ok(())
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let pattern_benchmark = args.iter().any(|a| a == "--pattern-benchmark");
    let tooltip_smoke = args.iter().any(|a| a == "--tooltip-smoke");
    let standalone_smoke = args.iter().any(|a| a == "--standalone-smoke");
    let smoke = standalone_smoke || pattern_benchmark || tooltip_smoke || args.iter().any(|a| a == "--smoke");
    let batch_smoke = std::env::args().any(|arg| arg == "--batch-smoke");
    let map_smoke = args.iter().any(|a| a == "--map-smoke");
    let example = args.iter().any(|a| a == "--example");
    let mut context = tauri::generate_context!();
    if smoke {
        // Create test windows with private WebKit storage. Production windows
        // retain their normal configuration and storage.
        for window in &mut context.config_mut().app.windows {
            window.create = false;
        }
    }
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(TooltipState::default())
        .manage(map_window::MapWindowState::default())
        .manage(map_window::BatchWindowState::default())
        .invoke_handler(tauri::generate_handler![
            color_picker::prepare_color_picker,
            desktop_invoke,
            phase_editor::open_phase_editor,
            map_window::open_map_window,
            map_window::close_map_window,
            map_window::open_batch_window,
            map_window::close_batch_window,
            native_smoke_report,
            show_calibration_tooltip,
            hide_calibration_tooltip,
            calibration_tooltip_ready,
            present_calibration_tooltip
        ])
        .setup(move |app| {
            let resources = app.path().resource_dir()?.join("dioptas");
            app.manage(Host {
                processor: Backend::requested(&args, std::env::var("DIOPTAS_BACKEND").ok().as_deref())
                    .and_then(|backend| ProcessorHost::start(example, backend, Some(&resources))),
                smoke,
                closing: AtomicBool::new(false),
            });
            #[cfg(debug_assertions)]
            if tauri::is_dev() && !smoke && Backend::requested(&args, std::env::var("DIOPTAS_BACKEND").ok().as_deref()) == Ok(Backend::Rust) {
                if let Ok(processor) = &app.state::<Host>().processor {
                    let handle = app.handle().clone();
                    processor.watch(move |status| {
                        use tauri::Emitter;
                        eprintln!("{}", status["message"].as_str().unwrap_or("Backend update"));
                        let _ = handle.emit("dioptas-backend-update",status);
                    });
                }
            }
            color_picker::install()?;
            let window = if smoke {
                let config = app.config().app.windows.iter().find(|window| window.label == "main").unwrap().clone();
                smoke_storage::configure(app.handle(), tauri::WebviewWindowBuilder::from_config(app.handle(), &config)?).build()?
            } else {
                app.get_webview_window("main").unwrap()
            };
            if tauri::is_dev() {
                window.set_title("Dioptas · Tauri live preview")?;
            }
            if smoke {
                use tauri::Listener;
                app.listen("native-smoke-diagnostic", |event| {
                    let diagnostics: Value = serde_json::from_str(event.payload()).unwrap_or_else(|_| json!({"message": event.payload()}));
                    println!("{}", json!({"tauriSmoke": {"stage": "diagnostic", "diagnostics": diagnostics}}));
                });
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_secs(if pattern_benchmark { 600 } else { 120 }));
                    eprintln!("Native smoke timed out before receiving a report.");
                    handle.exit(1);
                });
            }
            Ok(())
        })
        .on_page_load(move |webview, payload| {
            if smoke && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/field_appearance_check.js"));
                let _ = webview.eval(include_str!("../../scripts/native_smoke_diagnostics.js"));
            }
            if smoke && batch_smoke && std::env::var_os("DIOPTAS_BATCH_LAYOUT_STAGE").is_none() && webview.label() == "batch-window" && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                let _ = webview.eval(include_str!("../../scripts/batch_window_native_smoke.js"));
            }
            if smoke && webview.label() == "map-window" && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                static EXPECTED_CHECKED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
                if !EXPECTED_CHECKED.swap(true, std::sync::atomic::Ordering::SeqCst) {
                    if let Ok(expected) = std::env::var("DIOPTAS_MAP_WINDOW_EXPECTED") {
                        if let Ok(value) = serde_json::from_str::<Value>(&expected) {
                            let _ = webview.eval(format!("window.__dioptasMapPlacementExpected = {value};"));
                        }
                    }
                }
                let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                let _ = webview.eval(include_str!("../../scripts/map_window_native_smoke.js"));
            }
            if smoke && webview.label() == "phase-editor" && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                let _ = webview.eval(include_str!("../../scripts/phase_editor_native_smoke.js"));
            }
            if smoke
                && webview.label() == "main"
                && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished)
            {
                if standalone_smoke {
                    let directory = std::env::var("DIOPTAS_STANDALONE_TEST_DIRECTORY").unwrap_or_default();
                    let _ = webview.eval(format!("window.__dioptasStandaloneDirectory = {};", json!(directory)));
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(include_str!("../../scripts/standalone_native_smoke.js"));
                    return;
                }
                if batch_smoke {
                    if let Ok(stage) = std::env::var("DIOPTAS_BATCH_LAYOUT_STAGE") {
                        let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                        let _ = webview.eval(format!("window.__batchLayoutStage={};", json!(stage)));
                        let _ = webview.eval(include_str!("../../scripts/batch_layout_native_smoke.js"));
                        return;
                    }
                }
                if pattern_benchmark {
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(include_str!("../../scripts/pattern_native_benchmark.js"));
                    return;
                }
                if !tooltip_smoke {
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(include_str!("../../scripts/binary_native_smoke.js"));
                    let _ = webview.eval(include_str!("../../scripts/mask_native_smoke.js"));
                    let _ = webview.eval(include_str!("../../scripts/phase_native_smoke.js"));
                    let _ =
                        webview.eval(include_str!("../../scripts/phase_database_native_smoke.js"));
                }
                let _ = webview.eval(if tooltip_smoke {
                    include_str!("../../scripts/calibration_tooltip_native_smoke.js")
                } else if batch_smoke {
                    include_str!("../../scripts/batch_native_smoke.js")
                } else if map_smoke {
                    let _ = webview.eval(include_str!("../../scripts/map_window_native_main.js"));
                    include_str!("../../scripts/tauri_map_smoke.js")
                } else {
                    include_str!("../../scripts/tauri_smoke.js")
                });
            }
        })
        .on_window_event(|window, event| {
            if window.label() == "main" && matches!(event, tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed) {
                window.app_handle().state::<Host>().closing.store(true, Ordering::SeqCst);
            }
            map_window::window_event(window, event);
            if window.label() == "map-window" && matches!(event, tauri::WindowEvent::Destroyed) {
                use tauri::Emitter;
                let _ = window.app_handle().emit_to("main", "map-window-main", json!({"type": "closed"}));
            }
            if window.label() == "batch-window" && matches!(event, tauri::WindowEvent::Destroyed) {
                use tauri::Emitter;
                let _ = window.app_handle().emit_to("main", "batch-window-main", json!({"type": "closed", "shuttingDown": window.app_handle().state::<Host>().closing.load(Ordering::SeqCst)}));
            }
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
                if let Some(batch) = window.app_handle().get_webview_window("batch-window") { let _ = batch.destroy(); }
                if let Some(map) = window.app_handle().get_webview_window("map-window") { let _ = map.destroy(); }
                if let Some(editor) = window.app_handle().get_webview_window("phase-editor") { let _ = editor.destroy(); }
                if let Some(popup) = window
                    .app_handle()
                    .get_webview_window("calibration-tooltip")
                {
                    let _ = popup.destroy();
                }
            }
        })
        .build(context)
        .expect("Could not build the Dioptas native window");
    app.run(|handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            handle.state::<Host>().closing.store(true, Ordering::SeqCst);
            map_window::save(handle);
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
    fn companion_windows_read_only_and_unknown_windows_rejected() {
        assert!(window_action_allowed("batch-window", "batch_snapshot"));
        assert!(window_action_allowed("batch-window", "batch_levels"));
        for action in ["batch_select", "batch_load", "state", "integration_save_batch", "open_image"] {
            assert!(!window_action_allowed("batch-window", action));
        }
        assert!(!window_action_allowed("unknown", "batch_snapshot"));
        assert!(!window_action_allowed("map-window", "batch_snapshot"));
        assert!(window_action_allowed("map-window", "progress"));
        assert!(!window_action_allowed("map-window", "map_load"));
        assert!(window_action_allowed("main", "batch_select"));
    }
    #[test]
    fn batch_dialogs_distinguish_sources_and_explicit_payloads() {
        assert!(batch_image_output_choice("open_image", &json!({"batch_mode": "save", "paths": ["one.tif", "two.tif"]})));
        assert!(!batch_image_output_choice("open_image", &json!({"batch_mode": "save", "paths": ["one.tif"]})));
        assert!(!batch_image_output_choice("open_image", &json!({"batch_mode": "integrate", "paths": ["one.tif", "two.tif"]})));
        assert!(!batch_image_output_choice("open_image", &json!({"batch_mode": "save", "paths": ["one.tif", "two.tif"], "output_directory": "/tmp"})));
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
        assert!(file_choice("save_combined_pattern", &json!({"path": "/tmp/combined.xy"})).is_none());
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
        assert!(file_choice("integration_transfer", &json!({"source":"original"})).is_some());
        assert!(file_choice("integration_transfer", &json!({"source":"response"})).is_some());
        assert!(file_choice("integration_transfer", &json!({"enabled":true})).is_none());
        assert!(file_choice("integration_transfer", &json!({"source":"original","reset":true})).is_none());
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
