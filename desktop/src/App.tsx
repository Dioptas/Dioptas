import { useNativePhaseEditorSync } from "./phaseEditorWindow";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
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
import { IntegrationModeIcon, MapModeIcon, MaskModeIcon } from "./ModeIcons";
import { SettingsWorkspace } from "./SettingsWorkspace";
import "./sharedFooter.css";
import { usePlotReadout, type PatternHover } from "./plotReadout";
import {
  ReadingFields,
  sourceLabel,
  patternReading,
  detectorReading,
  cakeReading,
  cakeCoordinates,
  coordinateValue,
  type SourcedReading,
} from "./PlotStatus";
import { radialFields } from "./radialReadout";
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
import { number } from "./types";
import { MapView } from "./MapView";
import { MapControls } from "./MapControls";
import type { MapData } from "./mapDomain";
import { MaskView } from "./MaskView";
import { MaskPanel } from "./MaskPanel";
import { useMaskTools } from "./maskDomain";
import { RasterView, type RasterExport } from "./RasterView";
import { PatternView } from "./PatternView";
import { ORIGINAL_PATTERN_UID } from "./integration";
import { useLiveBackground, DEFAULT_BACKGROUND } from "./useLiveBackground";
import { BACKGROUND_RANGE_COLOR } from "./drawRangeSelection";
import { CalibrationControls } from "./CalibrationControls";
import { CalibrationPanel } from "./CalibrationPanel";
import { CalibrationWorkflowTabs } from "./CalibrationWorkflowTabs";
import { CalibrationRingControls } from "./CalibrationRingControls";
import { ImageIntensity } from "./ImageIntensity";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import { colorMaps } from "./colorMaps";
import { IntegrationView } from "./IntegrationView";
import {
  IntegrationImageControls,
  IntegrationPatternActions,
  IntegrationPatternTools,
  useShiftedCake,
} from "./IntegrationPlotControls";
import { IntegrationWorkspace } from "./IntegrationWorkspace";
import {
  CalibrationExtras,
  type CalibrationFitDraft,
  GeometryEditor,
  ManualGeometryDialog,
} from "./CalibrationExtras";
import type { RingOverlay } from "./types";
import type { ZoomMode } from "./usePlotNavigation";

export default function App() {
  const detectorExport = useRef<RasterExport>(null);
  const cakeExport = useRef<RasterExport>(null);
  const [integrationDisplay, setIntegrationDisplay] = useState("image");
  const [sqrtPattern, setSqrtPattern] = useState(false);
  const [patternAntialias, setPatternAntialias] = useState(true);
  const [patternAutoRange, setPatternAutoRange] = useState(true);
  const [showOriginalPattern, setShowOriginalPattern] = useState(true);
  const [originalPatternColor, setOriginalPatternColor] = useState("#ffffff");
  const [selectedOverlayUid, setSelectedOverlayUid] = useState<string | null>(
    null,
  );
  const [inspectBackground, setInspectBackground] = useState(false);
  const [cakeShift, setCakeShift] = useState(0);
  const [correctedImage, setCorrectedImage] = useState(true);
  const correctedImageRef = useRef(true);
  correctedImageRef.current = correctedImage;
  const [rawImage, setRawImage] = useState<Raster | null>(null);
  const [showImagePhases, setShowImagePhases] = useState(false);
  const [phaseGuides, setPhaseGuides] = useState<RingOverlay[]>([]);
  const phaseGuideRevision = useRef<number | null>(null);
  const [calibrationStep, setCalibrationStep] = useState(0);
  const [validationConvention, setValidationConvention] = useState<
    "pyfai" | "fit2d"
  >(() => {
    try {
      return localStorage.getItem("dioptas-validation-convention") === "fit2d"
        ? "fit2d"
        : "pyfai";
    } catch {
      return "pyfai";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(
        "dioptas-validation-convention",
        validationConvention,
      );
    } catch {
      /* Keep the session preference when local storage is unavailable. */
    }
  }, [validationConvention]);
  const [manualGeometryOpen, setManualGeometryOpen] = useState(false);
  const [geometryDirty, setGeometryDirty] = useState(false);
  const [selectedPicks, setSelectedPicks] = useState<number[]>([]);
  const [advancedDirty, setAdvancedDirty] = useState(false);
  const [fitDraft, setFitDraft] = useState<CalibrationFitDraft | null>(null);
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
  const [clickedReading, setClickedReading] = useState<SourcedReading | null>(
    null,
  );
  const [localImageClick, setLocalImageClick] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [localPatternClick, setLocalPatternClick] = useState<number>();
  const [patternResolution, setPatternResolution] = useState(0.01);
  const [cakePixelResolution, setCakePixelResolution] = useState({
    x: 1,
    y: 1,
  });
  const [progress, setProgress] = useState<Response["progress"]>();
  const progressGeneration = useRef(0);
  const [patternZoom, setPatternZoom] = useState<ZoomMode>("rectangle");
  const [cakeZoom, setCakeZoom] = useState<ZoomMode>("rectangle");
  const [setupDirty, setSetupDirty] = useState(false);
  const [setupValid, setSetupValid] = useState(true);
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
  const [mapPatternZoom, setMapPatternZoom] = useState<ZoomMode>("rectangle");
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

  const [pickingEnabled, setPickingEnabled] = useState(true);
  const [ring, setRing] = useState(1),
    [automatic, setAutomatic] = useState(true);
  const [rings, setRings] = useState<RingOverlay[]>([]);
  const bridge = useRef<Invoke | null>(null),
    inFlight = useRef(false);
  const commandTail = useRef<Promise<void> | null>(null);
  const autoProcessInFlight = useRef(false);
  const pendingMaskDraws = useRef(0);
  const pendingBackgroundUpdates = useRef(0);
  const pendingOverlayEdits = useRef(0);
  const currentState = useRef<State | null>(null);
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
  const displayedCake = useShiftedCake(
    cake,
    mode === "integration" ? cakeShift : 0,
  );
  const [busy, setBusy] = useState("Connecting to Dioptas…"),
    [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const canPick = !!state?.hasImage && !setupDirty && !geometryDirty;
  const tool: Tool =
    mode === "calibration" && pickingEnabled && canPick ? "pick" : "pan";
  const [logImage, setLogImage] = useState(false),
    [logPattern, setLogPattern] = useState(false);
  const [palette, setPalette] = useState<Palette>("grey");
  const [limits, setLimits] = useState<[number, number]>([0, 100]);
  const imageSource = useRef<Raster | null>(null);
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
  const [pixel, setPixel] = useState<NonNullable<Response["pixel"]> | null>(
    null,
  );
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    hoverSequence = useRef(0);
  const hoverLatest = useRef<{ x: number; y: number } | null>(null);
  const hoverLastSent = useRef(0);
  const hoverRequest = useRef(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const canDeferIntegration = useRef(false);
  const apply = useCallback((result: Response, resetImageView = true) => {
    if (!result.ok)
      throw new Error(result.error || "The operation could not be completed.");
    if ("map" in result) setMap(result.map ?? null);
    if (result.mapLevels) setMapLevels(result.mapLevels);
    if ("mapWarning" in result) setMapWarning(result.mapWarning ?? null);
    if (result.state) {
      currentState.current = result.state;
      if (typeof result.state.integration.originalPatternVisible === "boolean")
        setShowOriginalPattern(result.state.integration.originalPatternVisible);
      if (result.state.integration.originalPatternColor)
        setOriginalPatternColor(result.state.integration.originalPatternColor);
      // An existing live preview may still have the earlier Python worker
      // loaded until the user restarts it.
      canDeferIntegration.current = "integrationDirty" in result.state;
      if (result.patternOnly)
        phaseGuideRevision.current = result.state.revision;
      setState((previous) => {
        const next = result.state!;
        if (!previous || !result.patternOnly) return next;
        // Retain unchanged detector/controls inputs during a pattern-only edit.
        return {
          ...next,
          calibration: previous.calibration,
          geometry: previous.geometry,
          integration: { ...next.integration, roi: previous.integration.roi },
        };
      });
    }
    if (result.phaseGuides) setPhaseGuides(result.phaseGuides);
    if (result.rawImage) setRawImage(result.rawImage);
    if (result.image) {
      const sourceChanged =
        result.image.data !== imageSource.current?.data ||
        result.image.width !== imageSource.current?.width ||
        result.image.height !== imageSource.current?.height;
      imageSource.current = result.image;
      ++hoverSequence.current;
      hoverLatest.current = null;
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
      setPixel(null);
      setImage(result.image);
      // Recovery and state refreshes can resend the same detector image.
      // Only a changed source should replace the user's contrast limits.
      if (sourceChanged)
        setLimits(
          activeMode.current === "integration" &&
            !correctedImageRef.current &&
            result.rawImage
            ? result.rawImage.limits
            : result.image.limits,
        );
      if (resetImageView) setResetKey((k) => k + 1);
    }
    if (result.levels)
      (result.display === "cake" ? setCakeLimits : setLimits)(result.levels);
    if (result.nextRing !== undefined) setRing(result.nextRing);
    if ("linked" in result) setLinked(result.linked);
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
      shouldRun?: () => boolean,
    ) => {
      const historyLabel = command.startsWith("redo")
        ? currentState.current?.redoLabel
        : currentState.current?.undoLabel;
      const overlayEditing =
        (command === "integration_overlay" && args.operation !== "load") ||
        ([
          "undo_mask",
          "redo_mask",
          "undo_calibration",
          "redo_calibration",
        ].includes(command) &&
          historyLabel === "integration_overlay");
      const liveBackground =
        command === "integration_background" && message === "";
      if (
        !bridge.current ||
        (command === "integration_autoprocess_poll" &&
          (inFlight.current || commandTail.current)) ||
        (inFlight.current &&
          !autoProcessInFlight.current &&
          !pendingMaskDraws.current &&
          !pendingBackgroundUpdates.current &&
          !pendingOverlayEdits.current &&
          !liveBackground &&
          command !== "image_levels")
      )
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
      if (overlayEditing) pendingOverlayEdits.current++;
      if (liveBackground) pendingBackgroundUpdates.current++;
      if (previous) await previous;
      if (shouldRun && !shouldRun()) {
        if (liveBackground) pendingBackgroundUpdates.current--;
        if (overlayEditing) pendingOverlayEdits.current--;
        if (commandTail.current === completion) commandTail.current = null;
        release();
        return;
      }
      inFlight.current = true;
      autoProcessInFlight.current = command === "integration_autoprocess_poll";
      const displayOnly =
        command === "settings" &&
        typeof args.transparent_mask === "boolean" &&
        Object.keys(args).length === 1;
      const quiet =
        displayOnly ||
        overlayEditing ||
        maskDrawing ||
        liveBackground ||
        command === "integration_autoprocess_poll" ||
        command === "image_levels";
      if (!quiet) {
        ++progressGeneration.current;
        setProgress(undefined);
        setBusy(message);
      }
      if (command !== "integration_autoprocess_poll") setError(null);
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
        if (command === "integration_autoprocess_poll" && result.state)
          setError(result.state.integration.autoProcessError || null);
        if (
          (command === "load_peaks" && !result.cancelled) ||
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
          // Recovery refreshes the current image too. A failed peak pick must
          // keep the user's zoom so they can retry at the same location.
          apply(await bridge.current("state"), false);
        } catch {
          /* Keep the original error visible. */
        }
      } finally {
        if (!quiet) {
          ++progressGeneration.current;
          setProgress(undefined);
          setBusy("");
        }
        inFlight.current = false;
        autoProcessInFlight.current = false;
        if (maskDrawing) pendingMaskDraws.current--;
        if (overlayEditing) pendingOverlayEdits.current--;
        if (liveBackground) pendingBackgroundUpdates.current--;
        if (commandTail.current === completion) commandTail.current = null;
        release();
      }
    },
    [apply],
  );
  useNativePhaseEditorSync(run, state?.revision);
  useEffect(() => {
    if (mode !== "integration" || !state?.integration.autoProcess) return;
    const timer = setInterval(() => {
      if (!settingsOpen) void run("integration_autoprocess_poll", {}, "");
    }, 1000);
    return () => clearInterval(timer);
  }, [mode, state?.integration.autoProcess, settingsOpen, run]);
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
    let active = true;
    let polling = false;
    const generation = progressGeneration.current;
    const timer = setInterval(() => {
      if (polling) return;
      polling = true;
      void bridge
        .current?.("progress")
        .then((r) => {
          if (active && generation === progressGeneration.current && r.ok)
            setProgress(r.progress);
        })
        .catch(() => {})
        .finally(() => {
          polling = false;
        });
    }, 150);
    return () => {
      active = false;
      clearInterval(timer);
    };
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
      } else if (key === "p" && canPick) {
        setMode("calibration");
        setPickingEnabled(true);
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
    canPick,
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
              ...patternReading(point, state?.geometry.wavelength),
              hint:
                point.hint ??
                "Left drag zooms · right drag pans · right double-click restores the fitted view.",
            }
          : null,
      );
    },
    [reportPlot, state?.geometry.wavelength],
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
          const result = await bridge.current("pixel", {
            ...sample,
            raw:
              activeMode.current === "integration" &&
              !correctedImageRef.current,
          });
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
            ...detectorReading(
              pixel,
              image ? image.fullHeight - 1 - pixel.y : pixel.y,
              state?.geometry.wavelength,
            ),
            hint:
              mode === "mask"
                ? shapeHelp[maskTools.shape]
                : "Left drag zooms · right drag pans · right double-click restores the fitted view.",
          }
        : null,
    );
  }, [
    pixel,
    image?.fullHeight,
    mode,
    maskTools.shape,
    reportPlot,
    state?.geometry.wavelength,
  ]);
  useEffect(() => {
    onHover(null);
    clearPlot();
  }, [mode, settingsOpen, onHover, clearPlot]);
  useEffect(() => {
    setClickedReading(null);
    setLocalImageClick(null);
    setLocalPatternClick(undefined);
  }, [
    state?.imagePath,
    state?.configurationIndex,
    state?.projectName,
    state?.integration.frame,
    state?.integration.patternName,
    JSON.stringify(state?.calibration.transformations),
    JSON.stringify(state?.geometry),
    JSON.stringify(state?.shape),
  ]);
  useEffect(() => setLocalPatternClick(undefined), [state?.unit]);

  const cakeClick = useMemo(() => {
    const view = displayedCake ?? cake;
    if (!view || linked?.azimuth == null) return null;
    const [low, high] = view.azimuthRange;
    const period =
      ((high - low) * view.fullHeight) / Math.max(1, view.fullHeight - 1);
    const azi =
      period >= 359
        ? low + ((((linked.azimuth - low) % 360) + 360) % 360)
        : linked.azimuth;
    if (azi < low || azi > high) return null;
    return {
      x:
        ((linked.twoTheta - view.radialRange[0]) /
          (view.radialRange[1] - view.radialRange[0])) *
        view.fullWidth,
      y: ((azi - low) / (high - low)) * view.fullHeight,
    };
  }, [linked, displayedCake, cake]);
  const clickPositionReading =
    clickedReading && linked && state
      ? {
          text: clickedReading.text,
          fields: [
            ...radialFields(
              linked.radial,
              state.unit,
              state.geometry.wavelength,
              patternResolution,
            ),
            ...(linked.azimuth == null
              ? []
              : [
                  {
                    label: "χ",
                    title: "Azimuth χ (°)",
                    kind: "coordinate" as const,
                    value: coordinateValue(
                      linked.azimuth,
                      cake
                        ? (cakePixelResolution.y / cake.fullHeight) *
                            (cake.azimuthRange[1] - cake.azimuthRange[0])
                        : 0.1,
                    ),
                  },
                ]),
          ],
        }
      : clickedReading
        ? {
            ...clickedReading,
            fields: clickedReading.fields?.filter((f) => !!f.unit) ?? [
              {
                label: "x",
                value: String(clickedReading.x),
                kind: "pixel" as const,
              },
              {
                label: "y",
                value: String(clickedReading.row),
                kind: "pixel" as const,
              },
            ],
          }
        : null;

  const ready = !!state && !busy;
  const backgroundContext = (s: State | null) =>
    JSON.stringify([
      s?.unit,
      s?.configurationIndex,
      s?.imagePath,
      s?.integration.patternName,
      s?.projectName,
    ]);
  const backgroundKey = backgroundContext(state);
  const liveBackground = useLiveBackground(
    backgroundKey,
    state?.integration.patternBackground ?? DEFAULT_BACKGROUND,
    (settings, isCurrent) => {
      return run(
        "integration_background",
        {
          enabled: settings.enabled,
          smoothing: settings.smoothing,
          iterations: settings.iterations,
          order: settings.order,
          range: settings.range,
        },
        "",
        undefined,
        () =>
          isCurrent() &&
          backgroundContext(currentState.current) === backgroundKey,
      );
    },
  );
  const inspectedBackground =
    mode === "integration" &&
    inspectBackground &&
    liveBackground.settings.enabled
      ? liveBackground.settings
      : undefined;
  const inspectedOriginal = inspectedBackground
    ? pattern?.backgroundCurves?.[0]
    : undefined;
  const originalPatternVisible = showOriginalPattern;
  // Curve payloads follow the visible OverlayModel order.
  const selectedOverlayIndex =
    state?.integration.overlays
      .filter((overlay) => overlay.visible)
      .findIndex((overlay) => overlay.uid === selectedOverlayUid) ?? -1;
  const displayedPattern = useMemo(
    () =>
      pattern && inspectedOriginal
        ? { ...pattern, x: inspectedOriginal.x, y: inspectedOriginal.y }
        : pattern,
    [pattern, inspectedOriginal],
  );
  const displayedCurves = useMemo(
    () =>
      mode === "integration"
        ? [
            ...(pattern?.curves ?? []).map((curve, index) => ({
              ...curve,
              selected: index === selectedOverlayIndex,
            })),
            ...(inspectedBackground
              ? (pattern?.backgroundCurves ?? []).slice(
                  inspectedOriginal ? 1 : 0,
                )
              : []),
          ]
        : undefined,
    [
      mode,
      pattern?.curves,
      pattern?.backgroundCurves,
      selectedOverlayIndex,
      !!inspectedBackground,
      !!inspectedOriginal,
    ],
  );
  // The subtracted pattern can be cropped to the fitted range. Keep the slice
  // bounded by the original measurement so its edges can expand again.
  const backgroundX = pattern?.backgroundCurves?.[0]?.x ?? pattern?.x ?? [];
  const backgroundBounds = useMemo(
    () =>
      backgroundX.reduce<[number, number]>(
        ([min, max], x) =>
          Number.isFinite(x)
            ? [Math.min(min, x), Math.max(max, x)]
            : [min, max],
        [Infinity, -Infinity],
      ),
    [backgroundX],
  );
  const backgroundRange = inspectedBackground
    ? (liveBackground.settings.range ?? backgroundBounds)
    : undefined;
  useEffect(() => {
    if (!showImagePhases) {
      phaseGuideRevision.current = null;
      return;
    }
    if (
      mode === "integration" &&
      ready &&
      state &&
      phaseGuideRevision.current !== state.revision
    ) {
      phaseGuideRevision.current = state.revision;
      void run("integration_phase_guides", {}, "Updating phase guides…");
    }
  }, [mode, showImagePhases, state?.revision, ready]);
  const canIntegrate = !!state?.hasImage && !!state?.calibrated;
  const calibrationPreview =
    mode === "calibration" && busy ? progress?.calibration : undefined;
  const displayedRing = calibrationPreview?.activeRing ?? ring;
  const displayedCalibration =
    state?.calibration && calibrationPreview
      ? { ...state.calibration, picks: calibrationPreview.picks }
      : state?.calibration;
  const detectorPeaks = useMemo(
    () =>
      mode === "calibration"
        ? (displayedCalibration?.picks.flatMap((p, index) =>
            p.points.map(([y, x]) => ({
              x,
              y,
              ring: p.ring,
              selected: !calibrationPreview && selectedPicks.includes(index),
            })),
          ) ?? [])
        : [],
    [mode, displayedCalibration, calibrationPreview, selectedPicks],
  );
  const detectorRings = useMemo(
    () =>
      mode === "calibration"
        ? showRings
          ? (calibrationPreview?.rings ?? rings)
          : []
        : [
            ...(showImagePhases ? phaseGuides : []),
            ...(linked?.contours ?? []),
          ],
    [
      mode,
      showRings,
      calibrationPreview,
      rings,
      showImagePhases,
      phaseGuides,
      linked,
    ],
  );
  const cakeCalibrantLines = useMemo(
    () =>
      mode === "integration"
        ? showImagePhases
          ? phaseGuides
              .filter(
                (g, i, all) =>
                  all.findIndex(
                    (v) =>
                      v.phaseIndex === g.phaseIndex &&
                      v.reflectionIndex === g.reflectionIndex &&
                      v.twoTheta === g.twoTheta &&
                      v.color === g.color,
                  ) === i,
              )
              .map((g) => ({
                ring: 0,
                twoTheta: g.twoTheta!,
                color: g.color,
                lineWidth: g.lineWidth,
                opacity: g.opacity,
              }))
          : []
        : showRings
          ? state?.calibration.rings
          : undefined,
    [mode, showImagePhases, phaseGuides, showRings, state?.calibration],
  );
  const displayedRms =
    calibrationPreview?.rmsDegrees ?? state?.calibration.rmsDegrees;
  const fitPoints =
    state?.calibration.picks.reduce(
      (sum, group) => sum + group.points.length,
      0,
    ) ?? 0;
  const freeFitParameters = Object.values(
    fitDraft?.parameters ?? state?.calibration.parameters ?? {},
  ).filter((p) => p.refine).length;
  const validFitDraft =
    !fitDraft ||
    (Object.values(fitDraft.parameters).every((p) =>
      Number.isFinite(p.value),
    ) &&
      fitDraft.parameters.dist?.value > 0 &&
      fitDraft.parameters.wavelength?.value > 0 &&
      Number.isFinite(fitDraft.polarization) &&
      Math.abs(fitDraft.polarization) <= 1);
  const fitReady =
    ready &&
    (!!fitDraft || !!state?.calibration.setupConfirmed) &&
    !setupDirty &&
    !advancedDirty &&
    !geometryDirty &&
    validFitDraft &&
    fitPoints > 0 &&
    fitPoints >= freeFitParameters;
  const fitDraftDirty =
    !!fitDraft &&
    (fitDraft.polarization !== state?.calibration.polarization ||
      Object.entries(fitDraft.parameters).some(([key, parameter]) => {
        const applied = state?.calibration.parameters[key];
        return (
          parameter.value !== applied?.value ||
          parameter.refine !== applied?.refine
        );
      }));
  const canSaveCalibration =
    ready &&
    !!state?.calibrated &&
    !state.calibration.fitDirty &&
    !setupDirty &&
    !geometryDirty &&
    !fitDraftDirty;
  const fitBlocker = geometryDirty
    ? "Apply geometry changes on Validate before fitting."
    : setupDirty
      ? "Finish entering valid detector pixel sizes on Image."
      : advancedDirty
        ? "Finish entering valid refinement options."
        : !validFitDraft
          ? "Enter valid fit parameters."
          : fitPoints < Math.max(1, freeFitParameters)
            ? `Select at least ${Math.max(1, freeFitParameters)} peaks for the current free parameters.`
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
                "Check detector settings. Pick peaks on the image or open another tab.",
                pickingEnabled
                  ? `Pick ring ${ring}. ${state.calibration.workflow.autoIncrement ? "Ring number increases after each pick." : "Ring number stays fixed."}`
                  : "Picking is off. Move over the plots to inspect coordinates and intensity.",
                "Check fit parameters, then calibrate the detector.",
                state.calibration.fitDirty
                  ? "Ring selections changed. Calibrate or refine the geometry before saving."
                  : "Inspect the rings and residual. Save .poni is available in every tab.",
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
            <IntegrationModeIcon />
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
                title={`Undo ${mode === "calibration" ? "calibration" : mode === "integration" ? "integration" : "mask"} edit · ⌘/Ctrl+Z`}
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
                title={`Redo ${mode === "calibration" ? "calibration" : mode === "integration" ? "integration" : "mask"} edit · ⇧⌘/Ctrl+Z`}
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
                  onPatternZoom={setMapPatternZoom}
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
                  {mode === "calibration" && (
                    <div className="workspace-toolbar">
                      {displayedRms != null && (
                        <span className="fit-summary">
                          RMS {number(displayedRms, 5)}°
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
                            exportRef={detectorExport}
                            raster={
                              mode === "integration" &&
                              !correctedImage &&
                              rawImage
                                ? rawImage
                                : image
                            }
                            zoomMode="rectangle"
                            mask={
                              mode !== "integration" || state?.useMask
                                ? (mask ?? undefined)
                                : undefined
                            }
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
                            clickedPoint={
                              mode === "integration"
                                ? (linked?.imagePoint ?? localImageClick)
                                : null
                            }
                            peaks={detectorPeaks}
                            rings={detectorRings}
                            roi={
                              mode === "integration"
                                ? state?.integration.roi
                                : undefined
                            }
                            onRoiChange={
                              mode === "integration"
                                ? (limits) =>
                                    run(
                                      "integration_roi",
                                      { limits },
                                      "Updating integration region…",
                                    )
                                : undefined
                            }
                            showNumbers={mode === "calibration" && showNumbers}
                            currentPeakRing={
                              mode === "calibration" ? displayedRing : undefined
                            }
                            activeRing={
                              mode === "calibration" ? displayedRing : undefined
                            }
                            onPick={(point) => {
                              if (
                                mode === "calibration" &&
                                pickingEnabled &&
                                canPick
                              )
                                void run(
                                  "pick_peak",
                                  { ...point, ring, automatic },
                                  "Finding peaks…",
                                );
                            }}
                            onInspect={(point) => {
                              if (mode !== "integration") return;
                              setLocalImageClick(point);
                              setClickedReading({
                                source: "detector",
                                text: "Image click",
                                x: Math.floor(point.x),
                                row: image.fullHeight - 1 - Math.floor(point.y),
                                value: point.value,
                              });
                              if (state?.calibrated)
                                void run("validation_position", {
                                  source: "image",
                                  x: point.x,
                                  y: point.y,
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
                            raster={
                              mode === "integration" &&
                              !correctedImage &&
                              rawImage
                                ? rawImage
                                : image
                            }
                            ready={ready}
                            onAuto={(settings) =>
                              run(
                                "image_levels",
                                {
                                  ...settings,
                                  source:
                                    mode === "integration" && !correctedImage
                                      ? "raw_detector"
                                      : "detector",
                                },
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
                              exportRef={cakeExport}
                              raster={displayedCake ?? cake}
                              onResolution={setCakePixelResolution}
                              busy={!!busy}
                              onHover={(point) =>
                                reportPlot(
                                  "cake",
                                  point && cake
                                    ? {
                                        ...cakeReading(
                                          displayedCake ?? cake,
                                          point,
                                          state?.geometry.wavelength,
                                        ),
                                        hint: "Left drag zooms · right drag pans · right double-click restores the fitted view.",
                                      }
                                    : null,
                                )
                              }
                              linkedPosition={
                                mode === "integration"
                                  ? linked?.twoTheta
                                  : undefined
                              }
                              clickedPoint={
                                mode === "integration" ? cakeClick : null
                              }
                              activeRing={
                                mode === "calibration"
                                  ? displayedRing
                                  : undefined
                              }
                              calibrantLines={cakeCalibrantLines}
                              showNumbers={
                                mode === "calibration" && showNumbers
                              }
                              onInspect={(point) => {
                                if (mode !== "integration") return;
                                setLocalImageClick(null);
                                setClickedReading({
                                  source: "cake",
                                  ...cakeReading(
                                    displayedCake ?? cake,
                                    point,
                                    state?.geometry.wavelength,
                                  ),
                                });
                                const coords = cakeCoordinates(
                                  displayedCake ?? cake,
                                  point,
                                );
                                void run("validation_position", {
                                  source: "cake",
                                  ...coords,
                                });
                              }}
                              zoomMode={cakeZoom}
                              onZoomMode={setCakeZoom}
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
                          <>
                            <IntegrationPatternActions
                              state={state}
                              ready={ready}
                              run={run}
                            />
                            <IntegrationPatternTools
                              state={state}
                              ready={ready}
                              run={run}
                              background={liveBackground.settings}
                              onBackgroundChange={liveBackground.change}
                              log={logPattern}
                              sqrt={sqrtPattern}
                              onScale={(scale) => {
                                setLogPattern(scale === "log");
                                setSqrtPattern(scale === "sqrt");
                              }}
                              inspect={inspectBackground}
                              onInspect={() => setInspectBackground((v) => !v)}
                              antialias={patternAntialias}
                              onAntialias={() => setPatternAntialias((v) => !v)}
                              autoRange={patternAutoRange}
                              onAutoRange={() => setPatternAutoRange((v) => !v)}
                            />
                          </>
                        )}
                        {pattern ? (
                          <PatternView
                            pattern={displayedPattern!}
                            patternColor={
                              mode === "integration"
                                ? originalPatternColor
                                : "#ffffff"
                            }
                            showPattern={
                              mode !== "integration" || originalPatternVisible
                            }
                            emphasizePattern={
                              mode === "integration" &&
                              selectedOverlayUid === ORIGINAL_PATTERN_UID
                            }
                            compact={mode === "integration"}
                            log={logPattern}
                            sqrt={mode === "integration" && sqrtPattern}
                            antialias={
                              mode !== "integration" || patternAntialias
                            }
                            autoRange={
                              mode === "integration" && patternAutoRange
                            }
                            onAutoRange={
                              mode === "integration"
                                ? setPatternAutoRange
                                : undefined
                            }
                            zoomMode={patternZoom}
                            onZoomMode={setPatternZoom}
                            onHover={onPatternHover}
                            onResolution={setPatternResolution}
                            linkedPosition={
                              mode === "integration"
                                ? (linked?.radial ?? localPatternClick)
                                : undefined
                            }
                            activeRing={
                              mode === "calibration" ? displayedRing : undefined
                            }
                            calibrantLines={
                              mode === "calibration" && showRings
                                ? state?.calibration.referenceLines
                                : undefined
                            }
                            showNumbers={showNumbers}
                            regions={
                              backgroundRange &&
                              backgroundBounds[0] < backgroundBounds[1]
                                ? [
                                    {
                                      name: "Background range",
                                      appearance: "range",
                                      min: backgroundRange[0],
                                      max: backgroundRange[1],
                                      color: BACKGROUND_RANGE_COLOR,
                                      active: true,
                                      movable: false,
                                      bounds: [
                                        Math.min(
                                          backgroundBounds[0],
                                          backgroundRange[0],
                                        ),
                                        Math.max(
                                          backgroundBounds[1],
                                          backgroundRange[1],
                                        ),
                                      ],
                                      minWidth:
                                        ((backgroundBounds[1] -
                                          backgroundBounds[0]) /
                                          Math.max(1, backgroundX.length - 1)) *
                                        2,
                                    },
                                  ]
                                : undefined
                            }
                            editRegions={!!inspectedBackground && ready}
                            hoverHint={
                              inspectedBackground
                                ? "Drag an edge to update the background · drag inside to zoom · right drag pans"
                                : undefined
                            }
                            onRegionDragStart={liveBackground.begin}
                            regionsUpdating={liveBackground.updating}
                            onRegionInput={(_, min, max) =>
                              liveBackground.change({ range: [min, max] })
                            }
                            onRegionCancel={liveBackground.cancel}
                            onRegionChange={(_, min, max) =>
                              liveBackground.change({ range: [min, max] })
                            }
                            overlayLegend={
                              mode === "integration"
                                ? [
                                    ...(originalPatternVisible
                                      ? [
                                          {
                                            name:
                                              state?.integration?.patternName ??
                                              "",
                                            color: originalPatternColor,
                                          },
                                        ]
                                      : []),
                                    ...(pattern.curves ?? []),
                                  ]
                                : undefined
                            }
                            curves={displayedCurves}
                            referenceLines={
                              mode === "integration"
                                ? pattern.phaseLines
                                : undefined
                            }
                            onPick={(x, mouseY, resolution) => {
                              if (!ready || mode !== "integration") return;
                              const nearest = displayedPattern!.x.reduce(
                                (best, value, i) =>
                                  Math.abs(value - x) <
                                  Math.abs(displayedPattern!.x[best] - x)
                                    ? i
                                    : best,
                                0,
                              );
                              setLocalPatternClick(x);
                              setLocalImageClick(null);
                              setClickedReading({
                                source: "pattern",
                                ...patternReading(
                                  {
                                    x,
                                    mouseY,
                                    xResolution: resolution.x,
                                    yResolution: resolution.y,
                                    y: displayedPattern!.y[nearest],
                                    unit: displayedPattern!.unit,
                                  },
                                  state?.geometry.wavelength,
                                ),
                              });
                              if (state?.calibrated)
                                void run("validation_position", {
                                  source: "pattern",
                                  x,
                                });
                            }}
                          />
                        ) : (
                          <div className="empty-pattern">
                            <IntegrationModeIcon size={25} />
                            <span>
                              Your integrated diffraction pattern will appear
                              here.
                            </span>
                          </div>
                        )}
                      </section>
                    )}
                  </div>
                  {mode === "integration" && (
                    <IntegrationImageControls
                      onSaveImage={() => {
                        const source =
                          integrationDisplay === "cake" ? "cake" : "image";
                        const exporter = (
                          source === "cake" ? cakeExport : detectorExport
                        ).current;
                        if (!exporter) return;
                        void run(
                          "integration_save_image",
                          {
                            source,
                            png_data: exporter.png(),
                            suggested_name: `${state?.imageName?.replace(/\.[^.]+$/, "") ?? "image"}${source === "cake" ? "_cake" : ""}.png`,
                          },
                          "Saving image…",
                        );
                      }}
                      cakeShift={cakeShift}
                      onCakeShift={setCakeShift}
                      fullCake={
                        !!cake &&
                        (Math.abs(cake.azimuthRange[1] - cake.azimuthRange[0]) *
                          cake.height) /
                          Math.max(1, cake.height - 1) >=
                          359
                      }
                      value={integrationDisplay}
                      onChange={setIntegrationDisplay}
                      state={state}
                      ready={ready}
                      run={run}
                      showPhases={showImagePhases}
                      onShowPhases={() => setShowImagePhases((v) => !v)}
                      corrected={correctedImage}
                      onCorrected={() => {
                        setCorrectedImage((v) => !v);
                        setLimits(
                          (correctedImage ? rawImage : image)?.limits ?? limits,
                        );
                        onHover(null);
                      }}
                      roi={!!state?.integration.roi}
                      onRoi={() => {
                        const [h, w] = state?.shape ?? [1, 1];
                        void run("integration_roi", {
                          limits: state?.integration.roi
                            ? null
                            : [
                                Math.floor(h * 0.1),
                                Math.ceil(h * 0.9),
                                Math.floor(w * 0.1),
                                Math.ceil(w * 0.9),
                              ],
                        });
                      }}
                    />
                  )}
                </>
              )}
            </main>
            <aside
              className={`sidebar ${mode === "calibration" ? "calibration-task-panel" : mode === "map" ? "map-task-panel" : ""}`}
              data-calibration-section={
                mode === "calibration" ? calibrationStep : undefined
              }
            >
              <div className="options-label">
                {mode === "mask" ? "MASK OPTIONS" : "EXPERIMENT OPTIONS"}
              </div>
              {mode === "calibration" && (
                <CalibrationRingControls
                  calibration={displayedCalibration}
                  ring={displayedRing}
                  onRingChange={(value) => {
                    setRing(value);
                    setSelectedPicks(
                      state?.calibration.picks.flatMap((pick, index) =>
                        pick.ring === value ? [index] : [],
                      ) ?? [],
                    );
                  }}
                  picking={pickingEnabled}
                  onPickingChange={setPickingEnabled}
                  onAutoAdvanceChange={(autoIncrement) =>
                    run("workflow_settings", { autoIncrement })
                  }
                  ready={ready}
                  canPick={canPick}
                />
              )}
              {mode === "calibration" && (
                <CalibrationWorkflowTabs
                  active={calibrationStep}
                  disabled={[
                    false,
                    !setupValid || !state?.hasImage,
                    !setupValid || !state?.hasImage,
                    !setupValid || !state?.calibrated,
                  ]}
                  onChange={setCalibrationStep}
                />
              )}
              <div
                className="sidebar-scroll"
                id={
                  mode === "calibration"
                    ? "calibration-task-content"
                    : undefined
                }
                role={mode === "calibration" ? "tabpanel" : undefined}
                aria-labelledby={
                  mode === "calibration"
                    ? `calibration-section-${calibrationStep}`
                    : undefined
                }
              >
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
                        onValidityChange={setSetupValid}
                        additionalOptions={
                          <CalibrationExtras
                            state={state}
                            step={0}
                            ready={ready}
                            run={run}
                            onDirtyChange={() => {}}
                            imageToolsOnly
                          />
                        }
                        maskControls={
                          <CalibrationExtras
                            state={state}
                            step={0}
                            ready={ready}
                            run={run}
                            onDirtyChange={() => {}}
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
                        <div hidden={calibrationStep !== 3}>
                          <GeometryEditor
                            calibration={state?.calibration}
                            ready={ready}
                            run={run}
                            embedded
                            formId="validation-geometry-form"
                            convention={validationConvention}
                            onConventionChange={setValidationConvention}
                            onDirtyChange={setGeometryDirty}
                          />
                        </div>
                        {calibrationStep === 1 && (
                          <CalibrationPanel
                            selected={selectedPicks}
                            onSelected={setSelectedPicks}
                            onRingChange={setRing}
                            state={state}
                            ready={ready}
                            ring={ring}
                            automatic={automatic}
                            setAutomatic={setAutomatic}
                            run={run}
                          />
                        )}
                        <CalibrationExtras
                          state={state}
                          step={calibrationStep === 2 ? 2 : -1}
                          ready={ready}
                          run={run}
                          onDirtyChange={setAdvancedDirty}
                          onFitDraftChange={setFitDraft}
                        />
                      </>
                    )}
                    {mode === "integration" && (
                      <IntegrationView
                        state={state}
                        ready={ready}
                        run={run}
                        backgroundSettings={liveBackground.settings}
                        onBackgroundChange={liveBackground.change}
                        backgroundUpdating={liveBackground.updating}
                        onOverlaySelectionChange={setSelectedOverlayUid}
                        showOriginalPattern={originalPatternVisible}
                        onShowOriginalPatternChange={(visible) => {
                          void run("integration_overlay", {
                            operation: "original_visibility",
                            visible,
                          });
                        }}
                        originalPatternColor={originalPatternColor}
                        onOriginalPatternColorChange={(color) => {
                          void run("integration_overlay", {
                            operation: "original_color",
                            color,
                          });
                        }}
                      />
                    )}
                  </>
                )}
              </div>
              {mode === "calibration" && (
                <div className="calibration-task-footer">
                  {calibrationStep >= 2 && (
                    <div className="calibration-main-action">
                      {calibrationStep === 3 && geometryDirty && (
                        <button
                          type="submit"
                          form="validation-geometry-form"
                          className="primary calibration-apply-geometry"
                          disabled={!ready}
                        >
                          Apply geometry
                        </button>
                      )}
                      <button
                        className="primary fit-button"
                        title={`Start a fresh geometry from the current peaks and start values.${!fitReady ? ` ${fitBlocker}` : ""}`}
                        disabled={!fitReady}
                        onClick={() =>
                          run(
                            "calibrate",
                            { ...fitDraft, restart: true },
                            "Calibrating detector geometry…",
                          )
                        }
                      >
                        Calibrate
                      </button>
                      <button
                        className="secondary"
                        title={`Adjust the existing geometry using the current peaks.${!state?.calibrated ? " Calibrate or load a geometry first." : !fitReady ? ` ${fitBlocker}` : ""}`}
                        disabled={!fitReady || !state?.calibrated}
                        onClick={() =>
                          run(
                            "calibrate",
                            fitDraft ?? {},
                            "Refining detector geometry…",
                          )
                        }
                      >
                        Refine
                      </button>
                    </div>
                  )}
                  <div className="calibration-general-actions">
                    <button
                      className="secondary calibration-save"
                      aria-label="Save .poni calibration"
                      disabled={!canSaveCalibration}
                      onClick={() =>
                        run("save_calibration", {}, "Saving PONI calibration…")
                      }
                    >
                      <Save size={15} />
                      Save .poni
                    </button>
                    <div className="calibration-secondary-actions">
                      <button
                        className="quiet"
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
                        className="quiet"
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
            <div className="plot-status-line">
              <span
                data-testid="mouse-readout"
                className="plot-status-reading"
                data-plot={plotReading?.source}
                data-pixel-x={plotReading?.x}
                data-pixel-row={plotReading?.row}
                title={plotReading?.text}
              >
                {plotReading ? (
                  <ReadingFields reading={plotReading} />
                ) : (
                  (state?.imageName ?? "No image loaded")
                )}
              </span>
            </div>
            {mode === "integration" && (
              <div className="plot-status-line clicked-position">
                <span className="plot-status-kind">Click</span>
                <span
                  data-testid="click-readout"
                  data-plot={clickedReading?.source}
                  className="plot-status-reading"
                  title={
                    clickedReading
                      ? `${sourceLabel(clickedReading.source)} · ${clickPositionReading?.fields?.map((f) => `${f.label} ${f.value}`).join(" · ") ?? clickedReading.text}`
                      : "Click an image, cake or pattern to mark a linked position"
                  }
                >
                  {clickPositionReading ? (
                    <ReadingFields reading={clickPositionReading} />
                  ) : (
                    "—"
                  )}
                </span>
              </div>
            )}
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
