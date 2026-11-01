import { useEffect, useState } from "react";
import type { State } from "./types";
import type { IntegrationRun, IntegrationState } from "./integration";
import { Check, Field, Group } from "./IntegrationFields";
import "./integration.css";

/** Qt control groups; all science is dispatched to IntegrationWorkflow on the existing worker. */
export function IntegrationView({
  state,
  ready,
  run,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
}) {
  const source = state?.integration;
  const [draft, setDraft] = useState<IntegrationState | undefined>(source);
  const [tab, setTab] = useState("Image");
  const [subtract, setSubtract] = useState(false);
  const [bkgRange, setBkgRange] = useState(false);
  const [bkgMin, setBkgMin] = useState(0),
    [bkgMax, setBkgMax] = useState(50);
  const [separation, setSeparation] = useState(100);
  const [fileStep, setFileStep] = useState(1);
  useEffect(() => {
    setDraft(source);
    setBkgRange(!!source?.patternBackground.range);
    if (source?.patternBackground.range) {
      setBkgMin(source.patternBackground.range[0]);
      setBkgMax(source.patternBackground.range[1]);
    }
  }, [state?.revision, source]);
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
        className="integration-tabs"
        role="tablist"
        aria-label="Integration controls"
      >
        {[
          "Image",
          "Pattern",
          "Background",
          "Corrections",
          "Overlay",
          "Phase",
        ].map((name) => (
          <button
            key={name}
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>
      <fieldset
        disabled={!ready}
        className="integration-fieldset"
        role="tabpanel"
        aria-label={`${tab} controls`}
      >
        {tab === "Image" && (
          <>
            <Group title="Image" open>
              <button
                className="secondary full-input"
                onClick={() => action("open_image")}
              >
                Load image…
              </button>
              <div className="file-actions">
                <button
                  aria-label="Integration previous image"
                  onClick={() =>
                    action("next_image", { direction: -1, step: fileStep })
                  }
                >
                  ← Previous
                </button>
                <button
                  aria-label="Integration next image"
                  onClick={() =>
                    action("next_image", { direction: 1, step: fileStep })
                  }
                >
                  Next →
                </button>
              </div>
              <p
                className="integration-filename"
                title={state?.imagePath ?? ""}
              >
                {state?.imageName ?? "No image loaded"}
              </p>
              <p className="integration-note">
                {state?.shape?.[1]} × {state?.shape?.[0]} source pixels ·
                top-origin display rows
              </p>
              <Field
                label="File step"
                value={fileStep}
                min={1}
                max={100000}
                step={1}
                onChange={setFileStep}
              />
              <label className="field-label">
                Browse by
                <select
                  aria-label="Image file order"
                  value={source.fileIteration}
                  onChange={(e) =>
                    action("integration_navigation", { mode: e.target.value })
                  }
                >
                  <option value="number">Filename number</option>
                  <option value="time">Creation time</option>
                </select>
              </label>
              {source.frames > 1 && (
                <CommitField
                  label={`Frame (1–${source.frames})`}
                  value={source.frame}
                  onCommit={(frame) =>
                    action("integration_navigation", { frame })
                  }
                />
              )}
              <details className="integration-file-info">
                <summary>File Info</summary>
                <pre>
                  {source.fileInfo || state?.imagePath || "No file loaded"}
                </pre>
              </details>
            </Group>
            <Group title="Calibration" open>
              <button
                className="secondary full-input"
                onClick={() => action("open_calibration")}
              >
                Load calibration…
              </button>
              <p className="integration-filename">
                {state?.calibrationName ??
                  "Load a PONI or calibrate in Calibration"}
              </p>
              {state?.calibrated && (
                <p className="integration-note">
                  {(state.geometry.dist * 1000).toFixed(3)} mm · λ{" "}
                  {(state.geometry.wavelength * 1e10).toFixed(6)} Å
                </p>
              )}
            </Group>
            <Group title="Mask" open>
              <Check
                label="Apply detector mask"
                checked={state?.useMask ?? false}
                disabled={!state?.hasImage}
                onChange={(v) => action("settings", { use_mask: v })}
              />
              <div className="file-actions">
                <button
                  disabled={!state?.hasImage}
                  onClick={() => action("mask_file")}
                >
                  Load mask…
                </button>
                <button
                  disabled={!state?.hasImage}
                  onClick={() => action("mask_file", { save: true })}
                >
                  Save mask…
                </button>
              </div>
              <Check
                label="Integration transparent mask"
                checked={state?.transparentMask ?? false}
                onChange={(v) => action("settings", { transparent_mask: v })}
              />
              <p className="integration-note">
                {state?.maskedPixels.toLocaleString()} masked pixels · shared
                with Calibration and Mask
              </p>
            </Group>
            <Group title="Folder integration">
              <p className="integration-note">
                Integrate files with the current image extension in a chosen
                folder, including their frames. Uses current geometry, mask and
                corrections. Save the completed batch below.
              </p>
              <button
                className="secondary full-input"
                disabled={!state?.calibrated || !state.hasImage}
                onClick={() => action("integration_batch")}
              >
                Integrate folder…
              </button>
              <button
                className="secondary full-input"
                disabled={!source.batchFrames}
                onClick={() => action("integration_save_batch")}
              >
                Save batch… ({source.batchFrames} frames)
              </button>
            </Group>
          </>
        )}
        {tab === "Pattern" && (
          <>
            <Group title="Pattern files" open>
              <button
                className="secondary full-input"
                onClick={() => action("integration_open_pattern")}
              >
                Load pattern…
              </button>
              <div className="file-actions">
                <button
                  onClick={() =>
                    action("integration_open_pattern", { direction: -1 })
                  }
                >
                  ← Previous
                </button>
                <button
                  onClick={() =>
                    action("integration_open_pattern", { direction: 1 })
                  }
                >
                  Next →
                </button>
              </div>
              <p className="integration-filename">
                {source.patternName || "No pattern"}
              </p>
              <p className="integration-note">
                Loaded patterns and overlays use the selected radial coordinate.
              </p>
              <Check
                label="Save background subtracted"
                checked={subtract}
                onChange={setSubtract}
              />
              <button
                className="primary full-input"
                disabled={!source.patternName}
                onClick={() =>
                  action("integration_save_pattern", {
                    subtract_background: subtract,
                  })
                }
              >
                Save pattern…
              </button>
              <p className="integration-note">
                XY · XYE · CHI · DAT · FXYE. Error formats require Poisson
                errors.
              </p>
            </Group>
            <Group title="Autocreate" open>
              <button
                className="secondary full-input"
                onClick={() => action("integration_output_directory")}
              >
                Output folder…
              </button>
              <p
                title={source.outputDirectory}
                className="integration-filename"
              >
                {source.outputDirectory}
              </p>
              <div className="integration-formats">
                {[".xy", ".xye", ".chi", ".dat", ".fxye"].map((format) => (
                  <Check
                    key={format}
                    label={format}
                    checked={draft.formats.includes(format)}
                    onChange={(v) =>
                      set(
                        "formats",
                        v
                          ? [...draft.formats, format]
                          : draft.formats.filter((f) => f !== format),
                      )
                    }
                  />
                ))}
              </div>
              <Check
                label="Autocreate patterns on image load"
                checked={draft.autoSave}
                onChange={(v) => set("autoSave", v)}
              />
              <button
                className="secondary full-input"
                onClick={() =>
                  action("integration_settings", {
                    auto_save: draft.autoSave,
                    formats: draft.formats,
                  })
                }
              >
                Apply autocreate
              </button>
              <p className="integration-note">
                Saves on explicit Load / Previous / Next image.
                Background-subtracted patterns also go into bkg_subtracted.
                Autocreate is off when reopening a project.
              </p>
            </Group>
          </>
        )}
        {tab === "Background" && (
          <>
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
                  set("imageBackground", { ...draft.imageBackground, scale: v })
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
            <Group title="Pattern Background" open>
              <Check
                label="Subtract automatic pattern background"
                checked={draft.patternBackground.enabled}
                onChange={(v) =>
                  set("patternBackground", {
                    ...draft.patternBackground,
                    enabled: v,
                  })
                }
              />
              <Field
                label="Smooth width"
                value={draft.patternBackground.smoothing}
                min={0.000001}
                onChange={(v) =>
                  set("patternBackground", {
                    ...draft.patternBackground,
                    smoothing: v,
                  })
                }
              />
              <div className="integration-fields">
                <Field
                  label="Iterations"
                  value={draft.patternBackground.iterations}
                  min={1}
                  max={99999}
                  step={1}
                  onChange={(v) =>
                    set("patternBackground", {
                      ...draft.patternBackground,
                      iterations: v,
                    })
                  }
                />
                <Field
                  label="Polynomial order"
                  value={draft.patternBackground.order}
                  min={1}
                  max={1000}
                  step={1}
                  onChange={(v) =>
                    set("patternBackground", {
                      ...draft.patternBackground,
                      order: v,
                    })
                  }
                />
              </div>
              <Check
                label="Limit background range"
                checked={bkgRange}
                onChange={setBkgRange}
              />
              {bkgRange && (
                <div className="integration-fields">
                  <Field
                    label="Background minimum"
                    value={bkgMin}
                    onChange={setBkgMin}
                  />
                  <Field
                    label="Background maximum"
                    value={bkgMax}
                    onChange={setBkgMax}
                  />
                </div>
              )}
              <button
                className="primary full-input"
                onClick={() =>
                  action("integration_background", {
                    enabled: draft.patternBackground.enabled,
                    smoothing: draft.patternBackground.smoothing,
                    iterations: draft.patternBackground.iterations,
                    order: draft.patternBackground.order,
                    range: bkgRange ? [bkgMin, bkgMax] : null,
                  })
                }
              >
                Apply pattern background
              </button>
              <button
                className="secondary full-input"
                disabled={!source.patternBackground.enabled}
                onClick={() => action("integration_save_background")}
              >
                Save background…
              </button>
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
          </>
        )}
        {tab === "Corrections" && (
          <>
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
            {Object.entries(draft.corrections).map(([kind, correction]) => (
              <Group
                key={kind}
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
                <button
                  className="primary full-input"
                  onClick={() =>
                    action("integration_correction", {
                      kind,
                      enabled: correction.enabled,
                      parameters: correction.parameters,
                    })
                  }
                >
                  Apply correction
                </button>
              </Group>
            ))}
          </>
        )}
        {tab === "Overlay" && (
          <>
            <div className="file-actions">
              <button
                onClick={() =>
                  action("integration_overlay", { operation: "load" })
                }
              >
                Add file…
              </button>
              <button
                disabled={!source.patternName}
                onClick={() =>
                  action("integration_overlay", { operation: "capture" })
                }
              >
                Add pattern
              </button>
            </div>
            <p className="integration-note">
              Overlays use their file's numerical x coordinates. Select matching
              units before loading.
            </p>
            {source.overlays.map((overlay, index) => (
              <Group
                key={index}
                title={overlay.name || `Overlay ${index + 1}`}
                open
              >
                <Check
                  label={`Show overlay ${index + 1}`}
                  checked={overlay.visible}
                  onChange={(visible) =>
                    action("integration_overlay", {
                      operation: "update",
                      index,
                      visible,
                    })
                  }
                />
                <input
                  type="color"
                  aria-label={`Overlay ${index + 1} color`}
                  value={overlay.color}
                  onChange={(e) =>
                    action("integration_overlay", {
                      operation: "update",
                      index,
                      color: e.target.value,
                    })
                  }
                />
                <div className="integration-fields">
                  <CommitField
                    label={`Overlay ${index + 1} scale`}
                    value={overlay.scale}
                    onCommit={(scale) =>
                      action("integration_overlay", {
                        operation: "update",
                        index,
                        scale,
                      })
                    }
                  />
                  <CommitField
                    label={`Overlay ${index + 1} offset`}
                    value={overlay.offset}
                    onCommit={(offset) =>
                      action("integration_overlay", {
                        operation: "update",
                        index,
                        offset,
                      })
                    }
                  />
                </div>
                <div className="file-actions">
                  <button
                    onClick={() =>
                      action("integration_overlay", {
                        operation: "background",
                        index,
                      })
                    }
                  >
                    As Bkg
                  </button>
                  <button
                    onClick={() =>
                      action("integration_overlay", {
                        operation: "remove",
                        index,
                      })
                    }
                  >
                    Delete
                  </button>
                </div>
              </Group>
            ))}
            <Group title="Waterfall">
              <Field
                label="Waterfall separation"
                value={separation}
                onChange={setSeparation}
              />
              <div className="file-actions">
                <button
                  onClick={() =>
                    action("integration_overlay", {
                      operation: "waterfall",
                      separation,
                    })
                  }
                >
                  Waterfall
                </button>
                <button
                  onClick={() =>
                    action("integration_overlay", {
                      operation: "reset_offsets",
                    })
                  }
                >
                  Reset
                </button>
              </div>
            </Group>
          </>
        )}
        {tab === "Phase" && (
          <>
            <button
              className="secondary full-input"
              onClick={() => action("integration_phase", { operation: "load" })}
            >
              Add phase…
            </button>
            <p className="integration-note">
              JCPDS · CIF · EOSMAT. Conditions and reference selection use the
              existing phase model.
            </p>
            <Check
              label="Apply conditions to all phases"
              checked={source.sameConditions}
              onChange={(enabled) =>
                action("integration_phase", {
                  operation: "same_conditions",
                  enabled,
                })
              }
            />
            {source.phases.map((phase, index) => (
              <Group key={index} title={phase.name} open>
                <Check
                  label={`Show phase ${index + 1}`}
                  checked={phase.visible}
                  onChange={(visible) =>
                    action("integration_phase", {
                      operation: "update",
                      index,
                      visible,
                    })
                  }
                />
                <input
                  type="color"
                  aria-label={`Phase ${index + 1} color`}
                  value={phase.color}
                  onChange={(e) =>
                    action("integration_phase", {
                      operation: "update",
                      index,
                      color: e.target.value,
                    })
                  }
                />
                <div className="integration-fields">
                  <CommitField
                    label={`Phase ${index + 1} pressure (GPa)`}
                    value={phase.pressure}
                    onCommit={(pressure) =>
                      action("integration_phase", {
                        operation: "update",
                        index,
                        pressure,
                      })
                    }
                  />
                  <CommitField
                    label={`Phase ${index + 1} temperature (K)`}
                    value={phase.temperature}
                    onCommit={(temperature) =>
                      action("integration_phase", {
                        operation: "update",
                        index,
                        temperature,
                      })
                    }
                  />
                </div>
                {phase.references.length > 0 && (
                  <label className="field-label">
                    Reference
                    <select
                      aria-label={`Phase ${index + 1} reference`}
                      value={phase.reference}
                      onChange={(e) =>
                        action("integration_phase", {
                          operation: "update",
                          index,
                          reference: Number(e.target.value),
                        })
                      }
                    >
                      {phase.references.map((ref, i) => (
                        <option key={i} value={i}>
                          {ref}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <button
                  className="secondary full-input"
                  onClick={() =>
                    action("integration_phase", { operation: "remove", index })
                  }
                >
                  Delete phase
                </button>
              </Group>
            ))}
          </>
        )}
      </fieldset>
      <button
        className="primary integrate-button"
        disabled={!ready || !state?.calibrated || !state.hasImage}
        onClick={() => action("integrate")}
      >
        Integrate image <span>↵</span>
      </button>
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

/** Compose the shared renderers; visibility never changes scientific arrays. */
export function IntegrationDisplayControls({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div
      className="workspace-toolbar integration-display-controls"
      role="group"
      aria-label="Integration display"
    >
      {[
        ["image", "Image"],
        ["cake", "Cake"],
      ].map(([key, label]) => (
        <button
          key={key}
          aria-pressed={value === key}
          className={value === key ? "active" : ""}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
