import { Button, Input } from "./ui";
import { useEffect, useId, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ScientificNumberInput } from "./ScientificNumberInput";
import type { BatchData, BatchRun } from "./batchDomain";
import { batchNormalizationRegion } from "./batchDisplay";
import { unitLabel } from "./types";

/** Frame numbers are one-based in the UI; stored indices remain zero-based. */
export function BatchControls({
  batch,
  docked = false,
  optionsVisible = false,
  ready,
  calibrated,
  filesView,
  run,
  onRange,
  onStep,
}: {
  batch: BatchData | null;
  docked?: boolean;
  optionsVisible?: boolean;
  ready: boolean;
  calibrated: boolean;
  filesView: boolean;
  run: BatchRun;
  onRange: (start: number, stop: number) => void;
  onStep?: (step: number) => void;
}) {
  const count = batch?.entries.length ?? 0,
    max = filesView ? (batch?.total ?? 1) - 1 : count - 1;
  const [start, setStart] = useState(0),
    [stop, setStop] = useState(Math.max(0, max)),
    [step, setStep] = useState(1),
    [jump, setJump] = useState("1");
  const stepCallback = useRef(onStep);
  stepCallback.current = onStep;
  useEffect(() => {
    stepCallback.current?.(step);
  }, [step]);
  const [minimum, setMinimum] = useState(""),
    [maximum, setMaximum] = useState("");
  const region = batchNormalizationRegion(batch);
  const normalizationErrorId = useId();
  const axis =
    batch?.unit === "q_A^-1" ? "Q" : batch?.unit === "d_A" ? "d" : "2θ";
  useEffect(() => {
    setMinimum(region ? String(region.minimum) : "");
    setMaximum(region ? String(region.maximum) : "");
  }, [batch?.id, batch?.unit, region?.minimum, region?.maximum]);
  useEffect(() => {
    setStart(0);
    setStop(Math.max(0, max));
    setStep(1);
  }, [max, filesView, batch?.files[0]?.path]);
  useEffect(
    () => setJump(String((batch?.selected ?? 0) + 1)),
    [batch?.selected],
  );
  const normalizationValid =
    minimum.trim() !== "" &&
    maximum.trim() !== "" &&
    Number.isFinite(Number(minimum)) &&
    Number.isFinite(Number(maximum)) &&
    Number(minimum) >= 0 &&
    (batch?.unit !== "d_A" || Number(minimum) > 0) &&
    Number(minimum) < Number(maximum) &&
    (batch?.unit !== "2th_deg" || Number(maximum) <= 180);
  const select = (index: number) =>
    void run("batch_select", { index }, "Loading batch frame…");
  const current = batch?.selected ?? 0;
  const normalizationChanged =
    !region ||
    Number(minimum) !== region.minimum ||
    Number(maximum) !== region.maximum;
  const integration = filesView && (
    <div className="batch-action-row">
      <Button
        disabled={!ready || !batch?.canReintegrate || !calibrated}
        onClick={() =>
          run(
            "batch_load",
            { reintegrate: true, start: start + 1, stop: stop + 1, step },
            "Integrating batch…",
          )
        }
      >
        Integrate
      </Button>
    </div>
  );
  const normalization = (
    <fieldset className="batch-normalization-settings">
      <legend>Normalization region</legend>
      <p>
        Match the mean intensity in this {axis} region to{" "}
        {batch?.normalizationReferenceName ?? "the reference pattern"}.
      </p>
      <label>
        Minimum {unitLabel(batch?.unit ?? "2th_deg")}
        <ScientificNumberInput
          aria-label={`Normalization minimum ${axis}`}
          aria-invalid={!!batch && !normalizationValid}
          aria-describedby={
            batch && !normalizationValid ? normalizationErrorId : undefined
          }
          value={minimum}
          disabled={!ready || !batch}
          onValueChange={setMinimum}
        />
      </label>
      <label>
        Maximum {unitLabel(batch?.unit ?? "2th_deg")}
        <ScientificNumberInput
          aria-label={`Normalization maximum ${axis}`}
          aria-invalid={!!batch && !normalizationValid}
          aria-describedby={
            batch && !normalizationValid ? normalizationErrorId : undefined
          }
          value={maximum}
          disabled={!ready || !batch}
          onValueChange={setMaximum}
        />
      </label>
      {batch && !normalizationValid && (
        <p id={normalizationErrorId} className="ui-field-error">
          {axis === "2θ"
            ? "Enter an increasing 2θ interval between 0° and 180°."
            : `Enter an increasing, ${axis === "d" ? "positive" : "non-negative"} ${axis} interval.`}
        </p>
      )}
      <Button
        title={
          !normalizationValid
            ? "Enter a valid normalization region"
            : !normalizationChanged
              ? "Normalization limits are unchanged"
              : "Apply the normalization region"
        }
        disabled={
          !ready || !batch || !normalizationValid || !normalizationChanged
        }
        onClick={() =>
          run(
            "batch_normalization_settings",
            {
              minimum: Number(minimum),
              maximum: Number(maximum),
              unit: batch?.unit,
            },
            "Updating normalization region…",
          )
        }
      >
        Apply normalization region
      </Button>
      <p>Use the = icon beside the plot axis.</p>
    </fieldset>
  );
  const ranges = (
    <div className="batch-range-row">
      <label>
        Start
        <BatchRangeInput
          aria-label="Batch start frame"
          min={1}
          max={stop + 1}
          value={start + 1}
          disabled={!batch}
          onCommit={(value) => {
            setStart(value - 1);
            if (!filesView) onRange(value - 1, Math.min(stop, count - 1));
          }}
        />
      </label>
      <label>
        Stop
        <BatchRangeInput
          aria-label="Batch stop frame"
          min={start + 1}
          max={Math.max(1, max + 1)}
          value={stop + 1}
          disabled={!batch}
          onCommit={(value) => {
            setStop(value - 1);
            if (!filesView) onRange(start, Math.min(value - 1, count - 1));
          }}
        />
      </label>
      <label>
        Step
        <BatchRangeInput
          aria-label="Batch frame step"
          min={1}
          max={Math.max(1, max + 1)}
          value={step}
          disabled={!batch}
          onCommit={setStep}
        />
      </label>
    </div>
  );
  const navigation = (
    <div className="batch-navigation-row">
      <Button
        aria-label="Previous batch frame"
        title="Previous frame"
        disabled={!ready || !count || current - step < start}
        onClick={() => select(current - step)}
      >
        <ChevronLeft size={15} />
      </Button>
      <Input
        className="batch-frame-slider"
        aria-label="Batch frame slider"
        type="range"
        min={1}
        max={Math.max(1, count)}
        value={Math.min(Math.max(1, Number(jump) || 1), Math.max(1, count))}
        disabled={!ready || !count}
        onChange={(e) => setJump(e.target.value)}
        onPointerUp={(e) => select(Number(e.currentTarget.value) - 1)}
        onKeyUp={(e) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key))
            select(Number(e.currentTarget.value) - 1);
        }}
      />
      <Button
        aria-label="Next batch frame"
        title="Next frame"
        disabled={
          !ready || !count || current + step > Math.min(stop, count - 1)
        }
        onClick={() => select(current + step)}
      >
        <ChevronRight size={15} />
      </Button>
      <label className="batch-frame-number">
        Frame · {current + 1} of {count} · {count}/{batch?.total ?? 0} loaded
        <Input
          aria-label="Selected batch frame"
          type="number"
          min={1}
          max={Math.max(1, count)}
          disabled={!ready || !count}
          value={jump}
          onChange={(e) => setJump(e.target.value)}
          onBlur={() => {
            const n = Number(jump);
            if (
              Number.isInteger(n) &&
              n >= 1 &&
              n <= count &&
              n - 1 !== current
            )
              select(n - 1);
            else setJump(String(current + 1));
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
      </label>
    </div>
  );
  return (
    <div
      role={optionsVisible ? "tabpanel" : undefined}
      aria-label={optionsVisible ? "Batch options" : undefined}
      hidden={docked && !filesView && !optionsVisible}
      className={`batch-bottom-controls ${optionsVisible ? "batch-options-active" : ""}`}
    >
      {optionsVisible ? (
        <div className="batch-settings-content">
          {normalization}
          <fieldset className="batch-frame-settings">
            <legend>Frame range</legend>
            {ranges}
          </fieldset>
        </div>
      ) : (
        <>
          {integration}
          {!docked && navigation}
          {ranges}
        </>
      )}
    </div>
  );
}

/** Batch ranges change only after a complete, valid integer is committed. */
function BatchRangeInput({
  value,
  onCommit,
  min,
  max,
  ...props
}: {
  value: number;
  onCommit: (value: number) => void;
  min: number;
  max: number;
  disabled: boolean;
  "aria-label": string;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  const parsed = Number(text);
  const valid =
    text.trim() !== "" &&
    Number.isInteger(parsed) &&
    parsed >= min &&
    parsed <= max;
  return (
    <Input
      {...props}
      type="number"
      min={min}
      max={max}
      step={1}
      value={text}
      aria-invalid={!valid || undefined}
      title={`Integer from ${min} to ${max}; Enter or Tab applies`}
      onChange={(event) => setText(event.currentTarget.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
      onBlur={() => {
        if (valid && parsed !== value) onCommit(parsed);
        else setText(String(value));
      }}
    />
  );
}
