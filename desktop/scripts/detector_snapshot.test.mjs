import assert from "node:assert/strict";
import { test } from "node:test";
import {
  detectorPresentation,
  detectorPacket,
} from "../src/detectorSnapshot.ts";
import { RasterTransfer, decodeRaster } from "../src/rasterTransfer.ts";

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
