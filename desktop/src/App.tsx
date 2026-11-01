import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleHelp,
  CircleX,
  Crosshair,
  Eraser,
  FileImage,
  FolderOpen,
  Hand,
  Layers,
  LoaderCircle,
  Plus,
  Save,
  Sparkles,
  Trash2,
  Undo2,
} from "lucide-react";
import { connect } from "./bridge";
import { CrystalMark } from "./CrystalMark";
import type {
  Cake,
  ImageDisplayPreferences,
  Invoke,
  Palette,
  Pattern,
  Raster,
  Response,
  State,
  Tool,
} from "./types";
import { number, unitLabel } from "./types";
import { MapView } from "./MapView";
import { MapControls } from "./MapControls";
import type { MapData } from "./mapDomain";
import { MaskView } from "./MaskView";
import { MaskPanel } from "./MaskPanel";
import { useMaskTools } from "./maskDomain";
import { RasterView } from "./RasterView";
import { PatternView } from "./PatternView";
import { CalibrationControls } from "./CalibrationControls";
import { CalibrationPanel } from "./CalibrationPanel";
import { ImageIntensity } from "./ImageIntensity";
import { colorMaps } from "./colorMaps";
import { IntegrationView, IntegrationDisplayControls } from "./IntegrationView";
import { IntegrationWorkspace } from "./IntegrationWorkspace";
import { CalibrationExtras, GeometryEditor } from "./CalibrationExtras";
import type { RingOverlay } from "./types";
import type { ZoomMode } from "./usePlotNavigation";

function ZoomModeSelect({
  value,
  onChange,
  label,
}: {
  value: ZoomMode;
  onChange: (mode: ZoomMode) => void;
  label: string;
}) {
  return (
    <select
      className="zoom-mode"
      aria-label={label}
      title="Left-drag zoom mode"
      value={value}
      onChange={(event) => onChange(event.target.value as ZoomMode)}
    >
      <option value="horizontal">Horizontal</option>
      <option value="rectangle">Rectangle</option>
    </select>
  );
}

export default function App() {
  const [integrationDisplay, setIntegrationDisplay] = useState("image");
  const [calibrationStep, setCalibrationStep] = useState(0);
  const [selectedPicks, setSelectedPicks] = useState<number[]>([]);
  const [advancedDirty, setAdvancedDirty] = useState(false);
  const [accent, setAccent] = useState(() => {
    try {
      // Start this accent revision in the user's preferred orange; later
      // explicit selections continue to persist independently of the symbol.
      return localStorage.getItem("dioptas-accent-v2") === "green"
        ? "green"
        : "orange";
    } catch {
      return "orange";
    }
  });
  const [largeText, setLargeText] = useState(() => {
    try {
      return localStorage.getItem("dioptas-large-text") === "true";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("dioptas-accent-v2", accent);
      localStorage.setItem("dioptas-large-text", String(largeText));
    } catch {
      /* Preferences are optional when local storage is unavailable. */
    }
  }, [accent, largeText]);
  const [showRings, setShowRings] = useState(true),
    [showNumbers, setShowNumbers] = useState(true);
  const [linked, setLinked] = useState<Response["linked"]>();
  const [progress, setProgress] = useState<Response["progress"]>();
  const [detectorZoom, setDetectorZoom] = useState<ZoomMode>("rectangle");
  const [cakeZoom, setCakeZoom] = useState<ZoomMode>("rectangle");
  const [patternZoom, setPatternZoom] = useState<ZoomMode>("horizontal");
  const [setupDirty, setSetupDirty] = useState(false);
  const [mode, setMode] = useState<
    "calibration" | "integration" | "mask" | "map"
  >("calibration");
  const maskTools = useMaskTools();
  const [map, setMap] = useState<MapData | null>(null);
  const [mapLevels, setMapLevels] = useState<[number, number]>();
  const [mapWarning, setMapWarning] = useState<string | null>(null);
  const [mapReintegrate, setMapReintegrate] = useState(false);
  const requestMap = async (
    command: string,
    args: Record<string, unknown> = {},
  ) => {
    if (!bridge.current || inFlight.current) return;
    try {
      const result = await bridge.current(command, args);
      if (!result.ok) setError(result.error ?? "Map command failed.");
      return result;
    } catch (error) {
      setError(String(error));
    }
  };

  const [ring, setRing] = useState(1),
    [automatic, setAutomatic] = useState(true);
  const [rings, setRings] = useState<RingOverlay[]>([]);
  const bridge = useRef<Invoke | null>(null),
    inFlight = useRef(false);
  const [state, setState] = useState<State | null>(null);
  const [image, setImage] = useState<Raster | null>(null),
    [mask, setMask] = useState<Raster | null>(null);
  const [cake, setCake] = useState<Cake | null>(null),
    [pattern, setPattern] = useState<Pattern | null>(null);
  const [busy, setBusy] = useState("Connecting to Dioptas…"),
    [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null),
    [help, setHelp] = useState(false);
  const [tool, setTool] = useState<Tool>("pan"),
    [radius, setRadius] = useState(20);
  const [logImage, setLogImage] = useState(false),
    [logPattern, setLogPattern] = useState(false);
  const [palette, setPalette] = useState<Palette>("grey");
  const [limits, setLimits] = useState<[number, number]>([0, 100]);
  const cakeSource = useRef<Cake | null>(null);
  const [cakeLimits, setCakeLimits] = useState<[number, number]>([0, 100]);
  const [cakeLog, setCakeLog] = useState(false);
  const [cakePalette, setCakePalette] = useState<Palette>("grey");
  const [detectorPreferences, setDetectorPreferences] =
    useState<ImageDisplayPreferences>({
      size: "compact",
      orientation: "vertical",
      auto: { mode: "percentile", percentile: 0.4, filter_gaps: true },
    });
  const [cakePreferences, setCakePreferences] =
    useState<ImageDisplayPreferences>({
      size: "compact",
      orientation: "horizontal",
      auto: { mode: "percentile", percentile: 0.4, filter_gaps: true },
    });
  const [multiDetectorPreferences, setMultiDetectorPreferences] =
    useState<ImageDisplayPreferences>({
      size: "compact",
      orientation: "horizontal",
      auto: { mode: "percentile", percentile: 0.4, filter_gaps: true },
    });
  const multipleImages = mode === "integration" || calibrationStep === 3;
  useEffect(() => {
    if (!colorMaps[palette]) setPalette("grey");
    if (!colorMaps[cakePalette]) setCakePalette("grey");
  }, [palette, cakePalette]);
  const [resetKey, setResetKey] = useState(0);
  const [pixel, setPixel] = useState<{
    x: number;
    y: number;
    value: number | null;
  } | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    hoverSequence = useRef(0);
  const hoverLatest = useRef<{ x: number; y: number } | null>(null);
  const hoverLastSent = useRef(0);
  const hoverRequest = useRef(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const apply = useCallback((result: Response) => {
    if (!result.ok)
      throw new Error(result.error || "The operation could not be completed.");
    if ("map" in result) setMap(result.map ?? null);
    if (result.mapLevels) setMapLevels(result.mapLevels);
    if ("mapWarning" in result) setMapWarning(result.mapWarning ?? null);
    if (result.state) {
      setState(result.state);
    }
    if (result.image) {
      ++hoverSequence.current;
      hoverLatest.current = null;
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
      setPixel(null);
      setLinked(undefined);
      setImage(result.image);
      setLimits(result.image.limits);
      setResetKey((k) => k + 1);
    }
    if (result.levels)
      (result.display === "cake" ? setCakeLimits : setLimits)(result.levels);
    if (result.nextRing !== undefined) setRing(result.nextRing);
    if (result.linked) setLinked(result.linked);
    if (result.mask)
      setMask((previous) =>
        previous?.data === result.mask!.data &&
        previous.width === result.mask!.width &&
        previous.height === result.mask!.height
          ? previous
          : result.mask!,
      );
    if (result.rings) {
      setRings(result.rings);
      if (!result.linked) setLinked(undefined);
    }
    if ("pattern" in result) setPattern(result.pattern ?? null);
    if ("cake" in result) {
      setCake(result.cake ?? null);
      if (
        result.cake &&
        (result.cake.data !== cakeSource.current?.data ||
          result.cake.width !== cakeSource.current?.width ||
          result.cake.height !== cakeSource.current?.height)
      )
        setCakeLimits(result.cake.limits);
      cakeSource.current = result.cake ?? null;
    }
    if (result.savedPath) {
      setNotice(`Saved ${result.savedPath.split(/[\\/]/).at(-1)}`);
      if (toastTimer.current) clearTimeout(toastTimer.current);
      toastTimer.current = setTimeout(() => setNotice(null), 4500);
    }
  }, []);
  const run = useCallback(
    async (
      command: string,
      args: Record<string, unknown> = {},
      message = "Processing…",
    ) => {
      if (!bridge.current || inFlight.current) return;
      inFlight.current = true;
      setBusy(message);
      setError(null);
      if (command === "workflow_settings")
        setState((s) =>
          s
            ? {
                ...s,
                calibration: {
                  ...s.calibration,
                  workflow: { ...s.calibration.workflow, ...args },
                },
              }
            : s,
        );
      try {
        apply(await bridge.current(command, args));
        if (
          [
            "undo_calibration",
            "redo_calibration",
            "clear_peaks",
            "remove_pick",
            "remove_picks",
            "open_image",
            "example",
            "image_transform",
            "open_project",
          ].includes(command)
        )
          setSelectedPicks([]);
        if (
          command === "calibrate" ||
          command === "manual_geometry" ||
          command === "open_calibration"
        ) {
          setCalibrationStep(3);
          setTool("pan");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        try {
          apply(await bridge.current("state"));
        } catch {
          /* Keep the original error visible. */
        }
      } finally {
        setBusy("");
        inFlight.current = false;
      }
    },
    [apply],
  );
  useEffect(() => {
    let mounted = true;
    connect()
      .then(async (invoke) => {
        if (!mounted) return;
        bridge.current = invoke;
        await run("state", {}, "Opening workspace…");
      })
      .catch((e) => {
        if (mounted) {
          setError(String(e.message));
          setBusy("");
        }
      });
    return () => {
      mounted = false;
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, [run]);
  useEffect(() => {
    if (!busy) {
      setProgress(undefined);
      return;
    }
    const timer = setInterval(() => {
      void bridge
        .current?.("progress")
        .then((r) => {
          if (r.ok) setProgress(r.progress);
        })
        .catch(() => {});
    }, 350);
    return () => clearInterval(timer);
  }, [busy]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      const key = event.key.toLowerCase(),
        mod = event.metaKey || event.ctrlKey;
      if (mod && key === "o") {
        event.preventDefault();
        void run("open_image", {}, "Opening image…");
      } else if (mod && key === "s") {
        event.preventDefault();
        void run(
          mode === "mask" ? "mask_file" : "save_project",
          mode === "mask" ? { save: true } : {},
          "Saving…",
        );
      } else if (mod && key === "z") {
        event.preventDefault();
        void run(
          mode === "calibration"
            ? event.shiftKey
              ? "redo_calibration"
              : "undo_calibration"
            : event.shiftKey
              ? "redo_mask"
              : "undo_mask",
          {},
          "Restoring previous state…",
        );
      } else if (mod && key === "y") {
        event.preventDefault();
        void run(mode === "calibration" ? "redo_calibration" : "redo_mask");
      } else if (mode === "mask") {
        if (mod) return;
        if (key === "b") {
          maskTools.setShape("point");
          maskTools.setErase(false);
        }
        if (key === "e") {
          maskTools.setShape("point");
          maskTools.setErase(true);
        }
        if (key === "v") maskTools.setShape("navigate");
        if (key === "f") setResetKey((k) => k + 1);
        if (key === "escape") setHelp(false);
        return;
      } else if (mod) return;
      else if (key === "v") setTool("pan");
      else if (key === "b") setTool("mask");
      else if (key === "p") {
        setTool("pick");
        setCalibrationStep(1);
      } else if (key === "e") setTool("erase");
      else if (key === "f") setResetKey((k) => k + 1);
      else if (
        (event.key === "Delete" || event.key === "Backspace") &&
        mode === "calibration" &&
        selectedPicks.length
      ) {
        event.preventDefault();
        void run("remove_picks", { indices: selectedPicks });
        setSelectedPicks([]);
      } else if (event.key === "Enter" && state?.hasImage && state.calibrated)
        void run("integrate", {}, "Integrating image and cake…");
      else if (event.key === "Escape") {
        setHelp(false);
        setTool("pan");
      }
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [run, state?.hasImage, state?.calibrated, mode, selectedPicks, maskTools]);
  const onHover = useCallback((point: { x: number; y: number } | null) => {
    hoverLatest.current = point;
    if (!point) {
      ++hoverSequence.current;
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
      setPixel(null);
      return;
    }
    if (hoverTimer.current) return;
    hoverTimer.current = setTimeout(
      async () => {
        hoverTimer.current = null;
        const latest = hoverLatest.current;
        if (!latest) return;
        hoverLastSent.current = performance.now();
        const sample = { x: Math.floor(latest.x), y: Math.floor(latest.y) };
        setPixel({ ...sample, value: null });
        if (inFlight.current || hoverRequest.current) return;
        hoverRequest.current = true;
        const epoch = hoverSequence.current;
        try {
          const result = await bridge.current?.("pixel", sample);
          if (epoch === hoverSequence.current && result?.ok)
            setPixel(result.pixel ?? null);
        } catch {
          /* Closing a window can reject its pending readout. */
        } finally {
          hoverRequest.current = false;
        }
      },
      Math.max(0, 100 - (performance.now() - hoverLastSent.current)),
    );
  }, []);
  const ready = !!state && !busy;
  const canIntegrate = !!state?.hasImage && !!state?.calibrated;
  const fitPoints =
    state?.calibration.picks.reduce(
      (sum, group) => sum + group.points.length,
      0,
    ) ?? 0;
  const fitReady =
    ready &&
    !!state?.calibration.setupConfirmed &&
    !setupDirty &&
    !advancedDirty &&
    fitPoints > 0 &&
    fitPoints >= (state?.calibration.freeParameterCount ?? 6);
  return (
    <div
      className="app"
      data-accent={accent}
      data-text-size={largeText ? "large" : "normal"}
    >
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark">
            <CrystalMark />
          </div>
          <span>Dioptas</span>
        </div>
        <div className="project-breadcrumb">
          <FolderOpen size={14} />
          <span>{state?.projectName ?? "Untitled experiment"}</span>
          <ChevronRight size={13} />
          <strong>
            {mode === "calibration"
              ? "Calibration"
              : mode === "mask"
                ? "Mask"
                : mode === "map"
                  ? "Map"
                  : "Integration"}
          </strong>
        </div>
        <div className="header-actions">
          <button
            className="text-size-button"
            aria-label="Larger text"
            title="Larger interface text"
            aria-pressed={largeText}
            onClick={() => setLargeText((v) => !v)}
          >
            Aa
          </button>
          <select
            className="accent-choice"
            aria-label="Accent color"
            value={accent}
            onChange={(e) => setAccent(e.target.value)}
          >
            <option value="orange">Warm orange</option>
            <option value="green">Dioptase green</option>
          </select>
          <button
            className="quiet"
            disabled={!ready}
            onClick={() => run("open_project", {}, "Opening project…")}
          >
            <FolderOpen size={15} />
            Open project
          </button>
          <button
            className="quiet"
            disabled={!ready || (!state?.hasImage && !map)}
            onClick={() => run("save_project", {}, "Saving project…")}
            title="Save project · ⌘S"
          >
            <Save size={15} />
            Save
          </button>
          <div className="header-divider" />
          <button
            className="icon-button"
            aria-label="Show keyboard shortcuts"
            title="Keyboard shortcuts"
            onClick={() => setHelp(true)}
          >
            <CircleHelp size={18} />
          </button>
        </div>
      </header>
      <div className="app-body">
        <nav className="mode-navigation" aria-label="Workspace modes">
          <div className="workspace-label">
            <Layers size={14} />
            <span>WORKSPACE</span>
          </div>
          <button
            className={`workspace-nav ${mode === "calibration" ? "workspace-active" : ""}`}
            onClick={() => {
              setMode("calibration");
              setTool(calibrationStep === 1 ? "pick" : "pan");
            }}
          >
            <Crosshair size={17} />
            <span>Calibration</span>
            {mode === "calibration" && <span className="active-dot" />}
          </button>
          <button
            className={`workspace-nav ${mode === "integration" ? "workspace-active" : ""}`}
            onClick={() => {
              setMode("integration");
              setTool("pan");
            }}
          >
            <Activity size={17} />
            <span>Integration</span>
            {mode === "integration" && <span className="active-dot" />}
          </button>
          <button
            className={`workspace-nav ${mode === "mask" ? "workspace-active" : ""}`}
            onClick={() => {
              setMode("mask");
              setTool("pan");
            }}
          >
            <Layers size={17} />
            <span>Mask</span>
            {mode === "mask" && <span className="active-dot" />}
          </button>
          <button
            className={`workspace-nav ${mode === "map" ? "workspace-active" : ""}`}
            onClick={() => {
              setMode("map");
              setTool("pan");
            }}
          >
            <Layers size={17} />
            <span>Map</span>
            {mode === "map" && <span className="active-dot" />}
          </button>
        </nav>

        <IntegrationWorkspace active={mode === "integration"} display={integrationDisplay}>
        <main
          className={`${mode}-mode`}
          data-integration-display={integrationDisplay}
        >
          {mode === "map" ? (
            <MapView
              map={map}
              image={image}
              mask={mask}
              pattern={pattern}
              state={state}
              ready={ready}
              run={run}
              request={requestMap}
              warning={mapWarning}
              reintegrate={mapReintegrate}
              mapLevels={mapLevels}
              linked={linked}
            />
          ) : mode === "mask" ? (
            <MaskView
              image={image}
              mask={mask}
              state={state}
              ready={ready}
              busy={!!busy}
              run={run}
              tools={maskTools}
              resetKey={resetKey}
              onHover={onHover}
              pixel={pixel}
            />
          ) : (
            <>
              {mode === "integration" && (
                <IntegrationDisplayControls
                  value={integrationDisplay}
                  onChange={setIntegrationDisplay}
                />
              )}
              {mode === "calibration" && (
                <div className="workspace-toolbar">
                  <div
                    className="calibration-step-buttons"
                    role="group"
                    aria-label="Calibration steps"
                  >
                    {[
                      "Image & setup",
                      "Pick rings",
                      "Calibrate",
                      "Validate",
                    ].map((label, index) => (
                      <button
                        key={label}
                        aria-label={`Step ${index + 1}: ${label}`}
                        aria-pressed={calibrationStep === index}
                        className={calibrationStep === index ? "active" : ""}
                        disabled={
                          (index === 1 && !state?.hasImage) ||
                          (index === 3 && !state?.calibrated) ||
                          (index === 2 &&
                            !state?.calibration.picks.length &&
                            !state?.calibrated)
                        }
                        onClick={() => {
                          setCalibrationStep(index);
                          setTool(index === 1 ? "pick" : "pan");
                        }}
                      >
                        {index + 1}. {label}
                      </button>
                    ))}
                  </div>

                  {state?.calibration.rmsDegrees != null && (
                    <span className="fit-summary">
                      RMS {number(state.calibration.rmsDegrees, 5)}°
                    </span>
                  )}
                </div>
              )}
              {error && (
                <div className="error-banner" role="alert">
                  <CircleX size={16} />
                  <span>{error}</span>
                  <button
                    aria-label="Dismiss error"
                    onClick={() => setError(null)}
                  >
                    ×
                  </button>
                </div>
              )}
              {state && state.configurationCount > 1 && (
                <div className="info-banner">
                  Project contains {state.configurationCount} configurations.
                  This preview displays configuration{" "}
                  {state.configurationIndex + 1}; all configurations are
                  retained when saving.
                </div>
              )}
              <div
                className={`views-grid ${mode === "calibration" ? (calibrationStep === 3 ? "validation-views" : "image-only") : ""}`}
              >
                <section className="panel detector-panel">
                  <div className="detector-toolbar">
                    <div className="tool-group">
                      {mode === "calibration" && (
                        <button
                          className={tool === "pick" ? "active" : ""}
                          aria-label="Pick calibration peaks"
                          title="Pick peaks · P"
                          onClick={() => {
                            setTool("pick");
                            setCalibrationStep(1);
                          }}
                        >
                          <Plus size={14} />
                        </button>
                      )}
                      <button
                        className={tool === "pan" ? "active" : ""}
                        aria-label="Plot navigation"
                        title="Rectangle zoom / right-drag pan · V"
                        onClick={() => setTool("pan")}
                      >
                        <Hand size={14} />
                      </button>
                      <button
                        className={tool === "mask" ? "active" : ""}
                        aria-label="Mask brush"
                        title="Mask brush · B"
                        onClick={() => setTool("mask")}
                      >
                        <Crosshair size={14} />
                      </button>
                      <button
                        className={tool === "erase" ? "active" : ""}
                        aria-label="Erase mask"
                        title="Erase mask · E"
                        onClick={() => setTool("erase")}
                      >
                        <Eraser size={14} />
                      </button>
                    </div>
                    {mode === "calibration" && calibrationStep === 1 && (
                      <span className="picking-ring" data-testid="active-ring">
                        {tool === "pick" ? "Picking" : "Current"} ring{" "}
                        <strong>{ring}</strong>
                      </span>
                    )}
                    <span className="tool-description">
                      {tool === "pick"
                        ? `Pick ring ${ring}`
                        : tool === "pan"
                          ? "Zoom & inspect"
                          : tool === "mask"
                            ? "Paint mask"
                            : "Erase mask"}
                    </span>
                    {(tool === "mask" || tool === "erase") && (
                      <label className="brush-size">
                        <input
                          aria-label="Brush radius"
                          type="range"
                          min="2"
                          max="150"
                          value={radius}
                          onChange={(e) => setRadius(Number(e.target.value))}
                        />
                        <span>{radius} px</span>
                      </label>
                    )}
                    <div className="toolbar-spacer" />
                    <button
                      className="icon-button"
                      disabled={!ready || !state?.canUndoMask}
                      onClick={() => run("undo_mask", {}, "Restoring mask…")}
                      aria-label="Undo mask stroke"
                      title="Undo mask · ⌘Z"
                    >
                      <Undo2 size={14} />
                    </button>
                    <button
                      className="icon-button"
                      disabled={!ready || !state?.hasImage}
                      onClick={() =>
                        run("clear_mask", {}, "Clearing painted mask…")
                      }
                      aria-label="Clear painted mask"
                      title="Clear painted mask"
                    >
                      <Trash2 size={14} />
                    </button>
                    <ZoomModeSelect
                      value={detectorZoom}
                      onChange={setDetectorZoom}
                      label="Detector zoom mode"
                    />
                  </div>
                  {image ? (
                    <div className="detector-workspace">
                      <RasterView
                        raster={image}
                        zoomMode={detectorZoom}
                        mask={mask ?? undefined}
                        maskOpacity={
                          state?.transparentMask?.valueOf() ? 0.72 : 1
                        }
                        limits={limits}
                        log={logImage}
                        palette={palette}
                        tool={tool}
                        radius={radius}
                        busy={!!busy}
                        resetKey={resetKey}
                        onHover={onHover}
                        peaks={
                          mode === "calibration"
                            ? state?.calibration.picks.flatMap((p, index) =>
                                p.points.map(([y, x]) => ({
                                  x,
                                  y,
                                  ring: p.ring,
                                  selected: selectedPicks.includes(index),
                                })),
                              )
                            : []
                        }
                        rings={
                          mode === "calibration" && showRings
                            ? [...rings, ...(linked?.contours ?? [])]
                            : (linked?.contours ?? [])
                        }
                        showNumbers={showNumbers}
                        activeRing={
                          mode === "calibration" && calibrationStep === 1
                            ? ring
                            : undefined
                        }
                        onPick={(point) => {
                          if (mode === "calibration" && calibrationStep === 1)
                            void run(
                              "pick_peak",
                              { ...point, ring, automatic },
                              "Finding peaks…",
                            );
                        }}
                        onInspect={(point) => {
                          if (
                            state?.calibrated &&
                            (mode === "integration" || calibrationStep === 3)
                          )
                            void run("validation_position", {
                              source: "image",
                              ...point,
                            });
                        }}
                        onStroke={(points, erase) =>
                          run(
                            "mask_stroke",
                            { points, radius, erase },
                            "Applying mask and integrating…",
                          )
                        }
                      />
                      <ImageIntensity
                        preferences={
                          multipleImages
                            ? multiDetectorPreferences
                            : detectorPreferences
                        }
                        onPreferences={
                          multipleImages
                            ? setMultiDetectorPreferences
                            : setDetectorPreferences
                        }
                        raster={image}
                        ready={ready}
                        onAuto={(settings) =>
                          run(
                            "image_levels",
                            { ...settings },
                            "Updating intensity range…",
                          )
                        }
                        limits={limits}
                        onLimits={setLimits}
                        log={logImage}
                        onLog={setLogImage}
                        palette={palette}
                        onPalette={setPalette}
                      />
                    </div>
                  ) : (
                    <div className="empty-view">
                      <div className="empty-icon">
                        <FileImage size={32} strokeWidth={1} />
                      </div>
                      <h3>Open a calibrant image</h3>
                      <p>
                        Open a calibrant image to begin, or explore
                        <br />
                        the included CeO₂ reference measurement.
                      </p>
                      <button
                        className="primary"
                        disabled={!ready}
                        onClick={() =>
                          run("open_image", {}, "Opening detector image…")
                        }
                      >
                        <Plus size={15} />
                        Open detector image
                      </button>
                      {state?.exampleAvailable && (
                        <button
                          className="text-button"
                          disabled={!ready}
                          onClick={() =>
                            run("example", {}, "Loading CeO₂ reference data…")
                          }
                        >
                          Explore example
                          <ArrowUpRight size={14} />
                        </button>
                      )}
                    </div>
                  )}
                  <div className="panel-footer detector-readout">
                    <span
                      data-testid="mouse-readout"
                      data-pixel-x={pixel?.x}
                      data-pixel-row={
                        pixel && image
                          ? image.fullHeight - 1 - pixel.y
                          : undefined
                      }
                    >
                      {pixel
                        ? `x ${pixel.x} · y ${image ? image.fullHeight - 1 - pixel.y : pixel.y} · I ${pixel.value === null ? "—" : number(pixel.value, 3)}`
                        : "Left-drag zoom · right-drag pan · right-click out"}
                    </span>
                    {mode === "calibration" && (
                      <div className="image-overlay-controls">
                        <label>
                          <input
                            aria-label="Show calibrant lines"
                            type="checkbox"
                            checked={showRings}
                            onChange={(e) => setShowRings(e.target.checked)}
                          />
                          Calibrant lines
                        </label>
                        <label>
                          <input
                            aria-label="Show ring numbers"
                            type="checkbox"
                            checked={showNumbers}
                            disabled={!showRings}
                            onChange={(e) => setShowNumbers(e.target.checked)}
                          />
                          Numbers
                        </label>
                      </div>
                    )}
                  </div>
                </section>
                {(mode === "integration" || calibrationStep === 3) && (
                  <section className="panel cake-panel">
                    {cake ? (
                      <div className="detector-workspace cake-workspace">
                        <RasterView
                          raster={cake}
                          linkedPosition={linked?.twoTheta}
                          onInspect={(point) => {
                            const x =
                              cake.radialRange[0] +
                              (point.x / cake.fullWidth) *
                                (cake.radialRange[1] - cake.radialRange[0]);
                            void run("validation_position", {
                              source: "cake",
                              x,
                            });
                          }}
                          zoomMode={cakeZoom}
                          cake
                          limits={cakeLimits}
                          log={cakeLog}
                          palette={cakePalette}
                          resetKey={resetKey}
                        />
                        <ImageIntensity
                          preferences={cakePreferences}
                          onPreferences={setCakePreferences}
                          display="cake"
                          raster={cake}
                          ready={ready}
                          onAuto={(settings) =>
                            run(
                              "image_levels",
                              { ...settings, source: "cake" },
                              "Updating cake intensity…",
                            )
                          }
                          limits={cakeLimits}
                          onLimits={setCakeLimits}
                          log={cakeLog}
                          onLog={setCakeLog}
                          palette={cakePalette}
                          onPalette={setCakePalette}
                        />
                      </div>
                    ) : (
                      <div className="empty-view secondary-empty">
                        <Layers size={30} strokeWidth={1} />
                        <h3>Azimuthal cake</h3>
                        <p>
                          Load an image and its calibration
                          <br />
                          to calculate the azimuthal cake.
                        </p>
                      </div>
                    )}
                    <div className="panel-footer">
                      <span>
                        {cake
                          ? unitLabel(cake.unit)
                          : "Awaiting calibrated image"}
                      </span>
                      <ZoomModeSelect
                        value={cakeZoom}
                        onChange={setCakeZoom}
                        label="Cake zoom mode"
                      />
                    </div>
                  </section>
                )}
                {((pattern && calibrationStep === 3) ||
                  mode === "integration") && (
                  <section className="panel pattern-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="panel-dot amber" />
                        <h2>Integrated pattern</h2>
                        {pattern && (
                          <span className="pattern-legend">
                            <span /> {state?.imageName}
                          </span>
                        )}
                      </div>
                      <div className="pattern-actions">
                        <ZoomModeSelect
                          value={patternZoom}
                          onChange={setPatternZoom}
                          label="Pattern zoom mode"
                        />
                        <span className="panel-meta">
                          {pattern
                            ? `${number(pattern.x.length, 0)} points`
                            : "1D integration"}
                        </span>
                        <div className="segmented small">
                          <button
                            className={!logPattern ? "selected" : ""}
                            onClick={() => setLogPattern(false)}
                          >
                            Linear
                          </button>
                          <button
                            className={logPattern ? "selected" : ""}
                            onClick={() => setLogPattern(true)}
                          >
                            Log
                          </button>
                        </div>
                      </div>
                    </div>
                    {pattern ? (
                      <PatternView
                        pattern={pattern}
                        log={logPattern}
                        zoomMode={patternZoom}
                        linkedPosition={linked?.radial}
                        calibrantLines={
                          showRings ? state?.calibration.referenceLines : []
                        }
                        showNumbers={showNumbers}
                        curves={
                          mode === "integration" ? pattern.curves : undefined
                        }
                        referenceLines={
                          mode === "integration"
                            ? pattern.phaseLines
                            : undefined
                        }
                        onPick={(x) => {
                          if (state?.calibrated)
                            void run("validation_position", {
                              source: "pattern",
                              x,
                            });
                        }}
                      />
                    ) : (
                      <div className="empty-pattern">
                        <Activity size={25} strokeWidth={1} />
                        <span>
                          Your integrated diffraction pattern will appear here.
                        </span>
                      </div>
                    )}
                    <div className="panel-footer">
                      <span>
                        Left-drag zoom · right-drag pan · right-click out
                      </span>
                      <span>
                        {state?.elapsedMs !== null &&
                        state?.elapsedMs !== undefined
                          ? `1D + 2D integration · ${number(state.elapsedMs, 0)} ms`
                          : ""}
                      </span>
                    </div>
                  </section>
                )}
              </div>
            </>
          )}
        </main>
        <aside
          className={`sidebar ${mode === "calibration" ? "calibration-task-panel" : mode === "map" ? "map-task-panel" : ""}`}
        >
          <div className="options-label">
            {mode === "mask" ? "MASK OPTIONS" : "EXPERIMENT OPTIONS"}
          </div>
          <div className="sidebar-scroll">
            {mode === "map" ? (
              <MapControls
                map={map}
                state={state}
                ready={ready}
                run={run}
                reintegrate={mapReintegrate}
                onReintegrate={setMapReintegrate}
              />
            ) : mode === "mask" ? (
              <MaskPanel
                state={state}
                ready={ready}
                run={run}
                tools={maskTools}
              />
            ) : (
              <>
                {mode === "calibration" && calibrationStep > 0 ? (
                  <div
                    className="calibration-source-mini"
                    title={state?.imagePath ?? ""}
                  >
                    <FileImage size={16} />
                    <span>{state?.imageName ?? "No image"}</span>
                  </div>
                ) : mode === "calibration" ? (
                  <>
                    <section className="sidebar-section">
                      <div className="section-label">DATA SOURCE</div>
                      <button
                        className="source-card"
                        disabled={!ready}
                        onClick={() =>
                          run("open_image", {}, "Opening detector image…")
                        }
                        title={state?.imagePath ?? "Open a detector image"}
                      >
                        <div className="file-icon">
                          <FileImage size={20} />
                        </div>
                        <div>
                          <strong>
                            {state?.imageName ?? "Open detector image"}
                          </strong>
                          <small>
                            {state?.shape
                              ? `${number(state.shape[1])} × ${number(state.shape[0])} pixels`
                              : "TIFF, EDF, CBF, HDF5…"}
                          </small>
                        </div>
                        <Plus size={15} />
                      </button>
                      {state?.hasImage && (
                        <div className="file-actions">
                          <button
                            aria-label="Previous image"
                            disabled={!ready}
                            onClick={() =>
                              run(
                                "next_image",
                                { direction: -1 },
                                "Opening previous image…",
                              )
                            }
                          >
                            ← Previous
                          </button>
                          <button
                            aria-label="Next image"
                            disabled={!ready}
                            onClick={() =>
                              run(
                                "next_image",
                                { direction: 1 },
                                "Opening next image…",
                              )
                            }
                          >
                            Next →
                          </button>
                        </div>
                      )}
                      {state?.exampleAvailable && (
                        <button
                          className="example-link"
                          disabled={!ready}
                          onClick={() =>
                            run("example", {}, "Loading CeO₂ reference data…")
                          }
                        >
                          <Sparkles size={12} />
                          {state?.hasImage
                            ? "Reload CeO₂ example"
                            : "Try the CeO₂ example"}
                          <ArrowUpRight size={12} />
                        </button>
                      )}
                    </section>
                  </>
                ) : null}
                {mode === "calibration" &&
                  (calibrationStep === 0 || calibrationStep === 2) && (
                    <CalibrationControls
                      onDirtyChange={setSetupDirty}
                      step={calibrationStep}
                      calibration={state?.calibration}
                      ready={ready}
                      run={run}
                    />
                  )}
                {mode === "calibration" && (
                  <>
                    <CalibrationExtras
                      state={state}
                      step={calibrationStep}
                      ready={ready}
                      run={run}
                      onDirtyChange={setAdvancedDirty}
                    />
                    {(calibrationStep === 1 || calibrationStep === 3) && (
                      <CalibrationPanel
                        setupDirty={setupDirty || advancedDirty}
                        selected={selectedPicks}
                        onSelected={setSelectedPicks}
                        step={calibrationStep}
                        state={state}
                        ready={ready}
                        ring={ring}
                        setRing={(value) => {
                          setRing(value);
                          setSelectedPicks(
                            state?.calibration.picks.flatMap((p, i) =>
                              p.ring === value ? [i] : [],
                            ) ?? [],
                          );
                        }}
                        automatic={automatic}
                        setAutomatic={setAutomatic}
                        run={run}
                      />
                    )}
                    {(calibrationStep === 0 || calibrationStep === 3) && (
                      <GeometryEditor
                        calibration={state?.calibration}
                        ready={ready}
                        run={run}
                      />
                    )}
                    {calibrationStep === 3 && (
                      <section className="compact-section">
                        <label className="field-label">
                          Validation calibrant
                          <select
                            aria-label="Validation calibrant"
                            disabled={!ready}
                            value={state?.calibration.calibrant ?? "CeO2"}
                            onChange={(e) =>
                              run(
                                "validation_calibrant",
                                { calibrant: e.target.value },
                                "Updating reference lines…",
                              )
                            }
                          >
                            {(state?.calibration.calibrants ?? []).map(
                              (name) => (
                                <option key={name}>{name}</option>
                              ),
                            )}
                          </select>
                        </label>
                        <button
                          className="quiet full-input"
                          disabled={!ready}
                          onClick={() =>
                            run(
                              "open_calibrant",
                              { validation: true },
                              "Loading reference spacings…",
                            )
                          }
                        >
                          Load custom reference…
                        </button>
                      </section>
                    )}
                    {(calibrationStep === 0 || calibrationStep === 3) && (
                      <label className="check-row">
                        <input
                          aria-label="Transparent mask overlay"
                          type="checkbox"
                          checked={state?.transparentMask ?? false}
                          disabled={!ready || !state?.useMask}
                          onChange={(e) =>
                            run("settings", {
                              transparent_mask: e.target.checked,
                            })
                          }
                        />
                        Transparent mask
                      </label>
                    )}
                    <div className="file-actions">
                      <button
                        disabled={!ready || !state?.calibration.canUndo}
                        onClick={() => run("undo_calibration")}
                      >
                        Undo
                      </button>
                      <button
                        disabled={!ready || !state?.calibration.canRedo}
                        onClick={() => run("redo_calibration")}
                      >
                        Redo
                      </button>
                    </div>
                  </>
                )}
                {mode === "integration" && (
                  <IntegrationView state={state} ready={ready} run={run} />
                )}
              </>
            )}
          </div>
          {mode === "calibration" && (
            <div className="task-navigation">
              <button
                className="secondary"
                disabled={calibrationStep === 0}
                onClick={() => {
                  const next = calibrationStep - 1;
                  setCalibrationStep(next);
                  setTool(next === 1 ? "pick" : "pan");
                }}
              >
                ‹ Back
              </button>
              {calibrationStep < 2 && (
                <button
                  className="primary"
                  disabled={
                    calibrationStep === 0
                      ? !state?.hasImage || setupDirty
                      : !state?.calibration.picks.length
                  }
                  onClick={() => {
                    const next = calibrationStep + 1;
                    setCalibrationStep(next);
                    setTool(next === 1 ? "pick" : "pan");
                  }}
                >
                  {["Next: Pick rings", "Next: Calibrate"][calibrationStep]} ›
                </button>
              )}
              {calibrationStep === 0 && setupDirty && (
                <span className="fit-input-note">
                  Apply your setup changes before continuing.
                </span>
              )}
              {calibrationStep === 2 && (
                <>
                  <button
                    className="primary fit-button"
                    disabled={!fitReady}
                    onClick={() =>
                      run("calibrate", {}, "Fitting detector geometry…")
                    }
                  >
                    {state?.calibrated
                      ? "Refine geometry"
                      : "Calibrate detector"}
                  </button>
                  {!fitReady && (
                    <span className="fit-input-note">
                      {setupDirty || advancedDirty
                        ? "Apply your parameter changes before fitting."
                        : !state?.calibration.setupConfirmed
                          ? "Confirm the experiment values with Apply setup."
                          : fitPoints <
                              (state?.calibration.freeParameterCount ?? 6)
                            ? `Select at least ${state?.calibration.freeParameterCount ?? 6} peaks for the current free parameters.`
                            : "Processing…"}
                    </span>
                  )}
                </>
              )}
            </div>
          )}
        </aside>
        </IntegrationWorkspace>
      </div>
      <footer className="app-status">
        <div>
          {busy ? (
            <LoaderCircle className="spin" size={13} />
          ) : (
            <span className="ready-dot" />
          )}
          <span role="status">
            {progress?.running
              ? `${progress.label ?? (mode === "integration" ? "Processing" : "Refining ring")} ${progress.current} / ${progress.total}`
              : busy ||
                (mode === "calibration"
                  ? !state?.hasImage
                    ? "Open a calibrant image to begin."
                    : [
                        "Check image orientation and detector settings, then continue to Pick rings.",
                        `Pick ring ${ring}. ${state.calibration.workflow.autoIncrement ? "Ring number increases after each pick." : "Ring number stays fixed."}`,
                        "Check fit parameters, then calibrate the detector.",
                        "Inspect the rings and residual, then save the calibration.",
                      ][calibrationStep]
                  : mode === "map"
                    ? map
                      ? "Select a map cell to inspect its detector image and pattern."
                      : "Load scan images or a processed batch."
                    : canIntegrate
                      ? "Ready"
                      : "Load a calibration to integrate this image.")}
          </span>
        </div>
        <div>
          {progress?.running && (
            <button
              className="secondary"
              onClick={() => {
                void bridge.current?.("cancel_refinement");
              }}
            >
              {mode === "map"
                ? "Cancel map integration"
                : mode === "integration"
                  ? "Cancel processing"
                  : mode === "mask"
                    ? "Cancel mask processing"
                    : "Cancel refinement"}
            </button>
          )}
          <span>{state?.imageName ?? "No image loaded"}</span>
          <span className="status-divider" />
          <span>
            {import.meta.env.DEV ? "Live preview" : "Desktop preview · 01"}
          </span>
        </div>
      </footer>
      {notice && (
        <div className="toast" role="status">
          <Check size={15} />
          {notice}
        </div>
      )}
      {help && (
        <div className="modal-backdrop" onClick={() => setHelp(false)}>
          <section
            className="help-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Keyboard shortcuts"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-heading">
              <h2>Keyboard shortcuts</h2>
              <button
                className="icon-button"
                aria-label="Close shortcuts"
                onClick={() => setHelp(false)}
              >
                ×
              </button>
            </div>

            {[
              ["Open detector image", "⌘ / Ctrl O"],
              ["Save project", "⌘ / Ctrl S"],
              ["Undo painted mask", "⌘ / Ctrl Z"],
              ["Pick / navigate / mask / erase", "P / V / B / E"],
              ["Fit detector image", "F"],
              ["Zoom image or cake", "Scroll"],
              ["Zoom (selected mode)", "Left drag"],
              ["Pan any plot", "Right drag"],
              ["Zoom out one step", "Right click"],
              ["Zoom out two steps", "Right double-click"],
              ["Fit detector image", "F"],
            ].map(([label, key]) => (
              <div className="shortcut-row" key={label}>
                <span>{label}</span>
                <kbd>{key}</kbd>
              </div>
            ))}
            <button
              className="primary"
              autoFocus
              onClick={() => setHelp(false)}
            >
              Back to the data
              <ArrowUpRight size={15} />
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
