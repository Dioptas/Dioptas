import type { State } from "./types";
import { scientificValue } from "./ScientificNumberInput";

/** Expose the model's provenance, never infer a fit from a loaded geometry. */
export function GeometryProvenance({
  state,
  detail = false,
}: {
  state: State | null;
  detail?: boolean;
}) {
  if (!state?.calibrated) return null;
  const c = state.calibration;
  const source =
    (
      {
        fitted: "Fitted geometry",
        loaded: "Loaded geometry",
        manual: "Manual geometry",
      } as Record<string, string>
    )[c.geometrySource] ?? "Geometry";
  const points = c.picks.reduce(
    (total, group) => total + group.points.length,
    0,
  );
  const rings = new Set(c.picks.map((group) => group.ring)).size;
  return (
    <div
      className={`geometry-provenance${detail ? " calibration-provenance" : ""}`}
      role="group"
      aria-label="Calibration provenance"
    >
      <strong>{source}</strong>
      {state.calibrationName && state.calibrationName !== "current" && (
        <span className="geometry-source-file" title={state.calibrationName}>
          {state.calibrationName.split(/[\\/]/).at(-1)}
        </span>
      )}
      {detail && (
        <>
          <span title={String(state.geometry.wavelength * 1e10)}>
            λ {scientificValue(state.geometry.wavelength * 1e10)} Å
          </span>
          {c.geometrySource === "fitted" && (
            <span>
              {points} points · {rings} rings · {c.freeParameterCount} free
              parameters
            </span>
          )}
          <span>
            {c.rmsDegrees != null
              ? `RMS Δ2θ ${scientificValue(c.rmsDegrees, 4)}°`
              : "Fit residual unavailable · no fitted peak residuals"}
          </span>
          {c.fitDirty && (
            <span>Peak selections changed · refit before saving</span>
          )}
        </>
      )}
    </div>
  );
}
