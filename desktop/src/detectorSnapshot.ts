import type { Raster } from "./types";

export type DetectorPresentation = {
  identity: string;
  intensityKey?: string;
  label?: string;
  back?: boolean;
  raster: Record<string, unknown>;
  intensity: Record<string, unknown>;
  viewport?: { key: string; range: unknown };
};

const sourceIds = new WeakMap<object, string>();
const legacyIds = new Map<string, string>();
export function detectorBufferId(raster: Raster) {
  if (raster.bufferId) return raster.bufferId;
  if (typeof raster.data === "string") {
    let id = legacyIds.get(raster.data);
    if (!id) {
      id = crypto.randomUUID();
      legacyIds.set(raster.data, id);
    }
    while (legacyIds.size > 4) legacyIds.delete(legacyIds.keys().next().value!);
    return id;
  }
  let id = sourceIds.get(raster.data);
  if (!id) sourceIds.set(raster.data, (id = crypto.randomUUID()));
  return id;
}

/** Only the two existing detector components cross this presentation boundary.
 * Functions stay in the main window; rasters keep immutable content identities.
 */
export function detectorPresentation(
  identity: string,
  raster: Record<string, unknown>,
  intensity: Record<string, unknown>,
) {
  const callbacks = new Map<string, (...args: any[]) => unknown>();
  const buffers = new Map<string, Raster["data"]>();
  const clean = (props: Record<string, unknown>, prefix: string) =>
    Object.fromEntries(
      Object.entries(props).flatMap(([key, value]) => {
        if (key === "exportRef" || key === "viewport" || value === undefined)
          return [];
        if (typeof value === "function") {
          callbacks.set(
            `${prefix}.${key}`,
            value as (...args: any[]) => unknown,
          );
          return [[key, { callback: `${prefix}.${key}` }]];
        }
        if (key === "raster" || key === "mask") {
          if (!value) return [[key, value]];
          const image = value as Raster;
          const bufferId = detectorBufferId(image);
          buffers.set(bufferId, image.data);
          const { data: _, ...metadata } = image;
          return [[key, { ...metadata, bufferId }]];
        }
        return [[key, value]];
      }),
    );
  const view = raster.viewport as
    import("./plotViewport").PlotViewport | undefined;
  if (view) callbacks.set("viewport", view.write);
  return {
    presentation: {
      identity,
      raster: clean(raster, "raster"),
      // Both renderers use the source-precision levels already prepared by the
      // owner. Moving windows must never trigger another Auto calculation.
      intensity: { ...clean(intensity, "intensity"), initialLevelsReady: true },
      viewport: view ? { key: view.key, range: view.read() } : undefined,
    } as DetectorPresentation,
    callbacks,
    buffers,
  };
}

export function detectorPacket(
  result: unknown,
  buffers: Map<string, Raster["data"]>,
  known = new Set<string>(),
) {
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  const descriptors = [];
  for (const [id, data] of buffers) {
    if (known.has(id)) continue;
    // Legacy browser references do not use this native transport.
    if (typeof data === "string")
      throw Error("A native detector buffer must be binary.");
    const chunk = data instanceof ArrayBuffer ? new Uint8Array(data) : data;
    chunks.push(chunk);
    descriptors.push({ id, length: chunk.byteLength });
  }
  const header = new TextEncoder().encode(
    JSON.stringify({ result, buffers: descriptors }),
  );
  const packet = new Uint8Array(
    4 + header.byteLength + chunks.reduce((n, c) => n + c.byteLength, 0),
  );
  new DataView(packet.buffer).setUint32(0, header.length, true);
  packet.set(header, 4);
  let offset = 4 + header.length;
  for (const chunk of chunks) {
    packet.set(chunk, offset);
    offset += chunk.length;
  }
  return packet;
}
