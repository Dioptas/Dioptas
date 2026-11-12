use tauri::{AppHandle, Manager, WebviewWindowBuilder, Wry};

/// Native test companions must use the same disposable website store as their
/// main window. Regular app windows keep the production storage policy.
pub fn configure<'a>(
    app: &'a AppHandle,
    builder: WebviewWindowBuilder<'a, Wry, AppHandle>,
) -> WebviewWindowBuilder<'a, Wry, AppHandle> {
    if !app.state::<crate::Host>().smoke {
        return builder;
    }
    // Set at runtime rather than in generated WindowConfig: the current Tauri
    // config code generator emits Vec<u8> for the fixed-size store identifier.
    let store = std::env::var("DIOPTAS_TEST_WEBVIEW_STORE")
        .ok()
        .and_then(|value| serde_json::from_str::<[u8; 16]>(&value).ok());
    let mut builder = match store {
        Some(identifier) => builder.data_store_identifier(identifier),
        None => builder.incognito(true),
    };
    if let Some(directory) = app
        .config()
        .app
        .windows
        .iter()
        .find(|window| window.label == "main")
        .and_then(|main| main.data_directory.clone())
    {
        builder = builder.data_directory(directory);
    }
    builder
}
