import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronLeft, ChevronRight, Settings2 } from "lucide-react";
import type { BatchData, BatchRun } from "./batchDomain";

/** Qt's bottom navigation and action rows; UI frame/bin numbers start at zero. */
export function BatchControls({
  batch,
  ready,
  calibrated,
  filesView,
  run,
  onAutoScale,
  onRange,
}: {
  batch: BatchData | null;
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
    [jump, setJump] = useState("0");
  const normalizationButton = useRef<HTMLButtonElement>(null),
    popup = useRef<HTMLDivElement>(null);
  const [popupPosition, setPopupPosition] = useState({ left: 8, top: 8 });
  const [normalization, setNormalization] = useState(false);
  const [firstBin, setFirstBin] = useState(0),
    [lastBin, setLastBin] = useState(0),
    [reference, setReference] = useState(0);
  useEffect(() => {
    setStart(0);
    setStop(Math.max(0, max));
    setStep(1);
  }, [max, filesView, batch?.files[0]?.path]);
  useEffect(() => setJump(String(batch?.selected ?? 0)), [batch?.selected]);
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
  useEffect(() => {
    if (!normalization) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNormalization(false);
    };
    const outside = (e: PointerEvent) => {
      if (
        !popup.current?.contains(e.target as Node) &&
        !normalizationButton.current?.contains(e.target as Node)
      )
        setNormalization(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", outside, true);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("pointerdown", outside, true);
      normalizationButton.current?.focus();
    };
  }, [normalization]);
  const select = (index: number) =>
    void run("batch_select", { index }, "Loading batch frame…");
  const current = batch?.selected ?? 0;
  return (
    <div className="batch-bottom-controls">
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
                  const r =
                    normalizationButton.current!.getBoundingClientRect();
                  setPopupPosition({
                    left: Math.max(
                      8,
                      Math.min(innerWidth - 318, r.right - 310),
                    ),
                    top: Math.max(8, r.top - 280),
                  });
                  setNormalization((v) => !v);
                }}
              >
                <Settings2 size={15} />
              </button>
              {normalization &&
                createPortal(
                  <div
                    ref={popup}
                    className="batch-normalization-popup"
                    style={popupPosition}
                    role="dialog"
                    aria-label="Normalization settings"
                  >
                    <strong>Normalization settings</strong>
                    <p>
                      Match each frame’s mean intensity to the reference over
                      the selected bins. Bin and frame numbers start at 0.
                    </p>
                    <label>
                      First bin (inclusive)
                      <input
                        aria-label="First normalization bin"
                        type="number"
                        min={0}
                        max={lastBin}
                        value={firstBin}
                        onChange={(e) => setFirstBin(Number(e.target.value))}
                      />
                    </label>
                    <label>
                      Last bin (inclusive)
                      <input
                        aria-label="Last normalization bin"
                        type="number"
                        min={firstBin}
                        max={(batch?.x.length ?? 1) - 1}
                        value={lastBin}
                        onChange={(e) => setLastBin(Number(e.target.value))}
                      />
                    </label>
                    <label>
                      Reference frame
                      <input
                        aria-label="Normalization reference frame"
                        type="number"
                        min={0}
                        max={count - 1}
                        value={reference}
                        onChange={(e) => setReference(Number(e.target.value))}
                      />
                    </label>
                    <div>
                      <button
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
                  </div>,
                  document.body,
                )}
            </span>
          </>
        )}
      </div>
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
          min={0}
          max={Math.max(0, count - 1)}
          value={Math.min(
            Math.max(0, Number(jump) || 0),
            Math.max(0, count - 1),
          )}
          disabled={!ready || !count}
          onChange={(e) => setJump(e.target.value)}
          onPointerUp={(e) => select(Number(e.currentTarget.value))}
          onKeyUp={(e) => {
            if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key))
              select(Number(e.currentTarget.value));
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
          Frame ({count}/{batch?.total ?? 0})
          <input
            aria-label="Selected batch frame"
            type="number"
            min={0}
            max={Math.max(0, count - 1)}
            disabled={!ready || !count}
            value={jump}
            onChange={(e) => setJump(e.target.value)}
            onBlur={() => {
              const n = Number(jump);
              if (Number.isInteger(n) && n >= 0 && n < count && n !== current)
                select(n);
              else setJump(String(current));
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
            }}
          />
        </label>
      </div>
      <div className="batch-range-row">
        <label>
          Start:
          <input
            aria-label="Batch start frame"
            type="number"
            min={0}
            max={stop}
            value={start}
            disabled={!batch}
            onChange={(e) => {
              const value = Number(e.target.value);
              setStart(value);
              if (!filesView) onRange(value, Math.min(stop, count - 1));
            }}
          />
        </label>
        <label>
          Stop:
          <input
            aria-label="Batch stop frame"
            type="number"
            min={start}
            max={Math.max(0, max)}
            value={stop}
            disabled={!batch}
            onChange={(e) => {
              const value = Number(e.target.value);
              setStop(value);
              if (!filesView) onRange(start, Math.min(value, count - 1));
            }}
          />
        </label>
        <label>
          Step:
          <input
            aria-label="Batch frame step"
            type="number"
            min={1}
            max={Math.max(1, max + 1)}
            value={step}
            disabled={!batch}
            onChange={(e) => setStep(Number(e.target.value))}
          />
        </label>
      </div>
    </div>
  );
}
