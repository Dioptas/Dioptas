# Windows installer candidates

The Windows pipeline builds an x64 NSIS setup executable using the shared
`tauri.release.conf.json` identity/version/icons plus
`tauri.windows-release.conf.json`. It produces test artifacts only. No release,
tag, package-registry upload or updater publication is performed.

## Candidate configuration

- Per-user installation and Start menu shortcut; no application-installation
  administrator requirement is introduced.
- Embedded Microsoft offline WebView2 installer. The test extracts the actual
  NSIS payload, checks that it contains the full runtime installer rather than
  the small network bootstrapper, and verifies its Microsoft signature.
- App-local Visual C++ runtime DLLs. PE architecture and transitive import
  inspection reject missing third-party dependencies and reliance on a
  machine-installed Visual C++ runtime.
- Rust processor, scientific resources, examples, offline guide and notices.
  Python, Node and Rust tooling are not application runtime dependencies.
- Shared application identifier `org.dioptas.desktop`, separate from the
  preview and legacy Qt identities.

The application version is still the `0.1.0` packaging test version. The
`0.1.1` installer is a disposable upgrade fixture built from the same source;
neither version represents an announced public release.

## Build and test

On an x64 Windows MSVC build machine, from `desktop/`:

```powershell
npm ci
npm run test:windows-release-config
npm run release:windows -- --unsigned --test-upgrade
./scripts/verify_windows_installer.ps1
```

The verification script needs PowerShell 7, `dumpbin` from the MSVC developer
environment, `7z`, and `RUNNER_TEMP` pointing to an isolated test directory. It
refuses to replace an existing registered Dioptas Desktop installation. Use the
ephemeral Actions runner for these lifecycle checks, rather than a personal
Windows installation.

The manual `.github/workflows/native_windows_artifacts.yml` workflow provides
that environment. Its token has read-only repository access; outputs are retained
as Actions artifacts for 14 days. Dispatch the registered workflow with:

```sh
gh workflow run native_windows_artifacts.yml --ref BRANCH
```

Both processor and host build with checked-in Cargo lockfiles. Exact generated
contracts/equations retain LF line endings on Windows. WebView2 crates that omit
their MIT license texts use the original repository-level licenses at their
published `.cargo_vcs_info.json` revisions, with checked hashes and provenance.

## Installed-application qualification

The test silently installs the real setup executable into a path containing
spaces and a non-ASCII character, and verifies registry/shortcut/version data.
It then temporarily makes the checkout unavailable at its build-time path,
runs the installed processor with no developer PATH, and exercises corrections,
material lookup, combined patterns/cakes, std propagation, project round trips
and export.

One isolated native WebView2 instance tests the actual installed Tauri host,
binary IPC, full-resolution example, calibration loading, integration, phases,
project persistence, protection of bundled resources and processor cleanup.
This Windows-specific integration check cannot be replaced by headless
Chromium alone. It runs only on the isolated Windows runner; no local preview
or system mouse is used.

The second installer upgrades the first installation. Tests check both the
registry version and executable version, preserve a user-data marker, reject a
silent downgrade, and uninstall the app, registration and shortcuts while
preserving user settings. The checkout and temporary test paths are restored
on failure. Native Windows backend tests run in the shipping release profile
before building the installers, so processor failures stop packaging early.

Outputs are in `artifacts/native-windows/<version>-x64-<run>/`: setup executables,
`SHA256SUMS`, `build.json` and `verification.json`. The report identifies the
source revision and signing state explicitly.

## Pre-policy candidate, November 12, 2026 (superseded)

The [Windows qualification run](https://github.com/Dioptas/Dioptas/actions/runs/43166683224)
passed at clean source `6e2f39a4ad52999c906f4c05a3a739a5ea7ae862`.
The [full Rust desktop CI run](https://github.com/Dioptas/Dioptas/actions/runs/43166681837)
also passed at that source: Linux/macOS processors, independent numerical
references, Linux Tauri/GLib checks and headless desktop/host workflows.
The release-profile processor suite passed **282 tests**, with the two existing
external full-resolution Eiger fixture tests ignored. All 15 release-policy,
Windows dependency-policy and license tests also passed.

Both installed versions passed the processor and real native WebView2 checks
with the checkout hidden, the developer PATH removed, and an installation path
containing spaces and `ü`. The UI used the full 981 × 1043 example and the native
Rust/Dioptrin processor. Upgrade, downgrade protection, uninstall, settings
preservation and processor cleanup passed. Installed-payload inspection verified
739 resources, notices for 353 Cargo and five JavaScript packages, x64 binaries
and app-local Visual C++ dependencies. The embedded offline WebView2 installer
was 214,990,032 bytes with a valid Microsoft signature.

| Candidate | Purpose | SHA-256 |
| --- | --- | --- |
| `Dioptas Desktop_0.1.0_x64-setup.exe` | Unsigned test candidate | `79ad879246f32539783aa2fd239fad562e22fb32445b7b95bb3ff8c9cb4ff3f6` |
| `Dioptas Desktop_0.1.1_x64-setup.exe` | Disposable upgrade fixture | `d657756ab0437380c2690e3cc33a0ec0a55faf6baeca7e50e5be6ae166565f11` |

Local copies and the original `build.json`, `verification.json` and `SHA256SUMS`
are under `artifacts/native-windows/verified-2026-11-12/`. The downloaded Actions
archive also matched its GitHub SHA-256 digest before extraction.

Windows qualification found and corrected open HDF5 handles blocking atomic
project/embedded-Batch saves. It also exposed the published HDF5 bindings'
32-bit external-offset slot against HDF5 2.x's 64-bit Windows `HDoff_t`. The
[pinned local compatibility patch](vendor/HDF5_WINDOWS_ABI.md) retains complete
crate inventories, original license texts and checked provenance, and adds an
offset-above-4-GiB regression. Windows source snapshots now include the volume
and file identity, so replacing a source with matching size and timestamp is
detected. Scientific navigation/offline tests retain their assertions while
closing original acquisition sessions before removing source files on Windows.

## Verified EOS-only rebuild, November 12, 2026

[Qualification run 43207183077](https://github.com/Dioptas/Dioptas/actions/runs/43207183077)
passed at clean source `514050e86c325992bcbea8ea4d61c2d3b95e40f3` on the native
Windows Server 2022 x64 runner. All 330 release-profile Rust tests passed, with
the two existing external Eiger fixture tests ignored. All 19 release/dependency/license
and EOS-only policy tests passed before packaging.

Both installed versions passed real native WebView2 and Rust/Dioptrin checks
with the build checkout unavailable, no developer PATH, and an installation path
containing spaces and `ü`. Upgrade, downgrade protection, uninstall, settings
preservation and processor cleanup passed. Installed inspection checked 739
resources, 353 Cargo notices, five JavaScript notices, x64 binaries, app-local
Visual C++ dependencies and the EOS-only Peritheos catalog. All 685 EOS records
remain with zero experimental rows or dataset-file resources; empty citation and
column descriptors preserve valid refit provenance. The embedded 214,990,032-byte
offline WebView2 installer had a valid Microsoft signature.

| Candidate | Purpose | Bytes | SHA256 |
| --- | --- | ---: | --- |
| `Dioptas Desktop_0.1.0_x64-setup.exe` | Unsigned test candidate | 230,859,103 | `cf2da8e861f6cdfb964690ccd99ebb71e3f5879f8338bc307ff8d2649d58ad69` |
| `Dioptas Desktop_0.1.1_x64-setup.exe` | Disposable upgrade fixture | 230,861,495 | `abe8bb166acd9dd91b8f578e473ce5eef4fcda65e5ecc560ad58fab7da799daa` |

The downloaded Actions ZIP digest and both installer checksums were verified.
Original `build.json`, `verification.json` and `SHA256SUMS`, the installers and a
`qualification.json` receipt are retained in ignored
`artifacts/native-windows/verified-eos-only-2026-11-12-43207183077/`. These
supersede the earlier pre-policy Windows artifacts. Nothing was released or tagged.

The first rebuild gate exposed five portability assumptions in newer tests:
timestamp fixtures opened read-only handles, one HDF5 fixture removed an active
acquisition file, and an error-category assertion assumed Unix mappings. The
fixtures now request write access for timestamp changes, drop the original
acquisition owner before testing offline recovery, and compare actual platform
error categories. Every scientific assertion is retained; the corrections are
confined to test code. All five cases passed in the final Windows run, and all
165 local release library tests also passed (two external fixtures ignored).
The macOS rebuild source is `37f498ae`; the difference to this Windows source is
those test-only corrections, with identical application code and catalog.

## Signing boundary

The repository currently has no Windows signing credentials. CI deliberately
uses `--unsigned`, passes Tauri's `--no-sign`, and checks `NotSigned` on the
installer and installed application executables. These candidates can produce
Windows publisher/SmartScreen warnings and are not signed public releases.

The CLI defaults to requiring a signing configuration when `--unsigned` is
absent. `DIOPTAS_WINDOWS_SIGNER_THUMBPRINT` identifies the expected certificate;
the certificate/private key must already be available to SignTool. An optional
`DIOPTAS_WINDOWS_SIGN_COMMAND` supplies a provider-specific Tauri signing command
containing `%1`. Signed mode configures SHA-256 and timestamping, and lifecycle
verification requires valid timestamped signatures from the expected signer.
Real signed mode remains unqualified until credentials/provider integration are
available; no Windows certificate or signing-service subscription was purchased.

See [Microsoft's signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
and [SignPath Foundation's open-source program](https://signpath.org/) when
choosing a signing provider. Signing establishes publisher identity/integrity;
SmartScreen warnings can still appear while a new release builds reputation.

The bundled offline WebView2 prerequisite is inspected, but the Actions image
may already have WebView2 installed. A fully disconnected first installation
with WebView2 initially absent is a separate qualification case. Windows ARM64,
32-bit Windows, MSIX/MSI and physical Windows 10/11 hardware are outside this
initial x64 Server 2022 runner qualification.
