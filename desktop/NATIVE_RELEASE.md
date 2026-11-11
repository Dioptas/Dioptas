# Native installer candidates

Native installers are the primary distribution route. A pip distribution is
deferred. This pipeline builds candidates only: it has no tag creation, GitHub
Release, PyPI upload, updater publication or release write permission.

## Shared configuration

`package.json` owns the application version; `src-tauri/tauri.conf.json` reads
that version directly. `src-tauri/tauri.release.conf.json` overlays the stable
native identity (`org.dioptas.desktop`), window title, platform icons and bundle
metadata. The preview identity and legacy Qt identity remain separate, including
their settings/WebKit storage. The current `0.1.0` is a packaging test version,
not a newly announced public release version.

The release overlay is shared with future Windows/Linux installer jobs. Those
platforms still need their own build, dependency and installed-application tests.
Do not infer their qualification from a macOS candidate. Icons are generated
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
14 days. No release is published. Manual dispatch becomes available once the
workflow is present on the repository's default branch.

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
