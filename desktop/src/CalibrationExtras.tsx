import { Input, Select, Button } from "./ui";
import { useEffect, useState, Fragment } from "react";
import {
  FolderOpen,
  RotateCcw,
  RotateCw,
  FlipHorizontal,
  FlipVertical,
} from "lucide-react";
import type { State } from "./types";
import { CalibrationHelp, calibrationHelp } from "./CalibrationHelp";

import { ScientificNumberInput } from "./ScientificNumberInput";
import { numericDraftError } from "./numericDraft";
import {
  fitParameterLimits,
  fitEnergyLimits,
  type CalibrationFitEditor,
} from "./useCalibrationFitDraft";

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

export function CalibrationExtras({
  state,
  ready,
  run,
  step,
  onDirtyChange,
  fitEditor,
  imageToolsOnly = false,
  hideImageTools = false,
}: {
  state: State | null;
  ready: boolean;
  run: Run;
  step: number;
  onDirtyChange: (value: boolean) => void;
  fitEditor?: CalibrationFitEditor;
  imageToolsOnly?: boolean;
  hideImageTools?: boolean;
}) {
  const c = state?.calibration;
  const {
    parameters = c?.parameters ?? {},
    parameterSettings = c?.parameters ?? {},
    parameterText = {},
    setParameterText,
    setParameters,
    energyText = null,
    setEnergyText,
    polarization = String(c?.polarization ?? 0.99),
    setPolarization,
  } = fitEditor ?? {};
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
              <Button
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
              </Button>
            ))}
          </div>
          {c?.detectorOrientation !== undefined && (
            <label className="field-label">
              Detector orientation
              <Select
                aria-label="Detector orientation"
                value={c?.detectorOrientation ?? 3}
                disabled={!ready}
                onChange={(event) =>
                  run("calibration_setup", {
                    orientation: Number(event.target.value),
                  })
                }
              >
                <option value={0}>Unspecified · standard</option>
                <option value={3}>Bottom right · standard</option>
                <option value={1}>Top left</option>
                <option value={2}>Top right</option>
                <option value={4}>Bottom left</option>
              </Select>
            </label>
          )}
          <hr className="calibration-tool-divider" />
          <div className="file-actions">
            <Button
              type="button"
              disabled={!ready}
              title={c?.detectorFile ?? "Load detector definition"}
              onClick={() =>
                run("detector_file", {}, "Loading detector definition…")
              }
            >
              <FolderOpen size={14} />
              Detector file
            </Button>
            <Button
              type="button"
              variant="quiet"
              disabled={!ready || !c?.detectorFile}
              onClick={() => run("detector_file", { reset: true })}
            >
              Reset
            </Button>
          </div>
          <div className="file-actions">
            <Button
              type="button"
              disabled={!ready}
              title={c?.distortionFile ?? "Load distortion spline"}
              onClick={() =>
                run("distortion_file", {}, "Loading distortion spline…")
              }
            >
              <FolderOpen size={14} />
              Distortion spline
            </Button>
            <Button
              type="button"
              variant="quiet"
              disabled={!ready || !c?.distortionFile}
              onClick={() => run("distortion_file", { reset: true })}
            >
              Reset
            </Button>
          </div>
        </section>
      )}
      {step === 2 && fitEditor && (
        <div className="calibration-fit-controls">
          <section className="calibration-fit-page" aria-label="Fit parameters">
            <h3 className="calibration-fit-heading">Starting values</h3>
            <p className="control-note">
              Seeds for the next fit; they do not change the current geometry
              until you calibrate. Checked parameters are refined; the others
              stay fixed.
            </p>
            <div className="calibration-field-row calibration-calibrant-row">
              <label htmlFor="calibration-calibrant">Calibrant</label>
              <Select
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
              </Select>
              <Button
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
              </Button>
            </div>
            <div className="constraint-heading">
              <span>Parameter</span>
              <span>Start value</span>
              <span title="Checked parameters are refined; unchecked parameters stay fixed at their entered value.">
                Fit
              </span>
            </div>
            {fields.map(([key, label, unit]) => {
              const text =
                parameterText[key] ??
                String(parameterSettings[key]?.value ?? "");
              const error = numericDraftError(text, fitParameterLimits(key));
              return (
                <Fragment key={key}>
                  <div className="constraint-row">
                    <label htmlFor={`constraint-${key}`}>{label}</label>
                    <ScientificNumberInput
                      id={`constraint-${key}`}
                      aria-label={`${label} constraint value`}
                      step="any"
                      min={fitParameterLimits(key).min}
                      max={fitParameterLimits(key).max}
                      disabled={!ready}
                      value={text}
                      aria-invalid={error ? true : undefined}
                      aria-describedby={
                        error ? `constraint-${key}-error` : undefined
                      }
                      onValueChange={(value) => {
                        setParameterText?.((p) => ({ ...p, [key]: value }));
                        if (key === "wavelength") setEnergyText?.(null);
                      }}
                    />
                    <span className="calibration-unit">{unit}</span>
                    <Input
                      aria-label={`Refine ${label.toLowerCase()}`}
                      title="Checked: refine this parameter. Unchecked: hold it fixed."
                      type="checkbox"
                      disabled={!ready}
                      checked={parameters[key]?.refine ?? true}
                      onChange={(e) => {
                        setParameters?.((p) => ({
                          ...p,
                          [key]: { ...p[key], refine: e.target.checked },
                        }));
                      }}
                    />
                    {error && (
                      <span
                        className="ui-field-error constraint-error"
                        id={`constraint-${key}-error`}
                      >
                        {error}
                      </span>
                    )}
                  </div>
                  {key === "wavelength" && (
                    <>
                      <div className="constraint-row calibration-auxiliary-row">
                        <label htmlFor="fit-energy">Energy</label>
                        <ScientificNumberInput
                          id="fit-energy"
                          aria-label="Fit energy in kiloelectronvolts"
                          step="any"
                          disabled={!ready}
                          value={
                            energyText ??
                            (parameters.wavelength?.value > 0
                              ? String(
                                  12.39841984332 / parameters.wavelength.value,
                                )
                              : "")
                          }
                          aria-invalid={
                            energyText !== null &&
                            numericDraftError(energyText, fitEnergyLimits)
                              ? true
                              : undefined
                          }
                          aria-describedby={
                            energyText !== null &&
                            numericDraftError(energyText, fitEnergyLimits)
                              ? "fit-energy-error"
                              : undefined
                          }
                          onValueChange={(value) => {
                            setEnergyText?.(value);
                            setParameterText?.((p) => ({
                              ...p,
                              wavelength: numericDraftError(
                                value,
                                fitEnergyLimits,
                              )
                                ? ""
                                : String(12.39841984332 / Number(value)),
                            }));
                          }}
                        />
                        <span className="calibration-unit">keV</span>
                        {energyText !== null &&
                          numericDraftError(energyText, fitEnergyLimits) && (
                            <span
                              className="ui-field-error constraint-error"
                              id="fit-energy-error"
                            >
                              {numericDraftError(energyText, fitEnergyLimits)}
                            </span>
                          )}
                      </div>
                      <div className="constraint-row calibration-auxiliary-row">
                        <label htmlFor="fit-polarization">Polarization</label>
                        <ScientificNumberInput
                          id="fit-polarization"
                          className="full-input"
                          aria-label="Polarization factor"
                          type="number"
                          step=".01"
                          min="-1"
                          max="1"
                          value={polarization}
                          disabled={!ready}
                          aria-invalid={
                            numericDraftError(polarization, { min: -1, max: 1 })
                              ? true
                              : undefined
                          }
                          aria-describedby={
                            numericDraftError(polarization, { min: -1, max: 1 })
                              ? "fit-polarization-error"
                              : undefined
                          }
                          onValueChange={setPolarization}
                        />
                        {numericDraftError(polarization, {
                          min: -1,
                          max: 1,
                        }) && (
                          <span
                            className="ui-field-error constraint-error"
                            id="fit-polarization-error"
                          >
                            {numericDraftError(polarization, {
                              min: -1,
                              max: 1,
                            })}
                          </span>
                        )}
                      </div>
                    </>
                  )}
                </Fragment>
              );
            })}
          </section>
          <section
            className="calibration-fit-page calibration-refinement-section"
            aria-label="Refinement options"
          >
            <h3 className="calibration-fit-heading">Refinement</h3>
            <label className="check-row">
              <Input
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
                  <Select
                    id="refinement-algorithm"
                    aria-label="Refinement peak-search algorithm"
                    value={workflow.algorithm}
                    disabled={!ready}
                    onChange={(e) => toggle("algorithm", e.target.value)}
                  >
                    <option>Massif</option>
                    <option>Blob</option>
                  </Select>
                </div>
                {(
                  [
                    ["deltaTth", "Search width Δ2θ (°)"],
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
                    <Input
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
              <Input
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
            <Button
              type="button"
              className="icon-button"
              aria-label="Load mask"
              title="Load mask"
              disabled={!ready || !state?.hasImage}
              onClick={() => run("mask_file", {}, "Loading mask…")}
            >
              <FolderOpen size={16} />
            </Button>
          </div>
          <label className="check-row">
            <Input
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

export { GeometryEditor, ManualGeometryDialog } from "./GeometryEditor";
