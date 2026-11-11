import type { PackedPoints, RingOverlay } from "./types";

export function pointBufferSize(value: Record<string, unknown>) {
  const { count, offset, length } = value;
  if (
    !Number.isSafeInteger(count) ||
    Number(count) < 2 ||
    Number(count) > (256 * 1024 * 1024) / 16 ||
    !Number.isSafeInteger(offset) ||
    Number(offset) < 0 ||
    !Number.isSafeInteger(length) ||
    Number(length) < 2 ||
    Number(offset) + Number(length) > Number(count)
  )
    throw Error("Invalid binary phase-line dimensions.");
  return Number(count) * 16;
}

const littleEndian = new Uint8Array(new Uint32Array([1]).buffer)[0] === 1;
const decoded = new WeakMap<object, Float64Array>();
export function pointStorage(points: RingOverlay["points"]): object {
  return Array.isArray(points) || typeof points.data === "string"
    ? points
    : points.data;
}
export function packedCoordinates(points: PackedPoints) {
  const key = pointStorage(points);
  const cached = decoded.get(key);
  if (cached) return cached;
  const data =
    typeof points.data === "string"
      ? Uint8Array.from(atob(points.data), (c) => c.charCodeAt(0))
      : points.data;
  if (
    !data ||
    data.byteLength !==
      pointBufferSize(points as unknown as Record<string, unknown>)
  )
    throw Error("Missing or invalid phase-line buffer.");
  const buffer = data instanceof ArrayBuffer ? data : data.buffer;
  const offset = data instanceof ArrayBuffer ? 0 : data.byteOffset;
  let values: Float64Array;
  if (littleEndian) {
    const aligned =
      offset % 8 === 0
        ? data
        : new Uint8Array(buffer, offset, data.byteLength).slice();
    values =
      aligned instanceof ArrayBuffer
        ? new Float64Array(aligned)
        : new Float64Array(
            aligned.buffer,
            aligned.byteOffset,
            aligned.byteLength / 8,
          );
  } else {
    const view = new DataView(buffer, offset, data.byteLength);
    values = new Float64Array(data.byteLength / 8);
    for (let i = 0; i < values.length; i++)
      values[i] = view.getFloat64(i * 8, true);
  }
  decoded.set(key, values);
  return values;
}
export function forEachPoint(
  points: RingOverlay["points"],
  visit: (x: number, y: number, i: number) => void,
) {
  if (Array.isArray(points)) points.forEach(([x, y], i) => visit(x, y, i));
  else {
    const data = packedCoordinates(points);
    for (let i = 0; i < points.length; i++) {
      const at = (points.offset + i) * 2;
      visit(data[at], data[at + 1], i);
    }
  }
}
export function samePoints(a: RingOverlay["points"], b: RingOverlay["points"]) {
  if (a === b) return true;
  if (Array.isArray(a) || Array.isArray(b)) return false;
  return (
    pointStorage(a) === pointStorage(b) &&
    a.offset === b.offset &&
    a.length === b.length
  );
}
