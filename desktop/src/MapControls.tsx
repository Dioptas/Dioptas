import { useEffect, useState } from "react";
import type { State } from "./types";
import { unitLabel } from "./types";
import type { MapData, MapRoi, MapRun } from "./mapDomain";

function WindowEditor({
  roi,
  active,
  ready,
  run,
}: {
  roi: MapRoi;
  active: boolean;
  ready: boolean;
  run: MapRun;
}) {
  const [draft, setDraft] = useState(roi);
  useEffect(() => setDraft(roi), [roi]);
  const changed = JSON.stringify(draft) !== JSON.stringify(roi);
  return (
    <fieldset
      className={`map-window ${active ? "map-window-active" : ""}`}
      style={{ borderLeftColor: roi.color }}
      disabled={!ready}
    >
      <legend>
        <button
          className="text-button"
          onClick={() => run("map_layer", { name: roi.name })}
        >
          Window {roi.name}
        </button>
      </legend>
      <label className="field-label">
        Name
        <input
          aria-label={`Window ${roi.name} name`}
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
      </label>
      <div className="map-field-pair">
        <label className="field-label">
          From
          <input
            aria-label={`Window ${roi.name} minimum`}
            type="number"
            step="any"
            value={draft.min}
            onChange={(e) => setDraft({ ...draft, min: +e.target.value })}
          />
        </label>
        <label className="field-label">
          To
          <input
            aria-label={`Window ${roi.name} maximum`}
            type="number"
            step="any"
            value={draft.max}
            onChange={(e) => setDraft({ ...draft, max: +e.target.value })}
          />
        </label>
      </div>
      <label className="field-label">
        Value
        <select
          aria-label={`Window ${roi.name} value`}
          value={draft.reduction + (draft.background ? ":bkg" : "")}
          onChange={(e) => {
            const [reduction, bg] = e.target.value.split(":");
            setDraft({ ...draft, reduction, background: bg === "bkg" });
          }}
        >
          <option value="sum">Sum</option>
          <option value="sum:bkg">Sum − bkg</option>
          <option value="mean">Mean</option>
          <option value="max">Maximum</option>
          <option value="area">Peak area</option>
          <option value="center">Peak position</option>
          <option value="width">Peak width (FWHM)</option>
        </select>
      </label>
      <div className="file-actions">
        <button
          disabled={!changed || draft.min >= draft.max}
          onClick={() =>
            run("map_roi", {
              name: roi.name,
              new_name: draft.name,
              minimum: draft.min,
              maximum: draft.max,
              reduction: draft.reduction,
              background: draft.background,
            })
          }
        >
          Apply window
        </button>
        <button
          onClick={() => run("map_roi", { op: "remove", name: roi.name })}
        >
          Remove
        </button>
      </div>
    </fieldset>
  );
}

export function MapControls({
  map,
  state,
  ready,
  run,
  reintegrate,
  onReintegrate,
}: {
  map: MapData | null;
  state: State | null;
  ready: boolean;
  run: MapRun;
  reintegrate: boolean;
  onReintegrate: (v: boolean) => void;
}) {
  const [tab, setTab] = useState("Files");
  const [rows, setRows] = useState(1),
    [columns, setColumns] = useState(1);
  const [name, setName] = useState("Ratio"),
    [expression, setExpression] = useState("A/B");
  const [start, setStart] = useState(0),
    [stop, setStop] = useState(100),
    [reference, setReference] = useState(0);
  const [page, setPage] = useState(0);
  useEffect(() => {
    setPage(map?.selectedSlot == null ? 0 : Math.floor(map.selectedSlot / 100));
  }, [map?.selectedSlot, map?.points]);
  useEffect(() => {
    if (map) {
      setRows(map.dimension[0]);
      setColumns(map.dimension[1]);
    }
  }, [map?.dimension[0], map?.dimension[1]]);
  useEffect(() => {
    if (map) {
      setStart(map.normalizationRange[0]);
      setStop(map.normalizationRange[1]);
      setReference(map.normalizationReference);
    }
  }, [map?.normalized]);
  const selected = map?.selectedSlot;
  const arrange = (op: string, args = {}) =>
    run("map_arrange", { op, slot: selected, index: map?.selected, ...args });
  return (
    <div className="map-controls">
      <section className="sidebar-section">
        <div className="section-label">MAP SOURCE</div>
        <div className="file-actions">
          <button
            disabled={!ready || !state?.calibrated}
            onClick={() => run("map_load", {}, "Integrating map images…")}
          >
            Load images…
          </button>
          <button
            disabled={!ready || !state?.calibrated}
            onClick={() => run("map_folder", {}, "Integrating scan folder…")}
          >
            Folder…
          </button>
        </div>
        <button
          className="full-input"
          disabled={!ready}
          onClick={() => run("map_batch", {}, "Loading processed batch…")}
        >
          Load processed batch…
        </button>
        <button
          className="full-input quiet"
          disabled={!ready}
          onClick={() => run("open_calibration")}
        >
          {state?.calibrationName ?? "Load PONI calibration…"}
        </button>
        {!state?.calibrated && (
          <p className="map-note">
            Image integration needs a calibration. Stored batches can be opened
            directly.
          </p>
        )}
        {map && (
          <div className="file-actions">
            <button
              disabled={!ready || !state?.calibrated || !map.canRebuild}
              onClick={() =>
                run("map_load", { reintegrate: true }, "Reintegrating map…")
              }
            >
              Rebuild map
            </button>
            <button disabled={!ready} onClick={() => run("map_export")}>
              Save map data…
            </button>
          </div>
        )}
      </section>
      {map && (
        <>
          <div className="map-tabs" role="tablist" aria-label="Map controls">
            {["Files", "Layers", "Grid"].map((t) => (
              <button
                role="tab"
                aria-selected={tab === t}
                key={t}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "Files" && (
            <section className="sidebar-section">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={reintegrate}
                  disabled={
                    !ready ||
                    (!reintegrate && (!state?.hasImage || !state?.calibrated))
                  }
                  onChange={(e) => {
                    onReintegrate(e.target.checked);
                    if (map.selected !== null)
                      void run("map_select", {
                        index: map.selected,
                        reintegrate: e.target.checked,
                      });
                  }}
                />
                Reintegrate selected image
              </label>
              <p className="map-note">
                {map.points} points · {map.normalized ? "normalized" : "stored"}{" "}
                patterns · {unitLabel(map.unit)}. Files remain in acquisition
                order. Folder loading uses natural filename order.
              </p>
              <div
                className="map-file-list"
                role="listbox"
                aria-label="Scan arrangement"
              >
                {map.labels
                  .slice(page * 100, page * 100 + 100)
                  .map((label, offset) => {
                    const slot = page * 100 + offset,
                      point = map.slots[slot];
                    return (
                      <button
                        role="option"
                        aria-selected={selected === slot}
                        disabled={!ready}
                        key={slot}
                        className={
                          point !== null && map.excluded.includes(point)
                            ? "map-excluded"
                            : ""
                        }
                        onClick={() => run("map_select", { slot, reintegrate })}
                        title={label}
                      >
                        <span>{slot + 1}</span>
                        {label || "Raw source unavailable"}
                      </button>
                    );
                  })}
              </div>
              {map.labels.length > 100 && (
                <div className="file-actions">
                  <button
                    disabled={page === 0}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous 100
                  </button>
                  <button
                    disabled={(page + 1) * 100 >= map.labels.length}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next 100
                  </button>
                </div>
              )}
              <div className="file-actions">
                <button
                  disabled={!ready || selected == null || selected === 0}
                  onClick={() => arrange("move", { offset: -1 })}
                >
                  Move up
                </button>
                <button
                  disabled={
                    !ready ||
                    selected == null ||
                    selected >= map.slots.length - 1
                  }
                  onClick={() => arrange("move", { offset: 1 })}
                >
                  Move down
                </button>
              </div>
              <div className="file-actions">
                <button
                  disabled={!ready || selected == null}
                  onClick={() => arrange("insert")}
                >
                  Insert blank
                </button>
                <button
                  disabled={
                    !ready || selected == null || map.slots[selected] !== null
                  }
                  onClick={() => arrange("remove")}
                >
                  Remove blank
                </button>
              </div>
              <button
                disabled={!ready || map.selected == null}
                onClick={() => arrange("exclude")}
              >
                {map.selected != null && map.excluded.includes(map.selected)
                  ? "Include point"
                  : "Exclude point"}
              </button>
              <details className="map-normalization">
                <summary>Normalize patterns</summary>
                <p className="map-note">
                  Match mean intensity in the selected bin interval [start,
                  stop) to a reference point. Original values are retained for
                  Restore.
                </p>
                <div className="map-field-pair">
                  <label className="field-label">
                    Start bin
                    <input
                      aria-label="Normalization start bin"
                      type="number"
                      min="0"
                      value={start}
                      onChange={(e) => setStart(+e.target.value)}
                    />
                  </label>
                  <label className="field-label">
                    Stop bin
                    <input
                      aria-label="Normalization stop bin"
                      type="number"
                      min="1"
                      value={stop}
                      onChange={(e) => setStop(+e.target.value)}
                    />
                  </label>
                </div>
                <label className="field-label">
                  Reference point (0 based)
                  <input
                    aria-label="Normalization reference"
                    type="number"
                    min="0"
                    max={map.points - 1}
                    value={reference}
                    onChange={(e) => setReference(+e.target.value)}
                  />
                </label>
                <div className="file-actions">
                  <button
                    disabled={!ready}
                    onClick={() =>
                      run("map_normalize", { start, stop, reference })
                    }
                  >
                    Normalize
                  </button>
                  <button
                    disabled={!ready || !map.normalized}
                    onClick={() => run("map_normalize", { enabled: false })}
                  >
                    Restore original
                  </button>
                </div>
              </details>
            </section>
          )}
          {tab === "Layers" && (
            <section className="sidebar-section">
              <p className="map-note">
                Pattern windows in {unitLabel(map.unit)}. Peak area, position
                and width subtract a straight edge background.
              </p>
              {map.rois.map((roi) => (
                <WindowEditor
                  key={roi.name}
                  roi={roi}
                  active={map.active === roi.name}
                  ready={ready}
                  run={run}
                />
              ))}
              <button
                disabled={!ready}
                onClick={() => run("map_roi", { op: "add" })}
              >
                Add window
              </button>
              <div className="section-label">EXPRESSION LAYERS</div>
              {Object.entries(map.expressions).map(([key, value]) => (
                <div className="map-expression" key={key}>
                  <button
                    disabled={!ready}
                    onClick={() => run("map_layer", { name: key })}
                  >
                    {key}: {value}
                  </button>
                  <button
                    aria-label={`Remove layer ${key}`}
                    disabled={!ready}
                    onClick={() =>
                      run("map_expression", { name: key, remove: true })
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
              <label className="field-label">
                Layer name
                <input
                  aria-label="Expression layer name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="field-label">
                Expression
                <input
                  aria-label="Map expression"
                  value={expression}
                  onChange={(e) => setExpression(e.target.value)}
                />
              </label>
              <button
                disabled={!ready || !name || !expression}
                onClick={() => run("map_expression", { name, expression })}
              >
                Apply expression
              </button>
              <p className="map-note">
                Use window names, e.g. A/B or (A-B)/(A+B). Invalid or undefined
                values stay blank.
              </p>
            </section>
          )}
          {tab === "Grid" && (
            <section className="sidebar-section">
              <label className="field-label">
                Fits exactly
                <select
                  aria-label="Map grid preset"
                  value={JSON.stringify(map.dimension)}
                  disabled={!ready}
                  onChange={(e) => {
                    const [r, c] = JSON.parse(e.target.value);
                    void run("map_grid", { rows: r, columns: c });
                  }}
                >
                  <option value={JSON.stringify(map.dimension)}>
                    {map.dimension.join(" × ")}
                  </option>
                  {map.presets
                    .filter((d) => String(d) !== String(map.dimension))
                    .map((d) => (
                      <option key={String(d)} value={JSON.stringify(d)}>
                        {d.join(" × ")}
                      </option>
                    ))}
                </select>
              </label>
              <div className="map-field-pair">
                <label className="field-label">
                  Rows
                  <input
                    aria-label="Map rows"
                    type="number"
                    min="1"
                    value={rows}
                    onChange={(e) => setRows(+e.target.value)}
                  />
                </label>
                <label className="field-label">
                  Columns
                  <input
                    aria-label="Map columns"
                    type="number"
                    min="1"
                    value={columns}
                    onChange={(e) => setColumns(+e.target.value)}
                  />
                </label>
              </div>
              <button
                disabled={!ready || rows * columns < map.points}
                onClick={() => run("map_grid", { rows, columns })}
              >
                Apply grid
              </button>
              <p className="map-note">
                {rows * columns} cells for {map.points} points. Unfilled cells
                remain blank; row 0 is at the top.
              </p>
              {(
                [
                  ["snake", "Serpentine (snake) scan"],
                  ["transpose", "Swap fast and slow axis"],
                  ["flip_horizontal", "Mirror left/right"],
                  ["flip_vertical", "Mirror top/bottom"],
                ] as const
              ).map(([key, label]) => (
                <label className="check-row" key={key}>
                  <input
                    disabled={!ready}
                    type="checkbox"
                    checked={map[key]}
                    onChange={(e) =>
                      run("map_grid", { [key]: e.target.checked })
                    }
                  />
                  {label}
                </label>
              ))}
              <button
                disabled={!ready}
                onClick={() => run("map_arrange", { op: "gaps" })}
              >
                Check filename numbering
              </button>
            </section>
          )}
        </>
      )}
    </div>
  );
}
