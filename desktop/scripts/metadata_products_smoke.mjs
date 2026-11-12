import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { RasterTransfer } from "../src/rasterTransfer.ts";
import { nativeClient, root } from "./native_backend_client.mjs";

// Exercise the real binary stdio/TypeScript boundary, independently of the
// browser compatibility adapter. No Python or scientific fixture fabrication.
const native = nativeClient();
const packets = [];
const transfer = () =>
  new RasterTransfer(async (action, payload, buffers, products) => {
    const packet = await native.invokePacket(
      action,
      payload,
      buffers,
      products,
    );
    const size = packet.readUInt32LE(0);
    packets.push({
      action,
      headerBytes: size,
      header: JSON.parse(packet.subarray(4, 4 + size)),
    });
    return packet.buffer.slice(
      packet.byteOffset,
      packet.byteOffset + packet.byteLength,
    );
  });
try {
  const input = path.join(
    root,
    "desktop/backend/tests/fixtures/batch_background_input.h5",
  );
  assert.equal((await native.invoke("batch_open", { path: input })).ok, true);
  assert.equal((await native.invoke("map_batch", { path: input })).ok, true);
  const firstClient = transfer();
  const first = await firstClient.call("state");
  assert(first.ok && first.batch && first.map);
  const full = packets.at(-1);
  const second = await firstClient.call("state");
  const warm = packets.at(-1);
  assert.equal(second.batch, first.batch);
  assert.equal(second.map, first.map);
  assert.equal(second.map.values, first.map.values);
  assert.equal(second.batch.raster.data, first.batch.raster.data);
  assert.equal(second.map.raster.data, first.map.raster.data);
  assert.equal(Object.hasOwn(warm.header.result, "batch"), false);
  assert.equal(Object.hasOwn(warm.header.result, "map"), false);
  assert(warm.headerBytes < full.headerBytes);
  const separate = await transfer().call("state");
  assert(Object.hasOwn(packets.at(-1).header.result, "batch"));
  assert.deepEqual(separate.map.values, first.map.values);
  assert.notEqual(separate.map, first.map);
  const selected = await firstClient.call("batch_select", { index: 1 });
  assert(selected.ok);
  assert.equal(selected.batch.selected, 1);
  assert.notEqual(selected.batch, first.batch);
  assert.equal(selected.map, first.map);
  const mapSelected = await firstClient.call("map_select", { index: 1 });
  assert(mapSelected.ok);
  assert.equal(mapSelected.map.selected, 1);
  assert.notEqual(mapSelected.map, first.map);
  const legacy = await native.invokePacket("state");
  const length = legacy.readUInt32LE(0);
  const legacyHeader = JSON.parse(legacy.subarray(4, 4 + length));
  assert.equal(Object.hasOwn(legacyHeader, "products"), false);
  assert(legacyHeader.result.batch && legacyHeader.result.map);
  const receipt = {
    fullHeaderBytes: full.headerBytes,
    reusedHeaderBytes: warm.headerBytes,
    independentClients: true,
    unchangedProductAndRasterIdentity: true,
    selectedProductsInvalidated: true,
    legacyFullReply: true,
  };
  const output = path.join(root, "desktop/artifacts/metadata-products-native");
  await mkdir(output, { recursive: true });
  await writeFile(
    path.join(output, "results.json"),
    JSON.stringify(receipt, null, 2) + "\n",
  );
  console.log(JSON.stringify(receipt));
} finally {
  await native.close();
}
