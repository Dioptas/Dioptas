import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { Maximize2, Minimize2, Save, MoveHorizontal } from "lucide-react";
import { RasterView } from "./RasterView";
import { PatternView } from "./PatternView";
import { ImageIntensity } from "./ImageIntensity";
import { MapControls } from "./MapControls";
import { radialValues } from "./radialReadout";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import {
  number,
  type Pattern,
  type Raster,
  type Response,
  type State,
  type Unit,
} from "./types";
import type { MapData, MapRun } from "./mapDomain";
import type { ReportPlot, PatternHover } from "./plotReadout";
import type { ZoomMode } from "./usePlotNavigation";
import "./map.css";

function useDisplay(raster: Raster | null, name: string) {
  const [limits, setLimits] = useState<[number, number]>([0, 1]);
  const [log, setLog] = useState(false),
    [palette, setPalette] = useState("grey");
  const [prefs, setPrefs] = useImageDisplayPreferences(
    name,
    "horizontal",
    false,
  );
  useEffect(() => {
    if (raster) setLimits(raster.limits);
  }, [raster?.data]);
  return {
    limits,
    setLimits,
    log,
    setLog,
    palette,
    setPalette,
    prefs,
    setPrefs,
  };
}
function usePreference<T extends string | number | boolean>(
  name: string,
  fallback: T,
) {
  const key = `dioptas-map:${name}`;
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(key) ?? "null");
      return typeof stored === typeof fallback &&
        (typeof stored !== "number" || Number.isFinite(stored))
        ? stored
        : fallback;
    } catch {
      return fallback;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* Session-only preference. */
    }
  }, [key, value]);
  return [value, setValue] as const;
}

export function MapView({
  map,
  image,
  mask,
  pattern,
  state,
  ready,
  error,
  run,
  request,
  mapLevels,
  reportPlot,
  onDetectorHover,
  onPatternHover,
  patternZoom,
  onPatternZoom,
}: {
  map: MapData | null;
  image: Raster | null;
  mask: Raster | null;
  pattern: Pattern | null;
  state: State | null;
  ready: boolean;
  error?: string | null;
  run: MapRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  mapLevels?: [number, number];
  reportPlot: ReportPlot;
  onDetectorHover: (point: { x: number; y: number } | null) => void;
  onPatternHover: (point: PatternHover | null) => void;
  patternZoom: ZoomMode;
  onPatternZoom: (mode: ZoomMode) => void;
}) {
  const [reintegrateSelected, setReintegrateSelected] = usePreference<boolean>(
    "reintegrate-selected",
    true,
  );
  const reintegrate =
    reintegrateSelected && !!state?.calibrated && !map?.normalized;
  const [smooth, setSmooth] = usePreference<boolean>("smooth", false),
    [smoothFactor, setSmoothFactor] = usePreference<number>("smooth-factor", 5);
  const [showContours, setShowContours] = usePreference<boolean>(
      "contours",
      false,
    ),
    [contourCount, setContourCount] = usePreference<number>("contour-count", 5);
  const [preview, setPreview] = useState<Raster | null>(null),
    [contours, setContours] = useState<number[][][]>([]);
  const requestRef = useRef(request);
  requestRef.current = request;
  const runRef = useRef(run);
  runRef.current = run;
  useEffect(() => {
    if (error) setLive(false);
  }, [error]);
  useEffect(() => {
    let current = true;
    setPreview(null);
    setContours([]);
    if (map && ready && (smooth || showContours))
      void requestRef
        .current("map_display", {
          smooth: smooth ? smoothFactor : 1,
          contours: showContours ? contourCount : 0,
        })
        .then((result) => {
          if (current && result?.ok) {
            setPreview(result.mapPreview ?? null);
            setContours(result.mapContours ?? []);
          }
        });
    return () => {
      current = false;
    };
  }, [map, ready, smooth, smoothFactor, showContours, contourCount]);
  const display = useDisplay(map?.raster ?? null, "map"),
    detector = useDisplay(image, "map-detector");
  const [scale, setScale] = usePreference<"linear" | "log" | "sqrt">(
    "pattern-scale",
    "linear",
  );
  const [antialias, setAntialias] = usePreference<boolean>(
      "pattern-antialias",
      true,
    ),
    [autoRange, setAutoRange] = usePreference<boolean>(
      "pattern-auto-range",
      true,
    );
  const [editRegions, setEditRegions] = useState(true),
    [showRegions, setShowRegions] = useState(true);
  const [patternUnit, setPatternUnit] = useState<Unit | null>(null);
  const [mapOnly, setMapOnly] = useState(false),
    [share, setShare] = usePreference<number>("width", 36),
    [upperShare, setUpperShare] = usePreference<number>("height", 44);
  const [tabbedImage, setTabbedImage] = useState(false);
  const [live, setLive] = useState(false),
    [follow, setFollow] = useState(true);
  const layout = useRef<HTMLDivElement>(null),
    topPanel = useRef<HTMLDivElement>(null),
    mapExporter = useRef<{ png: () => string } | null>(null);
  useEffect(() => {
    if (mapOnly || !topPanel.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setTabbedImage(entry.contentRect.width < 740),
    );
    observer.observe(topPanel.current);
    return () => observer.disconnect();
  }, [mapOnly]);
  useEffect(() => {
    if (mapLevels) display.setLimits(mapLevels);
  }, [mapLevels]);
  const sourceRun: MapRun = async (command, args, message) => {
    if (
      ["map_load", "map_folder", "map_batch", "map_normalize"].includes(command)
    )
      setLive(false);
    await run(command, args, message);
  };
  const mapIdentity = map?.labels[0];
  useEffect(() => {
    setLive(false);
  }, [mapIdentity]);
  useEffect(() => {
    if (!live || !ready || !map) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const result = await requestRef.current("map_poll", { check_only: true });
      if (cancelled) return;
      if (result && !result.ok) {
        setLive(false);
        return;
      }
      if (result?.ok && result.mapPending) {
        await runRef.current(
          "map_poll",
          { follow },
          "Appending new scan images…",
        );
        if (cancelled) return;
      }
      timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 1200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [live, ready, follow, mapIdentity]);
  const viewPattern = useMemo(() => {
    if (!pattern) return null;
    const requested = patternUnit ?? pattern.unit;
    const unit =
      requested === pattern.unit ||
      (requested !== "2th_deg" && pattern.unit !== "2th_deg") ||
      state?.calibrated
        ? requested
        : pattern.unit;
    if (unit === pattern.unit) return pattern;
    const converted = pattern.x
      .map(
        (x, i) =>
          [
            radialValues(x, pattern.unit, state?.geometry.wavelength)[unit],
            pattern.y[i],
          ] as const,
      )
      .filter(
        (p): p is readonly [number, number | null] =>
          p[0] != null && Number.isFinite(p[0]),
      );
    return {
      x: converted.map((p) => p[0]),
      y: converted.map((p) => p[1]),
      unit,
    };
  }, [pattern, patternUnit, state?.geometry.wavelength, state?.calibrated]);
  const regions = useMemo(() => {
    if (!map || !viewPattern || !showRegions) return [];
    return map.rois.flatMap((roi) => {
      const values = [roi.min, roi.max].map(
        (x) =>
          radialValues(x, map.unit, state?.geometry.wavelength)[
            viewPattern.unit
          ],
      );
      if (!values.every((x): x is number => x != null && Number.isFinite(x)))
        return [];
      return [
        {
          ...roi,
          appearance: "range" as const,
          min: Math.min(...values),
          max: Math.max(...values),
          active:
            roi.name ===
            (map.rois.some((r) => r.name === map.active)
              ? map.active
              : map.rois[0]?.name),
        },
      ];
    });
  }, [map, viewPattern?.unit, showRegions, state?.geometry.wavelength]);
  const changeRegion = (name: string, min: number, max: number) => {
    if (!map || !viewPattern) return;
    const values = [min, max].map(
      (x) =>
        radialValues(x, viewPattern.unit, state?.geometry.wavelength)[map.unit],
    );
    if (values.every((x): x is number => x != null && Number.isFinite(x)))
      void run("map_roi", {
        name,
        minimum: Math.min(...values),
        maximum: Math.max(...values),
      });
  };
  const intensity = (
    raster: Raster,
    d: ReturnType<typeof useDisplay>,
    kind: "map" | "detector",
  ) => (
    <ImageIntensity
      raster={raster}
      limits={d.limits}
      onLimits={d.setLimits}
      log={d.log}
      onLog={d.setLog}
      palette={d.palette}
      onPalette={d.setPalette}
      preferences={d.prefs}
      onPreferences={d.setPrefs}
      display={kind}
      ready={ready}
      onAuto={async (settings) => {
        const result = await request(
          kind === "map" ? "map_levels" : "image_levels",
          { ...settings },
        );
        const levels = kind === "map" ? result?.mapLevels : result?.levels;
        if (levels) d.setLimits(levels);
      }}
    />
  );
  const detectorPanel = (
    <section className="map-detector-panel" aria-label="Map detector image">
      {image && state?.hasImage ? (
        <div className="detector-workspace">
          <RasterView
            raster={image}
            mask={state.useMask ? (mask ?? undefined) : undefined}
            maskOpacity={state.transparentMask ? 0.72 : 1}
            limits={detector.limits}
            log={detector.log}
            palette={detector.palette}
            busy={!ready}
            zoomMode="rectangle"
            onHover={onDetectorHover}
          />
          {intensity(image, detector, "detector")}
        </div>
      ) : (
        <div className="empty-view">
          <p>
            {map
              ? "No raw detector image for this cell."
              : "Select a map point to inspect its detector image."}
          </p>
        </div>
      )}
      <div className="map-detector-tools">
        <label className="check-row">
          <input
            aria-label="Map use mask"
            type="checkbox"
            checked={!!state?.useMask}
            disabled={!ready || !state?.hasImage}
            onChange={(e) =>
              run("map_mask", { use_mask: e.target.checked, reintegrate })
            }
          />
          Mask
        </label>
        <label className="check-row">
          <input
            aria-label="Map transparent mask"
            type="checkbox"
            checked={!!state?.transparentMask}
            disabled={!ready || !state?.hasImage}
            onChange={(e) =>
              run("map_mask", { transparent_mask: e.target.checked })
            }
          />
          Transparent
        </label>
      </div>
    </section>
  );
  const divider = (vertical: boolean) => (
    <div
      className={`map-divider ${vertical ? "map-column-divider" : "map-row-divider"}`}
      role="separator"
      aria-label={vertical ? "Map panel width" : "Detector and pattern heights"}
      aria-orientation={vertical ? "vertical" : "horizontal"}
      aria-valuenow={Math.round(vertical ? share : upperShare)}
      aria-valuemin={vertical ? 22 : 25}
      aria-valuemax={vertical ? 65 : 70}
      tabIndex={0}
      onPointerDown={(e) => {
        if (e.button === 0) {
          e.preventDefault();
          e.currentTarget.setPointerCapture(e.pointerId);
        }
      }}
      onPointerMove={(e) => {
        if (!e.currentTarget.hasPointerCapture(e.pointerId) || !layout.current)
          return;
        const b = layout.current.getBoundingClientRect();
        if (vertical)
          setShare(
            Math.max(22, Math.min(65, ((e.clientX - b.left) / b.width) * 100)),
          );
        else
          setUpperShare(
            Math.max(25, Math.min(70, ((e.clientY - b.top) / b.height) * 100)),
          );
      }}
      onPointerUp={(e) => {
        if (e.currentTarget.hasPointerCapture(e.pointerId))
          e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onDoubleClick={() => (vertical ? setShare(36) : setUpperShare(44))}
      onKeyDown={(e) => {
        const lower = vertical ? "ArrowLeft" : "ArrowUp",
          higher = vertical ? "ArrowRight" : "ArrowDown";
        if (e.key !== lower && e.key !== higher && e.key !== "Home") return;
        e.preventDefault();
        const delta = e.key === lower ? -3 : 3;
        if (vertical)
          setShare(
            e.key === "Home" ? 36 : Math.max(22, Math.min(65, share + delta)),
          );
        else
          setUpperShare(
            e.key === "Home"
              ? 44
              : Math.max(25, Math.min(70, upperShare + delta)),
          );
      }}
    >
      <span />
    </div>
  );
  return (
    <div
      ref={layout}
      className={`map-layout ${mapOnly ? "map-only" : ""}`}
      style={
        {
          "--map-share": `${share}%`,
          "--map-upper-share": `${upperShare}%`,
        } as CSSProperties
      }
    >
      <section className="map-scan-panel" aria-label="Scan map">
        {map ? (
          <div className="detector-workspace map-raster" data-testid="scan-map">
            <RasterView
              raster={preview ?? map.raster}
              contours={contours}
              limits={display.limits}
              log={display.log}
              palette={display.palette}
              zoomMode="rectangle"
              tool="pan"
              busy={!ready}
              exportRef={mapExporter}
              peaks={
                map.selectedCell
                  ? [
                      {
                        x: map.selectedCell[1],
                        y: map.raster.height - map.selectedCell[0] - 1,
                        ring: 1,
                        selected: true,
                      },
                    ]
                  : []
              }
              onInspect={(point) =>
                run(
                  "map_select",
                  {
                    row: map.raster.height - 1 - Math.floor(point.y),
                    column: Math.floor(point.x),
                    reintegrate,
                  },
                  "Loading scan point…",
                )
              }
              onHover={(point) => {
                if (!point) {
                  reportPlot("map", null);
                  return;
                }
                const row = map.raster.height - 1 - Math.floor(point.y),
                  col = Math.floor(point.x),
                  value = map.values[row]?.[col],
                  index = map.indices[row]?.[col];
                reportPlot("map", {
                  text: `Row ${row} · column ${col} · ${value == null ? "no value" : `I ${number(value, 5)}`} · ${index == null || index < 0 ? "blank" : `point ${index}`}`,
                  hint: "Click a map cell to inspect its detector image and pattern.",
                });
              }}
            />
            {intensity(map.raster, display, "map")}
          </div>
        ) : (
          <div className="empty-view">
            <h3>Load a scan</h3>
            <p>Integrate detector images or open a processed batch.</p>
            <button
              disabled={!ready || !state?.calibrated}
              className="primary"
              onClick={() => run("map_load", {}, "Integrating map…")}
            >
              Load images…
            </button>
          </div>
        )}
        <div className="integration-image-tools map-display-controls">
          <label>
            <input
              aria-label="Smooth map"
              type="checkbox"
              checked={smooth}
              disabled={!map}
              onChange={(e) => setSmooth(e.target.checked)}
            />
            Smooth
          </label>
          <input
            aria-label="Map smoothing factor"
            title={`Smoothing factor: ${smoothFactor}×`}
            type="range"
            min="2"
            max="10"
            value={smoothFactor}
            disabled={!smooth || !map}
            onChange={(e) => setSmoothFactor(+e.target.value)}
          />
          <label>
            <input
              aria-label="Map contours"
              type="checkbox"
              checked={showContours}
              disabled={!map}
              onChange={(e) => setShowContours(e.target.checked)}
            />
            Contours
          </label>
          <input
            aria-label="Map contour count"
            title={`${contourCount} contour levels`}
            type="range"
            min="1"
            max="20"
            value={contourCount}
            disabled={!showContours || !map}
            onChange={(e) => setContourCount(+e.target.value)}
          />
        </div>
        <div className="integration-image-tools map-toolbar">
          <button
            className="plot-tool-button map-icon-button"
            aria-label="Save map data…"
            title="Save map data as text or TIFF"
            disabled={!ready || !map}
            onClick={() => run("map_export")}
          >
            <Save size={16} />
          </button>
          <label className="map-layer-select">
            Layer
            <select
              aria-label="Map layer"
              disabled={!ready || !map}
              value={map?.active ?? ""}
              onChange={(e) => run("map_layer", { name: e.target.value })}
            >
              {map ? (
                [
                  ...map.rois.map((r) => r.name),
                  ...Object.keys(map.expressions),
                ].map((n) => <option key={n}>{n}</option>)
              ) : (
                <option>No map loaded</option>
              )}
            </select>
          </label>
          <button
            className="plot-tool-button map-icon-button"
            aria-label="Save PNG…"
            title="Save map viewport as PNG"
            disabled={!ready || !map}
            onClick={() => {
              const png = mapExporter.current?.png();
              if (png) void run("map_export", { png_data: png.split(",")[1] });
            }}
          >
            PNG
          </button>
          <button
            className="plot-tool-button map-icon-button"
            aria-label={mapOnly ? "Dock detector / pattern" : "Expand map"}
            title={
              mapOnly ? "Restore detector, controls and pattern" : "Expand map"
            }
            onClick={() => setMapOnly((v) => !v)}
          >
            {mapOnly ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </section>
      {!mapOnly && (
        <>
          {divider(true)}
          <div
            className={`map-analysis-top ${tabbedImage ? "map-image-tabbed" : ""}`}
            ref={topPanel}
          >
            {!tabbedImage && detectorPanel}
            <aside className="map-task-panel" aria-label="Map tasks">
              <MapControls
                map={map}
                state={state}
                ready={ready}
                run={sourceRun}
                live={live}
                onLive={setLive}
                follow={follow}
                onFollow={setFollow}
                reintegrateSelected={reintegrateSelected}
                onReintegrateSelected={setReintegrateSelected}
                windowUnit={viewPattern?.unit ?? map?.unit}
                imageTab={tabbedImage ? detectorPanel : undefined}
              />
            </aside>
          </div>
          {divider(false)}
          <section className="map-pattern-panel" aria-label="Map pattern">
            {viewPattern && viewPattern.x.length ? (
              <PatternView
                key={viewPattern.unit}
                pattern={viewPattern}
                log={scale === "log"}
                sqrt={scale === "sqrt"}
                antialias={antialias}
                compact
                autoRange={autoRange}
                onAutoRange={setAutoRange}
                zoomMode={patternZoom}
                onZoomMode={onPatternZoom}
                onHover={onPatternHover}
                hoverHint={
                  editRegions
                    ? "Drag window edges or body · click to center active window · left drag outside windows zooms · right drag pans"
                    : undefined
                }
                regions={regions}
                editRegions={editRegions && ready && showRegions}
                onRegionChange={changeRegion}
                onRegionSelect={(name) => {
                  if (map?.active !== name) void run("map_layer", { name });
                }}
                onPick={(x) => {
                  if (!editRegions || !showRegions || !map) return;
                  const active = regions.find((r) => r.active);
                  if (active) {
                    const half = (active.max - active.min) / 2;
                    changeRegion(active.name, x - half, x + half);
                  }
                }}
              />
            ) : (
              <div className="empty-pattern">
                Select a filled map cell to inspect its stored diffraction
                pattern.
              </div>
            )}
            <div
              className="integration-pattern-tools map-pattern-tools"
              role="group"
              aria-label="Map pattern controls"
            >
              <div className="plot-tool-group">
                {(
                  [
                    ["2th_deg", "2θ"],
                    ["q_A^-1", "Q"],
                    ["d_A", "d"],
                  ] as [Unit, string][]
                ).map(([unit, label]) => (
                  <button
                    key={unit}
                    className="plot-tool-button"
                    aria-label={`Map pattern unit ${label}`}
                    title={`Display pattern in ${label}`}
                    aria-pressed={(viewPattern?.unit ?? map?.unit) === unit}
                    disabled={
                      !pattern ||
                      (unit !== pattern.unit &&
                        (!state?.geometry.wavelength || !state?.calibrated) &&
                        (unit === "2th_deg" || pattern.unit === "2th_deg"))
                    }
                    onClick={() => setPatternUnit(unit)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="plot-tool-group">
                <button
                  className="plot-tool-button"
                  aria-label="Show pattern windows"
                  title="Show pattern windows"
                  aria-pressed={showRegions}
                  onClick={() => setShowRegions((v) => !v)}
                >
                  ROI
                </button>
                <button
                  className="plot-tool-button"
                  aria-label="Edit windows"
                  title="Edit pattern windows by dragging; turn off to zoom inside windows"
                  aria-pressed={editRegions}
                  disabled={!showRegions}
                  onClick={() => setEditRegions((v) => !v)}
                >
                  <MoveHorizontal size={15} />
                </button>
              </div>
              <div className="plot-tool-group">
                <button
                  className="plot-tool-button"
                  aria-label="Logarithmic map pattern intensity"
                  aria-pressed={scale === "log"}
                  title="Logarithmic intensity"
                  onClick={() => setScale(scale === "log" ? "linear" : "log")}
                >
                  Log
                </button>
                <button
                  className="plot-tool-button"
                  aria-label="Square root map pattern intensity"
                  aria-pressed={scale === "sqrt"}
                  title="Square-root intensity"
                  onClick={() => setScale(scale === "sqrt" ? "linear" : "sqrt")}
                >
                  √
                </button>
              </div>
              <button
                className="plot-tool-button"
                aria-label="Antialias map pattern"
                title="Antialiased pattern lines"
                aria-pressed={antialias}
                onClick={() => setAntialias((v) => !v)}
              >
                AA
              </button>
              <button
                className="plot-tool-button"
                aria-label="Map pattern auto range"
                title="Fit axes when the selected pattern changes"
                aria-pressed={autoRange}
                onClick={() => setAutoRange((v) => !v)}
              >
                A
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
