import { DetectorSurface, useDetectorDetached } from "./DetectorWindow";
import { Input, Button } from "./ui";
import { LayoutDivider } from "./LayoutDivider";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { PanelLeftClose, ExternalLink, MoveHorizontal } from "lucide-react";
import { RasterView } from "./RasterView";
import { PatternView } from "./PatternView";
import { ImageIntensity } from "./ImageIntensity";
import { MapControls } from "./MapControls";
import {
  patternViewport,
  plotViewContext,
  type SharedPlotViews,
} from "./plotViewport";
import { mapPatternInUnit } from "./mapPattern";
import type { PatternPosition } from "./linkedPosition";
import { detectorPlotSetup, patternPlotSetup } from "./diffractionPlotSetup";
import { radialValues } from "./radialReadout";
import { useMapDisplay, useMapPreference } from "./mapPreferences";
import { ScanMapPanel } from "./ScanMapPanel";
import { useLiveMapRegion } from "./useLiveMapRegion";
import {
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

export function MapView({
  map,
  progressPreview,
  plotViews,
  image,
  mask,
  pattern,
  state,
  ready,
  error,
  run,
  request,
  reportPlot,
  onDetectorHover,
  onPatternHover,
  patternZoom,
  onPatternZoom,
  mapWindow,
  linked,
  localImageClick,
  localPatternClick,
  onDetectorInspect,
  onPatternInspect,
}: {
  plotViews: SharedPlotViews;
  linked: Response["linked"];
  localImageClick: { x: number; y: number } | null;
  localPatternClick?: PatternPosition;
  onDetectorInspect: (point: {
    x: number;
    y: number;
    value: number | null;
  }) => void;
  onPatternInspect: (point: PatternHover) => void;
  map: MapData | null;
  progressPreview?: NonNullable<Response["progress"]>["mapPreview"];
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
  mapWindow: { detached: boolean; open: () => void; dock: () => void };
  reportPlot: ReportPlot;
  onDetectorHover: (point: { x: number; y: number } | null) => void;
  onPatternHover: (point: PatternHover | null) => void;
  patternZoom: ZoomMode;
  onPatternZoom: (mode: ZoomMode) => void;
}) {
  const detectorDetached = useDetectorDetached();
  const [reintegrateSelected, setReintegrateSelected] =
    useMapPreference<boolean>("reintegrate-selected", true);
  const reintegrate =
    reintegrateSelected && !!state?.calibrated && !map?.normalized;
  const requestRef = useRef(request);
  requestRef.current = request;
  const runRef = useRef(run);
  runRef.current = run;
  const liveRegion = useLiveMapRegion(map, run);
  const detector = useMapDisplay(image, "map-detector");
  useEffect(() => {
    if (error) setLive(false);
  }, [error]);
  const [scale, setScale] = useMapPreference<"linear" | "log" | "sqrt">(
    "pattern-scale",
    "linear",
  );
  const [antialias, setAntialias] = useMapPreference<boolean>(
      "pattern-antialias",
      true,
    ),
    [autoRange, setAutoRange] = useMapPreference<boolean>(
      "pattern-auto-range",
      true,
    );
  const [editRegions, setEditRegions] = useState(true),
    [showRegions, setShowRegions] = useState(true);
  const [patternUnit, setPatternUnit] = useState<Unit | null>(null);
  const [share, setShare] = useMapPreference<number>("width", 36),
    [upperShare, setUpperShare] = useMapPreference<number>("height", 44);
  const [tabbedImage, setTabbedImage] = useState(false);
  const [live, setLive] = useState(false),
    [follow, setFollow] = useState(true);
  const layout = useRef<HTMLDivElement>(null),
    topPanel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!topPanel.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setTabbedImage(entry.contentRect.width < 740),
    );
    observer.observe(topPanel.current);
    return () => observer.disconnect();
  }, []);
  const sourceRun: MapRun = async (command, args, message) => {
    if (
      ["map_load", "map_folder", "map_batch", "map_normalize"].includes(command)
    )
      setLive(false);
    await run(command, args, message);
  };
  const mapIdentity = JSON.stringify([
    state?.projectName,
    state?.configurationContext ?? state?.configurationIndex,
    map?.labels[0],
  ]);
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
    if (progressPreview) return progressPreview.pattern;
    if (!pattern) return null;
    const requested = patternUnit ?? pattern.unit;
    const unit =
      requested === pattern.unit ||
      (requested !== "2th_deg" && pattern.unit !== "2th_deg") ||
      state?.calibrated
        ? requested
        : pattern.unit;
    return mapPatternInUnit(pattern, unit, state?.geometry.wavelength);
  }, [
    pattern,
    patternUnit,
    state?.geometry.wavelength,
    state?.calibrated,
    progressPreview,
  ]);
  const patternPlot = viewPattern
    ? patternPlotSetup({
        pattern: viewPattern,
        viewport: patternViewport(
          plotViews.pattern,
          plotViewContext(state),
          viewPattern.unit,
          scale,
          state?.geometry.wavelength,
        ),
        patternColor: state?.integration.originalPatternColor,
        showPattern: state?.integration.originalPatternVisible ?? true,
        patternName: state?.integration.patternName,
        curves: viewPattern.curves,
        referenceLines: viewPattern.phaseLines,
        linked,
        localPatternClick,
        wavelength: state?.geometry.wavelength,
        onInspect: onPatternInspect,
      })
    : null;
  const regions = useMemo(() => {
    if (!map || !viewPattern || !showRegions) return [];
    return map.rois.flatMap((stored) => {
      const roi =
        liveRegion.draft?.name === stored.name
          ? { ...stored, ...liveRegion.draft }
          : stored;
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
  }, [
    map,
    liveRegion.draft,
    viewPattern?.unit,
    showRegions,
    state?.geometry.wavelength,
  ]);
  const changeRegion = (
    name: string,
    min: number,
    max: number,
    flush = true,
  ) => {
    if (!map || !viewPattern) return;
    const values = [min, max].map(
      (x) =>
        radialValues(x, viewPattern.unit, state?.geometry.wavelength)[map.unit],
    );
    if (values.every((x): x is number => x != null && Number.isFinite(x)))
      liveRegion.change(
        {
          name,
          min: Math.min(...values),
          max: Math.max(...values),
        },
        flush,
      );
  };
  const intensity = (
    raster: Raster,
    d: ReturnType<typeof useMapDisplay>,
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
      initialAutoActive={d.initialAutoActive}
      onAutoActiveChange={d.setAutoActive}
      onAuto={async (settings) => {
        const result = await request(
          kind === "map" ? "map_levels" : "image_levels",
          { ...settings },
        );
        const levels = kind === "map" ? result?.mapLevels : result?.levels;
        if (levels) d.setAutoLimits(levels);
      }}
    />
  );
  const detectorPanel = (
    <section className="map-detector-panel" aria-label="Map detector image">
      {image && state?.hasImage ? (
        <DetectorSurface>
          <RasterView
            raster={image}
            {...detectorPlotSetup({
              state,
              viewports: plotViews,
              mask,
              linked,
              localImageClick,
              onInspect: onDetectorInspect,
            })}
            limits={detector.limits}
            log={detector.log}
            palette={detector.palette}
            busy={!ready}
            onHover={onDetectorHover}
            rings={linked?.contours}
          />
          {intensity(image, detector, "detector")}
        </DetectorSurface>
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
          <Input
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
          <Input
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
    <LayoutDivider
      className={`map-divider ${vertical ? "map-column-divider" : "map-row-divider"}`}
      label={vertical ? "Map panel width" : "Detector and pattern heights"}
      orientation={vertical ? "vertical" : "horizontal"}
      value={vertical ? share : upperShare}
      min={vertical ? 22 : 25}
      max={vertical ? 65 : 70}
      defaultValue={vertical ? 36 : 44}
      step={3}
      onChange={vertical ? setShare : setUpperShare}
      pointerValue={(event) => {
        const box = layout.current?.getBoundingClientRect();
        return !box
          ? null
          : vertical
            ? ((event.clientX - box.left) / box.width) * 100
            : ((event.clientY - box.top) / box.height) * 100;
      }}
    />
  );

  return (
    <>
      <div
        ref={layout}
        className="map-layout"
        data-map-detached={mapWindow.detached}
        style={
          {
            "--map-share": `${share}%`,
            "--map-upper-share": `${upperShare}%`,
          } as CSSProperties
        }
      >
        {mapWindow.detached ? (
          <section className="map-scan-panel" aria-label="Scan map">
            <div className="empty-view map-detached-placeholder">
              <p>Map is open in a separate window.</p>
              <div className="map-detached-actions">
                <Button
                  className="plot-tool-button map-icon-button"
                  aria-label="Show map"
                  title="Show the separate map window"
                  onClick={mapWindow.open}
                >
                  <ExternalLink size={16} />
                </Button>
                <Button
                  className="plot-tool-button map-icon-button"
                  aria-label="Dock map"
                  title="Dock map here"
                  onClick={mapWindow.dock}
                >
                  <PanelLeftClose size={16} />
                </Button>
              </div>
            </div>
          </section>
        ) : (
          <ScanMapPanel
            map={map}
            progressPreview={progressPreview}
            calibrated={!!state?.calibrated}
            ready={ready}
            run={run}
            request={request}
            reintegrate={reintegrate}
            reportPlot={reportPlot}
            actions={
              <>
                <Button
                  className="plot-tool-button map-icon-button"
                  aria-label="Detach map"
                  title="Open map in a separate window and return to Integration"
                  disabled={!ready || !map}
                  onClick={mapWindow.open}
                >
                  <ExternalLink size={16} />
                </Button>
              </>
            }
          />
        )}
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
                keepImageMounted={detectorDetached}
                imageTab={tabbedImage ? detectorPanel : undefined}
              />
            </aside>
          </div>
          {divider(false)}
          <section className="map-pattern-panel" aria-label="Map pattern">
            {viewPattern && viewPattern.x.length ? (
              <PatternView
                key={viewPattern.unit}
                {...patternPlot!.props}
                onInspect={patternPlot!.inspect}
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
                onRegionDragStart={liveRegion.begin}
                onRegionInput={(name, min, max) =>
                  changeRegion(name, min, max, false)
                }
                onRegionCancel={liveRegion.cancel}
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
                {map
                  ? "Select a filled map cell to inspect its stored diffraction pattern."
                  : "Build a map to inspect its diffraction patterns."}
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
                  <Button
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
                  </Button>
                ))}
              </div>
              <div className="plot-tool-group">
                <Button
                  className="plot-tool-button"
                  aria-label="Show pattern windows"
                  title="Show pattern windows"
                  aria-pressed={showRegions}
                  disabled={!pattern}
                  onClick={() => setShowRegions((v) => !v)}
                >
                  ROI
                </Button>
                <Button
                  className="plot-tool-button"
                  aria-label="Edit windows"
                  title="Edit pattern windows by dragging; turn off to zoom inside windows"
                  aria-pressed={editRegions}
                  disabled={!pattern || !showRegions}
                  onClick={() => setEditRegions((v) => !v)}
                >
                  <MoveHorizontal size={15} />
                </Button>
              </div>
              <div className="plot-tool-group">
                <Button
                  className="plot-tool-button"
                  aria-label="Logarithmic map pattern intensity"
                  aria-pressed={scale === "log"}
                  disabled={!pattern}
                  title="Logarithmic intensity"
                  onClick={() => setScale(scale === "log" ? "linear" : "log")}
                >
                  Log
                </Button>
                <Button
                  className="plot-tool-button"
                  aria-label="Square root map pattern intensity"
                  aria-pressed={scale === "sqrt"}
                  disabled={!pattern}
                  title="Square-root intensity"
                  onClick={() => setScale(scale === "sqrt" ? "linear" : "sqrt")}
                >
                  √
                </Button>
              </div>
              <Button
                className="plot-tool-button"
                aria-label="Antialias map pattern"
                title="Antialiased pattern lines"
                aria-pressed={antialias}
                disabled={!pattern}
                onClick={() => setAntialias((v) => !v)}
              >
                AA
              </Button>
              <Button
                className="plot-tool-button"
                aria-label="Map pattern auto range"
                title="Fit axes when the selected pattern changes"
                aria-pressed={autoRange}
                disabled={!pattern}
                onClick={() => setAutoRange((v) => !v)}
              >
                A
              </Button>
            </div>
          </section>
        </>
      </div>
    </>
  );
}
