import { useEffect, useRef, useState } from "react";
import { RasterView } from "./RasterView";
import { PatternView } from "./PatternView";
import { ImageIntensity } from "./ImageIntensity";
import {
  number,
  unitLabel,
  type ImageDisplayPreferences,
  type Pattern,
  type Raster,
  type Response,
  type State,
} from "./types";
import type { MapData, MapRun } from "./mapDomain";
import type { ZoomMode } from "./usePlotNavigation";
import "./map.css";
const preferences = (): ImageDisplayPreferences => ({
  size: "compact",
  orientation: "horizontal",
  auto: { mode: "percentile", percentile: 0.4, filter_gaps: false },
});
function useDisplay(raster: Raster | null) {
  const [limits, setLimits] = useState<[number, number]>([0, 1]);
  const [log, setLog] = useState(false),
    [palette, setPalette] = useState("grey");
  const [prefs, setPrefs] = useState(preferences);
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
export function MapView({
  map,
  image,
  mask,
  pattern,
  state,
  ready,
  run,
  request,
  warning,
  reintegrate,
  mapLevels,
  linked,
}: {
  map: MapData | null;
  image: Raster | null;
  mask: Raster | null;
  pattern: Pattern | null;
  state: State | null;
  ready: boolean;
  run: MapRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  warning: string | null;
  reintegrate: boolean;
  mapLevels?: [number, number];
  linked?: Response["linked"];
}) {
  const [smooth, setSmooth] = useState(false),
    [smoothFactor, setSmoothFactor] = useState(5);
  const [showContours, setShowContours] = useState(false),
    [contourCount, setContourCount] = useState(5);
  const [preview, setPreview] = useState<Raster | null>(null),
    [contours, setContours] = useState<number[][][]>([]);
  const requestRef = useRef(request);
  requestRef.current = request;
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
  const display = useDisplay(map?.raster ?? null),
    detector = useDisplay(image);
  const [mapZoom, setMapZoom] = useState<ZoomMode>("rectangle"),
    [detectorZoom, setDetectorZoom] = useState<ZoomMode>("rectangle"),
    [patternZoom, setPatternZoom] = useState<ZoomMode>("horizontal");
  const [logPattern, setLogPattern] = useState(false),
    [editRegions, setEditRegions] = useState(false);
  const [readout, setReadout] = useState(""),
    [detectorReadout, setDetectorReadout] = useState("");
  const [mapOnly, setMapOnly] = useState(false),
    [share, setShare] = useState(43),
    [upperShare, setUpperShare] = useState(48);
  const layout = useRef<HTMLDivElement>(null),
    mapPanel = useRef<HTMLElement>(null);
  const hoverAt = useRef(0),
    hoverBusy = useRef(false);
  useEffect(() => {
    if (mapLevels) display.setLimits(mapLevels);
  }, [mapLevels]);
  const zoom = (
    value: ZoomMode,
    setter: (v: ZoomMode) => void,
    label: string,
  ) => (
    <select
      className="zoom-mode"
      aria-label={label}
      value={value}
      onChange={(e) => setter(e.target.value as ZoomMode)}
    >
      <option value="rectangle">Rectangle</option>
      <option value="horizontal">Horizontal</option>
    </select>
  );
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
  return (
    <div
      ref={layout}
      className={`map-layout ${mapOnly ? "map-only" : ""}`}
      style={{
        gridTemplateColumns: mapOnly
          ? "minmax(0,1fr)"
          : `minmax(0,${share}fr) 7px minmax(0,${100 - share}fr)`,
        gridTemplateRows: `minmax(220px,${upperShare}fr) 7px minmax(220px,${100 - upperShare}fr)`,
      }}
    >
      <section
        ref={mapPanel}
        className="panel map-scan-panel"
        aria-label="Scan map"
      >
        <div className="panel-heading map-heading">
          <div className="map-layer-select">
            <label htmlFor="map-layer">Layer:</label>
            <select
              id="map-layer"
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
          </div>
          {zoom(mapZoom, setMapZoom, "Map zoom mode")}
        </div>
        <div className="map-toolbar">
          <button onClick={() => setMapOnly((v) => !v)}>
            {mapOnly ? "Dock detector / pattern" : "Expand map"}
          </button>
          <button
            disabled={!ready || !map}
            onClick={() => {
              const canvas = mapPanel.current?.querySelector<HTMLCanvasElement>(
                '[data-testid="detector-canvas"]',
              );
              if (canvas)
                void run("map_export", {
                  png_data: canvas.toDataURL("image/png").split(",")[1],
                });
            }}
          >
            Save PNG…
          </button>
        </div>
        {map && (
          <div className="map-toolbar map-display-controls">
            <label>
              <input
                aria-label="Smooth map"
                type="checkbox"
                checked={smooth}
                onChange={(e) => setSmooth(e.target.checked)}
              />
              Smooth
            </label>
            {smooth && (
              <input
                aria-label="Map smoothing factor"
                type="range"
                min="2"
                max="10"
                value={smoothFactor}
                onChange={(e) => setSmoothFactor(+e.target.value)}
              />
            )}
            <label>
              <input
                aria-label="Map contours"
                type="checkbox"
                checked={showContours}
                onChange={(e) => setShowContours(e.target.checked)}
              />
              Contours
            </label>
            {showContours && (
              <input
                aria-label="Map contour count"
                type="range"
                min="1"
                max="20"
                value={contourCount}
                onChange={(e) => setContourCount(+e.target.value)}
              />
            )}
          </div>
        )}
        {map ? (
          <div className="detector-workspace map-raster" data-testid="scan-map">
            <RasterView
              raster={preview ?? map.raster}
              contours={contours}
              limits={display.limits}
              log={display.log}
              palette={display.palette}
              zoomMode={mapZoom}
              tool="pan"
              busy={!ready}
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
                  setReadout("");
                  return;
                }
                const row = map.raster.height - 1 - Math.floor(point.y),
                  col = Math.floor(point.x),
                  value = map.values[row]?.[col],
                  index = map.indices[row]?.[col];
                setReadout(
                  `Row ${row} · column ${col} · ${value == null ? "no value" : `I ${number(value, 5)}`} · ${index == null || index < 0 ? "blank" : `point ${index}`}`,
                );
              }}
            />
            {intensity(map.raster, display, "map")}
          </div>
        ) : (
          <div className="empty-view">
            <h3>Load a scan</h3>
            <p>
              Integrate an ordered set of detector images,
              <br />
              open a processed batch, or reopen a .dio project.
            </p>
            <button
              disabled={!ready || !state?.calibrated}
              className="primary"
              onClick={() => run("map_load", {}, "Integrating map…")}
            >
              Load images…
            </button>
          </div>
        )}
        <div className="panel-footer">
          <span data-testid="map-readout">
            {readout ||
              (map
                ? `${map.raster.height} rows × ${map.raster.width} columns · ${map.points} points`
                : "Scan map")}
          </span>
        </div>
        {warning && (
          <p role="status" className="map-warning">
            {warning}
          </p>
        )}
      </section>
      {!mapOnly && (
        <>
          <div
            className="map-divider map-column-divider"
            role="separator"
            aria-label="Map panel width"
            aria-orientation="vertical"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                setShare((v) =>
                  Math.max(
                    22,
                    Math.min(75, v + (e.key === "ArrowLeft" ? -3 : 3)),
                  ),
                );
              }
            }}
            onPointerDown={(e) =>
              e.currentTarget.setPointerCapture(e.pointerId)
            }
            onPointerMove={(e) => {
              if (
                e.currentTarget.hasPointerCapture(e.pointerId) &&
                layout.current
              ) {
                const bounds = layout.current.getBoundingClientRect();
                setShare(
                  Math.max(
                    22,
                    Math.min(
                      75,
                      ((e.clientX - bounds.left) / bounds.width) * 100,
                    ),
                  ),
                );
              }
            }}
          />
          <section
            className="panel map-detector-panel"
            aria-label="Map detector image"
          >
            <div className="panel-heading">
              <span>Detector image</span>
              {zoom(detectorZoom, setDetectorZoom, "Map detector zoom mode")}
            </div>
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
                  zoomMode={detectorZoom}
                  rings={linked?.contours ?? []}
                  onInspect={(point) => {
                    if (state.calibrated)
                      void run("validation_position", {
                        source: "image",
                        ...point,
                      });
                  }}
                  onHover={async (point) => {
                    if (!point) {
                      setDetectorReadout("");
                      return;
                    }
                    if (
                      !ready ||
                      hoverBusy.current ||
                      performance.now() - hoverAt.current < 100
                    )
                      return;
                    hoverAt.current = performance.now();
                    hoverBusy.current = true;
                    try {
                      const r = await request("pixel", point);
                      if (r?.pixel)
                        setDetectorReadout(
                          `X ${r.pixel.x} · row ${image.fullHeight - 1 - r.pixel.y} · I ${r.pixel.value == null ? "—" : number(r.pixel.value)}`,
                        );
                    } finally {
                      hoverBusy.current = false;
                    }
                  }}
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
            <div className="panel-footer">
              <span>
                {detectorReadout ||
                  (state?.hasImage ? state.imageName : "No image selected")}
              </span>
            </div>
          </section>
          <div
            className="map-divider map-row-divider"
            role="separator"
            aria-label="Detector and pattern heights"
            aria-orientation="horizontal"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                e.preventDefault();
                setUpperShare((v) =>
                  Math.max(
                    25,
                    Math.min(70, v + (e.key === "ArrowUp" ? -3 : 3)),
                  ),
                );
              }
            }}
            onPointerDown={(e) =>
              e.currentTarget.setPointerCapture(e.pointerId)
            }
            onPointerMove={(e) => {
              if (
                e.currentTarget.hasPointerCapture(e.pointerId) &&
                layout.current
              ) {
                const b = layout.current.getBoundingClientRect();
                setUpperShare(
                  Math.max(
                    25,
                    Math.min(70, ((e.clientY - b.top) / b.height) * 100),
                  ),
                );
              }
            }}
          />
          <section className="panel map-pattern-panel" aria-label="Map pattern">
            <div className="panel-heading map-heading">
              <span>
                Pattern {pattern ? `· ${unitLabel(pattern.unit)}` : ""}
              </span>
              <div className="map-pattern-actions">
                <button
                  className={editRegions ? "active" : ""}
                  aria-pressed={editRegions}
                  onClick={() => setEditRegions((v) => !v)}
                >
                  Edit windows
                </button>
                <button
                  aria-pressed={logPattern}
                  onClick={() => setLogPattern((v) => !v)}
                >
                  Log
                </button>
                {zoom(patternZoom, setPatternZoom, "Map pattern zoom mode")}
              </div>
            </div>
            {pattern ? (
              <PatternView
                pattern={pattern}
                log={logPattern}
                zoomMode={patternZoom}
                linkedPosition={
                  pattern.unit === state?.unit ? linked?.radial : undefined
                }
                regions={
                  map && pattern.unit === map.unit
                    ? map.rois.map((r) => ({
                        ...r,
                        active: r.name === map.active,
                      }))
                    : []
                }
                editRegions={editRegions && ready}
                onRegionChange={(name, minimum, maximum) =>
                  run("map_roi", { name, minimum, maximum })
                }
                onPick={(x) => {
                  if (state?.calibrated && pattern.unit === state.unit)
                    void run("validation_position", { source: "pattern", x });
                }}
              />
            ) : (
              <div className="empty-pattern">
                Select a filled map cell to inspect its stored diffraction
                pattern.
              </div>
            )}
            <div className="panel-footer">
              <span>
                {editRegions
                  ? "Drag a window or its edges · right drag pans"
                  : "Left drag zooms · right drag pans · right double-click fits"}
              </span>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
