import { LoaderCircle } from "lucide-react";
import { BackendStatusMessage } from "./BackendStatusMessage";
import { ReadingFields, sourceLabel, type SourcedReading } from "./PlotStatus";
import type { PlotReading } from "./plotReadout";
import { Button } from "./ui";

export interface AppFooterProps {
  mode: string;
  settingsOpen: boolean;
  correctionPreviewActive: boolean;
  linkedClicks: boolean;
  mainPlotReading: SourcedReading | null;
  clickedReading: SourcedReading | null;
  clickPositionReading: PlotReading | null;
  scxrdClick: PlotReading | null;
  scxrdFilename?: string | null;
  scxrdFrames: number;
  imageName?: string | null;
  busy: boolean;
  progressRunning: boolean;
  error: string | null;
  statusMessage: string;
  mapBackgroundPending: boolean;
  ready: boolean;
  onRefreshMap: () => void;
  onDismissError: () => void;
  onCancelMaskSelection?: () => void;
  onCancelProcessing: () => void;
}

export function AppFooter({
  mode,
  settingsOpen,
  correctionPreviewActive,
  linkedClicks,
  mainPlotReading,
  clickedReading,
  clickPositionReading,
  scxrdClick,
  scxrdFilename,
  scxrdFrames,
  imageName,
  busy,
  progressRunning,
  error,
  statusMessage,
  mapBackgroundPending,
  ready,
  onRefreshMap,
  onDismissError,
  onCancelMaskSelection,
  onCancelProcessing,
}: AppFooterProps) {
  return (
    <footer className="app-status">
      <div className="plot-status">
        <div className="plot-status-line">
          <span
            data-testid="mouse-readout"
            className="plot-status-reading"
            data-plot={mainPlotReading?.source}
            data-pixel-x={mainPlotReading?.x}
            data-pixel-row={mainPlotReading?.row}
            title={mainPlotReading?.text}
          >
            {mainPlotReading ? (
              <ReadingFields reading={mainPlotReading} />
            ) : mode === "scxrd" ? (
              (scxrdFilename ?? "No rotation scan loaded")
            ) : (
              (imageName ?? "No image loaded")
            )}
          </span>
        </div>
        {!correctionPreviewActive &&
          !settingsOpen &&
          (linkedClicks || mode === "map") && (
            <div className="plot-status-line clicked-position">
              <span
                className="plot-status-kind"
                title="Last selected position. Click a detector or pattern to choose a point; move the pointer to inspect values."
              >
                Click
              </span>
              <span
                data-testid="click-readout"
                data-plot={clickedReading?.source}
                className="plot-status-reading"
                title={
                  clickedReading
                    ? `${sourceLabel(clickedReading.source)} · ${clickPositionReading?.fields?.map((f) => `${f.label} ${f.value}`).join(" · ") ?? clickedReading.text}`
                    : "Click an image, cake or pattern to mark a linked position"
                }
              >
                {clickPositionReading ? (
                  <ReadingFields reading={clickPositionReading} />
                ) : (
                  "—"
                )}
              </span>
            </div>
          )}
        {!settingsOpen && mode === "scxrd" && (
          <div className="plot-status-line clicked-position">
            <span
              className="plot-status-kind"
              title="Last selected detector position. It stays while you change frames; the reading is taken at the click."
            >
              Click
            </span>
            <span
              data-testid="click-readout"
              data-plot={scxrdClick ? "detector" : undefined}
              className="plot-status-reading"
              title={scxrdClick?.text ?? "Click the image to mark a position"}
            >
              {scxrdClick ? <ReadingFields reading={scxrdClick} /> : "—"}
            </span>
          </div>
        )}
      </div>
      <div className="workflow-status">
        {busy ? (
          <LoaderCircle className="spin" size={13} />
        ) : (
          <span className="ready-dot" />
        )}
        <BackendStatusMessage
          error={error}
          message={statusMessage}
          crystalFrames={scxrdFrames}
          processing={busy || progressRunning}
        />
        {mode === "map" && mapBackgroundPending && ready && (
          <Button
            variant="secondary"
            className="status-action"
            onClick={onRefreshMap}
          >
            Update map
          </Button>
        )}
        {error && (
          <Button
            variant="secondary"
            className="status-action"
            aria-label="Dismiss error"
            onClick={onDismissError}
          >
            ×
          </Button>
        )}
        {onCancelMaskSelection && (
          <Button
            variant="secondary"
            className="status-action"
            onClick={onCancelMaskSelection}
          >
            Cancel selection
          </Button>
        )}
        {progressRunning && (
          <Button
            variant="secondary"
            className="status-action"
            onClick={onCancelProcessing}
          >
            {mode === "scxrd"
              ? "Stop processing"
              : mode === "map"
                ? "Cancel map processing"
                : mode === "integration"
                  ? "Cancel processing"
                  : mode === "mask"
                    ? "Cancel mask processing"
                    : "Cancel refinement"}
          </Button>
        )}
      </div>
    </footer>
  );
}
