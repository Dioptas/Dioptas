import type { State } from "./types";

/** A blocked calculation must not leave an old curve looking current. */
export function PatternFreshness({
  state,
  ready,
  onRetry,
}: {
  state: State | null;
  ready: boolean;
  onRetry: () => void;
}) {
  if (!state?.integrationDirty || !state.hasImage || !state.calibrated)
    return null;
  return (
    <span className="pattern-pending" role="status">
      Pattern out of date
      <button
        type="button"
        className="quiet"
        disabled={!ready}
        aria-label="Recalculate current pattern"
        title="Recalculate using the current image, geometry, mask and integration settings"
        onClick={onRetry}
      >
        Recalculate
      </button>
    </span>
  );
}
