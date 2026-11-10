import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Equal, Settings2, X } from "lucide-react";
import { Button, Popover } from "./ui";
import { ScientificNumberInput } from "./ScientificNumberInput";
import { PlotToggle } from "./IntegrationPlotControls";
import { decodeRaster } from "./rasterTransfer";
import { batchRadialBin } from "./batchPlot";
import { radialFields, radialValues } from "./radialReadout";
import { intensityValue } from "./readoutNumbers";
import { usePlotTypography } from "./usePlotTypography";
import { usePlotWheel, type PlotRange } from "./usePlotNavigation";
import { unitLabel } from "./types";
import type { BatchData } from "./batchDomain";
import type { PatternPosition } from "./linkedPosition";
import type { ReportPlot } from "./plotReadout";
import {
  clamp,
  batchSurfaceSeriesKey,
  surfaceCamera,
  surfaceSampling,
  type SurfaceCamera,
  type SurfaceOrientation,
} from "./batchSurfaceGeometry";
import {
  drawBatchSurface,
  hitBatchSurface,
  type SurfaceScene,
} from "./batchSurfaceRenderer";
import "./batchSurface.css";
import {
  captureBatchSurface,
  type BatchSurfaceCaptureRef,
} from "./batchSurfaceCapture";

function readCamera(id: string): {
  camera: SurfaceCamera;
  stretch: [number, number, number];
} {
  const fallback = {
    camera: surfaceCamera(),
    stretch: [1, 1, 1] as [number, number, number],
  };
  try {
    const saved = JSON.parse(
      localStorage.getItem(`dioptas-batch:surface:${id}`) ?? "null",
    );
    if (
      saved &&
      Object.keys(fallback.camera).every((k) =>
        Number.isFinite(saved.camera?.[k]),
      ) &&
      saved.camera.zoom >= 0.25 &&
      saved.camera.zoom <= 5 &&
      saved.camera.elevation >= -89 &&
      saved.camera.elevation <= 90 &&
      saved.stretch?.length === 3 &&
      saved.stretch.every(
        (v: number) => Number.isFinite(v) && v >= 0.2 && v <= 3,
      )
    )
      return saved;
  } catch {
    /* Defaults for invalid preferences. */
  }
  return fallback;
}

/** Display-only mesh of the native-owned, currently processed binary series.
 * No integration, normalization or background extraction occurs here.
 */
export function BatchSurfaceView({
  batch,
  position,
  limits,
  log,
  sqrt,
  palette,
  range,
  step,
  ready,
  onRange,
  onSelect,
  onNormalize,
  reportPlot,
  captureRef,
}: {
  batch: BatchData;
  position?: PatternPosition;
  limits: [number, number];
  log: boolean;
  sqrt: boolean;
  palette: string;
  range: PlotRange | null;
  step: number;
  ready: boolean;
  onRange: (range: PlotRange | null) => void;
  onSelect: (index: number, position?: PatternPosition) => void;
  onNormalize: () => void;
  reportPlot: ReportPlot;
  captureRef?: BatchSurfaceCaptureRef;
}) {
  const host = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const scene = useRef<SurfaceScene | null>(null);
  const [size, setSize] = useState({ width: 600, height: 300 });
  const seriesKey = batchSurfaceSeriesKey(batch);
  const [view, setView] = useState(() => readCamera(seriesKey));
  const [settings, setSettings] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const settingsId = useId();
  const settingsButton = useRef<HTMLButtonElement>(null);
  const drag = useRef<{
    x: number;
    y: number;
    button: number;
    camera: SurfaceCamera;
    moved: boolean;
  } | null>(null);
  const typography = usePlotTypography(host);
  const values = useMemo(
    () => decodeRaster(batch.raster),
    [batch.raster.data, batch.raster.dtype],
  );
  const sampling = useMemo(
    () => surfaceSampling(batch.entries.length, batch.x.length, range, step),
    [batch.entries.length, batch.x.length, range, step],
  );
  const marker =
    position &&
    radialValues(position.x, position.unit, batch.wavelength ?? undefined)[
      batch.unit
    ];
  const scale = log ? "log" : sqrt ? "sqrt" : "linear";
  useEffect(() => {
    if (!captureRef) return;
    const capture = () =>
      host.current ? captureBatchSurface(host.current) : null;
    captureRef.current = capture;
    return () => {
      if (captureRef.current === capture) captureRef.current = null;
    };
  }, [captureRef]);
  useEffect(() => {
    const observer = new ResizeObserver(([e]) =>
      setSize({ width: e.contentRect.width, height: e.contentRect.height }),
    );
    observer.observe(host.current!);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(
        `dioptas-batch:surface:${seriesKey}`,
        JSON.stringify(view),
      );
    } catch {
      /* Session still works. */
    }
  }, [seriesKey, view]);
  useEffect(() => () => reportPlot("batch", null), [reportPlot]);
  useLayoutEffect(() => {
    scene.current = drawBatchSurface(canvas.current!, {
      batch,
      values,
      sampling,
      size,
      camera: view.camera,
      stretch: view.stretch,
      limits,
      scale,
      palette,
      marker: marker ?? null,
      font: typography.mono,
      muted: typography.muted,
    });
    setUnavailable(scene.current === null);
  }, [
    batch,
    values,
    sampling,
    size,
    view,
    limits[0],
    limits[1],
    scale,
    palette,
    marker,
    typography.mono,
    typography.muted,
  ]);
  const orient = (orientation: SurfaceOrientation) =>
    setView((v) => ({ ...v, camera: surfaceCamera(orientation) }));
  const reset = () => {
    setView({ camera: surfaceCamera(), stretch: [1, 1, 1] });
    onRange(null);
  };
  usePlotWheel(canvas, (e) =>
    setView((v) => ({
      ...v,
      camera: {
        ...v.camera,
        zoom: clamp(v.camera.zoom * Math.exp(-e.deltaY * 0.001), 0.25, 5),
      },
    })),
  );
  const pointerHit = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const hit = hitBatchSurface(
      scene.current,
      event.clientX - box.left,
      event.clientY - box.top,
    );
    if (!hit) return null;
    const bin = batchRadialBin(hit.radial, batch.x);
    if (bin == null) return null;
    return {
      frame: clamp(hit.frame, 0, batch.entries.length - 1),
      column: clamp(Math.round(bin - 0.5), 0, batch.x.length - 1),
    };
  };
  const radialEdges = [
    batch.x[sampling.firstColumn],
    batch.x[sampling.lastColumn],
  ];
  const radialMin = Math.min(...radialEdges),
    radialMax = Math.max(...radialEdges);
  const setRadialRange = (minimum: number, maximum: number) => {
    const a = batchRadialBin(minimum, batch.x),
      b = batchRadialBin(maximum, batch.x);
    if (a == null || b == null || minimum > maximum) return;
    onRange({
      xMin: Math.floor(Math.min(a, b)),
      xMax: Math.floor(Math.max(a, b)) + 1,
      yMin: range?.yMin ?? 0,
      yMax: range?.yMax ?? batch.entries.length,
    });
  };
  return (
    <div className="batch-surface-view">
      <div
        className="batch-surface-toolbar"
        role="toolbar"
        aria-label="Surface orientation"
      >
        {(["Front", "Right", "Top", "Isometric"] as const).map((name) => (
          <PlotToggle
            key={name}
            label={`${name} surface view`}
            title={`Set ${name.toLowerCase()} view`}
            pressed={
              view.camera.azimuth === surfaceCamera(name).azimuth &&
              view.camera.elevation === surfaceCamera(name).elevation
            }
            onClick={() => orient(name)}
          >
            {name === "Isometric" ? "Iso" : name}
          </PlotToggle>
        ))}
        <Button
          ref={settingsButton}
          aria-label="Surface ranges and proportions"
          title="Radial range and axis proportions"
          aria-expanded={settings}
          aria-controls={settingsId}
          onClick={() => setSettings((v) => !v)}
        >
          <Settings2 size={15} />
        </Button>
        <PlotToggle
          label="Normalize batch surface"
          title="Normalize using the Batch region"
          pressed={batch.normalized}
          disabled={!ready}
          onClick={onNormalize}
        >
          <Equal size={15} />
        </PlotToggle>
        <span
          className="batch-surface-sampling"
          title={`Display sampling only. Frame stride ${sampling.frameStep}; radial stride ${sampling.columnStep}. Stored data and exports retain every sample.`}
        >
          {sampling.frames.length} × {sampling.columns.length} · step{" "}
          {sampling.frameStep}
        </span>
      </div>
      {settings && (
        <Popover
          id={settingsId}
          className="batch-surface-settings"
          role="group"
          aria-label="Surface settings"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setSettings(false);
              settingsButton.current?.focus();
            }
          }}
        >
          <Button
            className="batch-surface-close"
            aria-label="Close surface settings"
            onClick={() => {
              setSettings(false);
              settingsButton.current?.focus();
            }}
          >
            <X size={15} />
          </Button>
          <SurfaceNumber
            label={`Surface radial minimum ${unitLabel(batch.unit)}`}
            value={radialMin}
            onCommit={(n) => setRadialRange(n, radialMax)}
          />
          <SurfaceNumber
            label={`Surface radial maximum ${unitLabel(batch.unit)}`}
            value={radialMax}
            onCommit={(n) => setRadialRange(radialMin, n)}
          />
          {(["Frame", "Radial", "Intensity"] as const).map((label, i) => (
            <SurfaceNumber
              key={label}
              label={`${label} axis proportion`}
              value={view.stretch[i]}
              onCommit={(n) => {
                if (n >= 0.2 && n <= 3)
                  setView((v) => ({
                    ...v,
                    stretch: v.stretch.map((x, j) => (j === i ? n : x)) as [
                      number,
                      number,
                      number,
                    ],
                  }));
              }}
            />
          ))}
          <Button onClick={reset}>Reset surface and ranges</Button>
          <p>
            Drag to rotate; right drag to pan; wheel to zoom. F fits; R/T/I
            orient. Arrows move the frame or radial marker. Start/Stop/Step are
            in Batch Options.
          </p>
        </Popover>
      )}
      <div ref={host} className="batch-surface-canvas">
        <canvas
          ref={canvas}
          data-testid="batch-surface"
          data-unit={batch.unit}
          data-intensity-scale={scale}
          data-palette={palette}
          data-frame-step={sampling.frameStep}
          data-column-step={sampling.columnStep}
          data-vertices={sampling.frames.length * sampling.columns.length}
          data-frame-first={sampling.firstRow + 1}
          data-frame-last={sampling.lastRow + 1}
          data-radial-first={radialEdges[0]}
          data-radial-last={radialEdges[1]}
          data-azimuth={view.camera.azimuth}
          data-elevation={view.camera.elevation}
          data-zoom={view.camera.zoom}
          data-selected-frame={batch.selected + 1}
          data-linked-position={marker ?? undefined}
          data-normalized={batch.normalized}
          aria-label="Batch 3D intensity surface"
          aria-description={`Frame and ${unitLabel(batch.unit)} axes; ${scale} intensity. Frame ${batch.selected + 1}: ${batch.entries[batch.selected]?.name}, source frame ${batch.entries[batch.selected]?.frame ?? 1}. Display frame stride ${sampling.frameStep}, radial stride ${sampling.columnStep}.`}
          tabIndex={0}
          onContextMenu={(e) => e.preventDefault()}
          onPointerDown={(e) => {
            if (e.button !== 0 && e.button !== 2) return;
            e.currentTarget.focus();
            e.currentTarget.setPointerCapture(e.pointerId);
            drag.current = {
              x: e.clientX,
              y: e.clientY,
              button: e.button,
              camera: view.camera,
              moved: false,
            };
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (d) {
              const dx = e.clientX - d.x,
                dy = e.clientY - d.y;
              d.moved ||= Math.hypot(dx, dy) > 3;
              if (d.moved)
                setView((v) => ({
                  ...v,
                  camera:
                    d.button === 2
                      ? {
                          ...d.camera,
                          panX: d.camera.panX + dx,
                          panY: d.camera.panY + dy,
                        }
                      : {
                          ...d.camera,
                          azimuth: d.camera.azimuth + dx * 0.5,
                          elevation: clamp(
                            d.camera.elevation + dy * 0.5,
                            -89,
                            90,
                          ),
                        },
                }));
              return;
            }
            const hit = pointerHit(e);
            if (!hit) {
              reportPlot("batch", null);
              return;
            }
            const value = values[hit.frame * batch.x.length + hit.column];
            const fields = [
              {
                label: "Frame",
                value: String(hit.frame + 1),
                kind: "pixel" as const,
              },
              {
                label: "I",
                value: intensityValue(value),
                kind: "intensity" as const,
              },
              ...radialFields(
                batch.x[hit.column],
                batch.unit,
                batch.wavelength ?? undefined,
              ),
            ];
            reportPlot("batch", {
              fields,
              text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
              hint: `${batch.entries[hit.frame].name} · source frame ${batch.entries[hit.frame].frame}. Click to inspect; drag to rotate; right drag to pan.`,
            });
          }}
          onPointerUp={(e) => {
            const d = drag.current;
            drag.current = null;
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              e.currentTarget.releasePointerCapture(e.pointerId);
            if (!d || d.moved) return;
            if (d.button === 2) {
              setView((v) => ({
                ...v,
                camera: {
                  ...v.camera,
                  zoom: clamp(v.camera.zoom / 2, 0.25, 5),
                },
              }));
              return;
            }
            const hit = pointerHit(e);
            if (hit && ready)
              onSelect(hit.frame, { x: batch.x[hit.column], unit: batch.unit });
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
          onPointerLeave={() => reportPlot("batch", null)}
          onDoubleClick={(e) => {
            if (e.button === 2) {
              e.preventDefault();
              reset();
            }
          }}
          onKeyDown={(e) => {
            const key = e.key.toLowerCase();
            if (key === "f") {
              e.preventDefault();
              reset();
              return;
            }
            const orientation = (
              { r: "Right", t: "Top", i: "Isometric" } as const
            )[key as "r" | "t" | "i"];
            if (orientation) {
              e.preventDefault();
              orient(orientation);
              return;
            }
            if (
              !ready ||
              ![
                "ArrowUp",
                "ArrowDown",
                "ArrowLeft",
                "ArrowRight",
                "Home",
                "End",
              ].includes(e.key)
            )
              return;
            e.preventDefault();
            let frame = batch.selected;
            if (e.key === "ArrowUp")
              frame = clamp(frame + step, sampling.firstRow, sampling.lastRow);
            if (e.key === "ArrowDown")
              frame = clamp(frame - step, sampling.firstRow, sampling.lastRow);
            if (e.key === "Home") frame = sampling.firstRow;
            if (e.key === "End") frame = sampling.lastRow;
            const bin =
              marker == null
                ? sampling.firstColumn
                : Math.round((batchRadialBin(marker, batch.x) ?? 0.5) - 0.5);
            const col = clamp(
              bin +
                (e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0),
              sampling.firstColumn,
              sampling.lastColumn,
            );
            onSelect(frame, { x: batch.x[col], unit: batch.unit });
          }}
        />
        {unavailable && (
          <div className="batch-surface-error" role="alert">
            3D drawing is unavailable. Use the 2D view.
          </div>
        )}
      </div>
    </div>
  );
}

function SurfaceNumber({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number;
  onCommit: (n: number) => void;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  return (
    <label>
      {label}
      <ScientificNumberInput
        aria-label={label}
        value={text}
        onValueChange={setText}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
        onBlur={() => {
          if (text.trim() && Number.isFinite(Number(text)))
            onCommit(Number(text));
          setText(String(value));
        }}
      />
    </label>
  );
}
