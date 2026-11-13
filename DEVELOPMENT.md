# Dioptas Rust desktop development

The active Dioptas development application uses React/Tauri with native
Rust/Dioptrin processing, providing Calibration, Mask, Integration, Map and Single Crystal XRD modes
plus a linked Batch window. It retains Dioptas workflows and file formats;
qualified behavior and remaining limitations are recorded in the parity guides.

New desktop work targets `develop`; the Qt application and its tests live on
`legacy/qt`. Working rules are in [AGENTS.md](AGENTS.md), and everything beyond
setup lives under [docs/](docs/README.md).

## Run this checkout

Install Node/npm, Rust, a C/C++ compiler, CMake and Git, then:

```sh
npm ci
npm run tauri:dev -- -- -- --example
```

The example opens the **raw** `CeO2_Pilatus1M.tif` fixture, without loading its
reference PONI. The explicit example setup is CeO2, wavelength 0.406626 Å,
172 × 172 µm pixels, and a starting distance of 200 mm. These are starting
inputs, not a previously fitted geometry.

For an empty workspace, use `npm run tauri:dev`. On macOS, after setup, double-click
`launch.command` to reopen the raw-image example in **Live preview**.
The launcher now opens **Tauri**, using WKWebView on macOS. Its first run compiles
the Rust host and requires the Rust toolchain and platform build prerequisites.
The Tauri CLI owns a loopback Vite frontend on port 1420; React/CSS edits appear
in the running native window. If that port is occupied, it fails rather than
opening a different project's server. Closing the window also stops Vite.
Development also tracks React hook signatures in `.ts` modules: changing their
hook layout safely remounts the affected interface, while ordinary edits retain
interface state. Run `npm run test:hook-refresh` for the headless Chromium/WebKit
regression check against a real native session.

This applies to the native **live development preview**. Host Rust changes still
restart the host/window; bundled snapshot apps do not watch source files.
Neither application processing nor its active test suite requires Python.

For phase-editor work in its assigned checkout, use `npm run tauri:phase-dev`.
This opens the raw-image example with live React/CSS updates on its dedicated
port 1426, including the detached phase-editor window. It leaves the primary
preview's port 1420 and existing bundled windows alone. Bundled `.app` previews
contain the UI from their build and do not receive live edits.

## Build and package

A [standalone macOS Rust application](docs/parity/NATIVE_STANDALONE_PARITY.md) is now available.
`npm run tauri:bundle` builds the complete `.app` with processor, resources,
examples, offline guide and dependency notices. Move the entire application;
it runs without Python or a source checkout. Local bundles are ad-hoc signed,
with no publication/notarization step. Qualified macOS, Windows and Linux
installer pipelines are documented below; universal macOS is not provided.
The local native artifact and relocation checks are documented in that ledger.

For signed installer candidates, see [native release packaging](docs/release/NATIVE_RELEASE.md).
`npm run release:macos` uses the shared release configuration and Developer ID
credentials; the artifact-only workflow also notarizes and tests Apple Silicon
and Intel DMGs. It does not publish a release. The application version comes
from `package.json`; the first public candidate is `0.14.0-rc.1`. See the
[release notes](docs/release/RELEASE_0.14.0-rc.1.md) for downloads and testing.

The [native Windows installer pipeline](docs/release/NATIVE_WINDOWS_RELEASE.md) adds an x64
NSIS candidate with offline WebView2, bundled Visual C++ runtime, and automated
install/upgrade/uninstall and native WebView2 checks. Windows candidates are
explicitly unsigned until a Windows signing provider is configured.

The [native Linux pipeline](docs/release/NATIVE_LINUX_RELEASE.md) builds x64 `.deb` and
AppImage candidates using Ubuntu 22.04 and 24.04 build baselines respectively.
The `.deb` is tested on Ubuntu 22.04/24.04; AppImage is tested on Ubuntu 24.04. It checks installed GTK/WebKit operation under a virtual
display, source-free processing and package lifecycle without publishing.

Development supports `DIOPTAS_SOURCE_ROOT` for native source resources and
`DIOPTAS_NATIVE_PROCESSOR` for an explicit Rust executable. Release startup
uses installed resources and a sibling processor, with no checkout fallback.
A missing processor/resource manifest fails explicitly. Python backend requests
are rejected; the former application lives on `legacy/qt`.

To build a local executable with embedded UI (no development server):

```sh
npm run tauri:build -- --debug
target/debug/dioptas-desktop --example
```

## Tests and CI

The Rust desktop gate and the case-by-case inventory of all 82 legacy functional
definitions are documented in [Native functional coverage](docs/parity/NATIVE_FUNCTIONAL_COVERAGE.md).
Run `npm run test:ci-native` for processor and headless UI checks; independent
Independent numerical reference results are frozen data checked by Rust tests.

From the repository root:

```sh
npm test
npm run build
npm run backend:test
npm run test:functional-coverage
npm run test:fixtures
npm run test:native-backend
npm run test:native-calibration
npm run test:native-integration
npm run test:native-project
npm run test:native-map-progress
```

`npm run test:ci-native` runs the Rust and headless UI gates. Host checks use
`node scripts/check_native_desktop.mjs --host` without opening an app window.
On a machine with at least eight cores the UI gate runs several checks at a
time (half the cores); `DIOPTAS_GATE_UI_JOBS=1` runs them one after another, which is easier to read when one fails. Pull requests set
`DIOPTAS_GATE_CORE_TESTS=0` to skip the library tests of the build without
features; local runs and `develop` keep them.
CI tests on Linux runners only. It builds the processor once and spreads the
UI checks over three jobs (`DIOPTAS_GATE_UI_SHARD=2/3` with
`DIOPTAS_GATE_PREBUILT=1`), one check at a time within each.
Native bulk transport/progress tests use the Rust `test_fixtures` example to
create long test series; no Python environment or plugin installation is needed.
`npm run test:map-window` exercises Chromium and WebKit. All routine GUI checks
are headless. Use isolated native windows only for OS-specific behavior.

Independent scientific outputs are frozen under
`backend/tests/fixtures/reference-data/`, with inputs, settings, tolerances,
source hashes and package versions. `backend/tests/integration/frozen_references.rs`
compares the native results with these data. Existing DAC and Batch reference
fixtures and the native scientific/unit/transport suites remain active.
There is no Python test or numerical-reference CI job.

## Processing engine

Scientific commands run only in the native Rust/Dioptrin processor. The pyFAI
geometry labels name a coordinate convention, and do not select Python.
The legacy app and its test suite are preserved on `legacy/qt`. The former
React/Python compatibility adapter and reference generators are available in
Git history at the source revision recorded in [docs/architecture/REFERENCE_DATA.md](docs/architecture/REFERENCE_DATA.md).

How the host, the processor and binary image transfer fit together is described
in [host and transport](docs/architecture/HOST_AND_TRANSPORT.md).

## Shared UI controls

All views use the controls and surfaces in `src/ui`, including table fields,
popup menus and detached windows. The shared stylesheet owns their neutral
palette and interaction states. See [docs/architecture/UI_COMPONENTS.md](docs/architecture/UI_COMPONENTS.md) for
component usage and the checks that prevent new per-view control themes.

## Documentation

- [Documentation index](docs/README.md): every document by title.
- Workflow guides: [feature status](docs/guide/FEATURES.md),
  [calibration](docs/guide/CALIBRATION.md), [integration](docs/guide/INTEGRATION.md),
  [map](docs/guide/MAP.md), [batch](docs/guide/BATCH.md),
  [custom actions](docs/guide/CUSTOM_ACTIONS.md) and
  [layout and plot interaction](docs/guide/LAYOUT_AND_INTERACTION.md).
- Architecture: [command contract](docs/architecture/COMMAND_CONTRACT.md),
  [host and transport](docs/architecture/HOST_AND_TRANSPORT.md),
  [rendering](docs/architecture/RENDERING.md),
  [processing workers](docs/architecture/PROCESSING_WORKERS.md) and
  [reference data](docs/architecture/REFERENCE_DATA.md).
- [docs/parity/](docs/parity) holds the Qt comparisons, [docs/performance/](docs/performance)
  the measurements, [docs/release/](docs/release) the installer guides and
  [docs/history/](docs/history) the dated review records.
