import type { ScheduledRun } from "./workspaceCommands";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  FolderOpen,
  ChevronLeft,
  ChevronRight,
  Play,
  Settings2,
  Check,
  ImageUp,
  Link2,
  Unlink2,
} from "lucide-react";
import { CommitNumberField } from "./CommitNumberField";
import { CalibrationHelp } from "./CalibrationHelp";
import {
  RotationAxisDiagram,
  RotationDirectionIcon,
} from "./RotationAxisDiagram";
import { SingleCrystalPanelDivider } from "./SingleCrystalPanelDivider";
import { SingleCrystalModeIcon } from "./ModeIcons";
import { Button, Input, Select } from "./ui";
import { RasterView, type RasterMarker } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import { createPlotViews, detectorViewport } from "./plotViewport";
import { useCrystalDisplay } from "./useCrystalDisplay";
import { useCrystalHover } from "./useCrystalHover";
import { useCrystalClick } from "./useCrystalClick";
import type { PlotReading, ReportPlot } from "./plotReadout";
import type { Invoke, Run } from "./commandContracts";
import type { Response } from "./types";
import {
  dacEstimatePatch,
  dacEstimateSummary,
  busyFramesNote,
  excludedFramesNote,
  latticeFoundLabel,
  latticeMethod,
  maxGrains,
  mergeAngle,
  mergedNote,
  cellVolume,
  latticeMethods,
  exploratoryCrystalConfig as exploratory,
  cellMasks,
  detectorMasks,
  maskResult,
  maskSwitch,
  maskTotal,
  setupSummary,
  sharedImageRequest,
  stepPatch,
  widthFollowsStep,
  type CrystalConfig,
  type CrystalData,
  type LatticeMethod,
  type MaskKey,
} from "./singleCrystalDomain";
import "./integrationNumericFields.css";
import "./singleCrystal.css";
// Checked against Crystal::set_poni, RasterView marker placement and
// PhaseSmith reciprocal::Geometry::convert (right-handed sample rotation).
const ROTATION_AXIS_HELP =
  "The axis the crystal turns about, as seen in the image. Rotation direction is the sense of that turn: if Find lattices finds nothing, try the other direction.";
export const crystalNumber = (n: number, d = 3) =>
  Number.isFinite(n) ? n.toFixed(d) : "—";
const steps = ["Prepare masks", "Find spots", "Find lattices"] as const;
const MASK_NAMES: Record<MaskKey, { name: string; title?: string }> = {
  dac: { name: "DAC opening" },
  seat: { name: "Seat shadow" },
  diamond: { name: "Diamond spots" },
  persistent: {
    name: "Persistent pixels",
    title: "Detector flaws: pixels bright on most frames",
  },
  shared: {
    name: "Mask mode mask",
    title: "The mask drawn in Mask mode, on every frame",
  },
};
/** Setup open or closed once a series and a calibration are loaded. */
const SETUP_OPEN_KEY = "dioptas-scxrd:setup-open";
const readSetupOpen = () => {
  try {
    return localStorage.getItem(SETUP_OPEN_KEY) === "true";
  } catch {
    return false;
  }
};
const baseName = (path: string | null | undefined) =>
  path?.split(/[\\/]/).pop() ?? "";
/**
 * Single-crystal mode, rebuilt step by step after the Qt workflow: open a
 * rotation series, declare its angles and browse the frames. Processing steps
 * are added to the task panel one at a time.
 */
export function SingleCrystalWorkspace({
  active,
  data,
  run,
  ready,
  busy,
  progress,
  calibrated,
  invoke,
  reportPlot,
  reportClick,
  onDraftDirty,
}: {
  active: boolean;
  data: CrystalData | null;
  /** App's scheduled run (settings may queue behind a finishing reply). */
  run: Run;
  ready: boolean;
  busy: boolean;
  progress: Response["progress"];
  calibrated: boolean;
  invoke: Invoke | null;
  reportPlot: ReportPlot;
  reportClick: (reading: PlotReading | null) => void;
  onDraftDirty: (dirty: boolean) => void;
}) {
  const [plotViews] = useState(createPlotViews);
  const viewport = useMemo(
    () =>
      detectorViewport(
        plotViews.detector,
        JSON.stringify([data?.firstSource, data?.shape]),
      ),
    [plotViews, data?.firstSource, data?.shape[0], data?.shape[1]],
  );
  const initialized = useRef(false);
  const {
    preferences,
    setPreferences,
    limits,
    setLimits,
    log,
    setLog,
    palette,
    setPalette,
    autoLevels,
    setAutoLevels,
  } = useCrystalDisplay("raw");
  const [frameDraft, setFrameDraft] = useState("1");
  const frameCursor = useRef(data?.frame ?? 0);
  const lastImage = useRef<string | null>(null);
  useEffect(() => onDraftDirty(false), [onDraftDirty]);
  useEffect(() => {
    if (active && ready && !data && !initialized.current) {
      initialized.current = true;
      void run("scxrd_snapshot", {}, "");
    }
  }, [active, ready, !!data, run]);
  // Coming back from another mode: the processor takes over a changed Mask
  // mode mask in this request, so the shown and used mask are current.
  const wasActive = useRef(active);
  useEffect(() => {
    if (active && !wasActive.current && ready && data)
      void run("scxrd_snapshot", {}, "");
    wasActive.current = active;
  }, [active]);
  // Live scrubbing: at most one frame request is in flight; when it returns
  // only the newest wanted position is requested and the ones between are
  // dropped. While that runs, replies for older positions must not pull the
  // slider back, so the draft is resynchronised once the scrub has settled.
  const scrub = useRef({ wanted: -1, running: false });
  const [scrubSettled, setScrubSettled] = useState(0);
  useEffect(() => {
    if (scrub.current.running) return;
    frameCursor.current = data?.frame ?? 0;
    setFrameDraft(String((data?.frame ?? 0) + 1));
  }, [data?.frame, data?.firstSource, data?.frames, scrubSettled]);
  // While spots are being searched the processor sends the frame it has just
  // finished; show that instead of the selected frame.
  const live = busy ? progress?.scxrdPreview : undefined;
  const frame = live?.raster ?? data?.image;
  useEffect(() => {
    const key = frame?.bufferId ?? null;
    if (key !== lastImage.current && frame && autoLevels)
      setLimits(frame.limits ?? [0, 1]);
    lastImage.current = key;
  }, [frame, autoLevels]);
  const onHover = useCrystalHover(data, invoke, reportPlot, active);
  const click = useCrystalClick(data, invoke, reportClick);
  const frames = data?.frames ?? 0;
  // Opening a series resets the confirmation, so the lean settings are sent
  // again (nothing is sent when they already apply); with a calibration
  // present that settings reply carries the DAC mask.
  const syncSettings = (r: { ok: boolean }) => {
    if (r.ok) afterCommand.current = () => latestSetConfig.current({});
  };
  const openSeries = () =>
    void run("scxrd_load", {}, "Opening frames…", syncSettings);
  const changeFrame = (index: number) => {
    if (!data || !frames) return;
    const next = Math.max(0, Math.min(frames - 1, index));
    if (next === frameCursor.current) return;
    frameCursor.current = next;
    setFrameDraft(String(next + 1));
    const s = scrub.current;
    s.wanted = next;
    if (s.running) return;
    s.running = true;
    void (async () => {
      try {
        for (let sent = -1; sent !== s.wanted;) {
          sent = s.wanted;
          await run("scxrd_frame", { frame: sent, kind: "raw" }, "");
        }
      } finally {
        s.running = false;
        setScrubSettled((n) => n + 1);
      }
    })();
  };
  const commitFrameDraft = () => {
    const v = Number(frameDraft);
    if (Number.isInteger(v) && v >= 1 && v <= frames) changeFrame(v - 1);
    else setFrameDraft(String((data?.frame ?? 0) + 1));
  };
  // The axis vector's sign is the sense of rotation for increasing frames.
  const axisSign =
    (data?.config.axis[0] || data?.config.axis[1] || 1) < 0 ? -1 : 1;
  const [openStep, setOpenStep] = useState<number | null>(null);
  const maskIds = useId();
  /** The settings as they will be sent, including the mask defaults. */
  const config = data ? exploratory(data.config) : null;
  /** Numbers of each mask in use, from the Prepare masks report. */
  const maskCounts = data?.stages[0]?.masks;
  /** The mask whose fields are shown (at most one). */
  const [openMask, setOpenMask] = useState<MaskKey | null>(null);
  /**
   * Setup (rotation and calibration) stays open until a series and a
   * calibration are there; after that the user's choice is remembered.
   */
  const setupReady = !!data?.frames && !!data.geometry;
  const [setupOpenChoice, setSetupOpenChoice] = useState(readSetupOpen);
  const setupOpen = !setupReady || setupOpenChoice;
  const toggleSetup = () => {
    const next = !setupOpenChoice;
    setSetupOpenChoice(next);
    try {
      localStorage.setItem(SETUP_OPEN_KEY, String(next));
    } catch {
      // Not remembered (storage unavailable); the choice still applies now.
    }
  };
  /** Width per frame shown and set apart from Step. */
  const [widthSeparate, setWidthSeparate] = useState(false);
  useEffect(() => setWidthSeparate(false), [data?.firstSource]);
  const widthFollows = !!data && widthFollowsStep(data.config, widthSeparate);
  /**
   * Send changed settings. The backend remakes the DAC opening mask inside the
   * settings reply when it is the only mask, so the shown frame is never
   * without it; the measured masks wait for Run.
   */
  const setConfig = (patch: Partial<CrystalConfig>, then?: () => void) => {
    if (!data) return;
    if (!then) {
      queueConfig(patch);
      return;
    }
    const config = exploratory({ ...data.config, ...patch });
    if (JSON.stringify(config) === JSON.stringify(data.config)) then();
    else
      void run("scxrd_settings", { config }, "", (r) => {
        if (r.ok) afterCommand.current = then;
      });
  };
  // Settings changes (spin steps, wheel notches, checkboxes) never get lost
  // while a settings reply is pending: the newest wanted values wait and are
  // sent when it returns. A burst keeps everything it sent, so a reply that
  // arrives late cannot undo an earlier step.
  const latestData = useRef(data);
  latestData.current = data;
  const settingsQueue = useRef<{
    wanted: Partial<CrystalConfig> | null;
    sent: Partial<CrystalConfig>;
    running: boolean;
  }>({ wanted: null, sent: {}, running: false });
  const [stepping, setStepping] = useState(false);
  const queueConfig = (patch: Partial<CrystalConfig>) => {
    const q = settingsQueue.current;
    q.wanted = { ...(q.wanted ?? {}), ...patch };
    if (q.running) return;
    q.running = true;
    setStepping(true);
    void (async () => {
      try {
        while (q.wanted) {
          const wanted: Partial<CrystalConfig> = q.wanted;
          q.wanted = null;
          q.sent = { ...q.sent, ...wanted };
          const current = latestData.current;
          if (!current) break;
          const config = exploratory({ ...current.config, ...q.sent });
          if (JSON.stringify(config) === JSON.stringify(current.config))
            continue;
          // Queued if the previous reply has not released the app yet.
          await (run as unknown as ScheduledRun)(
            "scxrd_settings",
            { config },
            "",
            undefined,
            undefined,
            true,
          );
        }
      } finally {
        q.running = false;
        q.sent = {};
        setStepping(false);
      }
    })();
  };
  // A follow-up runs after a later render, so it calls the newest setConfig.
  // Declared before the follow-up effect below, so it is current there.
  const latestSetConfig = useRef(setConfig);
  useEffect(() => {
    latestSetConfig.current = setConfig;
  });
  // A command cannot start from inside another command's reply (the app is
  // still busy then), so a follow-up waits here until that command is done.
  const afterCommand = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (busy || !ready || !afterCommand.current) return;
    const next = afterCommand.current;
    afterCommand.current = null;
    next();
  }, [busy, ready, data?.revision, data?.config]);
  /**
   * Fit first frame start and DAC half-opening to the measured cell shadow.
   * The estimate only reports; what it determines is sent as settings, which
   * remakes the DAC mask.
   */
  const [dacNote, setDacNote] = useState<string | null>(null);
  useEffect(() => setDacNote(null), [data?.firstSource]);
  const estimateDac = () =>
    void run(
      "scxrd_edit",
      { operation: "estimate_dac" },
      "Estimating DAC opening…",
      (r) => {
        if (!r.ok || !r.dacEstimate) return;
        setDacNote(dacEstimateSummary(r.dacEstimate));
        const patch = dacEstimatePatch(r.dacEstimate);
        if (Object.keys(patch).length)
          afterCommand.current = () => latestSetConfig.current(patch);
      },
    );
  /**
   * Leave frames out of every step (or take them back), then find the spots
   * again, and the lattices too when they had been found.
   */
  const excludeFrames = (frames: number[], exclude: boolean) => {
    if (!data) return;
    const stage = data.stages[2].status === "complete" ? 2 : 1;
    void run(
      "scxrd_edit",
      { operation: "exclude_frames", frames, exclude },
      exclude ? "Excluding frames…" : "Including frames…",
      (r) => {
        if (r.ok)
          afterCommand.current = () =>
            void run(
              "scxrd_run",
              { stage, automatic: false },
              `${steps[stage]}…`,
            );
      },
    );
  };
  /** Under Find spots: busy frames to exclude, excluded frames to take back. */
  const framesNotes = (d: CrystalData) => {
    if (d.config.integration_method !== "summation") return null;
    const busy = d.busyFrames ?? [];
    const lines: [string, string, () => void][] = [];
    if (busy.length)
      lines.push([
        busyFramesNote(busy),
        "Exclude",
        () => excludeFrames(busy, true),
      ]);
    if (d.excludedFrames.length)
      lines.push([
        excludedFramesNote(d.excludedFrames),
        "Include",
        () => excludeFrames(d.excludedFrames, false),
      ]);
    return lines.map(([text, action, act]) => (
      <div
        key={action}
        className={`sc-frames-note${action === "Include" ? " sc-frames-note--excluded" : ""}`}
        role="status"
      >
        <small>{text}</small>
        <Button
          className="sc-estimate-button"
          disabled={!ready}
          title={
            action === "Exclude"
              ? "Leave these frames out of every step and find the spots again"
              : "Use these frames again and find the spots again"
          }
          onClick={act}
        >
          {action}
        </Button>
      </div>
    ));
  };
  /** Run through `stage`; a finished step is cleared first so it runs again. */
  const runTo = (stage: number, from: number, automatic: boolean) => {
    if (!data) return;
    const start = () =>
      void run(
        "scxrd_run",
        { stage, automatic },
        automatic ? "Running analysis…" : `${steps[stage]}…`,
      );
    setConfig({}, () =>
      data.stages[from]?.status === "complete"
        ? void run(
            "scxrd_edit",
            { operation: "rerun", index: from },
            "",
            (r) => {
              if (r.ok) afterCommand.current = start;
            },
          )
        : start(),
    );
  };
  const stepSummary = (stage: number) => {
    if (!data) return "";
    const state = data.stages[stage];
    if (stage === 2 && data.cells.length) {
      const kept = data.cells.filter((c) => c.kept).length;
      return `${data.cells.length} lattice${data.cells.length === 1 ? "" : "s"} · ${kept ? `${kept} kept` : "tick one"}`;
    }
    if (state.status === "attention" || state.status === "paused")
      return state.detail;
    if (state.status !== "complete") return "";
    return stage === 0
      ? state.masks
        ? (state.masks.warning ?? "")
        : state.detail
      : stage === 1
        ? `${data.trackCount} linked spots`
        : `${data.cells.length} lattice${data.cells.length === 1 ? "" : "s"}`;
  };
  const lastStage = data?.geometry ? 2 : 1;
  const analysed = !!data?.stages
    .slice(0, lastStage + 1)
    .every((stage) => stage.status === "complete");
  // Spots of the shown lattice are marked apart and drawn last (on top).
  const shownLattice = data?.shownLattice ?? null;
  const markers = useMemo<RasterMarker[]>(
    () =>
      (live?.peaks ?? data?.peaks ?? [])
        .map((p): RasterMarker => ({
          x: p.x,
          y: p.y,
          kind:
            shownLattice != null &&
            "lattice" in p &&
            p.lattice === shownLattice + 1
              ? "lattice"
              : p.flags || ("excluded" in p && p.excluded)
                ? "rejected"
                : "observed",
        }))
        .sort(
          (a, b) => Number(a.kind === "lattice") - Number(b.kind === "lattice"),
        ),
    [data?.peaks, live?.peaks, shownLattice],
  );
  useEffect(() => {
    if (!active) return;
    const key = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.closest('input,select,textarea,[contenteditable="true"],dialog')
      )
        return;
      if (!ready || !frames || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "PageUp" || e.key === "PageDown") {
        e.preventDefault();
        changeFrame(frameCursor.current + (e.key === "PageDown" ? 1 : -1));
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [active, ready, frames, data]);
  // Plain number boxes change by typing only: the wheel must not step a
  // focused one (and `data-no-wheel-steps` keeps the global wheel stepping
  // away from unfocused ones). Spin boxes step themselves (CommitNumberField).
  const workspaceRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = workspaceRef.current;
    if (!element) return;
    const wheel = (e: WheelEvent) => {
      const target = e.target;
      if (
        target instanceof HTMLInputElement &&
        target.type === "number" &&
        document.activeElement === target
      )
        e.preventDefault();
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [active]);
  const maskFields = (key: MaskKey) => {
    if (!data || !config) return null;
    switch (key) {
      case "dac":
        return (
          <>
            <CommitNumberField
              label="Half-opening"
              unit="°"
              value={config.dac_half_opening}
              onCommit={(v) => setConfig({ dac_half_opening: v })}
              step={0.5}
              positive
              max={89.9}
            />
            <div className="sc-estimate-line">
              <Button
                className="sc-estimate-button"
                disabled={!ready || !data.geometry}
                aria-label="Estimate start and half-opening from data"
                title="Estimate start and half-opening from data: fit first frame start and half-opening to the cell shadow in the frames"
                onClick={estimateDac}
              >
                Estimate
              </Button>
              {(!data.geometry || dacNote) && (
                <small className="sc-estimate-note" role="status">
                  {data.geometry ? dacNote : "Needs a calibration"}
                </small>
              )}
            </div>
          </>
        );
      case "seat":
        return (
          <>
            <CommitNumberField
              label="Below"
              unit="× lit"
              value={config.seat_threshold}
              onCommit={(v) => setConfig({ seat_threshold: v })}
              step={0.1}
              min={0.01}
              max={0.99}
            />
            <CommitNumberField
              label="Margin"
              unit="px"
              value={config.seat_guard}
              onCommit={(v) => setConfig({ seat_guard: v })}
              step={20}
              integer
              min={0}
              max={4096}
            />
          </>
        );
      case "diamond":
        return (
          <>
            <CommitNumberField
              label="Min. size"
              unit="px"
              value={config.diamond_min_size}
              onCommit={(v) => setConfig({ diamond_min_size: v })}
              step={5}
              integer
              min={1}
            />
            <CommitNumberField
              label="d tolerance"
              unit="%"
              value={config.diamond_tolerance}
              onCommit={(v) => setConfig({ diamond_tolerance: v })}
              step={0.5}
              min={0.01}
              max={20}
            />
            <CommitNumberField
              label="Level"
              unit="σ"
              value={config.diamond_level}
              onCommit={(v) => setConfig({ diamond_level: v })}
              step={1}
              min={3}
              max={50}
            />
            <CommitNumberField
              label="Margin"
              unit="px"
              value={config.diamond_margin}
              onCommit={(v) => setConfig({ diamond_margin: v })}
              step={5}
              integer
              min={0}
              max={200}
            />
          </>
        );
      case "persistent":
        return (
          <CommitNumberField
            label="Frames"
            unit="%"
            value={config.persistent_fraction}
            onCommit={(v) => setConfig({ persistent_fraction: v })}
            step={5}
            min={20}
            max={100}
          />
        );
      default:
        return null;
    }
  };
  /**
   * One mask: its switch, its name and its result on one row. The name
   * opens its fields below (closing any other); a mask without fields
   * (Mask mode mask) toggles with its name instead.
   */
  const maskRow = (key: MaskKey) => {
    if (!data || !config) return null;
    const { name, title } = MASK_NAMES[key];
    const on = !!config[maskSwitch(key)];
    const result = maskResult(key, config, maskCounts, data.sharedMask);
    const fields = maskFields(key);
    const open = openMask === key && !!fields;
    const check = (checked: boolean) => {
      setConfig({ [maskSwitch(key)]: checked } as Partial<CrystalConfig>);
      // Switching a mask on opens its fields.
      if (checked && fields) setOpenMask(key);
    };
    const resultText = result && (
      <span className="sc-mask-result">{result}</span>
    );
    return (
      <div key={key} className="sc-mask">
        {fields ? (
          <div className="sc-mask-row">
            <Input
              type="checkbox"
              aria-label={name}
              checked={on}
              onChange={(e) => check(e.target.checked)}
            />
            <Button
              variant="quiet"
              className="sc-mask-toggle"
              aria-expanded={open}
              aria-controls={`${maskIds}-${key}`}
              title={title}
              onClick={() => setOpenMask(open ? null : key)}
            >
              <ChevronRight
                size={13}
                className="sc-mask-chevron"
                aria-hidden="true"
              />
              <span className="sc-mask-name">{name}</span>
              {resultText}
            </Button>
          </div>
        ) : (
          <label className="sc-mask-row sc-mask-row--plain" title={title}>
            <Input
              type="checkbox"
              checked={on}
              onChange={(e) => check(e.target.checked)}
            />
            {/* No fields, no disclosure: the name stays in line. */}
            <span className="sc-mask-chevron" aria-hidden="true" />
            <span className="sc-mask-name">{name}</span>
            {resultText}
          </label>
        )}
        {open && (
          <div id={`${maskIds}-${key}`} className="sc-mask-fields">
            {fields}
          </div>
        )}
      </div>
    );
  };
  if (!active) return null;
  return (
    <div
      ref={workspaceRef}
      className="sc-workspace sc-workspace--lean"
      data-no-wheel-steps=""
      aria-label="Single-crystal processing workspace"
    >
      <section className="sc-detector">
        {frame ? (
          <div className="sc-raster">
            <RasterView
              raster={frame}
              viewport={viewport}
              limits={limits}
              log={log}
              palette={palette}
              busy={busy}
              markers={markers}
              mask={live ? undefined : (data?.maskImage ?? undefined)}
              maskOpacity={0.45}
              tool="pan"
              onHover={onHover}
              clickedPoint={click.clickedPoint}
              rings={click.rings}
              onInspect={click.onInspect}
            />
            <ImageIntensity
              raster={frame}
              limits={limits}
              onLimits={(v) => {
                setLimits(v);
                setAutoLevels(false);
              }}
              log={log}
              onLog={setLog}
              palette={palette}
              onPalette={setPalette}
              ready={ready}
              preferences={preferences}
              onPreferences={setPreferences}
              initialLevelsReady
              initialAutoActive={autoLevels}
              onAutoActiveChange={setAutoLevels}
              onAuto={(settings) => {
                setAutoLevels(true);
                void run("scxrd_levels", settings, "", (r) => {
                  if (r.ok && r.scxrd?.image) setLimits(r.scxrd.image.limits);
                });
              }}
            />
          </div>
        ) : (
          <div className="sc-empty">
            <SingleCrystalModeIcon size={42} />
            <Button variant="primary" disabled={!ready} onClick={openSeries}>
              <FolderOpen size={16} />
              Open series…
            </Button>
          </div>
        )}
        {!!frames && data && (
          <div className="sc-framebar" aria-label="Rotation frame navigation">
            <Button
              variant="quiet"
              aria-label="Previous rotation frame"
              disabled={!ready || data.frame === 0}
              onClick={() => changeFrame(frameCursor.current - 1)}
            >
              <ChevronLeft size={17} />
            </Button>
            <Input
              className="sc-frame-slider"
              aria-label="Rotation frame slider"
              type="range"
              min={1}
              max={frames}
              value={Math.min(Math.max(1, Number(frameDraft) || 1), frames)}
              disabled={!ready}
              onChange={(e) => changeFrame(Number(e.target.value) - 1)}
            />
            <Button
              variant="quiet"
              aria-label="Next rotation frame"
              disabled={!ready || data.frame + 1 === frames}
              onClick={() => changeFrame(frameCursor.current + 1)}
            >
              <ChevronRight size={17} />
            </Button>
            <label>
              <Input
                aria-label="Rotation frame"
                type="number"
                min={1}
                max={frames}
                value={frameDraft}
                onChange={(e) => setFrameDraft(e.target.value)}
                onBlur={commitFrameDraft}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
                disabled={!ready}
              />
              <span>/ {frames}</span>
            </label>
            <span className="sc-omega">
              ω{" "}
              {crystalNumber(
                data.config.omega_start +
                  Math.min(
                    Math.max(1, Number(frameDraft) || 1) - 1,
                    frames - 1,
                  ) *
                    data.config.omega_step,
              )}
              °
            </span>
            <Button
              variant="quiet"
              className="sc-share-frame"
              aria-label="Show frame in other modes"
              title="Show this frame in Mask, Calibration and Integration"
              disabled={!ready || !data.source}
              onClick={() => {
                const request = sharedImageRequest(data);
                if (request)
                  void run(
                    "open_image",
                    request,
                    "Showing frame in other modes…",
                  );
              }}
            >
              <ImageUp size={16} />
            </Button>
          </div>
        )}
      </section>
      <SingleCrystalPanelDivider />
      <aside className="sc-panel" aria-label="Single-crystal workflow controls">
        <section className="sc-section">
          <Button
            className="sc-open-series"
            disabled={!ready}
            onClick={openSeries}
          >
            <FolderOpen size={15} />
            Open series…
          </Button>
          {!!frames && data && (
            <p className="sc-source">
              {baseName(data.firstSource)} … {baseName(data.lastSource)}
              <br />
              {frames} frames · {data.shape[1]} × {data.shape[0]} px
            </p>
          )}
        </section>
        {!!frames && data && (
          <>
            <details className="compact-section sc-setup" open={setupOpen}>
              <summary
                aria-disabled={!setupReady || undefined}
                title={
                  setupReady
                    ? undefined
                    : "Stays open until a calibration is loaded"
                }
                onClick={(e) => {
                  e.preventDefault();
                  if (setupReady) toggleSetup();
                }}
              >
                Setup
                {!setupOpen && (
                  <span className="sc-setup-line">
                    {/* Wraps between the parts, never inside one. */}
                    {setupSummary(
                      data.config,
                      data.geometry?.wavelength ?? null,
                    )
                      .split(" · ")
                      .map((part, i) => (
                        <span key={i}>
                          {i > 0 && " · "}
                          <span>{part}</span>
                        </span>
                      ))}
                  </span>
                )}
              </summary>
              <fieldset className="sc-angles" disabled={!ready}>
                <CommitNumberField
                  label="First frame start"
                  unit="°"
                  value={data.config.omega_start}
                  onCommit={(v) => setConfig({ omega_start: v })}
                />
                <div className="sc-field-tool">
                  <CommitNumberField
                    label="Step"
                    unit="°"
                    value={data.config.omega_step}
                    onCommit={(v) =>
                      setConfig(stepPatch(data.config, v, widthSeparate))
                    }
                    positive
                  />
                  <Button
                    variant="quiet"
                    className="sc-link-button"
                    aria-pressed={!widthFollows}
                    aria-label="Set width per frame separately"
                    title={
                      widthFollows
                        ? "Width per frame follows step; click to set it separately"
                        : "Width per frame set separately; click to follow step"
                    }
                    onClick={() => {
                      if (widthFollows) setWidthSeparate(true);
                      else {
                        setWidthSeparate(false);
                        if (data.config.exposure !== data.config.omega_step)
                          setConfig({ exposure: data.config.omega_step });
                      }
                    }}
                  >
                    {widthFollows ? <Link2 size={14} /> : <Unlink2 size={14} />}
                  </Button>
                </div>
                {!widthFollows && (
                  <CommitNumberField
                    label="Width per frame"
                    unit="°"
                    value={data.config.exposure}
                    onCommit={(v) => setConfig({ exposure: v })}
                    positive
                  />
                )}
                <div className="field-label integration-number-field">
                  <span className="sc-help-label">
                    Rotation axis
                    <CalibrationHelp
                      label="Rotation axis"
                      text={ROTATION_AXIS_HELP}
                    >
                      <RotationAxisDiagram />
                    </CalibrationHelp>
                  </span>
                  <Select
                    aria-label="Rotation axis"
                    value={data.config.axis[0] ? "vertical" : "horizontal"}
                    onChange={(e) =>
                      setConfig({
                        axis:
                          e.target.value === "vertical"
                            ? [axisSign, 0, 0]
                            : [0, axisSign, 0],
                      })
                    }
                  >
                    <option value="vertical">vertical</option>
                    <option value="horizontal">horizontal</option>
                  </Select>
                </div>
                <div className="field-label integration-number-field">
                  <span>Rotation direction</span>
                  <span
                    className="segmented sc-direction"
                    role="group"
                    aria-label="Rotation direction"
                  >
                    {([-1, 1] as const).map((sign) => (
                      <Button
                        key={sign}
                        aria-pressed={axisSign === sign}
                        aria-label={
                          (sign > 0 ? "Counterclockwise" : "Clockwise") +
                          (data.config.axis[0]
                            ? ", seen from above"
                            : ", seen from the right")
                        }
                        title={
                          (sign > 0 ? "Counterclockwise" : "Clockwise") +
                          (data.config.axis[0]
                            ? ", seen from above"
                            : ", seen from the right")
                        }
                        onClick={() =>
                          setConfig({
                            axis: data.config.axis[0]
                              ? [sign, 0, 0]
                              : [0, sign, 0],
                          })
                        }
                      >
                        <RotationDirectionIcon
                          sign={sign}
                          horizontal={!data.config.axis[0]}
                        />
                      </Button>
                    ))}
                  </span>
                </div>
              </fieldset>
              <div className="sc-actions" aria-label="Calibration">
                <Button
                  disabled={!ready}
                  onClick={() =>
                    void run(
                      "scxrd_file",
                      { operation: "calibration" },
                      "Loading calibration…",
                      syncSettings,
                    )
                  }
                >
                  Load .poni…
                </Button>
                <Button
                  disabled={!ready || !calibrated}
                  onClick={() =>
                    void run(
                      "scxrd_file",
                      { operation: "use_calibration" },
                      "",
                      syncSettings,
                    )
                  }
                >
                  Use calibration
                </Button>
                <span>
                  {data.geometry
                    ? `λ ${crystalNumber(data.geometry.wavelength, 4)} Å`
                    : "No calibration"}
                </span>
              </div>
            </details>
            {busy && progress?.running ? (
              <div className="sc-working" role="status">
                {progress.label ?? "Working…"}
                {live && ` · frame ${live.frame + 1} · ${live.spots} spots`}
                {!!progress.total && (
                  <progress max={progress.total} value={progress.current} />
                )}
                <Button onClick={() => void invoke?.("cancel_refinement", {})}>
                  Cancel
                </Button>
              </div>
            ) : (
              <Button
                variant="primary"
                disabled={!ready}
                onClick={() => runTo(lastStage, 0, true)}
              >
                <Play size={15} />
                {analysed ? "Restart analysis" : "Start analysis"}
              </Button>
            )}
            <ol className="sc-step-list" aria-label="Analysis steps">
              {steps.map((name, stage) => (
                <li key={name}>
                  <div className="sc-step-row">
                    <Button
                      variant="quiet"
                      aria-label={`Run ${name}`}
                      title="Run up to this step"
                      disabled={!ready || (stage === 2 && !data.geometry)}
                      onClick={() => runTo(stage, stage, false)}
                    >
                      {data.stages[stage].status === "complete" ? (
                        <Check size={14} />
                      ) : (
                        <Play size={14} />
                      )}
                    </Button>
                    <span className="sc-step-name">
                      {name}
                      <small
                        className={
                          data.stages[stage].status === "attention" ||
                          // Masks were made but disagree with the data.
                          (stage === 0 && !!maskCounts?.warning)
                            ? "sc-step-problem"
                            : undefined
                        }
                      >
                        {stepSummary(stage) ||
                          (!data.geometry &&
                          (stage === 2 ||
                            (stage === 0 &&
                              config!.cell_masks_enabled &&
                              (config!.dac_enabled || config!.diamond_enabled)))
                            ? "Needs a calibration"
                            : "")}
                      </small>
                    </span>
                    {data.stages[stage].status === "complete" && (
                      <span
                        className="sc-step-time"
                        title={
                          stage === 0 && maskTotal(maskCounts)
                            ? `${maskTotal(maskCounts)} of all pixels in the scan`
                            : undefined
                        }
                      >
                        {stage === 0 && maskCounts
                          ? `${maskTotal(maskCounts)!.replace(" masked", "")} · `
                          : ""}
                        {data.stages[stage].seconds.toFixed(1)} s
                      </span>
                    )}
                    <Button
                      variant="quiet"
                      aria-label={`${name} settings`}
                      aria-expanded={openStep === stage}
                      onClick={() =>
                        setOpenStep(openStep === stage ? null : stage)
                      }
                    >
                      <Settings2 size={14} />
                    </Button>
                  </div>
                  {stage === 1 && framesNotes(data)}
                  {openStep === stage && (
                    <fieldset
                      className="sc-angles"
                      // Open while queued settings replies run (spin steps).
                      disabled={!ready && !stepping}
                    >
                      {stage === 0 && (
                        <>
                          <div
                            className="sc-mask-group"
                            role="group"
                            aria-label="Diamond anvil cell masks"
                          >
                            {/* Both headings start at the same x; the cell
                                switch sits at the end of its heading. */}
                            <label className="sc-mask-head">
                              Diamond anvil cell
                              <Input
                                type="checkbox"
                                checked={config!.cell_masks_enabled}
                                onChange={(e) =>
                                  setConfig({
                                    cell_masks_enabled: e.target.checked,
                                  })
                                }
                              />
                            </label>
                            {config!.cell_masks_enabled &&
                              cellMasks.map((key) => maskRow(key))}
                          </div>
                          <div
                            className="sc-mask-group"
                            role="group"
                            aria-label="Detector masks"
                          >
                            <div className="sc-mask-head">Detector</div>
                            {detectorMasks.map((key) => maskRow(key))}
                          </div>
                        </>
                      )}
                      {stage === 1 && (
                        <>
                          <CommitNumberField
                            label="Threshold"
                            unit="σ"
                            value={data.config.threshold}
                            onCommit={(v) => setConfig({ threshold: v })}
                            step={0.5}
                            min={1}
                            max={100}
                          />
                          <CommitNumberField
                            label="Minimum area"
                            unit="px"
                            value={data.config.min_pixels}
                            onCommit={(v) => setConfig({ min_pixels: v })}
                            step={1}
                            integer
                            min={1}
                            max={1000}
                          />
                          <CommitNumberField
                            label="Link radius"
                            unit="px"
                            value={data.config.link_radius}
                            onCommit={(v) => setConfig({ link_radius: v })}
                            step={0.5}
                            min={0.1}
                            max={30}
                          />
                        </>
                      )}
                      {stage === 2 && (
                        <>
                          <div className="field-label integration-number-field sc-wide-choice">
                            <span>Search</span>
                            <Select
                              aria-label="Lattice search"
                              value={latticeMethod(data.config)}
                              onChange={(e) =>
                                setConfig({
                                  lattice_method: e.target
                                    .value as LatticeMethod,
                                })
                              }
                            >
                              {latticeMethods.map((m) => (
                                <option key={m.value} value={m.value}>
                                  {m.label}
                                </option>
                              ))}
                            </Select>
                          </div>
                          <CommitNumberField
                            label="Max. grains"
                            value={maxGrains(data.config)}
                            onCommit={(v) => setConfig({ max_grains: v })}
                            step={1}
                            integer
                            min={1}
                            max={20}
                          />
                          <CommitNumberField
                            label="Merge within"
                            unit="°"
                            value={mergeAngle(data.config)}
                            onCommit={(v) => setConfig({ merge_angle: v })}
                            step={0.1}
                            min={0}
                            max={5}
                          />
                          <CommitNumberField
                            label="Shortest vector"
                            unit="Å"
                            value={data.config.min_cell}
                            onCommit={(v) => setConfig({ min_cell: v })}
                            positive
                          />
                          <CommitNumberField
                            label="Longest vector"
                            unit="Å"
                            value={data.config.max_cell}
                            onCommit={(v) => setConfig({ max_cell: v })}
                            positive
                          />
                          <CommitNumberField
                            label="Tolerance"
                            unit="Å⁻¹"
                            value={data.config.tolerance}
                            onCommit={(v) => setConfig({ tolerance: v })}
                            positive
                          />
                        </>
                      )}
                    </fieldset>
                  )}
                </li>
              ))}
            </ol>
            {data.cells.length > 0 && (
              <section className="sc-section sc-lattices" aria-label="Lattices">
                <div className="sc-mask-heading">
                  <span>Lattices</span>
                </div>
                {data.cells.map((cell, i) => {
                  const shown = shownLattice === i;
                  const share = Math.round((100 * cell.indexed) / cell.total);
                  return (
                    <div key={i} className="sc-lattice">
                      <div className="sc-mask-row">
                        <Input
                          type="checkbox"
                          aria-label={`Keep lattice ${i + 1}`}
                          title="Keep for the following steps"
                          checked={!!cell.kept}
                          disabled={!ready}
                          onChange={(e) =>
                            void run(
                              "scxrd_edit",
                              {
                                operation: "keep",
                                index: i,
                                keep: e.target.checked,
                              },
                              "",
                            )
                          }
                        />
                        <Button
                          variant="quiet"
                          className="sc-mask-toggle sc-lattice-toggle"
                          aria-pressed={shown}
                          title="Mark its spots on the image"
                          disabled={!ready}
                          onClick={() =>
                            void run(
                              "scxrd_edit",
                              shown
                                ? { operation: "show" }
                                : { operation: "show", index: i },
                              "",
                            )
                          }
                        >
                          <span className="sc-lattice-cell">
                            <span className="sc-mask-name">
                              {cell.parameters
                                .slice(0, 3)
                                .map((n) => crystalNumber(n))
                                .join(" · ")}{" "}
                              Å
                            </span>
                            <span className="sc-lattice-angles">
                              {cell.parameters
                                .slice(3)
                                .map((n) => crystalNumber(n, 2))
                                .join(" · ")}
                              ° · {Math.round(cellVolume(cell.parameters))} Å³
                            </span>
                          </span>
                          <span className="sc-mask-result sc-lattice-spots">
                            {cell.indexed} · {share} %
                            <span>{latticeFoundLabel(cell.found)}</span>
                          </span>
                        </Button>
                      </div>
                      {shown && (
                        <div className="sc-lattice-details">
                          {cell.indexed}/{cell.total} spots · withheld{" "}
                          {cell.validation}, rms {cell.rms.toFixed(4)} Å⁻¹
                          {cell.merged && ` · ${mergedNote(cell.merged)}`}
                        </div>
                      )}
                    </div>
                  );
                })}
              </section>
            )}
          </>
        )}
        {!frames && busy && progress?.running && (
          <div className="sc-working" role="status">
            {progress.label ?? "Working…"}
            {!!progress.total && (
              <progress max={progress.total} value={progress.current} />
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
