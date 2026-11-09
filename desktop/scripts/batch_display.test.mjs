import test from "node:test";
import assert from "node:assert/strict";
import {
  batchDisplayInUnit,
  batchNormalizationRegion,
} from "../src/batchDisplay.ts";
import { batchRadialBin } from "../src/batchPlot.ts";
test("batch markers project into nonuniform ascending and descending radial axes", () => {
  assert.equal(batchRadialBin(15, [10, 20, 40]), 1);
  assert.equal(batchRadialBin(30, [40, 20, 10]), 1);
  assert.equal(batchRadialBin(10, [40, 20, 10]), 2.5);
  assert.equal(batchRadialBin(10, [10]), 0.5);
  assert.equal(batchRadialBin(50, [10, 20, 40]), null);
});
test("linked batch coordinates convert without replacing the intensity matrix or columns", () => {
  const raster = { data: new Float32Array([1, 2, 3, 4]) };
  const original = { x: [10, 20], unit: "2th_deg", wavelength: 1e-10, raster };
  const converted = batchDisplayInUnit(original, "q_A^-1");
  assert.deepEqual(
    converted.x,
    original.x.map((v) => 4 * Math.PI * Math.sin((v * Math.PI) / 360)),
  );
  assert.equal(converted.raster, raster);
  assert.deepEqual(original.x, [10, 20]);
});
test("stored reciprocal axes link without inventing a wavelength", () => {
  const original = { x: [1, 2, 3], unit: "q_A^-1", wavelength: null };
  assert.deepEqual(batchDisplayInUnit(original, "d_A").x, [
    2 * Math.PI,
    Math.PI,
    (2 * Math.PI) / 3,
  ]);
  assert.equal(batchDisplayInUnit(original, "2th_deg"), original);
});
test("unreachable angular conversion keeps all source columns and their valid axis", () => {
  const original = { x: [1, 100], unit: "q_A^-1", wavelength: 1e-10 };
  assert.equal(batchDisplayInUnit(original, "2th_deg"), original);
});

test("normalization limits follow the shown axis and keep the stored physical region", () => {
  const original = {
    unit: "d_A",
    wavelength: null,
    normalizationRegion: { minimum: 2, maximum: 4, unit: "q_A^-1" },
  };
  assert.deepEqual(batchNormalizationRegion(original), {
    minimum: Math.PI / 2,
    maximum: Math.PI,
    unit: "d_A",
  });
  assert.deepEqual(original.normalizationRegion, {
    minimum: 2,
    maximum: 4,
    unit: "q_A^-1",
  });
  assert.equal(
    batchNormalizationRegion({ ...original, unit: "2th_deg" }),
    null,
  );
});

// Protocol tests cover the asynchronous native-read/window-message ordering.
import { batchWindowUpdate, BatchWindowSync } from "../src/batchWindowState.ts";
const windowBatch = (id = "series") => ({
  id,
  selected: 0,
  pattern: { y: [1] },
  raster: { data: "matrix" },
  entries: [{ name: "one" }, { name: "two" }],
  x: [1],
});
const turn = () => new Promise(setImmediate);
test("floating selection forwards only changing fields and preserves the matrix", () => {
  const a = windowBatch(),
    b = {
      ...a,
      selected: 1,
      pattern: { y: [2] },
      position: { x: 1, unit: "2th_deg" },
    };
  const update = batchWindowUpdate(a, b, { base: 1, sequence: 2 });
  assert.equal(update.kind, "selection");
  assert.equal(update.base, 1);
  assert.equal(update.sequence, 3);
  assert.equal("raster" in update, false);
  assert.equal(
    "batch" in batchWindowUpdate(a, b, { ...update, batch: a }),
    false,
  );
  assert.equal(
    batchWindowUpdate(a, JSON.parse(JSON.stringify(b)), update).kind,
    "selection",
  );
  assert.equal("entries" in update, false);
  assert.equal(batchWindowUpdate(b, b, update).kind, "retain");
  assert.equal(
    batchWindowUpdate(b, { ...b, raster: { data: "normalized" } }, update).kind,
    "snapshot",
  );
  assert.equal(
    batchWindowUpdate(b, { ...b, futureMatrixSetting: true }, update).kind,
    "snapshot",
  );
});
test("late initial snapshot receives the newest selection without another read", async () => {
  const a = windowBatch(),
    b = { ...a, selected: 1, pattern: { y: [2] } };
  let finish,
    reads = 0;
  const displayed = [];
  const sync = new BatchWindowSync(
    () => {
      reads++;
      return new Promise((resolve) => {
        finish = resolve;
      });
    },
    (x) => displayed.push(x),
  );
  const initial = batchWindowUpdate(undefined, a, { base: 0, sequence: 0 });
  sync.receive(initial, true);
  const update = batchWindowUpdate(a, b, initial);
  sync.receive(update, true);
  sync.receive(batchWindowUpdate(b, b, update), true);
  finish(a);
  await turn();
  assert.equal(reads, 1);
  assert.equal(displayed.length, 1);
  assert.equal(displayed[0].selected, 1);
  assert.equal(displayed[0].pattern, b.pattern);
  assert.equal(displayed[0].raster, a.raster);
  sync.receive(update, true); // Delayed/duplicate event cannot roll state back.
  assert.equal(displayed.length, 1);
});
test("a replaced matrix discards an older in-flight snapshot", async () => {
  const a = windowBatch(),
    b = { ...a, raster: { data: "normalized" }, normalized: true };
  const completions = [],
    displayed = [];
  const sync = new BatchWindowSync(
    () => new Promise((resolve) => completions.push(resolve)),
    (x) => displayed.push(x),
  );
  const initial = batchWindowUpdate(undefined, a, { base: 0, sequence: 0 });
  sync.receive(initial, true);
  const replaced = batchWindowUpdate(a, b, initial);
  sync.receive(replaced, true);
  completions[0](a);
  await turn();
  assert.equal(displayed.length, 0);
  assert.equal(completions.length, 2);
  completions[1](b);
  await turn();
  assert.equal(displayed[0], b);
  sync.receive({ ...initial, sequence: initial.sequence }, true);
  assert.equal(displayed.length, 1);
});
test("clearing or closing a floating view prevents a late read from restoring it", async () => {
  for (const closing of [false, true]) {
    const a = windowBatch(),
      displayed = [];
    let finish;
    const sync = new BatchWindowSync(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
      (x) => displayed.push(x),
    );
    const initial = batchWindowUpdate(undefined, a, { base: 0, sequence: 0 });
    sync.receive(initial, true);
    if (closing) sync.dispose();
    else sync.receive(batchWindowUpdate(a, null, initial), true);
    finish(a);
    await turn();
    assert.deepEqual(displayed, closing ? [] : [null]);
  }
});
test("status changes do not read again; failed initial reads can retry", async () => {
  const a = windowBatch(),
    displayed = [];
  let reads = 0;
  const sync = new BatchWindowSync(
    async () => (++reads === 1 ? undefined : a),
    (x) => displayed.push(x),
  );
  const initial = batchWindowUpdate(undefined, a, { base: 0, sequence: 0 });
  sync.receive(initial, false);
  assert.equal(reads, 0);
  let update = batchWindowUpdate(a, a, initial);
  sync.receive(update, true);
  await turn();
  update = batchWindowUpdate(a, a, update);
  sync.receive(update, true);
  await turn();
  assert.equal(reads, 2);
  assert.equal(displayed[0], a);
  sync.receive(batchWindowUpdate(a, a, update), true);
  await turn();
  assert.equal(reads, 2);
});
