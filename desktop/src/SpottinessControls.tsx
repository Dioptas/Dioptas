import { Button } from "./ui";
import { Check } from "./IntegrationFields";
import type { State } from "./types";

export function SpottinessControls({
  state,
  action,
}: {
  state: State;
  action: (command: string, args?: Record<string, unknown>) => void;
}) {
  const source = state.integration;
  const combined = state.combination?.patterns;
  return (
    <div className="spottiness-controls" role="group" aria-label="Spottiness">
      <Check
        label="Show Spottiness"
        checked={!!source.azimuthalStd}
        onChange={(enabled) =>
          action("integration_settings", { azimuthal_std: enabled })
        }
      />
      <Check
        label="Relative spread (std / mean)"
        checked={!!source.spottinessRelative}
        disabled={!source.azimuthalStd}
        onChange={(relative) =>
          action("integration_settings", { spottiness_relative: relative })
        }
      />
      <Button
        disabled={!source.spottinessAvailable}
        onClick={() =>
          action("integration_save_spottiness", {
            directory: source.outputDirectory,
            suggested_name: `${source.patternName || "pattern"}_spottiness.csv`,
          })
        }
      >
        Save Spottiness…
      </Button>
      <p className="spottiness-explanation">
        Population azimuthal std of the corrected image; separate from Poisson
        counting errors. Pattern background subtraction does not change these
        observables.
      </p>
      {source.azimuthalStd && !source.spottinessAvailable && (
        <p role="status" className="spottiness-explanation">
          {combined
            ? "Azimuthal std is unavailable for combined patterns. Disable Combine patterns to inspect one detector."
            : "Azimuthal std is unavailable. Integrate an image with a calibration; imported patterns do not provide this statistic."}
        </p>
      )}
    </div>
  );
}
