import { Button, Input } from "./ui";
import { useEffect, useState } from "react";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";
import { IntegrationBackgroundControls } from "./IntegrationBackgroundControls";
import { IntegrationCorrectionControls } from "./IntegrationCorrectionControls";
import type { BackgroundSettings } from "./useLiveBackground";
import { IntegrationPatternControls } from "./IntegrationPatternControls";
import { IntegrationImageControls } from "./IntegrationImageControls";
import { IntegrationPhaseControls } from "./IntegrationPhaseControls";
import "./integration.css";
import { IntegrationOverlayControls } from "./IntegrationOverlayControls";

// Qt keeps the active Integration tab while visiting another mode.
let retainedTab = "Image";

/** Qt control groups; all science is dispatched to IntegrationWorkflow on the existing worker. */
export function IntegrationView({
  state,
  ready,
  run,
  onOpenBatch,
  batchOpen,
  batchDocked,
  runProcessing,
  backgroundSettings,
  onBackgroundChange,
  backgroundUpdating,
  inspectBackground,
  onInspectBackgroundChange,
  backgroundDefaultRange,
  onOverlaySelectionChange,
  showOriginalPattern,
  onShowOriginalPatternChange,
  originalPatternColor,
  onOriginalPatternColorChange,
}: {
  state: State | null;
  ready: boolean;
  onOpenBatch: () => void;
  batchOpen: boolean;
  batchDocked: boolean;
  run: IntegrationRun;
  runProcessing: IntegrationRun;
  backgroundSettings: BackgroundSettings;
  onBackgroundChange: (patch: Partial<BackgroundSettings>) => void;
  backgroundUpdating: boolean;
  inspectBackground: boolean;
  onInspectBackgroundChange: (inspect: boolean) => void;
  backgroundDefaultRange: [number, number];
  onOverlaySelectionChange: (uid: string | null) => void;
  showOriginalPattern: boolean;
  onShowOriginalPatternChange: (show: boolean) => void;
  originalPatternColor: string;
  onOriginalPatternColorChange: (color: string) => void;
}) {
  const source = state?.integration;
  const [tab, setTab] = useState(retainedTab);
  useEffect(() => {
    retainedTab = tab;
  }, [tab]);
  const [backgroundTab, setBackgroundTab] = useState("pattern");
  const [correctionTab, setCorrectionTab] = useState("flat");
  const [fileStep, setFileStep] = useState(1);
  const [patternStep, setPatternStep] = useState(1);
  if (!source || !state) return null;
  const action = (command: string, args: Record<string, unknown> = {}) =>
    void run(command, args, "Updating integration…");
  return (
    <div className="integration-controls">
      <div
        className="integration-tabs calibration-workflow-tabs"
        role="tablist"
        aria-label="Integration controls"
      >
        {[
          "Image",
          "Pattern",
          "Overlay",
          "Phase",
          "Background",
          "Corrections",
        ].map((name) => (
          <Button
            key={name}
            role="tab"
            aria-selected={tab === name}
            aria-controls="integration-tabpanel"
            tabIndex={tab === name ? 0 : -1}
            onKeyDown={(event) => {
              const names = [
                "Image",
                "Pattern",
                "Overlay",
                "Phase",
                "Background",
                "Corrections",
              ];
              if (
                ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
              ) {
                event.preventDefault();
                const next =
                  event.key === "Home"
                    ? names[0]
                    : event.key === "End"
                      ? names[names.length - 1]
                      : names[
                          (names.indexOf(tab) +
                            (event.key === "ArrowLeft" ? -1 : 1) +
                            names.length) %
                            names.length
                        ];
                setTab(next);
                (
                  event.currentTarget.parentElement?.children[
                    names.indexOf(next)
                  ] as HTMLButtonElement
                )?.focus();
              }
            }}
            onClick={() => setTab(name)}
          >
            {name}
          </Button>
        ))}
      </div>
      <fieldset
        disabled={!ready}
        className={`integration-fieldset integration-tab-${tab.toLowerCase()}`}
        role="tabpanel"
        aria-label={`${tab} controls`}
        id="integration-tabpanel"
      >
        {tab === "Image" && (
          <IntegrationImageControls
            onOpenBatch={onOpenBatch}
            batchOpen={batchOpen}
            batchDocked={batchDocked}
            state={state}
            source={source}
            fileStep={fileStep}
            setFileStep={setFileStep}
            action={action}
            frameControl={
              source.frames > 1 && (
                <CommitField
                  label={`Frame (1–${source.frames})`}
                  value={source.frame}
                  onCommit={(frame) =>
                    action("integration_navigation", { frame })
                  }
                />
              )
            }
          />
        )}
        {tab === "Pattern" && (
          <IntegrationPatternControls
            source={source}
            action={action}
            step={patternStep}
            setStep={setPatternStep}
          />
        )}
        <div className="processing-pane" hidden={tab !== "Background"}>
          <IntegrationBackgroundControls
            state={state}
            run={runProcessing}
            background={backgroundSettings}
            onChange={onBackgroundChange}
            updating={backgroundUpdating}
            inspect={inspectBackground}
            onInspectChange={onInspectBackgroundChange}
            defaultRange={backgroundDefaultRange}
            tab={backgroundTab}
            onTabChange={setBackgroundTab}
          />
        </div>
        <div className="processing-pane" hidden={tab !== "Corrections"}>
          <IntegrationCorrectionControls
            key={`${state.projectName}:${state.configurationIndex}`}
            state={state}
            run={runProcessing}
            tab={correctionTab}
            onTabChange={setCorrectionTab}
          />
        </div>
        <div className="integration-overlay-page" hidden={tab !== "Overlay"}>
          <IntegrationOverlayControls
            source={source}
            run={run}
            onSelectionChange={onOverlaySelectionChange}
            showOriginal={showOriginalPattern}
            onShowOriginalChange={onShowOriginalPatternChange}
            originalColor={originalPatternColor}
            onOriginalColorChange={onOriginalPatternColorChange}
          />
        </div>
        <IntegrationPhaseControls
          active={tab === "Phase"}
          source={source}
          ready={ready}
          run={run}
        />
      </fieldset>
    </div>
  );
}
function CommitField({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number;
  onCommit: (value: number) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <label className="field-label integration-number-field">
      <span>{label}</span>
      <Input
        aria-label={label}
        type="number"
        value={draft}
        onChange={(e) => setDraft(Number(e.target.value))}
        onBlur={() => {
          if (draft !== value) onCommit(draft);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
      />
    </label>
  );
}
