use serde_json::{json, Value};
use std::sync::Mutex;
use tauri::{Manager, PhysicalPosition, PhysicalSize, State, WebviewWindow, WebviewWindowBuilder};

const LABEL: &str = "calibration-tooltip";

#[derive(Default)]
pub struct TooltipState(Mutex<Tooltip>);

#[derive(Default)]
struct Tooltip {
    generation: u64,
    source: String,
    content: Option<Value>,
}

// All coordinates here are physical desktop pixels, including negative monitor origins.
fn position(anchor: [f64; 4], size: [f64; 2], work: [f64; 4], scale: f64) -> PhysicalPosition<i32> {
    let margin = 12.0 * scale;
    let gap = 8.0 * scale;
    let right = anchor[2] + gap;
    let left = anchor[0] - size[0] - gap;
    let x = if right + size[0] <= work[2] - margin {
        right
    } else {
        left
    };
    let min_x = work[0] + margin;
    let min_y = work[1] + margin;
    PhysicalPosition::new(
        x.clamp(min_x, (work[2] - margin - size[0]).max(min_x))
            .round() as i32,
        (anchor[1] - size[1] - gap)
            .clamp(min_y, (work[3] - margin - size[1]).max(min_y))
            .round() as i32,
    )
}

fn number(value: &Value) -> Result<f64, String> {
    value
        .as_f64()
        .filter(|v| v.is_finite())
        .ok_or("Invalid tooltip coordinates".into())
}

#[tauri::command]
pub async fn show_calibration_tooltip(
    app: tauri::AppHandle,
    window: WebviewWindow,
    state: State<'_, TooltipState>,
    payload: Value,
) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Only the main window can open calibration help".into());
    }
    let source = payload["source"].as_str().ok_or("Missing help source")?;
    let text = payload["text"].as_str().ok_or("Missing help text")?;
    let font_size = payload["fontSize"]
        .as_str()
        .ok_or("Missing help font size")?;
    let width = number(&payload["width"])?;
    let height = number(&payload["height"])?;
    if !(24.0..=640.0).contains(&width) || !(20.0..=600.0).contains(&height) {
        return Err("Invalid tooltip dimensions".into());
    }
    let origin = window.inner_position().map_err(|e| e.to_string())?;
    let scale = window.scale_factor().map_err(|e| e.to_string())?;
    let anchor = &payload["anchor"];
    let anchor = [
        origin.x as f64 + number(&anchor["left"])? * scale,
        origin.y as f64 + number(&anchor["top"])? * scale,
        origin.x as f64 + number(&anchor["right"])? * scale,
        origin.y as f64 + number(&anchor["bottom"])? * scale,
    ];
    let monitor = window
        .monitor_from_point((anchor[0] + anchor[2]) / 2.0, (anchor[1] + anchor[3]) / 2.0)
        .map_err(|e| e.to_string())?
        .or(window.current_monitor().map_err(|e| e.to_string())?)
        .ok_or("No screen available for calibration help")?;
    let work = monitor.work_area();
    let size = PhysicalSize::new(
        (width * scale).ceil() as u32,
        (height * scale).ceil() as u32,
    );
    let point = position(
        anchor,
        [size.width as f64, size.height as f64],
        [
            work.position.x as f64,
            work.position.y as f64,
            work.position.x as f64 + work.size.width as f64,
            work.position.y as f64 + work.size.height as f64,
        ],
        scale,
    );
    let content = {
        let mut state = state.0.lock().map_err(|e| e.to_string())?;
        state.generation += 1;
        state.source = source.into();
        let content = json!({
            "generation": state.generation,
            "text": text,
            "fontSize": font_size,
            "width": width,
        });
        state.content = Some(content.clone());
        content
    };
    let popup = if let Some(popup) = app.get_webview_window(LABEL) {
        popup.hide().map_err(|e| e.to_string())?;
        popup
    } else {
        crate::smoke_storage::configure(
            &app,
            WebviewWindowBuilder::new(&app, LABEL, tauri::WebviewUrl::App("index.html".into())),
        )
        .title("Calibration help")
        .parent(&window)
        .map_err(|e| e.to_string())?
        .decorations(false)
        .resizable(false)
        .maximizable(false)
        .minimizable(false)
        .closable(false)
        .focused(false)
        .focusable(false)
        .visible(false)
        .skip_taskbar(true)
        .shadow(true)
        .background_color(tauri::webview::Color(41, 45, 50, 255))
        .disable_drag_drop_handler()
        .build()
        .map_err(|e| e.to_string())?
    };
    popup
        .set_ignore_cursor_events(true)
        .map_err(|e| e.to_string())?;
    popup.set_size(size).map_err(|e| e.to_string())?;
    popup.set_position(point).map_err(|e| e.to_string())?;
    // If the document is still loading, its ready command reads the stored content.
    popup
        .eval(format!(
            "window.dispatchEvent(new CustomEvent('calibration-tooltip', {{detail:{content}}}))"
        ))
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn calibration_tooltip_ready(
    window: WebviewWindow,
    state: State<'_, TooltipState>,
) -> Result<Option<Value>, String> {
    if window.label() != LABEL {
        return Err("Unknown tooltip window".into());
    }
    Ok(state.0.lock().map_err(|e| e.to_string())?.content.clone())
}

#[tauri::command]
pub fn present_calibration_tooltip(
    window: WebviewWindow,
    state: State<'_, TooltipState>,
    generation: u64,
) -> Result<(), String> {
    if window.label() != LABEL {
        return Err("Unknown tooltip window".into());
    }
    let state = state.0.lock().map_err(|e| e.to_string())?;
    if state.content.is_some() && state.generation == generation {
        #[cfg(target_os = "macos")]
        {
            // Tauri's show() calls makeKeyAndOrderFront on macOS even for a
            // non-focusable window. Help must only order forward, retaining
            // keyboard focus on the main window and its initiating control.
            let _main = objc2::MainThreadMarker::new()
                .ok_or("Calibration help must be presented on the UI thread")?;
            let pointer = window.ns_window().map_err(|e| e.to_string())?;
            let popup = unsafe { &*pointer.cast::<objc2_app_kit::NSWindow>() };
            popup.orderFront(None);
        }
        #[cfg(not(target_os = "macos"))]
        window.show().map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn dismiss(app: &tauri::AppHandle, source: Option<&str>) -> Result<(), String> {
    let state = app.state::<TooltipState>();
    let mut state = state.0.lock().map_err(|e| e.to_string())?;
    if source.is_none_or(|source| source == state.source) {
        state.content = None;
        if let Some(popup) = app.get_webview_window(LABEL) {
            popup.hide().map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

#[tauri::command]
pub fn hide_calibration_tooltip(
    app: tauri::AppHandle,
    window: WebviewWindow,
    source: String,
) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Only the main window can dismiss calibration help".into());
    }
    dismiss(&app, Some(&source))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn help_can_extend_beyond_app_and_flips_only_at_screen_edge() {
        let screen = [0.0, 24.0, 1920.0, 1080.0];
        // The app can end at x=1000 while its tooltip extends to x=1310.
        assert_eq!(
            position([960.0, 500.0, 982.0, 524.0], [320.0, 100.0], screen, 1.0),
            PhysicalPosition::new(990, 392)
        );
        assert_eq!(
            position([1800.0, 500.0, 1822.0, 524.0], [320.0, 100.0], screen, 1.0),
            PhysicalPosition::new(1472, 392)
        );
    }

    #[test]
    fn retina_and_negative_screen_origins_use_desktop_coordinates() {
        let screen = [-3840.0, -2160.0, 0.0, 0.0];
        assert_eq!(
            position(
                [-800.0, -1000.0, -756.0, -952.0],
                [640.0, 200.0],
                screen,
                2.0
            ),
            PhysicalPosition::new(-740, -1216)
        );
        assert_eq!(
            position(
                [-200.0, -1000.0, -156.0, -952.0],
                [640.0, 200.0],
                screen,
                2.0
            ),
            PhysicalPosition::new(-856, -1216)
        );
        assert_eq!(
            position(
                [-3800.0, -2140.0, -3756.0, -2092.0],
                [640.0, 200.0],
                screen,
                2.0
            )
            .y,
            -2136
        );
    }
}
