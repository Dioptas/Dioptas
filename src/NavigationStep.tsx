import { useEffect, useState } from "react";
import { Input } from "./ui";

/** File/frame steps are local preferences; invalid drafts restore the last valid step. */
export function NavigationStep({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  return (
    <label className="integration-file-step" title={label}>
      Step
      <Input
        className="numeric-stepper"
        type="number"
        aria-label={label}
        value={draft}
        min={1}
        max={100000}
        step={1}
        style={{
          width: `max(64px, calc(${Math.max(String(value).length, draft.length)}ch + 30px))`,
        }}
        onChange={(event) => {
          setDraft(event.target.value);
          const next = Number(event.target.value);
          if (Number.isInteger(next) && next >= 1 && next <= 100000)
            onChange(next);
        }}
        onBlur={() => setDraft(String(value))}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            setDraft(String(value));
          }
        }}
      />
    </label>
  );
}
