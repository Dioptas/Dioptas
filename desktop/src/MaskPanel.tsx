import { Button, Input, Select } from "./ui";
import { Fragment, useEffect, useId, useState } from "react";
import { FolderOpen, Plus, Save, Settings, Stamp } from "lucide-react";
import type { State, Unit } from "./types";
import type { MaskPlugin, MaskTools } from "./maskDomain";
import type { MaskRun } from "./MaskView";
import { CalibrationHelp } from "./CalibrationHelp";

function PluginSettings({
  plugin,
  ready,
  run,
}: {
  plugin: MaskPlugin;
  ready: boolean;
  run: MaskRun;
}) {
  const id = useId();
  const [values, setValues] = useState(plugin.settings);
  useEffect(
    () => setValues(plugin.settings),
    [JSON.stringify(plugin.settings)],
  );
  const updateSettings = (settings: MaskPlugin["settings"]) => {
    if (!ready) return;
    void run(
      "mask_plugin",
      { name: plugin.name, settings },
      "Updating dynamic mask…",
    );
  };
  return (
    <div className="mask-plugin">
      {Object.entries(plugin.schema).map(([key, spec]) => (
        <div key={key} className="mask-setting">
          <div className="mask-setting-label">
            <label htmlFor={`${id}-${key}`}>{spec.label ?? key}</label>
            {spec.description && (
              <CalibrationHelp
                label={`${plugin.name}: ${spec.label ?? key}`}
                text={spec.description}
              />
            )}
          </div>
          {spec.type === "bool" ? (
            <Input
              id={`${id}-${key}`}
              type="checkbox"
              aria-label={`${plugin.name}: ${spec.label ?? key}`}
              disabled={!ready}
              checked={!!values[key]}
              onChange={(e) => {
                setValues({ ...values, [key]: e.target.checked });
                updateSettings({ [key]: e.target.checked });
              }}
            />
          ) : spec.type === "choice" ? (
            <Select
              id={`${id}-${key}`}
              aria-label={`${plugin.name}: ${spec.label ?? key}`}
              disabled={!ready}
              value={String(values[key])}
              onChange={(e) => {
                setValues({ ...values, [key]: e.target.value });
                updateSettings({ [key]: e.target.value });
              }}
            >
              {spec.choices?.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </Select>
          ) : (
            <Input
              id={`${id}-${key}`}
              aria-label={`${plugin.name}: ${spec.label ?? key}`}
              type={spec.type === "str" ? "text" : "number"}
              disabled={!ready}
              min={spec.min}
              max={spec.max}
              step={spec.type === "int" ? 1 : (spec.step ?? "any")}
              value={String(values[key] ?? "")}
              onChange={(e) => setValues({ ...values, [key]: e.target.value })}
              onBlur={(e) => {
                const input = e.currentTarget;
                if (!input.reportValidity()) return;
                const value =
                  spec.type === "str" ? input.value : Number(input.value);
                if (
                  spec.type !== "str" &&
                  (input.value.trim() === "" || !Number.isFinite(value))
                ) {
                  setValues((current) => ({
                    ...current,
                    [key]: plugin.settings[key],
                  }));
                  return;
                }
                if (value !== plugin.settings[key])
                  updateSettings({ [key]: value });
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  e.currentTarget.blur();
                }
              }}
            />
          )}
        </div>
      ))}
      <div className="mask-grid">
        <Button
          disabled={!ready}
          // Reset directly without first committing the focused field's draft.
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            const defaults = Object.fromEntries(
              Object.entries(plugin.schema).map(([k, s]) => [
                k,
                s.default ?? "",
              ]),
            );
            setValues(defaults);
            updateSettings(defaults);
          }}
        >
          Defaults
        </Button>
      </div>
    </div>
  );
}
export function MaskPanel({
  state,
  ready,
  run,
  tools,
}: {
  state: State | null;
  ready: boolean;
  run: MaskRun;
  tools: MaskTools;
}) {
  const [above, setAbove] = useState(""),
    [below, setBelow] = useState("");
  const [unit, setUnit] = useState<Unit>("2th_deg"),
    [lower, setLower] = useState(""),
    [upper, setUpper] = useState("");
  const [pluginSettingsOpen, setPluginSettingsOpen] = useState<
    Record<string, boolean>
  >({});
  const enabled = ready && !!state?.hasImage;
  const edit = (operation: string, extra: Record<string, unknown> = {}) =>
    void run(
      "mask_edit",
      { operation, erase: tools.erase, ...extra },
      "Applying mask…",
    );
  const bound = (text: string) => (text.trim() === "" ? null : Number(text));
  return (
    <div className="mask-controls">
      <div className="mask-controls-scroll">
        <section className="sidebar-section">
          <div
            className="mask-grid"
            role="radiogroup"
            aria-label="Mask drawing mode"
          >
            {[false, true].map((erase) => (
              <label className="check-line" key={String(erase)}>
                <Input
                  type="radio"
                  name="mask-mode"
                  checked={tools.erase === erase}
                  onChange={() => tools.setErase(erase)}
                />
                {erase ? "Unmask" : "Mask"}
              </label>
            ))}
          </div>
          <div className="mask-grid mask-shape-grid">
            <button
              className="mask-navigate"
              aria-pressed={tools.shape === "navigate"}
              onClick={() => tools.setShape("navigate")}
            >
              Navigate
            </button>
            {(
              [
                ["circle", "Circle"],
                ["rectangle", "Rectangle"],
                ["point", "Point"],
                ["polygon", "Polygon"],
                ["arc", "Arc"],
              ] as const
            ).map(([shape, label]) => (
              <Fragment key={shape}>
                <Button
                  disabled={!enabled}
                  className={tools.shape === shape ? "active" : ""}
                  aria-pressed={tools.shape === shape}
                  onClick={() =>
                    tools.setShape(tools.shape === shape ? "navigate" : shape)
                  }
                >
                  {label}
                </Button>
                {shape === "point" && (
                  <label
                    className="mask-point-diameter"
                    title="Point diameter in source pixels"
                  >
                    <Input
                      aria-label="Mask point diameter"
                      className="numeric-stepper"
                      type="number"
                      min="2"
                      max="600"
                      value={tools.diameter}
                      onChange={(e) =>
                        tools.setDiameter(
                          Math.max(
                            2,
                            Math.min(600, Number(e.target.value) || 2),
                          ),
                        )
                      }
                    />
                    <span aria-hidden="true">px</span>
                  </label>
                )}
              </Fragment>
            ))}
          </div>
        </section>
        <section className="sidebar-section">
          <div className="mask-grid">
            <Button
              disabled={!enabled || above.trim() === ""}
              onClick={() => edit("above", { threshold: Number(above) })}
            >
              Above Thresh
            </Button>
            <Input
              aria-label="Above threshold counts"
              placeholder="counts"
              type="number"
              value={above}
              onChange={(e) => setAbove(e.target.value)}
            />
            <Button
              disabled={!enabled || below.trim() === ""}
              onClick={() => edit("below", { threshold: Number(below) })}
            >
              Below Thresh
            </Button>
            <Input
              aria-label="Below threshold counts"
              placeholder="counts"
              type="number"
              value={below}
              onChange={(e) => setBelow(e.target.value)}
            />
          </div>
        </section>
        <section className="sidebar-section">
          <div className="mask-setting">
            <span>Range</span>
            <Select
              aria-label="Mask radial unit"
              value={unit}
              onChange={(e) => {
                setUnit(e.target.value as Unit);
                setLower("");
                setUpper("");
              }}
            >
              <option value="2th_deg">2θ (°)</option>
              <option value="q_A^-1">q (Å⁻¹)</option>
              <option value="d_A">d (Å)</option>
            </Select>
          </div>
          <div className="mask-grid">
            <Input
              aria-label="Mask range minimum"
              placeholder="min"
              type="number"
              min="0"
              value={lower}
              onChange={(e) => setLower(e.target.value)}
            />
            <Input
              aria-label="Mask range maximum"
              placeholder="max"
              type="number"
              min="0"
              value={upper}
              onChange={(e) => setUpper(e.target.value)}
            />
            {[false, true].map((outside) => (
              <Button
                key={String(outside)}
                disabled={!enabled || !state?.calibrated || (!lower && !upper)}
                onClick={() =>
                  edit("range", {
                    unit,
                    lower: bound(lower),
                    upper: bound(upper),
                    outside,
                  })
                }
              >
                {outside ? "Outside" : "Inside"}
              </Button>
            ))}
          </div>
          {!state?.calibrated && (
            <p className="mask-help">Radial ranges require calibration.</p>
          )}
        </section>
        <section className="sidebar-section">
          <div className="mask-grid">
            {["grow", "shrink", "invert", "clear"].map((action) => (
              <Button
                key={action}
                disabled={!enabled}
                onClick={() => edit(action)}
              >
                {action[0].toUpperCase() + action.slice(1)}
              </Button>
            ))}
          </div>
        </section>
        <section className="sidebar-section">
          <button
            disabled={!enabled}
            title="Add detected LA Cosmic hits to the current mask; source intensities are preserved"
            onClick={() => edit("cosmic")}
          >
            Cosmic Removal
          </button>
        </section>
        <section className="sidebar-section mask-plugins">
          <div className="section-label">
            <span>Dynamic masking plugins</span>
            <CalibrationHelp
              label="Dynamic masking plugins"
              text="Enabled plugins recalculate their mask for every image using its pixel intensities, the chosen settings and, where needed, calibration. The masked pixels can therefore change from image to image. Changing a setting also recalculates the current mask."
            />
          </div>
          {state?.maskDetails.plugins.map((plugin) => (
            <div key={plugin.name} className="mask-plugin-row">
              <div className="mask-plugin-heading">
                <label className="check-line">
                  <Input
                    type="checkbox"
                    disabled={!enabled}
                    checked={plugin.enabled}
                    onChange={(e) =>
                      void run(
                        "mask_plugin",
                        { name: plugin.name, enabled: e.target.checked },
                        "Computing dynamic mask…",
                      )
                    }
                  />
                  {plugin.name}
                </label>
                <CalibrationHelp
                  label={plugin.name}
                  text={
                    plugin.description ||
                    "Configure this plugin with the settings button. Enable it to include its calculated mask; Imprint copies the current result into the user mask."
                  }
                />
                <Button
                  className="mask-plugin-icon-button"
                  aria-label={`${plugin.name} settings`}
                  title={`${plugin.name} settings`}
                  aria-expanded={!!pluginSettingsOpen[plugin.name]}
                  aria-controls={`mask-plugin-settings-${encodeURIComponent(plugin.name)}`}
                  disabled={!enabled || Object.keys(plugin.schema).length === 0}
                  onClick={() =>
                    setPluginSettingsOpen((open) => ({
                      ...open,
                      [plugin.name]: !open[plugin.name],
                    }))
                  }
                >
                  <Settings size={16} aria-hidden="true" />
                </Button>
                <Button
                  className="mask-plugin-icon-button"
                  aria-label={`Imprint ${plugin.name}`}
                  title={`Imprint ${plugin.name}`}
                  disabled={!enabled || !plugin.enabled}
                  onClick={() =>
                    void run(
                      "mask_plugin",
                      { name: plugin.name, imprint: true },
                      "Imprinting mask…",
                    )
                  }
                >
                  <Stamp size={16} aria-hidden="true" />
                </Button>
              </div>
              {Object.keys(plugin.schema).length > 0 && (
                <div
                  id={`mask-plugin-settings-${encodeURIComponent(plugin.name)}`}
                  hidden={!pluginSettingsOpen[plugin.name]}
                >
                  <PluginSettings plugin={plugin} ready={enabled} run={run} />
                </div>
              )}
            </div>
          ))}
        </section>
        <section className="sidebar-section">
          <label className="check-line">
            <Input
              type="checkbox"
              checked={state?.transparentMask ?? false}
              disabled={!enabled}
              onChange={(e) =>
                void run("settings", { transparent_mask: e.target.checked })
              }
            />
            Transparent
          </label>
        </section>
      </div>
      <div className="mask-file-actions">
        <Button
          aria-label="Load Mask"
          title="Load mask"
          disabled={!enabled}
          onClick={() =>
            void run("mask_file", { flipud: false }, "Loading mask…")
          }
        >
          <FolderOpen size={18} aria-hidden="true" />
        </Button>
        <Button
          aria-label="Add Mask"
          title="Add mask"
          disabled={!enabled}
          onClick={() =>
            void run("mask_file", { add: true, flipud: false }, "Adding mask…")
          }
        >
          <Plus size={18} aria-hidden="true" />
        </Button>
        <Button
          aria-label="Save Mask"
          title="Save mask"
          disabled={!enabled}
          onClick={() =>
            void run("mask_file", { save: true, flipud: false }, "Saving mask…")
          }
        >
          <Save size={18} aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
