# Native installer candidates

Native installers are the primary distribution route. A pip distribution is
deferred. This pipeline builds candidates only: it has no tag creation, GitHub
Release, PyPI upload, updater publication or release write permission.

## Shared configuration

`package.json` owns the application version; `src-tauri/tauri.conf.json` reads
that version directly. `src-tauri/tauri.release.conf.json` overlays the stable
native identity (`org.dioptas.desktop`), window title, platform icons and bundle
metadata. The preview identity and legacy Qt identity remain separate, including
their settings/WebKit storage. The current release candidate is `0.14.0-rc.1`. The early `0.1.0`
artifacts below were packaging tests and are superseded for public distribution.

The release overlay is shared with the [Windows installer pipeline](NATIVE_WINDOWS_RELEASE.md)
and [Linux installer pipeline](NATIVE_LINUX_RELEASE.md). Each platform has its own dependency and
installed-application tests. Do not infer their qualification from a macOS candidate. Icons are generated
from `src-tauri/icons/icon.svg` with the pinned Tauri CLI; `.icns` and `.ico`
outputs are checked in alongside the original artwork.

## macOS builds

Build each architecture on its own native runner: `macos-15` for Apple Silicon,
`macos-15-intel` for Intel. Both binaries target macOS 14.0 or newer; executing
on a newer runner does not establish compatibility with every macOS 14 system.
Universal binaries are outside this pipeline.

Both processor and host builds enforce their checked-in Cargo lockfiles. The
candidate workflow is manual-only; ordinary pushes do not sign or submit apps.

From `desktop/`, with the certificate/private key already in an unlocked keychain:

```sh
npm ci
npm run test:release-config
DIOPTAS_CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)' \
DIOPTAS_APPLE_TEAM_ID=TEAMID npm run release:macos
```

This builds and signs the app and DMG without submitting to Apple. It checks
Developer ID, team, hardened runtime, secure timestamps, resources, architecture,
minimum OS and system-only dynamic dependencies. It mounts the DMG read-only
without Finder, checks the Applications link, copies the application to a
temporary installation, and exercises its packaged Rust processor with source
and Python execution denied. Checks cover material/cylinder/sphere/capillary
corrections, integration, combined patterns/cakes, project round trips and export.

`--ad-hoc` explicitly produces a local candidate without Developer ID or
notarization; it is never labeled as Developer ID signed. `--native-smoke` opts
into one isolated native WebKit test window, retaining the real release signature
and using disposable storage. Routine checks are headless.

## Signed and notarized CI candidates

`.github/workflows/native_macos_artifacts.yml` uses the existing repository
secrets: `MACOS_CERTIFICATE_P12_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `APPLE_ID`,
`APPLE_TEAM_ID`, and `APPLE_APP_SPECIFIC_PASSWORD`. The existing standard-library
Python credential/notary helper is build tooling only; Python is not shipped or
used for scientific processing.

The job imports credentials into a temporary keychain, then runs:

```sh
npm run release:macos -- --notarize --native-smoke
```

Tauri signs both executables and the app. After the processor check, the app is
submitted to Apple, stapled and assessed by Gatekeeper. Only then is it copied
into the DMG. The DMG is also signed, notarized, stapled and assessed. Its copied
application is checked again, including the unchanged Developer ID signature,
notary tickets, processor workflow and native WebKit/IPC workflow. The credential
keychain is cleaned up even on failure.

Candidate outputs are under `artifacts/native-release/<version>-<target>-<run>/`:

- The DMG and a tar archive preserving the signed app bundle.
- `SHA256SUMS` for both downloadable artifacts.
- `build.json`: source revision, dirty-source status, version, target, signing,
  notarization status and installed-application verification.
- Notarization submissions, IDs and logs under `dist/notarization/`, plus the
  original signed ZIP under `dist/notarization-payloads/` for recovery.

Successful candidates and diagnostics are retained as Actions artifacts for
14 days. No release is published. The registered workflow can be dispatched
for this branch with `gh workflow run native_macos_artifacts.yml --ref BRANCH`.
The Actions UI's Run workflow button requires the workflow on the default branch.

The workflow accepts an architecture and an optional `recovery_run_id`. For a
run whose app was accepted by Apple but whose DMG packaging failed, recovery
restores the original signed app ZIP from that run's diagnostics, retrieves and
validates its existing Apple ticket, and packages it without rebuilding,
re-signing or re-submitting the app. The report keeps the original app revision
and the current packaging revision separately. Recovering a still-pending or
rejected app fails its ticket/Gatekeeper checks. The new DMG is submitted once.

For a DMG that was already signed and uploaded to Apple, use
`resume_dmg_run_id` instead of `recovery_run_id`, selecting only its original
architecture. This restores the exact original DMG and its saved submission ID,
waits on that ID, staples the accepted ticket and repeats copied-installation,
packaged-processor, native WebKit and EOS-only checks. It performs no build,
re-signing or new Apple upload. The app archive is copied from the verified DMG.
Original app and recovery-tool revisions are recorded separately; `source.json`
also preserves the original app revision across later recovery attempts.

```sh
gh workflow run native_macos_artifacts.yml --ref develop \
  -f architecture=intel -f resume_dmg_run_id=ORIGINAL_RUN_ID
```

Disk-image creation uses explicit HFS+ and retries only `Resource busy` errors,
up to five attempts with 2/4/8/16-second backoff. Other errors fail immediately.
Retries remove only this candidate's partial DMG; no system disk-image helpers
or unrelated mounts are terminated.

Apple can take longer than the 90-minute wait. A timeout fails the candidate;
it does not count as acceptance. Before rebuilding or signing again, inspect
the retained submission ID and resume with the original signed bytes, matching
credential keychain/team/identity environment, and the original output directory
as the working directory:

```sh
python3 /path/to/Dioptas/installer/macos/signing.py notarize /path/to/original.app \
  --submission-id ORIGINAL_SUBMISSION_ID
```

For an app submission, the original app can also be restored from the retained
signed ZIP without re-signing it. A resumed DMG submission uses its original
DMG. Do not silently resubmit the same pending candidate. After acceptance,
complete DMG packaging/verification before treating that candidate as ready.

Local DMGs can be rechecked with `npm run test:macos-dmg -- /absolute/path.dmg`.
Set `DIOPTAS_APPLE_TEAM_ID` to require Developer ID signing; add `--notarized`
to require stapled tickets and Gatekeeper acceptance, and `--native-smoke` only
when testing the native WebKit boundary.

## Pre-policy verification on November 11, 2026 (superseded)

- Apple Silicon: the [clean native macOS 15 job](https://github.com/Dioptas/Dioptas/actions/runs/43102048555/job/130795732247)
  built and signed the current app, obtained Apple acceptance for the app and
  DMG, stapled both, and passed copied-installation, processor and native WebKit
  checks. The downloaded DMG also passed signature/ticket/Gatekeeper and copied
  processor checks on the local macOS 26.6.2 machine.
- Intel: the original native macOS 15 job built/signed the app, passed the
  processor checks, and obtained Apple acceptance, then hit `hdiutil` resource
  contention during DMG creation. The [recovery run](https://github.com/Dioptas/Dioptas/actions/runs/43106031129)
  reused that exact accepted app, obtained its existing ticket, built/signed a
  new DMG, obtained Apple acceptance and passed all installed-app checks,
  including native WebKit on Intel. Only the new DMG was submitted during
  recovery. Downloaded checksums, DMG signature, staple and Gatekeeper
  assessment passed locally as well.
- Both applications come from `c3513f72`; Intel recovery uses packaging revision
  `1ea89f88`. Reports preserve both revisions. The retry/error-classification,
  signing and configuration tests pass; local Chromium/WebKit checks cover the
  two corrected fixture/cancellation timing races without renderer changes.
- The [full native CI run at `1ea89f88`](https://github.com/Dioptas/Dioptas/actions/runs/43106012596)
  passed all four jobs: complete headless desktop/Tauri checks, macOS processor,
  Linux processor/coverage and independent numerical references.

The verified local candidates and reports are in ignored
`artifacts/native-release/verified-2026-11-11/`. No public release or release tag
was created. macOS 14 remains the declared build minimum, not a runtime tested
here; Windows/Linux and universal macOS remain outside this qualification.

## Verified EOS-only macOS rebuild, November 12, 2026

[Candidate run 43205302215](https://github.com/Dioptas/Dioptas/actions/runs/43205302215)
rebuilt both native architectures at clean source
`37f498ae6ee3983f2d014501fceb1e38a134605b`. Both jobs passed. Each app and DMG
was Developer ID signed, accepted by Apple, stapled and assessed by Gatekeeper.
Copied-installation, packaged Rust processor and native WebKit checks passed on
the corresponding native macOS 15 runners. These are fresh builds, without app
recovery from an earlier candidate.

| DMG | Bytes | SHA256 |
| --- | ---: | --- |
| Apple Silicon | 20,401,345 | `94662e3c16156e8645f0abcad794c97fd523df336a4e9fe1166a8add7a2d4b47` |
| Intel | 21,437,864 | `58673c8ed099d32cc777dd98af508d8b189bccd3b0f1457deef522ad01e76834` |

Downloaded Actions ZIP digests and both DMG/app-archive checksums were verified.
Both archived application payloads contain the same EOS-only catalog hash as
`peritheos/SOURCE.json`: all 685 EOS records, zero experimental rows and zero
dataset-file resources. Only the four explicitly allowed Peritheos resource
files are present; empty dataset citation/column descriptors retain refit
provenance. Installed-artifact inspection repeats this check on both runners.

The Apple Silicon DMG also passed local headless copied-installation and
packaged-processor checks, signatures, notarization tickets and Gatekeeper.
The Intel DMG passed local read-only/copy, architecture, resource, signature,
notarization-ticket and Gatekeeper inspection; Intel execution was tested on its
native CI runner. No local native UI window was opened. macOS 14 remains the
declared build minimum rather than a runtime-tested OS in this qualification.

Candidates, original build/checksum reports and local checks are retained in
`artifacts/native-release/verified-eos-only-2026-11-12-43205302215/` with a
`qualification.json` receipt. They supersede the pre-policy November 11
candidates. No application release or tag was published.

## Peritheos distribution scope

All native formats distribute an EOS-only Peritheos catalog: 234 materials and
685 EOS records, retaining model parameters, thermal definitions, uncertainties,
structure, citations and source qualifications. The resource generator excludes
experimental dataset files and embedded observation/audit row tables.
Empty dataset descriptors (identifier, citation and column schema) remain solely
to keep refit provenance valid; all observation arrays are empty and all dataset
file resources are removed. The Rust processor
embeds this same projected catalog; removing only resource files is insufficient.
User-loaded EOS documents are not filtered.

`SOURCE.json` retains the original upstream document hashes and separately records
the projected catalog hash and counts. The shared build hook checks the catalog
before compilation, staging checks the resource directory against an explicit
four-file inventory, and each platform's installed-artifact inspector repeats the
check. Experimental CSVs and the optional Peritheos dataset package are excluded.

Installer candidates built before this policy are superseded for distribution.
Use the EOS-only qualification records above and in the Windows/Linux guides;
the older artifacts retain their original verification evidence only.

To verify the catalog against a checkout at the pinned Peritheos revision without
installing any Python scientific packages, run from the repository root:

```sh
python3 desktop/scripts/peritheos_eos_only.py --peritheos /path/to/peritheos
```

The full metadata generator still requires its independent Python reference
setup; its source annotations are derived from the original upstream documents
before the distribution projection is applied.

## Release candidate 0.14.0-rc.1

The first public Rust desktop candidate continues the Dioptas version sequence
after Qt 0.13.0. See [release notes](RELEASE_0.14.0-rc.1.md).
The application and installer filenames retain the complete semantic version.
The macOS numeric bundle version is 0.14.0. Debian package metadata uses
0.14.0~rc.1 so APT orders it before 0.14.0; the application still reports
0.14.0-rc.1. Lifecycle tests create an rc.2 upgrade fixture from the same source;
that fixture must never be uploaded as a release asset.
