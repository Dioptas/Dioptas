import assert from "node:assert/strict";
import { test } from "node:test";
import {
  handleCommandResponse,
  deferredResponse,
  commandCompletion,
} from "../src/commandResponse.ts";
const auto = { mode: "percentile", percentile: 3, filter_gaps: true };
const snapshot = {
  hasImage: true,
  calibrated: true,
  calibration: { canUndo: true },
  integration: { autoProcessError: "" },
};
function harness(overrides = {}, portOverrides = {}) {
  const events = [],
    applied = [];
  const context = {
    command: "open_image",
    args: {},
    invoke: async (command, args) => {
      events.push(["invoke", command, args]);
      return { ok: true };
    },
    submit: async () => ({ ok: true }),
    retryStoredMap: async () => {
      throw Error("Unexpected retry");
    },
    selectedPosition: undefined,
    pendingDrafts: () => false,
    detector: {
      autoActive: () => false,
      raw: () => false,
      previous: () => null,
      autoLevels: () => auto,
    },
    ...overrides,
  };
  const ports = {
    defer: (decision) => events.push(["defer", decision]),
    apply: (result, reset, retain) => {
      if (!result.ok) throw Error(result.error || "failed");
      applied.push({ result, reset, retain });
      events.push(["apply"]);
    },
    trace: (event) => events.push([event]),
    success: (result) => events.push(["success", result]),
    drafts: {
      integration: () => events.push(["draft", "integration"]),
      geometry: () => events.push(["draft", "geometry"]),
      fit: () => events.push(["draft", "fit"]),
    },
    workflow: {
      notice: (m) => events.push(["notice", m]),
      error: (m) => events.push(["error", m]),
      clearPicks: () => events.push(["clear-picks"]),
      calibrationStep: (step) => events.push(["step", step]),
    },
    ...portOverrides,
  };
  return { context, ports, events, applied };
}
test("deferred source/geometry decisions precede errors and never publish, prepare, sync drafts or callbacks", async () => {
  for (const reply of [
    {
      ok: false,
      error: "unresolved",
      hdf5SourceRequest: { path: "master.h5" },
      imageChange: { path: "new" },
    },
    {
      ok: true,
      cancelled: true,
      imageChange: { path: "new" },
      calibrationChange: { path: "calibration" },
    },
  ]) {
    const h = harness({ submit: async () => reply });
    const outcome = await handleCommandResponse(h.context, h.ports);
    assert.equal(outcome.status, "deferred");
    assert.equal(outcome.value, reply);
    assert.deepEqual(
      h.events.map((e) => e[0]),
      ["command-response", "defer"],
    );
  }
  assert.equal(deferredResponse({ ok: true }), undefined);
  assert.equal(
    deferredResponse({
      ok: true,
      imageChange: { path: "first" },
      calibrationChange: { path: "second" },
    }).request.path,
    "first",
  );
});
test("stored Map retry, physical inspection and source-precision levels finish before publication/callback", async () => {
  const image = {
      data: new ArrayBuffer(8),
      width: 2,
      height: 1,
      limits: [0, 100],
    },
    linked = { twoTheta: 5, azimuth: 12 };
  let release;
  const pending = new Promise((resolve) => (release = resolve));
  const h = harness({
    command: "map_select",
    args: { reintegrate: true },
    selectedPosition: linked,
    submit: async () => ({
      ok: false,
      error: "Reintegration needs the original image and a loaded calibration.",
    }),
    retryStoredMap: async () => {
      h.events.push(["retry"]);
      return {
        ok: true,
        map: { points: 2 },
        state: snapshot,
        image,
        linked: null,
      };
    },
    invoke: async (command, args) => {
      h.events.push(["invoke", command, args]);
      if (command === "validation_position") return { ok: true, linked };
      if (command === "image_levels") return pending;
      throw Error(command);
    },
    detector: {
      autoActive: () => true,
      raw: () => false,
      previous: () => null,
      autoLevels: () => auto,
    },
  });
  const work = handleCommandResponse(h.context, h.ports);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(h.applied.length, 0);
  assert.deepEqual(
    h.events.filter((e) => e[0] === "invoke").map((e) => e[1]),
    ["validation_position", "image_levels"],
  );
  assert.deepEqual(h.events.find((e) => e[1] === "validation_position")[2], {
    source: "cake",
    x: 5,
    azimuth: 12,
  });
  release({ ok: true, levels: [2, 9] });
  const outcome = await work;
  assert.equal(outcome.status, "applied");
  assert.equal(h.applied[0].retain, true);
  assert.equal(h.applied[0].result.image.data, image.data);
  assert.deepEqual(h.applied[0].result.image.limits, [2, 9]);
  assert.equal(h.applied[0].result.linked, linked);
  assert.ok(
    h.events.findIndex((e) => e[0] === "apply") <
      h.events.findIndex((e) => e[0] === "success"),
  );
});
test("unit-only replies preserve plot viewport and successful callback observes draft resets in order", async () => {
  const h = harness({
    command: "integration_settings",
    args: { unit: "q_A^-1" },
  });
  await handleCommandResponse(h.context, h.ports);
  assert.equal(h.applied[0].reset, false);
  const p = harness({
    command: "open_project",
    submit: async () => ({ ok: true, state: snapshot }),
  });
  await handleCommandResponse(p.context, p.ports);
  assert.deepEqual(
    p.events
      .filter((e) =>
        ["apply", "draft", "clear-picks", "success"].includes(e[0]),
      )
      .map((e) => e.slice(0, 2)),
    [
      ["apply"],
      ["draft", "integration"],
      ["draft", "geometry"],
      ["draft", "fit"],
      ["clear-picks"],
      ["success", { ok: true, state: snapshot }],
    ],
  );
});
test("canceled replies apply once and call success while retaining drafts and calibration step", async () => {
  const reply = { ok: true, cancelled: true, state: snapshot };
  const h = harness({ command: "open_calibration", submit: async () => reply });
  const outcome = await handleCommandResponse(h.context, h.ports);
  assert.equal(outcome.status, "cancelled");
  assert.equal(h.applied[0].result, reply);
  assert.equal(h.applied.length, 1);
  assert.deepEqual(
    h.events.filter((e) => ["draft", "step", "notice"].includes(e[0])),
    [],
  );
  assert.equal(h.events.at(-1)[0], "success");
});
test("failed preparation refreshes without resetting plot context and preserves original error if recovery fails", async () => {
  const original = Error("statistics failed");
  const h = harness({
    command: "pick_peak",
    submit: async () => ({
      ok: true,
      image: { data: new ArrayBuffer(8), width: 2, height: 1, limits: [0, 10] },
    }),
    detector: {
      autoActive: () => true,
      raw: () => false,
      previous: () => null,
      autoLevels: () => auto,
    },
    invoke: async (command) => {
      h.events.push(["invoke", command]);
      if (command === "image_levels") throw original;
      throw Error("recovery failed");
    },
  });
  const outcome = await handleCommandResponse(h.context, h.ports);
  assert.equal(outcome.status, "failed");
  assert.equal(outcome.error, original);
  assert.deepEqual(
    h.events.filter((e) => e[0] === "error"),
    [["error", "statistics failed"]],
  );
  assert.equal(
    h.events.some((e) => e[0] === "success"),
    false,
  );
  const p = harness({
    submit: async () => ({ ok: false, error: "backend rejected" }),
    invoke: async () => ({ ok: true, image: { data: new ArrayBuffer(8) } }),
  });
  await handleCommandResponse(p.context, p.ports);
  assert.equal(p.applied.length, 1);
  assert.equal(p.applied[0].reset, false);
});
test("notice precedence, pending drafts and history cancellation retain existing workflow policy", () => {
  const save = commandCompletion(
    "save_project",
    {},
    { ok: true, savedPath: "/tmp/test.dio", correctionNotice: "Recalculated" },
    undefined,
    true,
  );
  assert.deepEqual(
    save.filter((e) => e.kind === "notice").map((e) => e.message),
    [
      "Saved test.dio · unapplied option drafts remain in this session",
      "Recalculated",
    ],
  );
  assert.deepEqual(
    commandCompletion(
      "undo_calibration",
      {},
      { ok: true, cancelled: true },
      "integration_overlay",
    ),
    [
      { kind: "notice", message: "Undid overlay edit" },
      { kind: "clear-picks" },
    ],
  );
  assert.deepEqual(
    commandCompletion(
      "next_image",
      { direction: -1 },
      { ok: true, imageUnavailable: true },
    ),
    [{ kind: "notice", message: "No previous image available" }],
  );
});
