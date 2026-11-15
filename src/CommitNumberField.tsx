import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { ScientificNumberInput } from "./ScientificNumberInput";
import { useSpinBoxWheel } from "./spinBoxWheel";
import { Input } from "./ui";
import {
  numericDraftError,
  stepNumber,
  type NumericLimits,
} from "./numericDraft";

/** Commit valid numeric text on blur/Enter; Escape restores the applied value.
 * With `step` the box is the native Dioptas spin box (`.numeric-stepper`, as
 * in the phase editor and overlay controls): its arrows, the up/down keys and
 * the mouse wheel commit the next multiple of the step at once, clamped to
 * the limits; at a limit a step does nothing. Plain boxes never change with
 * the wheel. */
export function CommitNumberField({
  label,
  unit,
  value,
  onCommit,
  hideLabel = false,
  onValidationChange,
  validationId,
  step,
  ...limits
}: {
  label: string;
  /** Shown right of the box; the accessible name stays "label / unit". */
  unit?: string;
  value: number;
  onCommit: (value: number) => void;
  hideLabel?: boolean;
  onValidationChange?: (error: string | null) => void;
  validationId?: string;
  step?: number;
} & NumericLimits) {
  const [draft, setDraft] = useState(String(value));
  const id = useId();
  // A stepped value sent but not yet applied: older applied values arriving
  // meanwhile must not pull the box back.
  const awaiting = useRef<number | null>(null);
  useEffect(() => {
    if (awaiting.current === null || awaiting.current === value) {
      awaiting.current = null;
      setDraft(String(value));
    }
  }, [value]);
  const error = numericDraftError(draft, limits);
  useEffect(() => {
    onValidationChange?.(error);
  }, [error, onValidationChange]);
  useEffect(() => () => onValidationChange?.(null), [onValidationChange]);
  // Current state for steps that arrive faster than renders (wheel, keys).
  const latest = useRef({ draft, value, error, onCommit, limits, step });
  latest.current = { draft, value, error, onCommit, limits, step };
  const spin = (direction: 1 | -1) => {
    const s = latest.current;
    if (s.step === undefined) return;
    const from = s.error ? s.value : Number(s.draft);
    const next = stepNumber(from, s.step, direction, s.limits);
    if (next === from) {
      setDraft(String(from));
      return;
    }
    s.draft = String(next);
    setDraft(String(next));
    awaiting.current = next;
    s.onCommit(next);
  };
  const input = useRef<HTMLInputElement>(null);
  // Same wheel rule as every other spin box in Dioptas.
  useSpinBoxWheel(
    input,
    (direction) => spin(direction > 0 ? 1 : -1),
    step !== undefined,
  );
  const shared = {
    "aria-label": unit ? `${label} / ${unit}` : label,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error ? (validationId ?? `${id}-error`) : undefined,
    onBlur: () => {
      awaiting.current = null;
      if (!error && Number(draft) !== value) onCommit(Number(draft));
    },
    onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => {
      if (
        step !== undefined &&
        (event.key === "ArrowUp" || event.key === "ArrowDown")
      ) {
        event.preventDefault();
        event.stopPropagation();
        spin(event.key === "ArrowUp" ? 1 : -1);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.blur();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        awaiting.current = null;
        setDraft(String(value));
      }
    },
  };
  return (
    <label
      className={`field-label integration-number-field${unit ? " integration-number-with-unit" : ""}`}
    >
      <span className={hideLabel ? "visually-hidden" : undefined}>{label}</span>
      {step === undefined ? (
        <ScientificNumberInput
          ref={input}
          {...shared}
          value={draft}
          min={limits.min}
          max={limits.max}
          step={limits.integer ? 1 : "any"}
          onValueChange={setDraft}
        />
      ) : (
        // The native spin box: its arrows give only the direction; the value
        // comes from the step grid and the limits.
        <Input
          ref={input}
          {...shared}
          className="numeric-stepper"
          type="number"
          value={draft}
          min={limits.min ?? (limits.positive ? 0 : undefined)}
          max={limits.max}
          step={step}
          data-own-wheel
          onChange={(event) => {
            // Native arrow clicks emit plain input events; typing carries inputType.
            if (!("inputType" in event.nativeEvent)) {
              const moved = Number(event.currentTarget.value);
              const from = error ? value : Number(draft);
              if (Number.isFinite(moved) && moved !== from)
                spin(moved > from ? 1 : -1);
              else setDraft(String(from));
            } else setDraft(event.currentTarget.value);
          }}
        />
      )}
      {unit && (
        <span className="integration-number-unit" aria-hidden="true">
          {unit}
        </span>
      )}
      {error && !onValidationChange && (
        <span className="ui-field-error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </label>
  );
}
