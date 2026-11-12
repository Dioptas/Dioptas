import assert from "node:assert/strict";
import test from "node:test";
import { stapler } from "./stapler.mjs";

test("ticket validation retries a lost Apple connection and retains the command", async () => {
  let calls = 0;
  const waits = [];
  const args = ["validate", "/tmp/Dioptas Desktop.app"];
  const result = await stapler(args, {
    run: (received) => {
      assert.deepEqual(received, args);
      if (++calls === 1)
        throw Object.assign(new Error("exit 68"), {
          stdout: Buffer.from(
            "NSURLErrorDomain Code=-1005 The network connection was lost.",
          ),
        });
      return "validated";
    },
    wait: async (ms) => waits.push(ms),
  });
  assert.equal(result, "validated");
  assert.equal(calls, 2);
  assert.deepEqual(waits, [2000]);
});

test("permanent ticket failures stop immediately and network retries are bounded", async () => {
  for (const [message, expectedCalls] of [
    ["The staple is invalid", 1],
    ["NSURLErrorDomain Code=-1005", 5],
  ]) {
    let calls = 0;
    const waits = [];
    await assert.rejects(
      stapler(["validate", "candidate.dmg"], {
        run: () => {
          calls++;
          throw new Error(message);
        },
        wait: async (ms) => waits.push(ms),
      }),
    );
    assert.equal(calls, expectedCalls);
    assert(waits.every((ms) => ms <= 16000));
  }
});
