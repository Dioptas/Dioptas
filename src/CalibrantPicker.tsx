import { Button, Select } from "./ui";
import { FolderOpen } from "lucide-react";
import type { Calibration } from "./types";

type Run = import("./commandContracts").Run;

/**
 * Calibrant choice plus custom spacings loader, shared by the setup, fit and
 * validation steps. `validation` choices only change reference lines; setup
 * choices may require a refit when ring picks depend on the calibrant.
 */
export function CalibrantPicker({
  calibration: c,
  ready,
  run,
  purpose,
  id,
  iconSize = 16,
}: {
  calibration?: Calibration;
  ready: boolean;
  run: Run;
  purpose: "setup" | "fit" | "validation";
  id?: string;
  iconSize?: number;
}) {
  const validation = purpose === "validation";
  const label = {
    setup: "Setup",
    fit: "Calibration",
    validation: "Validation",
  }[purpose];
  const disabled = !ready || !c;
  return (
    <>
      <Select
        id={id}
        aria-label={`${label} calibrant`}
        disabled={disabled}
        value={c?.calibrant ?? ""}
        onChange={(e) =>
          validation
            ? run(
                "validation_calibrant",
                { calibrant: e.target.value },
                "Updating reference lines…",
              )
            : run(
                "calibration_setup",
                { calibrant: e.target.value },
                "Loading calibrant…",
              )
        }
      >
        {(c?.calibrants ?? []).map((name) => (
          <option key={name}>{name}</option>
        ))}
      </Select>
      <Button
        type="button"
        className="icon-button"
        aria-label={
          {
            setup: "Load custom setup calibrant…",
            fit: "Load custom calibrant…",
            validation: "Load custom validation reference",
          }[purpose]
        }
        title={
          validation
            ? "Load custom reference spacings"
            : "Load custom calibrant spacings (.D)"
        }
        disabled={disabled}
        onClick={() =>
          run(
            "open_calibrant",
            validation ? { validation: true } : {},
            validation
              ? "Loading reference spacings…"
              : "Loading calibrant spacings…",
          )
        }
      >
        <FolderOpen size={iconSize} />
      </Button>
    </>
  );
}
