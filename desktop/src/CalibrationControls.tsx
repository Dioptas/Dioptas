import { useEffect, useState, type ReactNode } from "react";
import type { Calibration, Response } from "./types";

export function CalibrationControls({
  calibration: c,
  ready,
  hasImage,
  run,
  onDirtyChange,
  onValidityChange,
  additionalOptions,
  maskControls,
}: {
  calibration?: Calibration;
  ready: boolean;
  hasImage: boolean;
  additionalOptions: ReactNode;
  maskControls: ReactNode;
  onDirtyChange: (dirty: boolean) => void;
  onValidityChange: (valid: boolean) => void;
  run: (
    command: string,
    args?: Record<string, unknown>,
    message?: string,
    onSuccess?: (result: Response) => void,
  ) => Promise<void>;
}) {
  const [px, setPx] = useState("79"),
    [py, setPy] = useState("79");
  useEffect(() => {
    if (c) setPx(String(Number(c.pixelX.toPrecision(7))));
  }, [c?.pixelX]);
  useEffect(() => {
    if (c) setPy(String(Number(c.pixelY.toPrecision(7))));
  }, [c?.pixelY]);
  const dirty =
    !!c &&
    [
      [px, c.pixelX],
      [py, c.pixelY],
    ].some(
      ([draft, saved]) =>
        !Number.isFinite(Number(draft)) ||
        Math.abs(Number(draft) - Number(saved)) >
          Math.max(1e-10, Math.abs(Number(saved)) * 1e-6),
    );
  const valid = [px, py].every(
    (value) =>
      value.trim() !== "" &&
      Number.isFinite(Number(value)) &&
      Number(value) >= 0.1 &&
      Number(value) <= 5000,
  );
  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    onValidityChange(valid);
  }, [valid, onValidityChange]);
  useEffect(
    () => () => {
      onDirtyChange(false);
      onValidityChange(true);
    },
    [onDirtyChange, onValidityChange],
  );
  const applySetup = async () => {
    await run(
      "calibration_setup",
      {
        pixel_x: Number(px),
        pixel_y: Number(py),
      },
      "Applying detector settings…",
      (result) => {
        if (!result.cancelled && result.state?.hasImage) {
          onDirtyChange(false);
        }
      },
    );
  };
  return (
    <>
      <form
        id="calibration-setup-form"
        onKeyDown={(event) => {
          if (
            event.key === "Enter" &&
            event.target instanceof HTMLInputElement
          ) {
            event.preventDefault();
            event.currentTarget.requestSubmit();
          }
        }}
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && hasImage && dirty && valid) void applySetup();
        }}
      >
        <section className="calibration-setup-page">
          <div className="setup-selector-pair">
            <div>
              <label className="field-label" htmlFor="detector">
                Detector
              </label>
              <select
                id="detector"
                title={c?.detectorFile ?? undefined}
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
                  <option value="__file__">
                    File: {c.detectorFile.split(/[\\/]/).at(-1)}
                  </option>
                )}
                {(c?.detectors ?? ["Custom"]).map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            </div>
          </div>
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
                onBlur={(event) => {
                  if (!event.currentTarget.reportValidity()) return;
                  if (ready && hasImage && dirty && valid) void applySetup();
                }}
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
                onBlur={(event) => {
                  if (!event.currentTarget.reportValidity()) return;
                  if (ready && hasImage && dirty && valid) void applySetup();
                }}
              />
            </label>
          </div>
          {additionalOptions}
        </section>
      </form>
      {maskControls}
    </>
  );
}
