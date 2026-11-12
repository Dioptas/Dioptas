import { useRef } from "react";
import { createPhaseCommandQueue } from "./phaseCommandQueue";
import { Input } from "./ui";
import { PhaseNumber } from "./PhaseNumber";
import type { IntegrationRun, IntegrationState } from "./integration";
import "./dacThermalPressureControls.css";

export function DacThermalPressureControls({
  source,
  ready,
  run,
}: {
  source: IntegrationState;
  ready: boolean;
  run: IntegrationRun;
}) {
  const latestRun = useRef(run);
  latestRun.current = run;
  const queue = useRef<IntegrationRun | null>(null);
  if (!queue.current)
    queue.current = createPhaseCommandQueue(() => latestRun.current);
  const enabled = source.phaseColdPressure;
  const set = (args: { enabled?: boolean; factor?: number }) =>
    queue.current!(
      "integration_phase",
      { operation: "dac_thermal_pressure", ...args },
      "Updating DAC thermal pressure…",
    );
  return (
    <div
      className="phase-dac-controls"
      role="group"
      aria-label="DAC thermal pressure settings"
    >
      <div className="phase-dac-fields">
        <label title="Predict heated volumes from cold/reference pressure with DAC confinement. Applies to all phases in every configuration.">
          <Input
            type="checkbox"
            aria-label="DAC thermal pressure"
            checked={enabled}
            disabled={!ready}
            onChange={(e) => void set({ enabled: e.target.checked })}
          />
          DAC thermal pressure
        </label>
        <label title="Dimensionless fraction of the thermal-pressure increase retained by confinement. 0.25 retains 25%; 0 gives constant-pressure heating. Allowed range: 0 ≤ fraction < 1.">
          <span>Fraction</span>
          <PhaseNumber
            label="DAC thermal-pressure fraction"
            value={source.phaseDacThermalPressureFactor ?? 0.25}
            disabled={!ready || !enabled}
            min={0}
            max={0.9999}
            step={0.01}
            onCommit={(factor) => set({ factor })}
          />
        </label>
      </div>
      <p className="phase-dac-note">
        {enabled
          ? "Enter cold/reference P₀; choose the hot temperature."
          : "Off: enter the measured pressure P."}{" "}
        The dimensionless fraction scales the retained thermal-pressure increase
        in compatible thermal EoS models, relative to their reference
        temperature. Legacy thermal coefficients are unchanged.
      </p>
    </div>
  );
}
