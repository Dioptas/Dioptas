import { useEffect, useMemo, useRef, useState } from "react";
import {
  FolderOpen,
  ChevronLeft,
  ChevronRight,
  Play,
  Settings2,
  Check,
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
import type { CrystalConfig, CrystalData } from "./singleCrystalDomain";
import "./integrationNumericFields.css";
import "./singleCrystal.css";
// Checked against Crystal::set_poni, RasterView marker placement and
// PhaseSmith reciprocal::Geometry::convert (right-handed sample rotation).
const ROTATION_AXIS_HELP =
  "The axis the crystal turns about, as seen in the image. Rotation direction is the sense of that turn: if Find lattices finds nothing, try the other direction.";
export const crystalNumber = (n: number, d = 3) =>
  Number.isFinite(n) ? n.toFixed(d) : "—";
/**
 * The flexible measured-track path; the fixed protocol and the omega
 * background are not offered here. Masks start on, as for a DAC measurement.
 */
const exploratory = (c: CrystalConfig): CrystalConfig =>
  c.integration_method === "summation"
    ? { ...c, confirmed: true, background: false }
    : {
        ...c,
        confirmed: true,
        integration_method: "summation",
        protocol: null,
        background: false,
        dac_enabled: true,
        dac_axis: [0, 0, 1],
        seat_enabled: true,
        // Measured on the ID11 Eiger scan: the shadow edge is sharp (fully lit
        // 8 px past half level), so mask below half the lit level plus one block.
        seat_threshold: 0.5,
        seat_guard: 16,
        diamond_enabled: true,
        aperture_radius: 6,
        omega_radius: 1.5,
        polarization: 0.99,
        link_radius: 3,
        refine_geometry: false,
        scan_scaling: false,
      };
const steps = ["Prepare masks", "Find spots", "Find lattices"] as const;
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
  const openSeries = () => void run("scxrd_load", {}, "Opening frames…");
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
  /** The settings as they will be sent, including the mask defaults. */
  const config = data ? exploratory(data.config) : null;
  const setConfig = (patch: Partial<CrystalConfig>, then?: () => void) => {
    if (!data) return;
    const config = exploratory({ ...data.config, ...patch });
    if (JSON.stringify(config) === JSON.stringify(data.config)) then?.();
    else
      void run("scxrd_settings", { config }, "", (r) => {
        if (r.ok && then) afterCommand.current = then;
      });
  };
  // A command cannot start from inside another command's reply (the app is
  // still busy then), so a follow-up waits here until that command is done.
  const afterCommand = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (busy || !ready || !afterCommand.current) return;
    const next = afterCommand.current;
    afterCommand.current = null;
    next();
  }, [busy, ready, data?.revision, data?.config]);
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
    if (stage === 2 && data.cells.length)
      return `${data.cells.length} candidate${data.cells.length === 1 ? "" : "s"}${data.selected == null ? " · choose one" : ""}`;
    if (state.status === "attention" || state.status === "paused")
      return state.detail;
    if (state.status !== "complete") return "";
    return stage === 0
      ? state.detail
      : stage === 1
        ? `${data.trackCount} linked spots`
        : `${data.cells.length} candidate${data.cells.length === 1 ? "" : "s"}`;
  };
  const lastStage = data?.geometry ? 2 : 1;
  const analysed = !!data?.stages
    .slice(0, lastStage + 1)
    .every((stage) => stage.status === "complete");
  const markers = useMemo<RasterMarker[]>(
    () =>
      (live?.peaks ?? data?.peaks ?? []).map((p) => ({
        x: p.x,
        y: p.y,
        kind:
          p.flags || ("excluded" in p && p.excluded) ? "rejected" : "observed",
      })),
    [data?.peaks, live?.peaks],
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
  // Numbers change by typing only: the wheel must not step a focused field.
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
  if (!active) return null;
  return (
    <div
      ref={workspaceRef}
      className="sc-workspace sc-workspace--lean"
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
            <fieldset className="sc-angles sc-section" disabled={!ready}>
              <legend className="section-label">Rotation</legend>
              <CommitNumberField
                label="First frame start"
                unit="°"
                value={data.config.omega_start}
                onCommit={(v) => setConfig({ omega_start: v })}
              />
              <CommitNumberField
                label="Step"
                unit="°"
                value={data.config.omega_step}
                onCommit={(v) => setConfig({ omega_step: v })}
                positive
              />
              <CommitNumberField
                label="Width per frame"
                unit="°"
                value={data.config.exposure}
                onCommit={(v) => setConfig({ exposure: v })}
                positive
              />
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
          </>
        )}
        {!!frames && data && (
          <>
            <section className="sc-section" aria-label="Calibration">
              <div className="section-label">Calibration</div>
              <div className="sc-actions">
                <Button
                  disabled={!ready}
                  onClick={() =>
                    void run(
                      "scxrd_file",
                      { operation: "calibration" },
                      "Loading calibration…",
                    )
                  }
                >
                  Load .poni…
                </Button>
                <Button
                  disabled={!ready || !calibrated}
                  onClick={() =>
                    void run("scxrd_file", { operation: "use_calibration" }, "")
                  }
                >
                  Use calibration
                </Button>
                {data.geometry && (
                  <span>λ {crystalNumber(data.geometry.wavelength, 4)} Å</span>
                )}
              </div>
            </section>
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
                          (stage === 0 && !!data.notice)
                            ? "sc-step-problem"
                            : undefined
                        }
                      >
                        {stepSummary(stage) ||
                          (!data.geometry &&
                          (stage === 2 ||
                            (stage === 0 &&
                              (config!.dac_enabled || config!.diamond_enabled)))
                            ? "Needs a calibration"
                            : "")}
                      </small>
                    </span>
                    {data.stages[stage].status === "complete" && (
                      <span className="sc-step-time">
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
                  {openStep === stage && (
                    <fieldset className="sc-angles" disabled={!ready}>
                      {stage === 0 && (
                        <>
                          <label className="sc-check">
                            <Input
                              type="checkbox"
                              checked={config!.dac_enabled}
                              onChange={(e) =>
                                setConfig({ dac_enabled: e.target.checked })
                              }
                            />
                            DAC opening
                          </label>
                          {config!.dac_enabled && (
                            <CommitNumberField
                              label="Half-opening"
                              unit="°"
                              value={config!.dac_half_opening}
                              onCommit={(v) =>
                                setConfig({ dac_half_opening: v })
                              }
                              positive
                              max={89.9}
                            />
                          )}
                          <label className="sc-check">
                            <Input
                              type="checkbox"
                              checked={config!.seat_enabled}
                              onChange={(e) =>
                                setConfig({ seat_enabled: e.target.checked })
                              }
                            />
                            Seat shadow
                          </label>
                          {config!.seat_enabled && (
                            <>
                              <CommitNumberField
                                label="Below / × lit"
                                value={config!.seat_threshold}
                                onCommit={(v) =>
                                  setConfig({ seat_threshold: v })
                                }
                                positive
                                max={0.99}
                              />
                              <CommitNumberField
                                label="Margin / px"
                                value={config!.seat_guard}
                                onCommit={(v) => setConfig({ seat_guard: v })}
                                integer
                                min={0}
                                max={4096}
                              />
                            </>
                          )}
                          <label className="sc-check">
                            <Input
                              type="checkbox"
                              checked={config!.diamond_enabled}
                              onChange={(e) =>
                                setConfig({ diamond_enabled: e.target.checked })
                              }
                            />
                            Diamond spots
                          </label>
                          {config!.diamond_enabled && (
                            <>
                              <CommitNumberField
                                label="Min. size"
                                unit="px"
                                value={config!.diamond_min_area}
                                onCommit={(v) =>
                                  setConfig({ diamond_min_area: v })
                                }
                                integer
                                min={1}
                              />
                              <CommitNumberField
                                label="d tolerance"
                                unit="%"
                                value={config!.diamond_tolerance}
                                onCommit={(v) =>
                                  setConfig({ diamond_tolerance: v })
                                }
                                positive
                                max={20}
                              />
                            </>
                          )}
                        </>
                      )}
                      {stage === 1 && (
                        <>
                          <CommitNumberField
                            label="Threshold"
                            unit="σ"
                            value={data.config.threshold}
                            onCommit={(v) => setConfig({ threshold: v })}
                            positive
                          />
                          <CommitNumberField
                            label="Minimum area"
                            unit="px"
                            value={data.config.min_pixels}
                            onCommit={(v) => setConfig({ min_pixels: v })}
                            integer
                            min={1}
                          />
                          <CommitNumberField
                            label="Link radius"
                            unit="px"
                            value={data.config.link_radius}
                            onCommit={(v) => setConfig({ link_radius: v })}
                            positive
                          />
                        </>
                      )}
                      {stage === 2 && (
                        <>
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
              <section
                className="sc-section sc-cell-list"
                aria-label="Lattice candidates"
              >
                <div className="section-label">Lattice candidates</div>
                {data.cells.map((cell, i) => (
                  <div
                    className={`sc-cell-card ${data.selected === i ? "sc-cell-chosen" : ""}`}
                    key={i}
                  >
                    <div className="sc-cell-card-head">
                      <Button
                        disabled={!ready}
                        aria-pressed={data.selected === i}
                        onClick={() =>
                          void run(
                            "scxrd_edit",
                            { operation: "cell", index: i },
                            "",
                          )
                        }
                      >
                        {data.selected === i ? "Selected" : "Use lattice"}
                      </Button>
                      <span>
                        {cell.indexed}/{cell.total} spots
                      </span>
                    </div>
                    <dl>
                      <dt>a, b, c / Å</dt>
                      <dd>
                        {cell.parameters
                          .slice(0, 3)
                          .map((n) => crystalNumber(n))
                          .join(" · ")}
                      </dd>
                      <dt>α, β, γ / °</dt>
                      <dd>
                        {cell.parameters
                          .slice(3)
                          .map((n) => crystalNumber(n, 2))
                          .join(" · ")}
                      </dd>
                    </dl>
                  </div>
                ))}
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
