import { useCallback, useEffect, useRef } from "react";
import { intensityValue } from "./readoutNumbers";
import { radialFields } from "./radialReadout";
import type { CorrectionPreview } from "./correctionPreview";
import type { PlotReading, ReportPlot } from "./plotReadout";
import type { Response } from "./types";

type Point = { x: number; y: number; value: number | null };
export type PreviewGeometrySample = (point: {
  x: number;
  y: number;
}) => Promise<Response["pixel"] | undefined>;

/** One trailing 10 Hz readout. Map values come from the native display buffer;
 * geometry-only queries add 2θ/Q/d without ever substituting image counts. */
export function useCorrectionPreviewReadout(
  map: CorrectionPreview,
  wavelength: number | undefined,
  report: ReportPlot,
  sampleGeometry: PreviewGeometrySample,
) {
  const latest = useRef<Point | null>(null);
  const sampler = useRef(sampleGeometry);
  sampler.current = sampleGeometry;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef(false),
    epoch = useRef(0),
    alive = useRef(true),
    last = useRef(0);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      ++epoch.current;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
  const schedule = useCallback(
    function scheduleReading() {
      if (!alive.current || timer.current || pending.current || !latest.current)
        return;
      timer.current = setTimeout(
        async () => {
          timer.current = null;
          const point = latest.current;
          if (!point || !alive.current) return;
          const generation = epoch.current;
          last.current = performance.now();
          pending.current = true;
          const x = Math.floor(point.x),
            y = Math.floor(point.y);
          const fields: NonNullable<PlotReading["fields"]> = [
            { label: "x", value: String(x), kind: "pixel" },
            {
              label: "y",
              value: String(map.raster.fullHeight - 1 - y),
              kind: "pixel",
            },
            {
              label: map.units === "mm" ? "Integral (mm)" : "Factor",
              value: intensityValue(point.value),
              title: `${map.label} (${map.units}); image is divided by this map`,
              kind: "intensity",
            },
          ];
          try {
            const pixel = await sampler.current({ x, y });
            if (pixel?.twoTheta !== undefined)
              fields.push(
                ...radialFields(
                  pixel.twoTheta,
                  "2th_deg",
                  wavelength,
                  pixel.twoThetaResolution,
                ),
              );
          } catch {
            /* A replaced processor/source cannot overwrite a newer readout. */
          }
          pending.current = false;
          if (alive.current && generation === epoch.current && latest.current) {
            report("detector", {
              x,
              row: map.raster.fullHeight - 1 - y,
              value: point.value,
              fields,
              text: `${map.label}: ${intensityValue(point.value)} ${map.units}`,
              hint: `${map.label} · ${map.units} · divisor · Back restores the image view`,
            });
          }
          if (latest.current !== point) scheduleReading();
        },
        Math.max(0, 100 - (performance.now() - last.current)),
      );
    },
    [map.label, map.units, map.raster.fullHeight, wavelength, report],
  );
  return useCallback(
    (point: Point | null) => {
      latest.current = point;
      if (!point) {
        ++epoch.current;
        if (timer.current) clearTimeout(timer.current);
        timer.current = null;
        report("detector", null);
      } else schedule();
    },
    [schedule, report],
  );
}
