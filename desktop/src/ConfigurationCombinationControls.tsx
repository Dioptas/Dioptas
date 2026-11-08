import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { Button, Input, Select } from "./ui";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";
import "./configurationCombination.css";

/** Qt's configuration factor and combined-result controls; images stay separate. */
export function ConfigurationCombinationControls({
  state,
  ready,
  run,
  showSelector = true,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
  showSelector?: boolean;
}) {
  const combination = state?.combination;
  const [factor, setFactor] = useState(String(combination?.factor ?? 1));
  useEffect(
    () => setFactor(String(combination?.factor ?? 1)),
    [combination?.factor, state?.configurationIndex],
  );
  if (!state || !combination || state.configurationCount < 2) return null;
  const update = (args: Record<string, unknown>) =>
    void run("combination_settings", args, "Combining detectors…");
  const commit = () => {
    const value = Number(factor);
    if (factor.trim() && Number.isFinite(value) && value !== combination.factor)
      update({ factor: value });
    else setFactor(String(combination.factor));
  };
  return (
    <div
      className="configuration-combination"
      role="group"
      aria-label="Detector configurations"
    >
      {showSelector && (
        <label className="configuration-choice">
          Configuration
          <Select
            aria-label="Configuration"
            value={state.configurationIndex}
            disabled={!ready}
            onChange={(e) =>
              void run(
                "configuration_select",
                { index: Number(e.target.value) },
                "Switching detector…",
              )
            }
          >
            {combination.configurations.map((c) => (
              <option key={c.index} value={c.index}>
                {c.index + 1}
                {c.imageName ? ` · ${c.imageName}` : ""}
              </option>
            ))}
          </Select>
        </label>
      )}
      <>
        <label className="configuration-factor">
          Factor
          <Input
            aria-label="Detector factor"
            type="number"
            step="any"
            value={factor}
            disabled={!ready}
            onChange={(e) => setFactor(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") setFactor(String(combination.factor));
            }}
          />
        </label>
        <Button
          aria-pressed={combination.patterns}
          disabled={!ready || (!combination.ready && !combination.patterns)}
          title={
            combination.reason ??
            `Combine integrated patterns from all detector configurations${combination.backends.pattern ? ` · ${combination.backends.pattern}` : ""}`
          }
          onClick={() => update({ patterns: !combination.patterns })}
        >
          Combine patterns
        </Button>
        <Button
          aria-label="Save combined pattern"
          title="Save combined pattern"
          className="configuration-save"
          disabled={
            !ready ||
            !combination.ready ||
            !combination.patterns ||
            state.integrationDirty
          }
          onClick={() =>
            void run(
              "save_combined_pattern",
              {
                suggested_name: `${state.imageName?.replace(/\.[^.]+$/, "") || "pattern"}_combined.xy`,
              },
              "Saving combined pattern…",
            )
          }
        >
          <Save size={17} />
        </Button>
        <Button
          aria-pressed={combination.cakes}
          disabled={!ready || (!combination.ready && !combination.cakes)}
          title={
            combination.reason ??
            `Merge calibrated 2D cakes from all detector configurations${combination.backends.cake ? ` · ${combination.backends.cake}` : ""}`
          }
          onClick={() => update({ cakes: !combination.cakes })}
        >
          Combined cake
        </Button>
        {combination.reason && (
          <span className="configuration-reason">{combination.reason}</span>
        )}
      </>
    </div>
  );
}
