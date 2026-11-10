import { Select } from "./ui";
import { useEffect, useState, useRef, useCallback } from "react";
import type { State } from "./types";
import type { IntegrationRun, IntegrationState } from "./integration";
import { Check, Field, Group, Sector } from "./IntegrationFields";
import "./integration.css";

const optionKeys = [
  "automaticBinning",
  "supersampling",
  "method",
  "sparseLayout",
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
        ...(source.method ? { method: source.method } : {}),
        ...(source.sparseLayout ? { sparse_layout: source.sparseLayout } : {}),
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
  const rebased =
    sourceKey ===
    JSON.stringify(
      optionsPayload(
        baseline.current.source,
        baseline.current.bins,
        baseline.current.unit,
      ),
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
    rebased,
  };
}
export type IntegrationSettingsDraft = ReturnType<
  typeof useIntegrationSettingsDraft
>;

/** Lives with the session so leaving Settings cannot discard a committed edit. */
export function useIntegrationSettingsAutoApply(
  editor: IntegrationSettingsDraft,
  ready: boolean,
  run: IntegrationRun,
) {
  const attempted = useRef("");
  const key = JSON.stringify(editor.changes);
  useEffect(() => {
    if (!editor.rebased) return;
    if (!editor.dirty) {
      attempted.current = "";
      return;
    }
    if (!ready || attempted.current === key) return;
    attempted.current = key;
    // Rebase responses through the draft hook; a response must not erase an
    // edit made while this command was waiting for the processor.
    void run("integration_settings", editor.changes, "Updating integration…");
  }, [key, editor.dirty, editor.rebased, ready, run]);
}

export function IntegrationSettings({
  editor,
  state,
  ready,
}: {
  editor: IntegrationSettingsDraft;
  state: State | null;
  ready: boolean;
}) {
  const source = state?.integration;
  const { draft, bins, unit, setDraft, setBins, setUnit } = editor;
  if (!source || !draft) return null;
  const set = <K extends keyof IntegrationState>(
    key: K,
    value: IntegrationState[K],
  ) => setDraft((current) => current && { ...current, [key]: value });
  return (
    <form
      className="integration-settings-container"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <fieldset disabled={!ready} className="integration-settings">
        <Group title="Integration" open>
          <label className="field-label">
            Radial coordinate
            <Select
              aria-label="Radial coordinate"
              value={unit}
              onChange={(e) => setUnit(e.target.value as State["unit"])}
            >
              <option value="2th_deg">2θ · degrees</option>
              <option value="q_A^-1">Q · Å⁻¹</option>
              <option value="d_A">d · Å</option>
            </Select>
          </label>
          <Check
            label="Automatic radial binning"
            checked={draft.automaticBinning}
            onChange={(v) => set("automaticBinning", v)}
          />
          <Field
            commitOnBlur
            label="Radial bins"
            value={draft.automaticBinning ? source.actualBins : bins}
            disabled={draft.automaticBinning}
            min={1}
            max={100000}
            step={1}
            onChange={setBins}
          />
          <label className="field-label">
            Integration method
            <Select
              aria-label="Integration method"
              value={
                draft.method ??
                (draft.supersampling > 1 ? "subpixel" : "polygon")
              }
              onChange={(e) => {
                const method = e.target.value as IntegrationState["method"];
                setDraft(
                  (current) =>
                    current && {
                      ...current,
                      ...(source.method ? { method } : {}),
                      supersampling:
                        method === "subpixel"
                          ? Math.max(2, current.supersampling)
                          : 1,
                    },
                );
              }}
            >
              <option value="polygon">Pixel splitting (polygon)</option>
              {source.method && (
                <option value="pyfai_full">
                  Pixel splitting (pyFAI-compatible)
                </option>
              )}
              <option value="subpixel">Subpixel sampling</option>
            </Select>
          </label>
          {draft.supersampling > 1 && (
            <Field
              commitOnBlur
              label="Subpixels per axis"
              value={draft.supersampling}
              min={2}
              max={20}
              step={1}
              onChange={(v) => set("supersampling", v)}
            />
          )}
          <p className="integration-note">
            {draft.method === "pyfai_full"
              ? "pyFAI-compatible full pixel splitting for the 1D pattern and cake. Approximate compatibility, including range and boundary conventions."
              : draft.supersampling > 1
                ? `Choose 2–20 subpixels per axis (4–400 sample positions per pixel). Current sampling: ${draft.supersampling} × ${draft.supersampling}.`
                : "Each pixel contributes to bins by its fractional polygon overlap. This method has no sampling factor."}
          </p>
          <Sector
            commitOnBlur
            title="1D azimuth"
            value={draft.azimuthRange}
            onChange={(v) => set("azimuthRange", v)}
          />
          <p className="integration-note">
            Minimum &gt; maximum selects a sector across ±180°.
          </p>
          {source.sparseLayout && (
            <>
              <label className="field-label">
                1D execution layout
                <Select
                  aria-label="1D execution layout"
                  value={draft.sparseLayout ?? "csc"}
                  disabled={draft.method === "pyfai_full"}
                  onChange={(e) =>
                    set(
                      "sparseLayout",
                      e.target.value as IntegrationState["sparseLayout"],
                    )
                  }
                >
                  <option value="csc">Pixel-oriented (CSC)</option>
                  <option value="csr">Bin-oriented (CSR)</option>
                  <option value="auto">Automatic · size estimate</option>
                </Select>
              </label>
              <p className="integration-note">
                {draft.method === "pyfai_full"
                  ? "pyFAI-compatible splitting uses its own CSR path. This control applies to polygon and subpixel 1D patterns."
                  : draft.sparseLayout === "auto"
                    ? "Uses CSR, except for images above about 8 MP with 2,000+ bins and no Poisson errors. This is a broad estimate, with no timing probes. Streamed and parallel batch workers retain CSC."
                    : "CSR is usually faster. CSC can help large detectors at low bin counts, or high bin counts without Poisson errors. The splitting weights stay the same; rounding can differ. Streamed batch workers retain CSC. Cakes use their own layout."}
              </p>
            </>
          )}
          <Check
            label="Trim leading and trailing zeros"
            checked={draft.trimZeros}
            onChange={(v) => set("trimZeros", v)}
          />
        </Group>
        <Group title="Cake" open>
          <Field
            commitOnBlur
            label="Cake azimuth bins"
            value={draft.cakeBins}
            min={1}
            max={10000}
            step={1}
            onChange={(v) => set("cakeBins", v)}
          />
          <Sector
            commitOnBlur
            title="Cake azimuth"
            value={draft.cakeAzimuthRange}
            onChange={(v) => set("cakeAzimuthRange", v)}
          />
          <p className="integration-note">
            Cake follows the 2θ or Q selection. Selecting d keeps the last cake
            axis. Text/data exports retain the source radial grid.
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
          <p className="integration-note">
            Counting uncertainty is propagated from original counts through
            image processing and squared integration weights. Geometry and
            correction calibration uncertainties are excluded; split bins can be
            correlated.
          </p>
          <Field
            commitOnBlur
            label="Polarization factor"
            value={draft.polarization}
            min={-1}
            max={1}
            onChange={(v) => set("polarization", v)}
          />
        </Group>
      </fieldset>
    </form>
  );
}
