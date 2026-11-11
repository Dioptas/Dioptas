import { Button } from "./ui";
import type { ZoomMode } from "./usePlotNavigation";

export function PlotZoomControls({
  mode,
  onChange,
  left,
  bottom,
  label,
  horizontalTitle,
  sliceDirection = "horizontal",
}: {
  mode: ZoomMode;
  onChange: (mode: ZoomMode) => void;
  left: number;
  bottom: number;
  label: string;
  horizontalTitle?: string;
  sliceDirection?: "horizontal" | "vertical";
}) {
  const sliceMode = sliceDirection;
  return (
    <>
      <Button
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
      </Button>
      <Button
        className="plot-zoom-button"
        style={{ left: Math.max(8, left - 72) + 22, bottom: bottom - 24 }}
        type="button"
        title={
          sliceMode === "vertical"
            ? "Y-range zoom: fit intensity to the visible profile"
            : (horizontalTitle ??
              (label === "Cake"
                ? "X-range zoom: keep the azimuth range"
                : "X-range zoom: fit intensity to the visible data"))
        }
        aria-label={`${label} ${sliceMode === "vertical" ? "Y" : "X"}-range zoom`}
        aria-pressed={mode === sliceMode}
        onClick={() => onChange(sliceMode)}
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
          <path
            d={sliceMode === "vertical" ? "M5 7h14M5 17h14" : "M7 5v14M17 5v14"}
          />
        </svg>
      </Button>
    </>
  );
}
