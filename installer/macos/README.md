# Native macOS signing and notarization utility

`signing.py` remains because native macOS packaging uses its Apple credential,
keychain and notarization support. It is a release utility, not application
processing or a Python test suite. See the current native packaging guides:

- [macOS release procedure](../../docs/release/NATIVE_RELEASE.md)
- [DMG recovery](../../NATIVE_DMG_RECOVERY.md)

The Qt/PyInstaller scripts and their Python tests are preserved on `legacy/qt`.
Native packaging tests use the Node release/configuration/stapler checks.
