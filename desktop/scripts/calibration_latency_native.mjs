// Run an already-built isolated host with calibration_latency_native.js
// substituted for its --navigation-benchmark driver. See MASSIF_PERFORMANCE.md.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { root } from "./native_backend_client.mjs";
import { nativeTestProfile } from "./native_test_profile.mjs";
const args = process.argv.slice(2),
  option = (n, f) => (args.includes(n) ? args[args.indexOf(n) + 1] : f);
const directory = path.join(root, "desktop/artifacts/calibration-latency");
await mkdir(directory, { recursive: true });
const app = path.resolve(option("--app", path.join(directory, "native-host"))),
  processor = path.resolve(
    option(
      "--processor",
      path.join(root, "desktop/backend/target/debug/dioptas-processor"),
    ),
  ),
  label = option("--label", "optimized");
const profile = await nativeTestProfile("calibration-latency");
const child = spawn(app, ["--backend=rust", "--navigation-benchmark"], {
  cwd: path.join(root, "desktop"),
  stdio: ["ignore", "pipe", "pipe"],
  env: {
    ...profile.env,
    DIOPTAS_SOURCE_ROOT: root,
    DIOPTAS_NATIVE_PROCESSOR: processor,
    DIOPTAS_NAVIGATION_BENCHMARK: JSON.stringify({
      root,
      label,
      foreground: false,
    }),
    DIOPTAS_DEV_RELOAD: "0",
    DIOPTAS_TRACE_NATIVE_NAV: "1",
  },
});
let final;
const logs = [],
  traces = [];
for (const stream of [child.stdout, child.stderr])
  createInterface({ input: stream }).on("line", (line) => {
    logs.push(line);
    if (line.startsWith('{"tauriSmoke":')) {
      const r = JSON.parse(line).tauriSmoke;
      if (!["diagnostic", "hmr"].includes(r.stage)) final = r;
    } else if (line.startsWith("DIOPTAS_NATIVE_TRACE "))
      traces.push(JSON.parse(line.slice(21)));
  });
const timer = setTimeout(() => child.kill("SIGTERM"), 120000);
const code = await new Promise((resolve, reject) => {
  child.once("error", reject);
  child.once("close", resolve);
});
clearTimeout(timer);
await writeFile(path.join(directory, `native-${label}.log`), logs.join("\n"));
assert.equal(code, 0, JSON.stringify(final ?? logs.slice(-15)));
assert.equal(final?.ok, true, JSON.stringify(final));
final.nativeTraces = traces;
await writeFile(
  path.join(directory, `native-${label}.json`),
  JSON.stringify(final, null, 2) + "\n",
);
const summary = {};
for (const kind of new Set(final.rows.map((r) => r.kind))) {
  const rows = final.rows.filter((r) => r.kind === kind);
  summary[kind] = {};
  for (const key of [
    "eventToDrawMs",
    "commandMs",
    "responseToDrawMs",
    "nextFrameMs",
    "presentedByMs",
  ]) {
    const v = rows.map((r) => r[key]).sort((a, b) => a - b);
    summary[kind][key] = {
      median: v[Math.floor(v.length / 2)],
      min: v[0],
      max: v.at(-1),
    };
  }
}
console.log(
  JSON.stringify(
    { label, focused: final.focused, visibility: final.visibility, summary },
    null,
    2,
  ),
);
