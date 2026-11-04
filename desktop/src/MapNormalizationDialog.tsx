import { useLayoutEffect, useRef, useState } from "react";
import type { MapData, MapRun } from "./mapDomain";

export function MapNormalizationDialog({
  map,
  ready,
  run,
  onClose,
  anchor,
}: {
  anchor: HTMLButtonElement | null;
  map: MapData;
  ready: boolean;
  run: MapRun;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [start, setStart] = useState(String(map.normalizationRange[0]));
  const [stop, setStop] = useState(String(map.normalizationRange[1]));
  const [reference, setReference] = useState(
    String(map.normalizationReference),
  );
  useLayoutEffect(() => {
    const opener = anchor;
    const popup = dialog.current!;
    popup.showModal();
    return () => {
      popup.close();
      opener?.focus({ preventScroll: true });
    };
  }, [anchor]);
  const values = [start, stop, reference].map(Number);
  const valid =
    [start, stop, reference].every((value) => value.trim() !== "") &&
    values.every(Number.isInteger) &&
    values[0] >= 0 &&
    values[1] > values[0] &&
    values[2] >= 0 &&
    values[2] < map.points;
  return (
    <dialog
      ref={dialog}
      className="map-normalization-dialog"
      aria-labelledby="map-normalization-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && valid)
            void run("map_normalize", {
              start: values[0],
              stop: values[1],
              reference: values[2],
            });
        }}
      >
        <h3 id="map-normalization-title">Normalize patterns</h3>
        <p className="map-note">
          Match mean intensity in the selected bins to a reference point.
          Original patterns remain available for Restore.
        </p>
        <div className="map-field-pair">
          <label className="field-label">
            Start bin
            <input
              autoFocus
              type="number"
              min="0"
              step="1"
              required
              aria-label="Normalization start bin"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label className="field-label">
            Stop bin (exclusive)
            <input
              type="number"
              min="1"
              step="1"
              required
              aria-label="Normalization stop bin"
              value={stop}
              onChange={(event) => setStop(event.target.value)}
            />
          </label>
        </div>
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
          <button type="submit" className="primary" disabled={!ready || !valid}>
            Normalize
          </button>
        </footer>
      </form>
    </dialog>
  );
}
