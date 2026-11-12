# Dioptas

Dioptas is a desktop application for calibration, masking, integration and
exploration of powder X-ray diffraction images, with phase references, pattern
overlays, Batch processing and linked scan maps.

Development on `develop` uses **Rust, React and Tauri**. Scientific processing
runs in Rust/Dioptrin over a Tauri-owned stdio connection; the default desktop
runtime needs no Python installation.

## Installation

**Native installers are the recommended installation route for the Rust
desktop.** Choose the macOS DMG for Apple Silicon or Intel, the Windows x64
setup executable, or a Linux x64 Debian package or AppImage. See the
[installation guide](docs/source/installation.rst) for requirements and steps.

The first Rust desktop prerelease is
[Dioptas 0.14.0-rc.1](https://github.com/Dioptas/Dioptas/releases/tag/0.14.0-rc.1),
with macOS, Windows and Linux installers for testing. Windows is currently
unsigned. The latest stable 0.13.x releases remain the legacy Qt edition.
See the [candidate release notes](docs/release/RELEASE_0.14.0-rc.1.md) and
[native installer guide](docs/release/NATIVE_RELEASE.md) for tested scope and limits.

**`pip install dioptas` installs the legacy Qt/Python edition.** It does not
install the Rust desktop. Existing Python package versions remain available for
legacy workflows and reproducibility; pip distribution of the Rust desktop is
deferred.

## Run the development application

Install Node/npm, Rust, a C/C++ compiler, CMake, Git and the platform prerequisites
for Tauri, then run:

```sh
git clone --branch develop https://github.com/Dioptas/Dioptas.git
cd Dioptas
npm ci
npm run tauri:dev
```

See the [development guide](DEVELOPMENT.md) for example data,
packaging, headless checks and workflow details, and the
[native qualification inventory](docs/parity/NATIVE_FUNCTIONAL_COVERAGE.md) for
coverage and remaining limitations. Branch promotion does not constitute a new
binary release or a claim of complete Qt parity.

## Branches and released Qt versions

- **`develop`**: active Rust/React/Tauri development.
- **[`legacy/qt`](https://github.com/Dioptas/Dioptas/tree/legacy/qt)**: the preserved
  Qt/Python development line, starting at the former `develop` tip
  `253d0fda505d4f9b159644050efe2f574ce8a3d9` (Qt 0.13.0).
- **`main` and stable Qt release tags**: the existing Qt release history.
- **`codex/rust-desktop`**: retained as a compatibility branch for existing
  desktop feature worktrees; new desktop work should target `develop`.

The stable 0.13.x [downloads](https://github.com/Dioptas/Dioptas/releases),
[PyPI package](https://pypi.org/project/dioptas/) and
[Read the Docs manual](https://dioptas.readthedocs.io/) describe released Qt
versions. For Qt installation, development and maintenance, use the
[legacy Qt guide](https://github.com/Dioptas/Dioptas/blob/legacy/qt/README.md):

```sh
git clone --branch legacy/qt https://github.com/Dioptas/Dioptas.git Dioptas-qt
```

The Qt/Python application, packaging and Python test suite live on `legacy/qt`.
`develop` retains frozen independent reference data, exercised by Rust and
headless UI tests. See [reference data and cleanup](docs/architecture/REFERENCE_DATA.md).
New scientific desktop commands belong in `backend`.

The Rust desktop workflow owns native processor, Tauri host, headless UI and
independent reference checks. Qt CI and branch packages target `legacy/qt` and
`main`. The inherited Qt release workflow rejects tags outside the legacy Qt
line; native installer workflows build and test candidates without publishing.

## Maintainer

Clemens Prescher (clemens.prescher@gmail.com)
