import { Button } from "./ui";
import { CircleHelp, Download } from "lucide-react";
import { useId, useState } from "react";
import { Check } from "./IntegrationFields";
import type { State } from "./types";

export function SpottinessControls({
  state,
  action,
}: {
  state: State;
  action: import("./commandContracts").CommandAction;
}) {
  const source = state.integration;
  const combined = state.combination?.patterns;
  const [helpOpen, setHelpOpen] = useState(false);
  const helpId = useId();
  return (
    <div className="spottiness-controls" role="group" aria-label="Spottiness">
      <Check
        label="Show Spottiness"
        checked={!!source.azimuthalStd}
        onChange={(enabled) =>
          action("integration_settings", { azimuthal_std: enabled })
        }
      />
      {source.azimuthalStd && (
        <>
          <Check
            label="Relative spread (std / mean)"
            displayLabel="Relative (std / mean)"
            checked={!!source.spottinessRelative}
            onChange={(relative) =>
              action("integration_settings", { spottiness_relative: relative })
            }
          />
          <Button
            className="spottiness-save"
            aria-label="Save Spottiness…"
            title="Save Spottiness…"
            disabled={!source.spottinessAvailable}
            onClick={() =>
              action("integration_save_spottiness", {
                directory: source.outputDirectory,
                suggested_name: `${source.patternName || "pattern"}_spottiness.csv`,
              })
            }
          >
            <Download size={16} aria-hidden="true" />
          </Button>
        </>
      )}
      <Button
        className="spottiness-help"
        aria-label="About Spottiness"
        aria-expanded={helpOpen}
        aria-controls={helpId}
        title="About Spottiness"
        onClick={() => setHelpOpen((open) => !open)}
      >
        <CircleHelp size={16} aria-hidden="true" />
      </Button>
      <p id={helpId} hidden={!helpOpen} className="spottiness-explanation">
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
