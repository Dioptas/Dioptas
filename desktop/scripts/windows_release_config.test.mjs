import assert from "node:assert/strict";
import test from "node:test";
import {
  windowsConfig,
  windowsSigning,
  peMachine,
  importLocation,
} from "./windows_release_config.mjs";

test("Windows candidates include offline WebView2 and app-local CRT without requiring admin", () => {
  assert.deepEqual(windowsConfig.bundle.targets, ["nsis"]);
  assert.equal(
    windowsConfig.bundle.windows.webviewInstallMode.type,
    "offlineInstaller",
  );
  assert.equal(windowsConfig.bundle.windows.bundleVCRuntime, true);
  assert.equal(windowsConfig.bundle.windows.nsis.installMode, "currentUser");
  assert.equal(windowsConfig.bundle.windows.allowDowngrades, false);
});
test("signed mode requires an expected signer; unsigned mode clears signing configuration", () => {
  assert.throws(() => windowsSigning(false, {}), /THUMBPRINT/);
  assert.deepEqual(
    windowsSigning(true, { DIOPTAS_WINDOWS_SIGN_COMMAND: "must not run" }),
    { certificateThumbprint: null, signCommand: null },
  );
  assert.equal(
    windowsSigning(false, { DIOPTAS_WINDOWS_SIGNER_THUMBPRINT: "A".repeat(40) })
      .certificateThumbprint,
    "A".repeat(40),
  );
});
test("PE inspection rejects invalid headers and distinguishes x64 from x86", () => {
  const bytes = Buffer.alloc(160);
  assert.throws(() => peMachine(bytes));
  bytes.writeUInt16LE(0x5a4d);
  bytes.writeUInt32LE(80, 0x3c);
  bytes.writeUInt32LE(0x4550, 80);
  bytes.writeUInt16LE(0x8664, 84);
  assert.equal(peMachine(bytes), 0x8664);
  bytes.writeUInt16LE(0x14c, 84);
  assert.equal(peMachine(bytes), 0x14c);
});
test("dependency checks reject machine-installed CRT and missing third-party DLLs", () => {
  assert.throws(
    () => importLocation("VCRUNTIME140.dll", new Set(), true),
    /must be bundled/,
  );
  assert.throws(
    () => importLocation("hdf5.dll", new Set(), false),
    /Unbundled/,
  );
  assert.equal(
    importLocation("VCRUNTIME140.dll", new Set(["vcruntime140.dll"]), false),
    "application",
  );
  assert.equal(
    importLocation("KERNEL32.dll", new Set(), true),
    "windows-system",
  );
  assert.equal(
    importLocation("api-ms-win-crt-runtime-l1-1-0.dll", new Set(), false),
    "windows-api-set",
  );
});
