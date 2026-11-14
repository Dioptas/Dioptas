#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app_update;
mod batch_export;
mod calibration_tooltip;
mod color_picker;
mod detector_window;
mod map_window;
mod peritheos_manual;
mod phase_editor;
mod processor;
mod processor_reload;
mod recovery;
mod smoke_dialog;
mod smoke_storage;

use calibration_tooltip::{
    calibration_tooltip_ready, hide_calibration_tooltip, present_calibration_tooltip,
    show_calibration_tooltip, TooltipState,
};

use dioptas_contract::image_formats::{COMPRESSED_IMAGE_EXTENSIONS, DETECTOR_IMAGE_EXTENSIONS};
use processor::{wire_contract, Backend, Packet};
use processor_reload::ProcessorHost;
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use tauri::{Manager, State};
use tauri_plugin_dialog::DialogExt;

fn application_title(app: &tauri::AppHandle, context: &str) -> String {
    let base = format!("Dioptas {}", app.package_info().version);
    if context.is_empty() {
        base
    } else {
        format!("{base} — {context}")
    }
}

struct Host {
    processor: Result<Arc<ProcessorHost>, String>,
    smoke: bool,
    closing: AtomicBool,
    exit_ready: AtomicBool,
    recovery: Arc<recovery::Recovery>,
    active_commands: Arc<recovery::ActiveCommands>,
}

fn begin_close(app: &tauri::AppHandle) {
    let host = app.state::<Host>();
    if host.closing.swap(true, Ordering::SeqCst) {
        return;
    }
    host.active_commands.stop();
    let commands = host.active_commands.clone();
    let recovery = host.recovery.clone();
    let processor = host.processor.clone();
    let app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        commands.wait();
        if let Ok(processor) = processor {
            use tauri::Emitter;
            let _ = app.emit_to("main", "dioptas-recovery-saving", json!(true));
            while let Err(error) = recovery.checkpoint(&processor, true) {
                let retry = app
                    .dialog()
                    .message(format!(
                        "The previous recovery file was preserved.\n\n{error}"
                    ))
                    .title("Could not save previous work")
                    .buttons(tauri_plugin_dialog::MessageDialogButtons::OkCancelCustom(
                        "Retry".into(),
                        "Close without saving".into(),
                    ))
                    .blocking_show();
                if !retry {
                    break;
                }
            }
        }
        map_window::save(&app);
        app.state::<Host>().exit_ready.store(true, Ordering::SeqCst);
        app.exit(0);
    });
}

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
        payload["output_directory"] = json!(folder
            .into_path()
            .map_err(|e| e.to_string())?
            .to_string_lossy());
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
        "open_calibrant" => ("Calibrant d spacings", &["D", "d"], "", false),
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

fn window_action_allowed(window: &str, action: &str) -> bool {
    match window {
        "main" => true,
        "phase-editor" => matches!(
            action,
            "integration_phase_editor" | "integration_phase" | "integration_phase_export"
        ),
        "map-window" => matches!(
            action,
            "map_snapshot" | "map_display" | "map_levels" | "progress"
        ),
        "batch-window" => matches!(action, "batch_snapshot" | "batch_levels"),
        _ => false,
    }
}

// Documentation navigation is an explicit UI action; numerical workers never launch a browser.
fn finish_packet(packet: Result<Packet, String>, action: &str) -> Result<Packet, String> {
    let packet = packet?;
    if action == "integration_phase_documentation" {
        let result = packet.result_value()?;
        let metadata = wire_contract::response_metadata(&result)?;
        if let Some(url) = result["documentationUrl"].as_str().filter(|_| metadata.ok) {
            peritheos_manual::open_system_browser(url)?;
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
    cached_products: Option<Value>,
) -> Result<tauri::ipc::Response, String> {
    if !window_action_allowed(window.label(), &action) {
        return Err("This command is not available to this desktop window.".into());
    }
    if host.closing.load(Ordering::SeqCst) && action != "cancel_refinement" && action != "progress"
    {
        return Err("Saving the session before closing…".into());
    }
    let _admitted = if matches!(action.as_str(), "cancel_refinement" | "progress") {
        None
    } else {
        Some(host.active_commands.enter()?)
    };
    let processor = host.processor.clone()?;
    let cached = cached_buffers.unwrap_or_default();
    if let Some(products) = &cached_products {
        wire_contract::validate_cached_products(products)?;
    }
    let mut payload = payload.unwrap_or_else(|| json!({}));
    if !payload.is_object() {
        return Err("Command arguments must be an object.".into());
    }
    // Check present field types before presenting a native chooser. Required
    // paths and scientific invariants remain with the native handlers.
    wire_contract::validate_payload(&action, &payload)?;
    if window.label() == "phase-editor" && action != "integration_phase_editor" {
        payload["editor_only"] = json!(true);
    }
    tauri::async_runtime::spawn_blocking(move || {
        if action == "choose_hdf5_companion" {
            let mut dialog = app
                .dialog()
                .file()
                .set_title("Choose the declared HDF5 source file");
            if let Some(directory) = payload["directory"].as_str() {
                dialog = dialog.set_directory(directory);
            }
            let Some(selected) = dialog.blocking_pick_file() else {
                return Ok(Packet::cancelled());
            };
            let selected = selected.into_path().map_err(|e| e.to_string())?;
            return Ok(Packet::metadata(
                json!({"ok":true,"chosenPath":selected.to_string_lossy()}),
            ));
        }
        if folder_choice(&action, &payload) {
            let Some(selected) = app.dialog().file().blocking_pick_folder() else {
                return Ok(Packet::cancelled());
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
                .add_filter(choice.label, choice.extensions);
            if let Some((label, extensions)) = choice.compressed {
                dialog = dialog.add_filter(label, extensions);
            }
            dialog = dialog.add_filter("All files", &["*"]);
            if action == "integration_save_batch" {
                dialog = dialog.set_title(if batch_export::multifile(&payload) {
                    "Choose Batch export basename"
                } else {
                    "Save Batch data"
                });
            }
            if let Some(directory) = payload["directory"].as_str() {
                dialog = dialog.set_directory(directory);
            }
            if matches!(
                action.as_str(),
                "scxrd_load"
                    | "map_load"
                    | "batch_load"
                    | "batch_load_data"
                    | "integration_overlay"
                    | "integration_phase_files"
            ) || (action == "open_image" && payload["multiple"] == true)
            {
                let Some(selected) = dialog.blocking_pick_files() else {
                    return Ok(Packet::cancelled());
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
                    return Ok(Packet::cancelled());
                }
                return finish_packet(
                    processor.request_packet_with_products(
                        &action,
                        payload,
                        cached,
                        cached_products,
                    ),
                    &action,
                );
            }
            let selected = if choice.save {
                let name = if action == "integration_save_batch" {
                    batch_export::suggested_name(&payload, choice.name)
                } else if matches!(
                    action.as_str(),
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
                return Ok(Packet::cancelled());
            };
            let path = selected.into_path().map_err(|e| e.to_string())?;
            payload["path"] = Value::String(path.to_string_lossy().into_owned());
        }
        if !choose_batch_image_output(&app, &action, &mut payload)? {
            return Ok(Packet::cancelled());
        }
        finish_packet(
            processor.request_packet_with_products(&action, payload, cached, cached_products),
            &action,
        )
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

/// Persist window placement and stop the processor before the process ends.
fn release_host(handle: &tauri::AppHandle) {
    handle.state::<Host>().closing.store(true, Ordering::SeqCst);
    map_window::save(handle);
    if let Ok(processor) = &handle.state::<Host>().processor {
        processor.shutdown();
    }
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let pattern_benchmark = args.iter().any(|a| a == "--pattern-benchmark");
    let navigation_benchmark = args.iter().any(|a| a == "--navigation-benchmark");
    let tooltip_smoke = args.iter().any(|a| a == "--tooltip-smoke");
    let standalone_smoke = args.iter().any(|a| a == "--standalone-smoke");
    let smoke = standalone_smoke
        || pattern_benchmark
        || navigation_benchmark
        || tooltip_smoke
        || args.iter().any(|a| a == "--smoke");
    let batch_smoke = std::env::args().any(|arg| arg == "--batch-smoke");
    let detector_smoke = args.iter().any(|a| a == "--detector-smoke");
    let map_smoke = args.iter().any(|a| a == "--map-smoke");
    let example = args.iter().any(|a| a == "--example");
    let mut context = tauri::generate_context!();
    let initial_title = format!("Dioptas {}", context.package_info().version);
    for window in &mut context.config_mut().app.windows {
        if window.label == "main" {
            window.title = initial_title.clone();
        }
    }
    if smoke {
        // Create test windows with private WebKit storage. Production windows
        // retain their normal configuration and storage.
        for window in &mut context.config_mut().app.windows {
            window.create = false;
        }
    }
    // Installed releases with a verification key update themselves. Previews,
    // local builds and isolated test windows never contact the release server.
    let updates = app_update::enabled(context.config(), smoke);
    let mut builder = tauri::Builder::default().plugin(tauri_plugin_dialog::init());
    if updates {
        builder = builder.plugin(tauri_plugin_updater::Builder::new().build());
    }
    let app = builder
        .manage(app_update::UpdateState::new(updates))
        .manage(TooltipState::default())
        .manage(map_window::MapWindowState::default())
        .manage(map_window::BatchWindowState::default())
        .manage(map_window::DetectorWindowState::default())
        .manage(detector_window::DetectorSnapshot::default())
        .invoke_handler(tauri::generate_handler![
            color_picker::prepare_color_picker,
            desktop_invoke,
            recovery::session_recovery,
            peritheos_manual::open_peritheos_manual,
            phase_editor::open_phase_editor,
            map_window::open_map_window,
            map_window::close_map_window,
            map_window::open_batch_window,
            map_window::close_batch_window,
            detector_window::open_detector_window,
            detector_window::close_detector_window,
            detector_window::publish_detector_snapshot,
            detector_window::detector_snapshot,
            native_smoke_report,
            app_update::update_check,
            app_update::update_download,
            app_update::update_apply,
            app_update::open_update_page,
            show_calibration_tooltip,
            hide_calibration_tooltip,
            calibration_tooltip_ready,
            present_calibration_tooltip
        ])
        .setup(move |app| {
            let resources = app.path().resource_dir()?.join("dioptas");
            let backend = Backend::requested(&args, std::env::var("DIOPTAS_BACKEND").ok().as_deref());
            let recovery_directory = if smoke || example || backend != Ok(Backend::Rust) { None } else {
                Some(std::env::var_os("DIOPTAS_RECOVERY_DIRECTORY").map(std::path::PathBuf::from)
                    .unwrap_or(app.path().app_data_dir()?.join("recovery")))
            };
            app.manage(Host {
                processor: backend
                    .and_then(|backend| ProcessorHost::start(example, backend, Some(&resources))),
                smoke,
                closing: AtomicBool::new(false),
                exit_ready: AtomicBool::new(false),
                recovery: Arc::new(recovery::Recovery::new(recovery_directory, recovery::startup_files(&args))),
                active_commands: Arc::new(recovery::ActiveCommands::default()),
            });
            // The timer never writes an idle session. Disk I/O and
            // serialization stay off the UI thread.
            if !smoke {
                let handle = app.handle().clone();
                std::thread::spawn(move || loop {
                    std::thread::sleep(std::time::Duration::from_secs(600));
                    let host = handle.state::<Host>();
                    if host.closing.load(Ordering::SeqCst) { break; }
                    if let Ok(processor) = &host.processor {
                        if let Err(error) = host.recovery.checkpoint(processor, false) {
                            use tauri::Emitter;
                            let _ = handle.emit_to("main", "dioptas-recovery-error", error);
                        }
                    }
                });
            }
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
            window.set_title(&application_title(app.handle(), if tauri::is_dev() { "Tauri live preview" } else { "" }))?;
            if navigation_benchmark && std::env::var("DIOPTAS_NAVIGATION_BENCHMARK")
                .ok().and_then(|config| serde_json::from_str::<Value>(&config).ok())
                .is_some_and(|config| config["foreground"] == true) {
                window.show()?;
                window.set_focus()?;
            }
            if smoke {
                use tauri::Listener;
                app.listen("native-smoke-diagnostic", |event| {
                    let diagnostics: Value = serde_json::from_str(event.payload()).unwrap_or_else(|_| json!({"message": event.payload()}));
                    println!("{}", json!({"tauriSmoke": {"stage": "diagnostic", "diagnostics": diagnostics}}));
                });
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_secs(if pattern_benchmark || navigation_benchmark { 600 } else { 120 }));
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
            if smoke && detector_smoke && webview.label() == "detector-window" && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/detector_window_native_child.js"));
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
                if detector_smoke {
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(include_str!("../../scripts/detector_window_native_main.js"));
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
                if navigation_benchmark {
                    if let Ok(config) = std::env::var("DIOPTAS_NAVIGATION_BENCHMARK") {
                        if let Ok(value) = serde_json::from_str::<Value>(&config) {
                            let _ = webview.eval(format!("window.__dioptasNavigationConfig = {value};"));
                        }
                    }
                    let _ = webview.eval(include_str!("../../scripts/image_navigation_native.js"));
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
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    let host = window.app_handle().state::<Host>();
                    if !host.smoke && !host.exit_ready.load(Ordering::SeqCst) {
                        api.prevent_close();
                        begin_close(window.app_handle());
                        return;
                    }
                }
            }
            if window.label() == "main" && matches!(event, tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed) {
                window.app_handle().state::<Host>().closing.store(true, Ordering::SeqCst);
            }
            map_window::window_event(window, event);
            if window.label() == "map-window" && matches!(event, tauri::WindowEvent::Destroyed) {
                use tauri::Emitter;
                let _ = window.app_handle().emit_to("main", "map-window-main", json!({"type": "closed"}));
            }
            if window.label() == "detector-window" && matches!(event, tauri::WindowEvent::Destroyed) {
                use tauri::Emitter;
                detector_window::clear(window.app_handle());
                let _ = window.app_handle().emit_to("main", "detector-window-main", json!({"type": "closed"}));
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
                if let Some(detector) = window.app_handle().get_webview_window("detector-window") { let _ = detector.destroy(); }
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
        #[cfg(any(target_os = "macos", target_os = "ios"))]
        if let tauri::RunEvent::Opened { urls } = &event {
            let files: Vec<_> = urls
                .iter()
                .filter_map(|url| url.to_file_path().ok())
                .map(|path| path.to_string_lossy().into_owned())
                .collect();
            if !files.is_empty() {
                use tauri::Emitter;
                handle.state::<Host>().recovery.opened_files(files);
                let _ = handle.emit_to("main", "dioptas-startup-files", ());
            }
        }
        if let tauri::RunEvent::ExitRequested { api, .. } = &event {
            let host = handle.state::<Host>();
            if !host.smoke && !host.exit_ready.load(Ordering::SeqCst) {
                api.prevent_exit();
                begin_close(handle);
                return;
            }
        }
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            release_host(handle);
        }
    });
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
            assert!(file_choice(
                "integration_save_pattern",
                &json!({"path":format!("/tmp/pattern.{extension}")})
            )
            .is_none());
        }
        assert!(!file_choice("integration_open_pattern", &json!({}))
            .unwrap()
            .extensions
            .contains(&"svg"));
    }

    #[test]
    fn spottiness_save_uses_csv_dialog() {
        let choice = file_choice("integration_save_spottiness", &json!({})).unwrap();
        assert!(choice.save);
        assert_eq!(choice.extensions, &["csv"]);
        assert_eq!(choice.name, "pattern_spottiness.csv");
        assert!(file_choice(
            "integration_save_spottiness",
            &json!({"path":"/tmp/spread.csv"})
        )
        .is_none());
    }

    #[test]
    fn companion_windows_read_only_and_unknown_windows_rejected() {
        assert!(window_action_allowed("batch-window", "batch_snapshot"));
        assert!(window_action_allowed("batch-window", "batch_levels"));
        for action in [
            "batch_select",
            "batch_load",
            "state",
            "integration_save_batch",
            "open_image",
        ] {
            assert!(!window_action_allowed("batch-window", action));
        }
        assert!(!window_action_allowed("unknown", "batch_snapshot"));
        assert!(!window_action_allowed("map-window", "batch_snapshot"));
        assert!(window_action_allowed("map-window", "progress"));
        assert!(!window_action_allowed("map-window", "map_load"));
        for action in [
            "state",
            "open_image",
            "image_levels",
            "pick_peak",
            "mask_edit",
            "integration_correction_preview",
        ] {
            assert!(!window_action_allowed("detector-window", action));
        }
        assert!(window_action_allowed("main", "batch_select"));
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
        assert!(file_choice(
            "save_combined_pattern",
            &json!({"path": "/tmp/combined.xy"})
        )
        .is_none());
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
        assert!(file_choice(
            "integration_overlay",
            &json!({"operation": "load", "paths": ["a.xy", "b.xy"]})
        )
        .is_none());
        assert!(file_choice("integration_phase", &json!({"operation": "update"})).is_none());
        assert!(file_choice("integration_phase", &json!({"operation": "load"})).is_some());
        assert!(file_choice(
            "integration_phase",
            &json!({"operation": "load", "paths": ["/tmp/phase.cif"]})
        )
        .is_none());
        assert!(file_choice("integration_phase_files", &json!({})).is_some());
        assert!(file_choice(
            "integration_phase_files",
            &json!({"paths": ["/tmp/phase.cif"]})
        )
        .is_none());
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
        assert!(file_choice(
            "integration_transfer",
            &json!({"source":"original","reset":true})
        )
        .is_none());
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
