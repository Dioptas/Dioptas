import { Fragment, useEffect, useState } from "react";
import type { State, Unit } from "./types";
import { number } from "./types";
import type { MaskPlugin, MaskTools } from "./maskDomain";
import { shapeHelp } from "./maskDomain";
import type { MaskRun } from "./MaskView";

function PluginSettings({
  plugin,
  ready,
  run,
}: {
  plugin: MaskPlugin;
  ready: boolean;
  run: MaskRun;
}) {
  const [values, setValues] = useState(plugin.settings);
  useEffect(
    () => setValues(plugin.settings),
    [JSON.stringify(plugin.settings)],
  );
  return (
    <details className="mask-plugin">
      <summary>{plugin.name} settings</summary>
      <p className="muted">{plugin.description}</p>
      {Object.entries(plugin.schema).map(([key, spec]) => (
        <label key={key} className="mask-setting" title={spec.description}>
          <span>{spec.label ?? key}</span>
          {spec.type === "bool" ? (
            <input
              type="checkbox"
              aria-label={`${plugin.name}: ${spec.label ?? key}`}
              checked={!!values[key]}
              onChange={(e) =>
                setValues({ ...values, [key]: e.target.checked })
              }
            />
          ) : spec.type === "choice" ? (
            <select
              aria-label={`${plugin.name}: ${spec.label ?? key}`}
              value={String(values[key])}
              onChange={(e) => setValues({ ...values, [key]: e.target.value })}
            >
              {spec.choices?.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          ) : (
            <input
              aria-label={`${plugin.name}: ${spec.label ?? key}`}
              type={spec.type === "str" ? "text" : "number"}
              min={spec.min}
              max={spec.max}
              step={spec.type === "int" ? 1 : (spec.step ?? "any")}
              value={String(values[key] ?? "")}
              onChange={(e) =>
                setValues({
                  ...values,
                  [key]:
                    spec.type === "str"
                      ? e.target.value
                      : e.target.value === ""
                        ? ""
                        : Number(e.target.value),
                })
              }
            />
          )}
        </label>
      ))}
      <div className="mask-grid">
        <button
          disabled={!ready}
          onClick={() =>
            void run(
              "mask_plugin",
              { name: plugin.name, settings: values },
              "Updating automatic mask…",
            )
          }
        >
          Apply settings
        </button>
        <button
          disabled={!ready}
          onClick={() =>
            setValues(
              Object.fromEntries(
                Object.entries(plugin.schema).map(([k, s]) => [
                  k,
                  s.default ?? "",
                ]),
              ),
            )
          }
        >
          Defaults
        </button>
      </div>
    </details>
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
  const [flip, setFlip] = useState(false);
  const enabled = ready && !!state?.hasImage;
  const edit = (operation: string, extra: Record<string, unknown> = {}) =>
    void run(
      "mask_edit",
      { operation, erase: tools.erase, ...extra },
      operation === "cosmic" ? "Removing cosmic rays…" : "Applying mask…",
    );
  const bound = (text: string) => (text.trim() === "" ? null : Number(text));
  return (
    <div className="mask-controls">
      <section className="sidebar-section">
        <div
          className="mask-grid"
          role="radiogroup"
          aria-label="Mask drawing mode"
        >
          {[false, true].map((erase) => (
            <label className="check-line" key={String(erase)}>
              <input
                type="radio"
                name="mask-mode"
                checked={tools.erase === erase}
                onChange={() => tools.setErase(erase)}
              />
              {erase ? "Unmask" : "Mask"}
            </label>
          ))}
        </div>
        <div className="mask-grid">
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
              <button
                disabled={!enabled}
                className={tools.shape === shape ? "active" : ""}
                aria-pressed={tools.shape === shape}
                onClick={() =>
                  tools.setShape(tools.shape === shape ? "navigate" : shape)
                }
              >
                {label}
              </button>
              {shape === "point" && (
                <label
                  className="mask-point-diameter"
                  title="Point diameter in source pixels"
                >
                  <input
                    aria-label="Mask point diameter"
                    className="numeric-stepper"
                    type="number"
                    min="2"
                    max="600"
                    value={tools.diameter}
                    onChange={(e) =>
                      tools.setDiameter(
                        Math.max(2, Math.min(600, Number(e.target.value) || 2)),
                      )
                    }
                  />
                  <span aria-hidden="true">px</span>
                </label>
              )}
            </Fragment>
          ))}
        </div>
        <p className="mask-help">{shapeHelp[tools.shape]}</p>
      </section>
      <section className="sidebar-section">
        <div className="section-label">THRESHOLD</div>
        <div className="mask-grid">
          <button
            disabled={!enabled || above.trim() === ""}
            onClick={() => edit("above", { threshold: Number(above) })}
          >
            Above Thresh
          </button>
          <input
            aria-label="Above threshold counts"
            placeholder="counts"
            type="number"
            value={above}
            onChange={(e) => setAbove(e.target.value)}
          />
          <button
            disabled={!enabled || below.trim() === ""}
            onClick={() => edit("below", { threshold: Number(below) })}
          >
            Below Thresh
          </button>
          <input
            aria-label="Below threshold counts"
            placeholder="counts"
            type="number"
            value={below}
            onChange={(e) => setBelow(e.target.value)}
          />
        </div>
        <div className="mask-setting">
          <span>Range</span>
          <select
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
          </select>
        </div>
        <div className="mask-grid">
          <input
            aria-label="Mask range minimum"
            placeholder="min"
            type="number"
            min="0"
            value={lower}
            onChange={(e) => setLower(e.target.value)}
          />
          <input
            aria-label="Mask range maximum"
            placeholder="max"
            type="number"
            min="0"
            value={upper}
            onChange={(e) => setUpper(e.target.value)}
          />
          {[false, true].map((outside) => (
            <button
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
            </button>
          ))}
        </div>
        {!state?.calibrated && (
          <p className="mask-help">Radial ranges require calibration.</p>
        )}
      </section>
      <section className="sidebar-section">
        <div className="section-label">MASK ACTIONS</div>
        <div className="mask-grid">
          {["grow", "shrink", "invert", "clear"].map((action) => (
            <button
              key={action}
              disabled={!enabled}
              onClick={() => edit(action)}
            >
              {action[0].toUpperCase() + action.slice(1)}
            </button>
          ))}
          <button
            disabled={!enabled || !state?.canUndoMask}
            onClick={() => void run("undo_mask")}
          >
            Undo mask
          </button>
          <button
            disabled={!enabled || !state?.canRedoMask}
            onClick={() => void run("redo_mask")}
          >
            Redo mask
          </button>
        </div>
        <button
          className="mask-wide"
          disabled={!enabled}
          onClick={() => edit("cosmic")}
        >
          Cosmic Removal
        </button>
      </section>
      <section className="sidebar-section">
        <div className="section-label">AUTOMATIC MASKING PLUGINS</div>
        <p className="mask-help">
          Available model plugins. Enable for each image; imprint bakes the
          current result into the editable mask.
        </p>
        {state?.maskDetails.plugins.map((plugin) => (
          <div key={plugin.name} className="mask-plugin-row">
            <label className="check-line">
              <input
                type="checkbox"
                disabled={!enabled}
                checked={plugin.enabled}
                onChange={(e) =>
                  void run(
                    "mask_plugin",
                    { name: plugin.name, enabled: e.target.checked },
                    "Computing automatic mask…",
                  )
                }
              />
              {plugin.name}
            </label>
            <div className="mask-setting">
              <span className="muted">
                {number(plugin.maskedPixels, 0)} pixels
              </span>
              <button
                disabled={!enabled || !plugin.enabled}
                onClick={() =>
                  void run(
                    "mask_plugin",
                    { name: plugin.name, imprint: true },
                    "Imprinting mask…",
                  )
                }
              >
                Imprint
              </button>
            </div>
            {Object.keys(plugin.schema).length > 0 && (
              <PluginSettings plugin={plugin} ready={enabled} run={run} />
            )}
          </div>
        ))}
        <p className="mask-help">
          No optional engine is required. Additional plugins appear only when
          installed.
        </p>
      </section>
      <section className="sidebar-section">
        <div className="section-label">DISPLAY & USE</div>
        <label className="check-line">
          <input
            type="checkbox"
            checked={state?.useMask ?? false}
            disabled={!enabled}
            onChange={(e) =>
              void run("settings", { use_mask: e.target.checked })
            }
          />
          Use mask
        </label>
        <label className="check-line">
          <input
            type="checkbox"
            checked={state?.transparentMask ?? false}
            disabled={!enabled}
            onChange={(e) =>
              void run("settings", { transparent_mask: e.target.checked })
            }
          />
          Transparent mask
        </label>
        <p className="mask-help">
          The same mask is used by calibration and integration.
        </p>
      </section>
      <section className="sidebar-section">
        <div className="section-label">MASK FILE</div>
        <div className="mask-grid">
          <button
            disabled={!enabled}
            onClick={() =>
              void run("mask_file", { flipud: flip }, "Loading mask…")
            }
          >
            Load Mask
          </button>
          <button
            disabled={!enabled}
            onClick={() =>
              void run("mask_file", { add: true, flipud: flip }, "Adding mask…")
            }
          >
            Add Mask
          </button>
        </div>
        <button
          className="mask-wide"
          disabled={!enabled}
          onClick={() =>
            void run("mask_file", { save: true, flipud: flip }, "Saving mask…")
          }
        >
          Save Mask
        </button>
        <label className="check-line">
          <input
            type="checkbox"
            checked={flip}
            onChange={(e) => setFlip(e.target.checked)}
          />
          Vertically flipped file (NumPy / EDF)
        </label>
        <p className="mask-help">
          .mask uses Dioptas orientation. Select flip for Qt’s vertically
          flipped .npy/.edf convention. Save stores the user mask; imprint
          active plugins first to include them.
        </p>
        {state?.maskDetails.filename && (
          <p className="mask-filename" title={state.maskDetails.filename}>
            {state.maskDetails.filename.split(/[\\/]/).at(-1)}
          </p>
        )}
      </section>
    </div>
  );
}
