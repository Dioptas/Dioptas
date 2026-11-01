import assert from "node:assert/strict";
import { test } from "node:test";
import {
  RasterTransfer,
  ByteCache,
  decodeRaster,
} from "../src/rasterTransfer.ts";

const image = (id, width = 2, dtype = "f32le") => ({
  width,
  height: 1,
  fullWidth: width,
  fullHeight: 1,
  step: 1,
  dtype,
  limits: [0, 1],
  bufferId: id,
});
function frame(result, buffers = {}) {
  const entries = Object.entries(buffers);
  const header = new TextEncoder().encode(
    JSON.stringify({
      result,
      buffers: entries.map(([id, b]) => ({ id, length: b.byteLength })),
    }),
  );
  const data = new Uint8Array(
    4 + header.length + entries.reduce((n, [, b]) => n + b.byteLength, 0),
  );
  new DataView(data.buffer).setUint32(0, header.length, true);
  data.set(header, 4);
  let at = 4 + header.length;
  for (const [, b] of entries) {
    data.set(new Uint8Array(b), at);
    at += b.byteLength;
  }
  return data.buffer;
}

test("binary arrays retain exact pixels and the same buffer identity on A/B/A", async () => {
  const a = new Float32Array([-3.5, NaN]).buffer,
    b = new Float32Array([1, 8]).buffer;
  const seen = [];
  const transfer = new RasterTransfer(async (action, payload, known) => {
    seen.push(known);
    return frame(
      { ok: true, image: image(action) },
      known.includes(action) ? {} : { [action]: action === "A" ? a : b },
    );
  });
  const first = await transfer.call("A");
  await transfer.call("B");
  const last = await transfer.call("A");
  assert.equal(first.image.data, last.image.data);
  assert.equal(decodeRaster(first.image), decodeRaster(last.image));
  assert.equal(decodeRaster(last.image)[0], -3.5);
  assert.ok(Number.isNaN(decodeRaster(last.image)[1]));
  assert.deepEqual(seen[2], ["A", "B"]);
});

test("identical bytes can be decoded as either mask or floating image", () => {
  const data = new ArrayBuffer(8);
  assert.equal(decodeRaster({ ...image("zero"), data }).length, 2);
  assert.equal(decodeRaster({ ...image("zero", 8, "u8"), data }).length, 8);
});

test("byte and entry limits evict old buffers; recently used data stays cached", () => {
  const cache = new ByteCache(8, 2);
  cache.set("A", 1, 4);
  cache.set("B", 2, 4);
  assert.equal(cache.get("A"), 1);
  cache.set("C", 3, 4);
  assert.equal(cache.get("B"), undefined);
  assert.deepEqual([...cache.snapshot().keys()], ["A", "C"]);
  cache.set("large", 4, 32);
  assert.equal(cache.get("large"), undefined);
});

test("concurrent replies keep advertised buffers alive through LRU eviction", async () => {
  let finish;
  const a = new Float32Array([1, 2]).buffer;
  const t = new RasterTransfer(
    async (action, payload, known) => {
      if (action === "held")
        return new Promise(
          (resolve) =>
            (finish = () => resolve(frame({ ok: true, image: image("A") }))),
        );
      return frame({ ok: true, image: image(action) }, { [action]: a });
    },
    8,
    1,
  );
  const initial = await t.call("A");
  const pending = t.call("held");
  await t.call("B");
  finish();
  assert.equal((await pending).image.data, initial.image.data);
});

test("bad framing, missing buffers, bad dimensions, and wrong lengths fail clearly", async () => {
  for (const f of [
    new ArrayBuffer(2),
    frame({ ok: true, image: image("missing") }),
    frame({ ok: true, image: image("bad", 3) }, { bad: new ArrayBuffer(4) }),
    frame({ ok: true, image: image("bad", -1) }, { bad: new ArrayBuffer(4) }),
  ]) {
    await assert.rejects(
      new RasterTransfer(async () => f).call("state"),
      /binary|buffer|image/i,
    );
  }
  const truncated = frame(
    { ok: true, image: image("A") },
    { A: new ArrayBuffer(8) },
  ).slice(0, -1);
  await assert.rejects(
    new RasterTransfer(async () => truncated).call("state"),
    /Truncated/,
  );
});
