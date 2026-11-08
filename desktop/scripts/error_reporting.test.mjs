import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createErrorReport,
  recordAction,
  withErrorReporting,
  currentFailure,
  dismissFailure,
} from "../src/errorReporting.ts";

test("reports retain the error message when WebKit's stack omits it and bound activity data", () => {
  const error = new Error("Important failure message");
  error.stack = "@\nevaluate@";
  for (let i = 0; i < 230; i++)
    recordAction(`step-${i}`, {
      data: new Uint8Array(1000000),
      values: Array(1000).fill(12),
    }).status = "completed";
  const report = createErrorReport("Failed operation", error);
  assert.match(report, /Important failure message/);
  assert.match(report, /evaluate@/);
  assert.match(report, /step-229/);
  assert.doesNotMatch(report, /step-179 /);
  assert.match(report, /binary data omitted/);
  assert.ok(report.length < 30000);
});
test("responses and transport rejection produce local reports; mismatch and cancellation stay concise", async () => {
  globalThis.window = new EventTarget();
  const normal = withErrorReporting(async () => ({
    ok: true,
    activity: { path: "/selected/image.tif" },
  }));
  await normal("open_image", {});
  const fail = withErrorReporting(async () => ({
    ok: false,
    error: "Native numerical error",
    errorContext: { nativeBacktrace: "native details" },
  }));
  await fail("integrate", {});
  assert.match(currentFailure().report, /selected\/image.tif/);
  assert.match(currentFailure().report, /Native numerical error/);
  assert.match(currentFailure().report, /native details/);
  dismissFailure();
  const reject = withErrorReporting(async () => {
    throw new Error("Processor disconnected");
  });
  await assert.rejects(reject("integrate", {}), /Processor disconnected/);
  assert.match(currentFailure().report, /Processor disconnected/);
  dismissFailure();
  const mismatch = withErrorReporting(async () => ({
    ok: false,
    error: "Open the matching detector image first.",
  }));
  await mismatch("open_calibration", {});
  assert.equal(currentFailure().report, undefined);
  dismissFailure();
  await withErrorReporting(async () => ({ ok: true, cancelled: true }))(
    "open_image",
    {},
  );
  assert.equal(currentFailure(), null);
});
