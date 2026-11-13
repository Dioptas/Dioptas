import type { CheckedInvocation } from "./commandContracts";
import type {
  CommandInvocation,
  CommandName,
  CommandResult,
  DetectorSnapshotResult,
} from "./commandContracts";
import type { Raster, Response } from "./types";
import { navigationTrace } from "./navigationTiming.ts";
import { pointBufferSize } from "./phaseGuidePoints.ts";

// Bound retained source buffers, including images we have just browsed away from.
export class ByteCache<K, V> {
  private entries = new Map<K, { value: V; storage: object }>();
  private storage = new Map<object, { size: number; references: number }>();
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
  private remove(key: K) {
    const entry = this.entries.get(key)!;
    const storage = this.storage.get(entry.storage)!;
    if (--storage.references === 0) {
      this.size -= storage.size;
      this.storage.delete(entry.storage);
    }
    this.entries.delete(key);
  }
  set(key: K, value: V, size: number, owner: object = {}) {
    if (this.entries.has(key)) this.remove(key);
    if (size > this.budget) return;
    const storage = this.storage.get(owner);
    if (storage) storage.references++;
    else {
      this.storage.set(owner, { size, references: 1 });
      this.size += size;
    }
    this.entries.set(key, { value, storage: owner });
    while (this.size > this.budget || this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value!;
      this.remove(oldest);
    }
  }
  snapshot() {
    return new Map([...this.entries].map(([k, e]) => [k, e.value]));
  }
}

type RasterBytes = ArrayBuffer | Uint8Array<ArrayBuffer>;
type CachedProduct = {
  id: string;
  bytes: number;
  value: unknown;
  buffers: Map<string, RasterBytes>;
  cost: number;
};
/** Charge retained packet owners as well as conservative JSON object storage. */
function productStorage(value: unknown, bytes: number) {
  const buffers = new Map<string, RasterBytes>();
  const owners = new Set<ArrayBuffer>();
  const visit = (value: unknown): void => {
    if (!value || typeof value !== "object") return;
    const object = value as Record<string, unknown>;
    if (
      typeof object.bufferId === "string" &&
      (object.data instanceof ArrayBuffer || object.data instanceof Uint8Array)
    ) {
      const data = object.data as RasterBytes;
      buffers.set(object.bufferId, data);
      owners.add(data instanceof ArrayBuffer ? data : data.buffer);
      return;
    }
    if (Array.isArray(value)) value.forEach(visit);
    else Object.values(object).forEach(visit);
  };
  visit(value);
  return {
    buffers,
    cost:
      bytes * 4 + [...owners].reduce((sum, owner) => sum + owner.byteLength, 0),
  };
}

export class RasterTransfer {
  private buffers: ByteCache<string, RasterBytes>;
  private products: ByteCache<string, CachedProduct>;
  private invoke: (
    action: string,
    payload: object,
    cached: string[],
    cachedProducts: Record<string, string>,
  ) => Promise<ArrayBuffer>;
  constructor(
    invoke: (
      action: string,
      payload: object,
      cached: string[],
      cachedProducts: Record<string, string>,
    ) => Promise<ArrayBuffer>,
    maxBytes = 128 * 1024 * 1024,
    maxEntries = 64,
    maxProductBytes = 64 * 1024 * 1024,
  ) {
    this.invoke = invoke;
    this.buffers = new ByteCache(maxBytes, maxEntries);
    this.products = new ByteCache(maxProductBytes, 2);
  }
  private remember(id: string, data: RasterBytes) {
    const owner = data instanceof ArrayBuffer ? data : data.buffer;
    // Charge the complete retained packet once, including all its views.
    this.buffers.set(id, data, owner.byteLength, owner);
  }

  call<const A extends CommandInvocation>(
    ...call: CheckedInvocation<A>
  ): Promise<CommandResult<A[0]>>;
  call(
    action: "detector_snapshot",
    payload?: object,
  ): Promise<DetectorSnapshotResult>;
  async call(
    action: CommandName | "detector_snapshot",
    payload: object = {},
  ): Promise<Response | DetectorSnapshotResult> {
    // Pin advertised buffers for this request. A concurrent response may evict
    // them from the LRU before this response arrives.
    const known = this.buffers.snapshot();
    const knownProducts = this.products.snapshot();
    // Product owners keep their raster bytes live even after LRU eviction.
    // Pin them along with the ordinary per-request advertised buffers.
    for (const product of knownProducts.values())
      for (const [id, bytes] of product.buffers) {
        known.delete(id);
        known.set(id, bytes);
      }
    navigationTrace("ipc-start", { action });
    const frame = await this.invoke(
      action,
      payload,
      [...known.keys()].slice(-64),
      Object.fromEntries(
        [...knownProducts].map(([field, product]) => [field, product.id]),
      ),
    );
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
    const incoming = new Map<string, RasterBytes>();
    if (
      !header ||
      !Array.isArray(header.buffers) ||
      !header.result ||
      typeof header.result !== "object"
    )
      throw Error("Invalid binary image header.");
    const productDescriptors = new Map<string, { id: string; bytes: number }>();
    const retainedProducts = new Map<string, CachedProduct>();
    if (header.products !== undefined) {
      if (
        !header.products ||
        typeof header.products !== "object" ||
        Array.isArray(header.products)
      )
        throw Error("Invalid metadata product table.");
      for (const [field, descriptor] of Object.entries(header.products)) {
        const entry = descriptor as { id?: unknown; bytes?: unknown } | null;
        if (
          !["batch", "map"].includes(field) ||
          !entry ||
          typeof entry.id !== "string" ||
          !/^[A-Za-z0-9:_-]{1,128}$/.test(entry.id) ||
          !Number.isSafeInteger(entry.bytes) ||
          Number(entry.bytes) < 0
        )
          throw Error("Invalid metadata product descriptor.");
        const description = { id: entry.id, bytes: Number(entry.bytes) };
        productDescriptors.set(field, description);
        if (!Object.hasOwn(header.result, field)) {
          const cached = knownProducts.get(field);
          if (!cached || cached.id !== entry.id || cached.bytes !== entry.bytes)
            throw Error("Missing or invalid cached metadata product.");
          retainedProducts.set(field, cached);
        }
      }
    }
    if (
      header.result.preparedCorrections !== undefined &&
      !Array.isArray(header.result.preparedCorrections)
    )
      throw Error("Invalid prepared correction buffers.");
    const preparedIds = new Set<string>(
      (header.result.preparedCorrections ?? [])
        .map((r: { bufferId?: string }) => r.bufferId)
        .filter((id: unknown): id is string => typeof id === "string"),
    );
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
        // Preloaded corrections need standalone storage to remain cacheable
        // even when the surrounding source packet exceeds the byte budget.
        // Keep other large images as views; copy small companions (usually masks).
        (preparedIds.has(id) || size <= frame.byteLength / 4
          ? frame.slice(offset, offset + size)
          : new Uint8Array(frame, offset, size));
      incoming.set(id, data);
      this.remember(id, data);
      offset += size;
    }
    if (offset !== frame.byteLength)
      throw Error("Unexpected binary image data.");
    const hydrate = (value: unknown): unknown => {
      if (Array.isArray(value)) {
        let result: unknown[] | undefined;
        for (let i = 0; i < value.length; i++) {
          const child = hydrate(value[i]);
          if (child !== value[i]) result ??= value.slice();
          if (result) result[i] = child;
        }
        return result ?? value;
      }
      if (!value || typeof value !== "object") return value;
      const obj = value as Record<string, unknown>;
      if (typeof obj.bufferId === "string" && obj.dtype === "xy-f64le") {
        const data =
          incoming.get(obj.bufferId) ??
          known.get(obj.bufferId) ??
          this.buffers.get(obj.bufferId);
        if (!data || data.byteLength !== pointBufferSize(obj))
          throw Error("Missing or invalid cached phase-line buffer.");
        this.remember(obj.bufferId, data);
        return { ...obj, data };
      }
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
        this.remember(obj.bufferId, data);
        return { ...obj, data };
      }
      let result: Record<string, unknown> | undefined;
      for (const [key, value] of Object.entries(obj)) {
        const child = hydrate(value);
        if (child !== value) result ??= { ...obj };
        if (result) result[key] = child;
      }
      return result ?? obj;
    };
    const result = hydrate(header.result) as Response;
    for (const [field, product] of retainedProducts)
      (result as unknown as Record<string, unknown>)[field] = product.value;
    for (const [field, descriptor] of productDescriptors) {
      const retained = retainedProducts.get(field);
      if (retained) {
        // Warm references reuse their already charged owners in constant time;
        // do not walk thousands of unchanged entries to recount their storage.
        this.products.set(field, retained, retained.cost);
        continue;
      }
      const value = (result as unknown as Record<string, unknown>)[field];
      const storage = productStorage(value, descriptor.bytes);
      this.products.set(
        field,
        { ...descriptor, value, buffers: storage.buffers, cost: storage.cost },
        storage.cost,
      );
    }
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
  RasterBytes,
  Partial<Record<Raster["dtype"], Float32Array | Uint8Array>>
>();
export function decodeRaster(raster: Raster): Float32Array | Uint8Array {
  let data: RasterBytes;
  if (typeof raster.data === "string") {
    // Base64 is used only by the headless browser test adapter.
    const raw = atob(raster.data);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    data = bytes.buffer;
  } else {
    data = raster.data;
    const cached = decoded.get(data)?.[raster.dtype];
    if (cached) return cached;
  }
  const buffer = data instanceof ArrayBuffer ? data : data.buffer;
  const offset = data instanceof ArrayBuffer ? 0 : data.byteOffset;
  let values: Float32Array | Uint8Array;
  if (raster.dtype === "u8")
    values = new Uint8Array(buffer, offset, data.byteLength);
  else if (littleEndian) {
    // Native headers align the first payload. Test packets and odd byte masks
    // can still produce an unaligned float payload: copy it once.
    const aligned =
      offset % 4 === 0
        ? data
        : new Uint8Array(buffer, offset, data.byteLength).slice();
    values =
      aligned instanceof ArrayBuffer
        ? new Float32Array(aligned)
        : new Float32Array(
            aligned.buffer,
            aligned.byteOffset,
            aligned.byteLength / 4,
          );
  } else {
    const view = new DataView(buffer, offset, data.byteLength);
    values = new Float32Array(data.byteLength / 4);
    for (let i = 0; i < values.length; i++)
      values[i] = view.getFloat32(i * 4, true);
  }
  decoded.set(data, { ...decoded.get(data), [raster.dtype]: values });
  return values;
}

/** Compatibility-only expected misses from older workers. Keep normalization at the wire
 * boundary: the original error response is untouched and no stale fields leak
 * into the historical minimal success shape. */
export function normalizeCompatibilityResult<C extends CommandName>(
  action: C,
  response: CommandResult<C>,
): CommandResult<C> {
  if (
    action === "pick_peak" &&
    !response.ok &&
    response.error ===
      "No peak found here. Click on a bright ring, or try single-peak mode."
  )
    return { ok: true, noPeakFound: true } as CommandResult<C>;
  if (
    action === "scxrd_pixel" &&
    !response.ok &&
    response.error === "Pixel outside SCXRD detector."
  )
    return { ok: true, scxrdPixel: null } as CommandResult<C>;
  return response;
}

/** Detector callback replies are already correlated by the event RPC's id.
 * Its narrow acknowledgement/data envelope is deliberately different from the
 * complete native command result. Keep that wire assertion at this boundary. */
export function detectorProfileReply(
  value: unknown,
): import("./detectorProfileCommands").ProfileReply | undefined {
  return value as import("./detectorProfileCommands").ProfileReply | undefined;
}
