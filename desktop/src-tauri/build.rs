fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&["desktop_invoke", "native_smoke_report"]),
    ))
    .expect("Tauri desktop configuration");
}
