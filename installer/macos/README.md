# macOS signing and notarization

Release builds require a **Developer ID Application** certificate and Apple
notarization credentials. Ordinary branch pushes remain ad-hoc signed. A manual
`CD_MACOS` run with `sign_and_notarize` enabled exercises the complete signed app
and DMG path without creating a release or publishing to PyPI.

This setup targets GitHub-hosted macOS runners. It does not require an App Store
listing or a provisioning profile for Dioptas's current capabilities.

## 1. Prepare this Mac

If Apple tools report that the Xcode licence has not been accepted, run this in
Terminal and review the agreement:

```sh
sudo xcodebuild -license
```

Then check that the tools are available:

```sh
xcrun --find notarytool
security find-identity -v -p codesigning
```

An `Apple Development` identity is for development. The download builds require
an identity named `Developer ID Application: Name or Organisation (TEAMID)`.

## 2. Create and export the certificate

1. Open **Keychain Access** on the Mac that will hold the private key.
2. Choose **Keychain Access → Certificate Assistant → Request a Certificate
   from a Certificate Authority**. Enter your Apple account email and a common
   name such as `Dioptas distribution`. Leave the CA email empty and select
   **Saved to disk**. Save the `.certSigningRequest` file.
3. Sign in as the team's **Account Holder** at
   [Apple Developer → Certificates](https://developer.apple.com/account/resources/certificates/list).
   Click **+**, select **Developer ID Application** (the portal may group this
   under **Developer ID**), and upload the request. Download the `.cer` file.
   Choose the Application certificate; an Installer certificate is for `.pkg`
   installers and is not needed for our `.app` and `.dmg` downloads.
4. Double-click the `.cer` to import it into the same Mac's login keychain.
   Under **My Certificates**, expand the new certificate and confirm that it
   has a private key beneath it.
5. Select the certificate identity, choose **Export**, and save it as
   `Dioptas-Developer-ID.p12` outside the repository, for example in Documents.
   Include its private key and set a strong export password. If `.p12` is not
   available, check that you selected the identity under **My Certificates**
   with its private key, rather than a certificate without a key.
6. Run `security find-identity -v -p codesigning` again. Confirm that the
   **Developer ID Application** identity is valid. Its parenthesized team ID
   must match the **Team ID** in your developer account's Membership details.
   Use the membership Team ID, rather than assuming an existing development
   certificate belongs to the same team.

Apple documents [certificate requests](https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request/)
and [Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/).
Keep a protected backup of the P12 and its password; the downloaded `.cer` alone
does not contain the private key.

## 3. Create the notarization password

Sign in at [account.apple.com](https://account.apple.com), open **Sign-In and
Security → App-Specific Passwords**, and generate one named
`Dioptas GitHub notarization`. The account must have two-factor authentication
enabled and access to the selected Developer Program team.

Use this app-specific password for notarization, not your normal Apple account
password. Changing your normal account password revokes app-specific passwords,
so update the GitHub secret if that happens.

See [Apple's password instructions](https://support.apple.com/en-us/102654) and
[notarytool authentication](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool).

## 4. Add five GitHub Actions repository secrets

Open [Dioptas → Settings → Secrets and variables → Actions](https://github.com/Dioptas/Dioptas/settings/secrets/actions)
and choose **New repository secret** for each entry:

| Secret | Value |
| --- | --- |
| `MACOS_CERTIFICATE_P12_BASE64` | Base64-encoded contents of the exported P12, including its private key |
| `MACOS_CERTIFICATE_PASSWORD` | Password chosen when exporting that P12 |
| `APPLE_ID` | Apple account email used for notarization |
| `APPLE_TEAM_ID` | The 10-character Team ID from Membership details |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password generated in step 3 |

To encode the certificate and copy it for the first secret, adjust this path:

```sh
base64 -i "$HOME/Documents/Dioptas-Developer-ID.p12" | pbcopy
```

Paste into GitHub's secret value field. Do not paste credentials into chat,
workflow YAML, issues, or commits. The workflow selects the imported certificate
by fingerprint and validates its team; no signing-identity secret is necessary.
It generates a random temporary keychain password on each run.

Alternatively, with GitHub CLI already authenticated, upload the file directly
and enter the other values at the CLI's interactive prompts:

```sh
base64 -i "$HOME/Documents/Dioptas-Developer-ID.p12" |
  gh secret set MACOS_CERTIFICATE_P12_BASE64 --repo Dioptas/Dioptas
gh secret set MACOS_CERTIFICATE_PASSWORD --repo Dioptas/Dioptas
gh secret set APPLE_ID --repo Dioptas/Dioptas
gh secret set APPLE_TEAM_ID --repo Dioptas/Dioptas
gh secret set APPLE_APP_SPECIFIC_PASSWORD --repo Dioptas/Dioptas
gh secret list --repo Dioptas/Dioptas
```

GitHub explains [certificate secrets and temporary runner keychains](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications).
Anyone able to change and run a workflow with these secrets can use the signing
identity. Limit repository write access to trusted maintainers. Forks need their
own secrets to run a signed build; their ordinary builds remain ad-hoc signed.

## 5. Test before releasing

The workflow changes must be pushed to GitHub. GitHub normally exposes the
manual workflow UI once `workflow_dispatch` exists on the default branch.
From [Actions → CD_MACOS](https://github.com/Dioptas/Dioptas/actions/workflows/build_mac.yml),
choose **Run workflow**, select the branch containing these changes, and leave
**Sign with Developer ID and notarize** enabled. Alternatively:

```sh
# Replace BRANCH_WITH_SIGNING with the branch containing these changes.
gh workflow run build_mac.yml --repo Dioptas/Dioptas \
  --ref BRANCH_WITH_SIGNING -f sign_and_notarize=true
```

This run imports the P12 into a temporary keychain, validates the notarization
credentials, signs all bundled code through PyInstaller with hardened runtime
and secure timestamps, runs the executable smoke test, notarizes the app,
staples its ticket, and verifies it with Gatekeeper. The archive contains that
stapled app. It then creates, signs, notarizes and staples the DMG separately.
The signing keychain and temporary credentials are removed even if a step fails.

Download the `DioptasMac` artifact, open its DMG, drag Dioptas to Applications,
and launch it normally. Also check the app extracted from its tar archive.
Do not remove quarantine attributes for this test. Gatekeeper may still show
the standard first-launch confirmation identifying the developer.

For additional checks, adjust the paths to the downloaded artifacts:

```sh
codesign --verify --deep --strict --verbose=2 /Applications/Dioptas_*.app
spctl --assess --type execute --verbose=2 /Applications/Dioptas_*.app
xcrun stapler validate /Applications/Dioptas_*.app
xcrun stapler validate "$HOME/Downloads/Dioptas_MacOS.dmg"
```

The `macos-notarization-logs` artifact contains submission IDs, status responses,
and rejection details when Apple provides them. A submission must return
`Accepted` before stapling or artifact upload. A 30-minute wait timeout also
fails the build; Apple may still be processing that submission, so inspect its
ID before submitting another build. First submissions can take longer.

To inspect Apple's recent submissions without building or uploading anything,
run the status-only check:

```sh
gh workflow run build_mac.yml --repo Dioptas/Dioptas \
  --ref BRANCH_WITH_SIGNING -f notarization_status_only=true
```

Its `notarization_status` job prints submission IDs and their current status.
The build job is skipped in this mode, so it can run while another build waits
for notarization.

Tagged releases use the same signing path and fail if any secret is missing,
the P12 is invalid, its team differs, notarization fails or times out, or
signature/Gatekeeper checks fail. They cannot silently publish an ad-hoc macOS
app. Ordinary branch builds do not access the Apple secrets or submit to Apple.

## Development checks

These checks require no Apple credentials or macOS services:

```sh
python -m unittest discover -s installer/macos -p 'test_*.py' -v
bash -n installer/macos/create_dmg.sh
```

Full validation still requires a real signed run and a downloaded-app launch.
No hardened-runtime exceptions are enabled by default. If a required optional
library or plugin fails in the signed smoke test, identify that failure before
adding a narrowly scoped entitlement. PyInstaller documents its
[macOS signing support](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing).
