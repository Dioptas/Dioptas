import { preparePatternBaseline } from "./pattern_benchmark_baseline.mjs";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const desktop = fileURLToPath(new URL("../", import.meta.url));
await mkdir(`${desktop}artifacts`, { recursive: true });
const cleanupBaseline = await preparePatternBaseline();
if (!process.argv.includes("--no-build")) {
  const build = spawn("npm", ["run", "tauri:build", "--", "--debug"], {
    cwd: desktop,
    stdio: "inherit",
    env: { ...process.env, VITE_DIOPTAS_PATTERN_BENCHMARK: "1" },
  });
  const code = await new Promise((resolve, reject) => {
    build.on("error", reject);
    build.on("close", resolve);
  });
  if (code) {
    await cleanupBaseline();
    throw Error(`Benchmark build exited ${code}`);
  }
}
const child = spawn(
  "target/debug/dioptas-desktop",
  ["--example", "--pattern-benchmark"],
  { cwd: desktop, stdio: ["ignore", "pipe", "pipe"] },
);
let final;
const logs = [];
for (const stream of [child.stdout, child.stderr])
  createInterface({ input: stream }).on("line", (line) => {
    logs.push(line);
    if (line.startsWith('{"tauriSmoke":')) {
      const report = JSON.parse(line).tauriSmoke;
      if (report.stage === "hmr")
        console.log(JSON.stringify(report.patternProgress));
      else final = report;
    } else console.log(line);
  });
const code = await new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", resolve);
});
await writeFile(
  `${desktop}artifacts/pattern-native.log`,
  logs.join("\n") + "\n",
);
await writeFile(
  `${desktop}artifacts/pattern-native.json`,
  JSON.stringify(final ?? { ok: false, code }, null, 2),
);
await cleanupBaseline();
if (code || !final?.ok)
  throw Error(final?.error ?? `Native benchmark exited ${code}`);
console.log("Native pattern benchmark complete");
