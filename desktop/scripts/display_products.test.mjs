import assert from "node:assert/strict";
import { test } from "node:test";
import {
  requestedDisplayProducts,
  wantsCake,
  withRequestedProducts,
} from "../src/displayProducts.ts";

test("cake demand follows the displayed view, with explicit combination support", () => {
  const view = {
    mode: "integration",
    display: "image",
    calibrationStep: 0,
    concealed: false,
    combinedCake: false,
  };
  for (const mode of ["map", "mask", "calibration", "integration"])
    assert.equal(wantsCake({ ...view, mode }), false);
  assert.equal(wantsCake({ ...view, display: "cake" }), true);
  assert.equal(wantsCake({ ...view, mode: "map", display: "cake" }), false);
  assert.equal(
    wantsCake({ ...view, mode: "calibration", calibrationStep: 3 }),
    true,
  );
  assert.equal(wantsCake({ ...view, display: "cake", concealed: true }), false);
  assert.equal(wantsCake({ ...view, combinedCake: true }), true);
  assert.deepEqual(requestedDisplayProducts({ ...view, showRings: true }), {
    cake: false,
    rings: false,
  });
  assert.deepEqual(
    requestedDisplayProducts({ ...view, mode: "calibration", showRings: true }),
    { cake: false, rings: true },
  );
});
test("one request wrapper covers every browsing entry point and explicit cake exports", async () => {
  const seen = [];
  let visible = false;
  const invoke = withRequestedProducts(
    async (action, payload) => {
      seen.push({ action, payload });
      return { ok: true };
    },
    () => ({ cake: visible, rings: false }),
  );
  for (const action of [
    "open_image",
    "next_image",
    "batch_select",
    "map_select",
    "integration_settings",
    "mask_edit",
    "open_project",
  ])
    await invoke(action, { index: 1 });
  assert.ok(seen.every((r) => r.payload.requested_products.cake === false));
  visible = true;
  await invoke("batch_select", { index: 2 });
  assert.equal(seen.at(-1).payload.requested_products.cake, true);
  visible = false;
  await invoke("integration_save_image", {
    source: "cake",
    path: "result.csv",
  });
  assert.equal(seen.at(-1).payload.requested_products.cake, true);
  await invoke("display_products", { cake: true });
  assert.equal(seen.at(-1).payload.requested_products.cake, true);
});
