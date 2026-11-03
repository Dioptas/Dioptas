import type { Unit } from "./types";
import type { PlotField } from "./plotReadout";
import { coordinateValue } from "./readoutNumbers.ts";

/** Display conversions use the session wavelength in metres, as in calc.convert_units. */
export function radialValues(
  x: number,
  unit: Unit,
  wavelength?: number,
): Record<Unit, number | null> {
  const lambda =
    wavelength && wavelength > 0 && Number.isFinite(wavelength)
      ? wavelength * 1e10
      : null;
  const q =
    unit === "q_A^-1"
      ? x
      : unit === "d_A"
        ? (2 * Math.PI) / x
        : lambda
          ? (4 * Math.PI * Math.sin((x * Math.PI) / 360)) / lambda
          : null;
  const ratio = q != null && lambda ? (q * lambda) / (4 * Math.PI) : null;
  return {
    "2th_deg":
      unit === "2th_deg"
        ? x
        : ratio != null && Math.abs(ratio) <= 1
          ? (Math.asin(ratio) * 360) / Math.PI
          : null,
    "q_A^-1": q,
    d_A: unit === "d_A" ? x : q != null ? (2 * Math.PI) / q : null,
  };
}

export function radialFields(
  x: number,
  unit: Unit,
  wavelength?: number,
  resolution = 0.01,
): PlotField[] {
  const values = radialValues(x, unit, wavelength);
  const step = Math.abs(resolution) || 0.01;
  const low = radialValues(x - step / 2, unit, wavelength);
  const high = radialValues(x + step / 2, unit, wavelength);
  const labels: Record<Unit, [string, string]> = {
    "2th_deg": ["2θ", "Scattering angle 2θ (°)"],
    "q_A^-1": ["Q", "Scattering vector Q (Å⁻¹)"],
    d_A: ["d", "d spacing (Å)"],
  };
  return (["2th_deg", "q_A^-1", "d_A"] as Unit[]).map((target) => {
    const value = values[target];
    const changes = [low[target], high[target]]
      .filter((edge): edge is number => edge != null && Number.isFinite(edge))
      .map((edge) => Math.abs(edge - (value ?? edge)) * 2);
    const targetStep = target === unit ? step : Math.max(...changes);
    return {
      label: labels[target][0],
      title: labels[target][1],
      unit: target,
      kind: "radial",
      value:
        value == null || Number.isNaN(value)
          ? "—"
          : value === Infinity
            ? "∞"
            : value === -Infinity
              ? "−∞"
              : coordinateValue(value, targetStep),
    };
  });
}
