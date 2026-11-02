import { useEffect, useState, useRef, Fragment } from "react";
import {
  Check,
  FolderOpen,
  RotateCcw,
  RotateCw,
  FlipHorizontal,
  FlipVertical,
} from "lucide-react";
import { CalibrationTabs } from "./CalibrationLayout";
import type { Calibration, State } from "./types";

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
];
export function CalibrationExtras({
  state,
  ready,
  run,
  step,
  onDirtyChange,
  imageToolsOnly = false,
  hideImageTools = false,
}: {
  state: State | null;
  ready: boolean;
  run: Run;
  step: number;
  onDirtyChange: (value: boolean) => void;
  imageToolsOnly?: boolean;
  hideImageTools?: boolean;
}) {
  const c = state?.calibration;
  const [fitTab, setFitTab] = useState(0);
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

  const dirty =
    !!c &&
    (Object.entries(parameters).some(
      ([key, p]) =>
        p.value !== c.parameters[key]?.value ||
        p.refine !== c.parameters[key]?.refine,
    ) ||
      Number(polarization) !== c.polarization);
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
    onDirtyChange(dirty || refinementDirty);
  }, [dirty, refinementDirty, onDirtyChange]);
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
                className="secondary"
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
              disabled={!ready || !c?.distortionFile}
              onClick={() => run("distortion_file", { reset: true })}
            >
              Reset
            </button>
          </div>
        </section>
      )}
      {step === 2 && (
        <CalibrationTabs
          label="Calibration fit sections"
          tabs={["Parameters", "Refinement"]}
          active={fitTab}
          onChange={setFitTab}
        />
      )}
      {step === 2 && (
        <section className="calibration-fit-page" hidden={fitTab !== 0}>
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
                  <label className="constraint-row calibration-auxiliary-row">
                    <span>Energy</span>
                    <input
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
                  </label>
                  <label className="constraint-row calibration-auxiliary-row">
                    <span>Polarization</span>
                    <input
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
                  </label>
                </>
              )}
            </Fragment>
          ))}
          <button
            type="button"
            className="secondary full-input"
            disabled={!ready || (!dirty && !!c?.setupConfirmed)}
            onClick={() =>
              run(
                "fit_parameters",
                { parameters, polarization: Number(polarization) },
                "Applying fit constraints…",
              )
            }
          >
            <Check size={14} />
            Apply fit parameters
          </button>
        </section>
      )}
      {step === 2 && (
        <section className="calibration-fit-page" hidden={fitTab !== 1}>
          <label className="check-row">
            <input
              aria-label="Automatic refinement"
              type="checkbox"
              disabled={!ready}
              checked={workflow?.automaticRefinement ?? true}
              onChange={(e) => toggle("automaticRefinement", e.target.checked)}
            />
            Automatic refinement
          </label>
          {workflow?.automaticRefinement && (
            <>
              <label className="calibration-field-row">
                <span>Peak-search algorithm</span>
                <select
                  aria-label="Refinement peak-search algorithm"
                  value={workflow.algorithm}
                  disabled={!ready}
                  onChange={(e) => toggle("algorithm", e.target.value)}
                >
                  <option>Massif</option>
                  <option>Blob</option>
                </select>
              </label>
              {(
                [
                  ["deltaTth", "Search width Δ2θ · °"],
                  ["meanFactor", "Intensity mean factor"],
                  ["intensityLimit", "Upper intensity limit"],
                  ["numberOfRings", "Number of rings"],
                ] as const
              ).map(([key, label]) => (
                <label className="calibration-field-row" key={key}>
                  <span>{label}</span>
                  <input
                    className="full-input"
                    aria-label={label}
                    type="number"
                    step={key === "numberOfRings" ? 1 : "any"}
                    disabled={!ready}
                    value={refinementDraft[key] ?? String(workflow[key])}
                    onChange={(e) =>
                      setRefinementDraft((draft) => ({
                        ...draft,
                        [key]: e.target.value,
                      }))
                    }
                  />
                </label>
              ))}
              {refinementDirty && (
                <button
                  type="button"
                  className="secondary full-input"
                  disabled={!ready}
                  onClick={() =>
                    run(
                      "workflow_settings",
                      Object.fromEntries(
                        Object.entries(refinementDraft).map(([key, value]) => [
                          key,
                          Number(value),
                        ]),
                      ),
                    )
                  }
                >
                  Apply refinement options
                </button>
              )}
            </>
          )}
        </section>
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
  formId,
}: {
  calibration?: Calibration;
  ready: boolean;
  run: Run;
  open?: boolean;
  embedded?: boolean;
  formId?: string;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const [convention, setConvention] = useState<"pyfai" | "fit2d">("pyfai");
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
            String(Number(((c?.[name]?.[key] ?? 0) * factor).toPrecision(10))),
          ],
        ),
      );
    setDrafts({ pyfai: valuesFor("pyfai"), fit2d: valuesFor("fit2d") });
  }, [JSON.stringify(c?.pyfai), JSON.stringify(c?.fit2d)]);
  const dirty = (["pyfai", "fit2d"] as const).some((name) =>
    (name === "pyfai" ? pyfaiFields : fit2dFields).some(([key, , , factor]) => {
      const value = (c?.[name]?.[key] ?? 0) * factor;
      const text = drafts[name][key];
      return (
        text !== undefined &&
        (text === "" ||
          !Number.isFinite(Number(text)) ||
          Math.abs(Number(text) - value) >
            Math.max(1e-10, Math.abs(value) * 1e-9))
      );
    }),
  );
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  const applyGeometry = () =>
    run(
      "manual_geometry",
      {
        convention,
        values: Object.fromEntries(
          fields.map(([key, , , factor]) => [key, Number(draft[key]) / factor]),
        ),
      },
      "Applying geometry…",
    );
  const content = (
    <>
      <div
        className="geometry-tabs"
        role="tablist"
        aria-label="Geometry convention"
      >
        {(["pyfai", "fit2d"] as const).map((value) => (
          <button
            type="button"
            key={value}
            role="tab"
            aria-selected={convention === value}
            tabIndex={convention === value ? 0 : -1}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
                event.preventDefault();
                setConvention(value === "pyfai" ? "fit2d" : "pyfai");
                event.currentTarget.parentElement
                  ?.querySelectorAll<HTMLButtonElement>("button")
                  [value === "pyfai" ? 1 : 0]?.focus();
              }
            }}
            onClick={() => setConvention(value)}
          >
            {value === "pyfai" ? "pyFAI" : "Fit2D"}
          </button>
        ))}
      </div>
      {dirty && !formId && (
        <p className="control-note">Apply geometry to continue.</p>
      )}
      {fields.map(([key, label, unit]) => (
        <label className="geometry-field" key={key}>
          <span>{label}</span>
          <input
            aria-label={`Manual ${label.toLowerCase()}`}
            required
            type="number"
            step="any"
            disabled={!ready}
            title={draft[key] ?? ""}
            value={draft[key] ?? ""}
            onChange={(e) =>
              setDrafts((values) => ({
                ...values,
                [convention]: { ...values[convention], [key]: e.target.value },
              }))
            }
          />
          <span className="calibration-unit">{unit}</span>
        </label>
      ))}
      {!formId && (
        <button
          type="button"
          className="secondary full-input"
          disabled={
            !ready ||
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
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog ref={dialog} className="manual-geometry-dialog" onClose={onClose}>
      <div className="manual-geometry-heading">
        <h2>Enter calibration manually</h2>
        <button
          type="button"
          autoFocus
          onClick={() => dialog.current?.close()}
          aria-label="Close manual geometry"
        >
          Close
        </button>
      </div>
      <GeometryEditor
        calibration={calibration}
        ready={ready}
        run={run}
        embedded
      />
    </dialog>
  );
}
