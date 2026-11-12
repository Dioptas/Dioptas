import type { PlotReading } from "./plotReadout";
import type { CrystalData } from "./singleCrystalDomain";
import { coordinateValue, intensityValue } from "./readoutNumbers.ts";
import { radialFields } from "./radialReadout.ts";
export function crystalPixelReading(
  data: Pick<CrystalData, "shape" | "config" | "frame" | "geometry">,
  point: { x: number; y: number; xResolution?: number; yResolution?: number },
  pixel: { value: number | null; twoTheta: number | null },
): PlotReading {
  const row = data.shape[0] - 1 - point.y;
  const fields: NonNullable<PlotReading["fields"]> = [
    {
      label: "x",
      value: coordinateValue(point.x, point.xResolution),
      kind: "pixel",
    },
    {
      label: "y",
      value: coordinateValue(row, point.yResolution),
      kind: "pixel",
    },
    { label: "I", value: intensityValue(pixel.value), kind: "intensity" },
    {
      label: "ω",
      value:
        (
          data.config.omega_start +
          data.frame * data.config.omega_step +
          data.config.exposure / 2
        ).toFixed(3) + "°",
      kind: "coordinate",
    },
  ];
  if (pixel.twoTheta != null)
    fields.push(
      ...radialFields(
        pixel.twoTheta,
        "2th_deg",
        data.geometry ? data.geometry.wavelength * 1e-10 : undefined,
      ),
    );
  return {
    text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
    fields,
    x: point.x,
    row,
    value: pixel.value,
    hint: "Left drag zooms · right drag pans · right double-click restores the fitted view.",
  };
}
