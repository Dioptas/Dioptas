import { useEffect, useState, useRef } from "react";
import { Check, ChevronRight, Save } from "lucide-react";
import type { Calibration } from "./types";

export function CalibrationControls({
  calibration: c,
  ready,
  run,
  onDirtyChange,
  step,
}: {
  calibration?: Calibration;
  ready: boolean;
  step: number;
  onDirtyChange: (dirty: boolean) => void;
  run: (
    command: string,
    args?: Record<string, unknown>,
    message?: string,
  ) => unknown;
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
    if (c) {
      setWavelength(String(Number(c.wavelength.toPrecision(7))));
      setDistance(String(Number(c.distance.toPrecision(7))));
      setPx(String(Number(c.pixelX.toPrecision(7))));
      setPy(String(Number(c.pixelY.toPrecision(7))));
    }
  }, [c?.wavelength, c?.distance, c?.pixelX, c?.pixelY]);
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
  return (
    <>
      <details
        ref={setupSection}
        className="sidebar-section calibration-setup compact-section"
        open={step === 0}
      >
        <summary>Experiment setup</summary>
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
        <button
          className="quiet full-input"
          disabled={!ready}
          onClick={() =>
            run("open_calibrant", {}, "Loading calibrant spacings…")
          }
        >
          Load custom calibrant…
        </button>
        {c?.detectorFile && (
          <p className="control-note">
            File detector: {c.detectorFile.split(/[\\/]/).at(-1)}
          </p>
        )}
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
          {c?.detectorFile && <option value="__file__">File definition</option>}
          {(c?.detectors ?? ["Custom"]).map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
        <div className="setup-pair">
          <label className="field-label">
            Pixel x · µm
            <input
              aria-label="Pixel width in micrometres"
              type="number"
              value={px}
              min=".1"
              step=".1"
              disabled={!ready || !c?.detectorIsCustom}
              onChange={(e) => setPx(e.target.value)}
            />
          </label>
          <label className="field-label">
            Pixel y · µm
            <input
              aria-label="Pixel height in micrometres"
              type="number"
              value={py}
              min=".1"
              step=".1"
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
              step=".0001"
              min=".01"
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
              step=".01"
              min="1.24"
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
          min="1"
          max="10000"
          value={distance}
          disabled={!ready}
          onChange={(e) => setDistance(e.target.value)}
        />
        <div className="setup-note">
          {dirty
            ? "Apply your setup changes before fitting."
            : !c?.setupConfirmed
              ? "Check the experiment values and confirm with Apply setup."
              : ""}
        </div>
        <button
          className="secondary full-input apply-setup"
          disabled={!ready}
          onClick={() =>
            run(
              "calibration_setup",
              {
                wavelength: Number(wavelength),
                distance: Number(distance),
                pixel_x: Number(px),
                pixel_y: Number(py),
              },
              "Applying experiment setup…",
            )
          }
        >
          <Check size={13} />
          Apply setup
          <ChevronRight size={13} />
        </button>
      </details>
      {step === 0 && (
        <section className="sidebar-section">
          <div className="section-label">CALIBRATION FILE</div>
          <button
            className="secondary full-input"
            disabled={!ready}
            onClick={() =>
              run("open_calibration", {}, "Loading PONI calibration…")
            }
          >
            Load existing .poni
          </button>
          <button
            className="quiet full-input"
            disabled={!ready || c?.fitDirty || c?.geometrySource === "none"}
            onClick={() =>
              run("save_calibration", {}, "Saving PONI calibration…")
            }
          >
            <Save size={13} />
            Save .poni calibration
          </button>
        </section>
      )}
    </>
  );
}
