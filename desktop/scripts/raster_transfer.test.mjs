import assert from "node:assert/strict";
import { test } from "node:test";
import {
  RasterTransfer,
  ByteCache,
  decodeRaster,
} from "../src/rasterTransfer.ts";
import { forEachPoint, packedCoordinates } from "../src/phaseGuidePoints.ts";

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
test("phase coordinate slices retain float64 bits and reuse advertised phase buffers", async () => {
  const coords = new Float64Array([
    -0, 1e-300, 1.2345678901234567, 4095.9999999999995, 20, -30,
  ]);
  const points = {
    bufferId: "phase",
    dtype: "xy-f64le",
    count: 3,
    offset: 1,
    length: 2,
  };
  const transfer = new RasterTransfer(async (_, __, known) =>
    frame(
      { ok: true, phaseGuides: [{ points }] },
      known.includes("phase") ? {} : { phase: coords.buffer },
    ),
  );
  const first = (await transfer.call("guides")).phaseGuides[0].points;
  const last = (await transfer.call("guides")).phaseGuides[0].points;
  assert.equal(first.data, last.data);
  assert.equal(packedCoordinates(first), packedCoordinates(last));
  const pairs = [];
  forEachPoint(last, (x, y) => pairs.push([x, y]));
  assert.deepEqual(pairs, [
    [coords[2], coords[3]],
    [20, -30],
  ]);
  for (const bad of [
    { offset: 2 },
    { length: 4 },
    { count: 4 },
    { count: Infinity },
    { offset: -1 },
  ]) {
    const broken = new RasterTransfer(async () =>
      frame(
        { ok: true, phaseGuides: [{ points: { ...points, ...bad } }] },
        { phase: coords.buffer },
      ),
    );
    await assert.rejects(broken.call("guides"), /phase-line/);
  }
});
function frame(result, buffers = {}, align = false, products = undefined) {
  const entries = Object.entries(buffers);
  let header = new TextEncoder().encode(
    JSON.stringify({
      result,
      ...(products === undefined ? {} : { products }),
      buffers: entries.map(([id, b]) => ({ id, length: b.byteLength })),
    }),
  );
  if (align) {
    const padded = new Uint8Array(Math.ceil(header.length / 4) * 4).fill(32);
    padded.set(header);
    header = padded;
  }
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

const product = (id, value) => ({
  id,
  bytes: new TextEncoder().encode(JSON.stringify(value)).length,
});
test("metadata reuse is per client, preserves identity, and publishes changed/null products", async () => {
  let batch = {
    selected: 0,
    entries: ["α", "β"],
    values: [
      [1, null],
      [-0, 3],
    ],
  };
  let id = "batch-1";
  const seen = [];
  const server = async (_, __, ___, known) => {
    seen.push(known);
    const products = {
      batch: product(id, batch),
      map: product("empty-map", null),
    };
    return frame(
      {
        ok: true,
        ...(known.batch === id ? {} : { batch }),
        ...(known.map === "empty-map" ? {} : { map: null }),
      },
      {},
      false,
      products,
    );
  };
  const t = new RasterTransfer(server);
  const first = await t.call("state");
  assert.equal((await t.call("state")).batch, first.batch);
  const values = first.batch.values;
  let visits = 0;
  Object.defineProperty(first.batch, "values", {
    configurable: true,
    enumerable: true,
    get: () => {
      visits++;
      return values;
    },
  });
  assert.equal((await t.call("state")).batch, first.batch);
  assert.equal(
    visits,
    0,
    "A warm product must not traverse the unchanged metadata tree",
  );
  Object.defineProperty(first.batch, "values", {
    configurable: true,
    enumerable: true,
    value: values,
  });
  assert.deepEqual(seen[1], { batch: "batch-1", map: "empty-map" });
  const other = await new RasterTransfer(server).call("state");
  assert.deepEqual(other.batch, first.batch);
  assert.notEqual(other.batch, first.batch);
  assert.deepEqual(seen.at(-1), {});
  batch = { ...batch, selected: 1 };
  id = "batch-2";
  const updated = await t.call("state");
  assert.equal(updated.batch.selected, 1);
  assert.notEqual(updated.batch, first.batch);
  batch = null;
  id = "empty-batch";
  assert.equal((await t.call("state")).batch, null);
  assert.equal((await t.call("state")).batch, null);
});

test("in-flight metadata pins survive concurrent replacement and cache eviction", async () => {
  const original = { selected: 0, entries: ["A"] };
  let finish;
  const t = new RasterTransfer(
    async (action, _, __, known) => {
      if (action === "settings")
        return new Promise((resolve) => {
          assert.equal(known.batch, "A");
          finish = () =>
            resolve(
              frame({ ok: true }, {}, false, { batch: product("A", original) }),
            );
        });
      const batch =
        action === "state" ? original : { selected: 1, entries: ["B"] };
      return frame({ ok: true, batch }, {}, false, {
        batch: product(action === "state" ? "A" : "B", batch),
      });
    },
    128,
    1,
    1024,
  );
  const first = await t.call("state");
  const pending = t.call("settings");
  await t.call("example");
  finish();
  assert.equal((await pending).batch, first.batch);
});

test("metadata owners pin binary rasters independently of the ordinary LRU", async () => {
  const bytes = new Float32Array([1.25, NaN]).buffer;
  const batch = { raster: image("pixels"), selected: 0 };
  const descriptor = { batch: product("batch", batch) };
  const t = new RasterTransfer(
    async (_, __, known, products) => {
      if (products.batch === "batch") {
        assert(known.includes("pixels"));
        return frame({ ok: true }, {}, false, descriptor);
      }
      return frame({ ok: true, batch }, { pixels: bytes }, false, descriptor);
    },
    0,
    1,
    1024,
  );
  const first = await t.call("state");
  const next = await t.call("state");
  assert.equal(first.batch, next.batch);
  assert.equal(first.batch.raster.data, next.batch.raster.data);
  assert(Number.isNaN(decodeRaster(next.batch.raster)[1]));
});

test("metadata budgets and malformed/unadvertised references fail safely", async () => {
  const batch = { entries: ["large"] };
  const table = { batch: product("large", batch) };
  const t = new RasterTransfer(
    async (_, __, ___, known) => {
      assert.deepEqual(known, {});
      return frame({ ok: true, batch }, {}, false, table);
    },
    128,
    1,
    0,
  );
  await t.call("state");
  await t.call("state");
  for (const products of [
    null,
    [],
    { other: product("x", batch) },
    { batch: { id: "x", bytes: -1 } },
    { batch: product("unseen", batch) },
  ]) {
    const bad = new RasterTransfer(async () =>
      frame({ ok: true }, {}, false, products),
    );
    await assert.rejects(bad.call("state"), /metadata product/);
  }
});

test("mixed arrays hydrate every descendant without primitive-array guessing", async () => {
  const bytes = new Float32Array([2, 4]).buffer;
  const t = new RasterTransfer(async () =>
    frame(
      { ok: true, mixed: [1, { nested: image("mixed") }, [3, 4]] },
      { mixed: bytes },
    ),
  );
  const response = await t.call("state");
  assert.deepEqual([...decodeRaster(response.mixed[1].nested)], [2, 4]);
  assert.deepEqual(response.mixed[2], [3, 4]);
});

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

test("aligned detector pixels are views of the IPC packet with unchanged float bits", async () => {
  const bits = Uint32Array.from(
    { length: 2048 },
    (_, i) =>
      [0x80000000, 0x7fc12345, 0x7f800000, 0xff800000, 0x3f800001, 0xffffffff][
        i % 6
      ],
  );
  const wire = frame(
    { ok: true, image: image("A", bits.length) },
    { A: bits.buffer },
    true,
  );
  const result = await new RasterTransfer(async () => wire).call("open_image");
  assert.ok(result.image.data instanceof Uint8Array);
  const floats = decodeRaster(result.image);
  assert.equal(floats.buffer, wire);
  assert.equal(floats.byteOffset % 4, 0);
  assert.deepEqual(
    new Uint32Array(floats.buffer, floats.byteOffset, floats.length),
    bits,
  );
  assert.equal(decodeRaster(result.image), floats);
  assert.equal(
    decodeRaster({ ...result.image, dtype: "u8" }).byteLength,
    bits.byteLength,
  );
});

test("legacy unaligned float packets and odd byte masks copy only the float payload", async () => {
  const values = Float32Array.from({ length: 2048 }, (_, i) => i / 7 - 100);
  const wire = frame(
    { ok: true, image: image("A", values.length), mask: image("M", 3, "u8") },
    { M: new Uint8Array([2, 0, 255]).buffer, A: values.buffer },
    true,
  );
  const result = await new RasterTransfer(async () => wire).call("open_image");
  assert.equal(result.image.data.byteOffset % 4, 3);
  assert.notEqual(decodeRaster(result.image).buffer, wire);
  assert.deepEqual(decodeRaster(result.image), values);
  assert.deepEqual(decodeRaster(result.mask), new Uint8Array([2, 0, 255]));
  assert.ok(
    result.mask.data instanceof ArrayBuffer,
    "small companions do not pin the whole packet",
  );
});

test("cache budgets count shared packet storage once and release it only after its last view", () => {
  const cache = new ByteCache(16, 10),
    packet = new ArrayBuffer(12);
  cache.set("A", new Uint8Array(packet, 0, 8), packet.byteLength, packet);
  cache.set("B", new Uint8Array(packet, 8, 4), packet.byteLength, packet);
  assert.deepEqual([...cache.snapshot().keys()], ["A", "B"]);
  cache.set("C", new ArrayBuffer(8), 8);
  assert.deepEqual([...cache.snapshot().keys()], ["C"]);
  cache.set("C", new ArrayBuffer(16), 16);
  assert.equal(cache.get("C").byteLength, 16);
});

test("a small view cannot hide an over-budget backing packet", async () => {
  const a = new Float32Array(2048).buffer;
  const known = [];
  const transfer = new RasterTransfer(async (_, __, cached) => {
    known.push(cached);
    return frame({ ok: true, image: image("A", 2048) }, { A: a }, true);
  }, a.byteLength);
  await transfer.call("open_image");
  await transfer.call("open_image");
  assert.deepEqual(known, [[], []]);
});

test("calculation preloads a correction even when its source packet exceeds the cache budget", async () => {
  const pixels = new Float32Array(1024).fill(1.25).buffer;
  const raster = image("correction", 1024);
  const transfer = new RasterTransfer(async (action, payload, known) => {
    if (action === "calculate") {
      return frame(
        {
          ok: true,
          image: image("source", 1024),
          rawImage: image("raw", 1024),
          preparedCorrections: [raster],
        },
        { source: pixels, raw: pixels, correction: pixels },
        true,
      );
    }
    assert(
      known.includes("correction"),
      "First Plot must advertise the preloaded buffer",
    );
    return frame({ ok: true, correctionPreview: { kind: "oiadac", raster } });
  }, 4096);
  const applied = await transfer.call("calculate");
  assert.equal(applied.preparedCorrections[0].data.byteLength, 4096);
  const plotted = await transfer.call("plot");
  assert.equal(
    applied.preparedCorrections[0].data,
    plotted.correctionPreview.raster.data,
  );
  assert.equal(decodeRaster(plotted.correctionPreview.raster)[1023], 1.25);
});
