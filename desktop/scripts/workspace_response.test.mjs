import assert from "node:assert/strict";
import { test } from "node:test";
import { applyWorkspaceResponse } from "../src/workspaceResponse.ts";
import {
  initialResponseSnapshot,
  clickContext,
} from "../src/responseSnapshot.ts";
const ref = (current) => ({ current });
const raster = (data = new ArrayBuffer(8), extra = {}) => ({
  data,
  width: 2,
  height: 1,
  limits: [1, 9],
  ...extra,
});
const state = (extra) => ({
  revision: 1,
  hasImage: true,
  imagePath: "a.h5",
  selectedImageSource: "/a",
  configurationContext: 1,
  calibration: { canUndo: false, canRedo: false, transformations: [] },
  geometry: { wavelength: 4e-11 },
  integration: { frame: 0, roi: [0, 1, 0, 2] },
  ...extra,
});
function harness({
  configurationChanged = false,
  cakeDisplayChanged = false,
} = {}) {
  const events = [],
    model = {
      ...initialResponseSnapshot(),
      state: state(),
      image: raster(),
      cake: raster(undefined, { unit: "2th_deg" }),
    };
  const ports = {
    snapshot: {
      current: ref(model),
      publish(next) {
        events.push(["publish"]);
        this.current.current = next;
      },
    },
    configuration: {
      begin() {
        events.push(["begin"]);
        return {
          configurationChanged,
          cakeDisplayChanged,
          restore: () => events.push(["restore"]),
        };
      },
    },
    session: {
      current: ref(model.state),
      supportsProducts: ref(false),
      canDefer: ref(false),
      retainedClick: ref(undefined),
      phaseGuideRevision: ref(null),
      resetCalibrationDrafts: (next) => events.push(["reset-drafts", next]),
      clearCalibrationSelection: () => events.push(["clear-selection"]),
    },
    detector: {
      source: ref(model.image),
      rawSource: ref(null),
      invalidateHover: (timer) => events.push(["invalidate-hover", timer]),
      autoActive: ref(true),
      useRaw: () => false,
      levels: (levels) => events.push(["detector-levels", levels]),
      resetView: () => events.push(["reset-view"]),
    },
    cake: {
      source: ref(model.cake),
      autoActive: ref(true),
      levels: (levels) => events.push(["cake-levels", levels]),
    },
    inspection: {
      linked: ref(undefined),
      batchPosition: (next) =>
        events.push(["batch-position", next.batchPosition]),
    },
    products: {
      guides: (g) => events.push(["guides", g]),
      ring: (ring) => events.push(["ring", ring]),
      requestedRings: ref({ rings: false }),
      requestedRingContext: ref("old"),
    },
    workflow: {
      revealOverlays: () => events.push(["reveal"]),
      openBatch: () => events.push(["open-batch"]),
      notice: (msg) => events.push(["notice", msg]),
    },
  };
  return { ports, events, model };
}
test("canonical backend refs update synchronously while pattern-only render inputs keep their identity", () => {
  const h = harness(),
    incoming = state({
      revision: 7,
      supportsRequestedProducts: true,
      integrationDirty: false,
      geometry: { wavelength: 5e-11 },
      calibration: { canUndo: true, canRedo: true },
      integration: { roi: [0, 5, 0, 5] },
    });
  applyWorkspaceResponse(
    { ok: true, state: incoming, patternOnly: true, rings: [] },
    h.ports,
    false,
    true,
  );
  assert.equal(h.ports.session.current.current, incoming);
  assert.equal(
    h.ports.snapshot.current.current.state.geometry,
    h.model.state.geometry,
  );
  assert.equal(
    h.ports.snapshot.current.current.state.calibration.canRedo,
    true,
  );
  assert.equal(h.ports.session.retainedClick.current, clickContext(incoming));
  assert.equal(h.ports.session.phaseGuideRevision.current, 7);
  assert.equal(h.ports.session.supportsProducts.current, true);
  assert.equal(h.ports.session.canDefer.current, true);
  assert.equal(h.ports.products.requestedRingContext.current, null);
  assert.deepEqual(
    h.events.map((e) => e[0]),
    ["begin", "publish", "restore"],
  );
  const prior = h.ports.session.phaseGuideRevision.current;
  applyWorkspaceResponse(
    {
      ok: true,
      state: { ...incoming, revision: 8 },
      patternOnly: true,
      phaseOnly: true,
    },
    h.ports,
    false,
  );
  assert.equal(h.ports.session.phaseGuideRevision.current, prior);
});
test("recovery source replay invalidates hover but preserves manual contrast and plot viewport", () => {
  const h = harness();
  h.ports.detector.autoActive.current = false;
  applyWorkspaceResponse(
    { ok: true, image: { ...h.model.image, limits: [2, 8] } },
    h.ports,
    false,
  );
  assert.equal(h.ports.detector.source.current.data, h.model.image.data);
  assert.deepEqual(
    h.events.filter((e) => ["detector-levels", "reset-view"].includes(e[0])),
    [],
  );
  assert.deepEqual(
    h.events.find((e) => e[0] === "invalidate-hover"),
    ["invalidate-hover", true],
  );
});
test("new detector pixels use raw levels when selected; explicit levels and per-configuration restore keep precedence", () => {
  const h = harness({ configurationChanged: true, cakeDisplayChanged: true });
  h.ports.detector.autoActive.current = false;
  h.ports.detector.useRaw = () => true;
  const image = raster(),
    rawImage = raster(undefined, { limits: [-3, 6] }),
    cake = raster(undefined, { unit: "q_A^-1", limits: [4, 20] });
  applyWorkspaceResponse(
    {
      ok: true,
      image,
      rawImage,
      cake,
      levels: [7, 12],
      display: "detector",
      state: state({ configurationContext: 2 }),
    },
    h.ports,
  );
  assert.deepEqual(
    h.events.filter((e) => e[0] === "detector-levels"),
    [
      ["detector-levels", [-3, 6]],
      ["detector-levels", [7, 12]],
    ],
  );
  assert.deepEqual(
    h.events.find((e) => e[0] === "cake-levels"),
    ["cake-levels", [4, 20]],
  );
  assert.equal(h.ports.detector.rawSource.current, rawImage);
  assert.equal(h.ports.cake.source.current, cake);
  assert.equal(h.ports.snapshot.current.current.cake.unit, "q_A^-1");
  assert.ok(
    h.events.findIndex((e) => e[0] === "publish") <
      h.events.findIndex((e) => e[0] === "restore"),
  );
  assert.equal(h.events.at(-1)[0], "clear-selection");
});
test("clear/replacement, calibration reset, guides, linked null and configuration cleanup retain effect ordering", () => {
  const h = harness({ configurationChanged: true }),
    incoming = state({ revision: 4 }),
    image = raster();
  applyWorkspaceResponse(
    {
      ok: true,
      state: incoming,
      calibrationReset: true,
      clearImage: true,
      image,
      phaseGuides: [],
      linked: null,
      batchWaterfallCreated: true,
      batchOpened: true,
      batchPosition: { x: 4, unit: "q_A^-1" },
      savedPath: "C:\\data\\saved.dio",
    },
    h.ports,
  );
  assert.equal(h.ports.inspection.linked.current, null);
  assert.equal(h.ports.detector.source.current, image);
  assert.equal(h.ports.detector.rawSource.current, null);
  assert.deepEqual(
    h.events.filter((e) => e[0] === "invalidate-hover"),
    [
      ["invalidate-hover", false],
      ["invalidate-hover", true],
    ],
  );
  assert.deepEqual(
    h.events
      .map((e) => e[0])
      .filter((e) =>
        ["clear-selection", "guides", "restore", "notice"].includes(e),
      ),
    ["clear-selection", "guides", "restore", "clear-selection", "notice"],
  );
  assert.equal(h.events.at(-1)[1], "Saved saved.dio");
});
test("failed snapshot has no side effects, and omitted cake cannot erase source identity", () => {
  const h = harness();
  assert.throws(
    () => applyWorkspaceResponse({ ok: false, error: "bad" }, h.ports),
    /bad/,
  );
  assert.deepEqual(h.events, []);
  const cake = h.ports.cake.source.current;
  applyWorkspaceResponse({ ok: true }, h.ports, false);
  assert.equal(h.ports.cake.source.current, cake);
  applyWorkspaceResponse({ ok: true, cake: null }, h.ports, false);
  assert.equal(h.ports.cake.source.current, null);
  assert.equal(h.ports.snapshot.current.current.cake, null);
});
