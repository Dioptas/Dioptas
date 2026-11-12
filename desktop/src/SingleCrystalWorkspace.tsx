import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  useLayoutEffect,
} from "react";
import {
  FolderOpen,
  ChevronLeft,
  ChevronRight,
  Check,
  Circle,
  AlertTriangle,
  Play,
  RotateCcw,
  ScanLine,
  Save,
} from "lucide-react";
import { CommitNumberField } from "./CommitNumberField";
import { Button, Input, Select } from "./ui";
import { RasterView, type RasterMarker } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import { createPlotViews, detectorViewport } from "./plotViewport";
import { useCrystalDisplay } from "./useCrystalDisplay";
import {
  SingleCrystalStages,
  type CrystalStageProps,
} from "./SingleCrystalStages";
import { useCrystalHover } from "./useCrystalHover";
import type { ReportPlot } from "./plotReadout";
import type { Invoke, Run } from "./commandContracts";
import type { Palette, Response } from "./types";
import {
  crystalDefaults,
  crystalConfigError,
  crystalSteps,
  nextCrystalStep,
  type CrystalConfig,
  type CrystalData,
  type CrystalFileOperation,
  type CrystalImageKind,
} from "./singleCrystalDomain";
import "./singleCrystal.css";
export const crystalNumber = (n: number, d = 3) =>
  Number.isFinite(n) ? n.toFixed(d) : "—";
const hints = [
  "Load a rotation scan, then confirm its acquisition and detector geometry.",
  "Remove the slowly varying omega background for peak positions. Intensities always use original counts.",
  "Detect peaks and link neighbouring frames into rotation tracks. Inspect and exclude unwanted tracks.",
  "Compare position-supported reduced primitive cells. Select the sample lattice when candidates are ambiguous.",
  "Validate predicted positions against observations. Keep the detector calibration fixed, or opt into refinement.",
  "Integrate complete measured tracks from original counts, with a local background and propagated counting errors.",
  "Merge equivalent observations, inspect symmetry evidence and optionally fit a robust omega scale from repeated families.",
  "Optional element-only candidate search in an explicitly supplied space group. This is candidate assessment, not a final structure refinement.",
  "Export signed observations, usable HKLF4 intensities and a reproducible recipe. Source files are never modified.",
];
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
  onDraftDirty,
}: {
  active: boolean;
  data: CrystalData | null;
  run: Run;
  ready: boolean;
  busy: boolean;
  progress: Response["progress"];
  calibrated: boolean;
  invoke: Invoke | null;
  reportPlot: ReportPlot;
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
  const contentRef = useRef<HTMLDivElement>(null);
  const [moreBelow, setMoreBelow] = useState(false);
  const initialized = useRef(false);
  const [resetToken, setResetToken] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>(
    {},
  );
  const onValidation = useCallback(
    (field: string, error: string | null) =>
      setFieldErrors((previous) =>
        previous[field] === error ? previous : { ...previous, [field]: error },
      ),
    [],
  );
  const [step, setStep] = useState(0),
    [draft, setDraft] = useState<CrystalConfig>(
      data?.config ?? crystalDefaults,
    );
  const imageKind = data?.previewKind || "raw";
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
  } = useCrystalDisplay(imageKind);
  const [observed, setObserved] = useState(true),
    [predicted, setPredicted] = useState(true),
    [rejected, setRejected] = useState(false),
    [selectedTrack, setSelectedTrack] = useState<number | null>(null),
    [maskPicking, setMaskPicking] = useState(false),
    [maskHover, setMaskHover] = useState<{ x: number; y: number } | null>(null),
    [corner, setCorner] = useState<{ x: number; y: number } | null>(null);
  const [frameDraft, setFrameDraft] = useState("1"),
    [frameStep, setFrameStep] = useState(1);
  const frameCursor = useRef(data?.frame ?? 0);
  useEffect(() => {
    frameCursor.current = data?.frame ?? 0;
  }, [data?.firstSource, data?.frames]);
  const lastImage = useRef<string | null>(null);
  const configKey = JSON.stringify(data?.config),
    dirty = !!data && JSON.stringify(draft) !== configKey;
  useEffect(() => {
    if (data?.config) setDraft(data.config);
  }, [configKey]);
  useEffect(() => {
    if (active && ready && !data && !initialized.current) {
      initialized.current = true;
      void run("scxrd_snapshot", {}, "");
    }
  }, [active, ready, !!data, run]);
  useEffect(() => {
    setFrameDraft(String((data?.frame ?? 0) + 1));
  }, [data?.frame]);
  useEffect(() => {
    const frame = data?.image;
    const key = frame ? `${imageKind}:${frame.bufferId}` : null;
    if (key !== lastImage.current && frame && autoLevels)
      setLimits(frame.limits ?? [0, 1]);
    lastImage.current = key;
  }, [data?.image, imageKind, autoLevels]);
  useEffect(() => {
    if (data?.error) {
      const i = data.stages.findIndex(
        (s) => s.status === "attention" || s.status === "paused",
      );
      if (i >= 0) setStep(i + 1);
    }
  }, [data?.error, data?.revision]);
  useLayoutEffect(() => {
    const element = contentRef.current;
    if (!element || !active) return;
    const update = () =>
      setMoreBelow(
        element.scrollHeight - element.scrollTop - element.clientHeight > 12,
      );
    const observer = new ResizeObserver(update);
    observer.observe(element);
    for (const child of element.children) observer.observe(child);
    element.addEventListener("scroll", update, { passive: true });
    update();
    return () => {
      observer.disconnect();
      element.removeEventListener("scroll", update);
    };
  }, [active, step, data?.revision, dirty, resetToken]);
  const onHover = useCrystalHover(data, invoke, reportPlot, active);
  const frame = data?.image;
  const configError = crystalConfigError(draft),
    fieldError = Object.values(fieldErrors).find(Boolean),
    valid = !configError && !fieldError;
  useEffect(() => onDraftDirty(dirty || !valid), [dirty, valid, onDraftDirty]);

  const canProcess =
    ready &&
    !!data?.frames &&
    !dirty &&
    !!data?.config.confirmed &&
    !!data?.geometry &&
    valid;
  const canRunCurrent =
    ready &&
    !!data?.frames &&
    !dirty &&
    !!data?.config.confirmed &&
    valid &&
    (step <= 2 || !!data?.geometry);
  const coreComplete =
    !!data?.frames &&
    data.stages.slice(0, 6).every((stage) => stage.status === "complete");
  const searchReady = !!data?.config.elements.trim();
  const reviewExport =
    coreComplete && (!searchReady || data?.stages[6].status === "complete");
  const update: CrystalStageProps["update"] = (key, value) =>
    setDraft((old) => ({ ...old, [key]: value }));
  const file = (operation: CrystalFileOperation) =>
    void run(
      "scxrd_file",
      { operation },
      operation === "open"
        ? "Verifying recipe sources…"
        : operation === "calibration"
          ? "Loading SCXRD calibration…"
          : "Saving…",
    );
  const changeFrame = (
    index: number,
    kind: CrystalImageKind = data?.previewKind || "raw",
  ) => {
    if (!data || index < 0 || index >= data.frames) return;
    frameCursor.current = index;
    void run("scxrd_frame", { frame: index, kind }, "");
  };
  useEffect(() => {
    if (!active) return;
    const key = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.closest('input,select,textarea,[contenteditable="true"],dialog')
      )
        return;
      if (e.key === "Escape" && maskPicking) {
        e.preventDefault();
        e.stopPropagation();
        setMaskPicking(false);
        setCorner(null);
        return;
      }
      if (!ready || !data?.frames || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "PageUp" || e.key === "PageDown") {
        e.preventDefault();
        changeFrame(
          Math.max(
            0,
            Math.min(
              data.frames - 1,
              frameCursor.current + (e.key === "PageDown" ? 1 : -1) * frameStep,
            ),
          ),
        );
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [
    active,
    ready,
    data?.frame,
    data?.frames,
    data?.previewKind,
    frameStep,
    maskPicking,
  ]);
  const runStage = (automatic: boolean) => {
    const stage = automatic
      ? searchReady
        ? 6
        : 5
      : Math.max(0, Math.min(6, step - 1));
    void run(
      "scxrd_run",
      { stage, automatic },
      automatic
        ? "Processing to the next decision…"
        : `Running ${crystalSteps[step]}…`,
      (result) => {
        if (result.ok && result.scxrd && !result.scxrd.error)
          setStep(
            stage === 6
              ? 7
              : automatic
                ? nextCrystalStep(result.scxrd)
                : Math.min(8, step + 1),
          );
      },
    );
  };
  const markers = useMemo<RasterMarker[]>(() => {
    const result: RasterMarker[] =
      data?.peaks
        .filter((p) => (p.flags || p.excluded ? rejected : observed))
        .map((p) => ({
          x: p.x,
          y: p.y,
          kind:
            p.track === selectedTrack
              ? "selected"
              : p.flags || p.excluded
                ? "rejected"
                : "observed",
        })) ?? [];
    if (predicted)
      result.push(
        ...(data?.predictions ?? []).map((p) => ({
          x: p.x,
          y: p.y,
          kind: "predicted" as const,
        })),
      );
    if (corner) result.push({ ...corner, kind: "selected" });
    return result;
  }, [
    data?.peaks,
    observed,
    rejected,
    selectedTrack,
    corner,
    predicted,
    data?.predictions,
  ]);
  if (!active) return null;
  return (
    <div
      className="sc-workspace"
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
              regions={[
                ...(data?.mask ?? []).map((bounds) => ({ bounds })),
                ...(corner && maskHover
                  ? [
                      {
                        bounds: [
                          Math.min(corner.x, maskHover.x),
                          Math.min(corner.y, maskHover.y),
                          Math.max(corner.x, maskHover.x),
                          Math.max(corner.y, maskHover.y),
                        ] as [number, number, number, number],
                        preview: true,
                      },
                    ]
                  : []),
              ]}
              tool={maskPicking ? "pick" : "pan"}
              onHover={(p) => {
                if (maskPicking) setMaskHover(p ? { x: p.x, y: p.y } : null);
                onHover(p);
              }}
              onPick={(point) => {
                if (!corner) {
                  setCorner(point);
                  return;
                }
                const w = data!.shape[1],
                  h = data!.shape[0];
                const bounds: [number, number, number, number] = [
                  Math.max(0, Math.floor(Math.min(corner.x, point.x))),
                  Math.max(0, Math.floor(Math.min(corner.y, point.y))),
                  Math.min(w, Math.ceil(Math.max(corner.x, point.x)) + 1),
                  Math.min(h, Math.ceil(Math.max(corner.y, point.y)) + 1),
                ];
                setCorner(null);
                void run(
                  "scxrd_edit",
                  { operation: "mask", bounds },
                  "Applying exclusion…",
                );
              }}
              onInspect={(point) => {
                if (maskPicking || !data?.peaks.length) return;
                const nearest = data.peaks.reduce((a, b) =>
                  Math.hypot(a.x - point.x, a.y - point.y) <
                  Math.hypot(b.x - point.x, b.y - point.y)
                    ? a
                    : b,
                );
                if (Math.hypot(nearest.x - point.x, nearest.y - point.y) < 10) {
                  setSelectedTrack(nearest.track);
                  if (!data.tracks.some((t) => t.id === nearest.track))
                    void run(
                      "scxrd_table",
                      {
                        kind: "tracks",
                        offset: Math.floor(nearest.track / 200) * 200,
                      },
                      "",
                    );
                  if (step !== 4 && step !== 5) setStep(2);
                }
              }}
            />
            <ImageIntensity
              key={imageKind}
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
            <ScanLine size={42} />
            <h2>Single-crystal XRD</h2>
            <p>
              Start with a rotation scan.
              <br />
              Inspect each step, or run to the next decision.
            </p>
            <Button
              variant="primary"
              disabled={!ready}
              onClick={() =>
                void run("scxrd_load", {}, "Verifying rotation frames…")
              }
            >
              <FolderOpen size={16} />
              Load frames…
            </Button>
            <Button
              variant="quiet"
              disabled={!ready}
              onClick={() => file("open")}
            >
              Open a saved recipe…
            </Button>
          </div>
        )}
        {!!data?.frames && (
          <div className="sc-framebar" aria-label="Rotation frame navigation">
            <Button
              variant="quiet"
              aria-label="Previous rotation frame"
              disabled={!ready || data.frame === 0}
              onClick={() =>
                changeFrame(Math.max(0, frameCursor.current - frameStep))
              }
            >
              <ChevronLeft size={17} />
            </Button>
            <label>
              Frame{" "}
              <Input
                aria-label="Rotation frame"
                type="number"
                min={1}
                max={data.frames}
                value={frameDraft}
                onChange={(e) => setFrameDraft(e.target.value)}
                onBlur={() => {
                  const v = Number(frameDraft);
                  if (
                    Number.isInteger(v) &&
                    v >= 1 &&
                    v <= data.frames &&
                    v !== data.frame + 1
                  )
                    changeFrame(v - 1);
                  else setFrameDraft(String(data.frame + 1));
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
                disabled={!ready}
              />
              <span>/ {data.frames}</span>
            </label>
            <Button
              variant="quiet"
              aria-label="Next rotation frame"
              disabled={!ready || data.frame + 1 === data.frames}
              onClick={() =>
                changeFrame(
                  Math.min(data.frames - 1, frameCursor.current + frameStep),
                )
              }
            >
              <ChevronRight size={17} />
            </Button>
            <CommitNumberField
              label="Frame step"
              value={frameStep}
              onCommit={setFrameStep}
              integer
              min={1}
              max={data.frames}
            />
            <span className="sc-omega">
              ω{" "}
              {crystalNumber(
                data.config.omega_start +
                  data.frame * data.config.omega_step +
                  data.config.exposure / 2,
              )}
              °
            </span>
            <label className="sc-image-kind">
              <span className="visually-hidden">Displayed rotation image</span>
              <Select
                aria-label="Displayed rotation image"
                disabled={!ready}
                value={data.previewKind}
                onChange={(e) =>
                  changeFrame(data.frame, e.target.value as CrystalImageKind)
                }
              >
                <option value="raw">Original counts</option>
                <option
                  value="background"
                  disabled={
                    !data.config.background ||
                    data.stages[0].status !== "complete"
                  }
                >
                  Background · positions
                </option>
                <option
                  value="corrected"
                  disabled={
                    !data.config.background ||
                    data.stages[0].status !== "complete"
                  }
                >
                  Subtracted · positions
                </option>
              </Select>
            </label>
          </div>
        )}
        {!!data?.frames && (
          <div className="sc-marker-legend" aria-label="Marker legend">
            <span className="sc-observed-key">○ Observed</span>
            <span className="sc-predicted-key">+ Predicted</span>
            <span>○ Flagged / excluded</span>
            <span>White: selected track</span>
          </div>
        )}
      </section>
      <aside className="sc-panel" aria-label="Single-crystal workflow controls">
        <nav
          className="sc-steps"
          role="tablist"
          aria-label="Single-crystal stages"
        >
          {crystalSteps.map((name, i) => {
            const status =
              i === 0
                ? data?.config.confirmed
                  ? "complete"
                  : "pending"
                : i === 8
                  ? data?.exported
                    ? "complete"
                    : "pending"
                  : (data?.stages[i - 1]?.status ?? "pending");
            return (
              <Button
                key={name}
                role="tab"
                id={`sc-tab-${i}`}
                aria-controls="sc-content"
                aria-selected={step === i}
                className={step === i ? "sc-selected" : ""}
                tabIndex={step === i ? 0 : -1}
                onKeyDown={(e) => {
                  const offset =
                    e.key === "ArrowRight" || e.key === "ArrowDown"
                      ? 1
                      : e.key === "ArrowLeft" || e.key === "ArrowUp"
                        ? -1
                        : 0;
                  if (offset || e.key === "Home" || e.key === "End") {
                    e.preventDefault();
                    e.stopPropagation();
                    const next =
                      e.key === "Home"
                        ? 0
                        : e.key === "End"
                          ? 8
                          : (i + offset + 9) % 9;
                    setStep(next);
                    document.getElementById(`sc-tab-${next}`)?.focus();
                  }
                }}
                onClick={() => {
                  setStep(i);
                  setMaskPicking(false);
                  setCorner(null);
                }}
                title={`${name}: ${status}`}
              >
                <span className={`sc-stage-icon sc-stage-icon--${status}`}>
                  {status === "complete" ? (
                    <Check size={13} />
                  ) : status === "attention" || status === "paused" ? (
                    <AlertTriangle size={13} />
                  ) : (
                    <Circle size={10} />
                  )}
                </span>
                {name}
              </Button>
            );
          })}
        </nav>
        <div
          ref={contentRef}
          className="sc-content"
          id="sc-content"
          role="tabpanel"
          aria-labelledby={`sc-tab-${step}`}
          tabIndex={0}
        >
          <p className="sc-hint">{hints[step]}</p>
          {data?.error && (
            <div className="sc-attention" role="alert">
              <strong>
                {data.stages[2].status === "attention" && data.cells.length
                  ? "Review cell choice"
                  : data.stages.some((stage) => stage.status === "paused")
                    ? "Processing stopped"
                    : "Stage needs attention"}
              </strong>
              <p>{data.error}</p>
            </div>
          )}
          {data?.notice && step === 0 && (
            <p className="sc-note">{data.notice}</p>
          )}
          <SingleCrystalStages
            key={resetToken}
            {...{
              step,
              setStep,
              data,
              run,
              ready,
              calibrated,
              draft,
              update,
              file,
              changeFrame,
              observed,
              setObserved,
              predicted,
              setPredicted,
              rejected,
              setRejected,
              selectedTrack,
              setSelectedTrack,
              maskPicking,
              setMaskPicking,
              corner,
              setCorner,
              onValidation,
            }}
          />
          {step > 0 &&
            step < 8 &&
            data?.stages[step - 1]?.status === "complete" && (
              <p className="sc-stage-result">
                <Check size={14} />
                {data.stages[step - 1].detail}
              </p>
            )}
        </div>
        {moreBelow && (
          <Button
            className="sc-scroll-cue"
            variant="quiet"
            onClick={() =>
              contentRef.current?.scrollBy({
                top: contentRef.current.clientHeight * 0.65,
                behavior: "smooth",
              })
            }
          >
            More controls below ↓
          </Button>
        )}
        <div className="sc-task-footer">
          {(dirty || !valid) && (
            <div className="sc-draft" role="status">
              <span>
                {valid
                  ? "Unapplied settings · dependent results will be invalidated."
                  : (configError ??
                    fieldError ??
                    "Check the processing settings.")}
              </span>
              <div className="sc-actions">
                <Button
                  variant="primary"
                  disabled={!ready || !valid}
                  onClick={() =>
                    void run(
                      "scxrd_settings",
                      { config: draft },
                      "Applying single-crystal settings…",
                    )
                  }
                >
                  Apply settings
                </Button>
                <Button
                  variant="quiet"
                  disabled={!ready}
                  onClick={() => {
                    setDraft(data?.config ?? crystalDefaults);
                    setFieldErrors({});
                    setResetToken((v) => v + 1);
                  }}
                >
                  Reset draft
                </Button>
              </div>
            </div>
          )}
          {busy ? (
            <div className="sc-working" role="status">
              {progress?.running
                ? (progress.label ?? "Processing…")
                : "Updating workspace…"}
              {!!progress?.running &&
                !!progress?.total &&
                progress.total > 0 && (
                  <progress max={progress.total} value={progress.current} />
                )}
              {progress?.running && (
                <span>Completed stages will be kept if you stop.</span>
              )}
            </div>
          ) : (
            <>
              {step > 0 && step < 8 && (
                <div className="sc-actions">
                  <Button
                    variant="secondary"
                    disabled={!canRunCurrent}
                    onClick={() => runStage(false)}
                  >
                    <Play size={14} />
                    Run {crystalSteps[step].toLowerCase()}
                  </Button>
                  {data?.stages[step - 1]?.status === "complete" && (
                    <Button
                      variant="quiet"
                      disabled={!ready || dirty}
                      title="Invalidate this stage and all dependent results"
                      onClick={() =>
                        void run(
                          "scxrd_edit",
                          { operation: "rerun", index: step - 1 },
                          "Preparing stage rerun…",
                        )
                      }
                    >
                      <RotateCcw size={14} />
                      Clear stage and later results
                    </Button>
                  )}
                </div>
              )}
              <Button
                variant="primary"
                className="sc-auto"
                data-testid="sc-primary-action"
                disabled={
                  step === 8 ? !ready || !data?.frames || dirty : !canProcess
                }
                onClick={() =>
                  step === 8
                    ? file("save")
                    : reviewExport
                      ? setStep(8)
                      : runStage(true)
                }
              >
                {step === 8 ? <Save size={16} /> : <Play size={16} />}
                {step === 8
                  ? "Save recipe…"
                  : reviewExport
                    ? "Review and export"
                    : "Run to next decision"}
              </Button>
              {!canProcess && step !== 8 && (
                <p className="sc-note">
                  {dirty
                    ? "Apply or reset the settings draft first."
                    : !data?.frames
                      ? "Load frames to begin."
                      : !data.config.confirmed
                        ? "Confirm acquisition settings in Frames."
                        : !data.geometry
                          ? "Background and peaks can run now. Load a PONI calibration for cell finding or automatic processing."
                          : "Wait for processing to finish."}
                </p>
              )}
            </>
          )}
          <span className="sc-engine">
            {data?.engine ?? "Rust · PhaseSmith"}
          </span>
        </div>
      </aside>
    </div>
  );
}
