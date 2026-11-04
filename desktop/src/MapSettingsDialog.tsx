import { useLayoutEffect, useRef, useState } from "react";
import type { MapData, MapRun } from "./mapDomain";
import { unitLabel, type Unit } from "./types";
import { radialValues } from "./radialReadout";

const formatBound = (value: number) => String(Number(value.toPrecision(12)));

export function MapSettingsDialog({
  map,
  ready,
  run,
  onClose,
  anchor,
  reintegrateSelected,
  onReintegrateSelected,
  displayUnit,
  wavelength,
}: {
  anchor: HTMLButtonElement | null;
  map: MapData;
  ready: boolean;
  run: MapRun;
  onClose: () => void;
  reintegrateSelected: boolean;
  onReintegrateSelected: (enabled: boolean) => void;
  displayUnit: Unit;
  wavelength?: number;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const coordinates = map.normalizationCoordinates;
  const activeWindow =
    map.rois.find((r) => r.name === map.active) ?? map.rois[0];
  const initial = coordinates ?? {
    minimum: activeWindow.min,
    maximum: activeWindow.max,
    unit: map.unit,
  };
  const converted = [initial.minimum, initial.maximum].map(
    (x) => radialValues(x, initial.unit, wavelength)[displayUnit],
  );
  const convertedValid = converted.every(
    (v): v is number => v != null && Number.isFinite(v),
  );
  const [unit, setUnit] = useState<Unit>(
    convertedValid ? displayUnit : initial.unit,
  );
  const [minimum, setMinimum] = useState(
    formatBound(convertedValid ? Math.min(...converted) : initial.minimum),
  );
  const [maximum, setMaximum] = useState(
    formatBound(convertedValid ? Math.max(...converted) : initial.maximum),
  );
  const [source, setSource] = useState<"range" | "window">(
    coordinates?.window ? "window" : "range",
  );
  const [windowName, setWindowName] = useState(
    coordinates?.window && map.rois.some((r) => r.name === coordinates.window)
      ? coordinates.window
      : activeWindow.name,
  );
  const [reference, setReference] = useState(
    String(map.normalizationReference),
  );
  const selectedWindow = map.rois.find((r) => r.name === windowName);
  const windowBounds = selectedWindow
    ? [selectedWindow.min, selectedWindow.max].map(
        (x) => radialValues(x, map.unit, wavelength)[displayUnit],
      )
    : [];
  const windowConverted =
    windowBounds.length === 2 &&
    windowBounds.every((v): v is number => v != null && Number.isFinite(v));
  const windowMinimum = windowConverted
    ? Math.min(...windowBounds)
    : selectedWindow?.min;
  const windowMaximum = windowConverted
    ? Math.max(...windowBounds)
    : selectedWindow?.max;
  useLayoutEffect(() => {
    const popup = dialog.current!;
    popup.showModal();
    return () => {
      popup.close();
      anchor?.focus({ preventScroll: true });
    };
  }, [anchor]);
  const validRange =
    minimum.trim() !== "" &&
    maximum.trim() !== "" &&
    Number.isFinite(Number(minimum)) &&
    Number.isFinite(Number(maximum)) &&
    Number(minimum) < Number(maximum);
  const referenceValue = Number(reference);
  const valid =
    (source === "window" ? !!selectedWindow : validRange) &&
    reference.trim() !== "" &&
    Number.isInteger(referenceValue) &&
    referenceValue >= 0 &&
    referenceValue < map.points;
  const changeUnit = (next: Unit) => {
    if (validRange) {
      const values = [Number(minimum), Number(maximum)].map(
        (x) => radialValues(x, unit, wavelength)[next],
      );
      if (values.every((v): v is number => v != null && Number.isFinite(v))) {
        setMinimum(formatBound(Math.min(...values)));
        setMaximum(formatBound(Math.max(...values)));
      } else {
        setMinimum("");
        setMaximum("");
      }
    }
    setUnit(next);
  };
  return (
    <dialog
      ref={dialog}
      className="map-settings-dialog"
      aria-labelledby="map-settings-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && valid && coordinates)
            void run("map_normalize", {
              reference: referenceValue,
              ...(source === "window"
                ? { window: windowName }
                : { minimum: Number(minimum), maximum: Number(maximum), unit }),
            });
        }}
      >
        <h3 id="map-settings-title">Map settings</h3>
        <label className="check-row map-reintegrate-setting">
          <input
            autoFocus
            aria-label="Reintegrate selected image"
            type="checkbox"
            checked={reintegrateSelected}
            onChange={(event) => onReintegrateSelected(event.target.checked)}
          />
          Reintegrate selected image
        </label>
        <h4>Normalize patterns</h4>
        <label className="field-label">
          Normalize using
          <select
            aria-label="Normalization source"
            value={source}
            onChange={(event) =>
              setSource(event.target.value as "range" | "window")
            }
          >
            <option value="range">Radial range</option>
            <option value="window">Pattern window</option>
          </select>
        </label>
        {source === "window" ? (
          <>
            <label className="field-label">
              Window
              <select
                aria-label="Normalization window"
                value={windowName}
                onChange={(event) => setWindowName(event.target.value)}
              >
                {map.rois.map((roi) => (
                  <option key={roi.name} value={roi.name}>
                    {roi.name}
                  </option>
                ))}
              </select>
            </label>
            {selectedWindow && (
              <p className="map-note">
                {Number(windowMinimum!.toPrecision(6))}–
                {Number(windowMaximum!.toPrecision(6))}{" "}
                {unitLabel(windowConverted ? displayUnit : map.unit)}
              </p>
            )}
          </>
        ) : (
          <>
            <label className="field-label">
              Unit
              <select
                aria-label="Normalization unit"
                value={unit}
                onChange={(event) => changeUnit(event.target.value as Unit)}
              >
                {(
                  [
                    ["2th_deg", "2θ (°)"],
                    ["q_A^-1", "Q (Å⁻¹)"],
                    ["d_A", "d (Å)"],
                  ] as [Unit, string][]
                ).map(([value, label]) => (
                  <option
                    key={value}
                    value={value}
                    disabled={
                      value !== map.unit &&
                      (value === "2th_deg" || map.unit === "2th_deg") &&
                      !wavelength
                    }
                  >
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <div className="map-field-pair">
              <label className="field-label">
                From
                <input
                  type="number"
                  step="any"
                  required
                  aria-label="Normalization minimum"
                  value={minimum}
                  onChange={(event) => setMinimum(event.target.value)}
                />
              </label>
              <label className="field-label">
                To
                <input
                  type="number"
                  step="any"
                  required
                  aria-label="Normalization maximum"
                  value={maximum}
                  onChange={(event) => setMaximum(event.target.value)}
                />
              </label>
            </div>
          </>
        )}
        <label className="field-label">
          Reference point (0 based)
          <input
            type="number"
            min="0"
            max={map.points - 1}
            step="1"
            required
            aria-label="Normalization reference"
            value={reference}
            onChange={(event) => setReference(event.target.value)}
          />
        </label>
        {!coordinates && (
          <p className="map-note">
            Restart the preview to enable range normalization.
          </p>
        )}
        <footer>
          <button
            type="button"
            disabled={!ready || !map.normalized}
            onClick={() => run("map_normalize", { enabled: false })}
          >
            Restore original
          </button>
          <span />
          <button type="button" onClick={onClose}>
            Close
          </button>
          <button
            type="submit"
            className="primary"
            disabled={!ready || !valid || !coordinates}
          >
            Normalize
          </button>
        </footer>
      </form>
    </dialog>
  );
}
