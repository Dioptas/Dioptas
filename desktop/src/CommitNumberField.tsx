import { useEffect, useId, useState } from "react";
import { ScientificNumberInput } from "./ScientificNumberInput";
import { numericDraftError, type NumericLimits } from "./numericDraft";

/** Commit valid numeric text on blur/Enter; Escape restores the applied value. */
export function CommitNumberField({
  label,
  value,
  onCommit,
  ...limits
}: {
  label: string;
  value: number;
  onCommit: (value: number) => void;
} & NumericLimits) {
  const [draft, setDraft] = useState(String(value));
  const id = useId();
  useEffect(() => setDraft(String(value)), [value]);
  const error = numericDraftError(draft, limits);
  return (
    <label className="field-label integration-number-field">
      <span>{label}</span>
      <ScientificNumberInput
        aria-label={label}
        value={draft}
        min={limits.min}
        max={limits.max}
        step={limits.integer ? 1 : "any"}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
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
      {error && (
        <span className="ui-field-error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </label>
  );
}
