import type { ReactNode } from "react";
import "./integrationNumericFields.css";

/** Separate only known unit suffixes; ranges and other parenthetical labels stay intact. */
export function splitNumericLabel(label: string) {
  const suffix = label.match(/\s+\((mm|µm|°|GPa|K|Å|Å⁻¹|Å³|%)\)$/);
  return {
    name: suffix ? label.slice(0, suffix.index) : label,
    unit: suffix?.[1],
  };
}

export function Field({
  label,
  displayLabel,
  value,
  onChange,
  min,
  max,
  step = "any",
  disabled = false,
}: {
  label: string;
  displayLabel?: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number | string;
  disabled?: boolean;
}) {
  const { name, unit } = splitNumericLabel(displayLabel ?? label);
  return (
    <label
      className={`field-label integration-number-field${unit ? " integration-number-with-unit" : ""}`}
    >
      <span>{name}</span>
      <input
        aria-label={label}
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {unit && (
        <span className="integration-number-unit" aria-hidden="true">
          {unit}
        </span>
      )}
    </label>
  );
}
export function Check({
  label,
  displayLabel = label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  displayLabel?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="check-row">
      <input
        aria-label={label}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      {displayLabel}
    </label>
  );
}
export function Group({
  title,
  children,
  open = false,
}: {
  title: string;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="integration-group" open={open}>
      <summary>{title}</summary>
      <div className="integration-group-body">{children}</div>
    </details>
  );
}
export function Sector({
  title,
  value,
  onChange,
}: {
  title: string;
  value: [number, number] | null;
  onChange: (v: [number, number] | null) => void;
}) {
  return (
    <div className="integration-sector">
      <Check
        label={`${title} full range`}
        checked={!value}
        onChange={(full) => onChange(full ? null : [-180, 180])}
      />
      <div className="integration-fields">
        <Field
          label={`${title} minimum (°)`}
          displayLabel="Minimum (°)"
          value={value?.[0] ?? -180}
          disabled={!value}
          min={-180}
          max={180}
          onChange={(v) => onChange([v, value![1]])}
        />
        <Field
          label={`${title} maximum (°)`}
          displayLabel="Maximum (°)"
          value={value?.[1] ?? 180}
          disabled={!value}
          min={-180}
          max={180}
          onChange={(v) => onChange([value![0], v])}
        />
      </div>
    </div>
  );
}
