import assert from "node:assert/strict";
import { test } from "node:test";
import { prepareDetectorImage } from "../src/prepareDetectorImage.ts";
const auto = { mode: "percentile", percentile: 7, filter_gaps: false };
const image = {
  data: new ArrayBuffer(8),
  width: 2,
  height: 1,
  limits: [0, 999],
};

test("new detector pixels wait for source-precision Auto limits before publication", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  let published = false;
  const work = prepareDetectorImage(
    async (command, args) => {
      assert.equal(command, "image_levels");
      assert.deepEqual(args, { ...auto, source: "detector" });
      return pending;
    },
    { ok: true, image },
    null,
    auto,
  ).then((result) => {
    published = true;
    return result;
  });
  await Promise.resolve();
  assert.equal(published, false);
  release({ ok: true, levels: [12.123456789, 45.987654321] });
  const result = await work;
  assert.equal(result.image.data, image.data);
  assert.deepEqual(result.image.limits, [12.123456789, 45.987654321]);
  assert.deepEqual(result.image.autoLevels, auto);
});

test("unchanged source refreshes retain manual contrast without another Auto calculation", async () => {
  const result = { ok: true, image: { ...image } };
  assert.equal(
    await prepareDetectorImage(
      () => {
        throw Error("Unneeded Auto request");
      },
      result,
      image,
      auto,
    ),
    result,
  );
});

test("raw detector display uses raw scientific pixels and keeps corrected pixels separate", async () => {
  const rawImage = { ...image, data: new ArrayBuffer(8) };
  const result = await prepareDetectorImage(
    async (_, args) => {
      assert.equal(args.source, "raw_detector");
      return { ok: true, levels: [-5, 8] };
    },
    { ok: true, image, rawImage },
    null,
    auto,
    true,
  );
  assert.deepEqual(result.rawImage.limits, [-5, 8]);
  assert.equal(result.image, image);
});

test("failed or missing-image selections do not calculate levels, and level errors propagate", async () => {
  for (const result of [
    { ok: false, error: "Missing image" },
    { ok: true, pattern: null },
  ])
    assert.equal(
      await prepareDetectorImage(
        () => {
          throw Error("Unneeded Auto request");
        },
        result,
        null,
        auto,
      ),
      result,
    );
  await assert.rejects(
    prepareDetectorImage(
      async () => ({ ok: false, error: "Image statistics failed" }),
      { ok: true, image },
      null,
      auto,
    ),
    /Image statistics failed/,
  );
});

test("native source-precision levels with matching Auto settings need no second scan", async () => {
  const native = {
    ok: true,
    image: { ...image, autoLevels: auto, limits: [12.123456789, 45.987654321] },
  };
  const result = await prepareDetectorImage(
    () => {
      throw Error("Duplicate source scan");
    },
    native,
    null,
    auto,
  );
  assert.equal(result, native);
  let calls = 0;
  await prepareDetectorImage(
    async () => {
      calls++;
      return { ok: true, levels: [20, 30] };
    },
    native,
    null,
    { ...auto, percentile: 10 },
  );
  assert.equal(calls, 1);
});
