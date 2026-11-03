import { useEffect, useRef, useState } from "react";

export function BackgroundNumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = "any",
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number | "any";
}) {
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState(String(value));
  useEffect(() => {
    if (document.activeElement !== input.current) setText(String(value));
  }, [value]);
  return (
    <label className="field-label">
      {label}
      <input
        ref={input}
        aria-label={label}
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
        onBlur={() => setText(String(value))}
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
}: {
  range: [number, number];
  onChange: (range: [number, number]) => void;
}) {
  return (
    <div className="integration-fields">
      <BackgroundNumberField
        label="Background minimum"
        value={range[0]}
        onChange={(value) => onChange([value, range[1]])}
      />
      <BackgroundNumberField
        label="Background maximum"
        value={range[1]}
        onChange={(value) => onChange([range[0], value])}
      />
    </div>
  );
}
