// Local-data regression: same native profile recipe as standalone PhaseSmith.
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { nativeClient } from "./native_backend_client.mjs";
const source = process.env.DIOPTAS_SCXRD_MEASURED_DIR;
const folder = process.argv[2];
if (!source || !folder)
  throw Error(
    "Set DIOPTAS_SCXRD_MEASURED_DIR and supply a NEW output directory.",
  );
await fs.mkdir(folder);
const native = nativeClient({ timeoutMs: 600000 });
const receipt = [];
async function call(action, payload = {}) {
  const t = performance.now();
  const r = await native.invoke(action, payload);
  receipt.push({
    action,
    payload,
    seconds: (performance.now() - t) / 1000,
    ok: r.ok,
    error: r.error,
    stages: r.scxrd?.stages,
  });
  await fs.writeFile(
    path.join(folder, "receipt.json"),
    JSON.stringify(receipt, null, 2),
  );
  assert.equal(r.ok, true, r.error);
  return r;
}
try {
  assert.equal((await call("__host__")).runtime, "rust");
  const loaded = await call("scxrd_load", {
    path: path.join(source, "eiger_0000.h5"),
  });
  await call("scxrd_file", {
    operation: "calibration",
    path: path.join(source, "CeO2_20240620_1849_dioptas.poni"),
  });
  const applied = await call("scxrd_file", {
    operation: "protocol",
    path:
      process.env.DIOPTAS_SCXRD_PROTOCOL ??
      fileURLToPath(
        new URL("../backend/data/scxrd-protocol-v29.json", import.meta.url),
      ),
  });
  const config = {
    ...applied.scxrd.config,
    confirmed: true,
    metric: [8.8101, 5.1824, 18.2288, 90, 90, 90],
    group: 61,
    elements: "Mg Si O",
    keep_stage_audit: true,
  };
  await fs.writeFile(
    path.join(folder, "frozen-config.json"),
    JSON.stringify(config, null, 2),
  );
  await call("scxrd_settings", { config });
  if (process.env.DIOPTAS_SCXRD_STEPWISE === "1") {
    for (const stage of [0, 1, 2, 3]) {
      const checkpoint = await call("scxrd_run", { stage });
      assert.equal(checkpoint.scxrd.error, null, checkpoint.scxrd.error);
      await fs.writeFile(
        path.join(folder, `checkpoint-${stage}.json`),
        JSON.stringify(checkpoint.scxrd, null, 2),
      );
      await call("scxrd_file", {
        operation: "audit",
        path: path.join(folder, `checkpoint-${stage}.npz`),
      });
    }
  }
  const result = await call("scxrd_run", { stage: 5 });
  assert.equal(result.scxrd.error, null, result.scxrd.error);
  const rows = [];
  for (let offset = 0; offset < result.scxrd.reflectionCount; offset += 200)
    rows.push(
      ...(await call("scxrd_table", { kind: "reflections", offset })).scxrd
        .reflections,
    );
  await fs.writeFile(
    path.join(folder, "reduction.json"),
    JSON.stringify({ ...result.scxrd, reflections: rows }, null, 2),
  );
  await call("scxrd_file", {
    operation: "save",
    path: path.join(folder, "matched.scxrd.json"),
  });
  await call("scxrd_file", {
    operation: "reflections",
    path: path.join(folder, "observations.txt"),
  });
  await call("scxrd_file", {
    operation: "audit",
    path: path.join(folder, "stages.npz"),
  });
  await call("scxrd_file", {
    operation: "protocol_save",
    path: path.join(folder, "effective-protocol.json"),
  });
  await call("scxrd_file", {
    operation: "hkl",
    path: path.join(folder, "observations.hkl"),
  });
  console.log(
    JSON.stringify(
      {
        rows: rows.length,
        usable: result.scxrd.usableReflections,
        scaling: result.scxrd.scaling,
        shadows: result.scxrd.shadows,
      },
      null,
      2,
    ),
  );
} finally {
  await native.close();
}
