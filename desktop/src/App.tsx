import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Crosshair,
  FileImage,
  FolderOpen,
  Layers,
  LoaderCircle,
  Plus,
  Redo2,
  Save,
  Settings,
  Sparkles,
  Undo2,
} from "lucide-react";
import { connect, updateWindowTitle } from "./bridge";
import { MapModeIcon, MaskModeIcon } from "./ModeIcons";
import { SettingsWorkspace } from "./SettingsWorkspace";
import "./sharedFooter.css";
import { usePlotReadout, type PatternHover } from "./plotReadout";
import { shapeHelp } from "./maskDomain";
import type {
  Cake,
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
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import { colorMaps } from "./colorMaps";
import { IntegrationView, IntegrationDisplayControls } from "./IntegrationView";
import { IntegrationWorkspace } from "./IntegrationWorkspace";
import {
  CalibrationExtras,
  GeometryEditor,
  ManualGeometryDialog,
} from "./CalibrationExtras";
import type { RingOverlay } from "./types";
import type { ZoomMode } from "./usePlotNavigation";

export default function App() {
  const [integrationDisplay, setIntegrationDisplay] = useState("image");
  const [calibrationStep, setCalibrationStep] = useState(0);
  const [manualGeometryOpen, setManualGeometryOpen] = useState(false);
  const [geometryDirty, setGeometryDirty] = useState(false);
  const [selectedPicks, setSelectedPicks] = useState<number[]>([]);
  const [advancedDirty, setAdvancedDirty] = useState(false);
  const [largeText, setLargeText] = useState(() => {
    try {
      return localStorage.getItem("dioptas-large-text") === "true";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("dioptas-large-text", String(largeText));
    } catch {
      /* Preferences are optional when local storage is unavailable. */
    }
  }, [largeText]);
  const [showRings, setShowRings] = useState(true),
    [showNumbers, setShowNumbers] = useState(true);
  const [linked, setLinked] = useState<Response["linked"]>();
  const [progress, setProgress] = useState<Response["progress"]>();
  const [patternZoom, setPatternZoom] = useState<ZoomMode>("horizontal");
  const [setupDirty, setSetupDirty] = useState(false);
  const [mode, setMode] = useState<
    "calibration" | "integration" | "mask" | "map"
  >("calibration");
  const activeMode = useRef(mode);
  useEffect(() => {
    activeMode.current = mode;
  }, [mode]);
  const maskTools = useMaskTools();
  const {
    reading: plotReading,
    report: reportPlot,
    clear: clearPlot,
  } = usePlotReadout();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const closeSettings = useCallback(() => {
    setSettingsOpen(false);
    document.querySelector<HTMLButtonElement>(".navigation-settings")?.focus();
  }, []);
  const [maskSelection, setMaskSelection] = useState<{
    text: string;
    cancel: () => void;
  } | null>(null);
  const [mapPatternZoom, setMapPatternZoom] = useState<ZoomMode>("horizontal");
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
  const commandTail = useRef<Promise<void> | null>(null);
  const pendingMaskDraws = useRef(0);
  const [state, setState] = useState<State | null>(null);
  useEffect(() => {
    void updateWindowTitle(state?.imageName).catch((error) =>
      console.warn("Could not update the native window title:", error),
    );
  }, [state?.imageName]);
  const [image, setImage] = useState<Raster | null>(null),
    [mask, setMask] = useState<Raster | null>(null);
  const [cake, setCake] = useState<Cake | null>(null),
    [pattern, setPattern] = useState<Pattern | null>(null);
  const [busy, setBusy] = useState("Connecting to Dioptas…"),
    [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const tool: Tool =
    mode === "calibration" && calibrationStep === 1 ? "pick" : "pan";
  const [logImage, setLogImage] = useState(false),
    [logPattern, setLogPattern] = useState(false);
  const [palette, setPalette] = useState<Palette>("grey");
  const [limits, setLimits] = useState<[number, number]>([0, 100]);
  const cakeSource = useRef<Cake | null>(null);
  const [cakeLimits, setCakeLimits] = useState<[number, number]>([0, 100]);
  const [cakeLog, setCakeLog] = useState(false);
  const [cakePalette, setCakePalette] = useState<Palette>("grey");
  const [detectorPreferences, setDetectorPreferences] =
    useImageDisplayPreferences("detector", "vertical");
  const [cakePreferences, setCakePreferences] = useImageDisplayPreferences(
    "cake",
    "horizontal",
  );
  const [multiDetectorPreferences, setMultiDetectorPreferences] =
    useImageDisplayPreferences("multi-detector", "horizontal");
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
  const canDeferIntegration = useRef(false);
  const apply = useCallback((result: Response) => {
    if (!result.ok)
      throw new Error(result.error || "The operation could not be completed.");
    if ("map" in result) setMap(result.map ?? null);
    if (result.mapLevels) setMapLevels(result.mapLevels);
    if ("mapWarning" in result) setMapWarning(result.mapWarning ?? null);
    if (result.state) {
      // An existing live preview may still have the earlier Python worker
      // loaded until the user restarts it.
      canDeferIntegration.current = "integrationDirty" in result.state;
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
      onSuccess?: (result: Response) => void,
    ) => {
      if (!bridge.current || (inFlight.current && !pendingMaskDraws.current))
        return;
      const commandMode = activeMode.current;
      const maskDrawing =
        commandMode === "mask" &&
        (command === "mask_stroke" ||
          (command === "mask_edit" &&
            ["rectangle", "circle", "polygon", "arc"].includes(
              String(args.operation),
            )));
      // Keep rapid drawing and the following edit in order without disabling
      // every control for each small mask update.
      const previous = commandTail.current;
      let release!: () => void;
      const completion = new Promise<void>((resolve) => (release = resolve));
      commandTail.current = completion;
      if (maskDrawing) pendingMaskDraws.current++;
      if (previous) await previous;
      inFlight.current = true;
      const displayOnly =
        command === "settings" &&
        typeof args.transparent_mask === "boolean" &&
        Object.keys(args).length === 1;
      const quiet = displayOnly || maskDrawing;
      if (!quiet) setBusy(message);
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
        const result = await bridge.current(
          command,
          commandMode === "mask" && canDeferIntegration.current
            ? { ...args, defer_integration: true }
            : args,
        );
        apply(result);
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
          !result.cancelled &&
          ["calibrate", "manual_geometry", "open_calibration"].includes(command)
        ) {
          setCalibrationStep(3);
        }
        onSuccess?.(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        try {
          apply(await bridge.current("state"));
        } catch {
          /* Keep the original error visible. */
        }
      } finally {
        if (!quiet) setBusy("");
        inFlight.current = false;
        if (maskDrawing) pendingMaskDraws.current--;
        if (commandTail.current === completion) commandTail.current = null;
        release();
      }
    },
    [apply],
  );
  useEffect(() => {
    if (
      state?.integrationDirty &&
      state.hasImage &&
      state.calibrated &&
      !busy &&
      !error &&
      !settingsOpen &&
      mode !== "mask"
    )
      void run("integrate", {}, "Integrating image and cake…");
  }, [
    state?.integrationDirty,
    state?.hasImage,
    state?.calibrated,
    busy,
    error,
    settingsOpen,
    mode,
    run,
  ]);
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
      ++hoverSequence.current;
      hoverLatest.current = null;
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
      if (settingsOpen) return;
      if (
        target.closest('[role="dialog"], dialog') ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      )
        return;
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
        return;
      } else if (mod) return;
      else if (key === "b" || key === "e") {
        setMode("mask");
        maskTools.setShape("point");
        maskTools.setErase(key === "e");
      } else if (key === "p" && state?.hasImage && !setupDirty) {
        setMode("calibration");
        setCalibrationStep(1);
      } else if (key === "f") setResetKey((k) => k + 1);
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
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [
    run,
    state?.hasImage,
    state?.calibrated,
    state?.calibration.setupConfirmed,
    setupDirty,
    mode,
    selectedPicks,
    maskTools,
    settingsOpen,
  ]);
  const onPatternHover = useCallback(
    (point: PatternHover | null) => {
      reportPlot(
        "pattern",
        point
          ? {
              text: `${unitLabel(point.unit)} ${number(point.x, 4)} · I ${point.y === null ? "—" : number(point.y, 3)}`,
              hint:
                point.hint ??
                "Left drag zooms · right drag pans · right double-click restores the fitted view.",
            }
          : null,
      );
    },
    [reportPlot],
  );
  const sampleHover = useCallback(function scheduleHover() {
    if (hoverTimer.current || hoverRequest.current || !hoverLatest.current)
      return;
    hoverTimer.current = setTimeout(
      async () => {
        hoverTimer.current = null;
        const latest = hoverLatest.current;
        if (!latest) return;
        hoverLastSent.current = performance.now();
        if (inFlight.current || !bridge.current) {
          scheduleHover();
          return;
        }
        const sample = { x: Math.floor(latest.x), y: Math.floor(latest.y) };
        hoverRequest.current = true;
        const epoch = hoverSequence.current;
        try {
          const result = await bridge.current("pixel", sample);
          // Publish coordinates and intensity together; pending reads must not
          // replace a valid reading with a temporary missing-value marker.
          if (epoch === hoverSequence.current && result.ok)
            setPixel(result.pixel ?? null);
        } catch {
          /* Closing a window can reject its pending readout. */
        } finally {
          hoverRequest.current = false;
          const pending = hoverLatest.current;
          // Coalesce movement during the request, including the last position
          // when the mouse stops before the outstanding response arrives.
          if (
            pending &&
            (epoch !== hoverSequence.current ||
              Math.floor(pending.x) !== sample.x ||
              Math.floor(pending.y) !== sample.y)
          )
            scheduleHover();
        }
      },
      Math.max(0, 100 - (performance.now() - hoverLastSent.current)),
    );
  }, []);
  const onHover = useCallback(
    (point: { x: number; y: number } | null) => {
      hoverLatest.current = point;
      if (!point) {
        ++hoverSequence.current;
        if (hoverTimer.current) clearTimeout(hoverTimer.current);
        hoverTimer.current = null;
        setPixel(null);
        return;
      }
      sampleHover();
    },
    [sampleHover],
  );
  useEffect(() => {
    reportPlot(
      "detector",
      pixel
        ? {
            text: `x ${pixel.x} · y ${image ? image.fullHeight - 1 - pixel.y : pixel.y} · I ${pixel.value === null ? "—" : number(pixel.value, 3)}`,
            x: pixel.x,
            value: pixel.value,
            row: image ? image.fullHeight - 1 - pixel.y : pixel.y,
            hint:
              mode === "mask"
                ? shapeHelp[maskTools.shape]
                : "Left drag zooms · right drag pans · right double-click restores the fitted view.",
          }
        : null,
    );
  }, [pixel, image?.fullHeight, mode, maskTools.shape, reportPlot]);
  useEffect(() => {
    onHover(null);
    clearPlot();
  }, [mode, settingsOpen, onHover, clearPlot]);

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
  const fitBlocker =
    setupDirty || advancedDirty
      ? "Apply your parameter changes before fitting."
      : !state?.calibration.setupConfirmed
        ? "Confirm the start values with Apply fit parameters."
        : fitPoints < (state?.calibration.freeParameterCount ?? 6)
          ? `Select at least ${state?.calibration.freeParameterCount ?? 6} peaks for the current free parameters.`
          : "Processing…";
  const statusMessage =
    error ||
    (progress?.running
      ? `${progress.label ?? (mode === "integration" ? "Processing" : "Refining ring")} ${progress.current} / ${progress.total}`
      : notice ||
        busy ||
        maskSelection?.text ||
        (mode === "map" ? mapWarning : null) ||
        plotReading?.hint ||
        (mode === "calibration" && calibrationStep === 2 && !fitReady
          ? fitBlocker
          : null) ||
        (mode === "calibration" && calibrationStep === 3 && geometryDirty
          ? "Apply geometry changes before refining or saving."
          : null) ||
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
            : mode === "mask"
              ? `${shapeHelp[maskTools.shape]} · ${number(state?.maskedPixels ?? 0, 0)} masked`
              : canIntegrate
                ? "Ready"
                : "Load a calibration to integrate this image."));
  return (
    <div className="app" data-text-size={largeText ? "large" : "normal"}>
      <div className="app-body">
        <nav className="mode-navigation" aria-label="Workspace modes">
          <button
            className={`workspace-nav ${!settingsOpen && mode === "calibration" ? "workspace-active" : ""}`}
            aria-label="Calibration"
            aria-pressed={!settingsOpen && mode === "calibration"}
            title="Calibration"
            onClick={() => {
              setSettingsOpen(false);
              setMode("calibration");
            }}
          >
            <Crosshair size={20} />
            <span>Calib</span>
          </button>
          <button
            className={`workspace-nav ${!settingsOpen && mode === "mask" ? "workspace-active" : ""}`}
            aria-label="Mask"
            aria-pressed={!settingsOpen && mode === "mask"}
            title="Mask"
            onClick={() => {
              setSettingsOpen(false);
              setMode("mask");
            }}
          >
            <MaskModeIcon />
            <span>Mask</span>
          </button>
          <button
            className={`workspace-nav ${!settingsOpen && mode === "integration" ? "workspace-active" : ""}`}
            aria-label="Integration"
            aria-pressed={!settingsOpen && mode === "integration"}
            title="Integration"
            onClick={() => {
              setSettingsOpen(false);
              setMode("integration");
            }}
          >
            <Activity size={20} />
            <span>Int</span>
          </button>
          <button
            className={`workspace-nav ${!settingsOpen && mode === "map" ? "workspace-active" : ""}`}
            aria-label="Map"
            aria-pressed={!settingsOpen && mode === "map"}
            title="Map"
            onClick={() => {
              setSettingsOpen(false);
              setMode("map");
            }}
          >
            <MapModeIcon />
            <span>Map</span>
          </button>
          <div className="navigation-utilities">
            <div
              className="navigation-group navigation-history"
              role="group"
              aria-label="Edit history"
            >
              <button
                className="workspace-nav"
                aria-label="Undo"
                title={`Undo ${mode === "calibration" ? "calibration" : "mask"} edit · ⌘/Ctrl+Z`}
                disabled={
                  !ready ||
                  !(mode === "calibration"
                    ? state?.calibration.canUndo
                    : state?.canUndoMask)
                }
                onClick={() =>
                  run(mode === "calibration" ? "undo_calibration" : "undo_mask")
                }
              >
                <Undo2 size={18} />
              </button>
              <button
                className="workspace-nav"
                aria-label="Redo"
                title={`Redo ${mode === "calibration" ? "calibration" : "mask"} edit · ⇧⌘/Ctrl+Z`}
                disabled={
                  !ready ||
                  !(mode === "calibration"
                    ? state?.calibration.canRedo
                    : state?.canRedoMask)
                }
                onClick={() =>
                  run(mode === "calibration" ? "redo_calibration" : "redo_mask")
                }
              >
                <Redo2 size={18} />
              </button>
            </div>
            <div className="navigation-group" role="group" aria-label="Project">
              {state?.projectName && (
                <div className="navigation-project" title={state.projectName}>
                  {state.projectName}
                </div>
              )}
              <button
                className="workspace-nav project-action"
                aria-label="Open project"
                title="Open project"
                disabled={!ready}
                onClick={() => run("open_project", {}, "Opening project…")}
              >
                <FolderOpen size={20} />
              </button>
              <button
                className="workspace-nav project-action"
                aria-label="Save project"
                disabled={!ready || (!state?.hasImage && !map)}
                onClick={() => run("save_project", {}, "Saving project…")}
                title={
                  state?.projectName
                    ? `Save ${state.projectName} · ⌘/Ctrl+S`
                    : "Save project · ⌘/Ctrl+S"
                }
              >
                <Save size={20} />
              </button>
            </div>
            <button
              className={`workspace-nav navigation-settings ${settingsOpen ? "workspace-active" : ""}`}
              onClick={() => {
                clearPlot();
                setSettingsOpen((open) => !open);
              }}
              aria-label="Settings"
              aria-controls="settings-workspace"
              aria-expanded={settingsOpen}
              title="Settings"
            >
              <Settings size={20} />
            </button>
          </div>
        </nav>

        <div className="workspace-stage">
          <IntegrationWorkspace
            concealed={settingsOpen}
            active={mode === "integration"}
            display={integrationDisplay === "cake" ? "cake" : "image"}
          >
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
                  reintegrate={mapReintegrate}
                  mapLevels={mapLevels}
                  linked={linked}
                  reportPlot={reportPlot}
                  onDetectorHover={onHover}
                  onPatternHover={onPatternHover}
                  patternZoom={mapPatternZoom}
                />
              ) : mode === "mask" ? (
                <MaskView
                  active={!settingsOpen}
                  image={image}
                  mask={mask}
                  state={state}
                  ready={ready}
                  busy={!!busy}
                  run={run}
                  tools={maskTools}
                  resetKey={resetKey}
                  onHover={onHover}
                  onSelectionStatus={setMaskSelection}
                />
              ) : (
                <>
                  {mode === "integration" && (
                    <IntegrationDisplayControls
                      value={integrationDisplay === "cake" ? "cake" : "image"}
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
                            className={
                              calibrationStep === index ? "active" : ""
                            }
                            disabled={
                              (index > 0 && setupDirty) ||
                              (index === 1 && !state?.hasImage) ||
                              (index === 3 && !state?.calibrated) ||
                              (index === 2 &&
                                !state?.calibration.picks.length &&
                                !state?.calibrated)
                            }
                            onClick={() => {
                              setCalibrationStep(index);
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
                    </div>
                  )}
                  {state && state.configurationCount > 1 && (
                    <div className="info-banner">
                      Project contains {state.configurationCount}{" "}
                      configurations. This preview displays configuration{" "}
                      {state.configurationIndex + 1}; all configurations are
                      retained when saving.
                    </div>
                  )}
                  <div
                    className={`views-grid ${mode === "calibration" ? (calibrationStep === 3 ? "validation-views" : "image-only") : ""}`}
                  >
                    <section className="panel detector-panel">
                      {image ? (
                        <div className="detector-workspace">
                          <RasterView
                            raster={image}
                            zoomMode="rectangle"
                            mask={mask ?? undefined}
                            maskOpacity={
                              state?.transparentMask?.valueOf() ? 0.72 : 1
                            }
                            limits={limits}
                            log={logImage}
                            palette={palette}
                            tool={tool}
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
                            currentPeakRing={
                              mode === "calibration" ? ring : undefined
                            }
                            activeRing={
                              mode === "calibration" && calibrationStep === 1
                                ? ring
                                : undefined
                            }
                            onPick={(point) => {
                              if (
                                mode === "calibration" &&
                                calibrationStep === 1
                              )
                                void run(
                                  "pick_peak",
                                  { ...point, ring, automatic },
                                  "Finding peaks…",
                                );
                            }}
                            onInspect={(point) => {
                              if (
                                state?.calibrated &&
                                (mode === "integration" ||
                                  calibrationStep === 3)
                              )
                                void run("validation_position", {
                                  source: "image",
                                  ...point,
                                });
                            }}
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
                                run(
                                  "example",
                                  {},
                                  "Loading CeO₂ reference data…",
                                )
                              }
                            >
                              Explore example
                              <ArrowUpRight size={14} />
                            </button>
                          )}
                        </div>
                      )}
                    </section>
                    {(mode === "integration" || calibrationStep === 3) && (
                      <section className="panel cake-panel">
                        {cake ? (
                          <div className="detector-workspace cake-workspace">
                            <RasterView
                              raster={cake}
                              onHover={(point) =>
                                reportPlot(
                                  "cake",
                                  point && cake
                                    ? {
                                        text: `2θ ${number(cake.radialRange[0] + (point.x / cake.fullWidth) * (cake.radialRange[1] - cake.radialRange[0]), 4)}° · χ ${number(cake.azimuthRange[0] + (point.y / cake.fullHeight) * (cake.azimuthRange[1] - cake.azimuthRange[0]), 2)}° · I ${point.value === null ? "—" : number(point.value, 3)}`,
                                        hint: "Left drag zooms · right drag pans · right double-click restores the fitted view.",
                                      }
                                    : null,
                                )
                              }
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
                              zoomMode="rectangle"
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
                      </section>
                    )}
                    {((pattern && calibrationStep === 3) ||
                      mode === "integration") && (
                      <section className="panel pattern-panel">
                        {mode === "integration" && (
                          <div className="pattern-display-controls">
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
                        )}
                        {pattern ? (
                          <PatternView
                            pattern={pattern}
                            log={logPattern}
                            zoomMode={patternZoom}
                            onHover={onPatternHover}
                            linkedPosition={linked?.radial}
                            calibrantLines={
                              showRings ? state?.calibration.referenceLines : []
                            }
                            showNumbers={showNumbers}
                            curves={
                              mode === "integration"
                                ? pattern.curves
                                : undefined
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
                              Your integrated diffraction pattern will appear
                              here.
                            </span>
                          </div>
                        )}
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
                    {mode === "calibration" && calibrationStep === 0 ? (
                      <>
                        <section className="sidebar-section setup-image-source">
                          <div className="setup-image-row">
                            <button
                              className="secondary setup-open-image"
                              disabled={!ready}
                              onClick={() =>
                                run("open_image", {}, "Opening detector image…")
                              }
                              title={
                                state?.imagePath ?? "Open a detector image"
                              }
                            >
                              <FolderOpen size={14} />
                              Open image
                            </button>
                            {state?.hasImage && (
                              <div className="setup-image-navigation">
                                <button
                                  className="secondary"
                                  title="Previous image"
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
                                  ←
                                </button>
                                <button
                                  className="secondary"
                                  title="Next image"
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
                                  →
                                </button>
                              </div>
                            )}
                          </div>
                          {state?.imageName && (
                            <div
                              className="setup-image-filename"
                              title={state.imagePath ?? state.imageName}
                            >
                              {state.imageName}
                            </div>
                          )}
                          {state?.exampleAvailable && !state?.hasImage && (
                            <button
                              className="example-link"
                              disabled={!ready}
                              onClick={() =>
                                run(
                                  "example",
                                  {},
                                  "Loading CeO₂ reference data…",
                                )
                              }
                            >
                              <Sparkles size={12} />
                              Try the CeO₂ example
                              <ArrowUpRight size={12} />
                            </button>
                          )}
                        </section>
                      </>
                    ) : null}
                    {mode === "calibration" && calibrationStep === 0 && (
                      <CalibrationControls
                        onDirtyChange={setSetupDirty}
                        onContinue={() => setCalibrationStep(1)}
                        additionalOptions={
                          <CalibrationExtras
                            state={state}
                            step={0}
                            ready={ready}
                            run={run}
                            onDirtyChange={setAdvancedDirty}
                            imageToolsOnly
                          />
                        }
                        maskControls={
                          <CalibrationExtras
                            state={state}
                            step={0}
                            ready={ready}
                            run={run}
                            onDirtyChange={setAdvancedDirty}
                            hideImageTools
                          />
                        }
                        calibration={state?.calibration}
                        ready={ready}
                        hasImage={!!state?.hasImage}
                        run={run}
                      />
                    )}
                    {mode === "calibration" && (
                      <>
                        {calibrationStep === 3 && (
                          <section className="calibration-validation-reference">
                            <label className="calibration-field-row">
                              <span>Calibrant</span>
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
                              className="icon-button"
                              aria-label="Load custom validation reference"
                              title="Load custom reference spacings"
                              disabled={!ready}
                              onClick={() =>
                                run(
                                  "open_calibrant",
                                  { validation: true },
                                  "Loading reference spacings…",
                                )
                              }
                            >
                              <FolderOpen size={16} />
                            </button>
                          </section>
                        )}
                        {calibrationStep === 3 && (
                          <GeometryEditor
                            calibration={state?.calibration}
                            ready={ready}
                            run={run}
                            embedded
                            formId="validation-geometry-form"
                            onDirtyChange={setGeometryDirty}
                          />
                        )}
                        {calibrationStep === 1 && (
                          <CalibrationPanel
                            selected={selectedPicks}
                            onSelected={setSelectedPicks}
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
                        {calibrationStep === 2 && (
                          <CalibrationExtras
                            state={state}
                            step={calibrationStep}
                            ready={ready}
                            run={run}
                            onDirtyChange={setAdvancedDirty}
                          />
                        )}
                      </>
                    )}
                    {mode === "integration" && (
                      <IntegrationView state={state} ready={ready} run={run} />
                    )}
                  </>
                )}
              </div>
              {mode === "calibration" && (
                <div className="calibration-task-footer">
                  <div className="task-navigation">
                    {calibrationStep > 0 && (
                      <button
                        className="secondary"
                        onClick={() => {
                          const next = calibrationStep - 1;
                          setCalibrationStep(next);
                        }}
                      >
                        ‹ Back
                      </button>
                    )}
                    {calibrationStep === 0 && (
                      <>
                        <button
                          type="submit"
                          form="calibration-setup-form"
                          className="primary"
                          disabled={!ready || !state?.hasImage}
                        >
                          Next: Pick rings ›
                        </button>
                      </>
                    )}
                    {calibrationStep === 1 && (
                      <button
                        className="primary"
                        disabled={!ready || !state?.calibration.picks.length}
                        onClick={() => {
                          const next = calibrationStep + 1;
                          setCalibrationStep(next);
                        }}
                      >
                        {
                          ["Next: Pick rings", "Next: Calibrate"][
                            calibrationStep
                          ]
                        }{" "}
                        ›
                      </button>
                    )}
                    {calibrationStep === 2 && (
                      <>
                        <button
                          className="primary fit-button"
                          title={!fitReady ? fitBlocker : undefined}
                          disabled={!fitReady}
                          onClick={() =>
                            run("calibrate", {}, "Fitting detector geometry…")
                          }
                        >
                          {state?.calibrated
                            ? "Refine geometry"
                            : "Calibrate detector"}
                        </button>
                      </>
                    )}
                    {calibrationStep === 3 && (
                      <>
                        {geometryDirty ? (
                          <button
                            type="submit"
                            form="validation-geometry-form"
                            className="secondary"
                            disabled={!ready}
                          >
                            Apply geometry
                          </button>
                        ) : (
                          <>
                            <button
                              className="secondary"
                              disabled={!fitReady || geometryDirty}
                              onClick={() =>
                                run(
                                  "calibrate",
                                  {},
                                  "Refining detector geometry…",
                                )
                              }
                            >
                              Refine geometry
                            </button>
                          </>
                        )}
                        <button
                          className="primary"
                          disabled={
                            !ready ||
                            geometryDirty ||
                            !state?.calibrated ||
                            state?.calibration.fitDirty
                          }
                          onClick={() =>
                            run(
                              "save_calibration",
                              {},
                              "Saving PONI calibration…",
                            )
                          }
                        >
                          <Save size={14} />
                          Save .poni calibration
                        </button>
                      </>
                    )}
                  </div>
                  <div className="calibration-alternative-entry">
                    <div>
                      <button
                        className="secondary"
                        disabled={!ready}
                        onClick={() =>
                          run(
                            "open_calibration",
                            {},
                            "Loading PONI calibration…",
                          )
                        }
                      >
                        <FolderOpen size={14} />
                        Load .poni
                      </button>
                      <button
                        className="secondary"
                        disabled={!ready}
                        onClick={() => setManualGeometryOpen(true)}
                      >
                        Enter manually
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </aside>
          </IntegrationWorkspace>
          {manualGeometryOpen && (
            <ManualGeometryDialog
              calibration={state?.calibration}
              ready={ready}
              onClose={() => setManualGeometryOpen(false)}
              run={(command, args, message) =>
                run(command, args, message, () => {
                  if (command === "manual_geometry")
                    setManualGeometryOpen(false);
                })
              }
            />
          )}
          {settingsOpen && (
            <SettingsWorkspace
              state={state}
              ready={ready}
              run={run}
              largeText={largeText}
              onLargeText={setLargeText}
              onClose={closeSettings}
              returnLabel={
                {
                  calibration: "Calibration",
                  mask: "Mask",
                  integration: "Integration",
                  map: "Map",
                }[mode]
              }
              patternZoom={mode === "map" ? mapPatternZoom : patternZoom}
              onPatternZoom={
                mode === "map" ? setMapPatternZoom : setPatternZoom
              }
              patternLabel={
                mode === "map" ? "Map pattern" : "Integrated pattern"
              }
            />
          )}
        </div>
        <footer className="app-status">
          <div className="plot-status">
            {plotReading && plotReading.source !== "detector" && (
              <span className="plot-status-source">
                {
                  {
                    cake: "Cake",
                    pattern: "Pattern",
                    map: "Map",
                  }[plotReading.source]
                }
              </span>
            )}
            <span
              data-testid="mouse-readout"
              className="plot-status-reading"
              data-plot={plotReading?.source}
              data-pixel-x={plotReading?.x}
              data-pixel-row={plotReading?.row}
              title={plotReading?.text}
            >
              {plotReading?.source === "detector" ? (
                <>
                  <span className="plot-coordinate">
                    x{" "}
                    <span className="plot-coordinate-value">
                      {plotReading.x}
                    </span>
                  </span>{" "}
                  <span className="plot-coordinate">
                    y{" "}
                    <span className="plot-coordinate-value">
                      {plotReading.row}
                    </span>
                  </span>{" "}
                  <span>
                    I{" "}
                    {plotReading.value == null
                      ? "—"
                      : number(plotReading.value, 3)}
                  </span>
                </>
              ) : (
                (plotReading?.text ?? state?.imageName ?? "No image loaded")
              )}
            </span>
          </div>
          <div className="workflow-status">
            {busy ? (
              <LoaderCircle className="spin" size={13} />
            ) : (
              <span className="ready-dot" />
            )}
            <span role={error ? "alert" : "status"} title={statusMessage}>
              {statusMessage}
            </span>
            {error && (
              <button
                className="secondary status-action"
                aria-label="Dismiss error"
                onClick={() => setError(null)}
              >
                ×
              </button>
            )}
            {maskSelection && (
              <button
                className="secondary status-action"
                onClick={maskSelection.cancel}
              >
                Cancel selection
              </button>
            )}
            {progress?.running && (
              <button
                className="secondary status-action"
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
          </div>
        </footer>
      </div>
    </div>
  );
}
