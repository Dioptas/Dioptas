import { useEffect, useState } from "react";
import { Button, Input } from "./ui";
import { CommitNumberField } from "./CommitNumberField";

/** Qt's independent frame arrows, step size and one-based position. */
export function IntegrationFrameNavigator({
  frame,
  frames,
  step,
  onStepChange,
  onSelect,
  onNavigate,
}: {
  frame: number;
  frames: number;
  step: number;
  onStepChange: (step: number) => void;
  onSelect: (frame: number) => void;
  onNavigate: (direction: number) => void;
}) {
  const [draft, setDraft] = useState(String(step));
  useEffect(() => setDraft(String(step)), [step]);
  return (
    <div
      className="integration-frame-browser"
      role="group"
      aria-label="Frame navigation"
    >
      <div className="integration-file-navigation">
        <div className="file-actions">
          <Button
            aria-label="Integration previous frame"
            title="Previous frame in this file"
            disabled={frame <= 1}
            onClick={() => onNavigate(-1)}
          >
            ‹
          </Button>
          <Button
            aria-label="Integration next frame"
            title="Next frame in this file"
            disabled={frame >= frames}
            onClick={() => onNavigate(1)}
          >
            ›
          </Button>
        </div>
        <label className="integration-file-step">
          Step
          <Input
            className="numeric-stepper"
            type="number"
            aria-label="Frame step"
            value={draft}
            min={1}
            max={100000}
            step={1}
            onChange={(event) => {
              setDraft(event.target.value);
              const value = Number(event.target.value);
              if (Number.isInteger(value) && value >= 1 && value <= 100000)
                onStepChange(value);
            }}
            onBlur={() => setDraft(String(step))}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
          />
        </label>
      </div>
      <CommitNumberField
        label={`Frame position (1–${frames})`}
        min={1}
        max={frames}
        integer
        value={frame}
        onCommit={onSelect}
      />
    </div>
  );
}
