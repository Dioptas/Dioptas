import type {
  CommandInvocation,
  CheckedInvocation,
  CheckedRunInvocation,
  CommandRequestReader,
} from "./commandContracts";
import {
  submitWorkspaceCommand,
  forwardScheduledRun,
  retryStoredMap,
  notifyScheduledSuccess,
  scheduledInvocation,
  withScheduling,
  withCommandMessage,
  withCommandSuccess,
} from "./workspaceCommands";
import type { ScheduledRun, ScheduledRunInvocation } from "./workspaceCommands";
import { forwardInvoke } from "./commandDispatch";
import { handleCommandResponse } from "./commandResponse";
import { useResponseSnapshot } from "./useResponseSnapshot";
import { clickContext } from "./responseSnapshot";
import { applyWorkspaceResponse } from "./workspaceResponse";
import { CommandCoordinator, commandPolicy } from "./commandCoordinator";
import { Hdf5SourceDialog } from "./Hdf5SourceDialog";
import { TabList } from "./TabList";
import type { Hdf5SourceRequest } from "./types";
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
import { useSessionRecovery } from "./SessionRecovery";
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
import { SingleCrystalHistory } from "./SingleCrystalHistory";
import { SingleCrystalWorkspace } from "./SingleCrystalWorkspace";
import {
  refreshBackendSnapshots,
  lostCrystalScanMessage,
} from "./backendReloadSnapshot";
import {
  beginBackendUpdate,
  isCurrentBackendUpdate,
  publishBackendGuidance,
} from "./backendUpdateStatus";
import { WorkspaceModeButtons } from "./WorkspaceModeButtons";
import { HistoryControls } from "./HistoryControls";
import { useGeometryDraft } from "./geometryDraft";
import { useWorkflowNotice } from "./useWorkflowNotice";
import { scientificValue } from "./ScientificNumberInput";
import { AppFooter } from "./AppFooter";
import { useWorkspaceShortcuts } from "./useWorkspaceShortcuts";
import {
  isScientificHistoryCommand,
  scientificHistoryAction,
} from "./historyLabels";
import {
  useIntegrationSettingsDraft,
  useIntegrationSettingsAutoApply,
} from "./IntegrationSettings";
import { GeometryProvenance } from "./GeometryProvenance";
import { BackendStatusMessage } from "./BackendStatusMessage";
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
  Plus,
  Save,
  Settings,
  Sparkles,
} from "lucide-react";
import { connect, updateWindowTitle } from "./bridge";
import { recordAction } from "./errorReporting";
import { SettingsWorkspace } from "./SettingsWorkspace";
import { AppUpdateNotice } from "./AppUpdateNotice";
import { useAppUpdate } from "./useAppUpdate";
import { useProcessingWorkerPreference } from "./ProcessingWorkerSettings";
import { useCustomCommands } from "./customCommands";
import { CustomCommandButtons } from "./CustomCommandButtons";
import "./sharedFooter.css";
import {
  usePlotReadout,
  type PatternHover,
  type PlotReading,
} from "./plotReadout";
import {
  patternReading,
  detectorReading,
  cakeReading,
  cakeCoordinates,
  coordinateValue,
  type SourcedReading,
} from "./PlotStatus";
import type { PatternPosition } from "./linkedPosition";
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
import { MapView } from "./MapView";
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
import { MAP_UPDATE_INTERVAL_MS } from "./updateRateLimit";
import { useLiveBackground, DEFAULT_BACKGROUND } from "./useLiveBackground";
import { BACKGROUND_RANGE_COLOR } from "./drawRangeSelection";
import { CalibrantPicker } from "./CalibrantPicker";
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
import { DistortionDialog } from "./DistortionDialog";
import type { RingOverlay } from "./types";
import type { ZoomMode } from "./usePlotNavigation";
import { LoadCalibrationButton } from "./LoadCalibrationButton";

export default function App() {
  const responseSnapshot = useResponseSnapshot();
  const {
    state,
    setState,
    image,
    rawImage,
    mask,
    cake,
    pattern,
    batch,
    map,
    scxrd,
    rings,
    linked,
    batchWarning,
    mapWarning,
    showOriginalPattern,
    setShowOriginalPattern,
    originalPatternColor,
    setOriginalPatternColor,
  } = responseSnapshot;
  const beforePreviewCommand = useRef<(command: string) => void>(() => {});
  const [plotViews] = useState(createPlotViews);
  const [mapPlotViews] = useState(() => ({
    ...createPlotViews(),
    pattern: plotViews.pattern,
  }));
  const [mapResetKey, setMapResetKey] = useState(0);
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
  const [selectedOverlayUid, setSelectedOverlayUid] = useState<string | null>(
    null,
  );
  const [inspectBackground, setInspectBackground] = useState(false);
  const [cakeShift, setCakeShift] = useState(0);
  const [correctedImage, setCorrectedImage] = useState(true);
  const correctedImageRef = useRef(true);
  correctedImageRef.current = correctedImage;
  const [showImagePhases, setShowImagePhases] = useState(false);
  const [phaseGuides, setPhaseGuides] = useState<RingOverlay[]>([]);
  const phaseGuideRevision = useRef<number | null>(null);
  const [calibrationStep, setCalibrationStep] = useState(0);
  const [wavelengthHint, setWavelengthHint] = useState<NonNullable<
    import("./types").Response["wavelengthHint"]
  > | null>(null);
  const [distortionOpen, setDistortionOpen] = useState(false);
  const [distortionPreview, setDistortionPreview] = useState<
    import("./types").DistortionPreview | null
  >(null);
  const [autoMaskUndoAvailable, setAutoMaskUndoAvailable] = useState(false);
  const [manualSection, setManualSection] = useState<"peaks" | "parameters">(
    "peaks",
  );
  useEffect(() => {
    if (calibrationStep === 1 && state && !state.calibrated) {
      setCalibrationStep(0);
    }
  }, [calibrationStep, state?.calibrated]);
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
  const currentLinked = useRef<Response["linked"]>(undefined);
  const retainedClickContext = useRef<string | undefined>(undefined);
  const [clickedReading, setClickedReading] = useState<SourcedReading | null>(
    null,
  );
  // The single-crystal click has its own detector and geometry: not linked.
  const [scxrdClick, setScxrdClick] = useState<PlotReading | null>(null);
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
  const [scxrdDraftDirty, setScxrdDraftDirty] = useState(false);
  const [mode, setMode] = useState<
    "calibration" | "integration" | "mask" | "map" | "scxrd"
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
  const appUpdate = useAppUpdate();
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
  const [batchDockVisible, setBatchDockVisible] = useState(
    () =>
      readLayoutFlag(layoutKeys.batchOpen) &&
      readLayoutFlag(layoutKeys.batchDocked),
  );
  const [batchOpenRequest, setBatchOpenRequest] = useState(0);
  const requestMap: CommandRequestReader = async <
    const A extends CommandInvocation,
  >(
    ...call: CheckedInvocation<A>
  ) => {
    const [command] = call;
    // Batch snapshots/levels are read-only and the worker serializes them.
    // A quiet image-level update must not drop the companion's refresh.
    if (
      !bridge.current ||
      (commands.busy &&
        command !== "batch_snapshot" &&
        command !== "batch_levels")
    )
      return;
    try {
      const result = await forwardInvoke(bridge.current, call);
      if (!result.ok) setError(result.error ?? "Map command failed.");
      return result;
    } catch (error) {
      setError(String(error));
    }
  };

  const [pickingEnabled, setPickingEnabled] = useState(true);
  const [ring, setRing] = useState(1),
    [automatic, setAutomatic] = useState(true);
  const bridge = useRef<Invoke | null>(null);
  const [commands] = useState(() => new CommandCoordinator());
  const currentState = useRef<State | null>(null);
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
  const canSwitchToPick = !!state?.hasImage && !setupDirty && !geometryDirty;
  const canPick = calibrationStep === 2 && canSwitchToPick;
  const tool: Tool =
    mode === "calibration" && pickingEnabled && canPick ? "pick" : "pan";
  // Calibration validation shows the image, cake and pattern together; clicks
  // there mark the same linked green position as in Integration.
  const linkedClicks =
    mode === "integration" || (mode === "calibration" && calibrationStep === 1);
  // Picking is only active in Manual; Validate clicks always inspect.
  const detectorInspects = linkedClicks;
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
  const multipleImages = mode === "integration" || calibrationStep === 1;
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
  const [hdf5SourceRequest, setHdf5SourceRequest] =
    useState<Hdf5SourceRequest>();
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
    (result: Response, resetImageView = true, retainClick = false) =>
      applyWorkspaceResponse(
        result,
        {
          snapshot: responseSnapshot,
          configuration: { begin: beginConfigurationDisplay },
          session: {
            current: currentState,
            supportsProducts: supportsRequestedProducts,
            canDefer: canDeferIntegration,
            retainedClick: retainedClickContext,
            phaseGuideRevision,
            resetCalibrationDrafts: (next) => {
              resetFitDraft(next.calibration);
              resetGeometryDraft(next.calibration);
            },
            clearCalibrationSelection: () => {
              setSelectedPicks([]);
              setPhaseGuides([]);
            },
          },
          detector: {
            source: imageSource,
            rawSource: rawImageSource,
            autoActive: detectorAutoActive,
            useRaw: () =>
              activeMode.current === "integration" &&
              !correctedImageRef.current,
            levels: setLimits,
            resetView: () => setResetKey((k) => k + 1),
            invalidateHover: (clearTimer) => {
              ++hoverSequence.current;
              hoverLatest.current = null;
              if (clearTimer) {
                if (hoverTimer.current) clearTimeout(hoverTimer.current);
                hoverTimer.current = null;
              }
              setPixel(null);
            },
          },
          cake: {
            source: cakeSource,
            autoActive: cakeAutoActive,
            levels: setCakeLimits,
          },
          inspection: {
            linked: currentLinked,
            batchPosition: (next) => {
              setLocalPatternClick(next.batchPosition!);
              setLocalImageClick(null);
              const fields = radialFields(
                next.batchPosition!.x,
                next.batchPosition!.unit,
                next.batchWavelength ?? undefined,
              );
              setClickedReading({
                source: "batch",
                fields,
                text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
              });
            },
          },
          products: {
            guides: setPhaseGuides,
            ring: setRing,
            requestedRings: requestedProductsRef,
            requestedRingContext,
          },
          workflow: {
            revealOverlays: () => setOverlayReveal((n) => n + 1),
            openBatch: () => {
              setMode("integration");
              setBatchOpenRequest((v) => v + 1);
            },
            notice: setNotice,
          },
        },
        resetImageView,
        retainClick,
      ),
    [],
  );
  const run = useCallback<ScheduledRun>(
    async <const A extends ScheduledRunInvocation>(
      ...call: CheckedRunInvocation<A>
    ): Promise<void> => {
      const [
        command,
        payload,
        suppliedMessage,
        ,
        shouldRun,
        queueIfBusy = false,
        replaceDrafts = false,
      ] = call;
      const args = { ...payload };
      const message = suppliedMessage ?? "Processing…";
      if (
        !replaceDrafts &&
        draftReplacement.request(command, () => {
          void forwardScheduledRun(
            run,
            scheduledInvocation(call, { replaceDrafts: true }),
          );
        })
      )
        return;
      const historyLabel = scientificHistoryAction(
        currentState.current,
        activeMode.current,
        command.startsWith("redo"),
      );
      const batchAction =
        command.startsWith("batch_") &&
        !["batch_levels", "batch_snapshot"].includes(command);
      const commandMode = batchAction ? "integration" : activeMode.current;
      const policy = commandPolicy({
        action: command,
        args,
        message,
        mode: commandMode,
        queueIfBusy,
        overlayHistory:
          isScientificHistoryCommand(command) &&
          historyLabel === "integration_overlay",
      });
      if (!bridge.current || !commands.accepts(policy)) return;
      beforePreviewCommand.current(command);
      if (batchAction) {
        setMode("integration");
        setSettingsOpen(false);
      }
      await commands.execute<Response>(
        policy,
        async () => {
          const invoke = bridge.current!;
          const quiet = policy.quiet;
          // Disabling the source selector while opening can blur it before the
          // size-confirmation response arrives (especially in WebKit).
          if (
            command === "select_image_source" &&
            document.activeElement instanceof HTMLElement
          )
            calibrationResetOpener.current = document.activeElement;
          const quietBackgroundJob = policy.backgroundJob;
          if (quietBackgroundJob) {
            ++progressGeneration.current;
            setProgress(undefined);
            setQuietBackgroundProcessing(true);
          }
          if (!quiet) {
            ++progressGeneration.current;
            setProgress(undefined);
            setBusy(message);
            // The automatic display refresh after a load must not wipe the
            // notice of the command that triggered it (e.g. Loaded calibration).
            if (command !== "display_products") setNotice(null);
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
          navigationTrace("command-start", { action: command });
          try {
            return await handleCommandResponse(
              {
                command,
                args,
                historyLabel,
                invoke,
                selectedPosition: currentLinked.current,
                pendingDrafts: () => pendingOptionDrafts.current,
                submit: () =>
                  submitWorkspaceCommand(
                    invoke,
                    call,
                    commandMode,
                    canDeferIntegration.current,
                  ),
                retryStoredMap: () => retryStoredMap(invoke, call, commandMode),
                detector: {
                  autoActive: () => detectorAutoActive.current,
                  raw: () =>
                    commandMode === "integration" && !correctedImageRef.current,
                  previous: (raw) =>
                    raw ? rawImageSource.current : imageSource.current,
                  autoLevels: () => {
                    const display = detectorDisplay.current;
                    return readImageAutoLevels(
                      display.name,
                      display.filterGaps,
                    );
                  },
                },
              },
              {
                apply,
                trace: (event, result) =>
                  navigationTrace(event, {
                    action: command,
                    bufferId: result.image?.bufferId,
                  }),
                defer: (decision) => {
                  if (
                    document.activeElement instanceof HTMLElement &&
                    document.activeElement !== document.body
                  )
                    calibrationResetOpener.current = document.activeElement;
                  if (decision.kind === "hdf5")
                    setHdf5SourceRequest(decision.request);
                  else setCalibrationResetRequest(decision.request);
                },
                drafts: {
                  integration: resetIntegrationDraft,
                  geometry: resetGeometryDraft,
                  fit: resetFitDraft,
                },
                workflow: {
                  notice: setNotice,
                  error: setError,
                  clearPicks: () =>
                    setSelectedPicks((previous) =>
                      previous.length ? [] : previous,
                    ),
                  calibrationStep: setCalibrationStep,
                },
                success: (result) => {
                  if (
                    command === "estimate_distortion" &&
                    result.distortionPreview
                  ) {
                    setDistortionPreview(result.distortionPreview);
                  } else if (
                    [
                      "open_image",
                      "example",
                      "open_project",
                      "reset_calibration",
                    ].includes(command)
                  ) {
                    setDistortionPreview(null);
                  }
                  if (result.autoMaskNotice) {
                    setAutoMaskUndoAvailable(true);
                  } else if (
                    [
                      "open_image",
                      "next_image",
                      "select_image_source",
                      "example",
                      "open_project",
                      "reset_calibration",
                      "undo_mask",
                      "redo_mask",
                      "clear_mask",
                      "mask_edit",
                      "mask_stroke",
                      "mask_file",
                    ].includes(command)
                  ) {
                    setAutoMaskUndoAvailable(false);
                  }
                  if (command === "auto_calibrate" && result.wavelengthHint) {
                    setWavelengthHint(result.wavelengthHint);
                  } else if (
                    [
                      "auto_calibrate",
                      "calibrate",
                      "manual_geometry",
                      "open_calibration",
                      "reset_calibration",
                      "open_image",
                      "example",
                      "open_project",
                    ].includes(command)
                  ) {
                    setWavelengthHint(null);
                  }
                  notifyScheduledSuccess(call, result);
                },
              },
            );
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
          }
        },
        shouldRun,
      );
    },
    [
      apply,
      commands,
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
        commands.busy ||
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
      run: withCommandMessage(run, "Preparing navigation benchmark…", {
        queueIfBusy: false,
        replaceDrafts: true,
      }),
      state: () => currentState.current,
      image: () => imageSource.current,
      series: () => ({ batch: batch ?? null, map: map ?? null }),
    };
    window.__dioptasNavigationProbe = probe;
    return () => {
      if (window.__dioptasNavigationProbe === probe)
        delete window.__dioptasNavigationProbe;
    };
  }, [run, batch, map]);
  useLayoutEffect(() => {
    navigationTrace("react-commit", {
      revision: state?.revision,
      bufferId: image?.bufferId,
    });
  }, [state?.revision, image?.bufferId]);
  useBackendReload((message, restored, failed) => {
    setNotice(message);
    const update = beginBackendUpdate(message, restored, failed);
    if ((restored || failed) && bridge.current)
      void refreshBackendSnapshots(
        bridge.current,
        (result) => {
          if (isCurrentBackendUpdate(update)) apply(result, false, true);
        },
        !!scxrd?.frames,
        restored,
      )
        .then((missingScan) => {
          if (missingScan && isCurrentBackendUpdate(update))
            publishBackendGuidance({
              kind: "lost-scan",
              message: lostCrystalScanMessage,
            });
        })
        .catch((error) => {
          if (isCurrentBackendUpdate(update)) setError(String(error));
        });
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
  const recovery = useSessionRecovery({
    ui: {
      // Single-crystal recipes have separate persistence from powder projects.
      mode: mode === "scxrd" ? "calibration" : mode,
      calibrationStep,
      validationConvention,
      integrationDisplay,
      showConfigurationControls,
      showRings,
      showNumbers,
      pickingEnabled,
      ring,
      logImage,
      palette,
      limits,
      detectorAuto: detectorAutoActive.current,
      cakeLog,
      cakePalette,
      cakeLimits,
      cakeAuto: cakeAutoActive.current,
      detectorPreferences,
      multiDetectorPreferences,
      cakePreferences,
      sqrtPattern,
      correctedImage,
      cakeShift,
    },
    refresh: async () => {
      let displayed = false;
      await run(
        "state",
        {},
        "Restoring workspace…",
        (result: Response) => {
          if (!result.state) return;
          resetIntegrationDraft(result.state);
          resetGeometryDraft(result.state.calibration);
          resetFitDraft(result.state.calibration);
          displayed = true;
        },
        undefined,
        true,
        true,
      );
      if (!displayed)
        throw new Error("The restored workspace could not be displayed.");
    },
    openStartup: async (action, path) => {
      if (action === "open_project")
        await run("open_project", { path }, "Opening requested project…");
      else if (action === "open_calibration")
        await run(
          "open_calibration",
          { path },
          "Opening requested calibration…",
        );
      else if (action === "open_image")
        await run("open_image", { path }, "Opening requested image…");
    },
    restoreUi: (ui) => {
      if (ui.mode !== undefined) setMode(ui.mode);
      if (ui.calibrationStep !== undefined)
        setCalibrationStep(
          ui.calibrationStep === 3 ? 1 : Math.min(2, ui.calibrationStep),
        );
      if (ui.validationConvention !== undefined)
        setValidationConvention(ui.validationConvention);
      if (ui.integrationDisplay !== undefined)
        setIntegrationDisplay(ui.integrationDisplay);
      if (ui.showConfigurationControls !== undefined)
        setShowConfigurationControls(ui.showConfigurationControls);
      if (ui.showRings !== undefined) setShowRings(ui.showRings);
      if (ui.showNumbers !== undefined) setShowNumbers(ui.showNumbers);
      if (ui.pickingEnabled !== undefined) setPickingEnabled(ui.pickingEnabled);
      if (ui.ring !== undefined) setRing(ui.ring);
      if (ui.logImage !== undefined) setLogImage(ui.logImage);
      if (ui.palette !== undefined) setPalette(ui.palette);
      if (ui.limits !== undefined) setLimits(ui.limits);
      if (ui.detectorAuto !== undefined)
        detectorAutoActive.current = ui.detectorAuto;
      if (ui.cakeLog !== undefined) setCakeLog(ui.cakeLog);
      if (ui.cakePalette !== undefined) setCakePalette(ui.cakePalette);
      if (ui.cakeLimits !== undefined) setCakeLimits(ui.cakeLimits);
      if (ui.cakeAuto !== undefined) cakeAutoActive.current = ui.cakeAuto;
      if (ui.detectorPreferences !== undefined)
        setDetectorPreferences(ui.detectorPreferences);
      if (ui.multiDetectorPreferences !== undefined)
        setMultiDetectorPreferences(ui.multiDetectorPreferences);
      if (ui.cakePreferences !== undefined)
        setCakePreferences(ui.cakePreferences);
      if (ui.sqrtPattern !== undefined) setSqrtPattern(ui.sqrtPattern);
      if (ui.correctedImage !== undefined) setCorrectedImage(ui.correctedImage);
      if (ui.cakeShift !== undefined) setCakeShift(ui.cakeShift);
    },
  });
  useEffect(() => {
    let mounted = true;
    connect()
      .then(async (invoke) => {
        if (!mounted) return;
        const displayInvoke = withRequestedProducts(
          invoke,
          () => requestedProductsRef.current,
        );
        bridge.current = <const A extends CommandInvocation>(
          ...call: CheckedInvocation<A>
        ) =>
          supportsRequestedProducts.current
            ? forwardInvoke(displayInvoke, call)
            : forwardInvoke(invoke, call);
        await run("state", {}, "Opening workspace…");
        if (mounted) await recovery.start();
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
  }, [run, recovery.start]);
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
  useWorkspaceShortcuts({
    run,
    currentState,
    canPick: canSwitchToPick,
    mode,
    setMode,
    onPickShortcut: () => {
      setMode("calibration");
      setCalibrationStep(2);
      setManualSection("peaks");
      setPickingEnabled(true);
    },
    setPickingEnabled,
    selectedPicks,
    setSelectedPicks,
    maskTools,
    plotViews,
    mapPlotViews,
    setResetKey,
    setMapResetKey,
    settingsOpen,
    changeConfigurationControls,
    showConfigurationControls,
    scxrdDraftDirty,
    setNotice,
    imageFileStep,
  });
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
        if (commands.busy || !bridge.current) {
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
  const shownLinked = linkedClicks ? linked : undefined;

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
                      linkedClicks && cake
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
    withScheduling(run, { queueIfBusy: true }),
  );
  const customInvoke = useCallback<Invoke>(
    <const A extends CommandInvocation>(...call: CheckedInvocation<A>) => {
      if (!bridge.current)
        return Promise.reject(new Error("The desktop bridge is unavailable."));
      return forwardInvoke(bridge.current, call);
    },
    [],
  );
  const customCommands = useCustomCommands(customInvoke, state);
  const customHistoryActive = settingsOpen && customActionsOpen;
  const refreshCustomCommands = customCommands.request;
  useEffect(() => {
    // Pick up edits made to the settings file outside this window.
    if (customHistoryActive) void refreshCustomCommands();
  }, [customHistoryActive, refreshCustomCommands]);
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
  const mapWindowRevision = useRef({ value: map, revision: 0 });
  if (mapWindowRevision.current.value !== map) {
    mapWindowRevision.current = {
      value: map,
      revision: mapWindowRevision.current.revision + 1,
    };
  }
  const mapWindow = useMapWindow({
    run: withScheduling(run, { queueIfBusy: true }),
    // Like native child reads, browser popup reads use the processing worker's
    // serialization rather than being dropped during a quiet main-window edit.
    request: async <const A extends CommandInvocation>(
      ...call: CheckedInvocation<A>
    ) => (bridge.current ? forwardInvoke(bridge.current, call) : undefined),
    status: {
      clicked: clickPositionReading,
      ready,
      calibrated: !!state?.calibrated,
      largeText,
      error,
      revision: state?.revision,
      mapRevision: mapWindowRevision.current.revision,
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
  const mapRefreshAttempted = useRef(false);
  const lastMapRefresh = useRef(-Infinity);
  useEffect(() => {
    if (mode !== "map" || !map?.backgroundPending) {
      mapRefreshAttempted.current = false;
      return;
    }
    if (ready && !error && !mapRefreshAttempted.current) {
      const timer = setTimeout(
        () => {
          mapRefreshAttempted.current = true;
          lastMapRefresh.current = performance.now();
          void run("map_refresh", {}, "Updating map background…");
        },
        Math.max(
          0,
          Math.ceil(
            MAP_UPDATE_INTERVAL_MS -
              (performance.now() - lastMapRefresh.current),
          ),
        ),
      );
      return () => clearTimeout(timer);
    }
  }, [mode, map?.backgroundPending, ready, error, run]);
  const detectorWindow = useDetectorWindow(
    {
      largeText,
      reading:
        mode !== "map" &&
        plotReading &&
        ["detector", "cake", "profile"].includes(plotReading.source)
          ? plotReading
          : null,
      // The detached detector shares the inspection bookmark even when the
      // main window switches to Map after docking its companion.
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
    mode !== "map" &&
    mode !== "scxrd" &&
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
    if (!ready || (!detectorInspects && mode !== "map") || !image) return;
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
    if (!ready || (!linkedClicks && mode !== "map")) return;
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
        linked: shownLinked,
        localPatternClick: linkedClicks ? localPatternClick : undefined,
        wavelength: state?.geometry.wavelength,
        onInspect: linkedClicks && ready ? inspectPattern : undefined,
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
        state.supportsBinaryPhaseGuides ? { binary: true } : {},
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
        ? [
            ...(showRings ? (calibrationPreview?.rings ?? rings) : []),
            ...(shownLinked?.contours ?? []),
          ]
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
      shownLinked,
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
  const autoCalibrateReady =
    ready &&
    !!state?.hasImage &&
    !setupDirty &&
    !advancedDirty &&
    !geometryDirty &&
    validFitDraft;
  const autoCalibrateBlocker = !state?.hasImage
    ? "Open a calibrant image first."
    : geometryDirty
      ? "Apply geometry changes on Validate before auto-calibrating."
      : setupDirty
        ? "Finish entering valid detector pixel sizes on Calibrate."
        : advancedDirty
          ? "Finish entering valid refinement options."
          : !validFitDraft
            ? "Enter valid fit parameters."
            : "";
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
      ? "Finish entering valid detector pixel sizes on Calibrate."
      : advancedDirty
        ? "Finish entering valid refinement options."
        : !validFitDraft
          ? "Enter valid fit parameters."
          : fitPoints < Math.max(1, freeFitParameters)
            ? `Select at least ${Math.max(1, freeFitParameters)} peaks for the current free parameters.`
            : "Processing…";
  const powderStatusMessage =
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
        (mode === "calibration" && calibrationStep === 1 && geometryDirty
          ? "Apply geometry changes before refining or saving."
          : null) ||
        (mode === "calibration"
          ? !state?.hasImage
            ? "Open a calibrant image to begin."
            : [
                "Check calibrant, pixel sizes, and wavelength, then click Auto-calibrate.",
                state.calibration.fitDirty
                  ? "Ring selections changed. Calibrate or refine the geometry before saving."
                  : state.calibration.rmsDegrees != null
                    ? "Inspect fitted ring alignment and RMS, then save .poni."
                    : "Inspect ring overlays. This geometry has no fitted peak residual.",
                pickingEnabled
                  ? `Pick ring ${ring}. ${state.calibration.workflow.autoIncrement ? "Ring number increases after each pick." : "Ring number stays fixed."}`
                  : "Picking is off. Move over the plots to inspect coordinates and intensity.",
              ][calibrationStep]
          : mode === "map"
            ? map
              ? map.backgroundPending
                ? "Map background update pending."
                : "Select a map cell to inspect its detector image and pattern."
              : state?.calibrated
                ? "Build a map from detector images or a folder."
                : "Load a calibration to build a map."
            : mode === "mask"
              ? `${shapeHelp[maskTools.shape]} · ${number(state?.maskedPixels ?? 0, 0)} masked`
              : canIntegrate
                ? "Ready"
                : "Load a calibration to integrate this image."));
  const statusMessage =
    mode === "scxrd"
      ? error ||
        (progress?.running
          ? processingProgressText(progress, "Single-crystal processing")
          : busy) ||
        (scxrdDraftDirty
          ? "Apply or reset the single-crystal settings draft first."
          : "") ||
        notice ||
        scxrd?.error ||
        (scxrd?.notice ? `Last action: ${scxrd.notice}` : "") ||
        (!scxrd?.frames ? "Open a rotation series." : "")
      : powderStatusMessage;
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
  const runImageControl = useMemo(
    () => withScheduling(run, { queueIfBusy: true }),
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
            {mode !== "map" && detectorWindow.detached && (
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
            {mode === "scxrd" ? (
              <SingleCrystalHistory
                data={scxrd}
                ready={ready && !scxrdDraftDirty}
                run={run}
              />
            ) : (
              <HistoryControls
                state={state}
                mode={mode}
                ready={ready}
                customActive={customHistoryActive}
                custom={customCommands}
                run={run}
              />
            )}
            <div className="navigation-group" role="group" aria-label="Project">
              {state?.projectName && (
                <div className="navigation-project" title={state.projectName}>
                  {state.projectName}
                </div>
              )}
              <Button
                className="workspace-nav project-action"
                aria-label={
                  mode === "scxrd"
                    ? "Open single-crystal recipe"
                    : "Open project"
                }
                title={
                  mode === "scxrd"
                    ? "Open single-crystal recipe · ⌘/Ctrl+O"
                    : "Open project"
                }
                disabled={!ready}
                onClick={() =>
                  mode === "scxrd"
                    ? run(
                        "scxrd_file",
                        { operation: "open" },
                        "Opening single-crystal recipe…",
                      )
                    : run("open_project", {}, "Opening project…")
                }
              >
                <FolderOpen size={20} />
              </Button>
              <Button
                className="workspace-nav project-action"
                aria-label={
                  mode === "scxrd"
                    ? "Save single-crystal recipe"
                    : "Save project"
                }
                disabled={
                  !ready ||
                  (mode === "scxrd"
                    ? !scxrd?.frames
                    : !state?.configurationLabels &&
                      !state?.hasImage &&
                      !map &&
                      !batch)
                }
                onClick={() =>
                  mode === "scxrd"
                    ? run(
                        "scxrd_file",
                        { operation: "save" },
                        "Saving single-crystal recipe…",
                      )
                    : run("save_project", {}, "Saving project…")
                }
                aria-description={
                  geometryDirty || fitEditor.dirty || integrationDraft.dirty
                    ? "Projects save applied options. Unapplied option drafts remain in this session."
                    : undefined
                }
                title={
                  mode === "scxrd"
                    ? "Save single-crystal recipe · ⌘/Ctrl+S"
                    : `${state?.projectName ? `Save ${state.projectName}` : "Save project"}${mode === "mask" ? "" : " · ⌘/Ctrl+S"}${geometryDirty || fitEditor.dirty || integrationDraft.dirty ? " · Saves applied options; unapplied drafts stay in this session" : ""}`
                }
              >
                <Save size={20} />
              </Button>
            </div>
            <AppUpdateNotice controller={appUpdate} ready={ready} />
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
          className={`workspace-stage ${configurationControlsVisible && mode !== "scxrd" ? "has-configurations" : ""}`}
        >
          {configurationControlsVisible && mode !== "scxrd" && state && (
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
              <SingleCrystalWorkspace
                active={mode === "scxrd" && !settingsOpen}
                data={scxrd}
                run={run}
                ready={ready}
                busy={!!busy}
                progress={progress}
                calibrated={!!state?.calibrated}
                invoke={bridge.current}
                reportPlot={reportPlot}
                reportClick={setScxrdClick}
                onDraftDirty={setScxrdDraftDirty}
              />
              {mode === "scxrd" ? null : mode === "map" ? (
                <MapView
                  resetKey={mapResetKey}
                  map={map}
                  progressPreview={progress?.mapPreview}
                  plotViews={mapPlotViews}
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
                  run={withScheduling(run, { queueIfBusy: true })}
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
                    className={`views-grid ${mode === "calibration" ? (calibrationStep === 1 ? "validation-views" : "image-only") : ""}`}
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
                                linked: shownLinked,
                                localImageClick: linkedClicks
                                  ? localImageClick
                                  : null,
                                onInspect: detectorInspects
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
                                  ? (calibrationPreview?.activeRing ??
                                    (calibrationStep === 2 && pickingEnabled
                                      ? ring
                                      : undefined))
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
                      {(mode === "integration" || calibrationStep === 1) && (
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
                                  shownLinked
                                    ? (radialValues(
                                        shownLinked.twoTheta,
                                        "2th_deg",
                                        state?.geometry.wavelength,
                                      )[cake.unit] ?? undefined)
                                    : undefined
                                }
                                clickedPoint={linkedClicks ? cakeClick : null}
                                activeRing={
                                  mode === "calibration"
                                    ? (calibrationPreview?.activeRing ??
                                      undefined)
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
                                  if (!linkedClicks) return;
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
                    {((pattern && calibrationStep === 1) ||
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
                              mode === "calibration"
                                ? (calibrationPreview?.activeRing ?? undefined)
                                : undefined
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
            {mode !== "map" && mode !== "scxrd" && (
              <aside
                className={`sidebar ${mode === "calibration" ? "calibration-task-panel" : ""}`}
                data-calibration-section={
                  mode === "calibration" ? calibrationStep : undefined
                }
                data-no-wheel-step={mode === "calibration" ? "" : undefined}
              >
                <div className="options-label">
                  {mode === "mask" ? "MASK OPTIONS" : "EXPERIMENT OPTIONS"}
                </div>
                {mode === "calibration" && (
                  <CalibrationWorkflowTabs
                    active={calibrationStep}
                    disabled={[
                      false,
                      !setupValid || !state?.calibrated,
                      !setupValid || !state?.hasImage,
                    ]}
                    onChange={setCalibrationStep}
                  />
                )}
                {mode === "calibration" && calibrationStep === 2 && (
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
                {mode === "calibration" && calibrationStep === 2 && (
                  <TabList
                    className="calibration-manual-tabs"
                    label="Manual calibration sections"
                    value={manualSection}
                    onChange={setManualSection}
                    options={[
                      {
                        value: "peaks" as const,
                        label: "Peaks",
                        id: "calibration-manual-peaks",
                        panelId: "calibration-task-content",
                      },
                      {
                        value: "parameters" as const,
                        label: "Parameters",
                        id: "calibration-manual-parameters",
                        panelId: "calibration-task-content",
                      },
                    ]}
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
                        <>
                          {state?.calibration.distortionFile && (
                            <div
                              className="calibration-distortion-banner"
                              role="status"
                              title={state.calibration.distortionFile}
                            >
                              <span className="calibration-distortion-banner-text">
                                Distortion:{" "}
                                <strong>
                                  {state.calibration.distortionFile
                                    .split(/[\\/]/)
                                    .at(-1)}
                                </strong>
                              </span>
                              <div className="calibration-distortion-banner-actions">
                                {state?.calibrated && (
                                  <Button
                                    type="button"
                                    variant="quiet"
                                    disabled={!ready}
                                    onClick={() => setDistortionOpen(true)}
                                  >
                                    Edit…
                                  </Button>
                                )}
                                <Button
                                  type="button"
                                  className="icon-button"
                                  aria-label="Clear active distortion"
                                  title="Clear active distortion"
                                  disabled={!ready}
                                  onClick={() => {
                                    setDistortionPreview(null);
                                    void run("distortion_file", {
                                      reset: true,
                                    });
                                  }}
                                >
                                  ×
                                </Button>
                              </div>
                            </div>
                          )}
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
                                fitEditor={fitEditor}
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
                        </>
                      )}
                      {mode === "calibration" && (
                        <>
                          {calibrationStep === 1 && (
                            <>
                              <GeometryProvenance state={state} detail />
                              {state?.calibration.distortionFile && (
                                <div
                                  className="calibration-distortion-banner"
                                  role="status"
                                  title={state.calibration.distortionFile}
                                >
                                  <span className="calibration-distortion-banner-text">
                                    Distortion:{" "}
                                    <strong>
                                      {state.calibration.distortionFile
                                        .split(/[\\/]/)
                                        .at(-1)}
                                    </strong>
                                  </span>
                                  <div className="calibration-distortion-banner-actions">
                                    <Button
                                      type="button"
                                      variant="quiet"
                                      disabled={!ready}
                                      onClick={() => setDistortionOpen(true)}
                                    >
                                      Edit…
                                    </Button>
                                    <Button
                                      type="button"
                                      className="icon-button"
                                      aria-label="Clear active distortion"
                                      title="Clear active distortion"
                                      disabled={!ready}
                                      onClick={() => {
                                        setDistortionPreview(null);
                                        void run("distortion_file", {
                                          reset: true,
                                        });
                                      }}
                                    >
                                      ×
                                    </Button>
                                  </div>
                                </div>
                              )}
                              {wavelengthHint && (
                                <section
                                  className="calibration-wavelength-hint"
                                  role="status"
                                  aria-label="Wavelength mismatch suggestion"
                                >
                                  <div className="calibration-wavelength-hint-header">
                                    <span>
                                      {wavelengthHint.suggestedWavelength !==
                                      undefined
                                        ? "Wavelength mismatch suspected"
                                        : `High residual (RMS ${wavelengthHint.currentRmsDegrees.toFixed(3)}°)`}
                                    </span>
                                    <Button
                                      type="button"
                                      className="icon-button"
                                      aria-label="Dismiss wavelength suggestion"
                                      onClick={() => setWavelengthHint(null)}
                                    >
                                      ×
                                    </Button>
                                  </div>
                                  {wavelengthHint.suggestedWavelength !==
                                  undefined ? (
                                    <>
                                      <p>
                                        Rings fit better at{" "}
                                        <strong>
                                          {wavelengthHint.suggestedWavelength.toFixed(
                                            4,
                                          )}{" "}
                                          Å
                                        </strong>{" "}
                                        (
                                        {wavelengthHint.suggestedEnergy?.toFixed(
                                          2,
                                        )}{" "}
                                        keV) — RMS{" "}
                                        {wavelengthHint.suggestedRmsDegrees?.toFixed(
                                          3,
                                        )}
                                        ° vs{" "}
                                        {wavelengthHint.currentRmsDegrees.toFixed(
                                          3,
                                        )}
                                        °.
                                      </p>
                                      <div className="calibration-wavelength-hint-actions">
                                        <Button
                                          type="button"
                                          variant="primary"
                                          disabled={!ready}
                                          onClick={() => {
                                            const wl = Number(
                                              wavelengthHint.suggestedWavelength!.toPrecision(
                                                6,
                                              ),
                                            );
                                            void run(
                                              "auto_calibrate",
                                              {
                                                ...(fitDraft ?? {}),
                                                parameters: {
                                                  ...(fitDraft?.parameters ??
                                                    {}),
                                                  wavelength: {
                                                    value: wl,
                                                    refine: false,
                                                  },
                                                },
                                              },
                                              `Auto-calibrating at ${wl} Å…`,
                                            );
                                          }}
                                        >
                                          Refit at{" "}
                                          {wavelengthHint.suggestedWavelength.toFixed(
                                            4,
                                          )}{" "}
                                          Å
                                        </Button>
                                        <Button
                                          type="button"
                                          variant="secondary"
                                          disabled={!ready}
                                          onClick={() => {
                                            const wl = Number(
                                              wavelengthHint.suggestedWavelength!.toPrecision(
                                                6,
                                              ),
                                            );
                                            void run(
                                              "calibrate",
                                              {
                                                ...(fitDraft ?? {}),
                                                restart: false,
                                                from_image: true,
                                                parameters: {
                                                  ...(fitDraft?.parameters ??
                                                    {}),
                                                  wavelength: {
                                                    value: wl,
                                                    refine: true,
                                                  },
                                                },
                                              },
                                              "Refining geometry and wavelength…",
                                            );
                                          }}
                                        >
                                          Fit wavelength
                                        </Button>
                                      </div>
                                    </>
                                  ) : (
                                    <>
                                      <p>
                                        Rings do not match cleanly at{" "}
                                        <strong>
                                          {wavelengthHint.currentWavelength.toFixed(
                                            4,
                                          )}{" "}
                                          Å
                                        </strong>
                                        . Check wavelength, calibrant, pixel
                                        size, or starting distance.
                                      </p>
                                      <div className="calibration-wavelength-hint-actions">
                                        <Button
                                          type="button"
                                          variant="primary"
                                          disabled={!ready}
                                          onClick={() => setCalibrationStep(0)}
                                        >
                                          Adjust setup
                                        </Button>
                                        <Button
                                          type="button"
                                          variant="secondary"
                                          disabled={!ready}
                                          onClick={() =>
                                            void run(
                                              "calibrate",
                                              {
                                                ...(fitDraft ?? {}),
                                                restart: false,
                                                from_image: true,
                                                parameters: {
                                                  ...(fitDraft?.parameters ??
                                                    {}),
                                                  wavelength: {
                                                    value:
                                                      wavelengthHint.currentWavelength,
                                                    refine: true,
                                                  },
                                                },
                                              },
                                              "Refining geometry and wavelength…",
                                            )
                                          }
                                        >
                                          Fit wavelength
                                        </Button>
                                      </div>
                                    </>
                                  )}
                                </section>
                              )}
                              <section className="calibration-validation-reference">
                                <label htmlFor="validation-calibrant">
                                  Calibrant
                                </label>
                                <CalibrantPicker
                                  calibration={state?.calibration}
                                  ready={ready}
                                  run={run}
                                  purpose="validation"
                                  id="validation-calibrant"
                                />
                              </section>
                            </>
                          )}
                          <div hidden={calibrationStep !== 1}>
                            <GeometryEditor
                              editor={geometryDraft}
                              ready={ready}
                              run={run}
                              embedded
                              formId="validation-geometry-form"
                              convention={validationConvention}
                              onConventionChange={setValidationConvention}
                            />
                            {state?.hasImage && state?.calibrated && (
                              <div className="calibration-rot3-action">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  disabled={!ready}
                                  title="Estimate spatial detector distortion (single or multi-configuration) and export a .spline or NeXus .h5 file."
                                  onClick={() => setDistortionOpen(true)}
                                >
                                  Distortion correction…
                                </Button>
                                <Button
                                  type="button"
                                  variant="secondary"
                                  disabled={!ready}
                                  title="Estimate in-plane detector rotation (Rotation 3) from azimuthal polarization modulation."
                                  onClick={() =>
                                    void run(
                                      "estimate_rot3",
                                      {
                                        polarization:
                                          state.calibration.polarization,
                                      },
                                      "Estimating Rotation 3 from polarization…",
                                    )
                                  }
                                >
                                  Fit Rotation 3 (polarization)
                                </Button>
                              </div>
                            )}
                          </div>
                          {calibrationStep === 2 &&
                            manualSection === "peaks" && (
                              <CalibrationPanel
                                selected={selectedPicks}
                                onSelected={setSelectedPicks}
                                onRingChange={setRing}
                                state={state}
                                ready={ready}
                                ring={ring}
                                picking={pickingEnabled}
                                automatic={automatic}
                                setAutomatic={setAutomatic}
                                run={run}
                              />
                            )}
                          <CalibrationExtras
                            state={state}
                            step={
                              calibrationStep === 2 &&
                              manualSection === "parameters"
                                ? 2
                                : calibrationStep === 1
                                  ? 1
                                  : -1
                            }
                            ready={ready}
                            run={run}
                            onDirtyChange={setAdvancedDirty}
                            fitEditor={fitEditor}
                          />
                          {calibrationStep === 2 && (
                            <div className="calibration-manual-refinement">
                              <label className="check-row">
                                <Input
                                  aria-label="Automatic refinement"
                                  type="checkbox"
                                  disabled={!ready}
                                  checked={
                                    state?.calibration.workflow
                                      ?.automaticRefinement ?? true
                                  }
                                  onChange={(e) =>
                                    run("workflow_settings", {
                                      automaticRefinement: e.target.checked,
                                    })
                                  }
                                />
                                Automatic refinement
                              </label>
                              <label
                                className="calibration-manual-rings"
                                title="Maximum number of rings used by automatic refinement"
                              >
                                Rings
                                <Input
                                  aria-label="Number of rings"
                                  type="number"
                                  min="1"
                                  max="100"
                                  step="1"
                                  key={`manual-rings-${state?.calibration.workflow?.numberOfRings ?? 15}`}
                                  defaultValue={
                                    state?.calibration.workflow
                                      ?.numberOfRings ?? 15
                                  }
                                  disabled={
                                    !ready ||
                                    !(
                                      state?.calibration.workflow
                                        ?.automaticRefinement ?? true
                                    )
                                  }
                                  onBlur={(e) => {
                                    const n = Math.round(
                                      Number(e.target.value),
                                    );
                                    if (
                                      Number.isFinite(n) &&
                                      n >= 1 &&
                                      n <= 100 &&
                                      n !==
                                        (state?.calibration.workflow
                                          ?.numberOfRings ?? 15)
                                    ) {
                                      void run("workflow_settings", {
                                        numberOfRings: n,
                                      });
                                    }
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                      e.currentTarget.blur();
                                    }
                                  }}
                                />
                              </label>
                            </div>
                          )}
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
                          runProcessing={withScheduling(run, {
                            shouldRun: () => {
                              const current = currentState.current;
                              return (
                                current?.projectName === state?.projectName &&
                                current?.configurationIndex ===
                                  state?.configurationIndex &&
                                current?.imagePath === state?.imagePath &&
                                current?.selectedImageSource ===
                                  state?.selectedImageSource
                              );
                            },
                          })}
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
                    {(calibrationStep === 2 || !!state?.hasImage) && (
                      <div className="calibration-main-action">
                        {calibrationStep === 1 && geometryDirty && (
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
                        {calibrationStep === 2 ? (
                          <>
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
                          </>
                        ) : (
                          <>
                            <Button
                              variant={
                                calibrationStep === 1 && state?.calibrated
                                  ? "secondary"
                                  : "primary"
                              }
                              className="auto-calibrate-button"
                              title={`Automatically calibrate from the image using the calibrant, wavelength, pixel sizes, and starting distance (no manual peak picking required).${!autoCalibrateReady && autoCalibrateBlocker ? ` ${autoCalibrateBlocker}` : ""}`}
                              disabled={!autoCalibrateReady}
                              onClick={() =>
                                run(
                                  "auto_calibrate",
                                  fitDraft ?? {},
                                  "Auto-calibrating detector geometry…",
                                )
                              }
                            >
                              Auto-calibrate
                            </Button>
                            {state?.calibrated && (
                              <Button
                                variant="secondary"
                                className="calibration-refine-image"
                                title={`Refine the current geometry directly against the image using Dioptrin.${!autoCalibrateReady && autoCalibrateBlocker ? ` ${autoCalibrateBlocker}` : ""}`}
                                disabled={!autoCalibrateReady}
                                onClick={() =>
                                  run(
                                    "calibrate",
                                    {
                                      ...(fitDraft ?? {}),
                                      restart: false,
                                      from_image: true,
                                    },
                                    "Refining detector geometry…",
                                  )
                                }
                              >
                                Refine
                              </Button>
                            )}
                          </>
                        )}
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
          {hdf5SourceRequest && (
            <Hdf5SourceDialog
              key={JSON.stringify(hdf5SourceRequest)}
              request={hdf5SourceRequest}
              onCancel={() => {
                setHdf5SourceRequest(undefined);
                const opener = calibrationResetOpener.current;
                requestAnimationFrame(() => opener?.focus());
              }}
              chooseFile={async (directory) => {
                const result = await bridge.current?.("choose_hdf5_companion", {
                  directory,
                });
                return result?.chosenPath;
              }}
              onOpen={(options) => {
                setHdf5SourceRequest(undefined);
                void run("open_image", options, "Opening HDF5 source…");
              }}
            />
          )}
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
              run={withCommandSuccess(run, (command) => {
                if (command === "manual_geometry") setManualGeometryOpen(false);
              })}
            />
          )}
          <DistortionDialog
            open={distortionOpen}
            onClose={() => setDistortionOpen(false)}
            state={state}
            ready={ready}
            run={run}
            preview={distortionPreview}
            onClearPreview={() => setDistortionPreview(null)}
          />
          {settingsOpen && (
            <SettingsWorkspace
              section={settingsSection}
              onSectionChange={setSettingsSection}
              integrationDraft={integrationDraft}
              onCustomActionsActiveChange={setCustomActionsOpen}
              appUpdate={appUpdate}
              customCommands={customCommands}
              state={state}
              ready={ready}
              run={run}
              largeText={largeText}
              onLargeText={setLargeText}
              patternZoom={patternZoom}
              onPatternZoom={setPatternZoom}
              showConfigurationControls={showConfigurationControls}
              onShowConfigurationControls={changeConfigurationControls}
              onClose={closeSettings}
              returnLabel={
                {
                  calibration: "Calibration",
                  mask: "Mask",
                  integration: "Integration",
                  map: "Map",
                  scxrd: "Single Crystal",
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
        <AppFooter
          mode={mode}
          settingsOpen={settingsOpen}
          correctionPreviewActive={Boolean(correctionPreview.map)}
          linkedClicks={linkedClicks}
          mainPlotReading={mainPlotReading}
          clickedReading={clickedReading}
          clickPositionReading={clickPositionReading}
          scxrdClick={scxrdClick}
          scxrdFilename={scxrd?.filename}
          scxrdFrames={scxrd?.frames ?? 0}
          imageName={state?.imageName}
          busy={Boolean(busy)}
          progressRunning={Boolean(progress?.running)}
          error={error}
          statusMessage={statusMessage}
          mapBackgroundPending={Boolean(map?.backgroundPending)}
          ready={ready}
          onRefreshMap={() =>
            void run("map_refresh", {}, "Updating map background…")
          }
          onDismissError={() => setError(null)}
          onCancelMaskSelection={maskSelection?.cancel}
          canUndoAutoMask={
            autoMaskUndoAvailable && Boolean(state?.canUndoMask)
          }
          onUndoAutoMask={() => {
            setAutoMaskUndoAvailable(false);
            void run("undo_mask", {});
          }}
          onCancelProcessing={() => {
            void bridge.current?.("cancel_refinement");
          }}
        />
      </div>
    </div>
  );
  return (
    <DetectorWindowProvider value={detectorWindow}>
      {workspace}
      {recovery.dialog}
    </DetectorWindowProvider>
  );
}
