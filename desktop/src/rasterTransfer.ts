import type { Raster, Response } from "./types";
import { navigationTrace } from "./navigationTiming.ts";

// Bound retained source buffers, including images we have just browsed away from.
export class ByteCache<K, V> {
  private entries = new Map<K, { value: V; size: number }>();
  private size = 0;
  private budget: number;
  private maxEntries: number;
  constructor(budget: number, maxEntries = 64) {
    this.budget = budget;
    this.maxEntries = maxEntries;
  }
  get(key: K) {
    const entry = this.entries.get(key);
    if (entry) {
      this.entries.delete(key);
      this.entries.set(key, entry);
    }
    return entry?.value;
  }
  set(key: K, value: V, size: number) {
    const old = this.entries.get(key);
    if (old) {
      this.size -= old.size;
      this.entries.delete(key);
    }
    if (size > this.budget) return;
    this.entries.set(key, { value, size });
    this.size += size;
    while (this.size > this.budget || this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value!;
      this.size -= this.entries.get(oldest)!.size;
      this.entries.delete(oldest);
    }
  }
  snapshot() {
    return new Map([...this.entries].map(([k, e]) => [k, e.value]));
  }
}

export class RasterTransfer {
  private buffers: ByteCache<string, ArrayBuffer>;
  private invoke: (
    action: string,
    payload: Record<string, unknown>,
    cached: string[],
  ) => Promise<ArrayBuffer>;
  constructor(
    invoke: (
      action: string,
      payload: Record<string, unknown>,
      cached: string[],
    ) => Promise<ArrayBuffer>,
    maxBytes = 128 * 1024 * 1024,
    maxEntries = 64,
  ) {
    this.invoke = invoke;
    this.buffers = new ByteCache(maxBytes, maxEntries);
  }

  async call(
    action: string,
    payload: Record<string, unknown> = {},
  ): Promise<Response> {
    // Pin advertised buffers for this request. A concurrent response may evict
    // them from the LRU before this response arrives.
    const known = this.buffers.snapshot();
    navigationTrace("ipc-start", { action });
    const frame = await this.invoke(action, payload, [...known.keys()]);
    navigationTrace("ipc-received", {
      action,
      bytes: frame instanceof ArrayBuffer ? frame.byteLength : null,
    });
    if (!(frame instanceof ArrayBuffer) || frame.byteLength < 4)
      throw Error("Invalid binary image response.");
    const length = new DataView(frame).getUint32(0, true);
    if (length > frame.byteLength - 4)
      throw Error("Truncated binary image header.");
    const header = JSON.parse(
      new TextDecoder().decode(new Uint8Array(frame, 4, length)),
    );
    let offset = 4 + length;
    const incoming = new Map<string, ArrayBuffer>();
    if (
      !header ||
      !Array.isArray(header.buffers) ||
      !header.result ||
      typeof header.result !== "object"
    )
      throw Error("Invalid binary image header.");
    for (const { id, length: size } of header.buffers) {
      if (typeof id !== "string" || incoming.has(id))
        throw Error("Invalid binary buffer id.");
      if (
        !Number.isSafeInteger(size) ||
        size < 0 ||
        size > frame.byteLength - offset
      )
        throw Error("Truncated binary image buffer.");
      const data =
        known.get(id) ??
        this.buffers.get(id) ??
        frame.slice(offset, offset + size);
      incoming.set(id, data);
      this.buffers.set(id, data, data.byteLength);
      offset += size;
    }
    if (offset !== frame.byteLength)
      throw Error("Unexpected binary image data.");
    const hydrate = (value: unknown): unknown => {
      if (Array.isArray(value)) return value.map(hydrate);
      if (!value || typeof value !== "object") return value;
      const obj = value as Record<string, unknown>;
      if (
        typeof obj.bufferId === "string" &&
        (obj.dtype === "f32le" || obj.dtype === "u8")
      ) {
        const data =
          incoming.get(obj.bufferId) ??
          known.get(obj.bufferId) ??
          this.buffers.get(obj.bufferId);
        if (
          !Number.isSafeInteger(obj.width) ||
          Number(obj.width) < 1 ||
          !Number.isSafeInteger(obj.height) ||
          Number(obj.height) < 1
        )
          throw Error("Invalid binary image dimensions.");
        const expected =
          Number(obj.width) * Number(obj.height) * (obj.dtype === "u8" ? 1 : 4);
        if (!data || data.byteLength !== expected)
          throw Error("Missing or invalid cached image buffer.");
        this.buffers.set(obj.bufferId, data, data.byteLength);
        return { ...obj, data };
      }
      return Object.fromEntries(
        Object.entries(obj).map(([k, v]) => [k, hydrate(v)]),
      );
    };
    const result = hydrate(header.result) as Response;
    navigationTrace("ipc-hydrated", {
      action,
      requestId: header.id,
      headerBytes: length,
      pixelBytes: frame.byteLength - 4 - length,
      bufferId: result.image?.bufferId,
    });
    return result;
  }
}

const littleEndian = new Uint8Array(new Uint32Array([1]).buffer)[0] === 1;
const decoded = new WeakMap<
  ArrayBuffer,
  Partial<Record<Raster["dtype"], Float32Array | Uint8Array>>
>();
export function decodeRaster(raster: Raster): Float32Array | Uint8Array {
  let buffer: ArrayBuffer;
  if (typeof raster.data === "string") {
    // Compatibility for the earlier pywebview host and browser test bridge.
    const raw = atob(raster.data);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    buffer = bytes.buffer;
  } else {
    buffer = raster.data;
    const cached = decoded.get(buffer)?.[raster.dtype];
    if (cached) return cached;
  }
  let values: Float32Array | Uint8Array;
  if (raster.dtype === "u8") values = new Uint8Array(buffer);
  else if (littleEndian) values = new Float32Array(buffer);
  else {
    const view = new DataView(buffer);
    values = new Float32Array(buffer.byteLength / 4);
    for (let i = 0; i < values.length; i++)
      values[i] = view.getFloat32(i * 4, true);
  }
  decoded.set(buffer, { ...decoded.get(buffer), [raster.dtype]: values });
  return values;
}
