# Linux installer candidates

The Linux workflow builds x64 `.deb` and AppImage candidates using the shared
release identity, version, icons and Rust processor. It retains Actions artifacts
only: no release, tag, package repository or updater publication is performed.
The current `0.1.0` is a packaging test version; `0.1.1` is only a `.deb` upgrade
fixture built from the same sources.

## Building

Use a native x64 Ubuntu 22.04 build machine with the Tauri Linux prerequisites,
Rust, Node, CMake and `patchelf`. The script enforces this build baseline so a
newer host cannot silently raise the glibc requirement. From `desktop/`:

```sh
npm ci
npm run test:linux-release-config
npm run release:linux -- --test-upgrade
```

Both Cargo lockfiles are enforced. The processor and host are ELF64 x86-64
binaries. The `.deb` declares the GTK/WebKitGTK runtime dependencies and glibc
2.35 minimum; Python, Node and Rust are build/test tools, not application runtime
requirements. Examples, scientific data, the offline guide, application icons and
third-party notices are included.

AppImage includes a versioned superset of installed build-image package
copyright texts for redistributed native libraries. `SYSTEM_NOTICES.json`
explicitly distinguishes this notice collection from an actual dependency list.
Cargo/JavaScript notices and the pinned HDF5 ABI patch provenance remain separate.
The portable payload also explicitly includes WebKit's dynamically loaded
`libGLESv2.so.2` client, with package/version/hash/copyright provenance. Host
OpenGL/EGL dispatch and graphics drivers remain system prerequisites; the
AppImage does not replace drivers with copies from the build machine.
Verification records the original GLES library hash separately from the
packaged hash because linuxdeploy can rewrite ELF search paths/layout. It
checks the relocated library's architecture, SONAME and glibc requirement;
the complete AppImage remains covered by its candidate checksum.

The workflow `.github/workflows/native_linux_artifacts.yml` builds on
`ubuntu-22.04`. Its verification matrix uses separate fresh Ubuntu 22.04 and
24.04 runners for each format. AppImage runners never install the `.deb` first.
The workflow token has read-only repository permissions.

The registered workflow is manual-only:

```sh
gh workflow run native_linux_artifacts.yml --ref BRANCH
```

Set its optional `candidate_run_id` input to repeat installation tests against
the unchanged artifacts from a previous Linux build run. This skips rebuilding;
reports retain the original binary source revision and the current verification
script revision separately. Never substitute the verifier revision for the
source recorded in `build.json`.

## Installing candidates

On Debian/Ubuntu, use APT to install the local candidate and resolve its runtime
dependencies:

```sh
sudo apt install './Dioptas Desktop_0.1.0_amd64.deb'
```

Launch **Dioptas Desktop** from the applications menu or `dioptas-desktop` from
a terminal. Remove the package with `sudo apt remove dioptas-desktop`.

For AppImage, make the file executable and launch it:

```sh
chmod +x './Dioptas Desktop_0.1.0_amd64.AppImage'
'./Dioptas Desktop_0.1.0_amd64.AppImage'
```

Use the actual artifact filename from `build.json`; Tauri's architecture suffix
can differ between formats. AppImage normally needs FUSE 2 (`libfuse2` on Ubuntu
22.04, `libfuse2t64` on 24.04). Its built-in `--appimage-extract-and-run` mode
is also tested as a fallback. Removing the AppImage does not delete user settings.
These candidates are unsigned. Public package-repository/signature integration
is a separate step.

## Qualification

Run lifecycle tests only on an explicitly disposable machine. The driver
requires `DIOPTAS_INSTALLER_TEST_ISOLATED=1`, a private D-Bus session and Xvfb.
The Actions workflow supplies those and retains JSON reports plus native logs.

Checks cover:

- Release-profile processor tests and package/configuration/license checks.
- Installed resource hashes, ELF architecture, glibc symbol requirements,
  resolved dynamic libraries, executable permissions and desktop entry validity.
- Source-checkout isolation and denial of Python/Node/Rust tool execution in
  the installed app, while retaining OS utilities needed by AppImage's launcher.
- Packaged processor corrections, material lookup, combined patterns/cakes,
  counting std, project round trips and export.
- The real installed Tauri/GTK/WebKit app under Xvfb: full-resolution example,
  binary IPC, calibration/integration/phases, project persistence, protection of
  packaged resources and processor cleanup.
- `.deb` installation, upgrade, registration, desktop entry removal, purge and
  preservation of a user-settings marker.
- Portable AppImage launch through FUSE and its extract-and-run fallback from a
  path with spaces and `ü`, with no system Dioptas installation present.

The source checkout is restored after the tests, including failures. The
runtime checks open no windows on the user's desktop and use a virtual X11
display with software rendering. They do not establish Wayland, physical GPU,
ARM64, older glibc, RPM, Flatpak or every-distribution compatibility.

Outputs are in `artifacts/native-linux/<version>-x64-<run>/`: candidates,
`SHA256SUMS` and `build.json` with clean/dirty source identity, build OS,
toolchain, hashes and explicit signing/publication state. The four installation
reports identify their runtime OS and tested format. A candidate is qualified
only after the build and all four installation jobs pass.

See the [Tauri AppImage](https://v2.tauri.app/distribute/appimage/) and
[Debian packaging guides](https://v2.tauri.app/distribute/debian/) for the build
baseline, and [AppImage's FUSE guidance](https://docs.appimage.org/user-guide/troubleshooting/fuse.html)
for portable launch prerequisites.
