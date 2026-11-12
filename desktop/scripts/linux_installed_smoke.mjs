// Runs only in the isolated lifecycle test, after its caller hides the checkout.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { nativeClient } from "./native_backend_client.mjs";

export async function linuxInstalledSmoke({
  inspection,
  executable,
  args = [],
  directory,
  profile,
  denyDirectory,
  logPath,
}) {
  await mkdir(directory, { recursive: true });
  const processor = path.resolve(
    inspection.resourcesDirectory,
    "../../../bin/dioptas-processor",
  );
  const native = nativeClient({
    executable: processor,
    args: ["--resource-dir", inspection.resourcesDirectory],
    cwd: directory,
  });
  try {
    const call = async (action, payload = {}) => {
      const result = await native.invoke(action, payload);
      assert.equal(result.ok, true, `${action}: ${result.error}`);
      return result;
    };
    assert.equal((await call("__host__")).runtime, "rust");
    await call("example");
    await call("open_calibration", {
      path: path.join(
        inspection.resourcesDirectory,
        "examples/CeO2_Pilatus1M.poni",
      ),
    });
    await call("integration_settings", {
      bins: 128,
      cake_bins: 24,
      poisson_errors: true,
    });
    for (const kind of ["cylinder", "sphere"]) {
      const result = await call("integration_correction", {
        kind,
        enabled: true,
        parameters: { radius: 0.2, beam_width: 0.12 },
        material: { mode: "formula", formula: "SiO2", density: 2.2 },
      });
      assert(result.pattern.y.every(Number.isFinite));
      assert(result.pattern.sigma.some((v) => v > 0));
    }
    await call("configuration", { operation: "duplicate" });
    const combined = await call("combination_settings", {
      patterns: true,
      cakes: true,
    });
    assert.equal(combined.pattern.y.length, 128);
    assert.equal(combined.cake.height, 24);
    const project = path.join(directory, "portable ü.dio");
    await call("save_project", { path: project });
    const reopened = await call("open_project", { path: project });
    assert.equal(reopened.state.configurationCount, 2);
    assert.deepEqual(reopened.pattern, combined.pattern);
    await call("save_combined_pattern", {
      path: path.join(directory, "portable.xy"),
    });
  } finally {
    await native.close();
  }

  const uiOutput = path.join(directory, "ui");
  await mkdir(uiOutput);
  const env = { ...process.env };
  for (const key of Object.keys(env))
    if (
      /^(LD_LIBRARY_PATH|LD_PRELOAD|PYTHONPATH|PYTHONHOME|DIOPTAS_NATIVE_PROCESSOR|DIOPTAS_BACKEND|APPDIR|APPIMAGE|APPIMAGE_EXTRACT_AND_RUN)$/i.test(
        key,
      )
    )
      delete env[key];
  Object.assign(env, {
    PATH: `${denyDirectory}:/usr/bin:/bin`,
    HOME: profile,
    XDG_CONFIG_HOME: path.join(profile, "config"),
    XDG_DATA_HOME: path.join(profile, "data"),
    XDG_CACHE_HOME: path.join(profile, "cache"),
    DIOPTAS_PYTHON: "/nonexistent/python",
    DIOPTAS_SOURCE_ROOT: "/nonexistent/checkout",
    HDF5_PLUGIN_PRELOAD: "::",
    DIOPTAS_STANDALONE_TEST_DIRECTORY: uiOutput,
    LIBGL_ALWAYS_SOFTWARE: "1",
    GALLIUM_DRIVER: "llvmpipe",
    WEBKIT_DISABLE_DMABUF_RENDERER: "1",
    GDK_GL: "gles",
    GDK_BACKEND: "x11",
    NO_AT_BRIDGE: "1",
    LIBGL_DEBUG: "verbose",
    EGL_LOG_LEVEL: "debug",
  });
  const logs = [];
  const child = spawn(
    executable,
    [...args, "--example", "--standalone-smoke"],
    { cwd: directory, env, detached: true, stdio: ["ignore", "pipe", "pipe"] },
  );
  child.stdout.on("data", (b) => logs.push(b.toString()));
  child.stderr.on("data", (b) => logs.push(b.toString()));
  const kill = (signal) => {
    try {
      process.kill(-child.pid, signal);
    } catch (e) {
      if (e.code !== "ESRCH") throw e;
    }
  };
  const timer = setTimeout(() => kill("SIGKILL"), 180_000);
  try {
    const code = await new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("close", resolve);
    });
    const reports = logs
      .join("")
      .split(/\r?\n/)
      .filter((line) => line.startsWith('{"tauriSmoke":'))
      .map((line) => JSON.parse(line).tauriSmoke);
    const ui = reports.findLast((report) => report.standalone);
    assert.equal(code, 0, logs.join(""));
    assert.equal(ui?.ok, true, ui?.error || logs.join(""));
    let reaped = false;
    for (let i = 0; i < 50; i++) {
      try {
        process.kill(ui.processingPid, 0);
        await delay(100);
      } catch (e) {
        if (e.code !== "ESRCH") throw e;
        reaped = true;
        break;
      }
    }
    assert(reaped, "Installed processor survived host exit");
    assert(
      (await readFile(path.join(uiOutput, "standalone.dio"))).length > 1000,
    );
    assert((await readFile(path.join(uiOutput, "standalone.xy"))).length > 100);
    return {
      ok: true,
      headlessProcessor: true,
      projectRoundtrip: true,
      combinedPatternAndCake: true,
      countingStd: true,
      nativeWebKit: ui,
      processorReaped: reaped,
      inspection,
      graphics: {
        backend: "x11",
        softwareRendering: true,
        dmabufDisabled: true,
        gdkGl: "gles",
      },
    };
  } catch (error) {
    error.inspection = inspection;
    throw error;
  } finally {
    clearTimeout(timer);
    kill("SIGTERM");
    await writeFile(logPath, logs.join(""));
  }
}
