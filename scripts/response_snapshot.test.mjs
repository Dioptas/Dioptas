import assert from "node:assert/strict";
import { test } from "node:test";
import {
  initialResponseSnapshot,
  reduceResponseSnapshot,
  clickContext,
} from "../src/responseSnapshot.ts";
const raster = (data = new ArrayBuffer(8), extra = {}) => ({
  data,
  width: 2,
  height: 1,
  limits: [0, 10],
  ...extra,
});
const state = (extra = {}) => ({
  revision: 1,
  imagePath: "/frames.h5",
  selectedImageSource: "/counts",
  configurationIndex: 0,
  configurationContext: 17,
  projectName: "one.dio",
  shape: [1, 2],
  calibration: {
    canUndo: false,
    canRedo: false,
    transformations: [],
    draft: "original",
  },
  geometry: { wavelength: 4e-11 },
  integration: { frame: 0, patternName: "frame_0", roi: [0, 1, 0, 2] },
  ...extra,
});
function populated() {
  return {
    ...initialResponseSnapshot(),
    state: state(),
    image: raster(),
    rawImage: raster(),
    mask: raster(),
    cake: raster(undefined, { unit: "2th_deg", radialRange: [1, 10] }),
    pattern: { x: [1, 2], y: [3, 4] },
    batch: {
      selected: 0,
      pattern: { x: [1], y: [2] },
      position: { x: 1, unit: "2th_deg" },
      phaseLines: [],
    },
    map: { points: 2 },
    rings: [{ points: [] }],
    linked: { twoTheta: 5 },
    batchWarning: "old",
    mapWarning: "old",
  };
}
test("omitted fields retain owners; explicit nullable fields clear only their declared products", () => {
  const previous = populated();
  assert.equal(
    reduceResponseSnapshot(previous, { ok: true }),
    previous,
    "empty polling replies avoid redundant renders",
  );
  const cleared = reduceResponseSnapshot(previous, {
    ok: true,
    pattern: null,
    cake: null,
    batch: null,
    map: null,
    linked: null,
    batchWarning: null,
    mapWarning: null,
    image: null,
    rawImage: null,
    mask: null,
    rings: null,
  });
  for (const key of [
    "pattern",
    "cake",
    "batch",
    "map",
    "linked",
    "batchWarning",
    "mapWarning",
  ])
    assert.equal(cleared[key], null, key);
  for (const key of ["image", "rawImage", "mask", "rings", "state"])
    assert.equal(cleared[key], previous[key], key);
  assert.equal(previous.pattern.y[0], 3);
});
test("image clear then replacement preserves full resolution and exact binary owners", () => {
  const previous = populated(),
    image = raster(),
    mask = { ...previous.mask };
  const next = reduceResponseSnapshot(previous, {
    ok: true,
    clearImage: true,
    image,
    mask,
  });
  assert.equal(next.image, image);
  assert.equal(next.image.data, image.data);
  assert.equal(next.rawImage, null);
  assert.equal(next.mask, mask, "replacement after clear is its own owner");
  assert.equal(next.pattern, previous.pattern);
  assert.equal(next.cake, previous.cake);
  const cleared = reduceResponseSnapshot(previous, {
    ok: true,
    clearImage: true,
  });
  for (const key of ["image", "rawImage", "mask"])
    assert.equal(cleared[key], null);
});
test("same mask bytes/dimensions retain immutable owner while shape/data changes replace it", () => {
  const previous = populated();
  assert.equal(
    reduceResponseSnapshot(previous, {
      ok: true,
      mask: { ...previous.mask, limits: [2, 9] },
    }).mask,
    previous.mask,
  );
  for (const mask of [raster(), { ...previous.mask, width: 1, height: 2 }])
    assert.equal(
      reduceResponseSnapshot(previous, { ok: true, mask }).mask,
      mask,
    );
});
test("pattern-only and phase-only updates retain detector references while merging history and ROI", () => {
  const previous = populated();
  for (const phaseOnly of [false, true]) {
    const incoming = state({
      revision: 2,
      geometry: { wavelength: 5e-11 },
      calibration: { canUndo: true, canRedo: true, draft: "incoming" },
      integration: {
        frame: 3,
        roi: [0, 8, 0, 8],
        originalPatternVisible: false,
        originalPatternColor: "#73bba6",
      },
    });
    const next = reduceResponseSnapshot(previous, {
      ok: true,
      state: incoming,
      patternOnly: true,
      phaseOnly,
    });
    assert.equal(next.state.geometry, previous.state.geometry);
    assert.equal(next.state.integration.roi, previous.state.integration.roi);
    assert.equal(next.state.calibration.draft, "original");
    assert.equal(next.state.calibration.canUndo, true);
    assert.equal(next.state.revision, 2);
    assert.equal(next.state.integration.frame, 3);
    assert.equal(next.showOriginalPattern, false);
    assert.equal(next.originalPatternColor, "#73bba6");
    assert.equal(next.image, previous.image);
    assert.equal(next.mask, previous.mask);
  }
});
test("full snapshots replace canonical state and keep valid source-unit cake pixels across display units", () => {
  const previous = populated(),
    incoming = state({ revision: 4, unit: "q_A^-1", configurationContext: 23 });
  const next = reduceResponseSnapshot(previous, {
    ok: true,
    state: incoming,
    cake: previous.cake,
  });
  assert.equal(next.state, incoming);
  assert.equal(next.cake, previous.cake);
  assert.equal(next.cake.unit, "2th_deg");
  assert.equal(next.cake.data, previous.cake.data);
  assert.notEqual(clickContext(incoming), clickContext(previous.state));
  assert.equal(
    clickContext({ ...incoming, revision: 77, unit: "d_A" }),
    clickContext(incoming),
  );
  assert.notEqual(
    clickContext({ ...incoming, selectedImageSource: "/other" }),
    clickContext(incoming),
  );
});
test("Batch phase/selection merges precede nullable plot updates without losing stored metadata", () => {
  const previous = populated(),
    lines = [{ position: 1 }],
    position = { x: 4, unit: "q_A^-1" };
  const next = reduceResponseSnapshot(previous, {
    ok: true,
    batchPhaseLines: lines,
    batchSelection: 2,
    batchPosition: position,
    pattern: null,
  });
  assert.equal(next.batch.phaseLines, lines);
  assert.equal(next.batch.selected, 2);
  assert.equal(next.batch.pattern, previous.batch.pattern);
  assert.equal(next.batch.position, position);
  assert.equal(next.pattern, null);
  assert.equal(previous.batch.selected, 0);
});
test("failed responses publish nothing; canceled successful snapshots still apply explicit products", () => {
  const previous = populated();
  assert.throws(
    () =>
      reduceResponseSnapshot(previous, {
        ok: false,
        error: "rejected",
        clearImage: true,
      }),
    /rejected/,
  );
  assert.ok(previous.image);
  assert.equal(
    reduceResponseSnapshot(previous, {
      ok: true,
      cancelled: true,
      pattern: null,
    }).pattern,
    null,
  );
});
