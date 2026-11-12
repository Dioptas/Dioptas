import { Button } from "./ui";
import { useRef } from "react";
import { Eye, Save } from "lucide-react";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";
import type { BackgroundSettings } from "./useLiveBackground";
import { Check } from "./IntegrationFields";
import {
  BackgroundNumberField,
  BackgroundRangeFields,
} from "./BackgroundRangeFields";
import {
  ProcessingToggle,
  ProcessingFile,
  ProcessingNumberField,
  ProcessingType,
} from "./IntegrationProcessingFields";
import "./integrationProcessingControls.css";

export function IntegrationBackgroundControls({
  state,
  run,
  background,
  onChange,
  updating,
  inspect,
  onInspectChange,
  defaultRange,
  tab,
  onTabChange,
}: {
  tab: string;
  onTabChange: (tab: string) => void;
  defaultRange: [number, number];
  state: State;
  run: IntegrationRun;
  background: BackgroundSettings;
  onChange: (patch: Partial<BackgroundSettings>) => void;
  updating: boolean;
  inspect: boolean;
  onInspectChange: (inspect: boolean) => void;
}) {
  const source = state.integration;
  const current = useRef(source.imageBackground);
  current.current = source.imageBackground;
  const tail = useRef(Promise.resolve());
  const editImage = (patch: Record<string, number | boolean>) => {
    const task = tail.current.then(() =>
      run(
        "integration_image_background",
        {
          scale: current.current.scale,
          offset: current.current.offset,
          ...patch,
        },
        "",
        (response) => {
          if (response.state)
            current.current = response.state.integration.imageBackground;
        },
      ),
    );
    tail.current = task.catch(() => {});
    return task;
  };
  const unit =
    state.unit === "2th_deg"
      ? "2θ · °"
      : state.unit === "q_A^-1"
        ? "Q · Å⁻¹"
        : "d · Å";
  // A new restriction starts from the actual plotted domain, including Q and d.
  const previousRange = useRef({ unit: state.unit, range: defaultRange });
  if (background.range)
    previousRange.current = { unit: state.unit, range: background.range };
  const range =
    background.range ??
    (previousRange.current.unit === state.unit
      ? previousRange.current.range
      : defaultRange);
  return (
    <>
      <nav
        className="integration-subnav processing-subnav"
        aria-label="Background type"
      >
        <ProcessingType
          label="Image"
          selected={tab === "image"}
          active={!!source.imageBackground.filename}
          onClick={() => onTabChange("image")}
        />
        <ProcessingType
          label="Pattern"
          selected={tab === "pattern"}
          active={background.enabled || source.patternBackground.overlay}
          onClick={() => onTabChange("pattern")}
        />
      </nav>
      <div className="processing-page">
        {tab === "image" ? (
          <div className="processing-form">
            <ProcessingFile
              kind="background"
              filename={source.imageBackground.filename}
              disabled={!state.hasImage}
              onLoad={() => void run("integration_image_background")}
              onRemove={() =>
                void run("integration_image_background", { reset: true })
              }
            />
            <ProcessingNumberField
              label="Image background scale"
              displayLabel="Scale"
              value={source.imageBackground.scale}
              disabled={!source.imageBackground.filename}
              onCommit={(scale) => editImage({ scale })}
            />
            <ProcessingNumberField
              label="Image background offset"
              displayLabel="Offset"
              value={source.imageBackground.offset}
              disabled={!source.imageBackground.filename}
              onCommit={(offset) => editImage({ offset })}
            />
            <ProcessingToggle
              label="Include background counting noise"
              checked={source.imageBackground.poisson ?? true}
              disabled={!source.imageBackground.filename}
              onCommit={(poisson) => editImage({ poisson })}
            />
            <p className="integration-note">
              Poisson errors use original sample counts. Background noise adds
              scale² × background counts; offset and correction references are
              treated as fixed.
            </p>
          </div>
        ) : (
          <div className="processing-form">
            <div className="processing-toolbar">
              <Check
                label="Subtract automatic pattern background"
                displayLabel="Subtract background"
                checked={background.enabled}
                disabled={!source.patternName}
                onChange={(enabled) => onChange({ enabled })}
              />
              <Button
                type="button"
                aria-label="Inspect background"
                title="Show the original pattern and fitted background; drag the range edges to refit"
                aria-pressed={inspect && background.enabled}
                disabled={!background.enabled}
                onClick={() => onInspectChange(!inspect)}
              >
                <Eye />
                <span className="processing-tool-label">Inspect</span>
              </Button>
              <Button
                type="button"
                aria-label="Save background…"
                title="Save fitted background…"
                disabled={!background.enabled || updating}
                onClick={() => void run("integration_save_background")}
              >
                <Save />
              </Button>
            </div>
            <BackgroundNumberField
              label="Smooth width"
              value={background.smoothing}
              min={0.000001}
              max={1e7}
              onChange={(smoothing) => onChange({ smoothing })}
            />
            <BackgroundNumberField
              label="Iterations"
              value={background.iterations}
              min={1}
              max={99999}
              step={1}
              onChange={(iterations) => onChange({ iterations })}
            />
            <BackgroundNumberField
              label="Polynomial order"
              value={background.order}
              min={1}
              max={1000}
              step={1}
              onChange={(order) => onChange({ order })}
            />
            <Check
              label="Limit background range"
              checked={!!background.range}
              onChange={(limited) =>
                onChange({ range: limited ? range : null })
              }
            />
            {background.range && (
              <BackgroundRangeFields
                range={background.range}
                unit={unit}
                onChange={(next) => {
                  if (next[0] < next[1]) onChange({ range: next });
                }}
              />
            )}
            {source.patternBackground.overlay && (
              <div className="processing-overlay-background">
                <span className="integration-note">
                  Overlay background active
                </span>
                <Button
                  type="button"
                  aria-label="Remove overlay background"
                  title="Remove overlay background"
                  onClick={() => void run("integration_clear_background")}
                >
                  Remove
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
