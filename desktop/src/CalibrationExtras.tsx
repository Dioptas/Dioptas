import { useEffect, useState } from "react";
import {
  Check,
  FolderOpen,
  RotateCcw,
  RotateCw,
  FlipHorizontal,
  FlipVertical,
} from "lucide-react";
import type { Calibration, State } from "./types";

type Run = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => unknown;
const fields = [
  ["dist", "Distance", "mm"],
  ["wavelength", "Wavelength", "Å"],
  ["poni1", "PONI 1", "mm"],
  ["poni2", "PONI 2", "mm"],
  ["rot1", "Rotation 1", "rad"],
  ["rot2", "Rotation 2", "rad"],
  ["rot3", "Rotation 3", "rad"],
];
export function CalibrationExtras({
  state,
  ready,
  run,
  step,
  onDirtyChange,
}: {
  state: State | null;
  ready: boolean;
  run: Run;
  step: number;
  onDirtyChange: (value: boolean) => void;
}) {
  const c = state?.calibration;
  const [parameters, setParameters] = useState<Calibration["parameters"]>({});
  const [polarization, setPolarization] = useState("0.99");

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
      {step === 0 && (
        <details className="compact-section" open={step === 0}>
          <summary>Image & detector</summary>
          <div className="orientation-tools">
            {(
              [
                ["rotate_left", "Rotate image −90°", RotateCcw],
                ["rotate_right", "Rotate image +90°", RotateCw],
                ["flip_horizontal", "Flip image horizontally", FlipHorizontal],
                ["flip_vertical", "Flip image vertically", FlipVertical],
                ["reset", "Reset image transformations", RotateCcw],
              ] as const
            ).map(([operation, label, Icon]) => (
              <button
                key={operation}
                className="icon-button"
                title={label}
                aria-label={label}
                disabled={!ready || !state?.hasImage}
                onClick={() =>
                  run("image_transform", { operation }, "Transforming image…")
                }
              >
                <Icon size={17} />
              </button>
            ))}
          </div>
          <div className="file-actions">
            <button
              disabled={!ready}
              onClick={() =>
                run("detector_file", {}, "Loading detector definition…")
              }
            >
              <FolderOpen size={14} />
              Detector file
            </button>
            <button
              disabled={!ready || !c?.detectorFile}
              onClick={() => run("detector_file", { reset: true })}
            >
              Reset
            </button>
          </div>
          {c?.detectorFile && (
            <p className="file-path" title={c.detectorFile}>
              {c.detectorFile.split(/[\\/]/).at(-1)}
            </p>
          )}
          <div className="file-actions">
            <button
              disabled={!ready}
              onClick={() =>
                run("distortion_file", {}, "Loading distortion spline…")
              }
            >
              <FolderOpen size={14} />
              Distortion spline
            </button>
            <button
              disabled={!ready || !c?.distortionFile}
              onClick={() => run("distortion_file", { reset: true })}
            >
              Reset
            </button>
          </div>
          {c?.distortionFile && (
            <p className="file-path" title={c.distortionFile}>
              {c.distortionFile.split(/[\\/]/).at(-1)}
            </p>
          )}
        </details>
      )}
      {step === 2 && (
        <details className="compact-section" open={step === 2}>
          <summary>Fit parameters</summary>
          <div className="constraint-heading">
            <span>Parameter · unit</span>
            <span>Value</span>
            <span>Fit</span>
          </div>
          {fields.map(([key, label, unit]) => (
            <div className="constraint-row" key={key}>
              <label htmlFor={`constraint-${key}`}>
                {label}
                <small>{unit}</small>
              </label>
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
              <input
                aria-label={`Refine ${label.toLowerCase()}`}
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
          ))}
          <label className="field-label">
            Polarization factor
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
          <button
            className="secondary full-input"
            disabled={!ready || !dirty}
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
          <p className="control-note">
            Checked parameters are refined. Unchecked parameters stay fixed at
            the entered value.
          </p>
        </details>
      )}
      {step === 2 && (
        <details className="compact-section" open={step === 2}>
          <summary>Refinement options</summary>
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
              <label className="field-label">
                Peak-search algorithm
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
                <label className="field-label" key={key}>
                  {label}
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
        </details>
      )}
      {(step === 0 || step === 3) && (
        <details className="compact-section" open={step === 0}>
          <summary>Detector mask</summary>
          <label className="check-row">
            <input
              aria-label="Use mask during calibration"
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
            Use detector mask
          </label>
          <div className="file-actions">
            <button
              disabled={!ready || !state?.hasImage}
              onClick={() => run("mask_file", {}, "Loading mask…")}
            >
              Load mask
            </button>
            <button
              disabled={!ready || !state?.hasImage}
              onClick={() => run("mask_file", { save: true }, "Saving mask…")}
            >
              Save mask
            </button>
          </div>
        </details>
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
}: {
  calibration?: Calibration;
  ready: boolean;
  run: Run;
  open?: boolean;
}) {
  const [convention, setConvention] = useState<"pyfai" | "fit2d">("pyfai");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const fields = convention === "pyfai" ? pyfaiFields : fit2dFields;
  useEffect(() => {
    const values = c?.[convention] ?? {};
    setDraft(
      Object.fromEntries(
        fields.map(([key, , , factor]) => [
          key,
          String(Number(((values[key] ?? 0) * factor).toPrecision(10))),
        ]),
      ),
    );
  }, [convention, JSON.stringify(c?.[convention])]);
  return (
    <details className="compact-section" open={open}>
      <summary>Manual geometry · pyFAI / Fit2D</summary>
      <select
        aria-label="Geometry convention"
        value={convention}
        onChange={(e) => setConvention(e.target.value as "pyfai" | "fit2d")}
      >
        <option value="pyfai">pyFAI</option>
        <option value="fit2d">Fit2D</option>
      </select>
      {fields.map(([key, label, unit]) => (
        <label className="geometry-field" key={key}>
          <span>
            {label}
            <small>{unit}</small>
          </span>
          <input
            aria-label={`Manual ${label.toLowerCase()}`}
            type="number"
            step="any"
            disabled={!ready}
            value={draft[key] ?? ""}
            onChange={(e) => setDraft((v) => ({ ...v, [key]: e.target.value }))}
          />
        </label>
      ))}
      <button
        className="secondary full-input"
        disabled={
          !ready ||
          fields.some(
            ([key]) =>
              draft[key] === "" || !Number.isFinite(Number(draft[key])),
          )
        }
        onClick={() =>
          run(
            "manual_geometry",
            {
              convention,
              values: Object.fromEntries(
                fields.map(([key, , , factor]) => [
                  key,
                  Number(draft[key]) / factor,
                ]),
              ),
            },
            "Applying geometry…",
          )
        }
      >
        <Check size={14} />
        Apply geometry
      </button>
    </details>
  );
}
