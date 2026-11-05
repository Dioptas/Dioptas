import { useAnchoredDialog } from "./useAnchoredDialog";
import { Dialog, DialogHeader } from "./Dialog";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronLeft, ChevronRight, Settings2 } from "lucide-react";
import type { BatchData, BatchRun } from "./batchDomain";

/** Frame numbers are one-based in the UI; stored indices remain zero-based. */
export function BatchControls({
  batch,
  docked = false,
  optionsVisible = false,
  ready,
  calibrated,
  filesView,
  run,
  onAutoScale,
  onRange,
}: {
  batch: BatchData | null;
  docked?: boolean;
  optionsVisible?: boolean;
  ready: boolean;
  calibrated: boolean;
  filesView: boolean;
  run: BatchRun;
  onAutoScale: () => void;
  onRange: (start: number, stop: number) => void;
}) {
  const count = batch?.entries.length ?? 0,
    max = filesView ? (batch?.total ?? 1) - 1 : count - 1;
  const [start, setStart] = useState(0),
    [stop, setStop] = useState(Math.max(0, max)),
    [step, setStep] = useState(1),
    [jump, setJump] = useState("1");
  const normalizationButton = useRef<HTMLButtonElement>(null),
    popup = useRef<HTMLDialogElement>(null);
  const [normalization, setNormalization] = useState(false);
  useAnchoredDialog(
    popup,
    normalizationButton.current,
    normalization,
    "end",
    true,
  );
  const [firstBin, setFirstBin] = useState(0),
    [lastBin, setLastBin] = useState(0),
    [reference, setReference] = useState(0);
  useEffect(() => {
    setStart(0);
    setStop(Math.max(0, max));
    setStep(1);
  }, [max, filesView, batch?.files[0]?.path]);
  useEffect(
    () => setJump(String((batch?.selected ?? 0) + 1)),
    [batch?.selected],
  );
  useEffect(() => {
    setFirstBin(batch?.normalizationRange[0] ?? 0);
    setLastBin(
      Math.min(
        (batch?.x.length ?? 1) - 1,
        (batch?.normalizationRange[1] ?? 1) - 1,
      ),
    );
    setReference(batch?.normalizationReference ?? 0);
  }, [
    batch?.normalizationRange[0],
    batch?.normalizationRange[1],
    batch?.normalizationReference,
    batch?.x.length,
  ]);
  const normalizationValid =
    [firstBin, lastBin, reference].every(Number.isInteger) &&
    firstBin >= 0 &&
    firstBin <= lastBin &&
    lastBin < (batch?.x.length ?? 0) &&
    reference >= 0 &&
    reference < count;
  const select = (index: number) =>
    void run("batch_select", { index }, "Loading batch frame…");
  const current = batch?.selected ?? 0;
  const actions = (
    <div className="batch-action-row">
      {filesView ? (
        <button
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
        </button>
      ) : (
        <>
          <button disabled={!ready || !batch} onClick={onAutoScale}>
            AutoScale
          </button>
          <span className="batch-control-divider" />
          <button
            aria-label="Normalize batch"
            aria-pressed={!!batch?.normalized}
            disabled={!ready || !batch}
            onClick={() =>
              run(
                "batch_normalize",
                {
                  enabled: !batch?.normalized,
                  start: (batch?.normalizationRange[0] ?? 0) + 1,
                  stop: batch?.normalizationRange[1],
                  reference: (batch?.normalizationReference ?? 0) + 1,
                },
                "Updating normalization…",
              )
            }
          >
            Normalize
          </button>
          <span className="batch-normalization-anchor">
            <button
              ref={normalizationButton}
              aria-label="Normalization settings"
              title="Normalization settings"
              disabled={!ready || !batch}
              onClick={() => {
                setFirstBin(batch?.normalizationRange[0] ?? 0);
                setLastBin(
                  Math.min(
                    (batch?.x.length ?? 1) - 1,
                    (batch?.normalizationRange[1] ?? 1) - 1,
                  ),
                );
                setReference(batch?.normalizationReference ?? 0);
                setNormalization((v) => !v);
              }}
            >
              <Settings2 size={15} />
            </button>
            {normalization &&
              createPortal(
                <Dialog
                  returnFocusTarget={normalizationButton.current}
                  dialogRef={popup}
                  onDismiss={() => setNormalization(false)}
                  className="batch-normalization-popup"
                  aria-label="Normalization settings"
                >
                  <DialogHeader
                    title="Normalization settings"
                    closeLabel="Close normalization settings"
                    onClose={() => setNormalization(false)}
                  />
                  <p>
                    Match each frame’s mean intensity to the reference over the
                    selected bins. Bin numbers start at 0; frame numbers start
                    at 1.
                  </p>
                  <label>
                    First bin (inclusive)
                    <input
                      aria-label="First normalization bin"
                      type="number"
                      min={0}
                      max={lastBin}
                      value={Number.isFinite(firstBin) ? firstBin : ""}
                      onChange={(e) => setFirstBin(e.target.valueAsNumber)}
                    />
                  </label>
                  <label>
                    Last bin (inclusive)
                    <input
                      aria-label="Last normalization bin"
                      type="number"
                      min={firstBin}
                      max={(batch?.x.length ?? 1) - 1}
                      value={Number.isFinite(lastBin) ? lastBin : ""}
                      onChange={(e) => setLastBin(e.target.valueAsNumber)}
                    />
                  </label>
                  <label>
                    Reference frame
                    <input
                      aria-label="Normalization reference frame"
                      type="number"
                      min={1}
                      max={count}
                      value={Number.isFinite(reference) ? reference + 1 : ""}
                      onChange={(e) => setReference(e.target.valueAsNumber - 1)}
                    />
                  </label>
                  <div>
                    <button
                      className="primary"
                      disabled={!ready || !normalizationValid}
                      onClick={() => {
                        void run(
                          "batch_normalization_settings",
                          { start: firstBin, stop: lastBin, reference },
                          "Updating normalization settings…",
                        );
                        setNormalization(false);
                      }}
                    >
                      Apply
                    </button>
                    <button onClick={() => setNormalization(false)}>
                      Cancel
                    </button>
                  </div>
                </Dialog>,
                document.body,
              )}
          </span>
        </>
      )}
    </div>
  );
  const ranges = (
    <div className="batch-range-row">
      <label>
        Start:
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
        Stop:
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
        Step:
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
      <button
        aria-label="Previous batch frame"
        title="Previous frame"
        disabled={!ready || !count || current - step < start}
        onClick={() => select(current - step)}
      >
        <ChevronLeft size={15} />
      </button>
      <input
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
      <button
        aria-label="Next batch frame"
        title="Next frame"
        disabled={
          !ready || !count || current + step > Math.min(stop, count - 1)
        }
        onClick={() => select(current + step)}
      >
        <ChevronRight size={15} />
      </button>
      <label className="batch-frame-number">
        Frame · {current + 1} of {count} · {count}/{batch?.total ?? 0} loaded
        <input
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
      hidden={docked && !filesView && !optionsVisible}
      className={`batch-bottom-controls ${docked && optionsVisible ? "batch-options-active" : ""}`}
    >
      {docked ? (
        <>
          <div
            className="batch-settings-content"
            hidden={!filesView && !optionsVisible}
          >
            {actions}
            {ranges}
          </div>
        </>
      ) : (
        <>
          {actions}
          {navigation}
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
    <input
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
