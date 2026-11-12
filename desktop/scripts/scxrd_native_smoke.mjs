import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/scxrd-native");
await fs.mkdir(artifacts, { recursive: true });
const fixture = path.join(root, "desktop/artifacts/scxrd-fixture");
const paths = (await fs.readdir(fixture))
  .filter((p) => p.endsWith(".tif"))
  .sort()
  .map((p) => path.join(fixture, p));
const native = nativeClient();
const receipts = [];
async function invoke(action, payload = {}) {
  const start = performance.now();
  const r = await native.invoke(action, payload);
  receipts.push({
    action,
    seconds: (performance.now() - start) / 1000,
    ok: r.ok,
    error: r.error,
    stages: r.scxrd?.stages,
    peakCount: r.scxrd?.peakCount,
    trackCount: r.scxrd?.trackCount,
    cells: r.scxrd?.cells,
    reflectionCount: r.scxrd?.reflectionCount,
    geometryReport: r.scxrd?.geometryReport,
    pause: r.scxrd?.error,
  });
  await fs.writeFile(
    path.join(artifacts, "receipts.json"),
    JSON.stringify(receipts, null, 2),
  );
  assert.equal(r.ok, true, `${action}: ${r.error}`);
  return r;
}
async function allData(scxrd) {
  const tracks = [],
    reflections = [];
  for (let offset = 0; offset < scxrd.trackCount; offset += 200)
    tracks.push(
      ...(await invoke("scxrd_table", { kind: "tracks", offset })).scxrd.tracks,
    );
  for (let offset = 0; offset < scxrd.reflectionCount; offset += 200)
    reflections.push(
      ...(await invoke("scxrd_table", { kind: "reflections", offset })).scxrd
        .reflections,
    );
  return { ...scxrd, tracks, reflections };
}
try {
  assert.equal((await invoke("__host__")).runtime, "rust");
  await invoke("open_image", {
    path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
  });
  await invoke("open_calibration", {
    path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
  });
  await invoke("integration_settings", { bins: 128, cake_bins: 36 });
  const powderBefore = await invoke("state");

  let r = await invoke("scxrd_load", { paths });
  assert.equal(r.scxrd.frames, 161);
  assert.equal(r.scxrd.config.confirmed, false);
  await invoke("scxrd_file", {
    operation: "calibration",
    path: path.join(fixture, "detector.poni"),
  });
  let config = {
    ...r.scxrd.config,
    omega_start: -40,
    omega_step: 0.5,
    exposure: 0.5,
    confirmed: true,
  };
  await invoke("scxrd_settings", { config });
  r = await invoke("scxrd_run", { stage: 4, automatic: true });
  console.log(
    "first pass",
    r.scxrd.stages.map((s) => s.status),
    r.scxrd.error,
    "tracks",
    r.scxrd.trackCount,
    "cells",
    r.scxrd.cells.length,
  );
  assert.ok(r.scxrd.cells.length > 0, `Cell search failed: ${r.scxrd.error}`);
  const cell = r.scxrd.cells.findIndex((c) =>
    c.parameters
      .slice(0, 3)
      .sort((a, b) => a - b)
      .every((v, i) => Math.abs(v - [7, 9, 11][i]) < 0.03),
  );
  assert.ok(cell >= 0, "Known 7×9×11 Å cell recovered");
  await invoke("scxrd_edit", { operation: "cell", index: cell });
  r = await invoke("scxrd_run", { stage: 5 });
  assert.equal(r.scxrd.error, null);
  assert.ok(r.scxrd.usableReflections > 25);
  r.scxrd = await allData(r.scxrd);
  await fs.writeFile(
    path.join(artifacts, "completed.json"),
    JSON.stringify(r.scxrd, null, 2),
  );
  const recoveredCell = r.scxrd.cells[cell].parameters;
  const rawObservations = new Map(
    r.scxrd.reflections
      .filter((row) => row.flags === 0)
      .map((row) => [
        row.track,
        [row.intensity / row.correction, row.sigma / row.correction],
      ]),
  );
  const reflectionHash = JSON.stringify(r.scxrd.reflections);
  const recipe = path.join(artifacts, "synthetic.scxrd.json");
  await invoke("scxrd_file", { operation: "save", path: recipe });
  await invoke("scxrd_file", {
    operation: "hkl",
    path: path.join(artifacts, "synthetic.hkl"),
  });
  await invoke("scxrd_file", {
    operation: "reflections",
    path: path.join(artifacts, "synthetic.txt"),
  });
  r = await invoke("scxrd_file", { operation: "open", path: recipe });
  r = await invoke("scxrd_run", { stage: 5 });
  r.scxrd = await allData(r.scxrd);
  assert.equal(
    JSON.stringify(r.scxrd.reflections),
    reflectionHash,
    "Same-engine recipe replay exactly reproduces observations",
  );
  const before = await invoke("state");
  await invoke("scxrd_frame", { frame: 90 });
  const after = await invoke("state");
  assert.deepEqual(after.state.geometry, before.state.geometry);
  assert.equal(after.state.imagePath, before.state.imagePath);
  assert.deepEqual(
    after.pattern,
    powderBefore.pattern,
    "Existing powder pattern retained",
  );
  assert.equal(
    after.image?.bufferId,
    powderBefore.image?.bufferId,
    "Existing detector image retained",
  );
  const peakCount = r.scxrd.peakCount;
  await invoke("scxrd_settings", { config: { ...config, adp: "anisotropic" } });
  r = await invoke("scxrd_snapshot");
  assert.equal(r.scxrd.peakCount, peakCount);
  assert.equal(r.scxrd.stages[4].status, "complete");
  await invoke("scxrd_settings", { config: { ...config, background: false } });
  r = await invoke("scxrd_run", { stage: 5, automatic: true });
  assert.equal(r.scxrd.error, null);
  const withoutBackground = await allData(r.scxrd);
  let compared = 0,
    maxRelativeDifference = 0;
  for (const row of withoutBackground.reflections.filter(
    (row) => row.flags === 0,
  )) {
    const original = rawObservations.get(row.track);
    if (!original) continue;
    for (const [i, value] of [
      row.intensity / row.correction,
      row.sigma / row.correction,
    ].entries())
      maxRelativeDifference = Math.max(
        maxRelativeDifference,
        Math.abs(value - original[i]) / Math.max(1, Math.abs(original[i])),
      );
    compared++;
  }
  assert.ok(compared > 200);
  assert.ok(
    maxRelativeDifference < 1e-12,
    `Position background must not change original-count I or sigma on matching supports: ${maxRelativeDifference}`,
  );
  await fs.writeFile(
    path.join(artifacts, "background-independence.json"),
    JSON.stringify(
      {
        compared,
        maxRelativeDifference,
        description:
          "Background-on/off runs compared by stable measured track identities; original-count I and sigma before physical factors, same declared integration support.",
      },
      null,
      2,
    ),
  );
  await invoke("scxrd_file", { operation: "open", path: recipe });
  await invoke("scxrd_run", { stage: 5 });
  r = await invoke("scxrd_snapshot");
  await invoke("scxrd_settings", {
    config: { ...r.scxrd.config, elements: "Si", search_seconds: 2 },
  });
  const search = await invoke("scxrd_run", { stage: 6 });
  assert.equal(search.scxrd.stages[6].status, "complete", search.scxrd.error);
  assert.ok(Number.isFinite(search.scxrd.structure.r1));
  await invoke("scxrd_file", {
    operation: "cif",
    path: path.join(artifacts, "synthetic-candidate.cif"),
  });
  assert.match(
    await fs.readFile(path.join(artifacts, "synthetic-candidate.cif"), "utf8"),
    /data_dioptas_candidate/,
  );
  await fs.writeFile(
    path.join(artifacts, "candidate-search.json"),
    JSON.stringify(
      {
        description:
          "Interface/engine operability only: this synthetic photon fixture does not encode an atomic structure.",
        structure: search.scxrd.structure,
      },
      null,
      2,
    ),
  );
  await invoke("scxrd_settings", { config: { ...config, threshold: 6 } });
  r = await invoke("scxrd_snapshot");
  assert.equal(r.scxrd.stages[0].status, "complete");
  assert.equal(r.scxrd.stages[1].status, "pending");
  assert.equal(r.scxrd.reflectionCount, 0);
  console.log(
    JSON.stringify(
      {
        ok: true,
        recoveredCell,
        backgroundVarianceIndependence: true,
        independentFixture: true,
        exactReplay: true,
        powderSessionPreserved: true,
        dependencyInvalidation: true,
        candidateSearchAndCif: true,
      },
      null,
      2,
    ),
  );
} finally {
  native.close();
}
