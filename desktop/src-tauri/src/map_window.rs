use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

#[tauri::command]
pub fn open_map_window(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" { return Err("Only the main window may detach the map.".into()); }
    if let Some(map) = app.get_webview_window("map-window") {
        map.show().map_err(|e| e.to_string())?;
        map.unminimize().map_err(|e| e.to_string())?;
        return map.set_focus().map_err(|e| e.to_string());
    }
    WebviewWindowBuilder::new(&app, "map-window", WebviewUrl::App("index.html".into()))
        .title("Map — Dioptas").inner_size(800., 760.).min_inner_size(460., 360.)
        .resizable(true).decorations(true).disable_drag_drop_handler()
        .build().map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn close_map_window(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" { return Err("Only the main window may dock the map.".into()); }
    if let Some(map) = app.get_webview_window("map-window") { map.close().map_err(|e| e.to_string())?; }
    Ok(())
}
