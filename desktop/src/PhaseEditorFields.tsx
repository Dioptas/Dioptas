import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useSpinBoxWheel } from "./spinBoxWheel";

/** A draft survives parent renders. Enter/blur commit; Escape restores the model. */
export function EditorNumber({
  label,
  value,
  onCommit,
  disabled = false,
  min,
  max,
  step = "any",
  optional = false,
  integer = false,
  title,
  significantDigits,
  stepper = false,
}: {
  label: string;
  value: number | null;
  onCommit: (value: number | null) => Promise<boolean> | void;
  disabled?: boolean;
  min?: number;
  max?: number;
  step?: number | "any";
  optional?: boolean;
  integer?: boolean;
  title?: string;
  significantDigits?: number;
  stepper?: boolean;
}) {
  const display = (n: number | null) =>
    n == null
      ? ""
      : significantDigits
        ? String(Number(n.toPrecision(significantDigits)))
        : String(n);
  const focused = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const dirty = useRef(false);
  const [text, setText] = useState(display(value));
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [wheelBusy, setWheelBusy] = useState(false);
  const pendingAction = useRef<Promise<boolean | void> | null>(null);
  const wheelTarget = useRef<number | null>(null);
  const wheelRunning = useRef(false);
  const last = useRef(value);
  const generation = useRef(0);
  const id = useId();
  const restore = () => {
    setText(
      focused.current ? (value == null ? "" : String(value)) : display(value),
    );
    dirty.current = false;
    setError("");
    last.current = value;
  };
  useEffect(() => {
    if (wheelTarget.current != null) {
      last.current = value;
      return;
    }
    setText(
      focused.current ? (value == null ? "" : String(value)) : display(value),
    );
    dirty.current = false;
    last.current = value;
    setError("");
  }, [value, significantDigits]);
  const commit = async (draft = text) => {
    if (pendingAction.current || disabled) return false;
    if (!dirty.current) return true;
    const empty = !draft.trim();
    const n = empty ? null : Number(draft);
    if (
      (empty && !optional) ||
      (n != null &&
        (!Number.isFinite(n) ||
          (min != null && n < min) ||
          (max != null && n > max) ||
          (integer && !Number.isInteger(n))))
    ) {
      setError(
        empty
          ? "Enter a value."
          : `Enter ${integer ? "an integer" : "a number"}${min != null ? ` ≥ ${min}` : ""}${max != null ? ` and ≤ ${max}` : ""}.`,
      );
      return false;
    }
    setError("");
    if (n === last.current) {
      dirty.current = false;
      return true;
    }
    last.current = n;
    const revision = ++generation.current;
    setPending(true);
    const applying = Promise.resolve(onCommit(n));
    pendingAction.current = applying;
    let accepted;
    try {
      accepted = await applying;
    } catch {
      setPending(false);
      restore();
      return false;
    } finally {
      pendingAction.current = null;
    }
    if (revision === generation.current) {
      setPending(false);
      if (accepted === false) restore();
      else dirty.current = false;
    }
    return accepted !== false;
  };
  const nudge = (direction: number, quantum = step === "any" ? 1 : step) => {
    if (disabled || pending) return;
    const n = Number(text);
    if (!text.trim() || !Number.isFinite(n)) return;
    const next = Math.min(
      max ?? Infinity,
      Math.max(
        min ?? -Infinity,
        Number((n + direction * quantum).toPrecision(12)),
      ),
    );
    input.current?.focus();
    dirty.current = true;
    setText(String(next));
    void commit(String(next));
  };
  useSpinBoxWheel(input, (direction) => {
    const current =
      wheelTarget.current ??
      (dirty.current ? Number(input.current?.value) : value);
    if (
      disabled ||
      current == null ||
      !input.current?.value.trim() ||
      !Number.isFinite(current)
    )
      return;
    input.current.focus({ preventScroll: true });
    const quantum = step === "any" ? 1 : step;
    wheelTarget.current = Math.min(
      max ?? Infinity,
      Math.max(
        min ?? -Infinity,
        Number((current + direction * quantum).toPrecision(12)),
      ),
    );
    setText(String(wheelTarget.current));
    if (wheelRunning.current) return;
    wheelRunning.current = true;
    setWheelBusy(true);
    void (async () => {
      try {
        while (wheelTarget.current != null) {
          if (pendingAction.current) await pendingAction.current;
          const target = wheelTarget.current;
          dirty.current = true;
          if (!(await commit(String(target)))) {
            wheelTarget.current = null;
            break;
          }
          if (wheelTarget.current === target) wheelTarget.current = null;
        }
      } finally {
        wheelRunning.current = false;
        setWheelBusy(false);
      }
    })();
  });
  return (
    <span className={`pe-number${stepper ? " pe-number-stepped" : ""}`}>
      <input
        ref={input}
        type="text"
        inputMode="decimal"
        aria-label={label}
        title={title || (value == null ? undefined : String(value))}
        value={text}
        disabled={disabled}
        readOnly={pending || wheelBusy}
        aria-busy={pending || wheelBusy}
        aria-invalid={!!error}
        aria-describedby={error ? id : undefined}
        data-editor-number="true"
        onFocus={() => {
          focused.current = true;
          if (!dirty.current && !error)
            setText(value == null ? "" : String(value));
        }}
        onChange={(e) => {
          dirty.current = true;
          setText(e.target.value);
          setError("");
        }}
        onBlur={() => {
          focused.current = false;
          const draft = text;
          void commit().then((ok) => {
            if (ok) setText(display(draft.trim() ? Number(draft) : null));
          });
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void commit();
          }
          if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            restore();
          }
          if (
            (e.key === "ArrowUp" || e.key === "ArrowDown") &&
            step !== "any" &&
            !pending
          ) {
            e.preventDefault();
            nudge(e.key === "ArrowUp" ? 1 : -1);
          }
        }}
      />
      {stepper && step !== "any" && (
        <span className="pe-number-steps">
          {[1, -1].map((direction) => (
            <button
              key={direction}
              type="button"
              tabIndex={-1}
              aria-label={`${direction === 1 ? "Increase" : "Decrease"} ${label}`}
              title={`${direction === 1 ? "Increase" : "Decrease"} by ${step}`}
              disabled={disabled || pending}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => nudge(direction)}
            >
              {direction === 1 ? <ChevronUp /> : <ChevronDown />}
            </button>
          ))}
        </span>
      )}
      {error && (
        <span id={id} className="pe-field-error">
          {error}
        </span>
      )}
    </span>
  );
}

export function TextEdit({
  label,
  value,
  onCommit,
  disabled = false,
}: {
  label: string;
  value: string;
  onCommit: (value: string) => Promise<boolean>;
  disabled?: boolean;
}) {
  const [text, setText] = useState(value);
  const last = useRef(value);
  useEffect(() => {
    setText(value);
    last.current = value;
  }, [value]);
  const commit = async () => {
    if (disabled || text === last.current) return;
    last.current = text;
    if (!(await onCommit(text))) {
      setText(value);
      last.current = value;
    }
  };
  return (
    <input
      aria-label={label}
      value={text}
      disabled={disabled}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => void commit()}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          void commit();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          setText(value);
          last.current = value;
        }
      }}
    />
  );
}
