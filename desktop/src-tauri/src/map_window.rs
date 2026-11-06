use serde_json::{json, Value};
use std::{fs, path::PathBuf, sync::Mutex};
use tauri::{LogicalSize, Manager, PhysicalPosition, WebviewUrl, WebviewWindowBuilder};

fn label<const K: u8>() -> &'static str {
    if K == 0 {
        "map-window"
    } else {
        "batch-window"
    }
}
const DEFAULT_SIZE: [f64; 2] = [800., 760.];
const MIN_SIZE: [f64; 2] = [460., 360.];

#[derive(Clone, Debug, PartialEq)]
struct Screen {
    name: Option<String>,
    origin: [f64; 2],
    size: [f64; 2],
    work_origin: [f64; 2],
    work_size: [f64; 2],
    scale: f64,
}
impl From<tauri::Monitor> for Screen {
    fn from(monitor: tauri::Monitor) -> Self {
        Self {
            name: monitor.name().cloned(),
            origin: [monitor.position().x as f64, monitor.position().y as f64],
            size: [monitor.size().width as f64, monitor.size().height as f64],
            work_origin: [
                monitor.work_area().position.x as f64,
                monitor.work_area().position.y as f64,
            ],
            work_size: [
                monitor.work_area().size.width as f64,
                monitor.work_area().size.height as f64,
            ],
            scale: monitor.scale_factor(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
struct Placement {
    screen: Screen,
    // Logical inner size, frame thickness, and outer-position offset from the
    // monitor work area. This survives screen rearrangement and DPI changes.
    size: [f64; 2],
    frame: [f64; 2],
    offset: [f64; 2],
}
impl Placement {
    fn json(&self) -> Value {
        json!({"version": 1, "size": self.size, "frame": self.frame, "offset": self.offset,
            "screen": {"name": self.screen.name, "origin": self.screen.origin,
                "size": self.screen.size, "workOrigin": self.screen.work_origin,
                "workSize": self.screen.work_size, "scale": self.screen.scale}})
    }
    fn parse(value: &Value) -> Option<Self> {
        fn pair(value: &Value, min: f64, max: f64) -> Option<[f64; 2]> {
            let values = value.as_array()?;
            if values.len() != 2 {
                return None;
            }
            let a = values[0].as_f64()?;
            let b = values[1].as_f64()?;
            (a.is_finite() && b.is_finite() && (min..=max).contains(&a) && (min..=max).contains(&b))
                .then_some([a, b])
        }
        if value["version"] != 1 {
            return None;
        }
        let screen = &value["screen"];
        let scale = screen["scale"].as_f64()?;
        if !(0.25..=8.).contains(&scale) {
            return None;
        }
        Some(Self {
            size: pair(&value["size"], 1., 100_000.)?,
            frame: pair(&value["frame"], 0., 500.)?,
            offset: pair(&value["offset"], -100_000., 100_000.)?,
            screen: Screen {
                name: screen["name"].as_str().map(str::to_owned),
                origin: pair(&screen["origin"], -100_000., 100_000.)?,
                size: pair(&screen["size"], 1., 100_000.)?,
                work_origin: pair(&screen["workOrigin"], -100_000., 100_000.)?,
                work_size: pair(&screen["workSize"], 1., 100_000.)?,
                scale,
            },
        })
    }
}

#[derive(Default)]
pub struct WindowPlacementState<const K: u8>(Mutex<WindowState>);
pub type MapWindowState = WindowPlacementState<0>;
pub type BatchWindowState = WindowPlacementState<1>;
#[derive(Default)]
struct WindowState {
    last_normal: Option<Placement>,
    restoring: bool,
}

fn state_path<const K: u8>(app: &tauri::AppHandle) -> Option<PathBuf> {
    // Native tests use a disposable file, never the user's window preferences.
    if app.state::<crate::Host>().smoke {
        return std::env::var_os(if K == 0 {
            "DIOPTAS_MAP_WINDOW_STATE"
        } else {
            "DIOPTAS_BATCH_WINDOW_STATE"
        })
        .map(PathBuf::from);
    }
    app.path().app_config_dir().ok().map(|dir| {
        dir.join(if K == 0 {
            "map-window-v1.json"
        } else {
            "batch-window-v1.json"
        })
    })
}
fn load<const K: u8>(app: &tauri::AppHandle) -> Option<Placement> {
    let bytes = fs::read(state_path::<K>(app)?).ok()?;
    if bytes.len() > 8192 {
        return None;
    }
    Placement::parse(&serde_json::from_slice::<Value>(&bytes).ok()?)
}
fn persist<const K: u8>(app: &tauri::AppHandle, placement: &Placement) -> Result<(), String> {
    let Some(path) = state_path::<K>(app) else {
        return Ok(());
    };
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let temporary = path.with_extension(format!("{}.tmp", std::process::id()));
    fs::write(&temporary, placement.json().to_string()).map_err(|e| e.to_string())?;
    fs::rename(&temporary, &path).map_err(|e| e.to_string())
}

fn target_screen(saved: &Placement, screens: &[Screen], fallback: usize) -> Option<usize> {
    let matching =
        screens
            .iter()
            .enumerate()
            .filter(|(_, screen)| match (&saved.screen.name, &screen.name) {
                (Some(a), Some(b)) => a == b,
                (None, None) => {
                    saved.screen.origin == screen.origin && saved.screen.size == screen.size
                }
                _ => false,
            });
    matching
        .min_by(|(_, a), (_, b)| {
            let distance = |s: &Screen| {
                (s.origin[0] - saved.screen.origin[0]).hypot(s.origin[1] - saved.screen.origin[1])
            };
            distance(a).total_cmp(&distance(b))
        })
        .map(|(i, _)| i)
        .or_else(|| (!screens.is_empty()).then(|| fallback.min(screens.len() - 1)))
}
fn restored_size(saved: &Placement, screen: &Screen) -> [f64; 2] {
    std::array::from_fn(|i| {
        let available = (screen.work_size[i] / screen.scale - saved.frame[i]).max(1.);
        saved.size[i].clamp(MIN_SIZE[i].min(available), available)
    })
}
fn restored_position(saved: &Placement, screen: &Screen, outer: [f64; 2]) -> PhysicalPosition<i32> {
    let p: [i32; 2] = std::array::from_fn(|i| {
        let origin = screen.work_origin[i];
        (origin + saved.offset[i] * screen.scale)
            .clamp(
                origin,
                (origin + screen.work_size[i] - outer[i]).max(origin),
            )
            .round() as i32
    });
    PhysicalPosition::new(p[0], p[1])
}

fn remember<const K: u8>(app: &tauri::AppHandle) {
    let state = app.state::<WindowPlacementState<K>>();
    if state.0.lock().unwrap().restoring {
        return;
    }
    let Some(window) = app.get_webview_window(label::<K>()) else {
        return;
    };
    // Closing or quitting while minimized/maximized retains the normal bounds.
    if window.is_minimized().unwrap_or(true)
        || window.is_maximized().unwrap_or(true)
        || window.is_fullscreen().unwrap_or(true)
    {
        return;
    }
    let capture = || -> Option<Placement> {
        let screen: Screen = window.current_monitor().ok()??.into();
        let scale = window.scale_factor().ok()?;
        let inner = window.inner_size().ok()?;
        let outer = window.outer_size().ok()?;
        let position = window.outer_position().ok()?;
        Some(Placement {
            screen: screen.clone(),
            size: [inner.width as f64 / scale, inner.height as f64 / scale],
            frame: [
                (outer.width as f64 - inner.width as f64).max(0.) / scale,
                (outer.height as f64 - inner.height as f64).max(0.) / scale,
            ],
            offset: [
                (position.x as f64 - screen.work_origin[0]) / screen.scale,
                (position.y as f64 - screen.work_origin[1]) / screen.scale,
            ],
        })
    };
    if let Some(placement) = capture() {
        state.0.lock().unwrap().last_normal = Some(placement);
    }
}
fn save_kind<const K: u8>(app: &tauri::AppHandle) {
    remember::<K>(app);
    let placement = app
        .state::<WindowPlacementState<K>>()
        .0
        .lock()
        .unwrap()
        .last_normal
        .clone();
    if let Some(placement) = placement {
        if let Err(error) = persist::<K>(app, &placement) {
            eprintln!("Could not save map window placement: {error}");
        }
    }
}
fn window_event_kind<const K: u8>(window: &tauri::Window, event: &tauri::WindowEvent) {
    if (window.label() == label::<K>() || window.label() == "main")
        && matches!(event, tauri::WindowEvent::CloseRequested { .. })
    {
        save_kind::<K>(window.app_handle());
    } else if window.label() == label::<K>()
        && matches!(
            event,
            tauri::WindowEvent::Moved(_)
                | tauri::WindowEvent::Resized(_)
                | tauri::WindowEvent::ScaleFactorChanged { .. }
        )
    {
        remember::<K>(window.app_handle());
    }
}

fn open_window<const K: u8>(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Only the main window may detach the map.".into());
    }
    if let Some(map) = app.get_webview_window(label::<K>()) {
        map.show().map_err(|e| e.to_string())?;
        map.unminimize().map_err(|e| e.to_string())?;
        return map.set_focus().map_err(|e| e.to_string());
    }
    let state = app.state::<WindowPlacementState<K>>();
    let saved = state
        .0
        .lock()
        .unwrap()
        .last_normal
        .clone()
        .or_else(|| load::<K>(&app));
    let screens: Vec<Screen> = window
        .available_monitors()
        .map_err(|e| e.to_string())?
        .into_iter()
        .map(Screen::from)
        .collect();
    let fallback_screen = window
        .current_monitor()
        .ok()
        .flatten()
        .or_else(|| window.primary_monitor().ok().flatten())
        .map(Screen::from);
    let fallback = fallback_screen
        .and_then(|screen| screens.iter().position(|s| *s == screen))
        .unwrap_or(0);
    let target = saved
        .as_ref()
        .and_then(|saved| target_screen(saved, &screens, fallback));
    state.0.lock().unwrap().restoring = true;
    let opened = (|| -> Result<(), String> {
        let map =
            crate::smoke_storage::configure(
                &app,
                WebviewWindowBuilder::new(&app, label::<K>(), WebviewUrl::App("index.html".into())),
            )
                .title(if K == 0 {
                    "Map — Dioptas"
                } else {
                    "Batch — Dioptas"
                })
                .inner_size(
                    if K == 0 { DEFAULT_SIZE[0] } else { 900. },
                    if K == 0 { DEFAULT_SIZE[1] } else { 600. },
                )
                .min_inner_size(MIN_SIZE[0], MIN_SIZE[1])
                .visible(false)
                .resizable(true)
                .decorations(true)
                .disable_drag_drop_handler()
                .build()
                .map_err(|e| e.to_string())?;
        if let (Some(saved), Some(index)) = (saved.as_ref(), target) {
            let screen = &screens[index];
            let size = restored_size(saved, screen);
            map.set_min_size(Some(LogicalSize::new(
                size[0].min(MIN_SIZE[0]),
                size[1].min(MIN_SIZE[1]),
            )))
            .map_err(|e| e.to_string())?;
            // Move to the target screen before sizing so logical dimensions
            // use that screen's DPI rather than the window's initial screen.
            map.set_position(restored_position(
                saved,
                screen,
                [
                    (size[0] + saved.frame[0]) * screen.scale,
                    (size[1] + saved.frame[1]) * screen.scale,
                ],
            ))
            .map_err(|e| e.to_string())?;
            map.set_size(LogicalSize::new(size[0], size[1]))
                .map_err(|e| e.to_string())?;
            let outer = map.outer_size().map_err(|e| e.to_string())?;
            map.set_position(restored_position(
                saved,
                screen,
                [outer.width as f64, outer.height as f64],
            ))
            .map_err(|e| e.to_string())?;
        }
        map.show().map_err(|e| e.to_string())?;
        map.set_focus().map_err(|e| e.to_string())
    })();
    state.0.lock().unwrap().restoring = false;
    if opened.is_ok() {
        remember::<K>(&app);
    } else if let Some(map) = app.get_webview_window(label::<K>()) {
        let _ = map.destroy();
    }
    opened
}

fn close_window<const K: u8>(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Only the main window may dock the map.".into());
    }
    if let Some(map) = app.get_webview_window(label::<K>()) {
        map.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn save(app: &tauri::AppHandle) {
    save_kind::<0>(app);
    save_kind::<1>(app);
}
pub fn window_event(window: &tauri::Window, event: &tauri::WindowEvent) {
    window_event_kind::<0>(window, event);
    window_event_kind::<1>(window, event);
}
#[tauri::command]
pub fn open_map_window(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
    open_window::<0>(app, window)
}
#[tauri::command]
pub fn close_map_window(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
    close_window::<0>(app, window)
}
#[tauri::command]
pub fn open_batch_window(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    open_window::<1>(app, window)
}
#[tauri::command]
pub fn close_batch_window(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    close_window::<1>(app, window)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn screen(name: &str, x: f64, y: f64, scale: f64) -> Screen {
        Screen {
            name: Some(name.into()),
            origin: [x, y],
            size: [1920. * scale, 1080. * scale],
            work_origin: [x, y + 24. * scale],
            work_size: [1920. * scale, 1030. * scale],
            scale,
        }
    }
    fn placement(screen: Screen) -> Placement {
        Placement {
            screen,
            size: [800., 700.],
            frame: [0., 28.],
            offset: [100., 50.],
        }
    }
    #[test]
    fn same_monitor_restores_exact_bounds_with_negative_origin() {
        let monitor = screen("external", -1920., 0., 1.);
        let saved = placement(monitor.clone());
        assert_eq!(
            target_screen(&saved, &[screen("laptop", 0., 0., 2.), monitor.clone()], 0),
            Some(1)
        );
        assert_eq!(restored_size(&saved, &monitor), [800., 700.]);
        assert_eq!(
            restored_position(&saved, &monitor, [800., 728.]),
            PhysicalPosition::new(-1820, 74)
        );
    }
    #[test]
    fn monitor_rearrangement_and_dpi_change_preserve_logical_size_and_offset() {
        let saved = placement(screen("external", -1920., 0., 1.));
        let moved = screen("external", 3000., -1600., 2.);
        assert_eq!(
            target_screen(&saved, &[moved.clone(), screen("laptop", 0., 0., 2.)], 1),
            Some(0)
        );
        assert_eq!(restored_size(&saved, &moved), [800., 700.]);
        assert_eq!(
            restored_position(&saved, &moved, [1600., 1456.]),
            PhysicalPosition::new(3200, -1452)
        );
    }
    #[test]
    fn disconnected_monitor_and_smaller_work_area_keep_entire_window_visible() {
        let mut saved = placement(screen("removed", -1920., 0., 1.));
        saved.offset = [5000., -5000.];
        saved.size = [3000., 2000.];
        let mut laptop = screen("laptop", 0., 0., 2.);
        laptop.work_size = [1800., 1200.];
        assert_eq!(target_screen(&saved, &[laptop.clone()], 0), Some(0));
        assert_eq!(restored_size(&saved, &laptop), [900., 572.]);
        assert_eq!(
            restored_position(&saved, &laptop, [1800., 1200.]),
            PhysicalPosition::new(0, 48)
        );
        assert_eq!(target_screen(&saved, &[], 0), None);
    }
    #[test]
    fn duplicate_names_choose_nearest_previous_monitor() {
        let saved = placement(screen("display", -1920., 0., 1.));
        assert_eq!(
            target_screen(
                &saved,
                &[
                    screen("display", 1920., 0., 1.),
                    screen("display", -1920., 0., 1.)
                ],
                0
            ),
            Some(1)
        );
    }
    #[test]
    fn persisted_settings_roundtrip_and_invalid_files_are_ignored() {
        let saved = placement(screen("external", -1920., -500., 2.));
        assert_eq!(Placement::parse(&saved.json()), Some(saved.clone()));
        for (key, invalid) in [
            ("size", json!([-1, 0])),
            ("offset", json!([null, 0])),
            ("frame", json!([0])),
            ("version", json!(2)),
        ] {
            let mut value = saved.json();
            value[key] = invalid;
            assert_eq!(Placement::parse(&value), None);
        }
        let mut value = saved.json();
        value["screen"]["scale"] = json!(0);
        assert_eq!(Placement::parse(&value), None);
        assert_eq!(Placement::parse(&json!({})), None);
    }
}
