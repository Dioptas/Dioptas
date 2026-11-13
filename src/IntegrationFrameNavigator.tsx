import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./ui";
import { CommitNumberField } from "./CommitNumberField";
import { NavigationStep } from "./NavigationStep";

/** Qt's independent frame arrows, step size and one-based position. */
export function IntegrationFrameNavigator({
  frame,
  frames,
  step,
  onStepChange,
  onSelect,
  onNavigate,
  onValidationChange,
  validationId,
}: {
  frame: number;
  frames: number;
  step: number;
  onStepChange: (step: number) => void;
  onSelect: (frame: number) => void;
  onNavigate: (direction: number) => void;
  onValidationChange?: (error: string | null) => void;
  validationId?: string;
}) {
  if (frames <= 1) return null;
  return (
    <div
      className="integration-frame-browser integration-browse-row"
      role="group"
      aria-label="Frame navigation"
    >
      <span className="integration-browse-label">Frame</span>
      <div className="integration-frame-content">
        <div className="integration-frame-navigation">
          <Button
            className="integration-browse-arrow"
            aria-label="Integration previous frame"
            title="Previous frame in this file"
            disabled={frame <= 1}
            onClick={() => onNavigate(-1)}
          >
            <ChevronLeft size={18} aria-hidden="true" />
          </Button>
          <div className="integration-frame-position">
            <CommitNumberField
              label={`Frame position (1–${frames})`}
              hideLabel
              min={1}
              max={frames}
              integer
              value={frame}
              onCommit={onSelect}
              onValidationChange={onValidationChange}
              validationId={validationId}
            />
          </div>
          <span className="integration-frame-total" aria-hidden="true">
            / {frames.toLocaleString("en-US")}
          </span>
          <Button
            className="integration-browse-arrow"
            aria-label="Integration next frame"
            title="Next frame in this file"
            disabled={frame >= frames}
            onClick={() => onNavigate(1)}
          >
            <ChevronRight size={18} aria-hidden="true" />
          </Button>
        </div>
        <NavigationStep
          label="Frame step"
          value={step}
          onChange={onStepChange}
        />
      </div>
    </div>
  );
}
