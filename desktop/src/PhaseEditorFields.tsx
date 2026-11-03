import { useEffect, useId, useRef, useState } from "react";

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
}) {
  const [text, setText] = useState(value == null ? "" : String(value));
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const last = useRef(value);
  const generation = useRef(0);
  const id = useId();
  const restore = () => {
    setText(value == null ? "" : String(value));
    setError("");
    last.current = value;
  };
  useEffect(() => {
    setText(value == null ? "" : String(value));
    last.current = value;
    setError("");
  }, [value]);
  const commit = async (draft = text) => {
    if (pending || disabled) return;
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
      return;
    }
    setError("");
    if (n === last.current) return;
    last.current = n;
    const revision = ++generation.current;
    setPending(true);
    const accepted = await onCommit(n);
    if (revision === generation.current) {
      setPending(false);
      if (accepted === false) restore();
    }
  };
  return (
    <span className="pe-number">
      <input
        type="text"
        inputMode="decimal"
        aria-label={label}
        title={title}
        value={text}
        disabled={disabled}
        readOnly={pending}
        aria-busy={pending}
        aria-invalid={!!error}
        aria-describedby={error ? id : undefined}
        data-editor-number="true"
        onChange={(e) => {
          setText(e.target.value);
          setError("");
        }}
        onBlur={() => void commit()}
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
            const n = Number(text);
            if (!text.trim() || !Number.isFinite(n)) return;
            const next = Math.min(
              max ?? Infinity,
              Math.max(
                min ?? -Infinity,
                Number(
                  (n + (e.key === "ArrowUp" ? step : -step)).toPrecision(12),
                ),
              ),
            );
            setText(String(next));
            void commit(String(next));
          }
        }}
      />
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
