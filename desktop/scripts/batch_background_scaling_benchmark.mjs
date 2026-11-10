// Full automatic-background commands, measured sequentially across worker counts.
// Usage: node scripts/batch_background_scaling_benchmark.mjs input.h5 parameters.json receipt.json [private-output-directory]
// DIOPTAS_BACKGROUND_BENCHMARK_WORKERS=1,3,4,6,8,10,12,13,14
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { nativeClient } from "./native_backend_client.mjs";

const [input, parametersFile, receipt, output] = process.argv.slice(2);
assert.ok(
  input && parametersFile && receipt,
  "Expected input, parameters and receipt paths",
);
const parameters = JSON.parse(await fs.readFile(parametersFile, "utf8"));
const counts = (
  process.env.DIOPTAS_BACKGROUND_BENCHMARK_WORKERS ?? "1,3,4,6,8,10,12,13,14"
)
  .split(",")
  .map(Number);
assert.ok(counts.every((n) => Number.isInteger(n) && n > 0));
const clients = new Map();
const results = counts.map((workers) => ({ workers, milliseconds: [] }));
let dimensions;
const call = async (native, action, payload = {}) => {
  const result = await native.invoke(action, payload);
  assert.equal(result.ok, true, `${action}: ${result.error}`);
  return result;
};
try {
  if (output) await fs.mkdir(output, { recursive: true });
  for (const workers of counts) {
    const native = nativeClient();
    clients.set(workers, native);
    const opened = await call(native, "batch_open", {
      path: path.resolve(input),
    });
    dimensions = {
      frames: opened.batch.raster.height,
      bins: opened.batch.x.length,
    };
    const selected = await call(native, "processing_workers", { workers });
    assert.equal(selected.state.processingWorkers.effective, workers);
    // One complete untimed fit initializes each worker pool and fit path.
    await call(native, "integration_background", {
      ...parameters,
      enabled: true,
    });
  }
  // Alternate direction to reduce systematic drift from run order. No measured
  // command overlaps another command or another worker-count configuration.
  for (let round = 0; round < 5; round++) {
    for (const workers of round % 2 ? counts.toReversed() : counts) {
      const start = performance.now();
      await call(clients.get(workers), "batch_background_from_pattern");
      results
        .find((r) => r.workers === workers)
        .milliseconds.push(performance.now() - start);
    }
  }
  for (const result of results) {
    const sorted = result.milliseconds.toSorted((a, b) => a - b);
    result.medianMilliseconds = sorted[Math.floor(sorted.length / 2)];
    if (output)
      await call(clients.get(result.workers), "integration_save_batch", {
        path: path.resolve(output, `workers-${result.workers}.h5`),
      });
  }
  const report = {
    ...dimensions,
    parameters,
    rounds: 5,
    untimedFitsPerCount: 1,
    order: "ascending/descending alternating",
    results,
  };
  await fs.writeFile(receipt, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report));
} finally {
  for (const native of clients.values()) await native.close();
}
