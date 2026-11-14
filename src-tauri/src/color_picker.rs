//! Keep WebKit's expanded macOS color panel beside the initiating color swatch.
use serde_json::Value;
use tauri::WebviewWindow;

fn coordinates(anchor: &Value) -> Result<[f64; 4], String> {
    let mut rect = [0.0; 4];
    for (index, key) in ["left", "top", "right", "bottom"].iter().enumerate() {
        rect[index] = anchor[key]
            .as_f64()
            .filter(|v| v.is_finite() && v.abs() < 100_000.0)
            .ok_or_else(|| format!("Invalid color picker {key}"))?;
    }
    if rect[2] <= rect[0] || rect[3] <= rect[1] {
        return Err("Invalid color swatch bounds".into());
    }
    Ok(rect)
}

#[tauri::command]
pub fn prepare_color_picker(window: WebviewWindow, anchor: Value) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Only the main window can open a color picker".into());
    }
    let rect = coordinates(&anchor)?;
    #[cfg(target_os = "macos")]
    {
        let native_window = window.clone();
        window
            .run_on_main_thread(move || platform::arm(&native_window, rect))
            .map_err(|e| e.to_string())?;
    }
    #[cfg(not(target_os = "macos"))]
    let _ = rect;
    Ok(())
}

pub fn install() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    platform::install()?;
    Ok(())
}

// Cocoa desktop coordinates are logical points with a bottom-left origin.
fn top_left(anchor: [f64; 4], size: [f64; 2], work: [f64; 4]) -> [f64; 2] {
    let gap = 8.0;
    let x = anchor[0].clamp(work[0] + gap, (work[2] - size[0] - gap).max(work[0] + gap));
    let below = anchor[1] - gap;
    let y = if below - size[1] >= work[1] + gap {
        below
    } else {
        anchor[3] + gap + size[1]
    };
    [
        x,
        y.clamp(
            work[1] + size[1] + gap,
            (work[3] - gap).max(work[1] + size[1] + gap),
        ),
    ]
}

#[cfg(target_os = "macos")]
mod platform {
    use super::top_left;
    use block2::RcBlock;
    use objc2::{rc::Retained, runtime::ProtocolObject, MainThreadMarker};
    use objc2_app_kit::{
        NSColorPanel, NSWindow, NSWindowDidBecomeKeyNotification, NSWindowDidUpdateNotification,
    };
    use objc2_foundation::{
        NSNotification, NSNotificationCenter, NSObjectProtocol, NSOperationQueue, NSPoint, NSRect,
        NSSize,
    };
    use std::{cell::RefCell, ptr::NonNull};
    use tauri::WebviewWindow;

    struct Placement {
        anchor: [f64; 4],
        work: [f64; 4],
        positioned: bool,
    }
    thread_local! {
        static PLACEMENT: RefCell<Option<Placement>> = const { RefCell::new(None) };
        static OBSERVERS: RefCell<Vec<Retained<ProtocolObject<dyn NSObjectProtocol>>>> = const { RefCell::new(Vec::new()) };
    }

    pub fn arm(window: &WebviewWindow, rect: [f64; 4]) {
        let Some(_mtm) = MainThreadMarker::new() else {
            return;
        };
        let Ok(pointer) = window.ns_window() else {
            return;
        };
        // Tauri owns the NSWindow; this reference is used only on its UI thread.
        let window = unsafe { &*pointer.cast::<NSWindow>() };
        let (Some(view), Some(screen)) = (window.contentView(), window.screen()) else {
            return;
        };
        let bounds = view.bounds();
        let y = bounds.origin.y
            + if view.isFlipped() {
                rect[1]
            } else {
                bounds.size.height - rect[3]
            };
        let local = NSRect::new(
            NSPoint::new(bounds.origin.x + rect[0], y),
            NSSize::new(rect[2] - rect[0], rect[3] - rect[1]),
        );
        let anchor = window.convertRectToScreen(view.convertRect_toView(local, None));
        let work = screen.visibleFrame();
        PLACEMENT.with(|state| {
            *state.borrow_mut() = Some(Placement {
                anchor: [
                    anchor.origin.x,
                    anchor.origin.y,
                    anchor.origin.x + anchor.size.width,
                    anchor.origin.y + anchor.size.height,
                ],
                work: [
                    work.origin.x,
                    work.origin.y,
                    work.origin.x + work.size.width,
                    work.origin.y + work.size.height,
                ],
                positioned: false,
            })
        });
        if std::env::var_os("DIOPTAS_DEBUG_COLOR_PICKER").is_some() {
            eprintln!("Color picker anchor: {anchor:?}, work area: {work:?}");
        }
        position_visible_panel();
    }

    fn position_visible_panel() {
        let Some(mtm) = MainThreadMarker::new() else {
            return;
        };
        if !NSColorPanel::sharedColorPanelExists(mtm) {
            return;
        }
        let panel = NSColorPanel::sharedColorPanel(mtm);
        if !panel.isVisible() {
            return;
        }
        PLACEMENT.with(|state| {
            let mut state = state.borrow_mut();
            let Some(placement) = state.as_mut() else {
                return;
            };
            if placement.positioned {
                return;
            }
            let frame = panel.frame();
            let point = top_left(
                placement.anchor,
                [frame.size.width, frame.size.height],
                placement.work,
            );
            placement.positioned = true;
            panel.setFrameTopLeftPoint(NSPoint::new(point[0], point[1]));
            if std::env::var_os("DIOPTAS_DEBUG_COLOR_PICKER").is_some() {
                eprintln!("Color picker positioned: {:?}", panel.frame());
            }
        });
    }

    pub fn install() -> Result<(), String> {
        MainThreadMarker::new().ok_or("Color picker setup requires the UI thread")?;
        let block = RcBlock::new(|_notification: NonNull<NSNotification>| {
            if !PLACEMENT.with(|state| state.borrow().as_ref().is_some_and(|p| !p.positioned)) {
                return;
            }
            // Run after AppKit finishes opening/restoring the native panel.
            let reposition = RcBlock::new(position_visible_panel);
            unsafe {
                NSOperationQueue::mainQueue().addOperationWithBlock(&reposition);
            }
        });
        // The observer and its capture-free blocks live for this application's UI lifetime.
        // A floating NSColorPanel need not become key when WebKit opens it.
        // Window updates also cover that path, without moving an already placed panel.
        for name in unsafe {
            [
                NSWindowDidBecomeKeyNotification,
                NSWindowDidUpdateNotification,
            ]
        } {
            let observer =
                unsafe {
                    NSNotificationCenter::defaultCenter()
                        .addObserverForName_object_queue_usingBlock(Some(name), None, None, &block)
                };
            OBSERVERS.with(|state| state.borrow_mut().push(observer));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn expanded_picker_stays_at_swatch_on_positive_and_negative_screen_origins() {
        assert_eq!(
            top_left(
                [800.0, 700.0, 820.0, 720.0],
                [250.0, 300.0],
                [0.0, 0.0, 1440.0, 900.0]
            ),
            [800.0, 692.0]
        );
        assert_eq!(
            top_left(
                [-100.0, 50.0, -80.0, 70.0],
                [250.0, 300.0],
                [-1440.0, 0.0, 0.0, 900.0]
            ),
            [-258.0, 378.0]
        );
    }
    #[test]
    fn malformed_color_anchors_are_rejected() {
        assert!(
            coordinates(&serde_json::json!({"left": 0, "top": 0, "right": 20, "bottom": 20}))
                .is_ok()
        );
        assert!(
            coordinates(&serde_json::json!({"left": 20, "top": 0, "right": 0, "bottom": 20}))
                .is_err()
        );
        assert!(coordinates(&serde_json::json!({})).is_err());
    }
}
