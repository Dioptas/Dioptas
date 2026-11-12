import { useCallback, useState, useId } from "react";
import { CommitNumberField } from "./CommitNumberField";
import type { NumericLimits } from "./numericDraft";
export function CrystalNumberField({
  field,
  label,
  value,
  onCommit,
  onValidation,
  ...limits
}: {
  field: string;
  label: string;
  value: number;
  onCommit: (v: number) => void;
  onValidation: (field: string, error: string | null) => void;
} & NumericLimits) {
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  const validation = useCallback(
    (error: string | null) => {
      setError(error);
      onValidation(field, error);
    },
    [field, onValidation],
  );
  return (
    <div className="sc-number">
      <CommitNumberField
        label={label}
        value={value}
        onCommit={onCommit}
        onValidationChange={validation}
        validationId={id}
        {...limits}
      />
      {error && (
        <span className="ui-field-error" id={id}>
          {error}
        </span>
      )}
    </div>
  );
}
