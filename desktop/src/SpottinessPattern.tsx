import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from "react";
import { PatternView } from "./PatternView";
import type { PlotRange } from "./usePlotNavigation";
import type { PlotViewport } from "./plotViewport";
import "./spottiness.css";
const same = (a: PlotRange, b: PlotRange) =>
  a.xMin === b.xMin &&
  a.xMax === b.xMax &&
  a.yMin === b.yMin &&
  a.yMax === b.yMax;

/** Linked radial navigation with independent diagnostic y limits. */
export function SpottinessPattern({
  enabled,
  relative,
  ...props
}: ComponentProps<typeof PatternView> & {
  enabled: boolean;
  relative: boolean;
}) {
  const key = props.viewport?.key ?? props.pattern.unit;
  const [reported, setReported] = useState<{
    key: string;
    range: PlotRange;
  } | null>(null);
  const [, render] = useState(0);
  const fallback = useRef<PlotRange | null>(null);
  const diagnosticY = useRef<{ key: string; range: PlotRange | null }>({
    key: "",
    range: null,
  });
  const report = useCallback(
    (range: PlotRange) => {
      setReported((old) =>
        old?.key === key && same(old.range, range) ? old : { key, range },
      );
    },
    [key],
  );
  const mainRange = reported?.key === key ? reported.range : null;
  const mainViewport: PlotViewport = {
    key,
    read: () => (props.viewport ? props.viewport.read() : fallback.current),
    write: (range) => {
      if (props.viewport) props.viewport.write(range);
      else fallback.current = range;
      props.onAutoRange?.(!range);
      render((v) => v + 1);
    },
  };
  const data = props.pattern.spottiness;
  const diagnostic = useMemo(
    () =>
      data
        ? {
            x: data.x,
            y: relative ? data.relative : data.std,
            unit: props.pattern.unit,
          }
        : null,
    [data, relative, props.pattern.unit],
  );
  const yKey = `${key}:${relative}`;
  if (diagnosticY.current.key !== yKey)
    diagnosticY.current = { key: yKey, range: null };
  const diagnosticViewport: PlotViewport = {
    key: yKey,
    read: () => {
      if (!mainRange) return null;
      const saved = diagnosticY.current.range;
      let min = Infinity,
        max = -Infinity;
      if (!saved && diagnostic)
        for (let i = 0; i < diagnostic.x.length; i++) {
          const y = diagnostic.y[i];
          if (
            diagnostic.x[i] >= mainRange.xMin &&
            diagnostic.x[i] <= mainRange.xMax &&
            y != null &&
            Number.isFinite(y)
          ) {
            min = Math.min(min, y);
            max = Math.max(max, y);
          }
        }
      if (!Number.isFinite(min)) {
        min = 0;
        max = 1;
      }
      const pad = Math.max((max - min) * 0.04, Math.abs(min) * 1e-6, 1e-6);
      return {
        ...mainRange,
        yMin: saved?.yMin ?? min - pad,
        yMax: saved?.yMax ?? max + pad,
      };
    },
    write: (range) => {
      diagnosticY.current = { key: yKey, range };
      mainViewport.write(
        range && mainRange
          ? { ...mainRange, xMin: range.xMin, xMax: range.xMax }
          : null,
      );
      if (!range) setReported(null);
    },
  };
  if (!enabled || !diagnostic) return <PatternView {...props} />;
  return (
    <div className="spottiness-plots" data-testid="spottiness-plots">
      <div className="spottiness-main">
        <PatternView
          {...props}
          viewport={mainViewport}
          onViewChange={report}
          axisLeft={90}
        />
      </div>
      <section
        className="spottiness-diagnostic"
        aria-label="Spottiness diagnostic"
      >
        <PatternView
          pattern={diagnostic}
          referenceLines={props.referenceLines}
          referenceMode="full-height"
          viewport={diagnosticViewport}
          compact={props.compact}
          axisLeft={90}
          log={false}
          antialias={props.antialias}
          yLabel={relative ? "std / mean" : "Azimuthal std"}
          valueLabel={relative ? "std/mean" : "std"}
          plotLabel="Spottiness diagnostic"
          zoomMode={props.zoomMode}
          onZoomMode={props.onZoomMode}
          linkedPosition={props.linkedPosition}
          onHover={props.onHover}
          onPick={props.onPick}
          hoverHint="Population azimuthal spread · original integrated mean before pattern background subtraction · undefined ratios are omitted"
        />
      </section>
    </div>
  );
}
