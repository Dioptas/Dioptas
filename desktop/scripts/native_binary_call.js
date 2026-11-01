// Test-window client for independently checking the native binary wire format.
// The UI itself always uses src/rasterTransfer.ts.
(() => {
  const cache = new Map();
  let retained = 0;
  window.__dioptasNativeCall = async (action, payload = {}) => {
    const known = new Map(cache); // pin exactly what this request advertises
    const wire = await window.__TAURI_INTERNALS__.invoke("desktop_invoke", {
      action,
      payload,
      cachedBuffers: [...known.keys()],
    });
    if (!(wire instanceof ArrayBuffer))
      throw Error("Native image IPC returned JSON instead of binary");
    const n = new DataView(wire).getUint32(0, true);
    const header = JSON.parse(
      new TextDecoder().decode(new Uint8Array(wire, 4, n)),
    );
    let offset = n + 4,
      bufferBytes = 0;
    for (const { id, length } of header.buffers) {
      if (offset + length > wire.byteLength)
        throw Error("Truncated native pixels");
      const data =
        known.get(id) ?? cache.get(id) ?? wire.slice(offset, offset + length);
      const old = cache.get(id);
      if (old) retained -= old.byteLength;
      cache.delete(id);
      cache.set(id, data);
      retained += data.byteLength;
      offset += length;
      bufferBytes += length;
    }
    if (offset !== wire.byteLength) throw Error("Invalid native buffer table");
    // This helper handles sequential scientific calls; the production client
    // additionally covers concurrent eviction in raster_transfer.test.mjs.
    const resolve = (value) => {
      if (Array.isArray(value)) return value.map(resolve);
      if (!value || typeof value !== "object") return value;
      if (value.bufferId && value.dtype) {
        const data = cache.get(value.bufferId) ?? known.get(value.bufferId);
        if (
          !data ||
          data.byteLength !==
            value.width * value.height * (value.dtype === "u8" ? 1 : 4)
        )
          throw Error("Native raster dimensions or pixels were lost");
        return { ...value, data };
      }
      return Object.fromEntries(
        Object.entries(value).map(([k, v]) => [k, resolve(v)]),
      );
    };
    const result = resolve(header.result);
    while (retained > 128 * 1024 * 1024 || cache.size > 64) {
      const oldest = cache.keys().next().value;
      retained -= cache.get(oldest).byteLength;
      cache.delete(oldest);
    }
    return {
      ...result,
      binaryTransfer: {
        bytes: wire.byteLength,
        bufferBytes,
        buffers: header.buffers.length,
      },
    };
  };
})();
