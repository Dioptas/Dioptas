# Dioptas 0.14.0-rc.2 — Rust desktop

The second release candidate of the Rust desktop, published on November 15,
2026. It adds session recovery and in-app updates, keeps the calibrant and image
orientation in PONI files, lists every supported detector format in image
dialogs, and fixes custom actions on Windows.

<!-- These notes were added after the release, which was published with
GitHub's generated notes because this file was missing. They summarize the rc.2
section of the changelog. -->

## What's new since rc.1

- **Restore the previous session** after an unexpected exit, including Undo and
  Redo history.
- **In-app updates** for installed releases, configurable in **Settings →
  General → Updates**. They follow GitHub's latest stable release.
- **PONI files** record the calibrant and the image orientation; plain-pixel
  calibrations are saved so that pyFAI gives the same 2θ on the raw image (#276,
  #277, #278).
- **Image dialogs** list every supported detector format, including Esperanto and
  gzip/bzip2-compressed files (#282).
- The application is named Dioptas, and window titles show its version. The Map
  detector image has its own view and zoom.
- A new [user manual](https://dioptas.github.io/Dioptas/manual/) with screenshots
  of the current application.
- **Fixes:** no image flicker when loading images or switching modes; the
  duplicate detector orientation select is removed; custom actions work on
  Windows.

The [changelog](../../changelog.md) lists every change.

## Downloads

| System | Installer | Requirements |
| --- | --- | --- |
| macOS, Apple Silicon | `Dioptas-Desktop_0.14.0-rc.2_macos_arm64.dmg` | macOS 14 or newer |
| macOS, Intel | `Dioptas-Desktop_0.14.0-rc.2_macos_x64.dmg` | macOS 14 or newer |
| Windows, x64 | `Dioptas-Desktop_0.14.0-rc.2_windows_x64-setup.exe` | Includes offline WebView2 installer and Visual C++ runtime libraries |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.2_linux_amd64.deb` | Tested on Ubuntu 22.04 and 24.04 |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.2_linux_amd64.AppImage` | Ubuntu 24.04 or compatible glibc 2.39+, FUSE 2 |

Downloads are on the
[0.14.0-rc.2 release page](https://github.com/Dioptas/Dioptas/releases/tag/0.14.0-rc.2).
The macOS installers are Developer ID signed and notarized; the Windows installer
and Linux downloads are unsigned. `SHA256SUMS` accompanies the downloads; the
`.app.tar.gz` files and `latest.json` are for in-app updates.

rc.1 installations need one manual installation of rc.2 or later; rc.1 cannot
update itself.
