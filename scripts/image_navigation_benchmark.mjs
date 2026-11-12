// Optional local benchmark of the real Rust binary protocol. No Python,
// browser/base64 adapter, or scientific approximations enter these timings.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  copyFile,
  mkdir,
  mkdtemp,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index < 0 ? fallback : args[index + 1];
};
const baseline = option("--baseline", null);
const processor = option(
  "--processor",
  path.join(root, "backend/target/debug/dioptas-processor"),
);
const output = option(
  "--output",
  path.join(root, "artifacts/image-navigation/native.json"),
);
const eiger = option("--eiger", null);
const repetitions = Number(option("--repetitions", "12"));
const median = (values) =>
  [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const summary = (values) => ({
  medianMs: median(values),
  minMs: Math.min(...values),
  maxMs: Math.max(...values),
  samples: values.length,
});
const temp = await mkdtemp(
  path.join(tmpdir(), "dioptas-navigation-benchmark-"),
);
const report = {
  scope:
    "Warm local filesystem; real Rust stdio response including image, pattern and cake; no OS compositor/physical-display latency; processes not CPU isolated",
  runs: {},
};
const science = {};
process.env.DIOPTAS_TRACE_FRAME = "1";
try {
  for (const folder of ["small", "large"]) {
    const dir = path.join(temp, folder);
    await mkdir(dir);
    if (folder === "large")
      for (let i = 0; i < 2000; i++)
        await writeFile(
          path.join(dir, `earlier_${String(i).padStart(5, "0")}.tif`),
          "",
        );
    for (const i of ["001", "002"])
      await copyFile(
        path.join(root, `tests/data/image_${i}.tif`),
        path.join(dir, `image_${i}.tif`),
      );
  }
  const cases = [
    {
      name: "tiff-4mp-uncalibrated",
      calibrated: false,
      folder: "small",
      mode: "number",
    },
    {
      name: "tiff-4mp-calibrated",
      calibrated: true,
      folder: "small",
      mode: "number",
    },
    {
      name: "tiff-4mp-time-2002-files",
      calibrated: true,
      folder: "large",
      mode: "time",
    },
    ...(eiger && (await stat(eiger).catch(() => null))
      ? [
          { name: "eiger-9mp-uncalibrated", calibrated: false, eiger: true },
          { name: "eiger-9mp-calibrated", calibrated: true, eiger: true },
        ]
      : []),
  ];
  if (args.includes("--all-paths"))
    for (const source of [
      { prefix: "tiff-4mp", folder: "small" },
      ...(eiger && (await stat(eiger).catch(() => null))
        ? [{ prefix: "eiger-9mp", eiger: true }]
        : []),
    ])
      for (const selection of [
        "batch",
        "map-stored",
        "map-reintegrated",
        "map-integration",
      ])
        cases.push({
          ...source,
          name: `${source.prefix}-${selection}`,
          calibrated: true,
          selection,
        });
  for (const [label, executable] of [
    ...(baseline ? [["before", baseline]] : []),
    ["after", processor],
  ]) {
    report.runs[label] = {};
    science[label] = {};
    for (const scenario of cases) {
      const native = nativeClient({ executable: path.resolve(executable) });
      let id = 0;
      const call = async (action, payload = {}) => {
        id++;
        const start = performance.now();
        const result = await native.invoke(action, payload);
        const ms = performance.now() - start;
        assert.equal(result.ok, true, `${action}: ${result.error}`);
        return { result, ms, id };
      };
      const stable = (value) => {
        if (Array.isArray(value)) return value.map(stable);
        if (!value || typeof value !== "object") return value;
        return Object.fromEntries(
          Object.entries(value)
            .filter(([key]) => key !== "elapsedMs")
            .map(([key, item]) => [key, stable(item)]),
        );
      };
      const signature = (result) => ({
        metadata: stable(result),
        pixels: Object.fromEntries(
          ["image", "rawImage", "mask", "cake"]
            .filter((key) => result[key]?.bufferId)
            .map((key) => [
              key,
              createHash("sha256")
                .update(native.buffers.get(result[key].bufferId))
                .digest("hex"),
            ]),
        ),
      });
      try {
        await call("integration_settings", { bins: 1000, cake_bins: 360 });
        await call("open_image", {
          path: scenario.eiger
            ? eiger
            : path.join(temp, scenario.folder, "image_001.tif"),
        });
        if (scenario.calibrated)
          await call("open_calibration", {
            path: scenario.eiger
              ? eiger.replace(/\.h5$/, ".poni")
              : path.join(root, "tests/data/LaB6_40keV_MarCCD.poni"),
          });
        if (scenario.mode)
          await call("integration_navigation", { mode: scenario.mode });
        if (scenario.selection) {
          await call("batch_load", {
            paths: scenario.eiger
              ? [eiger]
              : ["001", "002"].map((i) =>
                  path.join(temp, scenario.folder, `image_${i}.tif`),
                ),
            start: 1,
            stop: 2,
          });
          if (scenario.selection !== "batch") {
            const path = `${temp}/${scenario.name}.h5`;
            await call("integration_save_batch", { path });
            await call("map_batch", { path });
          }
        }
        const select = (direction) =>
          scenario.selection
            ? call(
                scenario.selection === "batch" ? "batch_select" : "map_select",
                {
                  index: direction > 0 ? 1 : 0,
                  ...(scenario.selection === "batch"
                    ? {}
                    : {
                        reintegrate: scenario.selection === "map-reintegrated",
                        integration_view:
                          scenario.selection === "map-integration",
                      }),
                },
              )
            : call("next_image", { direction });
        await select(1);
        await select(-1);
        await new Promise((resolve) => setTimeout(resolve, 20));
        native.diagnostics.length = 0;
        const rows = [];
        science[label][scenario.name] = [];
        for (let i = 0; i < repetitions; i++) {
          const direction = i % 2 === 0 ? 1 : -1;
          const { result, ms, id } = await select(direction);
          rows.push({ direction, ms, id });
          science[label][scenario.name].push(signature(result));
        }
        const diagnostics = (await call("integration_diagnostics")).result
          .integrationDiagnostics;
        const boundary = [];
        if (!scenario.eiger && scenario.mode === "number") {
          for (let i = 0; i < repetitions; i++) {
            const { result, ms } = await call("next_image", { direction: -1 });
            assert.equal(result.imageUnavailable, true);
            boundary.push(ms);
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 20));
        const ids = new Set(rows.map((row) => row.id));
        const stages = {};
        for (const line of native.diagnostics
          .join("")
          .split("\n")
          .filter((line) => line.startsWith("DIOPTAS_TRACE "))) {
          const trace = JSON.parse(line.slice("DIOPTAS_TRACE ".length));
          if (trace.stage === "packet" && !ids.has(trace.id)) continue;
          for (const [name, ms] of trace.steps) {
            const key = `${trace.stage}${trace.stage === "raster" ? `[${trace.id} pixels]` : ""}: ${name}`;
            (stages[key] ??= []).push(ms);
          }
        }
        const measured = {
          ...summary(rows.map((row) => row.ms)),
          rows,
          stages: Object.fromEntries(
            Object.entries(stages).map(([key, values]) => [
              key,
              summary(values),
            ]),
          ),
          diagnostics,
          ...(boundary.length ? { boundary: summary(boundary) } : {}),
        };
        report.runs[label][scenario.name] = measured;
        console.log(label, scenario.name, measured.medianMs.toFixed(2), "ms");
      } finally {
        await native.close();
      }
    }
  }
  const differences = [];
  const displayLimitRounding = [];
  if (baseline) {
    const compare = (after, before, key = "") => {
      if (Object.is(after, before) || differences.length >= 8) return;
      if (
        /\/metadata\/(image|rawImage|cake)\/limits\/[01]$/.test(key) &&
        typeof after === "number" &&
        typeof before === "number" &&
        Math.abs(after - before) <=
          4 * Number.EPSILON * Math.max(1, Math.abs(before))
      ) {
        displayLimitRounding.push({ key, before, after });
        return;
      }
      if (
        after &&
        before &&
        typeof after === "object" &&
        typeof before === "object"
      ) {
        for (const field of new Set([
          ...Object.keys(after),
          ...Object.keys(before),
        ]))
          compare(after[field], before[field], `${key}/${field}`);
      } else differences.push({ key, before, after });
    };
    compare(science.after, science.before);
    report.science = {
      exactResponseMetadataExceptElapsedMsAndDisplayLimits:
        differences.length === 0,
      exactDetectorMaskAndCakeBytes: differences.every(
        ({ key }) => !key.includes("/pixels/"),
      ),
      exactPatternsAndHistograms: differences.every(
        ({ key }) => !key.includes("/pattern/") && !key.includes("/histogram/"),
      ),
      displayLimitToleranceRelative: 4 * Number.EPSILON,
      displayLimitRounding,
      firstDifferences: differences,
    };
  }
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(report, null, 2) + "\n");
  console.log(output);
  assert.deepEqual(
    differences,
    [],
    "Output comparison failed; inspect the receipt for differing fields",
  );
} finally {
  await rm(temp, { recursive: true, force: true });
}
