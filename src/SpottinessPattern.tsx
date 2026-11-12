import {
  useCallback,
  useMemo,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentProps,
} from "react";
import { LayoutDivider } from "./LayoutDivider";
import {
  layoutKeys,
  readLayoutNumber,
  saveLayoutValue,
} from "./layoutPreferences";
import { PatternView } from "./PatternView";
import type { PlotRange } from "./usePlotNavigation";
import type { Unit } from "./types";
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
}: ComponentProps<typeof PatternView<Unit>> & {
  enabled: boolean;
  relative: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [preferredShare, setPreferredShare] = useState(() =>
    readLayoutNumber(layoutKeys.spottinessShare, 60, 10, 90),
  );
  const [height, setHeight] = useState(360);
  const visible = enabled && !!props.pattern.spottiness;
  useLayoutEffect(() => {
    const node = container.current;
    if (!visible || !node) return;
    const measure = () => setHeight(node.clientHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [visible]);
  // Keep both plots usable in a compact workspace, retaining the preferred
  // ratio when a temporarily smaller window constrains either pane.
  const available = Math.max(1, height - 8);
  const minShare = Math.min(45, (100 * 100) / available);
  const maxShare = 100 - Math.min(45, (112 * 100) / available);
  const share = Math.max(minShare, Math.min(maxShare, preferredShare));
  const changeShare = (next: number) => {
    const value = Math.max(minShare, Math.min(maxShare, next));
    setPreferredShare(value);
    saveLayoutValue(layoutKeys.spottinessShare, value);
  };
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
    <div
      ref={container}
      className="spottiness-plots"
      data-testid="spottiness-plots"
      style={{
        gridTemplateRows: `minmax(0, ${share}fr) 8px minmax(0, ${100 - share}fr)`,
      }}
    >
      <div className="spottiness-main">
        <PatternView
          {...props}
          viewport={mainViewport}
          onViewChange={report}
          axisLeft={90}
          showXAxis={false}
        />
      </div>
      <LayoutDivider
        className="integration-divider integration-divider-horizontal spottiness-divider"
        label="Pattern and Spottiness divider"
        orientation="horizontal"
        value={share}
        min={minShare}
        max={maxShare}
        defaultValue={60}
        onChange={changeShare}
        pointerValue={(event) => {
          const box = container.current?.getBoundingClientRect();
          return box ? ((event.clientY - box.top - 4) / available) * 100 : null;
        }}
      />
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
