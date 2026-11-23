# Dioptas 0.14.0-rc.3 — Rust desktop

The third release candidate of the Rust desktop. It addresses rc.2 testing
feedback from Windows: signed Varex TIFF images, custom actions that start
scripts in their own window, and plain Windows paths. Batch and Map are much
faster on Bliss/Eiger HDF5 masters, and background editing on large maps no
longer refits the whole map after every change.

## What's new since rc.2

- **Start custom actions detached:** a per-action option runs the program in its
  own window without capturing output, so Windows `.bat`/`.cmd` scripts and
  console programs work.
- **Varex TIFF images** from `ngMultiXRD` integrate correctly; their signed counts
  were read as unsigned and flattened the pattern.
- **Batch and Map on Bliss/Eiger masters** use the parallel Eiger reader for
  single- and multi-file masters: 500–550 instead of 110–122 images/s on a
  2,500-frame scan (Apple M4 Pro). Eiger files above 8 GiB open directly.
- **Map backgrounds:** the map applies the Integration pattern background, and
  background edits update a large map once, in parallel, instead of after every
  change.
- **Automatic radial binning** is on by default for new sessions.
- **Windows:** paths without the `\\?\` prefix, **Ctrl** in the shortcut list, and
  no more random "HDF5 source changed" errors after choosing companion files.

The [changelog](../../changelog.md) lists every change.

## Downloads

| System | Installer | Requirements |
| --- | --- | --- |
| macOS, Apple Silicon | `Dioptas-Desktop_0.14.0-rc.3_macos_arm64.dmg` | macOS 14 or newer |
| macOS, Intel | `Dioptas-Desktop_0.14.0-rc.3_macos_x64.dmg` | macOS 14 or newer |
| Windows, x64 | `Dioptas-Desktop_0.14.0-rc.3_windows_x64-setup.exe` | Includes offline WebView2 installer and Visual C++ runtime libraries |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.3_linux_amd64.deb` | Tested on Ubuntu 22.04 and 24.04 |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.3_linux_amd64.AppImage` | Ubuntu 24.04 or compatible glibc 2.39+, FUSE 2 |

The macOS installers are Developer ID signed and notarized. The Windows installer
is **unsigned** and may show publisher or SmartScreen warnings. Linux downloads
are unsigned. `SHA256SUMS` accompanies the downloads; the `.app.tar.gz` files and
`latest.json` are for in-app updates.

### Updating from rc.1 or rc.2

Install rc.3 over the previous candidate; settings are kept. Release candidates
are not offered through the in-app update button: it follows GitHub's latest
stable release, so it will first offer the stable 0.14.0.

## Testing this candidate

Keep original projects and save test sessions under new names. Qt and the Rust
desktop keep separate settings.

In particular, please check:

- On Windows: custom actions with **Start detached**, for example a `.bat` script;
  paths in dialogs and messages; and Varex or other 32-bit TIFF images.
- Batch and Map on Bliss/Eiger masters, including scans split over several data
  files, and background editing on large maps.
- Integration of new sessions with automatic radial binning, and projects saved
  with a fixed bin count.

When reporting an issue, include the operating system, this version, the steps to
reproduce it, and a small example file where possible.

## Tested scope and remaining limits

The automated qualification exercises installed applications with the source
checkout unavailable, packaged Rust processing, native IPC, and project/export
round trips. Windows and Debian packages also undergo upgrade/uninstall tests.
Continuous integration now runs the native tests on Windows for every change and
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
