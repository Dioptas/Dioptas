#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app_update;
mod batch_export;
mod calibration_tooltip;
mod color_picker;
mod detector_window;
mod file_dialogs;
mod map_window;
mod peritheos_manual;
mod phase_editor;
mod processor;
mod processor_reload;
mod recovery;
mod smoke_dialog;
mod smoke_storage;

use calibration_tooltip::{
    TooltipState, calibration_tooltip_ready, hide_calibration_tooltip, present_calibration_tooltip,
    show_calibration_tooltip,
};

use processor::{Backend, Packet, wire_contract};
use processor_reload::ProcessorHost;
use serde_json::{Value, json};
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
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
        if let Some(packet) = file_dialogs::resolve(&app, &action, &mut payload)? {
            return Ok(packet);
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
                    if let Ok(processor) = &host.processor
                        && let Err(error) = host.recovery.checkpoint(processor, false)
                    {
                        use tauri::Emitter;
                        let _ = handle.emit_to("main", "dioptas-recovery-error", error);
                    }
                });
            }
            #[cfg(debug_assertions)]
            if tauri::is_dev()
                && !smoke
                && Backend::requested(&args, std::env::var("DIOPTAS_BACKEND").ok().as_deref())
                    == Ok(Backend::Rust)
                && let Ok(processor) = &app.state::<Host>().processor
            {
                let handle = app.handle().clone();
                processor.watch(move |status| {
                    use tauri::Emitter;
                    eprintln!(
                        "{}",
                        status["message"].as_str().unwrap_or("Backend update")
                    );
                    let _ = handle.emit("dioptas-backend-update", status);
                });
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
            if navigation_benchmark && webview.label() == "batch-window" && matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                let _ = webview.eval(include_str!("../../scripts/series_navigation_child.js"));
                return;
            }
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
                if !EXPECTED_CHECKED.swap(true, std::sync::atomic::Ordering::SeqCst)
                    && let Ok(expected) = std::env::var("DIOPTAS_MAP_WINDOW_EXPECTED")
                    && let Ok(value) = serde_json::from_str::<Value>(&expected)
                {
                    let _ = webview.eval(format!(
                        "window.__dioptasMapPlacementExpected = {value};"
                    ));
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
                if batch_smoke
                    && let Ok(stage) = std::env::var("DIOPTAS_BATCH_LAYOUT_STAGE")
                {
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(format!("window.__batchLayoutStage={};", json!(stage)));
                    let _ = webview.eval(include_str!("../../scripts/batch_layout_native_smoke.js"));
                    return;
                }
                if pattern_benchmark {
                    let _ = webview.eval(include_str!("../../scripts/native_binary_call.js"));
                    let _ = webview.eval(include_str!("../../scripts/pattern_native_benchmark.js"));
                    return;
                }
                if navigation_benchmark {
                    if let Ok(config) = std::env::var("DIOPTAS_NAVIGATION_BENCHMARK")
                        && let Ok(value) = serde_json::from_str::<Value>(&config)
                    {
                        let _ = webview.eval(format!(
                            "window.__dioptasNavigationConfig = {value};"
                        ));
                    }
                    let _ = webview.eval(include_str!("../../scripts/series_navigation_native.js"));
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
            if window.label() == "main"
                && let tauri::WindowEvent::CloseRequested { api, .. } = event
            {
                let host = window.app_handle().state::<Host>();
                if !host.smoke && !host.exit_ready.load(Ordering::SeqCst) {
                    api.prevent_close();
                    begin_close(window.app_handle());
                    return;
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
}
