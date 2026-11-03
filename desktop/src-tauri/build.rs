fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "desktop_invoke",
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
