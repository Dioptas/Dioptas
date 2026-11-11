// A real packaged-WebKit check with the checkout and Python denied by macOS.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { inspectStandalone } from "./inspect_standalone.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const application =
  process.argv[2] ||
  path.join(
    desktop,
    "src-tauri/target/release/bundle/macos/Dioptas Desktop.app",
  );
const preserveSignature = process.argv.includes("--preserve-signature");
const inspectionOptions = preserveSignature
  ? { teamIdentifier: process.env.DIOPTAS_APPLE_TEAM_ID }
  : {};
assert(
  !preserveSignature || inspectionOptions.teamIdentifier,
  "Set DIOPTAS_APPLE_TEAM_ID when preserving a release signature",
);
const inspection = await inspectStandalone(application, inspectionOptions);
// Tauri intentionally rejects symlinked macOS executable paths (/var -> /private/var).
const directory = await realpath(
  await mkdtemp(path.join(os.tmpdir(), "Dioptas standalone qualification ")),
);
const app = path.join(directory, "Relocated Dioptas.app");
const artifacts = path.join(desktop, "artifacts/standalone");
await mkdir(artifacts, { recursive: true });
const logs = [];
let report;
try {
  await cp(application, app, { recursive: true });
  if (!preserveSignature) {
    const plist = path.join(app, "Contents/Info.plist");
    execFileSync("/usr/bin/plutil", [
      "-replace",
      "CFBundleIdentifier",
      "-string",
      `org.dioptas.standalone-qualification-${process.pid}`,
      plist,
    ]);
    execFileSync(
      "/usr/bin/codesign",
      ["--force", "--deep", "--sign", "-", app],
      {
        stdio: ["ignore", "ignore", "pipe"],
      },
    );
  }
  const home = path.join(directory, "home"),
    output = path.join(directory, "output");
  await mkdir(home);
  await mkdir(output);
  const repository = path.dirname(desktop.slice(0, -1));
  const blocked = [
    repository,
    path.join(os.homedir(), ".codex/worktrees/dioptas-react-desktop/Dioptas"),
    path.join(os.homedir(), "Programming/Dioptas"),
    path.join(os.homedir(), ".cargo"),
    "/opt/homebrew",
  ];
  const profile = `(version 1) (allow default)\n${blocked.map((p) => `(deny file-read* (subpath ${JSON.stringify(p)}))`).join("\n")}\n(deny process-exec (regex #".*/[Pp]ython[^/]*$"))\n`;
  const env = {
    ...process.env,
    HOME: home,
    PATH: "/nonexistent",
    DIOPTAS_PYTHON: "/nonexistent/python",
    DIOPTAS_SOURCE_ROOT: "/nonexistent/source-checkout",
    HDF5_PLUGIN_PRELOAD: "::",
    DIOPTAS_STANDALONE_TEST_DIRECTORY: output,
  };
  for (const key of [
    "DIOPTAS_BACKEND",
    "DIOPTAS_NATIVE_PROCESSOR",
    "DYLD_LIBRARY_PATH",
    "DYLD_FALLBACK_LIBRARY_PATH",
    "HDF5_PLUGIN_PATH",
  ])
    delete env[key];
  // Prove the exact profile denies the existing checkout, rather than merely
  // pointing the app at another directory while leaving source access possible.
  assert.equal(
    execFileSync(
      "/usr/bin/sandbox-exec",
      ["-p", profile, "/bin/echo", "sandbox-ready"],
      { env, encoding: "utf8" },
    ).trim(),
    "sandbox-ready",
  );
  assert.throws(() =>
    execFileSync(
      "/usr/bin/sandbox-exec",
      [
        "-p",
        profile,
        "/bin/cat",
        path.join(repository, "desktop/package.json"),
      ],
      { env, stdio: "pipe" },
    ),
  );
  const executable = path.join(app, "Contents/MacOS/dioptas-desktop");
  const child = spawn(
    "/usr/bin/sandbox-exec",
    ["-p", profile, executable, "--example", "--standalone-smoke"],
    { cwd: directory, env, stdio: ["ignore", "pipe", "pipe"] },
  );
  const timer = setTimeout(() => child.kill("SIGTERM"), 150_000);
  child.stdout.on("data", (data) => logs.push(data.toString()));
  child.stderr.on("data", (data) => logs.push(data.toString()));
  try {
    const code = await new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("close", resolve);
    });
    for (const line of logs.join("").split("\n")) {
      if (line.startsWith('{"tauriSmoke":'))
        report = JSON.parse(line).tauriSmoke;
    }
    assert.equal(code, 0, logs.join(""));
    assert.equal(report?.ok, true, report?.error || logs.join(""));
    assert.throws(
      () => process.kill(report.processingPid, 0),
      { code: "ESRCH" },
      "Packaged child survived window closure",
    );
    assert((await readFile(path.join(output, "standalone.dio"))).length > 1000);
    assert(
      (await readFile(path.join(output, "standalone.xy"), "utf8")).length > 100,
    );
    await inspectStandalone(app, inspectionOptions); // Signed resources must also remain intact after use.
    report = {
      ...report,
      sourceAccess: "denied by verified sandbox policy",
      pythonExecution: "denied",
      environmentPaths: "unavailable",
      relocated: true,
      processingReaped: true,
      postRunIntegrity: true,
      inspection,
    };
    await writeFile(
      path.join(artifacts, "native-smoke.json"),
      JSON.stringify(report, null, 2) + "\n",
    );
    console.log(JSON.stringify(report, null, 2));
  } finally {
    clearTimeout(timer);
    if (child.exitCode === null) child.kill("SIGTERM");
  }
} finally {
  await writeFile(path.join(artifacts, "native-smoke.log"), logs.join(""));
  await rm(directory, { recursive: true, force: true });
}
