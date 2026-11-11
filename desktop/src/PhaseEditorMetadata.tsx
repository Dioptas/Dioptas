import { useEffect, useRef, useState } from "react";
import { Button, Input, TextArea } from "./ui";
import type { EditorData, EditorEdit } from "./phaseEditorTypes";
import "./phaseEditorMetadata.css";

type RecordData = Record<string, any>;
type Draft = Record<string, string | boolean>;
const ranges = [
  ["experimental_pressure_range_gpa", "Experimental pressure", "GPa"],
  ["experimental_temperature_range_k", "Experimental temperature", "K"],
  ["pressure_gpa", "Validity pressure", "GPa"],
  ["temperature_k", "Validity temperature", "K"],
] as const;
const referenceFields = [
  ["authors", "Authors (separate with semicolons)"],
  ["year", "Year"],
  ["source", "Journal / source"],
  ["volume", "Volume"],
  ["locator", "Pages / article locator"],
  ["doi", "DOI"],
  ["details", "Reference details"],
] as const;
const shown = (value: unknown) =>
  value == null
    ? ""
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
function rows(record: RecordData) {
  return ["eos", "thermal"].flatMap((scope) => {
    const block = scope === "eos" ? record : record.thermal || {};
    return [
      ...new Set([
        ...Object.keys(record[scope]?.parameters || {}),
        ...Object.keys(block.parameter_errors || {}),
        ...(Array.isArray(block.fixed_parameters)
          ? block.fixed_parameters.filter((v: unknown) => typeof v === "string")
          : []),
      ]),
    ]
      .filter((key) => typeof record[scope]?.parameters?.[key] !== "string")
      .map((key) => ({
        scope,
        key,
        value: record[scope]?.parameters?.[key],
        error: block.parameter_errors?.[key],
        fixed: block.fixed_parameters?.includes(key) || false,
      }));
  });
}
function initial(record: RecordData): Draft {
  const ref =
    typeof record.reference === "string"
      ? { details: record.reference }
      : record.reference || {};
  const values: Draft = {
    notes: shown(record.notes),
    temperature_ref: shown(record.temperature_ref),
    "ref.authors_truncated": !!ref.authors_truncated,
  };
  for (const [key] of referenceFields)
    values[`ref.${key}`] =
      key === "authors" && Array.isArray(ref.authors)
        ? ref.authors.join("; ")
        : shown(ref[key]);
  for (const [key] of ranges)
    for (const bound of [0, 1])
      values[`${key}.${bound}`] = shown(
        (key.startsWith("experimental_")
          ? record[key]
          : record.validity?.[key])?.[bound],
      );
  for (const row of rows(record)) {
    values[`${row.scope}.${row.key}.error`] = shown(row.error);
    values[`${row.scope}.${row.key}.fixed`] = row.fixed;
  }
  return values;
}
export function PhaseEditorMetadata({
  data,
  locked,
  act,
  onDirty,
  onReload,
}: {
  data: EditorData;
  locked: boolean;
  act: EditorEdit;
  onDirty: (dirty: boolean) => void;
  onReload: () => Promise<void>;
}) {
  const incoming = data.recordData || {};
  const [baseline, setBaseline] = useState<RecordData>(incoming);
  const [baselineToken, setBaselineToken] = useState(data.recordToken);
  const [draft, setDraft] = useState<Draft>(() => initial(incoming));
  const [error, setError] = useState("");
  const [invalidField, setInvalidField] = useState("");
  const form = useRef<HTMLFormElement>(null);
  const [applying, setApplying] = useState(false);

  const original = initial(baseline);
  const dirty = JSON.stringify(original) !== JSON.stringify(draft);
  const stale = data.recordToken !== baselineToken;
  useEffect(() => {
    if (!dirty) {
      setBaseline(incoming);
      setBaselineToken(data.recordToken);
      setDraft(initial(incoming));
    }
  }, [data.recordToken, dirty]);
  useEffect(() => {
    onDirty(dirty || applying);
  }, [dirty, applying, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  const disabled = locked || applying || !data.eosEditable;
  const update = (key: string, value: string | boolean) => {
    const next = { ...draft, [key]: value };
    setDraft(next);
    onDirty(JSON.stringify(next) !== JSON.stringify(original));
    setError("");
    setInvalidField("");
  };
  const changed = (key: string) => draft[key] !== original[key];
  const input = (key: string, label: string, numeric = false) => (
    <Input
      aria-label={label}
      aria-invalid={invalidField === key || undefined}
      disabled={disabled}
      value={String(draft[key] ?? "")}
      inputMode={numeric ? "decimal" : undefined}
      onChange={(e) => update(key, e.target.value)}
    />
  );
  const reset = () => {
    onDirty(false);
    setBaseline(incoming);
    setBaselineToken(data.recordToken);
    setDraft(initial(incoming));
    setError("");
    setInvalidField("");
    void onReload();
  };
  const apply = async () => {
    const changes: RecordData = {};
    const numeric = (key: string, label: string): number | null => {
      const text = String(draft[key]).trim();
      if (!text) return null;
      const number = Number(text);
      if (!Number.isFinite(number)) {
        setInvalidField(key);
        throw Error(`${label}: enter a finite number, or clear the field.`);
      }
      return number;
    };
    try {
      for (const key of ["notes", "temperature_ref"])
        if (changed(key))
          changes[key] =
            key === "notes"
              ? String(draft[key]).trim()
              : numeric(key, "Reference temperature");
      if (changes.temperature_ref != null && changes.temperature_ref < 0) {
        setInvalidField("temperature_ref");
        throw Error("Reference temperature must be nonnegative (K).");
      }
      const reference: RecordData = {};
      for (const [key] of referenceFields)
        if (changed(`ref.${key}`)) {
          const text = String(draft[`ref.${key}`]).trim();
          if (key === "year") {
            if (text && (!/^\d+$/.test(text) || Number(text) > 9999)) {
              setInvalidField("ref.year");
              throw Error("Year must be an integer from 0 to 9999, or blank.");
            }
            reference[key] = text ? Number(text) : null;
          } else
            reference[key] =
              key === "authors"
                ? text
                    .split(";")
                    .map((v) => v.trim())
                    .filter(Boolean)
                : text;
        }
      if (changed("ref.authors_truncated"))
        reference.authors_truncated = draft["ref.authors_truncated"];
      if (Object.keys(reference).length) changes.reference = reference;
      const rangeChanges: RecordData = {};
      for (const [key, label, unit] of ranges)
        if ([0, 1].some((bound) => changed(`${key}.${bound}`))) {
          const low = numeric(`${key}.0`, label),
            high = numeric(`${key}.1`, label);
          if (low == null && high == null) rangeChanges[key] = null;
          else {
            if (
              low == null ||
              high == null ||
              low > high ||
              (unit === "K" && low < 0)
            ) {
              setInvalidField(`${key}.${low == null ? 0 : 1}`);
              throw Error(
                `${label}: enter ordered minimum and maximum values, or clear both.`,
              );
            }
            rangeChanges[key] = [low, high];
          }
        }
      if (Object.keys(rangeChanges).length) changes.ranges = rangeChanges;
      const parameters = rows(baseline).flatMap((row) => {
        const key = `${row.scope}.${row.key}`,
          result: RecordData = { scope: row.scope, key: row.key };
        if (changed(`${key}.error`))
          result.error = numeric(
            `${key}.error`,
            `${row.key} reported uncertainty`,
          );
        if (changed(`${key}.fixed`)) result.fixed = draft[`${key}.fixed`];
        return Object.keys(result).length > 2 ? [result] : [];
      });
      if (parameters.length) changes.parameters = parameters;
      setApplying(true);
      setError("");
      const accepted = await act("editor_metadata", {
        record_index: data.reference,
        expected_record_token: baselineToken,
        changes,
      });
      if (accepted) {
        // The successful response owns the new baseline; preserve failed drafts for correction.
        onDirty(false);
        setDraft(original);
      } else
        setError(
          "Draft retained. Review the application message, or cancel to reload the current record.",
        );
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      requestAnimationFrame(() => {
        const invalid = form.current?.querySelector<HTMLInputElement>(
          '[aria-invalid="true"]',
        );
        for (
          let ancestor = invalid?.parentElement;
          ancestor;
          ancestor = ancestor.parentElement
        )
          if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
        invalid?.focus();
      });
    } finally {
      setApplying(false);
    }
  };
  const ref =
    typeof baseline.reference === "string"
      ? { details: baseline.reference }
      : baseline.reference || {};
  const citation = [
    Array.isArray(ref.authors)
      ? ref.authors.join(", ") + (ref.authors_truncated ? " et al." : "")
      : "",
    ref.year,
    ref.title,
    ref.source,
    ref.volume,
    ref.locator,
    ref.details,
    ref.doi ? `doi: ${ref.doi}` : "",
  ]
    .filter((v) => v !== "" && v != null)
    .join(" · ");
  return (
    <details
      className="pe-record-details pe-metadata"
      data-dirty={dirty || undefined}
    >
      <summary>
        Publication record
        {dirty && <span className="pe-metadata-draft"> · draft</span>}
        <span className="pe-citation-preview">
          {[
            Array.isArray(ref.authors) && ref.authors.length
              ? `${ref.authors[0]}${ref.authors.length > 1 || ref.authors_truncated ? " et al." : ""}`
              : "",
            ref.year,
          ]
            .filter((v) => v !== "" && v != null)
            .join(" · ") || "Citation, source uncertainties and fit domain"}
        </span>
      </summary>
      <p className="pe-citation">
        {citation || "No literature reference recorded."}
      </p>
      <p>
        {data.eosEditable
          ? "Edit source-record metadata below, then apply or cancel the draft."
          : "Published source is read-only. Use Edit a copy to make changes."}
      </p>
      <form
        ref={form}
        onSubmit={(e) => {
          e.preventDefault();
          void apply();
        }}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            if (dirty && !disabled && !stale) void apply();
          }
        }}
      >
        <details open className="pe-metadata-section">
          <summary>Literature reference</summary>
          <div className="pe-citation-fields">
            {referenceFields
              .filter(([key]) =>
                ["authors", "year", "source", "doi"].includes(key),
              )
              .map(([key, label]) => (
                <label key={key}>
                  {label}
                  {input(`ref.${key}`, label)}
                </label>
              ))}
            <label className="pe-metadata-check">
              <Input
                type="checkbox"
                checked={!!draft["ref.authors_truncated"]}
                disabled={disabled}
                onChange={(e) =>
                  update("ref.authors_truncated", e.target.checked)
                }
              />
              Source lists the first author as et al.
            </label>
          </div>
          <details className="pe-metadata-section">
            <summary>Volume, pages and reference details</summary>
            <div className="pe-citation-fields">
              {referenceFields
                .filter(([key]) =>
                  ["volume", "locator", "details"].includes(key),
                )
                .map(([key, label]) => (
                  <label key={key}>
                    {label}
                    {input(`ref.${key}`, label)}
                  </label>
                ))}
            </div>
          </details>
        </details>
        <details className="pe-metadata-section">
          <summary>Reported uncertainties &amp; fixed parameters</summary>
          <p>
            Reported uncertainties and fixed flags describe the publication,
            independently of live fit constraints. Blank means unspecified; no
            confidence level is assumed. Edit coefficients in the controls
            above.
          </p>
          <div className="pe-publication-parameters">
            <div
              className="pe-publication-row pe-publication-head"
              aria-hidden="true"
            >
              <span>Parameter / value</span>
              <span>Reported uncertainty</span>
              <span>Publication fixed</span>
            </div>
            {rows(baseline).map((row) => (
              <div
                className="pe-publication-row"
                key={`${row.scope}.${row.key}`}
              >
                <div className="pe-publication-value">
                  <span>
                    {row.scope === "eos" ? "EoS" : "Thermal"} · {row.key}
                  </span>
                  <output>
                    {row.value == null ? "unspecified" : shown(row.value)}
                  </output>
                </div>
                {input(
                  `${row.scope}.${row.key}.error`,
                  `${row.scope} ${row.key} reported uncertainty`,
                  true,
                )}
                <label className="pe-metadata-check">
                  <Input
                    type="checkbox"
                    aria-label={`${row.scope} ${row.key} publication fixed`}
                    disabled={disabled}
                    checked={!!draft[`${row.scope}.${row.key}.fixed`]}
                    onChange={(e) =>
                      update(`${row.scope}.${row.key}.fixed`, e.target.checked)
                    }
                  />
                  <span className="pe-fixed-label">Fixed</span>
                </label>
              </div>
            ))}
          </div>
        </details>
        <details className="pe-metadata-section">
          <summary>Experimental &amp; validity ranges</summary>
          <p>
            Experimental ranges describe measured data. Validity ranges describe
            intended use. Clear both bounds to leave a range unspecified.
          </p>
          {ranges.map(([key, label, unit]) => (
            <div className="pe-metadata-range" key={key}>
              <span>
                {label} ({unit})
              </span>
              {input(`${key}.0`, `${label} minimum`, true)}
              <span>to</span>
              {input(`${key}.1`, `${label} maximum`, true)}
            </div>
          ))}
        </details>
        <label className="pe-metadata-temperature">
          Reference temperature (K)
          {input("temperature_ref", "Reference temperature", true)}
        </label>
        <p>
          Reference temperature is a model reference state; changing it can
          change predicted phase volumes. Blank uses the model’s default.
        </p>
        <label className="pe-metadata-notes">
          Record notes
          <TextArea
            aria-label="Record notes"
            rows={3}
            disabled={disabled}
            value={String(draft.notes)}
            onChange={(e) => update("notes", e.target.value)}
          />
        </label>
        {stale && dirty && (
          <p role="alert">
            The record changed outside this draft. Cancel to review its current
            values before editing again.
          </p>
        )}
        {error && (
          <p className="pe-edit-error" role="alert">
            {error}
          </p>
        )}
        {data.eosEditable && (
          <div className="pe-metadata-actions">
            <Button
              type="submit"
              className="primary"
              disabled={disabled || !dirty || stale}
            >
              Apply publication edits
            </Button>
            <Button
              type="button"
              disabled={locked || applying || !dirty}
              onClick={reset}
            >
              Cancel publication edits
            </Button>
            <span role="status">
              {applying
                ? "Applying…"
                : dirty
                  ? "Draft · not yet applied"
                  : "No pending edits"}
            </span>
          </div>
        )}
      </form>
    </details>
  );
}
