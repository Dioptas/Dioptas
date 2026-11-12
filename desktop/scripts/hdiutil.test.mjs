import assert from "node:assert/strict";
import test from "node:test";
import { hdiutil } from "./hdiutil.mjs";

test("transient disk-image contention retries, cleans its partial image and then succeeds", async () => {
  const waits = [];
  let calls = 0,
    cleanups = 0;
  const output = await hdiutil(["create"], {
    run: async () =>
      ++calls === 1
        ? { code: 1, output: "hdiutil: create failed - Resource busy" }
        : { code: 0, output: "created" },
    wait: async (ms) => waits.push(ms),
    beforeRetry: async () => {
      cleanups++;
    },
  });
  assert.equal(output, "created");
  assert.equal(calls, 2);
  assert.equal(cleanups, 1);
  assert.deepEqual(waits, [2000]);
});

test("permanent errors fail immediately and contention retries are bounded", async () => {
  for (const [output, expectedCalls] of [
    ["Permission denied", 1],
    ["Resource busy", 5],
  ]) {
    let calls = 0;
    const waits = [];
    await assert.rejects(
      hdiutil(["create"], {
        run: async () => {
          calls++;
          return { code: 1, output };
        },
        wait: async (ms) => waits.push(ms),
      }),
      /hdiutil failed/,
    );
    assert.equal(calls, expectedCalls);
    assert.ok(waits.every((ms) => ms <= 16000));
  }
});
