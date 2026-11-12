//! Signed application updates for installed release builds.
//!
//! The webview only sees four bounded commands. The update plugin's own
//! JavaScript commands stay without a capability, so page content can neither
//! choose an endpoint nor install a package by itself. Nothing is replaced
//! before the user confirms the restart.

use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
use std::time::{Duration, Instant};
use tauri::{Emitter, State};
use tauri_plugin_updater::{Update, UpdaterExt};

const RELEASE_PAGE: &str = "https://github.com/Dioptas/Dioptas/releases/latest";
const PROGRESS_EVENT: &str = "dioptas-update-progress";

pub struct UpdateState {
    enabled: bool,
    available: Mutex<Option<Update>>,
    /// The verified package of one announced version, kept until restart.
    package: Mutex<Option<(String, Vec<u8>)>>,
    downloading: AtomicBool,
}

impl UpdateState {
    pub fn new(enabled: bool) -> Self {
        Self {
            enabled,
            available: Mutex::new(None),
            package: Mutex::new(None),
            downloading: AtomicBool::new(false),
        }
    }
}

/// Only a release configuration with a verification key can update itself.
/// Previews and local builds have no `plugins.updater` section.
pub fn configured(config: &tauri::Config) -> bool {
    public_key_present(config.plugins.0.get("updater"))
}

fn public_key_present(updater: Option<&Value>) -> bool {
    updater
        .and_then(|updater| updater["pubkey"].as_str())
        .is_some_and(|key| !key.trim().is_empty())
}

pub fn enabled(config: &tauri::Config, smoke: bool) -> bool {
    configured(config) && !smoke && !tauri::is_dev()
}

fn downloaded(state: &UpdateState, version: &str) -> bool {
    state
        .package
        .lock()
        .unwrap()
        .as_ref()
        .is_some_and(|(stored, _)| stored == version)
}

#[tauri::command]
pub async fn update_check(
    app: tauri::AppHandle,
    state: State<'_, UpdateState>,
) -> Result<Value, String> {
    let current = app.package_info().version.to_string();
    if !state.enabled {
        return Ok(json!({"supported": false, "currentVersion": current, "update": null}));
    }
    let update = app
        .updater_builder()
        .timeout(Duration::from_secs(20))
        .build()
        .map_err(|error| format!("Updates are unavailable: {error}"))?
        .check()
        .await
        .map_err(|error| format!("Could not check for updates: {error}"))?;
    let summary = update.as_ref().map(|update| {
        json!({
            "version": update.version,
            "notes": update.body,
            "published": update.date.map(|date| date.unix_timestamp()),
            "downloaded": downloaded(&state, &update.version),
        })
    });
    if let Some(update) = &update {
        // A package of an older announcement must not be installed as this one.
        let mut package = state.package.lock().unwrap();
        if package.as_ref().is_some_and(|(version, _)| version != &update.version) {
            *package = None;
        }
    }
    *state.available.lock().unwrap() = update;
    Ok(json!({"supported": true, "currentVersion": current, "update": summary}))
}

struct Downloading<'a>(&'a AtomicBool);
impl Drop for Downloading<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::SeqCst);
    }
}

/// Downloads and verifies the announced package. The installed application is
/// not touched; `update_apply` replaces it when the user restarts.
#[tauri::command]
pub async fn update_download(
    app: tauri::AppHandle,
    state: State<'_, UpdateState>,
) -> Result<Value, String> {
    let update = state
        .available
        .lock()
        .unwrap()
        .clone()
        .ok_or("Check for updates before downloading.")?;
    if downloaded(&state, &update.version) {
        return Ok(json!({"version": update.version}));
    }
    if state.downloading.swap(true, Ordering::SeqCst) {
        return Err("The update is already downloading.".into());
    }
    let _guard = Downloading(&state.downloading);
    let mut received = 0u64;
    let mut reported = Instant::now() - Duration::from_secs(1);
    let progress = app.clone();
    let bytes = update
        .download(
            move |chunk, total| {
                received += chunk as u64;
                // The interface repaints at about 10 Hz; chunks arrive far faster.
                if reported.elapsed() >= Duration::from_millis(100) {
                    reported = Instant::now();
                    let _ = progress.emit_to(
                        "main",
                        PROGRESS_EVENT,
                        json!({"received": received, "total": total}),
                    );
                }
            },
            || {},
        )
        .await
        .map_err(|error| format!("Could not download the update: {error}"))?;
    *state.package.lock().unwrap() = Some((update.version.clone(), bytes));
    Ok(json!({"version": update.version}))
}

/// Installs the downloaded package and restarts. Called only from the user's
/// explicit restart action.
#[tauri::command]
pub async fn update_apply(
    app: tauri::AppHandle,
    state: State<'_, UpdateState>,
) -> Result<(), String> {
    let update = state
        .available
        .lock()
        .unwrap()
        .clone()
        .ok_or("Check for updates before installing.")?;
    let bytes = {
        let mut package = state.package.lock().unwrap();
        match package.take() {
            Some((version, bytes)) if version == update.version => bytes,
            other => {
                *package = other;
                return Err("Download the update before installing.".into());
            }
        }
    };
    // The Windows installer replaces files in place and the plugin exits this
    // process as soon as the installer starts, without the normal exit events.
    // Release the processor first so its executable is not locked.
    #[cfg(windows)]
    crate::release_host(&app);
    let version = update.version.clone();
    let installed = tauri::async_runtime::spawn_blocking(move || {
        let result = update.install(&bytes);
        (result, bytes)
    })
    .await
    .map_err(|error| error.to_string())?;
    if let (Err(error), bytes) = installed {
        // Keep the verified package so the user can retry without downloading.
        *state.package.lock().unwrap() = Some((version, bytes));
        let restart = if cfg!(windows) {
            " Restart Dioptas before continuing to work."
        } else {
            ""
        };
        return Err(format!("Could not install the update: {error}.{restart}"));
    }
    // macOS and Linux: the new version is in place; the normal exit handlers
    // save window placement and stop the processor before relaunching.
    app.request_restart();
    Ok(())
}

/// Manual download remains available when installation in place is impossible,
/// for example from a read-only location.
#[tauri::command]
pub fn open_update_page() -> Result<(), String> {
    crate::peritheos_manual::open_system_browser(RELEASE_PAGE)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_a_configured_verification_key_enables_updates() {
        assert!(!public_key_present(None));
        assert!(!public_key_present(Some(&json!({}))));
        assert!(!public_key_present(Some(&json!({"pubkey": ""}))));
        assert!(!public_key_present(Some(&json!({"pubkey": "  "}))));
        assert!(!public_key_present(Some(&json!({"pubkey": null}))));
        assert!(public_key_present(Some(&json!({"pubkey": "dW50cnVzdGVk"}))));
    }

    #[test]
    fn stored_packages_match_exact_versions() {
        let state = UpdateState::new(true);
        assert!(!downloaded(&state, "0.15.0"));
        *state.package.lock().unwrap() = Some(("0.15.0".into(), vec![1]));
        assert!(downloaded(&state, "0.15.0"));
        assert!(!downloaded(&state, "0.15.1"));
    }

    /// The shape written by `scripts/updater_release.mjs`.
    #[test]
    fn release_manifests_are_understood_by_the_updater() {
        let release: tauri_plugin_updater::RemoteRelease = serde_json::from_value(json!({
            "version": "0.15.0",
            "notes": "Faster maps.\n\nNew masks.",
            "pub_date": "2026-11-12T17:10:47.913Z",
            "platforms": {
                "darwin-aarch64": {"signature": "c2ln", "url": "https://github.com/Dioptas/Dioptas/releases/download/0.15.0/Dioptas-Desktop_0.15.0_macos_arm64.app.tar.gz"},
                "linux-x86_64-appimage": {"signature": "c2ln", "url": "https://github.com/Dioptas/Dioptas/releases/download/0.15.0/Dioptas-Desktop_0.15.0_linux_amd64.AppImage"},
                "linux-x86_64-deb": {"signature": "c2ln", "url": "https://github.com/Dioptas/Dioptas/releases/download/0.15.0/Dioptas-Desktop_0.15.0_linux_amd64.deb"},
                "windows-x86_64": {"signature": "c2ln", "url": "https://github.com/Dioptas/Dioptas/releases/download/0.15.0/Dioptas-Desktop_0.15.0_windows_x64-setup.exe"}
            }
        }))
        .unwrap();
        assert_eq!(release.version.to_string(), "0.15.0");
        assert!(release.pub_date.is_some());
        assert!(release.download_url("linux-x86_64-deb").unwrap().path().ends_with(".deb"));
        assert!(release.download_url("linux-x86_64").is_err());
        // A release candidate is offered the stable release of the same number.
        let candidate: tauri_plugin_updater::RemoteRelease = serde_json::from_value(json!({
            "version": "0.14.0-rc.2", "platforms": {}
        }))
        .unwrap();
        assert!(release.version > candidate.version);
    }

    #[test]
    fn manual_downloads_use_the_project_release_page() {
        assert!(RELEASE_PAGE.starts_with("https://github.com/Dioptas/Dioptas/"));
    }
}
