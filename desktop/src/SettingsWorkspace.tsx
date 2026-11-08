import { Input, Button, Select } from "./ui";
import { ShortcutReference } from "./ShortcutReference";
import { TabList } from "./TabList";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowLeftRight,
  Check,
  Cpu,
  Keyboard,
  Layers,
  Scan,
  SlidersHorizontal,
  Type,
  Terminal,
} from "lucide-react";
import type { ZoomMode } from "./usePlotNavigation";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";
import {
  IntegrationSettings,
  type IntegrationSettingsDraft,
} from "./IntegrationSettings";
import "./settings.css";
import { CustomCommandSettings } from "./CustomCommandSettings";
import type { CustomCommandController } from "./customCommands";

const categories = [
  {
    name: "General",
    icon: SlidersHorizontal,
    description: "Make the workspace comfortable for the way you work.",
  },
  {
    name: "Integration",
    icon: Scan,
    description:
      "Configure radial binning, azimuth ranges and integration corrections.",
  },
  {
    name: "Keyboard shortcuts",
    icon: Keyboard,
    description: "A quick reference for working with images and plots.",
  },
  {
    name: "Custom actions",
    icon: Terminal,
    description: "Create sidebar buttons for your own programs and scripts.",
  },
] as const;

export function SettingsWorkspace({
  integrationDraft,
  open = true,
  state,
  ready,
  run,
  largeText,
  onLargeText,
  showConfigurationControls,
  onShowConfigurationControls,
  onClose,
  returnLabel,
  patternZoom,
  onPatternZoom,
  patternLabel,
  customCommands,
  onCustomActionsActiveChange,
}: {
  integrationDraft: IntegrationSettingsDraft;
  open?: boolean;
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
  largeText: boolean;
  onLargeText: (large: boolean) => void;
  showConfigurationControls: boolean;
  onShowConfigurationControls: (show: boolean) => void;
  onClose: () => void;
  returnLabel: string;
  patternZoom: ZoomMode;
  onPatternZoom: (mode: ZoomMode) => void;
  patternLabel: string;
  customCommands: CustomCommandController;
  onCustomActionsActiveChange: (active: boolean) => void;
}) {
  const [section, setSection] = useState(0);
  useLayoutEffect(() => {
    onCustomActionsActiveChange(open && section === 3);
    return () => onCustomActionsActiveChange(false);
  }, [open, section, onCustomActionsActiveChange]);
  const tabs = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    setSection(0);
    tabs.current?.querySelector<HTMLButtonElement>('[role="tab"]')?.focus();
    const key = (event: KeyboardEvent) => {
      const target =
        event.target instanceof Element ? event.target : document.body;
      if (event.defaultPrevented || target.closest('dialog, [role="dialog"]'))
        return;
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, onClose]);

  return (
    <section
      hidden={!open}
      id="settings-workspace"
      className="settings-workspace"
      aria-labelledby="settings-title"
    >
      <header className="settings-header">
        <h1 id="settings-title">Settings</h1>
        <Button
          variant="quiet"
          className="settings-return"
          aria-label="Close settings"
          onClick={onClose}
        >
          <ArrowLeft size={16} /> Back to {returnLabel}
        </Button>
      </header>
      <div className="settings-layout">
        <div className="settings-category-column">
          <div ref={tabs}>
            <TabList
              className="settings-categories"
              label="Settings categories"
              orientation="vertical"
              value={section}
              onChange={setSection}
              options={categories.map(({ name, icon: Icon }, index) => ({
                value: index,
                label: (
                  <>
                    <Icon size={18} />
                    <span>{name}</span>
                  </>
                ),
                id: `settings-tab-${index === 2 ? "shortcuts" : name.toLowerCase().replaceAll(" ", "-")}`,
                panelId: `settings-panel-${index}`,
              }))}
            />
          </div>
          <p className="settings-navigation-note">
            Return to your work at any time using the modes on the left.
          </p>
        </div>
        <div className="settings-content">
          <div className="settings-section-heading">
            <h2>{categories[section].name}</h2>
            <p>{categories[section].description}</p>
          </div>
          <div
            id="settings-panel-0"
            className="settings-tabpanel settings-general"
            role="tabpanel"
            aria-labelledby="settings-tab-general"
            hidden={section !== 0}
          >
            <section className="settings-card">
              <div className="settings-card-heading">
                <Type size={18} />
                <h3>Interface text</h3>
              </div>
              <p>Choose a comfortable reading size for labels and controls.</p>
              <div
                className="settings-size-options"
                role="group"
                aria-label="Interface text size"
              >
                {[false, true].map((large) => (
                  <Button
                    key={String(large)}
                    className="settings-size-option"
                    aria-pressed={largeText === large}
                    aria-label={large ? "Larger" : "Standard"}
                    onClick={() => onLargeText(large)}
                  >
                    <span
                      className={`settings-type-sample ${large ? "is-large" : ""}`}
                      aria-hidden="true"
                    >
                      Aa<span>2θ · Q · Å</span>
                    </span>
                    <span className="settings-option-caption">
                      <span>{large ? "Larger" : "Standard"}</span>
                      <Check
                        size={16}
                        style={{
                          visibility:
                            largeText === large ? "visible" : "hidden",
                        }}
                      />
                    </span>
                  </Button>
                ))}
              </div>
            </section>
            <section className="settings-card">
              <div className="settings-card-heading">
                <Layers size={18} />
                <h3>Multi-detector setups</h3>
              </div>
              <div className="settings-preference-row">
                <div>
                  <label htmlFor="settings-configuration-controls">
                    Show configuration controls
                  </label>
                  <p id="settings-configuration-description">
                    Switch between detector setups and manage their separate
                    images, calibrations and processing settings.
                  </p>
                </div>
                <Input
                  id="settings-configuration-controls"
                  type="checkbox"
                  checked={showConfigurationControls}
                  onChange={(event) =>
                    onShowConfigurationControls(event.target.checked)
                  }
                  aria-describedby="settings-configuration-description"
                />
              </div>
            </section>
            <section className="settings-card">
              <div className="settings-card-heading">
                <Cpu size={18} />
                <h3>Processing</h3>
              </div>
              <div className="settings-preference-row">
                <div>
                  <label htmlFor="settings-processing-engine">
                    Processing engine
                  </label>
                  <p>
                    Peak searches, geometry fitting, patterns and cakes.
                    Unsupported integration options use pyFAI.
                  </p>
                </div>
                <Select
                  id="settings-processing-engine"
                  value={state?.calibration.engine ?? "pyfai"}
                  disabled={!ready}
                  onChange={(event) =>
                    run(
                      "calibration_engine",
                      { engine: event.target.value },
                      "Changing processing engine…",
                    )
                  }
                >
                  {(
                    state?.calibration.engines ?? [
                      { id: "pyfai", label: "pyFAI", available: true },
                    ]
                  ).map((engine) => (
                    <option
                      key={engine.id}
                      value={engine.id}
                      disabled={!engine.available}
                    >
                      {engine.label}
                      {!engine.available ? " · not installed" : ""}
                    </option>
                  ))}
                </Select>
              </div>
            </section>
            <section className="settings-card">
              <div className="settings-card-heading">
                <ArrowLeftRight size={18} />
                <h3>Pattern navigation</h3>
              </div>
              <div className="settings-preference-row">
                <div>
                  <label htmlFor="settings-pattern-zoom">
                    Pattern drag zoom
                  </label>
                  <p>{patternLabel}. Also available in the plot’s corner.</p>
                </div>
                <Select
                  id="settings-pattern-zoom"
                  aria-label="Pattern zoom mode"
                  value={patternZoom}
                  onChange={(event) =>
                    onPatternZoom(event.target.value as ZoomMode)
                  }
                >
                  <option value="rectangle">Rectangle</option>
                  <option value="horizontal">X-range</option>
                </Select>
              </div>
              <p className="settings-detail">
                {patternZoom === "horizontal"
                  ? "Select a radial range; both intensity limits fit the visible data. Right-click expands the radial range."
                  : "Select both a radial range and an intensity range."}
              </p>
            </section>
            <p className="settings-save-note">
              <Check size={14} /> General preferences take effect immediately.
            </p>
          </div>
          <div
            id="settings-panel-1"
            className="settings-tabpanel settings-integration"
            role="tabpanel"
            aria-labelledby="settings-tab-integration"
            hidden={section !== 1}
          >
            {state?.integration ? (
              <IntegrationSettings
                editor={integrationDraft}
                state={state}
                ready={ready}
                run={run}
              />
            ) : (
              <p className="settings-detail">
                Integration options will be available when the workspace is
                ready.
              </p>
            )}
          </div>
          <div
            id="settings-panel-3"
            className="settings-tabpanel settings-custom-commands"
            role="tabpanel"
            aria-labelledby="settings-tab-custom-actions"
            hidden={section !== 3}
          >
            <CustomCommandSettings controller={customCommands} ready={ready} />
          </div>
          <div
            tabIndex={0}
            id="settings-panel-2"
            className="settings-tabpanel settings-shortcuts"
            role="tabpanel"
            aria-labelledby="settings-tab-shortcuts"
            hidden={section !== 2}
          >
            <ShortcutReference />
          </div>
        </div>
      </div>
    </section>
  );
}
