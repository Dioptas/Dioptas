import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Equal, Settings2, X } from "lucide-react";
import { Button, Popover, Select } from "./ui";
import { disposeSurfaceGPU } from "./WebGLSurface";
import {
  surfacePhaseFrameHeights,
  type SurfacePhaseStyle,
} from "./batchSurfaceGuides";
import { ScientificNumberInput } from "./ScientificNumberInput";
import { PlotToggle } from "./IntegrationPlotControls";
import { decodeRaster } from "./rasterTransfer";
import { batchRadialBin } from "./batchPlot";
import { radialFields, radialValues } from "./radialReadout";
import { intensityValue } from "./readoutNumbers";
import { usePlotTypography } from "./usePlotTypography";
import {
  isPlotSecondaryGesture,
  usePlotWheel,
  type PlotRange,
} from "./usePlotNavigation";
import { unitLabel } from "./types";
import type { BatchData } from "./batchDomain";
import type { PatternPosition } from "./linkedPosition";
import type { ReportPlot } from "./plotReadout";
import {
  clamp,
  batchSurfaceSeriesKey,
  surfaceCamera,
  surfaceSampling,
  surfaceResolutions,
  type SurfaceResolution,
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
  phaseLines,
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
  phaseLines?: BatchData["phaseLines"];
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
  const [renderer, setRenderer] = useState("canvas");
  const [appearance, setAppearance] = useState<{
    contours: boolean;
    phaseStyle: SurfacePhaseStyle;
  }>(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("dioptas-batch:surface-appearance") ?? "null",
      );
      return {
        contours: saved?.contours !== false,
        phaseStyle: saved?.phaseStyle === "planes" ? "planes" : "lines",
      };
    } catch {
      return { contours: true, phaseStyle: "lines" };
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(
        "dioptas-batch:surface-appearance",
        JSON.stringify(appearance),
      );
    } catch {
      /* Keep session preferences. */
    }
  }, [appearance]);
  const [resolution, setResolution] = useState<SurfaceResolution>(() => {
    try {
      const saved = localStorage.getItem("dioptas-batch:surface-resolution");
      if (saved === "fast" || saved === "fine") return saved;
    } catch {
      /* Default detail. */
    }
    return "high";
  });
  const [interacting, setInteracting] = useState(false);
  const lastHover = useRef(-Infinity);
  const rightClick = useRef<{ time: number; x: number; y: number } | null>(
    null,
  );
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
    () =>
      surfaceSampling(
        batch.entries.length,
        batch.x.length,
        range,
        step,
        interacting ? "fast" : resolution,
      ),
    [
      batch.entries.length,
      batch.x.length,
      range,
      step,
      interacting,
      resolution,
    ],
  );
  const marker =
    position &&
    radialValues(position.x, position.unit, batch.wavelength ?? undefined)[
      batch.unit
    ];
  const scale = log ? "log" : sqrt ? "sqrt" : "linear";
  const hasPhases = !!phaseLines?.length;
  const phaseHeights = useMemo(
    () =>
      appearance.phaseStyle === "planes" && hasPhases
        ? surfacePhaseFrameHeights(
            values,
            batch.x.length,
            sampling,
            limits,
            scale,
          )
        : undefined,
    [
      values,
      batch.x.length,
      sampling,
      limits[0],
      limits[1],
      scale,
      appearance.phaseStyle,
      hasPhases,
    ],
  );
  useEffect(() => {
    try {
      localStorage.setItem("dioptas-batch:surface-resolution", resolution);
    } catch {
      /* Keep session preference. */
    }
  }, [resolution]);
  useEffect(() => {
    const element = canvas.current!;
    return () => {
      disposeSurfaceGPU(element);
    };
  }, []);
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
      contours: appearance.contours,
      phaseStyle: appearance.phaseStyle,
      phaseLines,
      phaseHeights,
    });
    setUnavailable(scene.current === null);
    setRenderer(canvas.current?.dataset.renderer ?? "canvas");
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
    appearance,
    phaseLines,
    phaseHeights,
  ]);
  const orient = (orientation: SurfaceOrientation) => {
    rightClick.current = null;
    setView((v) => ({ ...v, camera: surfaceCamera(orientation) }));
  };
  const reset = () => {
    rightClick.current = null;
    setView({ camera: surfaceCamera(), stretch: [1, 1, 1] });
    onRange(null);
  };
  usePlotWheel(canvas, (e) => {
    rightClick.current = null;
    setView((v) => ({
      ...v,
      camera: {
        ...v.camera,
        zoom: clamp(v.camera.zoom * Math.exp(-e.deltaY * 0.001), 0.25, 5),
      },
    }));
  });
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
        className="batch-surface-toolbar plot-controls"
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
        <PlotToggle
          label="Normalize batch surface"
          title="Normalize using the Batch region"
          pressed={batch.normalized}
          disabled={!ready}
          onClick={onNormalize}
        >
          <Equal size={15} />
        </PlotToggle>
        <Button
          ref={settingsButton}
          className="batch-surface-settings-toggle"
          aria-label="Surface ranges and proportions"
          title="Radial range and axis proportions"
          aria-expanded={settings}
          aria-pressed={settings}
          aria-controls={settingsId}
          onClick={() => setSettings((v) => !v)}
        >
          <Settings2 size={15} />
        </Button>
        <span
          className="batch-surface-sampling"
          title={`${surfaceResolutions[resolution].label} display detail${interacting ? "; lighter mesh while moving" : ""}. Frame stride ${sampling.frameStep}; radial stride ${sampling.columnStep}. Stored data and exports retain every sample.`}
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
          <label>
            Surface
            <Select
              aria-label="Surface appearance"
              value={appearance.contours ? "contours" : "plain"}
              onChange={(e) => {
                const contours = e.currentTarget.value === "contours";
                setAppearance((a) => ({
                  ...a,
                  contours,
                }));
              }}
            >
              <option value="contours">With contours</option>
              <option value="plain">Plain</option>
            </Select>
          </label>
          <label>
            Phase guides
            <Select
              aria-label="Surface phase guides"
              value={appearance.phaseStyle}
              onChange={(e) => {
                const phaseStyle = e.currentTarget.value as SurfacePhaseStyle;
                setAppearance((a) => ({
                  ...a,
                  phaseStyle,
                }));
              }}
            >
              <option value="lines">Surface lines</option>
              <option value="planes">Reference planes</option>
            </Select>
          </label>
          <p>
            Use the Phases icon to show the visible reference phases in their
            existing colors.
          </p>
          {appearance.phaseStyle === "planes" && (
            <p>
              Plane heights follow relative reflection intensities, scaled to
              each frame’s visible pattern maximum.
            </p>
          )}
          {renderer !== "webgl2" && appearance.phaseStyle === "planes" && (
            <p role="status">
              Reference planes require GPU drawing; showing surface lines.
            </p>
          )}
          <label>
            Resolution
            <Select
              aria-label="Surface resolution"
              value={resolution}
              onChange={(e) =>
                setResolution(e.currentTarget.value as SurfaceResolution)
              }
            >
              {Object.entries(surfaceResolutions).map(([value, preset]) => (
                <option key={value} value={value}>
                  {preset.label}
                </option>
              ))}
            </Select>
          </label>
          <p role="status">
            {renderer === "webgl2" ? "GPU drawing" : "Canvas fallback"} · Higher
            detail uses more stored samples. Zooming keeps the selected detail;
            rotation and panning use a lighter mesh while moving.
          </p>
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
          data-resolution={resolution}
          data-detail={interacting ? "moving" : "settled"}
          data-frame-first={sampling.firstRow + 1}
          data-frame-last={sampling.lastRow + 1}
          data-radial-first={radialEdges[0]}
          data-radial-last={radialEdges[1]}
          data-azimuth={view.camera.azimuth}
          data-elevation={view.camera.elevation}
          data-zoom={view.camera.zoom}
          data-pan-x={view.camera.panX}
          data-pan-y={view.camera.panY}
          data-selected-frame={batch.selected + 1}
          data-linked-position={marker ?? undefined}
          data-normalized={batch.normalized}
          aria-label="Batch 3D intensity surface"
          aria-description={`Frame and ${unitLabel(batch.unit)} axes; ${scale} intensity. Frame ${batch.selected + 1}: ${batch.entries[batch.selected]?.name}, source frame ${batch.entries[batch.selected]?.frame ?? 1}. Display frame stride ${sampling.frameStep}, radial stride ${sampling.columnStep}.`}
          tabIndex={0}
          onContextMenu={(e) => e.preventDefault()}
          onPointerDown={(e) => {
            if (e.button !== 0 && e.button !== 2) return;
            const secondary = isPlotSecondaryGesture(e);
            if (!secondary) rightClick.current = null;
            e.currentTarget.focus();
            e.currentTarget.setPointerCapture(e.pointerId);
            drag.current = {
              x: e.clientX,
              y: e.clientY,
              button: secondary ? 2 : 0,
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
              if (d.moved) {
                rightClick.current = null;
                setInteracting(true);
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
                          azimuth: d.camera.azimuth - dx * 0.5,
                          elevation: clamp(
                            d.camera.elevation + dy * 0.5,
                            -89,
                            90,
                          ),
                        },
                }));
              }
              return;
            }
            const now = performance.now();
            if (now - lastHover.current < 75) return;
            lastHover.current = now;
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
            setInteracting(false);
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              e.currentTarget.releasePointerCapture(e.pointerId);
            if (!d || d.moved) return;
            if (d.button === 2) {
              const previous = rightClick.current;
              if (
                previous &&
                e.timeStamp - previous.time <= 450 &&
                Math.hypot(e.clientX - previous.x, e.clientY - previous.y) <= 6
              ) {
                reset();
                return;
              }
              rightClick.current = {
                time: e.timeStamp,
                x: e.clientX,
                y: e.clientY,
              };
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
            rightClick.current = null;
            drag.current = null;
            setInteracting(false);
          }}
          onPointerLeave={() => reportPlot("batch", null)}
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
