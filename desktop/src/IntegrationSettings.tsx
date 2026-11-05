import { useEffect, useState, useRef, useCallback } from "react";
import type { State } from "./types";
import type { IntegrationRun, IntegrationState } from "./integration";
import { Check, Field, Group, Sector } from "./IntegrationFields";
import "./integration.css";

const optionKeys = [
  "automaticBinning",
  "supersampling",
  "azimuthRange",
  "cakeAzimuthRange",
  "cakeBins",
  "solidAngle",
  "poissonErrors",
  "polarization",
  "trimZeros",
] as const;
const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);
const optionsPayload = (
  source: IntegrationState | undefined,
  bins: number,
  unit: State["unit"],
) =>
  source
    ? {
        unit,
        bins: source.automaticBinning ? null : bins,
        supersampling: source.supersampling,
        azimuth_range: source.azimuthRange,
        cake_azimuth_range: source.cakeAzimuthRange,
        cake_bins: source.cakeBins,
        solid_angle: source.solidAngle,
        poisson_errors: source.poissonErrors,
        polarization: source.polarization,
        trim_zeros: source.trimZeros,
      }
    : {};

export function useIntegrationSettingsDraft(state: State | null) {
  const source = state?.integration;
  const currentBins = state?.bins ?? source?.actualBins ?? 0;
  const currentUnit = state?.unit ?? "2th_deg";
  const [draft, setDraft] = useState(source);
  const [bins, setBins] = useState(currentBins);
  const [unit, setUnit] = useState(currentUnit);
  const baseline = useRef({ source, bins: currentBins, unit: currentUnit });
  const sourceKey = JSON.stringify(
    optionsPayload(source, currentBins, currentUnit),
  );
  const sync = useCallback((next: State | null) => {
    if (!next) return;
    const count = next.bins ?? next.integration.actualBins;
    baseline.current = {
      source: next.integration,
      bins: count,
      unit: next.unit,
    };
    setDraft(next.integration);
    setBins(count);
    setUnit(next.unit);
  }, []);
  useEffect(() => {
    if (!source) return;
    const old = baseline.current;
    // Rebase unedited fields onto the latest model, retaining only deliberate
    // local edits. A plot-unit toggle must not be undone by a pending bin edit.
    setDraft((previous) => {
      if (!previous || !old.source) return source;
      const retained = Object.fromEntries(
        optionKeys
          .filter((key) => !same(previous[key], old.source![key]))
          .map((key) => [key, previous[key]]),
      );
      return { ...source, ...retained };
    });
    setBins((previous) =>
      previous !== old.bins ||
      (draft &&
        old.source &&
        draft.automaticBinning !== old.source.automaticBinning)
        ? previous
        : currentBins,
    );
    setUnit((previous) => (previous !== old.unit ? previous : currentUnit));
    baseline.current = { source, bins: currentBins, unit: currentUnit };
  }, [sourceKey]);
  useEffect(() => {
    if (draft?.automaticBinning && source) setBins(source.actualBins);
  }, [source?.actualBins, draft?.automaticBinning]);
  const values = optionsPayload(draft, bins, unit);
  const current = optionsPayload(source, currentBins, currentUnit);
  const changes = Object.fromEntries(
    Object.entries(values).filter(
      ([key, value]) => !same(value, current[key as keyof typeof current]),
    ),
  );
  return {
    draft,
    bins,
    unit,
    setDraft,
    setBins,
    setUnit,
    dirty: Object.keys(changes).length > 0,
    changes,
    sync,
  };
}
export type IntegrationSettingsDraft = ReturnType<
  typeof useIntegrationSettingsDraft
>;

export function IntegrationSettings({
  editor,
  state,
  ready,
  run,
}: {
  editor: IntegrationSettingsDraft;
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
}) {
  const source = state?.integration;
  const {
    draft,
    bins,
    unit,
    setDraft,
    setBins,
    setUnit,
    dirty,
    changes,
    sync,
  } = editor;
  if (!source || !draft) return null;
  const set = <K extends keyof IntegrationState>(
    key: K,
    value: IntegrationState[K],
  ) => setDraft((current) => current && { ...current, [key]: value });
  const settings = () =>
    void run(
      "integration_settings",
      changes,
      "Applying integration options…",
      (result) => sync(result.state ?? null),
    );
  return (
    <form
      className="integration-settings-container"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && dirty) settings();
      }}
    >
      <fieldset disabled={!ready} className="integration-settings">
        <Group title="Integration" open>
          <label className="field-label">
            Radial coordinate
            <select
              aria-label="Radial coordinate"
              value={unit}
              onChange={(e) => setUnit(e.target.value as State["unit"])}
            >
              <option value="2th_deg">2θ · degrees</option>
              <option value="q_A^-1">Q · Å⁻¹</option>
              <option value="d_A">d · Å</option>
            </select>
          </label>
          <Check
            label="Automatic radial binning"
            checked={draft.automaticBinning}
            onChange={(v) => set("automaticBinning", v)}
          />
          <Field
            label="Radial bins"
            value={draft.automaticBinning ? source.actualBins : bins}
            disabled={draft.automaticBinning}
            min={1}
            max={100000}
            step={1}
            onChange={setBins}
          />
          <p className="integration-note">
            Current integration: {source.actualBins} bins
          </p>
          <Field
            label="Supersampling"
            value={draft.supersampling}
            min={1}
            max={20}
            step={1}
            onChange={(v) => set("supersampling", v)}
          />
          <Sector
            title="1D azimuth"
            value={draft.azimuthRange}
            onChange={(v) => set("azimuthRange", v)}
          />
          <p className="integration-note">
            Minimum &gt; maximum selects a sector across ±180°.
          </p>
          <Check
            label="Trim trailing zeros"
            checked={draft.trimZeros}
            onChange={(v) => set("trimZeros", v)}
          />
        </Group>
        <Group title="Cake" open>
          <Field
            label="Cake azimuth bins"
            value={draft.cakeBins}
            min={1}
            max={10000}
            step={1}
            onChange={(v) => set("cakeBins", v)}
          />
          <Sector
            title="Cake azimuth"
            value={draft.cakeAzimuthRange}
            onChange={(v) => set("cakeAzimuthRange", v)}
          />
          <p className="integration-note">
            Cake radial axis uses 2θ (°), independent of the pattern coordinate.
          </p>
        </Group>
        <Group title="Integration corrections" open>
          <Check
            label="Correct solid angle"
            checked={draft.solidAngle}
            onChange={(v) => set("solidAngle", v)}
          />
          <Check
            label="Calculate Poisson errors"
            checked={draft.poissonErrors}
            onChange={(v) => set("poissonErrors", v)}
          />
          <Field
            label="Polarization factor"
            value={draft.polarization}
            min={-1}
            max={1}
            onChange={(v) => set("polarization", v)}
          />
        </Group>
      </fieldset>
      <div className="settings-apply-bar">
        <p>
          {dirty
            ? "Unapplied changes are kept when you leave Settings. Apply to recalculate."
            : "Binning, ranges and corrections match the current project."}
        </p>
        <button type="submit" className="primary" disabled={!ready || !dirty}>
          Apply integration options
        </button>
      </div>
    </form>
  );
}
