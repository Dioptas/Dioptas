import { Button, Input } from "./ui";
import { useEffect, useRef, useState } from "react";
import { FolderOpen, Trash2 } from "lucide-react";
import { Check, splitNumericLabel } from "./IntegrationFields";

/** A complete, validated edit is committed once, leaving intermediate text local. */
export function ProcessingNumberField({
  label,
  displayLabel = label,
  value,
  onCommit,
  min,
  max,
  disabled = false,
}: {
  label: string;
  displayLabel?: string;
  value: number;
  onCommit: (value: number) => Promise<void>;
  min?: number;
  max?: number;
  disabled?: boolean;
}) {
  const { name, unit } = splitNumericLabel(displayLabel);
  const [text, setText] = useState(String(value));
  const input = useRef<HTMLInputElement>(null);
  const latest = useRef(value);
  latest.current = value;
  useEffect(() => {
    if (document.activeElement !== input.current) setText(String(value));
  }, [value]);
  const commit = async () => {
    const element = input.current;
    if (!element) return;
    const next = element.valueAsNumber;
    if (
      !element.value.trim() ||
      !Number.isFinite(next) ||
      !element.validity.valid
    ) {
      setText(String(latest.current));
      return;
    }
    if (next !== latest.current) await onCommit(next);
    setText(String(latest.current));
  };
  return (
    <label
      className={`field-label${unit ? " processing-field-with-unit" : ""}`}
    >
      <span>{name}</span>
      <Input
        ref={input}
        aria-label={label}
        type="number"
        step="any"
        min={min}
        max={max}
        disabled={disabled}
        value={text}
        onChange={(event) => setText(event.currentTarget.value)}
        onBlur={() => void commit()}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
          if (event.key === "Escape") {
            event.preventDefault();
            event.currentTarget.value = String(latest.current);
            setText(String(latest.current));
            event.currentTarget.blur();
          }
        }}
      />
      {unit && (
        <span className="processing-field-unit" aria-hidden="true">
          {unit}
        </span>
      )}
    </label>
  );
}

export function ProcessingFile({
  filename,
  kind,
  disabled,
  onLoad,
  onRemove,
}: {
  filename: string | null;
  kind: string;
  disabled: boolean;
  onLoad: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="processing-file">
      <Button
        type="button"
        aria-label={`Load ${kind}…`}
        title={`Load ${kind}…`}
        disabled={disabled}
        onClick={onLoad}
      >
        <FolderOpen />
      </Button>
      <span className="integration-filename" title={filename ?? undefined}>
        {filename?.split(/[\\/]/).at(-1) || `No ${kind} loaded`}
      </span>
      <Button
        type="button"
        aria-label={`Remove ${kind}`}
        title={`Remove ${kind}`}
        disabled={disabled || !filename}
        onClick={onRemove}
      >
        <Trash2 />
      </Button>
    </div>
  );
}

export function ProcessingType({
  label,
  selected,
  active,
  onClick,
}: {
  label: string;
  selected: boolean;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      aria-label={label}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span>{label}</span>
      <span
        className="processing-active"
        data-active={active}
        role="img"
        aria-label={active ? "Active" : "Inactive"}
        title={active ? "Active" : "Inactive"}
      />
    </Button>
  );
}

/** Show an immediate toggle response while keeping the applied state authoritative. */
export function ProcessingToggle({
  label,
  displayLabel,
  checked,
  disabled,
  onCommit,
}: {
  label: string;
  displayLabel?: string;
  checked: boolean;
  disabled?: boolean;
  onCommit: (checked: boolean) => Promise<void>;
}) {
  const [pending, setPending] = useState<boolean | null>(null);
  return (
    <div aria-busy={pending !== null}>
      <Check
        label={label}
        displayLabel={displayLabel}
        checked={pending ?? checked}
        disabled={disabled || pending !== null}
        onChange={(next) => {
          setPending(next);
          void onCommit(next).finally(() => setPending(null));
        }}
      />
    </div>
  );
}
