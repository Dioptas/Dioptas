import { SpottinessControls } from "./SpottinessControls";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "./ui";
import { TabList } from "./TabList";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
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
let retainedPrimaryTab = "Image";
let retainedReferenceTab = "Phase";
const primaryTabs = ["Image", "Pattern", "Background", "Corrections"];
const referenceTabs = ["Overlay", "Phase"];
const allTabs = [
  "Image",
  "Pattern",
  "Overlay",
  "Phase",
  "Background",
  "Corrections",
];

/** Qt control groups; all science is dispatched to IntegrationWorkflow on the existing worker. */
export function IntegrationView({
  state,
  correctionPreviewKind,
  onCorrectionPreview,
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
  correctionPreviewKind: string | null;
  onCorrectionPreview: (kind: string) => void;
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
  const [primaryTab, setPrimaryTab] = useState(retainedPrimaryTab);
  const [referenceTab, setReferenceTab] = useState(retainedReferenceTab);
  const container = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(1);
  useLayoutEffect(() => {
    const node = container.current;
    if (!node) return;
    const measure = () => {
      // Qt splits the task panel at 900/1400 px. Scale with interface text.
      const scale =
        parseFloat(getComputedStyle(node).getPropertyValue("--text-small")) /
        14;
      const width = node.clientWidth / scale;
      setColumns(width < 900 ? 1 : width > 1400 ? 3 : 2);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    const textObserver = new MutationObserver(measure);
    const app = node.closest(".app");
    if (app)
      textObserver.observe(app, {
        attributes: true,
        attributeFilter: ["data-text-size"],
      });
    return () => {
      observer.disconnect();
      textObserver.disconnect();
    };
  }, [!!source]);
  const selectTab = (value: string) => {
    setTab(value);
    if (primaryTabs.includes(value)) setPrimaryTab(value);
    else setReferenceTab(value);
    onControlsCollapsedChange(false);
  };
  const visible = (name: string) =>
    !controlsCollapsed &&
    (columns === 1
      ? tab === name
      : primaryTabs.includes(name)
        ? primaryTab === name
        : columns === 3 || referenceTab === name);
  useEffect(() => {
    if (overlayReveal !== retainedOverlayReveal) {
      retainedOverlayReveal = overlayReveal;
      setTab("Overlay");
      setReferenceTab("Overlay");
      onControlsCollapsedChange(false);
    }
  }, [overlayReveal, onControlsCollapsedChange]);
  useEffect(() => {
    retainedTab = tab;
    retainedPrimaryTab = primaryTab;
    retainedReferenceTab = referenceTab;
  }, [tab, primaryTab, referenceTab]);
  const [backgroundTab, setBackgroundTab] = useState("pattern");
  const [correctionTab, setCorrectionTab] = useState("flat");
  const [frameStep, setFrameStep] = useState(1);
  const [patternStep, setPatternStep] = useState(1);
  if (!source || !state) return null;
  const action = (
    command: string,
    args: Record<string, unknown> = {},
    onSuccess?: Parameters<IntegrationRun>[3],
  ) => run(command, args, "Updating integration…", onSuccess);
  return (
    <div
      ref={container}
      className="integration-controls"
      data-control-columns={columns}
    >
      <div className="integration-controls-header">
        {(columns === 1
          ? [allTabs]
          : columns === 2
            ? [primaryTabs, referenceTabs]
            : [primaryTabs, ["Overlay"], ["Phase"]]
        ).map((names, index) => (
          <TabList
            key={index}
            className="integration-tabs calibration-workflow-tabs"
            label={
              index === 0
                ? "Integration controls"
                : index === 1
                  ? "Integration references"
                  : "Integration phases"
            }
            value={
              columns === 1
                ? tab
                : index === 0
                  ? primaryTab
                  : columns === 2
                    ? referenceTab
                    : names[0]
            }
            onChange={selectTab}
            options={names.map((name) => ({
              value: name,
              label: name,
              panelId: `integration-panel-${name.toLowerCase()}`,
            }))}
          />
        ))}
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
          aria-controls={allTabs
            .map((name) => `integration-panel-${name.toLowerCase()}`)
            .join(" ")}
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
      <div className="integration-controls-pages">
        {allTabs.map((name) => (
          <fieldset
            key={name}
            hidden={!visible(name)}
            disabled={!ready}
            className={`integration-fieldset integration-tab-${name.toLowerCase()}`}
            role="tabpanel"
            aria-label={`${name} controls`}
            id={`integration-panel-${name.toLowerCase()}`}
          >
            {name === "Image" && (
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
            {name === "Pattern" && (
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
            {name === "Background" && (
              <div className="processing-pane">
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
            )}
            {name === "Corrections" && (
              <div className="processing-pane">
                <IntegrationCorrectionControls
                  previewKind={correctionPreviewKind}
                  onPreview={onCorrectionPreview}
                  key={`${state.projectName}:${state.configurationContext ?? state.configurationIndex}`}
                  state={state}
                  run={runProcessing}
                  tab={correctionTab}
                  onTabChange={setCorrectionTab}
                />
              </div>
            )}
            {name === "Overlay" && (
              <div className="integration-overlay-page">
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
            )}
            {name === "Phase" && (
              <IntegrationPhaseControls
                active={visible("Phase")}
                source={source}
                ready={ready}
                run={run}
              />
            )}
          </fieldset>
        ))}
      </div>
    </div>
  );
}
