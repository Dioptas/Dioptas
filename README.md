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

The native installers are currently tested candidates; no public native release
has been published yet. Existing assets on the
[GitHub releases page](https://github.com/Dioptas/Dioptas/releases) are legacy Qt
releases. Candidate access and verification are documented in the
[native installer guide](desktop/NATIVE_RELEASE.md).

**`pip install dioptas` installs the legacy Qt/Python edition.** It does not
install the Rust desktop. Existing Python package versions remain available for
legacy workflows and reproducibility; pip distribution of the Rust desktop is
deferred.

## Run the development application

Install Node/npm, Rust, a C/C++ compiler, CMake, Git and the platform prerequisites
for Tauri, then run:

```sh
git clone --branch develop https://github.com/Dioptas/Dioptas.git
cd Dioptas/desktop
npm ci
npm run tauri:dev
```

See the [desktop development guide](desktop/README.md) for example data,
packaging, headless checks and workflow details, and the
[native qualification inventory](desktop/NATIVE_FUNCTIONAL_COVERAGE.md) for
coverage and remaining limitations. Branch promotion does not constitute a new
binary release or a claim of complete Qt parity.

## Branches and released Qt versions

- **`develop`**: active Rust/React/Tauri development.
- **[`legacy/qt`](https://github.com/Dioptas/Dioptas/tree/legacy/qt)**: the preserved
  Qt/Python development line, starting at the former `develop` tip
  `253d0fda505d4f9b159644050efe2f574ce8a3d9` (Qt 0.13.0).
- **`main` and existing release tags**: the existing stable release history.
- **`codex/rust-desktop`**: retained as a compatibility branch for existing
  desktop feature worktrees; new desktop work should target `develop`.

The existing [downloads](https://github.com/Dioptas/Dioptas/releases),
[PyPI package](https://pypi.org/project/dioptas/) and
[Read the Docs manual](https://dioptas.readthedocs.io/) describe released Qt
versions. For Qt installation, development and maintenance, use the
[legacy Qt guide](https://github.com/Dioptas/Dioptas/blob/legacy/qt/README.md):

```sh
git clone --branch legacy/qt https://github.com/Dioptas/Dioptas.git Dioptas-qt
```

Python sources in this branch remain available for explicit compatibility and
independent numerical references. New scientific desktop commands belong in
`desktop/backend`; they must not silently fall back to Python.

The Rust desktop workflow owns native processor, Tauri host, headless UI and
independent reference checks. Qt CI and branch packages target `legacy/qt` and
`main`. The inherited Qt release workflow rejects tags outside the legacy Qt
line; native installer workflows build and test candidates without publishing.

## Maintainer

Clemens Prescher (clemens.prescher@gmail.com)
