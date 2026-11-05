import { useEffect, useState } from "react";
import type { State } from "./types";
import type { IntegrationRun, IntegrationState } from "./integration";
import { Check, Field, Group } from "./IntegrationFields";
import {
  BackgroundRangeFields,
  BackgroundNumberField,
} from "./BackgroundRangeFields";
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
  backgroundSettings,
  onBackgroundChange,
  backgroundUpdating,
  onOverlaySelectionChange,
  showOriginalPattern,
  onShowOriginalPatternChange,
  originalPatternColor,
  onOriginalPatternColorChange,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
  backgroundSettings: BackgroundSettings;
  onBackgroundChange: (patch: Partial<BackgroundSettings>) => void;
  backgroundUpdating: boolean;
  onOverlaySelectionChange: (uid: string | null) => void;
  showOriginalPattern: boolean;
  onShowOriginalPatternChange: (show: boolean) => void;
  originalPatternColor: string;
  onOriginalPatternColorChange: (color: string) => void;
}) {
  const source = state?.integration;
  const [draft, setDraft] = useState<IntegrationState | undefined>(source);
  const [tab, setTab] = useState(retainedTab);
  useEffect(() => { retainedTab = tab; }, [tab]);
  const [backgroundTab, setBackgroundTab] = useState("pattern");
  const [correctionTab, setCorrectionTab] = useState("flat");
  const [bkgRange, setBkgRange] = useState(false);
  const [bkgMin, setBkgMin] = useState(0),
    [bkgMax, setBkgMax] = useState(50);
  const [fileStep, setFileStep] = useState(1);
  const [patternStep, setPatternStep] = useState(1);
  const currentBackgroundRange = backgroundSettings.range;
  useEffect(() => {
    setDraft(source);
    setBkgRange(!!currentBackgroundRange);
    if (currentBackgroundRange) {
      setBkgMin(currentBackgroundRange[0]);
      setBkgMax(currentBackgroundRange[1]);
    }
  }, [state?.revision, source, currentBackgroundRange]);
  if (!source || !draft) return null;
  const set = <K extends keyof IntegrationState>(
    key: K,
    value: IntegrationState[K],
  ) => setDraft((d) => d && { ...d, [key]: value });
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
          <button
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
          </button>
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
        {tab === "Background" && (
          <>
            <nav className="integration-subnav" aria-label="Background type">
              <button
                aria-pressed={backgroundTab === "image"}
                onClick={() => setBackgroundTab("image")}
              >
                Image Bkg
              </button>
              <button
                aria-pressed={backgroundTab === "pattern"}
                onClick={() => setBackgroundTab("pattern")}
              >
                Pattern Bkg
              </button>
            </nav>
            {backgroundTab === "image" && (
              <Group title="Image Background" open>
                <p className="integration-filename">
                  {source.imageBackground.filename ?? "None"}
                </p>
                <div className="file-actions">
                  <button
                    disabled={!state?.hasImage}
                    onClick={() => action("integration_image_background")}
                  >
                    Load background…
                  </button>
                  <button
                    disabled={!source.imageBackground.filename}
                    onClick={() =>
                      action("integration_image_background", { reset: true })
                    }
                  >
                    Remove
                  </button>
                </div>
                <Field
                  label="Image background scale"
                  value={draft.imageBackground.scale}
                  onChange={(v) =>
                    set("imageBackground", {
                      ...draft.imageBackground,
                      scale: v,
                    })
                  }
                />
                <Field
                  label="Image background offset"
                  value={draft.imageBackground.offset}
                  onChange={(v) =>
                    set("imageBackground", {
                      ...draft.imageBackground,
                      offset: v,
                    })
                  }
                />
                <button
                  className="secondary full-input"
                  disabled={!source.imageBackground.filename}
                  onClick={() =>
                    action("integration_image_background", {
                      scale: draft.imageBackground.scale,
                      offset: draft.imageBackground.offset,
                    })
                  }
                >
                  Apply image background
                </button>
              </Group>
            )}
            {backgroundTab === "pattern" && (
              <Group title="Pattern Background" open>
                <Check
                  label="Subtract automatic pattern background"
                  checked={backgroundSettings.enabled}
                  disabled={!source.patternName}
                  onChange={(enabled) => onBackgroundChange({ enabled })}
                />
                <BackgroundNumberField
                  label="Smooth width"
                  value={backgroundSettings.smoothing}
                  min={0.000001}
                  max={1e7}
                  onChange={(smoothing) => onBackgroundChange({ smoothing })}
                />
                <div className="integration-fields">
                  <BackgroundNumberField
                    label="Iterations"
                    value={backgroundSettings.iterations}
                    min={1}
                    max={99999}
                    step={1}
                    onChange={(iterations) =>
                      onBackgroundChange({ iterations })
                    }
                  />
                  <BackgroundNumberField
                    label="Polynomial order"
                    value={backgroundSettings.order}
                    min={1}
                    max={1000}
                    step={1}
                    onChange={(order) => onBackgroundChange({ order })}
                  />
                </div>
                <Check
                  label="Limit background range"
                  checked={bkgRange}
                  onChange={(limited) => {
                    setBkgRange(limited);
                    onBackgroundChange({
                      range: limited ? [bkgMin, bkgMax] : null,
                    });
                  }}
                />
                {bkgRange && (
                  <BackgroundRangeFields
                    range={[bkgMin, bkgMax]}
                    onChange={(range) => {
                      setBkgMin(range[0]);
                      setBkgMax(range[1]);
                      if (range[0] < range[1]) onBackgroundChange({ range });
                    }}
                  />
                )}
                {source.patternBackground.overlay && (
                  <>
                    <p className="integration-note">
                      An overlay is also assigned as background.
                    </p>
                    <button
                      className="secondary full-input"
                      onClick={() => action("integration_clear_background")}
                    >
                      Remove overlay background
                    </button>
                  </>
                )}
              </Group>
            )}
          </>
        )}
        {tab === "Corrections" && (
          <>
            <nav className="integration-subnav" aria-label="Correction type">
              {[
                ["flat", "Flat field"],
                ["cbn", "cBN seat"],
                ["oiadac", "Inc. Abs."],
              ].map(([key, name]) => (
                <button
                  key={key}
                  aria-pressed={correctionTab === key}
                  onClick={() => setCorrectionTab(key)}
                >
                  {name}
                </button>
              ))}
            </nav>
            {correctionTab === "flat" && (
              <Group title="Flat Field" open>
                <p className="integration-filename">
                  {source.flatField.filename ?? "None"}
                </p>
                <div className="file-actions">
                  <button onClick={() => action("integration_flat_field")}>
                    Load flat field…
                  </button>
                  <button
                    disabled={!source.flatField.filename}
                    onClick={() =>
                      action("integration_flat_field", { reset: true })
                    }
                  >
                    Remove
                  </button>
                </div>
                <Check
                  label="Apply flat field"
                  checked={source.flatField.enabled}
                  disabled={!source.flatField.filename}
                  onChange={(enabled) =>
                    action("integration_flat_field", { enabled })
                  }
                />
                <p className="integration-note">
                  Uses Qt's mean-normalized response correction.
                </p>
              </Group>
            )}
            {Object.entries(draft.corrections)
              .filter(([kind]) => kind === correctionTab)
              .map(([kind, correction]) => (
                <Group
                  key={kind}
                  open
                  title={
                    kind === "cbn" ? "cBN Seat" : "Oblique detector absorption"
                  }
                >
                  <Check
                    label={`Apply ${kind === "cbn" ? "cBN seat" : "detector absorption"}`}
                    checked={correction.enabled}
                    onChange={(enabled) =>
                      set("corrections", {
                        ...draft.corrections,
                        [kind]: { ...correction, enabled },
                      })
                    }
                  />
                  {Object.entries(correction.fields).map(([key, field]) => (
                    <Field
                      key={key}
                      label={field.label}
                      value={correction.parameters[key]}
                      min={field.min}
                      max={field.max}
                      onChange={(value) =>
                        set("corrections", {
                          ...draft.corrections,
                          [kind]: {
                            ...correction,
                            parameters: {
                              ...correction.parameters,
                              [key]: value,
                            },
                          },
                        })
                      }
                    />
                  ))}
                </Group>
              ))}
          </>
        )}
        <div className="integration-overlay-page" hidden={tab !== "Overlay"}>
          <IntegrationOverlayControls source={source} run={run} onSelectionChange={onOverlaySelectionChange} showOriginal={showOriginalPattern} onShowOriginalChange={onShowOriginalPatternChange} originalColor={originalPatternColor} onOriginalColorChange={onOriginalPatternColorChange} />
        </div>
        <IntegrationPhaseControls active={tab === "Phase"} source={source} ready={ready} run={run} />
      </fieldset>
      {((tab === "Background" && backgroundTab === "pattern") ||
        (tab === "Corrections" && correctionTab !== "flat")) && (
        <div className="integration-task-actions">
          {tab === "Background" && backgroundTab === "pattern" ? (
            <>
              <button
                className="secondary"
                disabled={
                  !ready || !backgroundSettings.enabled || backgroundUpdating
                }
                onClick={() => action("integration_save_background")}
              >
                Save background…
              </button>
            </>
          ) : tab === "Corrections" && correctionTab !== "flat" ? (
            <button
              className="primary"
              disabled={!ready || !state?.hasImage}
              onClick={() =>
                action("integration_correction", {
                  kind: correctionTab,
                  enabled: draft.corrections[correctionTab].enabled,
                  parameters: draft.corrections[correctionTab].parameters,
                })
              }
            >
              Apply correction
            </button>
          ) : null}
        </div>
      )}
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
    <label className="field-label">
      {label}
      <input
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
