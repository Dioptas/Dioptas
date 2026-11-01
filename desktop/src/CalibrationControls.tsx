import { useEffect, useState, useRef, type ReactNode } from "react";
import { Check, FolderOpen } from "lucide-react";
import type { Calibration, Response } from "./types";
import "./calibrationSetup.css";

export function CalibrationControls({
  calibration: c,
  ready,
  hasImage,
  run,
  onDirtyChange,
  step,
  onContinue,
  additionalOptions,
}: {
  calibration?: Calibration;
  ready: boolean;
  hasImage: boolean;
  step: number;
  onContinue: () => void;
  additionalOptions: ReactNode;
  onDirtyChange: (dirty: boolean) => void;
  run: (
    command: string,
    args?: Record<string, unknown>,
    message?: string,
    onSuccess?: (result: Response) => void,
  ) => Promise<void>;
}) {
  const setupSection = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (setupSection.current) setupSection.current.open = step === 0;
  }, [step]);
  const [wavelength, setWavelength] = useState(".3344"),
    [distance, setDistance] = useState("200");
  const [px, setPx] = useState("79"),
    [py, setPy] = useState("79");
  useEffect(() => {
    if (c) setWavelength(String(Number(c.wavelength.toPrecision(7))));
  }, [c?.wavelength]);
  useEffect(() => {
    if (c) setDistance(String(Number(c.distance.toPrecision(7))));
  }, [c?.distance]);
  useEffect(() => {
    if (c) setPx(String(Number(c.pixelX.toPrecision(7))));
  }, [c?.pixelX]);
  useEffect(() => {
    if (c) setPy(String(Number(c.pixelY.toPrecision(7))));
  }, [c?.pixelY]);
  const dirty =
    !!c &&
    [
      [wavelength, c.wavelength],
      [distance, c.distance],
      [px, c.pixelX],
      [py, c.pixelY],
    ].some(
      ([draft, saved]) =>
        !Number.isFinite(Number(draft)) ||
        Math.abs(Number(draft) - Number(saved)) >
          Math.max(1e-10, Math.abs(Number(saved)) * 1e-6),
    );
  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);
  const applySetup = async () => {
    await run(
      "calibration_setup",
      {
        wavelength: Number(wavelength),
        distance: Number(distance),
        pixel_x: Number(px),
        pixel_y: Number(py),
      },
      "Applying experiment setup…",
      (result) => {
        if (result.state?.calibration.setupConfirmed) {
          onDirtyChange(false);
          if (step === 0) onContinue();
        }
      },
    );
  };
  return (
    <>
      <form
        id="calibration-setup-form"
        onInvalidCapture={() => {
          if (setupSection.current) setupSection.current.open = true;
        }}
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && hasImage) void applySetup();
        }}
      >
        <details
          ref={setupSection}
          className="sidebar-section calibration-setup compact-section"
          open={step === 0}
        >
          <summary>Experiment setup</summary>
          <div className="setup-pair setup-selector-pair">
            <div>
              <label className="field-label" htmlFor="calibrant">
                Calibrant
              </label>
              <select
                id="calibrant"
                value={c?.calibrant ?? "CeO2"}
                disabled={!ready}
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
            </div>
            <div>
              <label className="field-label" htmlFor="detector">
                Detector
              </label>
              <select
                id="detector"
                value={c?.detectorFile ? "__file__" : (c?.detector ?? "Custom")}
                disabled={!ready}
                onChange={(e) =>
                  run(
                    "calibration_setup",
                    { detector: e.target.value },
                    "Configuring detector…",
                  )
                }
              >
                {c?.detectorFile && (
                  <option value="__file__">File definition</option>
                )}
                {(c?.detectors ?? ["Custom"]).map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            </div>
          </div>
          {c?.detectorFile && (
            <p className="control-note">
              File detector: {c.detectorFile.split(/[\\/]/).at(-1)}
            </p>
          )}
          <div className="setup-pair">
            <label className="field-label">
              Pixel width · µm
              <input
                aria-label="Pixel width in micrometres"
                type="number"
                required
                value={px}
                min=".1"
                max="5000"
                step="any"
                disabled={!ready || !c?.detectorIsCustom}
                onChange={(e) => setPx(e.target.value)}
              />
            </label>
            <label className="field-label">
              Pixel height · µm
              <input
                aria-label="Pixel height in micrometres"
                type="number"
                required
                value={py}
                min=".1"
                max="5000"
                step="any"
                disabled={!ready || !c?.detectorIsCustom}
                onChange={(e) => setPy(e.target.value)}
              />
            </label>
          </div>
          <div className="setup-pair">
            <label className="field-label">
              Wavelength · Å
              <input
                aria-label="Wavelength in angstroms"
                type="number"
                required
                step="any"
                min=".01"
                max="10"
                value={wavelength}
                disabled={!ready}
                onChange={(e) => setWavelength(e.target.value)}
              />
            </label>
            <label className="field-label">
              Energy · keV
              <input
                aria-label="Energy in kiloelectronvolts"
                type="number"
                required
                step="any"
                min="1.2398"
                value={
                  Number(wavelength) > 0
                    ? Number((12.39841984332 / Number(wavelength)).toFixed(4))
                    : ""
                }
                disabled={!ready}
                onChange={(e) => {
                  const value = Number(e.target.value);
                  if (value > 0) setWavelength(String(12.39841984332 / value));
                }}
              />
            </label>
          </div>
          <label className="field-label" htmlFor="distance">
            Starting distance · mm
          </label>
          <input
            id="distance"
            className="full-input"
            aria-label="Starting distance in millimetres"
            type="number"
            required
            min="1"
            max="10000"
            step="any"
            value={distance}
            disabled={!ready}
            onChange={(e) => setDistance(e.target.value)}
          />

          {step !== 0 && (
            <>
              <p className="setup-note">
                {dirty
                  ? "Apply your setup changes before fitting."
                  : !c?.setupConfirmed
                    ? "Check the experiment values and confirm with Apply setup."
                    : ""}
              </p>
              <button
                type="submit"
                className="secondary full-input apply-setup"
                disabled={!ready}
              >
                <Check size={13} /> Apply setup
              </button>
            </>
          )}
        </details>
      </form>
      {step === 0 && (
        <details className="compact-section setup-more-options">
          <summary>More setup options</summary>
          <p className="control-note">
            Custom references, image orientation, detector files, masks and
            manual geometry.
          </p>
          <details className="compact-section">
            <summary>Custom calibrant & processing</summary>
            <button
              type="button"
              className="quiet full-input"
              disabled={!ready}
              onClick={() =>
                run("open_calibrant", {}, "Loading calibrant spacings…")
              }
            >
              Load custom calibrant…
            </button>
            <label className="field-label" htmlFor="calibration-engine">
              Processing engine
            </label>
            <select
              id="calibration-engine"
              value={c?.engine ?? "pyfai"}
              disabled={!ready}
              onChange={(e) =>
                run(
                  "calibration_engine",
                  { engine: e.target.value },
                  "Changing processing engine…",
                )
              }
            >
              {(
                c?.engines ?? [{ id: "pyfai", label: "pyFAI", available: true }]
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
            </select>
          </details>
          {additionalOptions}
        </details>
      )}
      {step === 0 && (
        <button
          type="button"
          className="secondary full-input load-calibration"
          disabled={!ready}
          onClick={() =>
            run("open_calibration", {}, "Loading PONI calibration…")
          }
        >
          <FolderOpen size={14} /> Load .poni
        </button>
      )}
    </>
  );
}
