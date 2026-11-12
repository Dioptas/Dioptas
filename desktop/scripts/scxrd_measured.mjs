import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { nativeClient, root } from "./native_backend_client.mjs";
const source = process.env.DIOPTAS_SCXRD_MEASURED_DIR;
if (!source)
  throw new Error(
    "Set DIOPTAS_SCXRD_MEASURED_DIR to the MgSiO3 Eiger example directory.",
  );
const folder = path.join(root, "desktop/artifacts/scxrd-measured");
await fs.mkdir(folder, { recursive: true });
const native = nativeClient();
let receipt = [];
async function call(action, payload = {}) {
  let t = performance.now();
  let r = await native.invoke(action, payload);
  receipt.push({
    action,
    payload,
    seconds: (performance.now() - t) / 1000,
    ok: r.ok,
    error: r.error,
    stages: r.scxrd?.stages,
    frames: r.scxrd?.frames,
    shape: r.scxrd?.shape,
    peaks: r.scxrd?.peakCount,
    tracks: r.scxrd?.trackCount,
    cells: r.scxrd?.cells,
    pause: r.scxrd?.error,
    geometry: r.scxrd?.geometryReport,
    usable: r.scxrd?.usableReflections,
  });
  await fs.writeFile(
    path.join(folder, "receipt.json"),
    JSON.stringify(receipt, null, 2),
  );
  assert.equal(r.ok, true, r.error);
  return r;
}
try {
  let r = await call("scxrd_load", {
    path: path.join(source, "eiger_0000.h5"),
  });
  await call("scxrd_file", {
    operation: "calibration",
    path: path.join(source, "CeO2_20240620_1849_dioptas.poni"),
  });
  await call("scxrd_edit", { operation: "frame", index: 0 });
  await call("scxrd_edit", { operation: "frame", index: 1 });
  await call("scxrd_settings", {
    config: {
      ...r.scxrd.config,
      omega_start: -36,
      omega_step: 0.5,
      exposure: 0.5,
      axis: [-1, 0, 0],
      background: false,
      confirmed: true,
    },
  });
  r = await call("scxrd_run", { stage: 2, automatic: false });
  await fs.writeFile(
    path.join(folder, "cell-stage.json"),
    JSON.stringify(r.scxrd, null, 2),
  );
  console.log(
    "blind cells",
    r.scxrd.cells.length,
    r.scxrd.cells[0]?.parameters,
  );
  if (r.scxrd.cells.length) {
    await call("scxrd_edit", { operation: "cell", index: 0 });
    await call("scxrd_settings", {
      config: {
        ...r.scxrd.config,
        metric: [8.8101, 5.1824, 18.2288, 90, 90, 90],
        refine_geometry: true,
        group: 61,
      },
    });
    r = await call("scxrd_run", { stage: 5 });
    await fs.writeFile(
      path.join(folder, "processed.json"),
      JSON.stringify(r.scxrd, null, 2),
    );
    await call("scxrd_file", {
      operation: "save",
      path: path.join(folder, "measured.scxrd.json"),
    });
  }
  console.log(JSON.stringify(receipt.at(-2), null, 2));
} finally {
  await native.close();
}
