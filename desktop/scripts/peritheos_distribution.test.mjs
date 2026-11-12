import assert from "node:assert/strict";
import { cp, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  assertEosOnly,
  verifyPeritheosResources,
} from "./peritheos_distribution.mjs";

const catalog = fileURLToPath(
  new URL("../backend/resources/peritheos", import.meta.url),
);

test("the embedded and staged catalog contains 234 materials and all 685 EOS records without experimental payloads", async () => {
  const receipt = await verifyPeritheosResources(catalog);
  assert.equal(receipt.materials, 234);
  assert.equal(receipt.eos_records, 685);
});

test("experimental tables are rejected at any depth, including empty dataset descriptors", () => {
  for (const payload of [
    { datasets: [] },
    { rows: [{ pressure: 12, volume: 4 }] },
    { source_equation: {} },
    { observations: [1, 2] },
  ]) {
    assert.throws(
      () => assertEosOnly({ eos_records: [{ evidence: payload }] }),
      /Peritheos/,
    );
  }
  assert.doesNotThrow(() =>
    assertEosOnly({
      parameters: { K0: 160 },
      reference: "Source",
      observations: 12,
      validity: { pressure_gpa: [0, 100] },
    }),
  );
});

test("packaging rejects an unexpected Peritheos data file", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "dioptas-eos-only-"));
  try {
    await cp(catalog, root, { recursive: true });
    await writeFile(path.join(root, "observations.csv"), "P,V\n1,2\n");
    await assert.rejects(
      verifyPeritheosResources(root),
      /Unexpected Peritheos distribution file/,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
