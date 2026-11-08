// Optional local 9M benchmark. Scientific packets use the real Rust binary
// protocol; no browser/base64 adapter is included in the measured interval.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";
const args = process.argv.slice(2);
const value = (name, fallback) => {
  const i = args.indexOf(name);
  return i < 0 ? fallback : args[i + 1];
};
const folder = value("--data", "/Users/clemens/Programming/Dioptrin/test_data");
const baseline = value("--baseline", null);
const current = value(
  "--processor",
  path.join(root, "desktop/backend/target/release/dioptas-processor"),
);
const receipt = {};
const science = {};
for (const [label, executable] of [
  ...(baseline ? [["before", baseline]] : []),
  ["after", current],
]) {
  process.env.DIOPTAS_NATIVE_PROCESSOR = path.resolve(executable);
  if (args.includes("--trace")) process.env.DIOPTAS_TRACE_FRAME = "1";
  else delete process.env.DIOPTAS_TRACE_FRAME;
  const n = nativeClient();
  let requestId = 0;
  const invoke = async (a, p = {}) => {
    const id = ++requestId;
    const start = performance.now();
    const r = await n.invoke(a, p);
    assert.equal(r.ok, true, `${a}: ${r.error}`);
    return { r, ms: performance.now() - start, id };
  };
  try {
    await invoke("integration_settings", {
      bins: 2000,
      cake_bins: 90,
      trim_zeros: false,
    });
    await invoke("open_image", { path: path.join(folder, "eiger_0000.h5") });
    await invoke("open_calibration", {
      path: path.join(folder, "eiger_0000.poni"),
    });
    await invoke("mask_file", { path: path.join(folder, "eiger_0000.mask") });
    await invoke("map_load", { paths: [path.join(folder, "eiger_0000.h5")] });
    const firstGuide = await invoke("validation_position", {
      source: "cake",
      x: 5,
      azimuth: 15,
    });
    n.diagnostics.length = 0;
    const rows = [];
    science[label] = [];
    for (const reintegrate of [false, true])
      for (const index of reintegrate
        ? [12, 202, 390, 604]
        : [11, 201, 389, 603]) {
        const selected = await invoke("map_select", { index, reintegrate });
        // Same policy as the frontend's restoreMapPosition: a valid retained
        // inspection needs no second processor request.
        const linked = selected.r.linked
          ? { r: selected.r, ms: 0 }
          : await invoke("validation_position", {
              source: "cake",
              x: 5,
              azimuth: 15,
            });
        rows.push({
          index,
          requestId: selected.id,
          reintegrate,
          selectionMs: selected.ms,
          restoreInspectionMs: linked.ms,
          totalMs: selected.ms + linked.ms,
        });
        science[label].push({
          pattern: selected.r.pattern,
          // Cache IDs are opaque and may use different algorithms across builds.
          // Independently compare the actual wire bytes with the same digest.
          imageBytesSha256: createHash("sha256")
            .update(n.buffers.get(selected.r.image.bufferId))
            .digest("hex"),
          maskBytesSha256: createHash("sha256")
            .update(n.buffers.get(selected.r.mask.bufferId))
            .digest("hex"),
          histogram: selected.r.image.histogram,
          limits: selected.r.image.limits,
          linked: linked.r.linked,
        });
      }
    const median = (v) => v.sort((a, b) => a - b)[Math.floor(v.length / 2)];
    const guideRows = [];
    for (const x of [3.5, 4, 4.5, 5.5, 6, 7.5, 9, 12]) {
      const selected = await invoke("validation_position", {
        source: "cake",
        x,
        azimuth: 15,
      });
      guideRows.push({ x, ms: selected.ms });
      science[label].push({ guidePosition: x, linked: selected.r.linked });
    }
    const repeatedGuideMs = [];
    for (let i = 0; i < 4; ++i) {
      const repeated = await invoke("validation_position", {
        source: "cake",
        x: 12,
        azimuth: 15,
      });
      repeatedGuideMs.push(repeated.ms);
      science[label].push({ repeatedGuide: i, linked: repeated.r.linked });
    }
    receipt[label] = {
      rows,
      medianStoredMs: median(
        rows.filter((r) => !r.reintegrate).map((r) => r.totalMs),
      ),
      medianReintegratedMs: median(
        rows.filter((r) => r.reintegrate).map((r) => r.totalMs),
      ),
      diagnostics: (await invoke("integration_diagnostics")).r
        .integrationDiagnostics,
      guides: {
        firstRequestMs: firstGuide.ms,
        medianNewPositionMs: median(guideRows.map((r) => r.ms)),
        medianRepeatedPositionMs: median(repeatedGuideMs),
        rows: guideRows,
      },
    };
    await new Promise((resolve) => setImmediate(resolve));
    const traces = n.diagnostics
      .join("")
      .split("\n")
      .filter((line) => line.startsWith("DIOPTAS_TRACE "))
      .map((line) => JSON.parse(line.slice("DIOPTAS_TRACE ".length)));
    if (traces.length) {
      const collect = (stage, name, ids) =>
        traces
          .filter((t) => t.stage === stage && (!ids || ids.has(t.id)))
          .flatMap((t) =>
            t.steps.filter(([n]) => n === name).map(([, ms]) => ms),
          );
      const ids = new Set(rows.map((r) => r.requestId));
      receipt[label].breakdown = {};
      for (const [stage, name] of [
        ["open-image", "metadata"],
        ["open-image", "decode and warm-plan handoff"],
        ["open-image", "display preparation"],
        ["open-image", "processing masks and integration"],
        ["raster", "f32 conversion and SHA256"],
        ["raster", "f32 conversion"],
        ["raster", "SHA256 and shared storage"],
        ["raster", "buffer fingerprint and shared storage"],
        ["raster", "shared count distribution"],
        ["raster", "exact auto levels"],
        ["raster", "full pixel histogram"],
        ["packet", "encode response"],
        ["packet", "write and flush"],
      ]) {
        const values = collect(
          stage,
          name,
          stage === "packet" ? ids : undefined,
        );
        if (values.length)
          receipt[label].breakdown[name] = {
            medianMs: median(values),
            samples: values.length,
          };
      }
    }
    console.log(label, JSON.stringify(receipt[label]));
  } finally {
    await n.close();
  }
}
if (baseline) {
  assert.deepEqual(science.after, science.before);
  receipt.science = {
    exactPatternsImagesMasksHistogramsAndLinkedPositions: true,
  };
}
const output = path.join(root, "desktop/artifacts/native-map-selection");
await mkdir(output, { recursive: true });
await writeFile(
  path.join(output, "receipt.json"),
  JSON.stringify(receipt, null, 2) + "\n",
);
console.log(receipt.science ?? "Complete");
