import test from "node:test";
import assert from "node:assert/strict";
import {
  linuxConfig,
  elfMachine,
  requiredGlibc,
  resolvedDependencies,
} from "./linux_release_config.mjs";

test("Linux candidates use deb/AppImage, explicit glibc baseline and no multimedia payload", () => {
  assert.deepEqual(linuxConfig.bundle.targets, ["deb", "appimage"]);
  assert(linuxConfig.bundle.linux.deb.depends.includes("libc6 (>= 2.35)"));
  assert.equal(linuxConfig.bundle.linux.deb.section, "science");
  assert.equal(linuxConfig.bundle.linux.appimage.bundleMediaFramework, false);
  assert(
    linuxConfig.bundle.linux.appimage.files["/usr/lib/libGLESv2.so.2"],
    "Bundle WebKit's dynamically loaded GLES client",
  );
});
test("ELF inspection rejects wrong formats, byte order and truncated files", () => {
  const b = Buffer.alloc(64);
  b.write("\x7fELF");
  b[4] = 2;
  b[5] = 1;
  b.writeUInt16LE(62, 18);
  assert.equal(elfMachine(b), 62);
  assert.throws(() => elfMachine(b.subarray(0, 30)), /Truncated/);
  b[5] = 2;
  assert.throws(() => elfMachine(b), /little-endian/);
  assert.throws(() => elfMachine(Buffer.alloc(64)), /Expected ELF/);
});
test("glibc requirements compare numerically and fail above the baseline", () => {
  assert.equal(requiredGlibc("GLIBC_2.9 GLIBC_2.34 GLIBC_2.2.5"), "2.34.0");
  assert.equal(requiredGlibc("GLIBCXX_3.4.30"), null);
  assert.throws(() => requiredGlibc("GLIBC_2.36"), /above/);
  assert.equal(requiredGlibc("GLIBC_2.39", [2, 39]), "2.39.0");
  assert.throws(() => requiredGlibc("GLIBC_2.40", [2, 39]), /above/);
});
test("ELF dependency inspection rejects missing and build-path dependencies", () => {
  assert.deepEqual(
    resolvedDependencies(
      "libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x1)\n/lib64/ld-linux-x86-64.so.2 (0x2)",
    ),
    ["/lib/x86_64-linux-gnu/libc.so.6", "/lib64/ld-linux-x86-64.so.2"],
  );
  assert.throws(
    () => resolvedDependencies("libhdf5.so => not found"),
    /Missing/,
  );
  assert.throws(
    () =>
      resolvedDependencies(
        "libtest.so => /home/runner/work/Dioptas/libtest.so (0x1)",
      ),
    /Build-time/,
  );
});
