import assert from "node:assert/strict";
import test from "node:test";
import { applicationWindowTitle } from "../src/windowTitle.ts";

test("the version stays first with no image, loaded files and companion windows", () => {
  for (const context of [
    undefined,
    null,
    "",
    "eiger_0000.h5",
    "Phase Editor — MgO",
    "Map",
    "Batch",
    "Detector",
  ]) {
    const title = applicationWindowTitle("0.14.0-rc.1", context);
    assert(title.startsWith("Dioptas 0.14.0-rc.1"));
    if (context) assert(title.endsWith(` — ${context}`));
    else assert.equal(title, "Dioptas 0.14.0-rc.1");
  }
  assert.equal(
    applicationWindowTitle("0.14.0-rc.2", "example.tif", "Live preview"),
    "Dioptas 0.14.0-rc.2 — example.tif · Live preview",
  );
});
