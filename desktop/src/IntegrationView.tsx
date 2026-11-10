import { SpottinessControls } from "./SpottinessControls";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "./ui";
import { TabList } from "./TabList";
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
let retainedOverlayReveal = 0;

/** Qt control groups; all science is dispatched to IntegrationWorkflow on the existing worker. */
export function IntegrationView({
  state,
  overlayReveal = 0,
  controlsCollapsed,
  onControlsCollapsedChange,
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
  fileStep,
  setFileStep,
}: {
  state: State | null;
  overlayReveal?: number;
  controlsCollapsed: boolean;
  onControlsCollapsedChange: (collapsed: boolean) => void;
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
  fileStep: number;
  setFileStep: (step: number) => void;
}) {
  const source = state?.integration;
  const [tab, setTab] = useState(retainedTab);
  useEffect(() => {
    if (overlayReveal !== retainedOverlayReveal) {
      retainedOverlayReveal = overlayReveal;
      setTab("Overlay");
      onControlsCollapsedChange(false);
    }
  }, [overlayReveal, onControlsCollapsedChange]);
  useEffect(() => {
    retainedTab = tab;
  }, [tab]);
  const [backgroundTab, setBackgroundTab] = useState("pattern");
  const [correctionTab, setCorrectionTab] = useState("flat");
  const [frameStep, setFrameStep] = useState(1);
  const [patternStep, setPatternStep] = useState(1);
  if (!source || !state) return null;
  const action = (command: string, args: Record<string, unknown> = {}) =>
    void run(command, args, "Updating integration…");
  return (
    <div className="integration-controls">
      <div className="integration-controls-header">
        <TabList
          className="integration-tabs calibration-workflow-tabs"
          label="Integration controls"
          value={tab}
          onChange={(value) => {
            setTab(value);
            onControlsCollapsedChange(false);
          }}
          options={[
            "Image",
            "Pattern",
            "Overlay",
            "Phase",
            "Background",
            "Corrections",
          ].map((name) => ({
            value: name,
            label: name,
            panelId: "integration-tabpanel",
          }))}
        />
        <Button
          type="button"
          variant="quiet"
          className="integration-controls-toggle"
          aria-label={
            controlsCollapsed
              ? "Expand Integration controls"
              : "Collapse Integration controls"
          }
          aria-expanded={!controlsCollapsed}
          aria-controls="integration-tabpanel"
          title={
            controlsCollapsed
              ? "Expand controls, or select any tab"
              : "Collapse controls"
          }
          onClick={() => onControlsCollapsedChange(!controlsCollapsed)}
        >
          {controlsCollapsed ? (
            <ChevronDown size={16} />
          ) : (
            <ChevronUp size={16} />
          )}
        </Button>
      </div>
      <fieldset
        hidden={controlsCollapsed}
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
            frameStep={frameStep}
            setFrameStep={setFrameStep}
          />
        )}
        {tab === "Pattern" && (
          <div className="spottiness-pattern-controls">
            <IntegrationPatternControls
              source={source}
              action={action}
              step={patternStep}
              setStep={setPatternStep}
            />
            <SpottinessControls state={state} action={action} />
          </div>
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
            key={`${state.projectName}:${state.configurationContext ?? state.configurationIndex}`}
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
          active={!controlsCollapsed && tab === "Phase"}
          source={source}
          ready={ready}
          run={run}
        />
      </fieldset>
    </div>
  );
}
