import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

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
    setText(
      focused.current ? (value == null ? "" : String(value)) : display(value),
    );
    dirty.current = false;
    last.current = value;
    setError("");
  }, [value, significantDigits]);
  const commit = async (draft = text) => {
    if (pending || disabled) return false;
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
    const accepted = await onCommit(n);
    if (revision === generation.current) {
      setPending(false);
      if (accepted === false) restore();
      else dirty.current = false;
    }
    return accepted !== false;
  };
  const nudge = (direction: number) => {
    if (disabled || pending || step === "any") return;
    const n = Number(text);
    if (!text.trim() || !Number.isFinite(n)) return;
    const next = Math.min(
      max ?? Infinity,
      Math.max(
        min ?? -Infinity,
        Number((n + direction * step).toPrecision(12)),
      ),
    );
    input.current?.focus();
    dirty.current = true;
    setText(String(next));
    void commit(String(next));
  };
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
        readOnly={pending}
        aria-busy={pending}
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
