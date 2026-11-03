import { useMemo, type ReactNode } from "react";
import { decodeRaster } from "./rasterTransfer";
import { Save } from "lucide-react";
import type { Cake, State, Unit } from "./types";
import type { IntegrationRun } from "./integration";
import type { BackgroundSettings } from "./useLiveBackground";

export function PlotToggle({
  label,
  title,
  pressed,
  disabled,
  onClick,
  children,
}: {
  label: string;
  title: string;
  pressed: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      className="plot-tool-button"
      type="button"
      aria-label={label}
      title={title}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function IntegrationImageControls({
  value,
  onChange,
  state,
  ready,
  run,
  showPhases,
  onShowPhases,
  corrected,
  onCorrected,
  roi,
  onRoi,
  cakeShift,
  onCakeShift,
  fullCake,
  onSaveImage,
}: {
  value: string;
  onChange: (value: string) => void;
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
  showPhases: boolean;
  onShowPhases: () => void;
  corrected: boolean;
  onCorrected: () => void;
  roi: boolean;
  onRoi: () => void;
  cakeShift: number;
  onCakeShift: (shift: number) => void;
  fullCake: boolean;
  onSaveImage: () => void;
}) {
  return (
    <div
      className="integration-image-tools"
      role="group"
      aria-label="Integration image controls"
    >
      <button
        className="plot-tool-button"
        type="button"
        aria-label="Save image"
        title={
          value === "cake"
            ? "Save cake image or data"
            : "Save detector image or data"
        }
        disabled={
          !ready || !state?.hasImage || (value === "cake" && !state?.calibrated)
        }
        onClick={onSaveImage}
      >
        <Save size={15} />
      </button>
      <PlotToggle
        label="Image region of interest"
        title="Restrict integration to a detector region; drag inside to move it or drag an edge or corner to resize"
        pressed={roi}
        disabled={!ready || !state?.hasImage || value === "cake"}
        onClick={onRoi}
      >
        ROI
      </PlotToggle>
      <div
        className="integration-image-mode"
        role="group"
        aria-label="Integration display"
      >
        <button
          className="plot-tool-button integration-display-switch"
          type="button"
          title={value === "image" ? "Show cake" : "Show image"}
          onClick={() => onChange(value === "image" ? "cake" : "image")}
        >
          {value === "image" ? "Cake" : "Image"}
        </button>
      </div>
      <span className="plot-tool-divider" />
      <label
        className="check-row"
        title="Use the detector mask for integration and show it on the image"
      >
        <input
          aria-label="Apply detector mask"
          type="checkbox"
          checked={!!state?.useMask}
          disabled={!ready || !state?.hasImage}
          onChange={(event) =>
            void run("settings", { use_mask: event.target.checked })
          }
        />
        Mask
      </label>
      <label
        className="check-row"
        title="Show masked pixels through a transparent mask"
      >
        <input
          aria-label="Integration transparent mask"
          type="checkbox"
          checked={!!state?.transparentMask}
          disabled={!ready || !state?.hasImage}
          onChange={(event) =>
            void run("settings", { transparent_mask: event.target.checked })
          }
        />
        Transparent
      </label>
      <span className="plot-tool-divider" aria-hidden="true" />
      {state?.integration.imageBackground.filename && (
        <PlotToggle
          label="Show corrected image"
          title="Display the background-subtracted and corrected detector image"
          pressed={corrected}
          disabled={!state?.hasImage || value === "cake"}
          onClick={onCorrected}
        >
          bkg
        </PlotToggle>
      )}
      <PlotToggle
        label="Show image phases"
        title="Show phase reference lines on the image or cake"
        pressed={showPhases}
        disabled={!state?.integration.phases.length}
        onClick={onShowPhases}
      >
        Phases
      </PlotToggle>
      <label
        className="integration-cake-shift"
        data-visible={value === "cake"}
        aria-hidden={value !== "cake"}
        title="Roll the full cake in azimuth without reintegrating"
      >
        <span className="plot-tool-divider" aria-hidden="true" />
        χ
        <input
          aria-label="Cake azimuth shift"
          type="range"
          min={-180}
          max={180}
          value={cakeShift}
          disabled={value !== "cake" || !fullCake}
          onChange={(e) => onCakeShift(Number(e.target.value))}
        />
        <span>{cakeShift}°</span>
      </label>
    </div>
  );
}

export function IntegrationPatternActions({
  state,
  ready,
  run,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
}) {
  const hasPattern = !!state?.integration.patternName;
  return (
    <div
      className="integration-pattern-actions"
      role="group"
      aria-label="Pattern actions"
    >
      <button
        aria-label="Save pattern"
        title="Save displayed pattern"
        disabled={!ready || !hasPattern}
        onClick={() =>
          void run("integration_save_pattern", {
            subtract_background: true,
          })
        }
      >
        <Save size={15} />
      </button>
      <button
        disabled={!ready || !hasPattern}
        onClick={() =>
          void run("integration_overlay", { operation: "capture" })
        }
      >
        As Overlay
      </button>
      <button
        disabled={!ready || !hasPattern}
        onClick={() =>
          void run("integration_overlay", { operation: "capture_background" })
        }
      >
        As Bkg
      </button>
      <span
        className="integration-pattern-calibration"
        title={`${state?.calibrationName ?? "No calibration"} · wavelength`}
      >
        λ{" "}
        {state?.calibrated
          ? (state.geometry.wavelength * 1e10).toFixed(5)
          : "—"}{" "}
        Å
      </span>
      <button
        disabled={!ready}
        title={state?.calibrationName ?? "Load a PONI calibration"}
        onClick={() => void run("open_calibration")}
      >
        Load calibration…
      </button>
    </div>
  );
}

export function IntegrationPatternTools({
  state,
  ready,
  run,
  log,
  sqrt,
  onScale,
  inspect,
  onInspect,
  antialias,
  onAntialias,
  autoRange,
  onAutoRange,
  background,
  onBackgroundChange,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
  log: boolean;
  sqrt: boolean;
  onScale: (scale: "linear" | "log" | "sqrt") => void;
  inspect: boolean;
  onInspect: () => void;
  antialias: boolean;
  onAntialias: () => void;
  autoRange: boolean;
  onAutoRange: () => void;
  background: BackgroundSettings;
  onBackgroundChange: (patch: Partial<BackgroundSettings>) => void;
}) {
  const bkg = background;
  return (
    <div
      className="integration-pattern-tools"
      role="group"
      aria-label="Pattern display controls"
    >
      <div
        className="plot-tool-group"
        role="group"
        aria-label="Pattern radial unit"
      >
        {(
          [
            ["2th_deg", "2θ", "Two theta (degrees)"],
            ["q_A^-1", "Q", "Scattering vector (Å⁻¹)"],
            ["d_A", "d", "d spacing (Å)"],
          ] as [Unit, string, string][]
        ).map(([unit, label, title]) => (
          <PlotToggle
            key={unit}
            label={`Pattern unit ${label}`}
            title={title}
            pressed={state?.unit === unit}
            disabled={!ready}
            onClick={() => void run("integration_settings", { unit })}
          >
            {label}
          </PlotToggle>
        ))}
      </div>
      <div
        className="plot-tool-group"
        role="group"
        aria-label="Pattern intensity scale"
      >
        <PlotToggle
          label="Logarithmic pattern intensity"
          title="Logarithmic intensity scale"
          pressed={log}
          onClick={() => onScale(log ? "linear" : "log")}
        >
          Log
        </PlotToggle>
        <PlotToggle
          label="Square root pattern intensity"
          title="Square-root intensity scale"
          pressed={sqrt}
          onClick={() => onScale(sqrt ? "linear" : "sqrt")}
        >
          √
        </PlotToggle>
      </div>
      <div className="plot-tool-group">
        <PlotToggle
          label="Subtract pattern background"
          title="Subtract the fitted automatic pattern background"
          pressed={!!bkg?.enabled}
          disabled={!ready || !state?.integration.patternName}
          onClick={() => onBackgroundChange({ enabled: !bkg.enabled })}
        >
          bg
        </PlotToggle>
        <PlotToggle
          label="Inspect pattern background"
          title="Show the original pattern and fitted background; drag either range edge to refit live"
          pressed={inspect && !!bkg?.enabled}
          disabled={!bkg?.enabled}
          onClick={onInspect}
        >
          I
        </PlotToggle>
      </div>
      <div className="plot-tool-group">
        <PlotToggle
          label="Antialias pattern"
          title="Antialiased line drawing"
          pressed={antialias}
          onClick={onAntialias}
        >
          AA
        </PlotToggle>
      </div>
      <PlotToggle
        label="Pattern auto range"
        title="Automatically rescale axes when the pattern changes"
        pressed={autoRange}
        onClick={onAutoRange}
      >
        A
      </PlotToggle>
    </div>
  );
}

/** Display-only azimuth roll; never resample detector or scientific arrays. */
export function useShiftedCake(
  cake: Cake | null,
  degrees: number,
): Cake | null {
  return useMemo(() => {
    if (!cake || !degrees) return cake;
    const period =
      ((cake.azimuthRange[1] - cake.azimuthRange[0]) * cake.height) /
      Math.max(1, cake.height - 1);
    if (period < 359) return cake;
    const input = decodeRaster(cake);
    const shift = Math.round((degrees / period) * cake.height);
    const output = new Float32Array(input.length);
    for (let row = 0; row < cake.height; row++) {
      const source = (row - shift + cake.height) % cake.height;
      output.set(
        input.subarray(source * cake.width, (source + 1) * cake.width),
        row * cake.width,
      );
    }
    const offset = (shift / cake.height) * period;
    return {
      ...cake,
      data: output.buffer,
      bufferId: undefined,
      azimuthRange: [
        cake.azimuthRange[0] - offset,
        cake.azimuthRange[1] - offset,
      ],
    };
  }, [cake, degrees]);
}
