import { useCallback, useEffect, useRef, useState } from "react";
import type { Invoke } from "./commandContracts";
import type { PlotReading } from "./plotReadout";
import type { RingOverlay } from "./types";
import type { CrystalData } from "./singleCrystalDomain";
import { crystalPixelReading } from "./singleCrystalReadout";

type Point = {
  x: number;
  y: number;
  xResolution?: number;
  yResolution?: number;
};

/** The single-crystal click: a detector position that stays put while frames
 * change, read once at click time (like the Integration image click). With
 * an SC calibration it also carries the green constant-2θ line through the
 * point, traced from the SC geometry by the processor. It is
 * not linked to the powder modes: the scan has its own detector and geometry. */
export function useCrystalClick(
  data: CrystalData | null,
  invoke: Invoke | null,
  report: (reading: PlotReading | null) => void,
) {
  const [point, setPoint] = useState<Point | null>(null);
  const [line, setLine] = useState<RingOverlay[]>([]);
  const context = useRef({ data, invoke, report });
  context.current = { data, invoke, report };
  const epoch = useRef(0);
  const read = useCallback(async (p: Point) => {
    const seq = ++epoch.current,
      c = context.current;
    if (!c.invoke || !c.data?.image) return;
    try {
      const result = await c.invoke("scxrd_pixel", {
        x: Math.floor(p.x),
        y: Math.floor(p.y),
        contour: true,
      });
      if (seq !== epoch.current) return;
      const pixel = result.ok ? result.scxrdPixel : undefined;
      const d = context.current.data;
      setLine(pixel?.contour ?? []);
      context.current.report(
        pixel && d ? crystalPixelReading(d, p, pixel) : null,
      );
    } catch {
      /* A closed/replaced processor can reject an in-flight readout. */
    }
  }, []);
  // A different scan or detector shape invalidates the position.
  const scan = JSON.stringify([data?.firstSource, data?.shape]);
  useEffect(() => {
    ++epoch.current;
    setPoint(null);
    setLine([]);
    context.current.report(null);
  }, [scan]);
  // A new calibration changes the radial values of the same pixel.
  const geometry = JSON.stringify(data?.geometry ?? null);
  const pointRef = useRef(point);
  pointRef.current = point;
  useEffect(() => {
    if (pointRef.current) void read(pointRef.current);
  }, [geometry, read]);
  const onInspect = useCallback(
    (p: Point) => {
      const shape = context.current.data?.shape;
      if (!shape || p.x < 0 || p.y < 0 || p.x >= shape[1] || p.y >= shape[0])
        return;
      setPoint(p);
      void read(p);
    },
    [read],
  );
  return { clickedPoint: point, rings: line, onInspect };
}
