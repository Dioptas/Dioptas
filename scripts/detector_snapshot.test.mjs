import assert from "node:assert/strict";
import { test } from "node:test";
import {
  detectorPresentation,
  detectorPacket,
  detectorTools,
} from "../src/detectorSnapshot.ts";
import { cakeSourcePixel } from "../src/cakeRadialAxis.ts";
import { RasterTransfer, decodeRaster } from "../src/rasterTransfer.ts";
import { forEachPoint } from "../src/phaseGuidePoints.ts";

const image = {
  bufferId: "detector-a",
  data: new Float32Array([1.25, -6, 70000, 0]).buffer,
  dtype: "f32le",
  width: 2,
  height: 2,
  fullWidth: 2,
  fullHeight: 2,
  step: 1,
  limits: [-6, 70000],
  histogram: { edges: [-6, 1, 70000], counts: [1, 3] },
};
test("detached phase lines use binary buffers and metadata retains no coordinate bytes", async () => {
  const data = new Float64Array([1.2345678901234567, 2, 3, 4]).buffer;
  const points = {
    bufferId: "phase",
    dtype: "xy-f64le",
    count: 2,
    offset: 0,
    length: 2,
    data,
  };
  const value = detectorPresentation(
    "phase-view",
    { raster: image, rings: [{ ring: 0, phaseIndex: 0, points }] },
    { raster: image },
  );
  assert.equal(value.buffers.size, 2);
  assert.equal(value.presentation.raster.rings[0].points.data, undefined);
  const transfer = new RasterTransfer(
    async (_, __, known) =>
      detectorPacket(
        { ok: true, presentation: value.presentation },
        value.buffers,
        new Set(known),
      ).buffer,
  );
  const first = await transfer.call("snapshot");
  const last = await transfer.call("snapshot");
  const a = first.presentation.raster.rings[0].points,
    b = last.presentation.raster.rings[0].points;
  assert.equal(a.data, b.data);
  const pairs = [];
  forEachPoint(b, (x, y) => pairs.push([x, y]));
  assert.deepEqual(pairs, [
    [1.2345678901234567, 2],
    [3, 4],
  ]);
});

test("detached profile metadata retains the radial grid for width dragging without copying pixels", () => {
  let bins;
  const cake = {
    ...image,
    fullWidth: 3,
    radialRange: [1, 3],
    azimuthRange: [-90, 90],
    unit: "q_A^-1",
  };
  const tools = detectorTools(null, {
    cake,
    onBins: (n) => {
      bins = n;
    },
  });
  const copy = JSON.parse(JSON.stringify(tools.profile)).cake;
  assert.deepEqual(copy.radialRange, cake.radialRange);
  assert.equal(copy.unit, "q_A^-1");
  assert.equal(copy.sourceBufferId, cake.bufferId);
  assert.equal(copy.data, undefined);
  assert.equal(cakeSourcePixel(copy, 2), 1.5);
  tools.callbacks.get("profile.onBins")(7);
  assert.equal(bins, 7);
});

test("detector presentation retains callbacks, histogram and source identity without pixels in metadata", async () => {
  let picked, saved;
  const view = {
    key: "config-a",
    read: () => ({ xMin: 0, xMax: 1, yMin: 1, yMax: 2 }),
    write: (range) => {
      saved = range;
    },
  };
  const result = detectorPresentation(
    "configuration/source/geometry",
    {
      raster: image,
      onPick: (p) => {
        picked = p;
      },
      viewport: view,
      exportRef: {},
    },
    { raster: image, onLimits: () => {}, initialLevelsReady: false },
  );
  assert.equal(result.buffers.size, 1);
  assert.equal(result.presentation.raster.raster.data, undefined);
  assert.deepEqual(
    result.presentation.raster.raster.histogram,
    image.histogram,
  );
  assert.equal(result.presentation.intensity.initialLevelsReady, true);
  assert.equal(result.presentation.raster.exportRef, undefined);
  result.callbacks.get("raster.onPick")({ x: 1, y: 2 });
  result.callbacks.get("viewport")(null);
  assert.deepEqual(picked, { x: 1, y: 2 });
  assert.equal(saved, null);
  assert.doesNotThrow(() => JSON.stringify(result.presentation));
});

test("binary snapshots reuse source bytes exactly and cached snapshots transfer only metadata", async () => {
  const value = detectorPresentation(
    "one",
    { raster: image },
    { raster: image },
  );
  let calls = 0,
    transferred = [];
  const transfer = new RasterTransfer(async (_, __, known) => {
    calls++;
    const packet = detectorPacket(
      { ok: true, presentation: value.presentation },
      value.buffers,
      new Set(known),
    );
    transferred.push(packet.byteLength);
    return packet.buffer;
  });
  const first = await transfer.call("detector_snapshot");
  const second = await transfer.call("detector_snapshot");
  const a = first.presentation.raster.raster,
    b = second.presentation.raster.raster;
  assert.deepEqual([...decodeRaster(a)], [1.25, -6, 70000, 0]);
  assert.equal(a.data, b.data);
  assert.equal(calls, 2);
  assert.ok(transferred[1] < transferred[0]);
  assert.equal(first.presentation.identity, "one");
});
