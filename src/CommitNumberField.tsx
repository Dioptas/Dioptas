import { useEffect, useId, useState } from "react";
import { ScientificNumberInput } from "./ScientificNumberInput";
import { numericDraftError, type NumericLimits } from "./numericDraft";

/** Commit valid numeric text on blur/Enter; Escape restores the applied value. */
export function CommitNumberField({
  label,
  value,
  onCommit,
  hideLabel = false,
  onValidationChange,
  validationId,
  ...limits
}: {
  label: string;
  value: number;
  onCommit: (value: number) => void;
  hideLabel?: boolean;
  onValidationChange?: (error: string | null) => void;
  validationId?: string;
} & NumericLimits) {
  const [draft, setDraft] = useState(String(value));
  const id = useId();
  useEffect(() => setDraft(String(value)), [value]);
  const error = numericDraftError(draft, limits);
  useEffect(() => {
    onValidationChange?.(error);
  }, [error, onValidationChange]);
  useEffect(() => () => onValidationChange?.(null), [onValidationChange]);
  return (
    <label className="field-label integration-number-field">
      <span className={hideLabel ? "visually-hidden" : undefined}>{label}</span>
      <ScientificNumberInput
        aria-label={label}
        value={draft}
        min={limits.min}
        max={limits.max}
        step={limits.integer ? 1 : "any"}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? (validationId ?? `${id}-error`) : undefined}
        onValueChange={setDraft}
        onBlur={() => {
          if (!error && Number(draft) !== value) onCommit(Number(draft));
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            event.stopPropagation();
            event.currentTarget.blur();
          }
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            setDraft(String(value));
          }
        }}
      />
      {error && !onValidationChange && (
        <span className="ui-field-error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </label>
  );
}
