import test from "node:test";
import assert from "node:assert/strict";
import {
  batchExportBaseName,
  isBatchMultifile,
} from "../src/batchExportNaming.ts";
test("export defaults follow processed file names or raw-series prefixes", () => {
  const files = ["sample_0001.tif", "sample_0002.tif"].map((name) => ({
    name,
    path: `/data/${name}`,
  }));
  assert.equal(
    batchExportBaseName({ exportBaseName: "MgO_processed_042", files }),
    "MgO_processed_042",
  );
  assert.equal(batchExportBaseName({ files }), "sample");
  assert.equal(batchExportBaseName({ files: [files[0]] }), "sample_0001");
  assert.equal(
    batchExportBaseName({ files: [{ name: "", path: "/data/run.2026.nxs" }] }),
    "run.2026",
  );
  assert.equal(batchExportBaseName(null), "batch");
  assert.equal(isBatchMultifile("fxye"), true);
  assert.equal(isBatchMultifile("h5"), false);
});
