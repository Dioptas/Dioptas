/// Cancel a real AppKit open/save panel during an explicitly requested native
/// smoke check. The only caller is guarded by Host::smoke.
#[cfg(target_os = "macos")]
pub fn cancel_file_panel() -> Result<(), String> {
    use objc2::MainThreadMarker;
    use objc2_app_kit::{NSApplication, NSSavePanel};
    let main = MainThreadMarker::new().ok_or("Native dialog check must run on the UI thread")?;
    for window in NSApplication::sharedApplication(main).windows() {
        if let Some(panel) = window.downcast_ref::<NSSavePanel>() {
            if panel.isVisible() {
                // A nil sender is Cocoa's normal programmatic Cancel action.
                unsafe { panel.cancel(None) };
                return Ok(());
            }
        }
    }
    Err("No native file panel is visible yet".into())
}

#[cfg(not(target_os = "macos"))]
pub fn cancel_file_panel() -> Result<(), String> {
    Err("Native file-panel automation is currently macOS-only".into())
}
