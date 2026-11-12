# Application updates

Installed release builds can find, download and install a newer Dioptas release
from GitHub. Previews, local builds, the standalone bundle and isolated test
windows never contact the release server.

## What the user sees

- A small download button appears above Settings in the left sidebar when a
  newer release exists. It never opens by itself and there is no start-up dialog.
- Its popover shows the release notes with **Download update**, **Later** and
  **Skip this version**. The download runs in the background.
  A skipped version is not announced again; **Check for updates** in Settings
  brings it back.
- When the package is downloaded and verified, the button offers **Restart to
  update**. Nothing is replaced before that click, and it is disabled while a
  command is processing. Unsaved session changes are not kept.
- Settings › General › Updates has **Check for updates** and the switch for the
  automatic check (shortly after start, then every six hours). Automatic checks
  fail silently when the computer is offline.
- If installation in place is impossible, for example from a read-only location,
  the popover offers the GitHub download page instead.

## How it works

`tauri-plugin-updater` runs in the host only. The webview has four commands
(`update_check`, `update_download`, `update_apply`, `open_update_page`) defined
in `src-tauri/src/app_update.rs`; the plugin's own JavaScript commands have no
capability. The interface state is in `src/appUpdateModel.ts` and
`src/useAppUpdate.ts`.

The application reads
`https://github.com/Dioptas/Dioptas/releases/latest/download/latest.json`.
GitHub's "latest" release excludes drafts and prereleases, so release
candidates are not offered to users of a stable version.

| Installation              | Update package          | Notes                                                |
| ------------------------- | ----------------------- | ---------------------------------------------------- |
| macOS, both architectures | notarized `.app.tar.gz` | replaces the application bundle                      |
| Windows                   | NSIS `-setup.exe`       | per-user installation, passive installer, relaunches |
| Linux AppImage            | the `.AppImage`         | replaces the AppImage file                           |
| Linux `.deb`              | the `.deb`              | installed through the system's administrator prompt  |

Every package is signed with the project's update key (minisign). The
application contains the public key and rejects anything else. Because
`latest.json` itself is unsigned, `requireSignedVersion` binds each signature to
its version: a manipulated manifest cannot present an older package as new.
This key is independent of Apple Developer ID and Windows code signing.

## One-time setup

Updates stay switched off until the release configuration contains a key.

1. Create the key pair on a trusted computer and keep the private file and its
   password in a password manager. Losing it means installed versions can no
   longer be updated automatically; they would need one manual installation.

   ```sh
   cd desktop
   npx tauri signer generate -w ~/.tauri/dioptas-update.key
   ```

2. Put the printed public key into `plugins.updater.pubkey` in
   `src-tauri/tauri.release.conf.json` and commit it.
3. Add the repository secrets `TAURI_SIGNING_PRIVATE_KEY` (the content of the
   key file) and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`. Scoping them to the
   `native-release` environment with a required reviewer is recommended.

Only versions built after step 2 can update themselves. Earlier installations,
including 0.14.0-rc.1, need one manual installation of such a version.

## Publishing a release

1. Run the native macOS, Windows and Linux artifact workflows for the release
   commit and wait for their verification.
2. Run **Native release** (`.github/workflows/native_release.yml`) with the run
   IDs of those workflows. It downloads the verified candidates and runs
   `scripts/updater_release.mjs`, which

   - requires one version, one unedited source commit, notarized macOS
     candidates and unchanged checksums,
   - signs the five update packages and verifies each signature against the
     configured public key, exactly as an installed application will,
   - writes `latest.json`, `SHA256SUMS` and the public file names.

   The notes in the update popover are the introduction of
   `RELEASE_<version>.md` (everything before its first `##` heading).

3. Review the draft release on GitHub and publish it. The tag is the version
   without a prefix and points at the commit the installers were built from.

Keep these rules, because installed applications follow `releases/latest`:

- Only a stable Rust desktop release may be marked as the latest release. When
  publishing a Qt maintenance release from `legacy/qt`, clear "Set as the latest
  release"; otherwise update checks find no manifest until the next Rust release.
- Never replace the files of a published release. Publish a new version instead.

## Tests

```sh
npm test                    # includes scripts/app_update.test.mjs
npm run test:release-config # includes scripts/updater_release.test.mjs
npm run test:app-update     # headless notice, popover and Settings card
cargo test --locked --manifest-path src-tauri/Cargo.toml app_update
```

Not covered by automated tests: replacing a real installation on macOS, Windows
and Linux. Before the first public release with updates, install a test version
on each system and update it from a test release, for example in a fork with
its own endpoint and key.
