import { Button, Input } from "./ui";
import { useEffect, useState } from "react";

/** Qt BrowseFileWidget's shared load/checkbox, step and file-order rows. */
export function IntegrationFileNavigator({
  kind,
  step,
  onStepChange,
  canNavigate,
  order,
  onOrderChange,
  checkboxLabel,
  checked,
  onCheckedChange,
  onLoad,
  onNavigate,
}: {
  kind: "image" | "pattern";
  step: number;
  onStepChange: (value: number) => void;
  canNavigate: boolean;
  order: string;
  onOrderChange: (mode: string) => void;
  checkboxLabel: string;
  checked: boolean;
  onCheckedChange: (value: boolean) => void;
  onLoad: () => void;
  onNavigate: (direction: number) => void;
}) {
  const [draft, setDraft] = useState(String(step));
  useEffect(() => setDraft(String(step)), [step]);
  const title = kind === "image" ? "Image" : "Pattern";
  return (
    <div className="integration-file-browser">
      <div className="integration-file-loading">
        <Button
          variant="secondary"
          className="integration-file-load"
          onClick={onLoad}
        >
          Load {kind}…
        </Button>
        <label className="check-row">
          <Input
            type="checkbox"
            checked={checked}
            onChange={(event) => onCheckedChange(event.target.checked)}
          />
          {checkboxLabel}
        </label>
      </div>
      <div className="integration-file-navigation">
        <div className="file-actions">
          <Button
            aria-label={`Integration previous ${kind}`}
            title={`Previous ${kind} file`}
            disabled={!canNavigate}
            onClick={() => onNavigate(-1)}
          >
            ‹
          </Button>
          <Button
            aria-label={`Integration next ${kind}`}
            title={`Next ${kind} file`}
            disabled={!canNavigate}
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
            aria-label={kind === "image" ? "File step" : "Pattern file step"}
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
      <div
        className="integration-file-order"
        role="radiogroup"
        aria-label={`${title} file order`}
      >
        {[
          ["number", "By Name"],
          ["time", "By Time"],
        ].map(([mode, label]) => (
          <label className="check-row" key={mode}>
            <Input
              type="radio"
              name={`integration-${kind}-order`}
              value={mode}
              checked={order === mode}
              onChange={() => onOrderChange(mode)}
            />
            {label}
          </label>
        ))}
      </div>
    </div>
  );
}
