import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createPlotViews,
  detectorViewport,
  patternViewport,
  plotViewContext,
} from "../src/plotViewport.ts";
const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} vs ${b}`);
test("a shared detector view preserves pixel ranges and resets incompatible images", () => {
  const views = createPlotViews();
  const range = { xMin: 200, xMax: 400, yMin: 300, yMax: 500 };
  detectorViewport(views.detector, "981x1043").write(range);
  assert.deepEqual(detectorViewport(views.detector, "981x1043").read(), range);
  assert.equal(detectorViewport(views.detector, "512x512").read(), null);
  detectorViewport(views.detector, "981x1043").write(null);
  assert.equal(detectorViewport(views.detector, "981x1043").read(), null);
});
test("pattern view boundaries follow the same physical interval in 2θ, Q, and descending d", () => {
  const views = createPlotViews();
  patternViewport(views.pattern, "scan", "2th_deg", "linear", 1e-10).write({
    xMin: 30,
    xMax: 60,
    yMin: 10,
    yMax: 100,
  });
  const q = patternViewport(
    views.pattern,
    "scan",
    "q_A^-1",
    "linear",
    1e-10,
  ).read();
  close(q.xMin, 4 * Math.PI * Math.sin(Math.PI / 12));
  close(q.xMax, 2 * Math.PI);
  const d = patternViewport(
    views.pattern,
    "scan",
    "d_A",
    "linear",
    1e-10,
  ).read();
  close(d.xMin, 1);
  close(d.xMax, 1 / (2 * Math.sin(Math.PI / 12)));
  assert.equal(
    patternViewport(views.pattern, "scan", "d_A", "linear", 2e-10).read(),
    null,
  );
});
test("pattern intensity bounds follow log and square-root scales without changing the physical range", () => {
  const views = createPlotViews();
  patternViewport(views.pattern, "scan", "q_A^-1", "linear").write({
    xMin: 1,
    xMax: 2,
    yMin: 100,
    yMax: 10000,
  });
  const log = patternViewport(views.pattern, "scan", "q_A^-1", "log").read();
  close(log.yMin, 2);
  close(log.yMax, 4);
  const sqrt = patternViewport(views.pattern, "scan", "q_A^-1", "sqrt").read();
  close(sqrt.yMin, 10);
  close(sqrt.yMax, 100);
  const signed = { xMin: 1, xMax: 2, yMin: -5, yMax: 10 };
  patternViewport(views.pattern, "scan", "q_A^-1", "sqrt").write(signed);
  assert.deepEqual(
    patternViewport(views.pattern, "scan", "q_A^-1", "sqrt").read(),
    signed,
  );
});

test("replacing a configuration at the same index resets its plot context", () => {
  const state = {
    configurationIndex: 0,
    configurationContext: 12,
    shape: [32, 40],
    calibration: { transformations: [] },
  };
  const views = createPlotViews();
  const before = plotViewContext(state);
  detectorViewport(views.detector, before).write({
    xMin: 2,
    xMax: 8,
    yMin: 3,
    yMax: 9,
  });
  const after = plotViewContext({ ...state, configurationContext: 13 });
  assert.notEqual(before, after);
  assert.equal(detectorViewport(views.detector, after).read(), null);
  assert.equal(plotViewContext({ ...state }), before);
});
