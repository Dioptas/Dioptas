import { useCallback, useEffect, useRef } from "react";
import type { Invoke } from "./commandContracts";
import type { ReportPlot } from "./plotReadout";
import type { CrystalData } from "./singleCrystalDomain";
import { crystalPixelReading } from "./singleCrystalReadout";
export function useCrystalHover(
  data: CrystalData | null,
  invoke: Invoke | null,
  report: ReportPlot,
  active: boolean,
) {
  const latest = useRef<{
    x: number;
    y: number;
    xResolution?: number;
    yResolution?: number;
  } | null>(null);
  const epoch = useRef(0),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    running = useRef(false),
    last = useRef(0);
  const context = useRef({ data, invoke, report, active });
  context.current = { data, invoke, report, active };
  const clear = useCallback(() => {
    ++epoch.current;
    latest.current = null;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    report("detector", null);
  }, [report]);
  useEffect(() => {
    clear();
    return clear;
  }, [
    active,
    data?.frame,
    data?.frames,
    data?.shape[0],
    data?.shape[1],
    data?.previewKind,
    data?.image?.bufferId,
    JSON.stringify(data?.geometry),
    clear,
  ]);
  const schedule = useCallback(function sample() {
    if (timer.current || running.current || !latest.current) return;
    timer.current = setTimeout(
      async () => {
        timer.current = null;
        const p = latest.current,
          c = context.current;
        if (!p || !c.invoke || !c.active || !c.data?.frames || !c.data.image)
          return;
        const x = Math.floor(p.x),
          y = Math.floor(p.y);
        if (
          !Number.isFinite(x) ||
          !Number.isFinite(y) ||
          x < 0 ||
          y < 0 ||
          x >= c.data.shape[1] ||
          y >= c.data.shape[0]
        ) {
          c.report("detector", null);
          return;
        }
        const seq = epoch.current;
        running.current = true;
        last.current = performance.now();
        try {
          const result = await c.invoke("scxrd_pixel", {
            x,
            y,
          });
          if (seq !== epoch.current) return;
          if (!result.ok) {
            c.report("detector", null);
            return;
          }
          const pixel = result.scxrdPixel;
          if (!pixel) {
            c.report("detector", null);
            return;
          }
          c.report("detector", crystalPixelReading(c.data, p, pixel));
        } catch {
          /* A closed/replaced processor can reject an in-flight readout. */
          if (seq === epoch.current) c.report("detector", null);
        } finally {
          running.current = false;
          if (latest.current && latest.current !== p) sample();
        }
      },
      Math.max(0, 100 - (performance.now() - last.current)),
    );
  }, []);
  return useCallback(
    (point: typeof latest.current) => {
      latest.current = point;
      if (!point || !context.current.active) clear();
      else schedule();
    },
    [clear, schedule],
  );
}
