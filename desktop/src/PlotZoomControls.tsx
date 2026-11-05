import type { ZoomMode } from "./usePlotNavigation";

export function PlotZoomControls({
  mode,
  onChange,
  left,
  bottom,
  label,
  horizontalTitle,
}: {
  mode: ZoomMode;
  onChange: (mode: ZoomMode) => void;
  left: number;
  bottom: number;
  label: string;
  horizontalTitle?: string;
}) {
  return (
    <>
      <button
        className="plot-zoom-button"
        style={{ left: Math.max(8, left - 72), bottom: bottom - 24 }}
        type="button"
        title="Rectangle zoom: select both axes"
        aria-label={`${label} rectangle zoom`}
        aria-pressed={mode === "rectangle"}
        onClick={() => onChange("rectangle")}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden="true"
        >
          <rect x="4" y="5" width="16" height="14" />
        </svg>
      </button>
      <button
        className="plot-zoom-button"
        style={{ left: Math.max(8, left - 72) + 22, bottom: bottom - 24 }}
        type="button"
        title={
          horizontalTitle ??
          (label === "Cake"
            ? "X-range zoom: keep the azimuth range"
            : "X-range zoom: fit intensity to the visible data")
        }
        aria-label={`${label} X-range zoom`}
        aria-pressed={mode === "horizontal"}
        onClick={() => onChange("horizontal")}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden="true"
        >
          <path d="M7 5v14M17 5v14" />
        </svg>
      </button>
    </>
  );
}
