// Mutates only an explicitly authorized disposable Linux test machine.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmod,
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { root } from "./native_backend_client.mjs";
import { inspectLinuxInstall } from "./inspect_linux_install.mjs";
import { linuxInstalledSmoke } from "./linux_installed_smoke.mjs";
import { elfMachine } from "./linux_release_config.mjs";

assert.equal(process.platform, "linux");
assert.equal(
  process.env.DIOPTAS_INSTALLER_TEST_ISOLATED,
  "1",
  "Use an explicitly isolated installer test machine",
);
assert(
  process.env.DISPLAY && process.env.DBUS_SESSION_BUS_ADDRESS,
  "Run under Xvfb and dbus-run-session",
);
const candidateDirectory = path.resolve(process.argv[2]);
const reportPath = path.resolve(process.argv[3]);
const format = process.argv[4] ?? "deb";
assert(["deb", "appimage"].includes(format));
const metadata = JSON.parse(
  await readFile(path.join(candidateDirectory, "build.json"), "utf8"),
);
const verificationRevision = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: root,
  encoding: "utf8",
}).trim();
assert.equal(metadata.signing, "unsigned-test");
assert.equal(metadata.published, false);
assert.equal(metadata.format, format);
const ceiling = metadata.glibcBaseline.split(".").map(Number);
for (const b of metadata.builds) {
  assert.equal(path.basename(b.file), b.file);
  assert.equal(
    createHash("sha256")
      .update(await readFile(path.join(candidateDirectory, b.file)))
      .digest("hex"),
    b.sha256,
  );
}
const run = (command, args, options = {}) =>
  execFileSync(command, args, { encoding: "utf8", ...options });
const debs = metadata.builds.filter((b) => b.kind === "deb");
if (format === "deb") assert(debs.length);
const packageName =
  format === "deb"
    ? run("dpkg-deb", [
        "--field",
        path.join(candidateDirectory, debs[0].file),
        "Package",
      ]).trim()
    : "dioptas-desktop";
assert.equal(packageName, "dioptas-desktop");
try {
  assert.notEqual(
    run("dpkg-query", ["-W", "-f=${db:Status-Status}", packageName]).trim(),
    "installed",
    "Do not replace an existing installation",
  );
} catch (e) {
  if (e.status !== 1) throw e;
}
const temporary = await mkdtemp(
  path.join(os.tmpdir(), "Dioptas Linux installer ü "),
);
const profile = path.join(temporary, "profile");
const settings = path.join(profile, "config", metadata.identifier);
await mkdir(settings, { recursive: true });
const sentinel = path.join(settings, "installer-preserve.txt");
await writeFile(sentinel, "retain user settings");
const denyDirectory = path.join(temporary, "deny-tools");
await mkdir(denyDirectory);
const denyLog = path.join(temporary, "denied-tools.log");
for (const name of ["python", "python3", "node", "cargo", "rustc"]) {
  const file = path.join(denyDirectory, name);
  await writeFile(
    file,
    `#!/bin/sh\nprintf '%s\\n' '${name}' >> '${denyLog.replaceAll("'", "'\\''")}'\nexit 126\n`,
  );
  await chmod(file, 0o755);
}
const previousDirectory = process.cwd(),
  originalRoot = path.resolve(root),
  hiddenRoot = `${originalRoot}.unavailable-${process.pid}`;
const receipts = [];
let hidden = false,
  installed = false;
try {
  process.chdir(temporary);
  await rename(originalRoot, hiddenRoot);
  hidden = true;
  if (format !== "appimage") {
    for (const b of debs) {
      const deb = path.join(candidateDirectory, b.file);
      assert.equal(
        run("dpkg-deb", ["--field", deb, "Architecture"]).trim(),
        "amd64",
      );
      assert.equal(
        run("dpkg-deb", ["--field", deb, "Version"]).trim(),
        b.version,
      );
      const depends = run("dpkg-deb", ["--field", deb, "Depends"]);
      assert(
        depends.includes("libwebkit2gtk-4.1-0") &&
          depends.includes("libgtk-3-0"),
        depends,
      );
      run(
        "sudo",
        ["apt-get", "install", "-y", "--no-install-recommends", deb],
        { stdio: "inherit" },
      );
      installed = true;
      assert.equal(
        run("dpkg-query", ["-W", "-f=${Version}", packageName]).trim(),
        b.version,
      );
      const inspection = await inspectLinuxInstall("/", false, ceiling);
      const runtime = await linuxInstalledSmoke({
        inspection,
        executable: "/usr/bin/dioptas-desktop",
        directory: path.join(temporary, `deb-${b.version}`),
        profile,
        denyDirectory,
        logPath: `${reportPath}.deb-${b.version}.log`,
      });
      receipts.push({
        kind: "deb",
        version: b.version,
        depends: depends.trim(),
        registration: true,
        runtime,
      });
      assert.equal(await readFile(sentinel, "utf8"), "retain user settings");
    }
    run("sudo", ["apt-get", "purge", "-y", packageName], { stdio: "inherit" });
    installed = false;
    for (const file of [
      "/usr/bin/dioptas-desktop",
      "/usr/bin/dioptas-processor",
      path.join(
        receipts[0].runtime.inspection.resourcesDirectory,
        "RESOURCE_MANIFEST.json",
      ),
      receipts[0].runtime.inspection.desktopFile,
    ]) {
      await assert.rejects(readFile(file), { code: "ENOENT" });
    }
  }
  assert.equal(await readFile(sentinel, "utf8"), "retain user settings");
  if (format !== "deb") {
    // AppImage qualification uses a separate fresh runner, without installing
    // the .deb or its dependencies first.
    for (const file of [
      "/usr/bin/dioptas-desktop",
      "/usr/bin/dioptas-processor",
      "/usr/lib/dioptas-desktop/dioptas/RESOURCE_MANIFEST.json",
      `/usr/lib/${metadata.productName}/dioptas/RESOURCE_MANIFEST.json`,
    ]) {
      await assert.rejects(readFile(file), { code: "ENOENT" });
    }
    const portable = metadata.builds.find((b) => b.kind === "appimage");
    assert(portable);
    const portableDirectory = path.join(temporary, "Portable App ü");
    await mkdir(portableDirectory);
    const appimage = path.join(portableDirectory, portable.file);
    await copyFile(path.join(candidateDirectory, portable.file), appimage);
    await chmod(appimage, 0o755);
    assert.equal(elfMachine(await readFile(appimage)), 62);
    run(appimage, ["--appimage-extract"], {
      cwd: portableDirectory,
      maxBuffer: 16 * 1024 * 1024,
    });
    const inspection = await inspectLinuxInstall(
      path.join(portableDirectory, "squashfs-root"),
      true,
      ceiling,
    );
    for (const mode of ["fuse", "extract-and-run"]) {
      const runtime = await linuxInstalledSmoke({
        inspection,
        executable: appimage,
        args: mode === "fuse" ? [] : ["--appimage-extract-and-run"],
        directory: path.join(temporary, mode),
        profile,
        denyDirectory,
        logPath: `${reportPath}.${mode}.log`,
      });
      receipts.push({
        kind: "appimage",
        mode,
        version: portable.version,
        runtime,
      });
    }
    await rm(appimage);
  }
  assert.equal(await readFile(sentinel, "utf8"), "retain user settings");
  await assert.rejects(readFile(denyLog), { code: "ENOENT" });
  await writeFile(
    reportPath,
    JSON.stringify(
      {
        ok: true,
        sourceRevision: metadata.sourceRevision,
        verificationRevision,
        signing: metadata.signing,
        published: false,
        system: await readFile("/etc/os-release", "utf8"),
        sourceCheckoutAtBuildPathUnavailable: true,
        developerToolExecutionsDenied: true,
        format,
        installedVersions: receipts,
        upgrade: format !== "appimage" && debs.length > 1,
        uninstall: format !== "appimage",
        portableRemoval: format !== "deb",
        userSettingsMarkerPreserved: true,
      },
      null,
      2,
    ) + "\n",
  );
} catch (error) {
  await writeFile(
    reportPath,
    JSON.stringify(
      {
        ok: false,
        sourceRevision: metadata.sourceRevision,
        verificationRevision,
        format,
        error: error.stack ?? String(error),
        inspection: error.inspection,
      },
      null,
      2,
    ) + "\n",
  );
  throw error;
} finally {
  if (installed) {
    try {
      run("sudo", ["apt-get", "purge", "-y", packageName], {
        stdio: "inherit",
      });
    } catch {}
  }
  if (hidden) await rename(hiddenRoot, originalRoot);
  process.chdir(previousDirectory);
  await rm(temporary, { recursive: true, force: true });
}
