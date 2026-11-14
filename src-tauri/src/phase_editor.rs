use serde_json::json;
use tauri::{Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

#[tauri::command]
pub fn open_phase_editor(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
    uid: String,
) -> Result<(), String> {
    if window.label() != "main" || uid.len() != 32 || !uid.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("Invalid phase editor target.".into());
    }
    if let Some(editor) = app.get_webview_window("phase-editor") {
        editor
            .emit("phase-editor-target", json!({ "uid": uid }))
            .map_err(|e| e.to_string())?;
        editor.show().map_err(|e| e.to_string())?;
        editor.unminimize().map_err(|e| e.to_string())?;
        return editor.set_focus().map_err(|e| e.to_string());
    }
    crate::smoke_storage::configure(
        &app,
        WebviewWindowBuilder::new(
            &app,
            "phase-editor",
            WebviewUrl::App(format!("index.html?phase_uid={uid}").into()),
        ),
    )
    .title(crate::application_title(&app, "Phase Editor"))
    .inner_size(1200., 760.)
    .min_inner_size(760., 420.)
    .resizable(true)
    .decorations(true)
    .disable_drag_drop_handler()
    .build()
    .map_err(|e| e.to_string())?;
    Ok(())
}
