import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createRateLimitedInput,
  MAP_UPDATE_INTERVAL_MS,
  PATTERN_UPDATE_INTERVAL_MS,
} from "../src/updateRateLimit.ts";

test("pointer updates coalesce at 30 Hz and preserve the exact release position", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"], now: 0 });
  const values = [];
  const input = createRateLimitedInput(
    PATTERN_UPDATE_INTERVAL_MS,
    (value) => values.push([Date.now(), value]),
    Date.now,
  );
  input.push(1);
  t.mock.timers.tick(0);
  assert.deepEqual(values, [[0, 1]]);
  for (let i = 2; i <= 20; i++) {
    input.push(i);
    t.mock.timers.tick(1);
  }
  assert.equal(values.length, 1);
  t.mock.timers.tick(15);
  assert.deepEqual(values, [
    [0, 1],
    [34, 20],
  ]);
  input.push(21);
  input.flush(22);
  t.mock.timers.tick(100);
  assert.equal(values.at(-1)[1], 22);
  assert.equal(values.length, 3);
});

test("whole-map updates use a separate 500 ms interval and cancellation drops pending input", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"], now: 0 });
  const values = [];
  const input = createRateLimitedInput(
    MAP_UPDATE_INTERVAL_MS,
    (value) => values.push(value),
    Date.now,
  );
  input.push(1);
  t.mock.timers.tick(0);
  input.push(2);
  t.mock.timers.tick(499);
  assert.deepEqual(values, [1]);
  input.push(3);
  t.mock.timers.tick(1);
  assert.deepEqual(values, [1, 3]);
  input.push(4);
  input.cancel();
  t.mock.timers.tick(1000);
  assert.deepEqual(values, [1, 3]);
});
