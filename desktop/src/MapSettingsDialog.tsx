import { useAnchoredDialog } from "./useAnchoredDialog";
import { ScientificNumberInput } from "./ScientificNumberInput";
import { Dialog, DialogHeader } from "./Dialog";
import { useRef, useState } from "react";
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
  useAnchoredDialog(dialog, anchor, true, "end");
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
    <Dialog
      dialogRef={dialog}
      returnFocusTarget={anchor}
      className="map-settings-dialog"
      onDismiss={onClose}
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
        <DialogHeader
          compact
          title="Map settings"
          titleId="map-settings-title"
          closeLabel="Close"
          onClose={onClose}
        />
        <label className="check-row map-reintegrate-setting">
          <Input
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
          Use
          <Select
            aria-label="Normalization source"
            value={source}
            onChange={(event) =>
              setSource(event.target.value as "range" | "window")
            }
          >
            <option value="range">Radial range</option>
            <option value="window">Pattern window</option>
          </Select>
        </label>
        {source === "window" ? (
          <>
            <label className="field-label">
              Window
              <Select
                aria-label="Normalization window"
                value={windowName}
                onChange={(event) => setWindowName(event.target.value)}
              >
                {map.rois.map((roi) => (
                  <option key={roi.name} value={roi.name}>
                    {roi.name}
                  </option>
                ))}
              </Select>
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
              <Select
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
              </Select>
            </label>
            <div className="map-field-pair">
              <label className="field-label">
                From
                <ScientificNumberInput
                  type="number"
                  step="any"
                  required
                  aria-label="Normalization minimum"
                  value={minimum}
                  onValueChange={setMinimum}
                />
              </label>
              <label className="field-label">
                To
                <ScientificNumberInput
                  type="number"
                  step="any"
                  required
                  aria-label="Normalization maximum"
                  value={maximum}
                  onValueChange={setMaximum}
                />
              </label>
            </div>
          </>
        )}
        <label className="field-label map-reference-file">
          Reference file
          <Select
            required
            aria-label="Normalization reference"
            title={map.labels[map.slots.indexOf(referenceValue)] ?? ""}
            value={reference}
            onChange={(event) => setReference(event.target.value)}
          >
            {map.slots.map((point, slot) => (
              <option
                key={slot}
                value={point ?? `blank-${slot}`}
                disabled={point === null}
              >
                {slot + 1} ·{" "}
                {point === null
                  ? "Blank cell"
                  : map.labels[slot] || "Raw source unavailable"}
              </option>
            ))}
          </Select>
        </label>
        {!coordinates && (
          <p className="map-note">
            Restart the preview to enable range normalization.
          </p>
        )}
        <footer>
          <Button
            type="button"
            disabled={!ready || !map.normalized}
            onClick={() => run("map_normalize", { enabled: false })}
          >
            Restore original
          </Button>
          <span />
          <Button
            type="submit"
            variant="primary"
            disabled={!ready || !valid || !coordinates}
          >
            Normalize
          </Button>
        </footer>
      </form>
    </Dialog>
  );
}
