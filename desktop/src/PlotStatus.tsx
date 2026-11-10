import { cakeSourceCoordinate } from "./cakeRadialAxis";
import type { Cake, Response } from "./types";
import type {
  PatternHover,
  PlotField,
  PlotReading,
  PlotSource,
} from "./plotReadout";
import { radialFields } from "./radialReadout";

import { intensityValue as value, coordinateValue } from "./readoutNumbers";
export { coordinateValue } from "./readoutNumbers";

export type SourcedReading = PlotReading & { source: PlotSource };
export function detectorReading(
  pixel: NonNullable<Response["pixel"]>,
  row: number,
  wavelength?: number,
): PlotReading {
  const fields: PlotField[] = [
    { label: "x", value: String(pixel.x), kind: "pixel" },
    { label: "y", value: String(row), kind: "pixel" },
    { label: "I", value: value(pixel.value), kind: "intensity" },
    ...(pixel.twoTheta === undefined
      ? []
      : radialFields(
          pixel.twoTheta,
          "2th_deg",
          wavelength,
          pixel.twoThetaResolution,
        )),
  ];
  return {
    x: pixel.x,
    row,
    value: pixel.value,
    fields,
    text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
  };
}
export function patternReading(
  point: PatternHover,
  wavelength?: number,
): PlotReading {
  const fields: PlotField[] = [
    ...radialFields(point.x, point.unit, wavelength, point.xResolution),
    {
      label: "y",
      value: coordinateValue(point.mouseY, point.yResolution),
      title: "Mouse intensity coordinate",
      kind: "coordinate",
    },
    {
      label: "I",
      value: value(point.y),
      title: "Pattern intensity at the nearest radial sample",
      kind: "intensity",
    },
  ];
  return {
    fields,
    text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
    hint: point.hint,
  };
}
export function cakeCoordinates(cake: Cake, point: { x: number; y: number }) {
  return {
    x: cakeSourceCoordinate(cake, point.x),
    azimuth:
      cake.azimuthRange[0] +
      (point.y / cake.fullHeight) *
        (cake.azimuthRange[1] - cake.azimuthRange[0]),
  };
}
export function cakeReading(
  cake: Cake,
  point: {
    x: number;
    y: number;
    value: number | null;
    xResolution?: number;
    yResolution?: number;
  },
  wavelength?: number,
): PlotReading {
  const coords = cakeCoordinates(cake, point);
  const fields: PlotField[] = [
    ...radialFields(
      coords.x,
      cake.unit,
      wavelength,
      ((point.xResolution ?? 1) / Math.max(1, cake.fullWidth - 1)) *
        (cake.radialRange[1] - cake.radialRange[0]),
    ),
    {
      label: "χ",
      title: "Azimuth χ (°)",
      kind: "coordinate",
      value: coordinateValue(
        coords.azimuth,
        ((point.yResolution ?? 1) / cake.fullHeight) *
          (cake.azimuthRange[1] - cake.azimuthRange[0]),
      ),
    },
    { label: "I", value: value(point.value), kind: "intensity" },
  ];
  return {
    fields,
    text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
  };
}
export function ReadingFields({ reading }: { reading: PlotReading }) {
  const fields: PlotField[] | null =
    reading.fields ??
    (reading.x !== undefined
      ? [
          { label: "x", value: String(reading.x), kind: "pixel" },
          { label: "y", value: String(reading.row), kind: "pixel" },
          { label: "I", value: value(reading.value), kind: "intensity" },
        ]
      : null);
  return fields
    ? fields.map((field, i) => (
        <span
          className={`plot-coordinate plot-field-${i}`}
          key={field.label}
          title={field.title}
          data-unit={field.unit}
          data-field={field.label}
          data-kind={field.kind}
        >
          <span>{field.label} </span>
          <span
            className="plot-coordinate-value"
            style={
              field.value.length >
              (field.kind === "pixel"
                ? 4
                : field.kind === "coordinate"
                  ? 6.5
                  : 6)
                ? { width: `${field.value.length}ch` }
                : undefined
            }
          >
            {field.value}
          </span>
        </span>
      ))
    : reading.text;
}
export const sourceLabel = (source: PlotSource) =>
  ({
    detector: "Image",
    cake: "Cake",
    pattern: "Pattern",
    map: "Map",
    batch: "Batch",
  })[source];
