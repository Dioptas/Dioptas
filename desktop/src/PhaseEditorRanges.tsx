import { Button, Input } from "./ui";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { EditorData, EditorEdit } from "./phaseEditorTypes";

const rows = [
  ["experimental_pressure_range_gpa", "Experimental pressure", "GPa"],
  ["experimental_temperature_range_k", "Experimental temperature", "K"],
  ["pressure_gpa", "Validity pressure", "GPa"],
  ["temperature_k", "Validity temperature", "K"],
] as const;
type Draft = Record<string, [string, string]>;

export function PhaseEditorRanges({
  data,
  locked,
  act,
  onDirty,
}: {
  data: EditorData;
  locked: boolean;
  act: EditorEdit;
  onDirty: (dirty: boolean) => void;
}) {
  const record = data.recordData || {};
  const validity = (record.validity || {}) as Record<string, unknown>;
  const initial = Object.fromEntries(
    rows.map(([key]) => {
      const values = (
        key.startsWith("experimental_") ? record[key] : validity[key]
      ) as number[] | undefined;
      return [key, values ? values.map(String) : ["", ""]];
    }),
  ) as Draft;
  const signature = JSON.stringify(initial);
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState("");
  const [applying, setApplying] = useState(false);
  const dirty = JSON.stringify(draft) !== signature;
  useEffect(() => {
    setDraft(initial);
    setError("");
  }, [signature]);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  const disabled = locked || !data.eosEditable || applying;
  const apply = async () => {
    const ranges: Record<string, number[] | null> = {};
    for (const [key, label] of rows) {
      const values = draft[key].map((value) => value.trim());
      if (values.every((value) => !value)) {
        ranges[key] = null;
        continue;
      }
      const numbers = values.map(Number);
      if (
        values.some((value) => !value) ||
        numbers.some((value) => !Number.isFinite(value)) ||
        numbers[0] > numbers[1] ||
        (key.includes("temperature") && numbers[0] < 0)
      ) {
        setError(
          `${label}: enter an ordered minimum and maximum, or clear both limits.`,
        );
        return;
      }
      ranges[key] = numbers;
    }
    setError("");
    setApplying(true);
    try {
      await act("editor_ranges", { ranges });
    } finally {
      setApplying(false);
    }
  };
  return (
    <details className="pe-record-details pe-ranges">
      <summary>Experimental &amp; validity ranges</summary>
      <p>
        Experimental ranges describe the measured data. Validity ranges describe
        intended use. Clear both limits to leave a range unspecified.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void apply();
        }}
      >
        {rows.map(([key, label, unit], index) => (
          <div className="pe-range-row" key={key}>
            <span>
              {index % 2 === 0
                ? label.replace(" pressure", " P")
                : label.replace(" temperature", " T")}
            </span>
            {[0, 1].map((bound) => (
              <Input
                key={bound}
                type="number"
                step="any"
                aria-label={`${label} ${bound ? "maximum" : "minimum"}`}
                placeholder={bound ? "max" : "min"}
                disabled={disabled}
                min={unit === "K" ? 0 : undefined}
                value={draft[key][bound]}
                onChange={(event) => {
                  const values = [...draft[key]] as [string, string];
                  values[bound] = event.target.value;
                  setDraft({ ...draft, [key]: values });
                  setError("");
                }}
              />
            ))}
            <span className="pe-unit">{unit}</span>
            <Button
              type="button"
              disabled={disabled || draft[key].every((value) => !value)}
              aria-label={`Clear ${label.toLowerCase()} range`}
              title={`Clear ${label.toLowerCase()} range`}
              onClick={() => {
                setDraft({ ...draft, [key]: ["", ""] });
                setError("");
              }}
            >
              <X aria-hidden="true" />
            </Button>
          </div>
        ))}
        {error && (
          <div className="pe-edit-error" role="alert">
            {error}
          </div>
        )}
        {data.eosEditable && (
          <div className="pe-range-actions">
            <Button type="submit" disabled={disabled || !dirty}>
              Apply ranges
            </Button>
            <Button
              type="button"
              disabled={disabled || !dirty}
              onClick={() => {
                setDraft(initial);
                setError("");
              }}
            >
              Reset range edits
            </Button>
          </div>
        )}
      </form>
    </details>
  );
}
