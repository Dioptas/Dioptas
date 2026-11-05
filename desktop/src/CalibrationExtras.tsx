import { ScientificNumberInput } from "./ScientificNumberInput";
import { Dialog, DialogHeader } from "./Dialog";
import { TabList } from "./TabList";
import { useEffect, useState, useRef, Fragment } from "react";
import {
  Check,
  FolderOpen,
  RotateCcw,
  RotateCw,
  FlipHorizontal,
  FlipVertical,
} from "lucide-react";
import type { Calibration, State } from "./types";
import { CalibrationHelp, calibrationHelp } from "./CalibrationHelp";

type Run = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => unknown;
const fields = [
  ["dist", "Distance", "mm"],
  ["wavelength", "Wavelength", "Å"],
  ["rot1", "Rotation 1", "rad"],
  ["rot2", "Rotation 2", "rad"],
  ["rot3", "Rotation 3", "rad"],
  ["poni1", "PONI 1", "mm"],
  ["poni2", "PONI 2", "mm"],
] as const;
export type CalibrationFitDraft = {
  parameters: Calibration["parameters"];
  polarization: number;
};

export function CalibrationExtras({
  state,
  ready,
  run,
  step,
  onDirtyChange,
  onFitDraftChange,
  imageToolsOnly = false,
  hideImageTools = false,
}: {
  state: State | null;
  ready: boolean;
  run: Run;
  step: number;
  onDirtyChange: (value: boolean) => void;
  onFitDraftChange?: (draft: CalibrationFitDraft | null) => void;
  imageToolsOnly?: boolean;
  hideImageTools?: boolean;
}) {
  const c = state?.calibration;
  const [parameters, setParameters] = useState<Calibration["parameters"]>(
    c?.parameters ?? {},
  );
  const [polarization, setPolarization] = useState(
    String(c?.polarization ?? 0.99),
  );

  useEffect(() => {
    if (c) {
      setParameters(c.parameters);
      setPolarization(String(c.polarization));
    }
  }, [JSON.stringify(c?.parameters), c?.polarization]);

  useEffect(() => {
    onFitDraftChange?.({ parameters, polarization: Number(polarization) });
  }, [parameters, polarization, onFitDraftChange]);
  useEffect(() => () => onFitDraftChange?.(null), [onFitDraftChange]);
  const [refinementDraft, setRefinementDraft] = useState<
    Record<string, string>
  >({});
  const workflow = c?.workflow;
  useEffect(() => {
    setRefinementDraft({});
  }, [
    workflow?.deltaTth,
    workflow?.meanFactor,
    workflow?.intensityLimit,
    workflow?.numberOfRings,
  ]);
  const refinementDirty =
    !!workflow &&
    Object.entries(refinementDraft).some(
      ([key, value]) =>
        Number(value) !== Number(workflow[key as keyof typeof workflow]),
    );
  useEffect(() => {
    onDirtyChange(refinementDirty);
  }, [refinementDirty, onDirtyChange]);
  const toggle = (name: string, value: unknown) =>
    run("workflow_settings", { [name]: value });
  return (
    <>
      {step === 0 && !hideImageTools && (
        <section className="image-detector-tools">
          <div className="calibration-group-label">Image orientation</div>
          <div className="orientation-tools">
            {(
              [
                ["rotate_left", "Rotate image −90°", RotateCcw, "Rotate −90°"],
                ["rotate_right", "Rotate image +90°", RotateCw, "Rotate +90°"],
                [
                  "flip_horizontal",
                  "Flip image horizontally",
                  FlipHorizontal,
                  "Flip horizontal",
                ],
                [
                  "flip_vertical",
                  "Flip image vertically",
                  FlipVertical,
                  "Flip vertical",
                ],
                [
                  "reset",
                  "Reset image transformations",
                  RotateCcw,
                  "Reset transformations",
                ],
              ] as const
            ).map(([operation, label, Icon, text]) => (
              <button
                type="button"
                key={operation}
                className={operation === "reset" ? "quiet" : "secondary"}
                title={label}
                aria-label={label}
                disabled={!ready || !state?.hasImage}
                onClick={() =>
                  run("image_transform", { operation }, "Transforming image…")
                }
              >
                <Icon size={15} />
                {text}
              </button>
            ))}
          </div>
          <hr className="calibration-tool-divider" />
          <div className="file-actions">
            <button
              type="button"
              disabled={!ready}
              title={c?.detectorFile ?? "Load detector definition"}
              onClick={() =>
                run("detector_file", {}, "Loading detector definition…")
              }
            >
              <FolderOpen size={14} />
              Detector file
            </button>
            <button
              type="button"
              className="quiet"
              disabled={!ready || !c?.detectorFile}
              onClick={() => run("detector_file", { reset: true })}
            >
              Reset
            </button>
          </div>
          <div className="file-actions">
            <button
              type="button"
              disabled={!ready}
              title={c?.distortionFile ?? "Load distortion spline"}
              onClick={() =>
                run("distortion_file", {}, "Loading distortion spline…")
              }
            >
              <FolderOpen size={14} />
              Distortion spline
            </button>
            <button
              type="button"
              className="quiet"
              disabled={!ready || !c?.distortionFile}
              onClick={() => run("distortion_file", { reset: true })}
            >
              Reset
            </button>
          </div>
        </section>
      )}
      {step === 2 && (
        <div className="calibration-fit-controls">
          <section className="calibration-fit-page" aria-label="Fit parameters">
            <h3 className="calibration-fit-heading">Parameters</h3>
            <div className="calibration-field-row calibration-calibrant-row">
              <label htmlFor="calibration-calibrant">Calibrant</label>
              <select
                id="calibration-calibrant"
                aria-label="Calibration calibrant"
                disabled={!ready}
                value={c?.calibrant ?? "CeO2"}
                onChange={(e) =>
                  run(
                    "calibration_setup",
                    { calibrant: e.target.value },
                    "Loading calibrant…",
                  )
                }
              >
                {(c?.calibrants ?? ["CeO2"]).map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
              <button
                type="button"
                className="icon-button"
                aria-label="Load custom calibrant…"
                title="Load custom calibrant spacings (.D)"
                disabled={!ready}
                onClick={() =>
                  run("open_calibrant", {}, "Loading calibrant spacings…")
                }
              >
                <FolderOpen size={16} />
              </button>
            </div>
            <div className="constraint-heading">
              <span>Parameter</span>
              <span>Value</span>
              <span title="Checked parameters are refined; unchecked parameters stay fixed at their entered value.">
                Fit
              </span>
            </div>
            {fields.map(([key, label, unit]) => (
              <Fragment key={key}>
                <div className="constraint-row">
                  <label htmlFor={`constraint-${key}`}>{label}</label>
                  <input
                    id={`constraint-${key}`}
                    aria-label={`${label} constraint value`}
                    type="number"
                    step="any"
                    disabled={!ready}
                    value={parameters[key]?.value ?? ""}
                    onChange={(e) => {
                      setParameters((p) => ({
                        ...p,
                        [key]: { ...p[key], value: Number(e.target.value) },
                      }));
                    }}
                  />
                  <span className="calibration-unit">{unit}</span>
                  <input
                    aria-label={`Refine ${label.toLowerCase()}`}
                    title="Checked: refine this parameter. Unchecked: hold it fixed."
                    type="checkbox"
                    disabled={!ready}
                    checked={parameters[key]?.refine ?? true}
                    onChange={(e) => {
                      setParameters((p) => ({
                        ...p,
                        [key]: { ...p[key], refine: e.target.checked },
                      }));
                    }}
                  />
                </div>
                {key === "wavelength" && (
                  <>
                    <div className="constraint-row calibration-auxiliary-row">
                      <label htmlFor="fit-energy">Energy</label>
                      <input
                        id="fit-energy"
                        aria-label="Fit energy in kiloelectronvolts"
                        type="number"
                        step="any"
                        min="0"
                        disabled={!ready}
                        value={
                          parameters.wavelength?.value > 0
                            ? Number(
                                (
                                  12.39841984332 / parameters.wavelength.value
                                ).toFixed(4),
                              )
                            : ""
                        }
                        onChange={(e) => {
                          const value = Number(e.target.value);
                          if (value > 0)
                            setParameters((p) => ({
                              ...p,
                              wavelength: {
                                ...p.wavelength,
                                value: 12.39841984332 / value,
                              },
                            }));
                        }}
                      />
                      <span className="calibration-unit">keV</span>
                    </div>
                    <div className="constraint-row calibration-auxiliary-row">
                      <label htmlFor="fit-polarization">Polarization</label>
                      <input
                        id="fit-polarization"
                        className="full-input"
                        aria-label="Polarization factor"
                        type="number"
                        step=".01"
                        min="-1"
                        max="1"
                        value={polarization}
                        disabled={!ready}
                        onChange={(e) => {
                          setPolarization(e.target.value);
                        }}
                      />
                    </div>
                  </>
                )}
              </Fragment>
            ))}
          </section>
          <section
            className="calibration-fit-page calibration-refinement-section"
            aria-label="Refinement options"
          >
            <h3 className="calibration-fit-heading">Refinement</h3>
            <label className="check-row">
              <input
                aria-label="Automatic refinement"
                type="checkbox"
                disabled={!ready}
                checked={workflow?.automaticRefinement ?? true}
                onChange={(e) =>
                  toggle("automaticRefinement", e.target.checked)
                }
              />
              Automatic refinement
            </label>
            {workflow?.automaticRefinement && (
              <>
                <div className="calibration-field-row">
                  <label htmlFor="refinement-algorithm">
                    Peak-search algorithm
                  </label>
                  <select
                    id="refinement-algorithm"
                    aria-label="Refinement peak-search algorithm"
                    value={workflow.algorithm}
                    disabled={!ready}
                    onChange={(e) => toggle("algorithm", e.target.value)}
                  >
                    <option>Massif</option>
                    <option>Blob</option>
                  </select>
                </div>
                {(
                  [
                    ["deltaTth", "Search width Δ2θ · °"],
                    ["meanFactor", "Intensity mean factor"],
                    ["intensityLimit", "Upper intensity limit"],
                    ["numberOfRings", "Number of rings"],
                  ] as const
                ).map(([key, label]) => (
                  <div
                    className="calibration-field-row calibration-refinement-field"
                    key={key}
                  >
                    <label htmlFor={`refinement-${key}`}>{label}</label>
                    <input
                      id={`refinement-${key}`}
                      className="full-input"
                      aria-label={label}
                      type="number"
                      step={key === "numberOfRings" ? 1 : "any"}
                      min={key === "numberOfRings" ? 1 : 0.00001}
                      max={key === "numberOfRings" ? 100 : 1e15}
                      required
                      disabled={!ready}
                      value={refinementDraft[key] ?? String(workflow[key])}
                      onChange={(e) =>
                        setRefinementDraft((draft) => ({
                          ...draft,
                          [key]: e.target.value,
                        }))
                      }
                      onBlur={(e) => {
                        const value = e.currentTarget.valueAsNumber;
                        if (
                          ready &&
                          e.currentTarget.validity.valid &&
                          value !== workflow[key]
                        )
                          toggle(key, value);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          if (e.currentTarget.reportValidity())
                            e.currentTarget.blur();
                        }
                      }}
                    />
                    <CalibrationHelp
                      label={label}
                      text={calibrationHelp[key]}
                    />
                  </div>
                ))}
              </>
            )}
          </section>
        </div>
      )}
      {!imageToolsOnly && (step === 0 || step === 3) && (
        <section
          className="calibration-mask-controls"
          aria-label="Detector mask"
        >
          <div className="calibration-mask-row">
            <label className="check-row">
              <input
                aria-label="Use mask"
                type="checkbox"
                checked={state?.useMask ?? false}
                disabled={!ready || !state?.hasImage}
                onChange={(e) =>
                  run(
                    "settings",
                    { use_mask: e.target.checked },
                    "Updating mask…",
                  )
                }
              />
              Use mask
            </label>
            <button
              type="button"
              className="icon-button"
              aria-label="Load mask"
              title="Load mask"
              disabled={!ready || !state?.hasImage}
              onClick={() => run("mask_file", {}, "Loading mask…")}
            >
              <FolderOpen size={16} />
            </button>
          </div>
          <label className="check-row">
            <input
              aria-label="Transparent"
              type="checkbox"
              checked={state?.transparentMask ?? false}
              disabled={!ready || !state?.useMask}
              onChange={(e) =>
                run("settings", { transparent_mask: e.target.checked })
              }
            />
            Transparent
          </label>
        </section>
      )}
    </>
  );
}

const pyfaiFields = [
  ["dist", "Distance", "mm", 1000],
  ["poni1", "PONI 1", "m", 1],
  ["poni2", "PONI 2", "m", 1],
  ["rot1", "Rotation 1", "rad", 1],
  ["rot2", "Rotation 2", "rad", 1],
  ["rot3", "Rotation 3", "rad", 1],
  ["pixel1", "Pixel height", "µm", 1e6],
  ["pixel2", "Pixel width", "µm", 1e6],
  ["wavelength", "Wavelength", "Å", 1e10],
  ["polarization_factor", "Polarization", "", 1],
] as const;
const fit2dFields = [
  ["directDist", "Direct distance", "mm", 1],
  ["centerX", "Center x", "pixels", 1],
  ["centerY", "Center y", "pixels", 1],
  ["tilt", "Tilt", "°", 1],
  ["tiltPlanRotation", "Tilt rotation", "°", 1],
  ["pixelX", "Pixel width", "µm", 1],
  ["pixelY", "Pixel height", "µm", 1],
  ["wavelength", "Wavelength", "Å", 1e10],
  ["polarization_factor", "Polarization", "", 1],
] as const;
export function GeometryEditor({
  calibration: c,
  ready,
  run,
  open = false,
  embedded = false,
  onDirtyChange,
  onActiveDirtyChange,
  formId,
  convention: savedConvention,
  onConventionChange,
}: {
  calibration?: Calibration;
  ready: boolean;
  run: Run;
  open?: boolean;
  embedded?: boolean;
  formId?: string;
  convention?: "pyfai" | "fit2d";
  onConventionChange?: (convention: "pyfai" | "fit2d") => void;
  onDirtyChange?: (dirty: boolean) => void;
  onActiveDirtyChange?: (dirty: boolean) => void;
}) {
  const [localConvention, setLocalConvention] = useState<"pyfai" | "fit2d">(
    "pyfai",
  );
  const convention = savedConvention ?? localConvention;
  const setConvention = (value: "pyfai" | "fit2d") => {
    setLocalConvention(value);
    onConventionChange?.(value);
  };
  const [drafts, setDrafts] = useState<
    Record<"pyfai" | "fit2d", Record<string, string>>
  >({ pyfai: {}, fit2d: {} });
  const fields = convention === "pyfai" ? pyfaiFields : fit2dFields;
  const draft = drafts[convention];
  useEffect(() => {
    const valuesFor = (name: "pyfai" | "fit2d") =>
      Object.fromEntries(
        (name === "pyfai" ? pyfaiFields : fit2dFields).map(
          ([key, , , factor]) => [
            key,
            String((c?.[name]?.[key] ?? 0) * factor),
          ],
        ),
      );
    setDrafts({ pyfai: valuesFor("pyfai"), fit2d: valuesFor("fit2d") });
  }, [JSON.stringify(c?.pyfai), JSON.stringify(c?.fit2d)]);
  const changed = (name: "pyfai" | "fit2d") =>
    (name === "pyfai" ? pyfaiFields : fit2dFields).some(([key, , , factor]) => {
      const text = drafts[name][key];
      return (
        text !== undefined &&
        (text.trim() === "" ||
          !Number.isFinite(Number(text)) ||
          Number(text) !== (c?.[name]?.[key] ?? 0) * factor)
      );
    });
  const dirty = changed("pyfai") || changed("fit2d");
  const activeDirty = changed(convention);
  const otherConvention = convention === "pyfai" ? "fit2d" : "pyfai";
  const otherDirty = changed(otherConvention);
  useEffect(() => {
    onActiveDirtyChange?.(activeDirty);
  }, [activeDirty, onActiveDirtyChange]);
  useEffect(() => () => onActiveDirtyChange?.(false), [onActiveDirtyChange]);
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  const applyGeometry = () => {
    if (!activeDirty) return;
    return run(
      "manual_geometry",
      {
        convention,
        values: Object.fromEntries(
          fields.map(([key, , , factor]) => [
            key,
            Number(draft[key]) === (c?.[convention]?.[key] ?? 0) * factor
              ? (c?.[convention]?.[key] ?? 0)
              : Number(draft[key]) / factor,
          ]),
        ),
      },
      "Applying geometry…",
    );
  };
  const content = (
    <>
      <TabList
        className="geometry-tabs"
        label="Geometry convention"
        value={convention}
        onChange={setConvention}
        options={(["pyfai", "fit2d"] as const).map((value) => ({
          value,
          label: value === "pyfai" ? "pyFAI" : "Fit2D",
          title: changed(value)
            ? `${value === "pyfai" ? "pyFAI" : "Fit2D"} · unapplied changes`
            : undefined,
        }))}
      />
      {dirty && (
        <p className="control-note">
          {otherDirty
            ? `${otherConvention === "pyfai" ? "pyFAI" : "Fit2D"} has unapplied edits. Return there to apply or reset; this convention remains available for comparison.`
            : "Apply or reset this geometry draft before editing the other convention."}
        </p>
      )}
      {fields.map(([key, label, unit]) => (
        <label className="geometry-field" key={key}>
          <span>{label}</span>
          <ScientificNumberInput
            aria-label={`Manual ${label.toLowerCase()}`}
            required
            type="number"
            step="any"
            disabled={!ready || otherDirty}
            title={draft[key] ?? ""}
            value={draft[key] ?? ""}
            onValueChange={(value) =>
              setDrafts((values) => ({
                ...values,
                [convention]: { ...values[convention], [key]: value },
              }))
            }
          />
          <span className="calibration-unit">{unit}</span>
        </label>
      ))}
      {!formId && (
        <>
          <button
            type="button"
            className="secondary full-input"
            disabled={
              !ready ||
              !activeDirty ||
              fields.some(
                ([key]) =>
                  draft[key] === "" || !Number.isFinite(Number(draft[key])),
              )
            }
            onClick={applyGeometry}
          >
            <Check size={14} />
            Apply geometry
          </button>
          {activeDirty && (
            <button
              type="button"
              className="quiet full-input"
              onClick={() =>
                setDrafts((values) => ({
                  ...values,
                  [convention]: Object.fromEntries(
                    fields.map(([key, , , factor]) => [
                      key,
                      String((c?.[convention]?.[key] ?? 0) * factor),
                    ]),
                  ),
                }))
              }
            >
              Reset geometry draft
            </button>
          )}
        </>
      )}
    </>
  );
  return embedded ? (
    <section className="geometry-editor">
      {formId ? (
        <form
          id={formId}
          onSubmit={(event) => {
            event.preventDefault();
            if (ready) applyGeometry();
          }}
        >
          {content}
        </form>
      ) : (
        content
      )}
    </section>
  ) : (
    <details className="compact-section" open={open}>
      <summary>Manual geometry · pyFAI / Fit2D</summary>
      {content}
    </details>
  );
}

export function ManualGeometryDialog({
  calibration,
  ready,
  run,
  onClose,
}: {
  calibration?: Calibration;
  ready: boolean;
  run: Run;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <Dialog
      dialogRef={dialog}
      className="manual-geometry-dialog"
      aria-label="Enter calibration manually"
      onDismiss={onClose}
      onClose={onClose}
    >
      <DialogHeader
        title="Enter calibration manually"
        closeLabel="Close manual geometry"
        onClose={onClose}
      />
      <GeometryEditor
        calibration={calibration}
        ready={ready}
        run={run}
        embedded
      />
    </Dialog>
  );
}
