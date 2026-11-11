import { useCakeProfileNavigation } from "./useCakeProfileNavigation";
import { useCakeRadialAxis } from "./useCakeRadialAxis";
import { cakeSourcePixel } from "./cakeRadialAxis";

import { CakeProfilePanel } from "./CakeProfilePanel";
import { useCorrectionPreview } from "./useCorrectionPreview";
import { CorrectionPreviewDetector } from "./CorrectionPreviewDetector";
import {
  DetectorSurface,
  DetectorWindowTools,
  DetectorWindowProvider,
  useDetectorWindow,
} from "./DetectorWindow";
import { IntegrationLeftPane } from "./IntegrationLeftPane";
import { ImageSourceControl } from "./ImageSourceControl";
import { processingProgressText } from "./processingProgress";
import { useBackendReload } from "./useBackendReload";
import {
  requestedDisplayProducts,
  withRequestedProducts,
} from "./displayProducts";
import { navigationTimingEnabled, navigationTrace } from "./navigationTiming";
import { usePlotZoomPreference } from "./usePlotZoomPreference";
import {
  CalibrationResetDialog,
  type CalibrationResetRequest,
} from "./CalibrationResetDialog";
import { Button, Select, Input } from "./ui";
import { useDraftReplacement } from "./useDraftReplacement";
import { useCalibrationFitDraft } from "./useCalibrationFitDraft";
import { IntegrationModeIcon } from "./ModeIcons";
import { WorkspaceModeButtons } from "./WorkspaceModeButtons";
import { HistoryControls } from "./HistoryControls";
import { useGeometryDraft } from "./geometryDraft";
import { useWorkflowNotice } from "./useWorkflowNotice";
import { scientificValue } from "./ScientificNumberInput";
import {
  historyActionLabel,
  scientificHistoryCommand,
  scientificHistoryAction,
  isScientificHistoryCommand,
  isCalibrationHistoryCommand,
  canTraverseScientificHistory,
} from "./historyLabels";
import {
  useIntegrationSettingsDraft,
  useIntegrationSettingsAutoApply,
} from "./IntegrationSettings";
import { GeometryProvenance } from "./GeometryProvenance";
import { StatusMessage } from "./StatusMessage";
import {
  layoutKeys,
  readLayoutFlag,
  saveLayoutValue,
} from "./layoutPreferences";
import { useNativePhaseEditorSync } from "./phaseEditorWindow";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  RotateCcw,
  ArrowUpRight,
  FileImage,
  FolderOpen,
  Layers,
  LoaderCircle,
  Plus,
  Save,
  Settings,
  Sparkles,
} from "lucide-react";
import { connect, updateWindowTitle } from "./bridge";
import { fileOperationFailure, recordAction } from "./errorReporting";
import { SettingsWorkspace } from "./SettingsWorkspace";
import { useProcessingWorkerPreference } from "./ProcessingWorkerSettings";
import { useCustomCommands } from "./customCommands";
import { CustomCommandButtons } from "./CustomCommandButtons";
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
import { restoreMapPosition, type PatternPosition } from "./linkedPosition";
import { radialFields, radialValues } from "./radialReadout";
import { detectorPlotSetup, patternPlotSetup } from "./diffractionPlotSetup";
import {
  createPlotViews,
  detectorViewport,
  patternViewport,
  plotViewContext,
} from "./plotViewport";
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
import { BatchDock } from "./BatchDock";
import { useBatchWindow } from "./batchWindow";
import type { BatchData } from "./batchDomain";
import { MapView } from "./MapView";
import type { MapData } from "./mapDomain";
import { useMapWindow } from "./mapWindow";
import { MaskView } from "./MaskView";
import { MaskPanel } from "./MaskPanel";
import { useMaskTools } from "./maskDomain";
import { RasterView, type RasterExport } from "./RasterView";
import { PatternFigureDialog } from "./PatternFigureDialog";
import type { PatternFigureSource } from "./patternFigure";
import type { PlotFigureExport } from "./plotFigureExport";
import { SpottinessPattern } from "./SpottinessPattern";
import { ORIGINAL_PATTERN_UID } from "./integration";
import { useLiveBackground, DEFAULT_BACKGROUND } from "./useLiveBackground";
import { BACKGROUND_RANGE_COLOR } from "./drawRangeSelection";
import { CalibrationControls } from "./CalibrationControls";
import { CalibrationPanel } from "./CalibrationPanel";
import { CalibrationWorkflowTabs } from "./CalibrationWorkflowTabs";
import { CalibrationRingControls } from "./CalibrationRingControls";
import { ImageIntensity } from "./ImageIntensity";
import { useRasterLevels } from "./useRasterLevels";
import {
  readImageAutoLevels,
  useImageDisplayPreferences,
} from "./useImageDisplayPreferences";
import { prepareDetectorImage } from "./prepareDetectorImage";
import { colorMaps } from "./colorMaps";
import { useConfigurationImageDisplays } from "./useConfigurationImageDisplays";
import { IntegrationView } from "./IntegrationView";
import {
  IntegrationImageControls,
  IntegrationPatternActions,
  IntegrationPatternTools,
  useShiftedCake,
} from "./IntegrationPlotControls";
import { ConfigurationControls } from "./ConfigurationControls";
import { IntegrationWorkspace } from "./IntegrationWorkspace";
import {
  CalibrationExtras,
  GeometryEditor,
  ManualGeometryDialog,
} from "./CalibrationExtras";
import type { RingOverlay } from "./types";
import type { ZoomMode } from "./usePlotNavigation";
import { LoadCalibrationButton } from "./LoadCalibrationButton";

function clickContext(state: State | null) {
  return JSON.stringify([
    state?.imagePath,
    state?.selectedImageSource,
    state?.configurationContext ?? state?.configurationIndex,
    state?.projectName,
    state?.integration.frame,
    state?.integration.patternName,
    state?.calibration.transformations,
    state?.geometry,
    state?.shape,
  ]);
}

export default function App() {
  const beforePreviewCommand = useRef<(command: string) => void>(() => {});
  const [plotViews] = useState(createPlotViews);
  const cakeWindowViewport =
    useRef<import("./plotViewport").ViewportMemory["current"]>(null);
  const detectorExport = useRef<RasterExport>(null);
  const cakeExport = useRef<RasterExport>(null);
  const patternExport = useRef<PlotFigureExport>(null);
  const [figureEditor, setFigureEditor] = useState<{
    source: PatternFigureSource;
  } | null>(null);
  const [overlayReveal, setOverlayReveal] = useState(0);
  const [integrationDisplay, setIntegrationDisplay] = useState("image");
  const [showCakeProfile, setShowCakeProfile] = useState(false);
  const [cakeProfileBins, setCakeProfileBins] = useState(1);
  const [integrationControlsCollapsed, setIntegrationControlsCollapsed] =
    useState(false);
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
  const [showConfigurationControls, setShowConfigurationControls] = useState(
    () => readLayoutFlag(layoutKeys.configurationControls),
  );
  useEffect(() => {
    saveLayoutValue(
      layoutKeys.configurationControls,
      showConfigurationControls,
    );
  }, [showConfigurationControls]);
  const [showRings, setShowRings] = useState(true),
    [showNumbers, setShowNumbers] = useState(true);
  const [linked, setLinked] = useState<Response["linked"]>();
  const currentLinked = useRef<Response["linked"]>(undefined);
  const retainedClickContext = useRef<string | undefined>(undefined);
  const [clickedReading, setClickedReading] = useState<SourcedReading | null>(
    null,
  );
  const [localImageClick, setLocalImageClick] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [localPatternClick, setLocalPatternClick] = useState<PatternPosition>();
  const [patternResolution, setPatternResolution] = useState(0.01);
  const [cakePixelResolution, setCakePixelResolution] = useState({
    x: 1,
    y: 1,
  });
  const [progress, setProgress] = useState<Response["progress"]>();
  const progressGeneration = useRef(0);
  const [quietBackgroundProcessing, setQuietBackgroundProcessing] =
    useState(false);
  const [patternZoom, setPatternZoom] = usePlotZoomPreference("pattern");
  const [cakeZoom, setCakeZoom] = usePlotZoomPreference("cake");
  const [setupDirty, setSetupDirty] = useState(false);
  const [setupValid, setSetupValid] = useState(true);
  const [mode, setMode] = useState<
    "calibration" | "integration" | "mask" | "map"
  >(() =>
    readLayoutFlag(layoutKeys.batchOpen) ? "integration" : "calibration",
  );
  useEffect(() => {
    recordAction("Switch mode", { mode }).status = "completed";
  }, [mode]);
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
  const [imageFileStep, setImageFileStep] = useState(1);
  const [settingsSection, setSettingsSection] = useState(0);
  const [customActionsOpen, setCustomActionsOpen] = useState(false);
  const closeSettings = useCallback(() => {
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
    setSettingsOpen(false);
    document.querySelector<HTMLButtonElement>(".navigation-settings")?.focus();
  }, []);
  const toggleSettings = useCallback(() => {
    clearPlot();
    if (settingsOpen) closeSettings();
    else {
      if (document.activeElement instanceof HTMLElement)
        document.activeElement.blur();
      setSettingsOpen(true);
    }
  }, [settingsOpen, closeSettings, clearPlot]);
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (
        !(event.ctrlKey || event.metaKey) ||
        event.altKey ||
        event.shiftKey ||
        (event.key !== "," && event.code !== "Comma") ||
        event.defaultPrevented ||
        (event.target instanceof Element &&
          event.target.closest('dialog, [role="dialog"]'))
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      if (!event.repeat) toggleSettings();
    };
    // This app shortcut also works from fields and focused plots.
    window.addEventListener("keydown", keyboard, true);
    return () => window.removeEventListener("keydown", keyboard, true);
  }, [toggleSettings]);
  const [maskSelection, setMaskSelection] = useState<{
    text: string;
    cancel: () => void;
  } | null>(null);
  const [mapPatternZoom, setMapPatternZoom] =
    usePlotZoomPreference("map-pattern");
  const [batch, setBatch] = useState<BatchData | null>(null);
  const [batchDockVisible, setBatchDockVisible] = useState(
    () =>
      readLayoutFlag(layoutKeys.batchOpen) &&
      readLayoutFlag(layoutKeys.batchDocked),
  );
  const [batchOpenRequest, setBatchOpenRequest] = useState(0);
  const [batchWarning, setBatchWarning] = useState<string | null>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [mapWarning, setMapWarning] = useState<string | null>(null);
  const requestMap = async (
    command: string,
    args: Record<string, unknown> = {},
  ) => {
    // Batch snapshots/levels are read-only and the worker serializes them.
    // A quiet image-level update must not drop the companion's refresh.
    if (
      !bridge.current ||
      (inFlight.current &&
        command !== "batch_snapshot" &&
        command !== "batch_levels")
    )
      return;
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
  const quietInFlight = useRef(false);
  const pendingMaskDraws = useRef(0);
  const pendingBackgroundUpdates = useRef(0);
  const pendingCorrectionEdits = useRef(0);
  const pendingOverlayEdits = useRef(0);
  const pendingFrameSelections = useRef(0);
  const pendingMapRegions = useRef(0);
  const currentState = useRef<State | null>(null);
  const [state, setState] = useState<State | null>(null);
  const { cake: requestedCake, rings: requestedRings } =
    requestedDisplayProducts({
      mode,
      display: integrationDisplay,
      profile: showCakeProfile && integrationDisplay === "cake",
      calibrationStep,
      concealed: settingsOpen,
      combinedCake: !!state?.combination?.cakes,
      showRings,
    });
  const requestedProductsRef = useRef({
    cake: requestedCake,
    rings: requestedRings,
  });
  requestedProductsRef.current = { cake: requestedCake, rings: requestedRings };
  const supportsRequestedProducts = useRef(false);
  const requestingCake = useRef(false);
  const requestedRingContext = useRef<string | null>(null);
  const integrationDraft = useIntegrationSettingsDraft(state);
  const resetIntegrationDraft = integrationDraft.sync;
  const fitEditor = useCalibrationFitDraft(state?.calibration);
  const fitDraft = fitEditor.draft;
  const resetFitDraft = fitEditor.sync;
  const geometryDraft = useGeometryDraft(state?.calibration);
  const resetGeometryDraft = geometryDraft.sync;
  const geometryDirty = geometryDraft.dirty;
  const activeGeometryDirty = geometryDraft.changed(validationConvention);
  const activeGeometryValid = geometryDraft.valid(validationConvention);
  const draftReplacement = useDraftReplacement({
    geometry: geometryDirty,
    fit: fitEditor.dirty,
    integration: integrationDraft.dirty,
  });
  const pendingOptionDrafts = useRef(false);
  pendingOptionDrafts.current =
    geometryDirty || fitEditor.dirty || integrationDraft.dirty;
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

  const cakeRadialAxis = useCakeRadialAxis(
    displayedCake ?? cake,
    state?.unit,
    state?.geometry.wavelength,
  );
  const [busy, setBusy] = useState("Connecting to Dioptas…"),
    [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useWorkflowNotice();
  const canPick = !!state?.hasImage && !setupDirty && !geometryDirty;
  const tool: Tool =
    mode === "calibration" && pickingEnabled && canPick ? "pick" : "pan";
  const [logImage, setLogImage] = useState(false),
    [logPattern, setLogPattern] = useState(false);
  const [palette, setPalette] = useState<Palette>("grey");
  const [limits, setLimits] = useState<[number, number]>([0, 100]);
  const [maskAutoActive, setMaskAutoActive] = useState(true);
  const [maskLimits, setMaskLimits] = useRasterLevels(image, maskAutoActive);
  const imageSource = useRef<Raster | null>(null);
  const rawImageSource = useRef<Raster | null>(null);
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
  const {
    detectorAutoActive,
    cakeAutoActive,
    configurationDisplays,
    configurationCakeDisplays,
    beginConfigurationDisplay,
  } = useConfigurationImageDisplays({
    limits,
    logImage,
    palette,
    detectorPreferences,
    multiDetectorPreferences,
    cakeLimits,
    cakeLog,
    cakePalette,
    cakePreferences,
    setLimits,
    setLogImage,
    setPalette,
    setDetectorPreferences,
    setMultiDetectorPreferences,
    setCakeLimits,
    setCakeLog,
    setCakePalette,
    setCakePreferences,
  });
  const multipleImages = mode === "integration" || calibrationStep === 3;
  const detectorDisplay = useRef({ name: "detector", filterGaps: true });
  detectorDisplay.current = {
    name:
      mode === "map"
        ? "map-detector"
        : mode === "mask"
          ? "mask-detector"
          : multipleImages
            ? "multi-detector"
            : "detector",
    filterGaps: true,
  };
  useEffect(() => {
    if (!colorMaps[palette]) setPalette("grey");
    if (!colorMaps[cakePalette]) setCakePalette("grey");
  }, [palette, cakePalette]);
  const [resetKey, setResetKey] = useState(0);
  const [calibrationResetRequest, setCalibrationResetRequest] =
    useState<CalibrationResetRequest>();
  const calibrationResetOpener = useRef<HTMLElement | null>(null);
  const [pixel, setPixel] = useState<NonNullable<Response["pixel"]> | null>(
    null,
  );
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    hoverSequence = useRef(0);
  const hoverLatest = useRef<{ x: number; y: number } | null>(null);
  const hoverLastSent = useRef(0);
  const hoverRequest = useRef(false);
  const canDeferIntegration = useRef(false);
  const apply = useCallback(
    (result: Response, resetImageView = true, retainClick = false) => {
      if (!result.ok)
        throw new Error(
          result.error || "The operation could not be completed.",
        );
      const configurationDisplay = beginConfigurationDisplay(
        result,
        currentState.current,
      );
      if (result.batchWaterfallCreated) setOverlayReveal((n) => n + 1);
      if ("batch" in result) setBatch(result.batch ?? null);
      if (result.batchPhaseLines !== undefined)
        setBatch((b) => (b ? { ...b, phaseLines: result.batchPhaseLines } : b));
      if (result.batchPosition) {
        setLocalPatternClick(result.batchPosition);
        setLocalImageClick(null);
        const fields = radialFields(
          result.batchPosition.x,
          result.batchPosition.unit,
          result.batchWavelength ?? undefined,
        );
        setClickedReading({
          source: "batch",
          fields,
          text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
        });
      }
      if (result.batchSelection !== undefined)
        setBatch((b) =>
          b
            ? {
                ...b,
                selected: result.batchSelection!,
                pattern: result.pattern ?? b.pattern,
                position: result.batchPosition ?? b.position,
              }
            : b,
        );
      if ("batchWarning" in result)
        setBatchWarning(result.batchWarning ?? null);
      if (result.batchOpened) {
        setMode("integration");
        setBatchOpenRequest((v) => v + 1);
      }
      if ("map" in result) setMap(result.map ?? null);
      if ("mapWarning" in result) setMapWarning(result.mapWarning ?? null);
      if (result.state) {
        supportsRequestedProducts.current =
          result.state.supportsRequestedProducts === true;
        if (result.calibrationReset) {
          resetFitDraft(result.state.calibration);
          resetGeometryDraft(result.state.calibration);
        }
        if (result.calibrationReset || result.imageStateReset) {
          setSelectedPicks([]);
          setPhaseGuides([]);
        }
        if (retainClick)
          retainedClickContext.current = clickContext(result.state);
        currentState.current = result.state;
        if (
          typeof result.state.integration.originalPatternVisible === "boolean"
        )
          setShowOriginalPattern(
            result.state.integration.originalPatternVisible,
          );
        if (result.state.integration.originalPatternColor)
          setOriginalPatternColor(
            result.state.integration.originalPatternColor,
          );
        // An existing live preview may still have the earlier Python worker
        // loaded until the user restarts it.
        canDeferIntegration.current = "integrationDirty" in result.state;
        if (result.patternOnly && !result.phaseOnly)
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
      if (result.clearImage) {
        setImage(null);
        setRawImage(null);
        setMask(null);
        setPixel(null);
        imageSource.current = null;
        rawImageSource.current = null;
        ++hoverSequence.current;
        hoverLatest.current = null;
      }
      if (result.rawImage) {
        rawImageSource.current = result.rawImage;
        setRawImage(result.rawImage);
      }
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
        if (
          sourceChanged &&
          (detectorAutoActive.current ||
            configurationDisplay.configurationChanged)
        ) {
          setLimits(
            activeMode.current === "integration" &&
              !correctedImageRef.current &&
              result.rawImage
              ? result.rawImage.limits
              : result.image.limits,
          );
        }
        if (resetImageView) setResetKey((k) => k + 1);
      }
      if (result.levels)
        (result.display === "cake" ? setCakeLimits : setLimits)(result.levels);
      if (result.nextRing !== undefined) setRing(result.nextRing);
      if ("linked" in result) {
        currentLinked.current = result.linked;
        setLinked(result.linked);
      }
      if (result.mask)
        setMask((previous) =>
          previous?.data === result.mask!.data &&
          previous.width === result.mask!.width &&
          previous.height === result.mask!.height
            ? previous
            : result.mask!,
        );
      if (result.rings) {
        if (!result.rings.length && !requestedProductsRef.current.rings)
          requestedRingContext.current = null;
        setRings(result.rings);
      }
      if ("pattern" in result) setPattern(result.pattern ?? null);
      if ("cake" in result) {
        setCake(result.cake ?? null);
        if (
          result.cake &&
          (cakeAutoActive.current || configurationDisplay.cakeDisplayChanged) &&
          (result.cake.data !== cakeSource.current?.data ||
            result.cake.width !== cakeSource.current?.width ||
            result.cake.height !== cakeSource.current?.height)
        )
          setCakeLimits(result.cake.limits);
        cakeSource.current = result.cake ?? null;
      }
      configurationDisplay.restore();
      if (configurationDisplay.configurationChanged) {
        setSelectedPicks([]);
        setPhaseGuides([]);
      }
      if (result.configurationNavigation) {
        const { advanced, skipped } = result.configurationNavigation;
        setNotice(
          advanced.length
            ? `Advanced ${advanced.length} configuration${advanced.length === 1 ? "" : "s"}${skipped.length ? ` · ${skipped.length} without a matching file` : ""}`
            : "No matching files for configuration browsing",
        );
      }
      if (result.savedPath || result.savedPaths?.length) {
        setNotice(
          result.savedPaths?.length
            ? `Saved ${result.savedPaths.length} batch files`
            : `Saved ${result.savedPath!.split(/[\\/]/).at(-1)}`,
        );
      }
    },
    [],
  );
  const run = useCallback(
    async (
      command: string,
      args: Record<string, unknown> = {},
      message = "Processing…",
      onSuccess?: (result: Response) => void,
      shouldRun?: () => boolean,
      queueIfBusy = false,
      replaceDrafts = false,
    ): Promise<void> => {
      if (
        !replaceDrafts &&
        draftReplacement.request(command, () => {
          void run(
            command,
            args,
            message,
            onSuccess,
            shouldRun,
            queueIfBusy,
            true,
          );
        })
      )
        return;
      const historyLabel = scientificHistoryAction(
        currentState.current,
        activeMode.current,
        command.startsWith("redo"),
      );
      const overlayEditing =
        command === "batch_waterfall" ||
        (command === "integration_overlay" && args.operation !== "load") ||
        (isScientificHistoryCommand(command) &&
          historyLabel === "integration_overlay");
      const liveBackground =
        command === "integration_background" && message === "";
      const liveMapRegion = command === "map_roi" && message === "";
      const liveCorrection =
        message === "" &&
        [
          "integration_correction",
          "integration_image_background",
          "integration_flat_field",
          "integration_transfer",
        ].includes(command);
      const frameSelection =
        command === "map_select" ||
        command === "batch_select" ||
        command === "next_image" ||
        (command === "integration_navigation" &&
          (args.frame !== undefined || args.direction !== undefined));
      const livePhaseConditions =
        command === "integration_phase" &&
        args.operation === "update" &&
        (typeof args.pressure === "number" ||
          typeof args.temperature === "number");
      if (
        !bridge.current ||
        (command === "integration_autoprocess_poll" &&
          (inFlight.current || commandTail.current)) ||
        (inFlight.current &&
          !quietInFlight.current &&
          !queueIfBusy &&
          !autoProcessInFlight.current &&
          !pendingMaskDraws.current &&
          !pendingBackgroundUpdates.current &&
          !pendingCorrectionEdits.current &&
          !pendingOverlayEdits.current &&
          !pendingFrameSelections.current &&
          !pendingMapRegions.current &&
          !liveMapRegion &&
          !liveCorrection &&
          !liveBackground &&
          !livePhaseConditions &&
          command !== "cake_profile" &&
          command !== "integration_phase_state" &&
          command !== "integration_phase_guides" &&
          command !== "image_levels" &&
          command !== "image_batch_mode" &&
          !frameSelection)
      )
        return;
      beforePreviewCommand.current(command);
      const batchAction =
        command.startsWith("batch_") &&
        !["batch_levels", "batch_snapshot"].includes(command);
      const commandMode = batchAction ? "integration" : activeMode.current;
      if (batchAction) {
        setMode("integration");
        setSettingsOpen(false);
      }
      const maskDrawing =
        commandMode === "mask" &&
        (command === "mask_stroke" ||
          (command === "mask_edit" &&
            ["rectangle", "circle", "polygon", "arc"].includes(
              String(args.operation),
            )));
      // Keep quiet edits and frame selections in order without disabling every
      // control. Further clicks must not be dropped while an image loads.
      const previous = commandTail.current;
      let release!: () => void;
      const completion = new Promise<void>((resolve) => (release = resolve));
      commandTail.current = completion;
      if (maskDrawing) pendingMaskDraws.current++;
      if (overlayEditing) pendingOverlayEdits.current++;
      if (frameSelection) pendingFrameSelections.current++;
      if (liveMapRegion) pendingMapRegions.current++;
      if (liveBackground) pendingBackgroundUpdates.current++;
      if (liveCorrection) pendingCorrectionEdits.current++;
      if (previous) await previous;
      if (shouldRun && !shouldRun()) {
        if (liveBackground) pendingBackgroundUpdates.current--;
        if (liveCorrection) pendingCorrectionEdits.current--;
        if (overlayEditing) pendingOverlayEdits.current--;
        if (frameSelection) pendingFrameSelections.current--;
        if (liveMapRegion) pendingMapRegions.current--;
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
        liveMapRegion ||
        liveCorrection ||
        livePhaseConditions ||
        command === "integration_phase_state" ||
        command === "integration_phase_guides" ||
        command === "integration_autoprocess_poll" ||
        frameSelection ||
        command === "cake_profile" ||
        command === "validation_position" ||
        command === "image_levels" ||
        command === "image_batch_mode";
      // Disabling the source selector while opening can blur it before the
      // size-confirmation response arrives (especially in WebKit).
      if (
        command === "select_image_source" &&
        document.activeElement instanceof HTMLElement
      )
        calibrationResetOpener.current = document.activeElement;
      const quietBackgroundJob = quiet && (liveBackground || overlayEditing);
      if (quietBackgroundJob) {
        ++progressGeneration.current;
        setProgress(undefined);
        setQuietBackgroundProcessing(true);
      }
      if (!quiet) {
        ++progressGeneration.current;
        setProgress(undefined);
        setBusy(message);
        setNotice(null);
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
      quietInFlight.current = quiet;
      navigationTrace("command-start", { action: command });
      try {
        const selectedPosition = currentLinked.current;
        let result = await bridge.current(
          command,
          commandMode === "mask" &&
            canDeferIntegration.current &&
            ![
              "configuration",
              "configuration_select",
              "combination_settings",
              "configuration_navigation",
              "save_combined_pattern",
              "processing_workers",
            ].includes(command)
            ? { ...args, defer_integration: true }
            : command === "map_select"
              ? { ...args, integration_view: commandMode === "integration" }
              : args,
        );
        navigationTrace("command-response", {
          action: command,
          bufferId: result.image?.bufferId,
        });
        if (result.imageChange || result.calibrationChange) {
          if (
            document.activeElement instanceof HTMLElement &&
            document.activeElement !== document.body
          )
            calibrationResetOpener.current = document.activeElement;
          setCalibrationResetRequest(
            result.imageChange ?? result.calibrationChange,
          );
          return;
        }
        // Stored-only map projects can be inspected even when their raw files are unavailable.
        if (
          command === "map_select" &&
          args.reintegrate === true &&
          !result.ok &&
          result.error ===
            "Reintegration needs the original image and a loaded calibration."
        ) {
          result = await bridge.current(command, {
            ...args,
            integration_view: commandMode === "integration",
            reintegrate: false,
          });
        }
        const retainMapClick =
          result.ok &&
          ((!!result.map &&
            (command === "map_select" || command === "map_poll")) ||
            result.batchSelection !== undefined);
        if (retainMapClick)
          result = await restoreMapPosition(
            bridge.current,
            result,
            selectedPosition,
          );
        const display = detectorDisplay.current;
        const raw = commandMode === "integration" && !correctedImageRef.current;
        if (detectorAutoActive.current)
          result = await prepareDetectorImage(
            bridge.current,
            result,
            raw ? rawImageSource.current : imageSource.current,
            readImageAutoLevels(display.name, display.filterGaps),
            raw,
          );
        navigationTrace("command-prepared", {
          action: command,
          bufferId: result.image?.bufferId,
        });
        // Qt's unit buttons relabel the existing cake. Retain the same pixel
        // viewport while its axis changes (the pattern owns its unit adapter).
        const unitOnly =
          ["settings", "integration_settings"].includes(command) &&
          Object.keys(args).length === 1 &&
          "unit" in args;
        apply(result, !unitOnly, retainMapClick);
        navigationTrace("command-applied", {
          action: command,
          bufferId: result.image?.bufferId,
        });
        if (command === "next_image" && result.ok)
          setNotice(
            result.imageUnavailable
              ? Number(args.direction ?? 1) < 0
                ? "No previous image available"
                : "No new image available"
              : null,
          );
        if (!result.cancelled && result.state) {
          if (["open_project", "example"].includes(command))
            resetIntegrationDraft(result.state);
          if (
            ["open_project", "example", "open_calibration"].includes(command)
          ) {
            resetGeometryDraft(result.state.calibration);
            resetFitDraft(result.state.calibration);
          }
        }
        if (!result.cancelled && result.state) {
          if (command === "manual_geometry")
            resetGeometryDraft(result.state.calibration);
          if (command === "calibrate") resetFitDraft(result.state.calibration);
        }
        if (
          command === "save_project" &&
          result.savedPath &&
          pendingOptionDrafts.current
        ) {
          setNotice(
            `Saved ${result.savedPath.split(/[\\/]/).at(-1)} · unapplied option drafts remain in this session`,
          );
        }
        if (result.correctionNotice) setNotice(result.correctionNotice);
        if (command === "pick_peak" && result.noPeakFound)
          setNotice("No peaks found in this area");
        if (command === "open_calibration" && !result.cancelled) {
          setNotice(
            `Loaded calibration: ${result.state?.calibrationName ?? "PONI"}${result.state?.hasImage ? "" : " · Load a matching detector image"}`,
          );
        }
        if (isScientificHistoryCommand(command)) {
          setNotice(
            `${command.startsWith("undo") ? "Undid" : "Redid"} ${historyActionLabel(historyLabel)}`,
          );
        }
        if (command === "integration_autoprocess_poll" && result.state)
          setError(result.state.integration.autoProcessError || null);
        if (
          (command === "load_peaks" && !result.cancelled) ||
          isCalibrationHistoryCommand(command) ||
          [
            "clear_peaks",
            "remove_pick",
            "remove_picks",
            "open_image",
            "select_image_source",
            "example",
            "image_transform",
            "open_project",
          ].includes(command)
        )
          setSelectedPicks((previous) => (previous.length ? [] : previous));
        if (
          !result.cancelled &&
          ["calibrate", "manual_geometry", "open_calibration"].includes(command)
        ) {
          setCalibrationStep(
            command === "open_calibration" && !result.state?.hasImage ? 0 : 3,
          );
        }
        onSuccess?.(result);
      } catch (e) {
        const details = e instanceof Error ? e.message : String(e);
        const failure = fileOperationFailure(command, details, args);
        setError(failure?.title ?? details);
        try {
          // Recovery refreshes the current image too. A failed peak pick must
          // keep the user's zoom so they can retry at the same location.
          apply(await bridge.current("state"), false);
        } catch {
          /* Keep the original error visible. */
        }
      } finally {
        if (quietBackgroundJob) {
          ++progressGeneration.current;
          setProgress(undefined);
          setQuietBackgroundProcessing(false);
        }
        if (!quiet) {
          ++progressGeneration.current;
          setProgress(undefined);
          setBusy("");
        }
        inFlight.current = false;
        quietInFlight.current = false;
        autoProcessInFlight.current = false;
        if (maskDrawing) pendingMaskDraws.current--;
        if (overlayEditing) pendingOverlayEdits.current--;
        if (frameSelection) pendingFrameSelections.current--;
        if (liveMapRegion) pendingMapRegions.current--;
        if (liveBackground) pendingBackgroundUpdates.current--;
        if (liveCorrection) pendingCorrectionEdits.current--;
        if (commandTail.current === completion) commandTail.current = null;
        release();
      }
    },
    [
      apply,
      resetIntegrationDraft,
      resetGeometryDraft,
      resetFitDraft,
      draftReplacement.request,
    ],
  );
  const correctionPreview = useCorrectionPreview(
    state,
    mode === "integration" && !settingsOpen,
    run,
    bridge,
  );
  beforePreviewCommand.current = correctionPreview.beforeCommand;
  useProcessingWorkerPreference(state, !busy, run);
  const changeConfigurationControls = useCallback(
    (show: boolean) => {
      if (
        !currentState.current ||
        busy ||
        inFlight.current ||
        integrationDraft.dirty
      )
        return;
      const combination = currentState.current.combination;
      if (!show && (combination?.patterns || combination?.cakes)) {
        void run(
          "combination_settings",
          { patterns: false, cakes: false },
          "Disabling configurations…",
          () => setShowConfigurationControls(false),
        );
      } else setShowConfigurationControls(show);
    },
    [busy, integrationDraft.dirty, run],
  );
  useEffect(() => {
    if (state?.combination?.patterns || state?.combination?.cakes)
      setShowConfigurationControls(true);
  }, [state?.combination?.patterns, state?.combination?.cakes]);
  useEffect(() => {
    if (!navigationTimingEnabled) return;
    const probe = {
      run: (action: string, payload: Record<string, unknown> = {}) =>
        run(
          action,
          payload,
          "Preparing navigation benchmark…",
          undefined,
          undefined,
          false,
          true,
        ),
      state: () => currentState.current,
      image: () => imageSource.current,
    };
    window.__dioptasNavigationProbe = probe;
    return () => {
      if (window.__dioptasNavigationProbe === probe)
        delete window.__dioptasNavigationProbe;
    };
  }, [run]);
  useLayoutEffect(() => {
    navigationTrace("react-commit", {
      revision: state?.revision,
      bufferId: image?.bufferId,
    });
  }, [state?.revision, image?.bufferId]);
  useBackendReload((message, restored) => {
    setNotice(message);
    if (restored)
      void bridge
        .current?.("state")
        .then((result) => apply(result, false, true))
        .catch((error) => setError(String(error)));
  });
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
      mode !== "mask" &&
      (mode !== "map" || !map)
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
    map,
    run,
  ]);
  useEffect(() => {
    const ringContext = JSON.stringify([
      clickContext(state),
      state?.calibration.calibrant,
    ]);
    const missingRings =
      requestedRings &&
      !rings.length &&
      requestedRingContext.current !== ringContext;
    if (
      supportsRequestedProducts.current &&
      ((requestedCake && !cake) || missingRings) &&
      state?.hasImage &&
      state.calibrated &&
      !state.integrationDirty &&
      !busy &&
      !error &&
      !requestingCake.current
    ) {
      requestingCake.current = true;
      if (requestedRings) requestedRingContext.current = ringContext;
      void run(
        "display_products",
        { cake: requestedCake, rings: requestedRings },
        requestedCake ? "Preparing cake…" : "Preparing calibration rings…",
      ).finally(() => {
        requestingCake.current = false;
      });
    }
  }, [
    requestedCake,
    requestedRings,
    rings.length,
    state,
    cake,
    state?.hasImage,
    state?.calibrated,
    state?.integrationDirty,
    busy,
    error,
    run,
  ]);
  useEffect(() => {
    let mounted = true;
    connect()
      .then(async (invoke) => {
        if (!mounted) return;
        const displayInvoke = withRequestedProducts(
          invoke,
          () => requestedProductsRef.current,
        );
        bridge.current = (action, payload) =>
          supportsRequestedProducts.current
            ? displayInvoke(action, payload)
            : invoke(action, payload);
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
    };
  }, [run]);
  useEffect(() => {
    if (!busy && !quietBackgroundProcessing) {
      setProgress(undefined);
      return;
    }
    let active = true;
    let polling = false;
    const timer = setInterval(() => {
      if (polling) return;
      polling = true;
      // Consecutive quiet edits can share a render; capture the active job
      // for each poll so a completed edit cannot suppress its successor.
      const generation = progressGeneration.current;
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
  }, [busy, quietBackgroundProcessing]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      const target =
        event.target instanceof Element ? event.target : document.body;
      if (settingsOpen) return;
      if (
        target.closest(
          '[role="dialog"], dialog, [role="listbox"], [role="menu"]',
        ) ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      )
        return;
      // Native controls own their unmodified activation keys.
      if (target.closest('[contenteditable="true"]')) return;
      if (
        !(event.metaKey || event.ctrlKey) &&
        ["Enter", " "].includes(event.key) &&
        target.closest('button, a, summary, [role="tab"]')
      )
        return;
      if (event.defaultPrevented) return;
      const key = event.key.toLowerCase(),
        mod = event.metaKey || event.ctrlKey;
      if (!mod && !event.altKey && event.shiftKey && key === "c") {
        event.preventDefault();
        if (!event.repeat)
          changeConfigurationControls(!showConfigurationControls);
      } else if (
        !mod &&
        !event.altKey &&
        !event.shiftKey &&
        ["PageUp", "PageDown"].includes(event.key) &&
        (mode === "integration" || mode === "calibration") &&
        currentState.current?.hasImage
      ) {
        event.preventDefault();
        void run(
          "next_image",
          {
            direction: event.key === "PageUp" ? -1 : 1,
            step: mode === "integration" ? imageFileStep : 1,
            files_only: true,
          },
          "Opening image…",
        );
      } else if (mod && key === "o") {
        event.preventDefault();
        void run(
          "open_image",
          mode === "integration"
            ? {
                multiple: true,
                batch_mode:
                  currentState.current?.integration.imageBatchMode ??
                  "integrate",
              }
            : {},
          "Opening image…",
        );
      } else if (mod && key === "s") {
        event.preventDefault();
        void run(
          mode === "mask" ? "mask_file" : "save_project",
          mode === "mask" ? { save: true } : {},
          "Saving…",
        );
      } else if (mod && key === "z") {
        event.preventDefault();
        if (
          !canTraverseScientificHistory(
            currentState.current,
            event.shiftKey,
            mode,
          )
        )
          return;
        void run(
          scientificHistoryCommand(
            scientificHistoryAction(currentState.current, mode, event.shiftKey),
            event.shiftKey,
          ),
          {},
          "Restoring previous state…",
        );
      } else if (mod && key === "y") {
        event.preventDefault();
        if (!canTraverseScientificHistory(currentState.current, true, mode))
          return;
        void run(
          scientificHistoryCommand(
            scientificHistoryAction(currentState.current, mode, true),
            true,
          ),
          {},
          "Restoring previous state…",
        );
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
        if (key === "f") {
          plotViews.detector.current = null;
          setResetKey((k) => k + 1);
        }
        return;
      } else if (mod) return;
      else if (key === "b" || key === "e") {
        setMode("mask");
        maskTools.setShape("point");
        maskTools.setErase(key === "e");
      } else if (key === "p" && canPick) {
        setMode("calibration");
        setPickingEnabled(true);
      } else if (key === "f") {
        plotViews.detector.current = null;
        setResetKey((k) => k + 1);
      } else if (
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
    changeConfigurationControls,
    showConfigurationControls,
    imageFileStep,
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
  useLayoutEffect(() => {
    onHover(null);
    clearPlot();
  }, [correctionPreview.map?.kind, onHover, clearPlot]);
  const positionContext = clickContext(state);
  useEffect(() => {
    if (retainedClickContext.current === positionContext) return;
    setClickedReading(null);
    setLocalImageClick(null);
    setLocalPatternClick(undefined);
  }, [positionContext]);
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
    const source = radialValues(
      linked.twoTheta,
      "2th_deg",
      state?.geometry.wavelength,
    )[view.unit];
    if (source == null || !Number.isFinite(source)) return null;
    return {
      x: cakeSourcePixel(view, source),
      y: ((azi - low) / (high - low)) * view.fullHeight,
    };
  }, [linked, displayedCake, cake, state?.geometry.wavelength]);
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
                      mode === "integration" && cake
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
  useIntegrationSettingsAutoApply(
    integrationDraft,
    ready,
    (command, args, message) =>
      run(command, args, message, undefined, undefined, true),
  );
  const customInvoke = useCallback<Invoke>((command, args) => {
    if (!bridge.current)
      return Promise.reject(new Error("The desktop bridge is unavailable."));
    return bridge.current(command, args);
  }, []);
  const customCommands = useCustomCommands(customInvoke, state);
  const customHistoryActive = settingsOpen && customActionsOpen;
  useLayoutEffect(() => {
    if (!customHistoryActive) return;
    const keyboard = (event: KeyboardEvent) => {
      const target =
        event.target instanceof Element ? event.target : document.body;
      if (
        event.defaultPrevented ||
        target.closest(
          'input, textarea, select, [contenteditable="true"], [role="dialog"], dialog',
        )
      )
        return;
      if (!(event.metaKey || event.ctrlKey)) return;
      const key = event.key.toLowerCase();
      if (key !== "z" && key !== "y") return;
      event.preventDefault();
      if (key === "y" || event.shiftKey) {
        if (customCommands.canRedo) void customCommands.redo();
      } else if (customCommands.canUndo) void customCommands.undo();
    };
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [
    customHistoryActive,
    customCommands.canUndo,
    customCommands.canRedo,
    customCommands.undo,
    customCommands.redo,
  ]);
  const mapWindow = useMapWindow({
    run: (command, args, message, done) =>
      run(command, args, message, done, undefined, true),
    // Like native child reads, browser popup reads use the processing worker's
    // serialization rather than being dropped during a quiet main-window edit.
    request: async (command, args) => bridge.current?.(command, args),
    status: {
      ready,
      calibrated: !!state?.calibrated,
      largeText,
      error,
      revision: state?.revision,
      progress: progress
        ? {
            running: progress.running,
            current: progress.current,
            total: progress.total,
            label: progress.label,
            fps: progress.fps,
            elapsedSeconds: progress.elapsedSeconds,
          }
        : undefined,
    },
    onOpen: () => {
      setSettingsOpen(false);
      setMode("integration");
    },
    onDock: () => {
      setSettingsOpen(false);
      setMode("map");
    },
    onError: setError,
  });
  const detectorWindow = useDetectorWindow(
    {
      largeText,
      reading:
        plotReading &&
        ["detector", "cake", "profile"].includes(plotReading.source)
          ? plotReading
          : null,
      clicked: correctionPreview.map ? null : clickPositionReading,
      message: progress?.running
        ? processingProgressText(progress)
        : busy || "",
      error,
    },
    JSON.stringify([
      mode,
      state?.configurationContext ?? state?.configurationIndex,
      state?.revision,
      state?.selectedImageSource,
      state?.shape,
      state?.calibration.transformations,
    ]),
    setError,
    JSON.stringify([
      mode,
      state?.configurationContext ?? state?.configurationIndex,
    ]),
  );
  const mainPlotReading =
    detectorWindow.detached &&
    plotReading &&
    ["detector", "cake", "profile"].includes(plotReading.source)
      ? null
      : plotReading;
  const inspectDetector = (point: {
    x: number;
    y: number;
    value: number | null;
  }) => {
    if (!ready || (mode !== "integration" && mode !== "map") || !image) return;
    setLocalImageClick(point);
    setClickedReading({
      source: "detector",
      text: "Image click",
      x: Math.floor(point.x),
      row: image.fullHeight - 1 - Math.floor(point.y),
      value: point.value,
    });
    if (state?.calibrated && state.hasImage)
      void run(
        "validation_position",
        { source: "image", x: point.x, y: point.y },
        "",
        undefined,
        undefined,
        true,
      );
  };
  const inspectPattern = (point: PatternHover) => {
    if (!ready || (mode !== "integration" && mode !== "map")) return;
    setLocalPatternClick({ x: point.x, unit: point.unit });
    setLocalImageClick(null);
    if (point.xResolution != null) setPatternResolution(point.xResolution);
    setClickedReading({
      source: "pattern",
      ...patternReading(point, state?.geometry.wavelength),
    });
    if (state?.calibrated && state.hasImage) {
      const x = radialValues(point.x, point.unit, state.geometry.wavelength)[
        state.unit
      ];
      if (x != null && Number.isFinite(x))
        void run(
          "validation_position",
          { source: "pattern", x },
          "",
          undefined,
          undefined,
          true,
        );
    }
  };
  const backgroundContext = (s: State | null) =>
    JSON.stringify([
      s?.unit,
      s?.configurationIndex,
      s?.imagePath,
      s?.selectedImageSource,
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
  const patternPlot = displayedPattern
    ? patternPlotSetup({
        pattern: displayedPattern,
        viewport: patternViewport(
          plotViews.pattern,
          plotViewContext(state),
          displayedPattern.unit,
          logPattern
            ? "log"
            : mode === "integration" && sqrtPattern
              ? "sqrt"
              : "linear",
          state?.geometry.wavelength,
        ),
        patternColor: mode === "integration" ? originalPatternColor : "#ffffff",
        showPattern: mode !== "integration" || originalPatternVisible,
        patternName: state?.integration.patternName,
        curves: displayedCurves,
        referenceLines:
          mode === "integration" ? pattern?.phaseLines : undefined,
        legendCurves: pattern?.curves ?? [],
        showLegend: mode === "integration",
        linked: mode === "integration" ? linked : undefined,
        localPatternClick:
          mode === "integration" ? localPatternClick : undefined,
        wavelength: state?.geometry.wavelength,
        onInspect: mode === "integration" && ready ? inspectPattern : undefined,
      })
    : null;
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
      const revision = state.revision;
      void run(
        "integration_phase_guides",
        {},
        "",
        undefined,
        () => phaseGuideRevision.current === revision,
      );
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
  const canSaveCalibration =
    ready &&
    !!state?.calibrated &&
    !state.calibration.fitDirty &&
    !setupDirty &&
    !geometryDirty;
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
      ? processingProgressText(
          progress,
          mode === "integration" ? "Processing" : "Refining ring",
        )
      : busy ||
        notice ||
        maskSelection?.text ||
        (mode === "integration"
          ? batchWarning
          : mode === "map"
            ? mapWarning
            : null) ||
        ((geometryDirty || fitEditor.dirty) && mode !== "calibration"
          ? "Unapplied calibration edits; the current geometry is still in use."
          : null) ||
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
                  : state.calibration.rmsDegrees != null
                    ? "Inspect fitted ring alignment and RMS, then save .poni."
                    : "Inspect ring overlays. This geometry has no fitted peak residual.",
              ][calibrationStep]
          : mode === "map"
            ? map
              ? "Select a map cell to inspect its detector image and pattern."
              : state?.calibrated
                ? "Build a map from detector images or a folder."
                : "Load a calibration to build a map."
            : mode === "mask"
              ? `${shapeHelp[maskTools.shape]} · ${number(state?.maskedPixels ?? 0, 0)} masked`
              : canIntegrate
                ? "Ready"
                : "Load a calibration to integrate this image."));
  const batchWindow = useBatchWindow({
    batch,
    run,
    request: requestMap,
    status: {
      clicked: clickPositionReading,
      position: linked
        ? { x: linked.twoTheta, unit: "2th_deg" }
        : localPatternClick,
      ready,
      calibrated: !!state?.calibrated,
      largeText,
      error,
      revision: state?.revision,
      progress: progress
        ? {
            running: progress.running,
            current: progress.current,
            total: progress.total,
            label: progress.label,
            fps: progress.fps,
            elapsedSeconds: progress.elapsedSeconds,
          }
        : undefined,
    },
    onOpen: () => {
      setMode("integration");
      setBatchDockVisible(false);
      saveLayoutValue(layoutKeys.batchDocked, false);
      saveLayoutValue(layoutKeys.batchOpen, true);
    },
    onDock: () => {
      setMode("integration");
      setBatchDockVisible(true);
      saveLayoutValue(layoutKeys.batchDocked, true);
      saveLayoutValue(layoutKeys.batchOpen, true);
    },
    onClose: () => saveLayoutValue(layoutKeys.batchOpen, false),
    onError: setError,
    cancel: () => bridge.current?.("cancel_refinement"),
  });
  const openBatch = () => {
    clearPlot();
    setSettingsOpen(false);
    setMode("integration");
    const docked = readLayoutFlag(layoutKeys.batchDocked);
    saveLayoutValue(layoutKeys.batchOpen, true);
    if (docked) setBatchDockVisible(true);
    else batchWindow.open();
  };
  const activateBatch = () => {
    if (batchWindow.detached) {
      batchWindow.open();
    } else if (batchDockVisible) {
      clearPlot();
      setBatchDockVisible(false);
      saveLayoutValue(layoutKeys.batchOpen, false);
    } else {
      openBatch();
    }
  };
  const restoredBatchLayout = useRef(false);
  useEffect(() => {
    if (!ready || restoredBatchLayout.current) return;
    restoredBatchLayout.current = true;
    if (readLayoutFlag(layoutKeys.batchOpen)) openBatch();
  }, [ready]);
  const handledBatchOpen = useRef(0);
  useEffect(() => {
    if (handledBatchOpen.current === batchOpenRequest) return;
    handledBatchOpen.current = batchOpenRequest;
    openBatch();
  }, [batchOpenRequest]);
  const configurationControlsVisible =
    showConfigurationControls && !!state?.configurationLabels && !settingsOpen;
  const runImageControl = useCallback<import("./integration").IntegrationRun>(
    (command, args, message, done) =>
      run(command, args, message, done, undefined, true),
    [run],
  );
  const imageControls = (
    <IntegrationImageControls
      onUndock={detectorWindow.open}
      profile={showCakeProfile && integrationDisplay === "cake"}
      onProfile={() => {
        const enabled = showCakeProfile && integrationDisplay === "cake";
        if (!enabled) {
          setIntegrationDisplay("cake");
          correctionPreview.close();
        }
        setShowCakeProfile(!enabled);
      }}
      onSaveImage={async () => {
        const source = integrationDisplay === "cake" ? "cake" : "image";
        const exporter = (source === "cake" ? cakeExport : detectorExport)
          .current;
        if (!exporter && !detectorWindow.detached) return;
        let png: string;
        try {
          png = detectorWindow.detached
            ? await detectorWindow.png()
            : exporter!.png();
        } catch (error) {
          setError(String(error));
          return;
        }
        void runImageControl(
          "integration_save_image",
          {
            source,
            png_data: png,
            suggested_name: `${state?.imageName?.replace(/\.[^.]+$/, "") ?? "image"}${source === "cake" ? "_cake" : ""}.png`,
          },
          "Saving image…",
        );
      }}
      cakeShift={cakeShift}
      onCakeShift={setCakeShift}
      fullCake={
        !!cake &&
        (Math.abs(cake.azimuthRange[1] - cake.azimuthRange[0]) * cake.height) /
          Math.max(1, cake.height - 1) >=
          359
      }
      value={integrationDisplay}
      onChange={(value) => {
        correctionPreview.close();
        setIntegrationDisplay(value);
      }}
      state={state}
      ready={ready && !correctionPreview.map}
      run={runImageControl}
      showPhases={showImagePhases}
      onShowPhases={() => setShowImagePhases((v) => !v)}
      corrected={correctedImage}
      onCorrected={() => {
        setCorrectedImage((v) => !v);
        if (detectorAutoActive.current)
          setLimits((correctedImage ? rawImage : image)?.limits ?? limits);
        onHover(null);
      }}
      roi={!!state?.integration.roi}
      onRoi={() => {
        const [h, w] = state?.shape ?? [1, 1];
        void runImageControl("integration_roi", {
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
  );
  const cakeNavigation = useCakeProfileNavigation(
    cakeWindowViewport,
    JSON.stringify([
      state?.configurationContext,
      cake?.fullWidth,
      cake?.fullHeight,
      cake?.unit,
      !!state?.combination?.cakes,
    ]),
    cake,
  );
  const profileVisible =
    showCakeProfile && integrationDisplay === "cake" && !correctionPreview.map;
  const imageProfile = (
    <CakeProfilePanel
      state={state}
      cake={
        cake
          ? { ...cake, azimuthRange: (displayedCake ?? cake).azimuthRange }
          : null
      }
      cakeView={cakeNavigation.cakeView}
      onAzimuthRange={cakeNavigation.onAzimuthRange}
      linked={linked}
      shift={cakeShift}
      bins={cakeProfileBins}
      onBins={setCakeProfileBins}
      ready={ready && !settingsOpen && profileVisible}
      run={runImageControl}
      reportPlot={reportPlot}
      onInspect={(azimuth) => {
        if (!linked) return;
        setLocalImageClick(null);
        setClickedReading({
          source: "profile",
          text: `Azimuth ${azimuth}°`,
        });
        void runImageControl("validation_position", {
          source: "cake",
          unit: "2th_deg",
          x: linked.twoTheta,
          azimuth,
        });
      }}
    />
  );
  const workspace = (
    <div
      className="app"
      data-text-size={largeText ? "large" : "normal"}
      onClickCapture={(event) => {
        if (calibrationResetRequest || !(event.target instanceof Element))
          return;
        const control = event.target.closest<HTMLElement>(
          "button, input, select",
        );
        if (control) calibrationResetOpener.current = control;
      }}
    >
      <div className="app-body">
        <nav className="mode-navigation" aria-label="Workspace modes">
          <WorkspaceModeButtons
            mode={settingsOpen ? null : mode}
            onSelect={(next) => {
              setSettingsOpen(false);
              setMode(next);
            }}
          />
          <div className="navigation-utilities">
            {detectorWindow.detached && (
              <Button
                className="workspace-nav"
                aria-label="Show detector window"
                title="Show detector window"
                onClick={detectorWindow.open}
              >
                <ArrowUpRight size={20} />
              </Button>
            )}
            <CustomCommandButtons
              controller={customCommands}
              ready={ready}
              onError={setError}
            />
            <HistoryControls
              state={state}
              mode={mode}
              ready={ready}
              customActive={customHistoryActive}
              custom={customCommands}
              run={run}
            />
            <div className="navigation-group" role="group" aria-label="Project">
              {state?.projectName && (
                <div className="navigation-project" title={state.projectName}>
                  {state.projectName}
                </div>
              )}
              <Button
                className="workspace-nav project-action"
                aria-label="Open project"
                title="Open project"
                disabled={!ready}
                onClick={() => run("open_project", {}, "Opening project…")}
              >
                <FolderOpen size={20} />
              </Button>
              <Button
                className="workspace-nav project-action"
                aria-label="Save project"
                disabled={
                  !ready ||
                  (!state?.configurationLabels &&
                    !state?.hasImage &&
                    !map &&
                    !batch)
                }
                onClick={() => run("save_project", {}, "Saving project…")}
                aria-description={
                  geometryDirty || fitEditor.dirty || integrationDraft.dirty
                    ? "Projects save applied options. Unapplied option drafts remain in this session."
                    : undefined
                }
                title={`${state?.projectName ? `Save ${state.projectName}` : "Save project"} · ⌘/Ctrl+S${geometryDirty || fitEditor.dirty || integrationDraft.dirty ? " · Saves applied options; unapplied drafts stay in this session" : ""}`}
              >
                <Save size={20} />
              </Button>
            </div>
            <Button
              className={`workspace-nav navigation-settings ${settingsOpen ? "workspace-active" : ""}`}
              onClick={toggleSettings}
              aria-label="Settings"
              aria-controls="settings-workspace"
              aria-expanded={settingsOpen}
              title="Settings · ⌘/Ctrl+,"
              aria-keyshortcuts="Control+, Meta+,"
            >
              <Settings size={20} />
            </Button>
          </div>
        </nav>

        <div
          className={`workspace-stage ${configurationControlsVisible ? "has-configurations" : ""}`}
        >
          {configurationControlsVisible && state && (
            <div className="configuration-toolbar">
              <ConfigurationControls
                state={state}
                ready={
                  ready &&
                  !setupDirty &&
                  !geometryDirty &&
                  !fitEditor.dirty &&
                  !integrationDraft.dirty
                }
                run={run}
              />
            </div>
          )}
          <IntegrationWorkspace
            concealed={settingsOpen}
            active={mode === "integration"}
            controlsCollapsed={integrationControlsCollapsed}
            detectorDetached={detectorWindow.detached}
            display={
              correctionPreview.map
                ? "image"
                : integrationDisplay === "cake"
                  ? "cake"
                  : "image"
            }
          >
            <main
              className={`${mode}-mode`}
              data-integration-display={
                correctionPreview.map ? "image" : integrationDisplay
              }
            >
              {mode === "map" ? (
                <MapView
                  map={map}
                  progressPreview={progress?.mapPreview}
                  plotViews={plotViews}
                  mapWindow={mapWindow}
                  linked={linked}
                  localImageClick={localImageClick}
                  localPatternClick={localPatternClick}
                  onDetectorInspect={inspectDetector}
                  onPatternInspect={inspectPattern}
                  image={image}
                  mask={mask}
                  pattern={pattern}
                  state={state}
                  ready={ready}
                  run={run}
                  request={requestMap}
                  error={error}
                  reportPlot={reportPlot}
                  onDetectorHover={onHover}
                  onPatternHover={onPatternHover}
                  patternZoom={mapPatternZoom}
                  onPatternZoom={setMapPatternZoom}
                />
              ) : mode === "mask" ? (
                <MaskView
                  contrast={{
                    limits: maskLimits,
                    setLimits: setMaskLimits,
                    autoActive: maskAutoActive,
                    setAutoActive: setMaskAutoActive,
                  }}
                  plotViews={plotViews}
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
                          RMS {scientificValue(displayedRms, 4)}° · {fitPoints}{" "}
                          points ·{" "}
                          {
                            new Set(state?.calibration.picks.map((p) => p.ring))
                              .size
                          }{" "}
                          rings
                        </span>
                      )}
                      <div className="image-overlay-controls">
                        <label>
                          <Input
                            aria-label="Show calibrant lines"
                            type="checkbox"
                            checked={showRings}
                            onChange={(e) => setShowRings(e.target.checked)}
                          />
                          Calibrant lines
                        </label>
                        <label>
                          <Input
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
                  {state &&
                    !state.configurationLabels &&
                    state.configurationCount > 1 && (
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
                    <IntegrationLeftPane
                      active={mode === "integration"}
                      batch={
                        mode === "integration" && batchDockVisible ? (
                          <BatchDock
                            activeImagePath={state?.imagePath}
                            position={
                              linked
                                ? { x: linked.twoTheta, unit: "2th_deg" }
                                : localPatternClick
                            }
                            batch={batch}
                            calibrated={!!state?.calibrated}
                            ready={ready}
                            run={run}
                            request={requestMap}
                            reportPlot={reportPlot}
                            onDetach={() => batchWindow.open()}
                            linkedDisplay={{
                              unit: state?.unit ?? batch?.unit ?? "2th_deg",
                              log: logPattern,
                              sqrt: sqrtPattern,
                              onScale: (scale) => {
                                setLogPattern(scale === "log");
                                setSqrtPattern(scale === "sqrt");
                              },
                            }}
                            onHide={() => {
                              setBatchDockVisible(false);
                              saveLayoutValue(layoutKeys.batchOpen, false);
                            }}
                          />
                        ) : null
                      }
                    >
                      <section className="panel detector-panel">
                        {correctionPreview.map && (
                          <CorrectionPreviewDetector
                            key={correctionPreview.map.kind}
                            map={correctionPreview.map}
                            wavelength={state?.geometry.wavelength}
                            sampleGeometry={correctionPreview.sampleGeometry}
                            ready={ready}
                            onBack={correctionPreview.close}
                            onAuto={correctionPreview.auto}
                            reportPlot={reportPlot}
                          />
                        )}
                        {image ? (
                          <DetectorSurface
                            active={
                              mode !== "integration" ||
                              integrationDisplay === "image"
                            }
                            showUndock={mode !== "integration"}
                          >
                            <RasterView
                              exportRef={detectorExport}
                              raster={
                                mode === "integration" &&
                                !correctedImage &&
                                rawImage
                                  ? rawImage
                                  : image
                              }
                              {...detectorPlotSetup({
                                state,
                                viewports: plotViews,
                                mask,
                                showMask:
                                  mode !== "integration" || state?.useMask,
                                linked:
                                  mode === "integration" ? linked : undefined,
                                localImageClick:
                                  mode === "integration"
                                    ? localImageClick
                                    : null,
                                onInspect:
                                  mode === "integration"
                                    ? inspectDetector
                                    : undefined,
                              })}
                              limits={limits}
                              log={logImage}
                              palette={palette}
                              tool={tool}
                              busy={!!busy}
                              resetKey={resetKey}
                              onHover={onHover}
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
                              showNumbers={
                                mode === "calibration" && showNumbers
                              }
                              currentPeakRing={
                                mode === "calibration"
                                  ? displayedRing
                                  : undefined
                              }
                              activeRing={
                                mode === "calibration"
                                  ? displayedRing
                                  : undefined
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
                            />
                            <ImageIntensity
                              key={`detector-${state?.configurationContext ?? state?.configurationIndex}`}
                              initialAutoActive={detectorAutoActive.current}
                              onAutoActiveChange={(active) => {
                                detectorAutoActive.current = active;
                              }}
                              initialLevelsReady={configurationDisplays.current.has(
                                state?.configurationContext ??
                                  state?.configurationIndex ??
                                  0,
                              )}
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
                              onAuto={(settings) => {
                                detectorAutoActive.current = true;
                                return run(
                                  "image_levels",
                                  {
                                    ...settings,
                                    source:
                                      mode === "integration" && !correctedImage
                                        ? "raw_detector"
                                        : "detector",
                                  },
                                  "Updating intensity range…",
                                );
                              }}
                              limits={limits}
                              onLimits={(value) => {
                                detectorAutoActive.current = false;
                                setLimits(value);
                              }}
                              log={logImage}
                              onLog={(value) => {
                                detectorAutoActive.current = false;
                                setLogImage(value);
                              }}
                              palette={palette}
                              onPalette={setPalette}
                            />
                          </DetectorSurface>
                        ) : (
                          <div className="empty-view">
                            <div className="empty-icon">
                              <FileImage size={32} strokeWidth={1} />
                            </div>
                            <h3>
                              {mode === "integration"
                                ? "Open a detector image"
                                : "Open a calibrant image"}
                            </h3>
                            <p>
                              {mode === "integration" && batchWarning ? (
                                batchWarning
                              ) : (
                                <>
                                  Open a calibrant image to begin, or explore
                                  <br />
                                  the included CeO₂ reference measurement.
                                </>
                              )}
                            </p>
                            <Button
                              variant="primary"
                              disabled={!ready}
                              onClick={() =>
                                run("open_image", {}, "Opening detector image…")
                              }
                            >
                              <Plus size={15} />
                              Open detector image
                            </Button>
                            {state?.exampleAvailable && (
                              <Button
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
                              </Button>
                            )}
                          </div>
                        )}
                      </section>
                      {(mode === "integration" || calibrationStep === 3) && (
                        <section className="panel cake-panel">
                          {cake ? (
                            <DetectorSurface
                              enabled={mode === "integration"}
                              active={integrationDisplay === "cake"}
                              showUndock={false}
                              interactionKey="cake"
                              cakeWavelength={state?.geometry.wavelength}
                              profile={
                                mode === "integration" && profileVisible
                                  ? imageProfile
                                  : null
                              }
                            >
                              <RasterView
                                exportRef={cakeExport}
                                viewport={cakeNavigation.viewport}
                                raster={displayedCake ?? cake}
                                radialAxis={cakeRadialAxis}
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
                                    ? linked
                                      ? (radialValues(
                                          linked.twoTheta,
                                          "2th_deg",
                                          state?.geometry.wavelength,
                                        )[cake.unit] ?? undefined)
                                      : undefined
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
                                calibrantLines={cakeCalibrantLines?.map(
                                  (line) => ({
                                    ...line,
                                    twoTheta:
                                      radialValues(
                                        line.twoTheta,
                                        "2th_deg",
                                        state?.geometry.wavelength,
                                      )[cake.unit] ?? NaN,
                                  }),
                                )}
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
                                    unit: cake.unit,
                                    ...coords,
                                  });
                                }}
                                zoomMode={cakeZoom}
                                onZoomMode={setCakeZoom}
                                cake
                                showCakeAzimuthAxis={
                                  !(mode === "integration" && profileVisible)
                                }
                                limits={cakeLimits}
                                log={cakeLog}
                                palette={cakePalette}
                                resetKey={resetKey}
                              />
                              <ImageIntensity
                                key={`cake-${state?.configurationContext ?? state?.configurationIndex}-${!!state?.combination?.cakes}`}
                                initialAutoActive={cakeAutoActive.current}
                                onAutoActiveChange={(active) => {
                                  cakeAutoActive.current = active;
                                }}
                                initialLevelsReady={configurationCakeDisplays.current.has(
                                  `${state?.configurationContext ?? state?.configurationIndex}:${!!state?.combination?.cakes}`,
                                )}
                                preferences={cakePreferences}
                                onPreferences={setCakePreferences}
                                display="cake"
                                raster={cake}
                                ready={ready}
                                onAuto={(settings) => {
                                  cakeAutoActive.current = true;
                                  return run(
                                    "image_levels",
                                    { ...settings, source: "cake" },
                                    "Updating cake intensity…",
                                  );
                                }}
                                limits={cakeLimits}
                                onLimits={(value) => {
                                  cakeAutoActive.current = false;
                                  setCakeLimits(value);
                                }}
                                log={cakeLog}
                                onLog={(value) => {
                                  cakeAutoActive.current = false;
                                  setCakeLog(value);
                                }}
                                palette={cakePalette}
                                onPalette={setCakePalette}
                              />
                            </DetectorSurface>
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
                      {mode === "integration" && (
                        <DetectorWindowTools
                          controls={imageControls}
                          profile={profileVisible ? imageProfile : null}
                        />
                      )}
                    </IntegrationLeftPane>
                    {((pattern && calibrationStep === 3) ||
                      mode === "integration") && (
                      <section className="panel pattern-panel">
                        {mode === "integration" && (
                          <>
                            <IntegrationPatternActions
                              state={state}
                              ready={ready}
                              run={run}
                              onSaveFigure={() => {
                                try {
                                  const source =
                                    patternExport.current?.source?.();
                                  if (source) setFigureEditor({ source });
                                } catch (error) {
                                  setError(
                                    error instanceof Error
                                      ? error.message
                                      : String(error),
                                  );
                                }
                              }}
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
                          <SpottinessPattern
                            enabled={
                              mode === "integration" &&
                              !!state?.integration.azimuthalStd
                            }
                            relative={!!state?.integration.spottinessRelative}
                            {...patternPlot!.props}
                            exportRef={patternExport}
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
                            onPick={patternPlot!.inspect}
                          />
                        ) : (
                          <div className="empty-pattern">
                            <IntegrationModeIcon size={25} />
                            {state?.hasImage && !state?.calibrated ? (
                              <>
                                <span>
                                  Load a calibration to integrate this image.
                                </span>
                                <LoadCalibrationButton
                                  ready={ready}
                                  label="Load calibration to integrate the image"
                                  onLoad={() =>
                                    void run(
                                      "open_calibration",
                                      {},
                                      "Loading calibration…",
                                    )
                                  }
                                />
                              </>
                            ) : (
                              <span>
                                Your integrated diffraction pattern will appear
                                here.
                              </span>
                            )}
                          </div>
                        )}
                      </section>
                    )}
                  </div>
                </>
              )}
            </main>
            {mode !== "map" && (
              <aside
                className={`sidebar ${mode === "calibration" ? "calibration-task-panel" : ""}`}
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
                  {mode === "mask" ? (
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
                              <Button
                                variant="secondary"
                                className="setup-open-image"
                                disabled={!ready}
                                onClick={() =>
                                  run(
                                    "open_image",
                                    {},
                                    "Opening detector image…",
                                  )
                                }
                                title={
                                  state?.imagePath ?? "Open a detector image"
                                }
                              >
                                <FolderOpen size={14} />
                                Open image
                              </Button>
                              {state?.hasImage && (
                                <div className="setup-image-navigation">
                                  <Button
                                    variant="secondary"
                                    title="Previous image"
                                    aria-label="Previous image"
                                    disabled={!ready}
                                    onClick={() =>
                                      run(
                                        "next_image",
                                        { direction: -1, files_only: true },
                                        "Opening previous image…",
                                      )
                                    }
                                  >
                                    ←
                                  </Button>
                                  <Button
                                    variant="secondary"
                                    title="Next image"
                                    aria-label="Next image"
                                    disabled={!ready}
                                    onClick={() =>
                                      run(
                                        "next_image",
                                        { direction: 1, files_only: true },
                                        "Opening next image…",
                                      )
                                    }
                                  >
                                    →
                                  </Button>
                                </div>
                              )}
                            </div>
                            <ImageSourceControl
                              state={state}
                              disabled={!ready}
                              onChange={(dataset) =>
                                void run(
                                  "select_image_source",
                                  { dataset },
                                  "Opening image source…",
                                )
                              }
                            />
                            {state?.imageName && (
                              <div
                                className="setup-image-filename"
                                title={state.imagePath ?? state.imageName}
                              >
                                {state.imageName}
                              </div>
                            )}
                            {state?.exampleAvailable && !state?.hasImage && (
                              <Button
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
                              </Button>
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
                            <>
                              <GeometryProvenance state={state} detail />
                              <section className="calibration-validation-reference">
                                <label className="calibration-field-row">
                                  <span>Calibrant</span>
                                  <Select
                                    aria-label="Validation calibrant"
                                    disabled={!ready}
                                    value={
                                      state?.calibration.calibrant ?? "CeO2"
                                    }
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
                                  </Select>
                                </label>
                                <Button
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
                                </Button>
                              </section>
                            </>
                          )}
                          <div hidden={calibrationStep !== 3}>
                            <GeometryEditor
                              editor={geometryDraft}
                              ready={ready}
                              run={run}
                              embedded
                              formId="validation-geometry-form"
                              convention={validationConvention}
                              onConventionChange={setValidationConvention}
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
                            fitEditor={fitEditor}
                          />
                        </>
                      )}
                      {mode === "integration" && (
                        <IntegrationView
                          correctionPreviewKind={
                            correctionPreview.map?.kind ?? null
                          }
                          onCorrectionPreview={correctionPreview.toggle}
                          controlsCollapsed={integrationControlsCollapsed}
                          onControlsCollapsedChange={
                            setIntegrationControlsCollapsed
                          }
                          overlayReveal={overlayReveal}
                          fileStep={imageFileStep}
                          setFileStep={setImageFileStep}
                          onOpenBatch={activateBatch}
                          batchOpen={batchDockVisible || batchWindow.detached}
                          batchDocked={batchDockVisible}
                          state={state}
                          ready={ready}
                          run={run}
                          runProcessing={(command, args, message, onSuccess) =>
                            run(command, args, message, onSuccess, () => {
                              const current = currentState.current;
                              return (
                                current?.projectName === state?.projectName &&
                                current?.configurationIndex ===
                                  state?.configurationIndex &&
                                current?.imagePath === state?.imagePath &&
                                current?.selectedImageSource ===
                                  state?.selectedImageSource
                              );
                            })
                          }
                          backgroundSettings={liveBackground.settings}
                          onBackgroundChange={liveBackground.change}
                          backgroundUpdating={liveBackground.updating}
                          inspectBackground={inspectBackground}
                          onInspectBackgroundChange={setInspectBackground}
                          backgroundDefaultRange={
                            pattern?.x.length
                              ? [
                                  Math.min(pattern.x[0], pattern.x.at(-1)!),
                                  Math.max(pattern.x[0], pattern.x.at(-1)!),
                                ]
                              : [0, 50]
                          }
                          onOverlaySelectionChange={setSelectedOverlayUid}
                          showOriginalPattern={originalPatternVisible}
                          onShowOriginalPatternChange={(visible) => {
                            setShowOriginalPattern(visible);
                            void run("integration_overlay", {
                              operation: "original_visibility",
                              visible,
                            });
                          }}
                          originalPatternColor={originalPatternColor}
                          onOriginalPatternColorChange={(color) => {
                            setOriginalPatternColor(color);
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
                          <Button
                            type="submit"
                            form="validation-geometry-form"
                            className="primary calibration-apply-geometry"
                            disabled={
                              !ready ||
                              !activeGeometryDirty ||
                              !activeGeometryValid
                            }
                            title={
                              activeGeometryDirty
                                ? "Apply the visible convention"
                                : "Return to the convention with unapplied edits to apply it"
                            }
                          >
                            Apply geometry
                          </Button>
                        )}
                        <Button
                          variant="primary"
                          className="fit-button"
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
                        </Button>
                        <Button
                          variant="secondary"
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
                        </Button>
                      </div>
                    )}
                    <div className="calibration-general-actions">
                      <Button
                        variant="secondary"
                        className="calibration-save"
                        aria-label="Save .poni calibration"
                        disabled={!canSaveCalibration}
                        title={
                          !ready
                            ? "Wait for processing to finish."
                            : !state?.calibrated
                              ? "Calibrate or load a geometry before saving."
                              : geometryDirty
                                ? "Apply or reset the geometry draft before saving."
                                : setupDirty
                                  ? "Finish detector settings before saving."
                                  : state?.calibration.fitDirty
                                    ? "Ring selections changed; calibrate or refine before saving."
                                    : "Save the current applied geometry. Unapplied fit starting values remain in this session."
                        }
                        onClick={() =>
                          run(
                            "save_calibration",
                            {},
                            "Saving PONI calibration…",
                          )
                        }
                      >
                        <Save size={15} />
                        Save .poni
                      </Button>
                      <div className="calibration-secondary-actions">
                        <Button
                          variant="quiet"
                          aria-label="Reset calibration"
                          title="Reset calibration and detector setup; keep the image"
                          disabled={
                            !ready || (!state?.hasImage && !state?.calibrated)
                          }
                          onClick={(event) => {
                            calibrationResetOpener.current =
                              event.currentTarget;
                            setCalibrationResetRequest("reset");
                          }}
                        >
                          <RotateCcw size={14} />
                        </Button>
                        <Button
                          variant="quiet"
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
                        </Button>
                        <Button
                          variant="quiet"
                          disabled={!ready}
                          onClick={() => setManualGeometryOpen(true)}
                        >
                          Enter manually
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </aside>
            )}
          </IntegrationWorkspace>
          {draftReplacement.dialog}
          {calibrationResetRequest && (
            <CalibrationResetDialog
              request={calibrationResetRequest}
              onCancel={() => {
                setCalibrationResetRequest(undefined);
                const opener = calibrationResetOpener.current;
                requestAnimationFrame(() => opener?.focus());
              }}
              onConfirm={(keepCalibration = false) => {
                const request = calibrationResetRequest;
                setCalibrationResetRequest(undefined);
                if (request === "reset")
                  void run("reset_calibration", {}, "Resetting calibration…");
                else if ("calibrationShape" in request)
                  void run(
                    "open_calibration",
                    { path: request.path, clear_image: true },
                    "Loading calibration for a different detector…",
                  );
                else
                  void run(
                    "open_image",
                    {
                      ...request.options,
                      path: request.path,
                      frame: request.frame,
                      ...(request.calibrated === false
                        ? { reset_image_state: true }
                        : keepCalibration
                          ? { keep_calibration: true }
                          : { reset_calibration: true }),
                    },
                    request.calibrated === false
                      ? "Opening image and resetting its coordinates…"
                      : keepCalibration
                        ? "Opening image with current calibration…"
                        : "Opening image and resetting calibration…",
                  );
              }}
            />
          )}
          {manualGeometryOpen && (
            <ManualGeometryDialog
              editor={geometryDraft}
              convention={validationConvention}
              onConventionChange={setValidationConvention}
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
              section={settingsSection}
              onSectionChange={setSettingsSection}
              integrationDraft={integrationDraft}
              onCustomActionsActiveChange={setCustomActionsOpen}
              customCommands={customCommands}
              state={state}
              ready={ready}
              run={run}
              largeText={largeText}
              onLargeText={setLargeText}
              showConfigurationControls={showConfigurationControls}
              onShowConfigurationControls={changeConfigurationControls}
              onClose={closeSettings}
              returnLabel={
                {
                  calibration: "Calibration",
                  mask: "Mask",
                  integration: "Integration",
                  map: "Map",
                }[mode]
              }
            />
          )}
        </div>
        {figureEditor && (
          <PatternFigureDialog
            source={figureEditor.source}
            initialPath={null}
            run={run}
            onClose={() => setFigureEditor(null)}
          />
        )}
        <footer className="app-status">
          <div className="plot-status">
            <div className="plot-status-line">
              <span
                data-testid="mouse-readout"
                className="plot-status-reading"
                data-plot={mainPlotReading?.source}
                data-pixel-x={mainPlotReading?.x}
                data-pixel-row={mainPlotReading?.row}
                title={mainPlotReading?.text}
              >
                {mainPlotReading ? (
                  <ReadingFields reading={mainPlotReading} />
                ) : (
                  (state?.imageName ?? "No image loaded")
                )}
              </span>
            </div>
            {!correctionPreview.map &&
              !settingsOpen &&
              (mode === "integration" || mode === "map") && (
                <div className="plot-status-line clicked-position">
                  <span
                    className="plot-status-kind"
                    title="Last selected position. Click a detector or pattern to choose a point; move the pointer to inspect values."
                  >
                    Click
                  </span>
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
            <StatusMessage error={error} message={statusMessage} />
            {error && (
              <Button
                variant="secondary"
                className="status-action"
                aria-label="Dismiss error"
                onClick={() => setError(null)}
              >
                ×
              </Button>
            )}
            {maskSelection && (
              <Button
                variant="secondary"
                className="status-action"
                onClick={maskSelection.cancel}
              >
                Cancel selection
              </Button>
            )}
            {progress?.running && (
              <Button
                variant="secondary"
                className="status-action"
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
              </Button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
  return (
    <DetectorWindowProvider value={detectorWindow}>
      {workspace}
    </DetectorWindowProvider>
  );
}
