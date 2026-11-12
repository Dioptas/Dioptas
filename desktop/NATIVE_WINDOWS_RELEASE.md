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
