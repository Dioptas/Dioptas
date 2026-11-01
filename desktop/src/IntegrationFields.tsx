import type { ReactNode } from "react";

export function Field({
  label,
  value,
  onChange,
  min,
  max,
  step = "any",
  disabled = false,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number | string;
  disabled?: boolean;
}) {
  return (
    <label className="field-label">
      {label}
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
    </label>
  );
}
export function Check({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
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
      {label}
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
          value={value?.[0] ?? -180}
          disabled={!value}
          min={-180}
          max={180}
          onChange={(v) => onChange([v, value![1]])}
        />
        <Field
          label={`${title} maximum (°)`}
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
