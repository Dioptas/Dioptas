import type { Raster } from "./types";

export type DetectorPresentation = {
  identity: string;
  intensityKey?: string;
  label?: string;
  back?: boolean;
  controls?: Record<string, unknown>;
  profile?: Record<string, unknown>;
  cakeAxis?: { requested: "2th_deg" | "q_A^-1"; wavelength?: number };
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
  const cleanPoints = (value: unknown): unknown => {
    if (Array.isArray(value)) {
      // Legacy point pairs already belong to their immutable ring; only packed
      // descriptors need cleaning, never traverse every scalar coordinate.
      if (Array.isArray(value[0]) || typeof value[0] === "number") return value;
      return value.map(cleanPoints);
    }
    if (!value || typeof value !== "object") return value;
    const obj = value as Record<string, unknown>;
    if (obj.dtype === "xy-f64le" && typeof obj.bufferId === "string") {
      buffers.set(obj.bufferId, obj.data as Raster["data"]);
      const { data: _, ...metadata } = obj;
      return metadata;
    }
    return Object.fromEntries(
      Object.entries(obj).map(([key, item]) => [key, cleanPoints(item)]),
    );
  };
  const clean = (props: Record<string, unknown>, prefix: string) =>
    Object.fromEntries(
      Object.entries(props).flatMap(([key, value]) => {
        if (
          key === "exportRef" ||
          key === "viewport" ||
          key === "radialAxis" ||
          value === undefined
        )
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
        return [[key, key === "rings" ? cleanPoints(value) : value]];
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

/** Toolbar callbacks stay with the main scientific command queue. */
export function detectorTools(
  controls: Record<string, unknown> | null,
  profile: Record<string, unknown> | null,
) {
  const callbacks = new Map<string, (...args: any[]) => unknown>();
  const clean = (props: Record<string, unknown> | null, prefix: string) =>
    props
      ? Object.fromEntries(
          Object.entries(props).map(([key, value]) => {
            if (typeof value === "function") {
              callbacks.set(
                `${prefix}.${key}`,
                value as (...args: any[]) => unknown,
              );
              return [key, { callback: `${prefix}.${key}` }];
            }
            // Keep source-grid metadata for the profile and interactive width guide.
            if (key === "cake" && value) {
              const cake = value as import("./types").Cake;
              return [
                key,
                {
                  sourceBufferId: cake.bufferId,
                  radialRange: cake.radialRange,
                  unit: cake.unit,
                  azimuthRange: cake.azimuthRange,
                  fullHeight: cake.fullHeight,
                  fullWidth: cake.fullWidth,
                },
              ];
            }
            return [key, value];
          }),
        )
      : undefined;
  return {
    controls: clean(controls, "controls"),
    profile: clean(profile, "profile"),
    callbacks,
  };
}
