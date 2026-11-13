import { Input } from "./ui";
import { useEffect, useRef, useState } from "react";

export function BackgroundNumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = "any",
  hideLabel = false,
}: {
  hideLabel?: boolean;
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number | "any";
}) {
  const input = useRef<HTMLInputElement>(null);
  const format = (number: number) =>
    !hideLabel || !number
      ? String(number)
      : Math.abs(number) < 1e-8
        ? number.toExponential(2)
        : String(Number(number.toPrecision(10)));
  const [text, setText] = useState(format(value));
  useEffect(() => {
    if (document.activeElement !== input.current) setText(format(value));
  }, [value]);
  return (
    <label className="field-label">
      {!hideLabel && label}
      <Input
        ref={input}
        aria-label={label}
        title={String(value)}
        type="number"
        step={step}
        min={min}
        max={max}
        value={text}
        onChange={(event) => {
          const next = event.currentTarget.value;
          setText(next);
          if (
            next.trim() &&
            Number.isFinite(Number(next)) &&
            event.currentTarget.validity.valid
          )
            onChange(Number(next));
        }}
        onBlur={() => setText(format(value))}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
    </label>
  );
}

export function BackgroundRangeFields({
  range,
  onChange,
  unit,
}: {
  unit?: string;
  range: [number, number];
  onChange: (range: [number, number]) => void;
}) {
  const [draft, setDraft] = useState(range);
  useEffect(() => setDraft(range), [range[0], range[1]]);
  const change = (next: [number, number]) => {
    setDraft(next);
    if (next[0] < next[1]) onChange(next);
  };
  const invalid = draft[0] >= draft[1];
  return (
    <div className={unit ? "processing-range" : "integration-fields"}>
      <BackgroundNumberField
        label="Background minimum"
        hideLabel={!!unit}
        value={draft[0]}
        onChange={(value) => change([value, draft[1]])}
      />
      {unit && <span aria-hidden="true">–</span>}
      <BackgroundNumberField
        label="Background maximum"
        hideLabel={!!unit}
        value={draft[1]}
        onChange={(value) => change([draft[0], value])}
      />
      {unit && <span className="processing-range-unit">{unit}</span>}
      {invalid && (
        <span className="processing-range-error" role="alert">
          Minimum must be below maximum.
        </span>
      )}
    </div>
  );
}
