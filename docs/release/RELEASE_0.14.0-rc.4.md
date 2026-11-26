# Dioptas 0.14.0-rc.4 — Rust desktop

The fourth release candidate of the Rust desktop. It adds GPU-accelerated 1D
and 2D integration via Apple Metal (macOS) and NVIDIA CUDA (Windows and Linux),
and updates the processing engine to Dioptrin 0.16.0 with unified exact
fractional-area 2D cakes and per-pixel corner handling for gapped detectors.

## What's new since rc.3

- **GPU-accelerated integration (Metal and CUDA):** choose compute backend and
  GPU precision (compensated float32, float32, or CUDA float64) in
  **Settings → Integration**. On Windows and Linux, CUDA kernels ship as
  embedded precompiled PTX so Volta+ NVIDIA GPUs need only the display driver,
  with automatic CPU fallback when a GPU is unavailable or not applicable.
- **Dioptrin 0.16.0:** unified exact fractional-area `shared_grid` 2D cake
  integration, plus per-pixel angular corners for gapped/multi-module detectors
  in 2D pixel splitting so quads do not straddle module gaps.
- **Host and session hardening:** optional project checkpoints are restored on
  session errors, phase guide contours use typed payloads, and the Tauri host
  follows Rust 2024 with clippy enforced in CI.

The [changelog](../../changelog.md) lists every change.

## Downloads

| System | Installer | Requirements |
| --- | --- | --- |
| macOS, Apple Silicon | `Dioptas-Desktop_0.14.0-rc.4_macos_arm64.dmg` | macOS 14 or newer |
| macOS, Intel | `Dioptas-Desktop_0.14.0-rc.4_macos_x64.dmg` | macOS 14 or newer |
| Windows, x64 | `Dioptas-Desktop_0.14.0-rc.4_windows_x64-setup.exe` | Includes offline WebView2 installer and Visual C++ runtime libraries |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.4_linux_amd64.deb` | Tested on Ubuntu 22.04 and 24.04 |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.4_linux_amd64.AppImage` | Ubuntu 24.04 or compatible glibc 2.39+, FUSE 2 |

The macOS installers are Developer ID signed and notarized. The Windows installer
is **unsigned** and may show publisher or SmartScreen warnings. Linux downloads
are unsigned. `SHA256SUMS` accompanies the downloads; the `.app.tar.gz` files and
`latest.json` are for in-app updates.

### Updating from rc.1, rc.2 or rc.3

Install rc.4 over the previous candidate; settings are kept. Release candidates
are not offered through the in-app update button: it follows GitHub's latest
stable release, so it will first offer the stable 0.14.0.

## Testing this candidate

Keep original projects and save test sessions under new names. Qt and the Rust
desktop keep separate settings.

In particular, please check:

- **GPU integration** in **Settings → Integration** on Apple Silicon (Metal) and
  NVIDIA GPUs (CUDA on Windows/Linux): 1D patterns, 2D cakes, Batch/Map series,
  precision modes, and fallback to CPU on machines without a supported GPU.
- **2D cake integration** with Dioptrin 0.16.0, especially on gapped/multi-module
  detectors (e.g., Pilatus, Eiger) and across standard and pyFAI-compatible
  splitting modes.
- Saving and reopening projects with GPU backend preferences set.

When reporting an issue, include the operating system, this version, the steps to
reproduce it, and a small example file where possible.

## Tested scope and remaining limits

The automated qualification exercises installed applications with the source
checkout unavailable, packaged Rust processing, native IPC, and project/export
round trips. Windows and Debian packages also undergo upgrade/uninstall tests.
Continuous integration runs the native tests on Windows for every change and
the headless interface checks on Windows for every merge.

macOS qualification uses native Apple Silicon and Intel macOS 15 runners; macOS
14 is the declared minimum. Windows qualification uses an x64 Windows Server
2022 runner, and the processor and interface checks have also been run on
Windows 11. Linux qualification uses Ubuntu with a virtual X11 display and
software rendering; physical GPUs, Wayland and other distributions need further
testing. ARM64 Windows/Linux and universal macOS installers are not provided.

A growing Live HDF5 master is read with the file list it had when a run started;
data files added later are picked up by the next run.

This candidate does not claim complete Qt feature or detector equivalence.
`pip install dioptas` continues to install the legacy Qt edition.
