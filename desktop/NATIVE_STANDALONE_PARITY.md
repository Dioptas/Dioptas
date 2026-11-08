# Standalone Rust application — 2026-11-08

## Artifact and startup

`npm run tauri:bundle` creates a macOS `.app` with embedded frontend assets, the
Rust processor and `Contents/Resources/dioptas`. The local bundle is ad-hoc
signed; the helper clears notarization/certificate inputs and does not publish
anything. Move the complete `.app` together. No Python, source checkout,
Node/npm, Rust compiler, Vite server or Homebrew installation is needed at runtime.

The host obtains its resource directory from Tauri's installed-application
resolver. Rust receives that path through `--resource-dir`, and inherits the
launch working directory. Release startup searches beside the host for the
processor and never falls back to a build-machine checkout. Missing resource
manifests/processors fail explicitly. The old `--source-root` processor argument
remains available only for explicit test/development clients. Python compatibility
selection still requires its own separately supplied environment; Python is not
part of this bundle.

Automatic pattern export cannot write inside the packaged resource tree. Select
an output folder outside the application when using a bundled example; ordinary
measurement folders keep their existing export behavior. Resource/signature
integrity is checked again after the native workflow.

## Included resources and native code

- Raw CeO₂ Pilatus TIFF, its separate reference PONI and a molybdenum phase.
  Example starts uncalibrated, preserving the existing workflow.
- Offline HTML guide, calibrants, scientific/reference metadata and provenance,
  interface notices, data qualifications and detector/source notices. Material
  core metadata is included; optional numerical dataset packages are excluded.
- Embedded calibrants, detector catalogue, material metadata, symmetry/scattering
  data, plugin schemas and defaults remain compiled into the processor/libraries.
  Fonts use the operating system; there is no font or asset download.
- `RESOURCE_MANIFEST.json` records payload sizes and SHA-256 hashes.
  `THIRD_PARTY_NOTICES.json` indexes target-resolved Cargo application/build
  dependencies and production JavaScript dependencies, their license texts,
  source archives and upstream notice URLs. Missing texts fail the build.
  Nineteen crates omit their full license from the published archive; checked-in
  overrides retain the exact upstream commit, original text and hashes. MPL-2.0
  uses the canonical Mozilla text and preserves the crate source location.
- The qualified arm64 processor dynamically links only Apple's `libSystem` and
  `libiconv`. HDF5 and its enabled native codecs are linked into the executable.
  The host links Apple system frameworks. No Homebrew dylib or HDF5 plugin
  installation is used. The artifact inspection rejects other native dependencies.

## Checks performed

The actual release `.app`, not just the build configuration, is inspected:

1. Verify every resource hash, both Mach-O architectures/deployment records,
   absence of Python source/runtime files, internal-only symlinks, system-only
   dynamic dependencies, and `codesign --verify --deep --strict` integrity.
2. Copy the complete app outside the repository into a directory with spaces;
   give this test copy its own bundle identifier and temporary home/settings.
3. Prove a macOS sandbox profile denies the real checkout, then run the copied
   app with checkout/cache/Homebrew access denied, Python execution denied,
   PATH unavailable and external HDF5 plugin loading disabled.
4. Exercise the bundled WebKit UI and actual Tauri binary IPC: full-resolution
   raw example, embedded calibrants/detectors/materials, PONI load, 128-point
   integration and 128×36 cake, phase load, configuration duplication, project
   save/reopen and pattern export. Closing the test window reaps its processor.
5. Run independent calibration and Bitshuffle-LZ4/gzip HDF5 integration reference
   comparisons against the processor inside the release app. Python supplies
   test oracles only; the Rust child has Python/PATH unavailable.

The first relocated-window trial failed because the test harness used macOS's
symlinked `/var` temporary path. Tauri deliberately rejects symlinked executable
paths. The harness now canonicalizes its temporary location; the subsequent
complete sandboxed check passes without weakening Tauri's path policy.

Native regression tests cover loading the packaged example from a resource-only
directory, integration and project restoration after those resources are removed.
Host tests cover incomplete-resource failure. Checkpoint: 47 backend tests and
20 host tests pass, together with strict Clippy and the frontend build.

## Reproduce

From `desktop/`:

```sh
npm ci
npm run tauri:bundle
npm run test:standalone-artifact
# Deliberately opens one isolated test window; no existing previews are changed.
npm run test:standalone-native
```

The application is at
`src-tauri/target/release/bundle/macos/Dioptas Desktop.app`.
Receipts/logs are in ignored `artifacts/standalone/`. The inspection/smoke scripts
also accept an explicit `.app` path. For independent Python reference scripts,
set `DIOPTAS_NATIVE_PROCESSOR` to the bundled executable and
`DIOPTAS_RESOURCE_DIR` to `Contents/Resources/dioptas`.

## Qualification boundary

This is a local macOS arm64 migration artifact, not a published/notarized release.
Both binaries declare macOS 14.0 and have no newer deployment record; runtime
execution was checked on this machine, not on every macOS 14+ system. Windows,
Linux and universal macOS artifacts are not qualified here. They retain the
existing scientific/file support limits in the other native ledgers.

The shared Dioptrin pin is still unpublished; producing a clean source build on
another machine requires making that revision available. This does not affect
running the complete built application. Do not confuse runtime independence
with independent reproduction of the build or universal scientific parity.
