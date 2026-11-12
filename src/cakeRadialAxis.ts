import type { Cake, Unit } from "./types";
import { radialValues } from "./radialReadout.ts";
import { linearTicks } from "./plotTicks.ts";

export type CakeAxisUnit = "2th_deg" | "q_A^-1";
type Grid = Pick<Cake, "radialRange" | "fullWidth" | "unit">;

/** Native ranges contain the first and last bin centers, not image edges.
 * Keep every consumer in the original uniform grid; only labels are converted.
 */
export function cakeSourceCoordinate(cake: Grid, pixel: number): number {
  const [low, high] = cake.radialRange;
  return cake.fullWidth > 1
    ? low + ((pixel - 0.5) / (cake.fullWidth - 1)) * (high - low)
    : low;
}
export function cakeSourcePixel(cake: Grid, coordinate: number): number {
  const [low, high] = cake.radialRange;
  return high !== low && cake.fullWidth > 1
    ? 0.5 + ((coordinate - low) / (high - low)) * (cake.fullWidth - 1)
    : cake.fullWidth / 2;
}

/** Qt wires only the 2θ and Q buttons to the cake. d leaves that axis alone. */
export function nextCakeAxisUnit(
  unit: Unit | undefined,
  previous: CakeAxisUnit,
): CakeAxisUnit {
  return unit === "2th_deg" || unit === "q_A^-1" ? unit : previous;
}

export function createCakeRadialAxis(
  cake: Grid,
  requested: CakeAxisUnit,
  wavelength?: number,
) {
  const convert = (value: number, from: Unit, to: Unit): number | null => {
    if (!Number.isFinite(value)) return null;
    if (from === to) return value;
    // Beyond the physical angular branch sin() turns around; do not invent ticks
    // there when a user pans outside the image or changes wavelength.
    if (from === "2th_deg" && (value < 0 || value > 180)) return null;
    const result = radialValues(value, from, wavelength)[to];
    return result != null && Number.isFinite(result) ? result : null;
  };
  const convertible = cake.radialRange.every(
    (v) => convert(v, cake.unit, requested) != null,
  );
  const unit = convertible ? requested : cake.unit;
  const note = convertible
    ? undefined
    : !(wavelength && Number.isFinite(wavelength) && wavelength > 0)
      ? `${requested === "q_A^-1" ? "Q" : "2θ"} requires a wavelength; showing the source radial unit.`
      : "The source radial range cannot be converted at this wavelength; showing the source radial unit.";
  const atPixel = (pixel: number) =>
    convert(cakeSourceCoordinate(cake, pixel), cake.unit, unit);
  const pixelAt = (value: number) => {
    const source = convert(value, unit, cake.unit);
    return source == null ? null : cakeSourcePixel(cake, source);
  };
  const bounds = (low: number, high: number): [number, number] | null => {
    // Clip only to the physical conversion domain, never rescale the raster.
    let a = cakeSourceCoordinate(cake, low),
      b = cakeSourceCoordinate(cake, high);
    if (cake.unit !== unit) {
      if (cake.unit === "2th_deg") {
        a = Math.max(0, a);
        b = Math.min(180, b);
      } else if (unit === "2th_deg" && wavelength) {
        a = Math.max(0, a);
        b = Math.min((4 * Math.PI) / (wavelength * 1e10), b);
      }
    }
    const min = convert(a, cake.unit, unit),
      max = convert(b, cake.unit, unit);
    return min != null && max != null && min < max ? [min, max] : null;
  };
  return {
    unit,
    requested,
    note,
    atPixel,
    pixelAt,
    bounds,
    ticks(low: number, high: number, intervals: number) {
      const range = bounds(low, high);
      if (!range) return [];
      return linearTicks(...range, intervals).flatMap((tick) => {
        const pixel = pixelAt(tick.value);
        return pixel != null && pixel >= low - 1e-9 && pixel <= high + 1e-9
          ? [{ ...tick, pixel }]
          : [];
      });
    },
  };
}
export type CakeRadialAxis = ReturnType<typeof createCakeRadialAxis>;
