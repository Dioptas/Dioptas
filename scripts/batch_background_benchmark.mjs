// Measure a complete pattern-background update through the real Rust stdio
// transport. Input matrices and optional saved output stay outside receipts.
// Usage: node scripts/batch_background_benchmark.mjs input.h5 parameters.json receipt.json [result.h5]
// DIOPTAS_NATIVE_PROCESSOR selects an independently built baseline executable.
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
const native = nativeClient();
const call = async (action, payload = {}) => {
  const result = await native.invoke(action, payload);
  assert.equal(result.ok, true, `${action}: ${result.error}`);
  return result;
};
try {
  const opened = await call("batch_open", { path: path.resolve(input) });
  await call("integration_background", { ...parameters, enabled: false });
  const milliseconds = [];
  for (let run = 0; run < 3; run++) {
    const start = performance.now();
    await call(
      run === 0 ? "integration_background" : "batch_background_from_pattern",
      run === 0 ? { ...parameters, enabled: true } : {},
    );
    milliseconds.push(performance.now() - start);
  }
  if (output)
    await call("integration_save_batch", { path: path.resolve(output) });
  const result = {
    frames: opened.batch.raster.height,
    bins: opened.batch.x.length,
    parameters,
    milliseconds,
  };
  await fs.writeFile(receipt, `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify(result));
} finally {
  await native.close();
}
