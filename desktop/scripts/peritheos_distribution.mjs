import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const policy = JSON.parse(
  await readFile(
    new URL("./peritheos_distribution_policy.json", import.meta.url),
    "utf8",
  ),
);

export function assertEosOnly(value, location = "catalog") {
  if (Array.isArray(value)) {
    value.forEach((item, index) =>
      assertEosOnly(item, `${location}[${index}]`),
    );
  } else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      assert(
        !policy.omitFields.includes(key),
        `Excluded Peritheos field: ${location}.${key}`,
      );
      assert(
        !(
          policy.omitCollections.includes(key) &&
          item !== null &&
          typeof item === "object"
        ),
        `Experimental Peritheos payload: ${location}.${key}`,
      );
      assertEosOnly(item, `${location}.${key}`);
    }
  }
}

// The same checked catalog is include_str!-embedded by the processor and staged
// as a resource. Fail before compilation and inspect the installed copy again.
export async function verifyPeritheosResources(directory) {
  assert.deepEqual(
    (await readdir(directory)).sort(),
    ["LICENSE", "SOURCE.json", "materials.json", "record-display.json"].sort(),
    "Unexpected Peritheos distribution file",
  );
  const bytes = await readFile(path.join(directory, "materials.json"));
  const materials = JSON.parse(bytes);
  const source = JSON.parse(
    await readFile(path.join(directory, "SOURCE.json"), "utf8"),
  );
  const display = JSON.parse(
    await readFile(path.join(directory, "record-display.json"), "utf8"),
  );
  assertEosOnly(materials);
  assertEosOnly(display);
  const receipt = {
    policy: policy.id,
    catalog_sha256: createHash("sha256").update(bytes).digest("hex"),
    materials: materials.length,
    eos_records: materials.reduce(
      (count, material) => count + material.eos_records.length,
      0,
    ),
  };
  assert.deepEqual(
    source.distribution,
    receipt,
    "Peritheos distribution provenance differs",
  );
  assert.equal(Object.keys(display).length, receipt.eos_records);
  return receipt;
}
