# Dioptas 0.14.0-rc.1 — Rust desktop

This is the first release candidate of the Rust-based Dioptas desktop, following
the Qt 0.13.0 release. It is intended for testing with your own diffraction images
and projects before the stable 0.14.0 release.

Scientific processing runs locally in Rust/Dioptrin. Each installer includes the
processing engine, examples, scientific resources and an offline guide. No
separate Python, Node or Rust installation is needed.

The desktop includes Calibration, Mask, Integration and Map modes, a linked Batch
window, detector corrections, combined patterns/cakes, phase references, and
native project persistence. The bundled Peritheos catalog contains EOS definitions
and provenance without experimental dataset files or observation/audit tables.

## Downloads

| System | Installer | Requirements |
| --- | --- | --- |
| macOS, Apple Silicon | `Dioptas-Desktop_0.14.0-rc.1_macos_arm64.dmg` | macOS 14 or newer |
| macOS, Intel | `Dioptas-Desktop_0.14.0-rc.1_macos_x64.dmg` | macOS 14 or newer |
| Windows, x64 | `Dioptas-Desktop_0.14.0-rc.1_windows_x64-setup.exe` | Includes offline WebView2 installer and Visual C++ runtime libraries |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.1_linux_amd64.deb` | Tested on Ubuntu 22.04 and 24.04 |
| Linux, x64 | `Dioptas-Desktop_0.14.0-rc.1_linux_amd64.AppImage` | Ubuntu 24.04 or compatible glibc 2.39+, FUSE 2 |

The macOS installers are Developer ID signed and notarized. The Windows installer
is **unsigned** and may show publisher or SmartScreen warnings. Linux downloads
are unsigned. `SHA256SUMS` accompanies the downloads.

On macOS, drag the app from the DMG into Applications. On Windows, run the setup
executable and launch Dioptas Desktop from the Start menu. On Ubuntu, install the
Debian package with `sudo apt install ./DOWNLOADED_FILE.deb`. For AppImage, make
the file executable and launch it; `--appimage-extract-and-run` is available when
FUSE cannot be used.

## Testing this candidate

Keep original projects and save test sessions under new names. The Rust desktop
reads current format-2 `.dio` projects; older formats need a compatible legacy
application and explicit data export. Opening a native project in an older Qt
writer can discard native metadata. Qt and the Rust desktop keep separate settings.

Please test installation and launch, your detector formats, PONI loading and
calibration, masks, integration/cakes, Batch/Map, project save/reopen, and exports.
When reporting an issue, include the operating system, this version, the steps to
reproduce it, and a small example file where possible.

## Tested scope and remaining limits

The automated qualification exercises installed applications with the source
checkout unavailable, packaged Rust processing, native IPC, and project/export
round trips. Windows and Debian packages also undergo upgrade/uninstall tests.
The test-only rc.2 upgrade fixture is not a public release.

macOS qualification uses native Apple Silicon and Intel macOS 15 runners; macOS
14 is the declared minimum. Windows qualification uses an x64 Windows Server
2022 runner; testing on ordinary Windows 10/11 machines is a purpose of this
candidate. A fully offline Windows installation without a preexisting WebView2
runtime has not been separately qualified.

Linux qualification uses Ubuntu with a virtual X11 display and software
rendering. Physical GPUs, Wayland and other distributions need further testing.
ARM64 Windows/Linux and universal macOS installers are not provided.

This candidate does not claim complete Qt feature or detector equivalence.
`pip install dioptas` continues to install the legacy Qt edition. Automatic updates
are not included; install a newer candidate manually.
