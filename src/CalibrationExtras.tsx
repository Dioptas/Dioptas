import { Input, Button } from "./ui";
import { useEffect, Fragment } from "react";
import {
  FolderOpen,
  RotateCcw,
  RotateCcwSquare,
  RotateCwSquare,
  FlipHorizontal2,
  FlipVertical2,
} from "lucide-react";
import type { State } from "./types";

import { ScientificNumberInput } from "./ScientificNumberInput";
import { numericDraftError } from "./numericDraft";
import {
  fitParameterLimits,
  fitEnergyLimits,
  formatCleanNumber,
  type CalibrationFitEditor,
} from "./useCalibrationFitDraft";

type Run = import("./commandContracts").Run;
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
  useEffect(() => {
    onDirtyChange(false);
  }, [onDirtyChange]);
  return (
    <>
      {step === 0 && imageToolsOnly && fitEditor && (
        <section
          className="calibration-fit-page calibration-beam-setup"
          aria-label="Beam and start parameters"
        >
          <div className="setup-pair">
            <div className="field-label">
              <div className="calibration-field-header">
                <label htmlFor="setup-wavelength">Wavelength · Å</label>
                <label
                  className="calibration-inline-fit"
                  title="Checked: refine wavelength during calibration. Unchecked: hold wavelength fixed."
                >
                  <Input
                    aria-label="Refine wavelength"
                    type="checkbox"
                    disabled={!ready}
                    checked={parameters.wavelength?.refine ?? false}
                    onChange={(e) =>
                      setParameters?.((p) => ({
                        ...p,
                        wavelength: {
                          ...p.wavelength,
                          refine: e.target.checked,
                        },
                      }))
                    }
                  />
                  Fit
                </label>
              </div>
              <ScientificNumberInput
                id="setup-wavelength"
                aria-label="Wavelength in angstroms"
                step="any"
                disabled={!ready}
                value={
                  parameterText.wavelength ??
                  formatCleanNumber(parameters.wavelength?.value ?? 0.3344)
                }
                aria-invalid={
                  numericDraftError(
                    parameterText.wavelength ??
                      formatCleanNumber(parameters.wavelength?.value ?? 0.3344),
                    fitParameterLimits("wavelength"),
                  )
                    ? true
                    : undefined
                }
                onValueChange={(value) => {
                  setParameterText?.((p) => ({ ...p, wavelength: value }));
                  setEnergyText?.(null);
                }}
              />
            </div>
            <label className="field-label">
              Energy · keV
              <ScientificNumberInput
                id="setup-energy"
                aria-label="Energy in kiloelectronvolts"
                step="any"
                disabled={!ready}
                value={
                  energyText ??
                  (parameters.wavelength?.value > 0
                    ? formatCleanNumber(
                        12.39841984332 / parameters.wavelength.value,
                        7,
                      )
                    : "")
                }
                aria-invalid={
                  energyText !== null &&
                  numericDraftError(energyText, fitEnergyLimits)
                    ? true
                    : undefined
                }
                onValueChange={(value) => {
                  setEnergyText?.(value);
                  setParameterText?.((p) => ({
                    ...p,
                    wavelength: numericDraftError(value, fitEnergyLimits)
                      ? ""
                      : formatCleanNumber(12.39841984332 / Number(value), 7),
                  }));
                }}
              />
            </label>
          </div>
          <div className="setup-pair">
            <label className="field-label">
              Distance · mm
              <ScientificNumberInput
                id="setup-distance"
                aria-label="Starting distance in millimetres"
                step="any"
                disabled={!ready}
                value={
                  parameterText.dist ??
                  formatCleanNumber(parameters.dist?.value ?? 200)
                }
                aria-invalid={
                  numericDraftError(
                    parameterText.dist ??
                      formatCleanNumber(parameters.dist?.value ?? 200),
                    fitParameterLimits("dist"),
                  )
                    ? true
                    : undefined
                }
                onValueChange={(value) =>
                  setParameterText?.((p) => ({ ...p, dist: value }))
                }
              />
            </label>
            <label className="field-label">
              Polarization
              <ScientificNumberInput
                id="setup-polarization"
                aria-label="Polarization factor"
                step=".01"
                min="-1"
                max="1"
                disabled={!ready}
                value={polarization}
                aria-invalid={
                  numericDraftError(polarization, { min: -1, max: 1 })
                    ? true
                    : undefined
                }
                onValueChange={(value) => setPolarization?.(value)}
              />
            </label>
          </div>
        </section>
      )}
      {step === 0 && !hideImageTools && (
        <section className="image-detector-tools">
          <div className="calibration-group-label">Orientation</div>
          <div className="orientation-tools">
            {(
              [
                ["rotate_left", "Rotate image −90°", RotateCcwSquare],
                ["rotate_right", "Rotate image +90°", RotateCwSquare],
                ["flip_horizontal", "Flip image horizontally", FlipHorizontal2],
                ["flip_vertical", "Flip image vertically", FlipVertical2],
                ["reset", "Reset image transformations", RotateCcw],
              ] as const
            ).map(([operation, label, Icon]) => (
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
                <Icon size={16} aria-hidden="true" />
              </Button>
            ))}
          </div>
          <details
            className="calibration-disclosure"
            open={Boolean(c?.detectorFile || c?.distortionFile)}
          >
            <summary>Detector &amp; distortion files</summary>
            <div className="calibration-disclosure-body">
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
            </div>
          </details>
        </section>
      )}
      {step === 2 && fitEditor && (
        <div className="calibration-fit-controls">
          <section className="calibration-fit-page" aria-label="Fit parameters">
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
                (parameterSettings[key] !== undefined
                  ? formatCleanNumber(parameterSettings[key].value)
                  : "");
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
                    {key === "rot3" ? (
                      <span aria-hidden="true" />
                    ) : (
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
                    )}
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
                              ? formatCleanNumber(
                                  12.39841984332 / parameters.wavelength.value,
                                  7,
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
                                : formatCleanNumber(
                                    12.39841984332 / Number(value),
                                    7,
                                  ),
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
            <div className="calibration-rot3-action">
              <Button
                type="button"
                variant="secondary"
                disabled={
                  !ready ||
                  !state?.hasImage ||
                  !state?.calibrated ||
                  !!numericDraftError(polarization, {
                    min: -1,
                    max: 1,
                  })
                }
                title="Estimate detector rotation 3 from azimuthal intensity variation using the current polarization factor."
                onClick={() =>
                  run(
                    "estimate_rot3",
                    { polarization: Number(polarization) },
                    "Estimating rot3 from polarization…",
                  )
                }
              >
                Fit Rotation 3 (polarization)
              </Button>
            </div>
          </section>
        </div>
      )}
      {!imageToolsOnly && (step === 0 || step === 1 || step === 2) && (
        <section
          className="calibration-mask-controls"
          aria-label="Detector mask"
        >
          <div className="calibration-mask-row">
            <div className="calibration-mask-checks">
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
            </div>
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
        </section>
      )}
    </>
  );
}

export { GeometryEditor, ManualGeometryDialog } from "./GeometryEditor";
