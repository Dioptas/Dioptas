fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "desktop_invoke",
            "open_phase_editor",
            "open_peritheos_manual",
            "open_map_window",
            "close_map_window",
            "open_batch_window",
            "close_batch_window",
            "open_detector_window",
            "close_detector_window",
            "publish_detector_snapshot",
            "detector_snapshot",
            "prepare_color_picker",
            "native_smoke_report",
            "show_calibration_tooltip",
            "hide_calibration_tooltip",
            "calibration_tooltip_ready",
            "present_calibration_tooltip",
        ]),
    ))
    .expect("Tauri desktop configuration");
}
