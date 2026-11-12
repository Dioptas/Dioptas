import { Input, Button } from "./ui";
import { ShortcutReference } from "./ShortcutReference";
import { TabList } from "./TabList";
import { useEffect, useLayoutEffect, useRef } from "react";
import {
  ArrowLeft,
  Check,
  Keyboard,
  Layers,
  Gem,
  Scan,
  SlidersHorizontal,
  Type,
  Terminal,
} from "lucide-react";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";
import {
  IntegrationSettings,
  type IntegrationSettingsDraft,
} from "./IntegrationSettings";
import "./settings.css";
import { CustomCommandSettings } from "./CustomCommandSettings";
import { ConfigurationBrowsingSettings } from "./ConfigurationBrowsingSettings";
import { ProcessingWorkerSettings } from "./ProcessingWorkerSettings";
import { DacThermalPressureControls } from "./DacThermalPressureControls";
import type { CustomCommandController } from "./customCommands";
import { AppUpdateSettings } from "./AppUpdateSettings";
import type { AppUpdateController } from "./useAppUpdate";

const categories = [
  {
    name: "General",
    icon: SlidersHorizontal,
    description: "Make the workspace comfortable for the way you work.",
  },
  {
    name: "Configurations",
    icon: Layers,
    description:
      "Manage detector configurations and customize file and folder browsing.",
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
  {
    name: "Phase",
    icon: Gem,
    description:
      "Set how pressure and temperature determine phase-line positions.",
  },
] as const;

export function SettingsWorkspace({
  integrationDraft,
  open = true,
  section,
  onSectionChange,
  state,
  ready,
  run,
  largeText,
  onLargeText,
  showConfigurationControls,
  onShowConfigurationControls,
  onClose,
  returnLabel,
  customCommands,
  onCustomActionsActiveChange,
  appUpdate,
}: {
  integrationDraft: IntegrationSettingsDraft;
  open?: boolean;
  section: number;
  onSectionChange: (section: number) => void;
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
  largeText: boolean;
  onLargeText: (large: boolean) => void;
  showConfigurationControls: boolean;
  onShowConfigurationControls: (show: boolean) => void;
  onClose: () => void;
  returnLabel: string;
  customCommands: CustomCommandController;
  onCustomActionsActiveChange: (active: boolean) => void;
  appUpdate: AppUpdateController;
}) {
  useLayoutEffect(() => {
    onCustomActionsActiveChange(open && section === 4);
    return () => onCustomActionsActiveChange(false);
  }, [open, section, onCustomActionsActiveChange]);
  const tabs = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    tabs.current
      ?.querySelector<HTMLButtonElement>('[role="tab"][aria-selected="true"]')
      ?.focus();
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
              onChange={onSectionChange}
              options={categories.map(({ name, icon: Icon }, index) => ({
                value: index,
                label: (
                  <>
                    <Icon size={18} />
                    <span>{name}</span>
                  </>
                ),
                id: `settings-tab-${index === 3 ? "shortcuts" : name.toLowerCase().replaceAll(" ", "-")}`,
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
            <ProcessingWorkerSettings state={state} ready={ready} run={run} />
            <AppUpdateSettings controller={appUpdate} />
            <p className="settings-save-note">
              <Check size={14} /> General preferences take effect immediately.
            </p>
          </div>
          <div
            id="settings-panel-1"
            className="settings-tabpanel settings-configurations"
            role="tabpanel"
            aria-labelledby="settings-tab-configurations"
            hidden={section !== 1}
          >
            <section className="settings-card">
              <div className="settings-preference-row settings-configuration-enable">
                <Input
                  id="settings-configuration-controls"
                  type="checkbox"
                  disabled={!ready || integrationDraft.dirty}
                  checked={showConfigurationControls}
                  onChange={(event) =>
                    onShowConfigurationControls(event.target.checked)
                  }
                  aria-describedby="settings-configuration-description"
                  aria-keyshortcuts="Shift+C"
                />
                <div>
                  <label htmlFor="settings-configuration-controls">
                    Enable configurations
                  </label>
                  <p id="settings-configuration-description">
                    Keep each detector’s image, calibration and processing
                    together. Switching off retains your setups and disables
                    combination. Press Shift+C in the workspace to toggle.
                  </p>
                </div>
              </div>
            </section>
            <ConfigurationBrowsingSettings
              enabled={showConfigurationControls}
              filename={state?.imageName}
              directory={state?.imagePath?.replace(/[\\/][^\\/]*$/, "")}
            />
          </div>
          <div
            id="settings-panel-2"
            className="settings-tabpanel settings-integration"
            role="tabpanel"
            aria-labelledby="settings-tab-integration"
            hidden={section !== 2}
          >
            {state?.integration ? (
              <IntegrationSettings
                editor={integrationDraft}
                state={state}
                ready={ready}
              />
            ) : (
              <p className="settings-detail">
                Integration options will be available when the workspace is
                ready.
              </p>
            )}
          </div>
          <div
            id="settings-panel-5"
            className="settings-tabpanel settings-phase"
            role="tabpanel"
            aria-labelledby="settings-tab-phase"
            hidden={section !== 5}
          >
            <section className="settings-card">
              <h3>DAC thermal pressure</h3>
              {state?.integration && (
                <DacThermalPressureControls
                  source={state.integration}
                  ready={ready}
                  run={run}
                />
              )}
              <p className="settings-detail">
                Applies to all phases in every configuration. Saved with the
                project; Undo/Redo restores the setting and phase positions.
              </p>
            </section>
          </div>
          <div
            id="settings-panel-4"
            className="settings-tabpanel settings-custom-commands"
            role="tabpanel"
            aria-labelledby="settings-tab-custom-actions"
            hidden={section !== 4}
          >
            <CustomCommandSettings controller={customCommands} ready={ready} />
          </div>
          <div
            tabIndex={0}
            id="settings-panel-3"
            className="settings-tabpanel settings-shortcuts"
            role="tabpanel"
            aria-labelledby="settings-tab-shortcuts"
            hidden={section !== 3}
          >
            <ShortcutReference />
          </div>
        </div>
      </div>
    </section>
  );
}
