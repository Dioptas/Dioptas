import { Button, Select } from "./ui";
import { useEffect, useState } from "react";
import type { State } from "./types";
import type { IntegrationRun, IntegrationState } from "./integration";
import { Check, Field, Group, Sector } from "./IntegrationFields";
import "./integration.css";

export function IntegrationSettings({
  state,
  ready,
  run,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
}) {
  const source = state?.integration;
  const [draft, setDraft] = useState(source);
  const [bins, setBins] = useState(state?.bins ?? source?.actualBins ?? 0);
  useEffect(() => {
    setDraft(source);
    setBins(state?.bins ?? source?.actualBins ?? 0);
  }, [state?.revision, source]);
  if (!source || !draft) return null;
  const set = <K extends keyof IntegrationState>(
    key: K,
    value: IntegrationState[K],
  ) => setDraft((current) => current && { ...current, [key]: value });
  const action = (command: string, args: Record<string, unknown>) =>
    void run(command, args, "Updating integration…");
  const settings = () =>
    action("integration_settings", {
      bins: draft.automaticBinning ? null : bins,
      supersampling: draft.supersampling,
      azimuth_range: draft.azimuthRange,
      cake_azimuth_range: draft.cakeAzimuthRange,
      cake_bins: draft.cakeBins,
      solid_angle: draft.solidAngle,
      poisson_errors: draft.poissonErrors,
      polarization: draft.polarization,
      trim_zeros: draft.trimZeros,
    });
  return (
    <div className="integration-settings-container">
      <fieldset disabled={!ready} className="integration-settings">
        <Group title="Integration" open>
          <label className="field-label">
            Radial coordinate
            <Select
              aria-label="Radial coordinate"
              value={state?.unit ?? "2th_deg"}
              onChange={(e) =>
                action("integration_settings", { unit: e.target.value })
              }
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
            Cake radial axis remains 2θ, following Qt's configuration model.
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
        <p>Apply binning, ranges and corrections to the current project.</p>
        <Button variant="primary" disabled={!ready} onClick={settings}>
          Apply integration options
        </Button>
      </div>
    </div>
  );
}
