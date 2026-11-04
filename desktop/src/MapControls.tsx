import { TableScroll, TableActions } from "./DataTable";
import {
  ArrowUp,
  ArrowDown,
  PlusSquare,
  MinusSquare,
  Ban,
  CircleCheck,
  FolderOpen,
  RefreshCw,
} from "lucide-react";
import { MapLayers } from "./MapLayers";
import { useEffect, useState, useRef, type ReactNode } from "react";
import type { State } from "./types";
import { unitLabel } from "./types";
import type { MapData, MapRun } from "./mapDomain";

export function MapControls({
  map,
  state,
  ready,
  run,
  reintegrate,
  onReintegrate,
  imageTab,
}: {
  imageTab?: ReactNode;
  map: MapData | null;
  state: State | null;
  ready: boolean;
  run: MapRun;
  reintegrate: boolean;
  onReintegrate: (v: boolean) => void;
}) {
  const [tab, setTab] = useState("Points");
  const [rows, setRows] = useState(1),
    [columns, setColumns] = useState(1);
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
  const list = useRef<HTMLDivElement>(null);
  const draggedSlot = useRef<number | null>(null);
  const keyboardSelection = useRef(false);
  useEffect(() => {
    const row = list.current?.querySelector<HTMLElement>(
      '[aria-selected="true"]',
    );
    if (ready) row?.scrollIntoView({ block: "nearest" });
    if (ready && keyboardSelection.current) {
      row?.focus({ preventScroll: true });
      keyboardSelection.current = false;
    }
  }, [map?.selectedSlot, page, ready]);
  useEffect(() => {
    if (!imageTab && tab === "Image") setTab("Points");
  }, [!!imageTab, tab]);
  const selected = map?.selectedSlot;
  const arrange = (op: string, args = {}) =>
    run("map_arrange", { op, slot: selected, index: map?.selected, ...args });
  return (
    <div className="map-controls">
      <div className="map-tabs" role="tablist" aria-label="Map controls">
        {[...(imageTab ? ["Image"] : []), "Points", "Layers", "Grid"].map(
          (t) => (
            <button
              key={t}
              role="tab"
              id={`map-tab-${t}`}
              aria-selected={tab === t}
              aria-controls="map-tab-content"
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ),
        )}
      </div>
      <div
        id="map-tab-content"
        className={`map-tab-content ${tab === "Image" ? "map-image-tab" : ""}`}
        role="tabpanel"
        aria-labelledby={`map-tab-${tab}`}
      >
        {tab === "Image" && imageTab}
        {tab === "Points" && (
          <section className="sidebar-section map-source-section">
            <div className="map-source-actions">
              <button
                disabled={!ready || !state?.calibrated}
                onClick={() => run("map_load", {}, "Integrating map images…")}
              >
                <FolderOpen size={15} /> Load images…
              </button>
              <button
                disabled={!ready || !state?.calibrated}
                onClick={() =>
                  run("map_folder", {}, "Integrating scan folder…")
                }
              >
                Folder…
              </button>
              <button
                aria-label="Load processed batch…"
                title="Load a processed HDF5 / NeXus batch"
                disabled={!ready}
                onClick={() => run("map_batch", {}, "Loading processed batch…")}
              >
                Batch…
              </button>
            </div>
            <div className="map-source-calibration">
              <button
                className="quiet"
                title={state?.calibrationName ?? "Load a PONI calibration"}
                disabled={!ready}
                onClick={() => run("open_calibration")}
              >
                {state?.calibrationName ?? "Load calibration…"}
              </button>
              {map && (
                <button
                  aria-label="Rebuild map"
                  title="Reintegrate all map images with the current settings"
                  disabled={!ready || !state?.calibrated || !map.canRebuild}
                  onClick={() =>
                    run("map_load", { reintegrate: true }, "Reintegrating map…")
                  }
                >
                  <RefreshCw size={14} /> Rebuild
                </button>
              )}
            </div>
            {!state?.calibrated && (
              <p className="map-note">
                Load a calibration to integrate images. Processed batches can be
                opened directly.
              </p>
            )}
          </section>
        )}
        {map && (
          <>
            {tab === "Points" && (
              <section className="sidebar-section map-points-section">
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
                  {map.points} points ·{" "}
                  {map.normalized ? "normalized" : "stored"} patterns ·{" "}
                  {unitLabel(map.unit)}.
                </p>
                <div className="map-points-tools" ref={list}>
                  <TableScroll
                    className="map-file-list data-list"
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
                                ? "data-list-row map-excluded"
                                : "data-list-row"
                            }
                            draggable={ready}
                            onDragStart={(event) => {
                              draggedSlot.current = slot;
                              event.dataTransfer.effectAllowed = "move";
                              event.dataTransfer.setData(
                                "text/plain",
                                String(slot),
                              );
                            }}
                            onDragOver={(event) => {
                              event.preventDefault();
                              event.dataTransfer.dropEffect = "move";
                            }}
                            onDrop={(event) => {
                              event.preventDefault();
                              const from = draggedSlot.current;
                              draggedSlot.current = null;
                              if (from !== null && from !== slot)
                                void run("map_arrange", {
                                  op: "move",
                                  slot: from,
                                  offset: slot - from,
                                });
                            }}
                            onDragEnd={() => {
                              draggedSlot.current = null;
                            }}
                            onKeyDown={(event) => {
                              const offset =
                                event.key === "ArrowUp"
                                  ? -1
                                  : event.key === "ArrowDown"
                                    ? 1
                                    : 0;
                              if (
                                !offset ||
                                slot + offset < 0 ||
                                slot + offset >= map.slots.length
                              )
                                return;
                              event.preventDefault();
                              keyboardSelection.current = true;
                              if (event.altKey)
                                void run("map_arrange", {
                                  op: "move",
                                  slot,
                                  offset,
                                });
                              else
                                void run("map_select", {
                                  slot: slot + offset,
                                  reintegrate,
                                });
                            }}
                            onClick={() =>
                              run("map_select", { slot, reintegrate })
                            }
                            title={label}
                          >
                            <span>{slot + 1}</span>
                            <span className="map-point-name">
                              {point === null
                                ? "— Blank cell"
                                : label || "Raw source unavailable"}
                            </span>
                          </button>
                        );
                      })}
                  </TableScroll>
                  <TableActions
                    orientation="vertical"
                    aria-label="Point arrangement actions"
                  >
                    <button
                      aria-label="Move up"
                      title="Move up · Alt+↑"
                      disabled={!ready || selected == null || selected === 0}
                      onClick={() => arrange("move", { offset: -1 })}
                    >
                      <ArrowUp size={16} />
                    </button>
                    <button
                      aria-label="Move down"
                      title="Move down · Alt+↓"
                      disabled={
                        !ready ||
                        selected == null ||
                        selected >= map.slots.length - 1
                      }
                      onClick={() => arrange("move", { offset: 1 })}
                    >
                      <ArrowDown size={16} />
                    </button>
                    <span className="map-action-spacer" />
                    <button
                      aria-label="Insert blank"
                      title="Insert blank cell before selection"
                      disabled={!ready || selected == null}
                      onClick={() => arrange("insert")}
                    >
                      <PlusSquare size={16} />
                    </button>
                    <button
                      aria-label="Remove blank"
                      title="Remove selected blank cell"
                      disabled={
                        !ready ||
                        selected == null ||
                        map.slots[selected] !== null ||
                        !map.slots
                          .slice(selected + 1)
                          .some((point) => point !== null)
                      }
                      onClick={() => arrange("remove")}
                    >
                      <MinusSquare size={16} />
                    </button>
                    <button
                      aria-label={
                        map.selected != null &&
                        map.excluded.includes(map.selected)
                          ? "Include point"
                          : "Exclude point"
                      }
                      title={
                        map.selected != null &&
                        map.excluded.includes(map.selected)
                          ? "Put point back in map"
                          : "Leave selected point out of map"
                      }
                      disabled={!ready || map.selected == null}
                      onClick={() => arrange("exclude")}
                    >
                      {map.selected != null &&
                      map.excluded.includes(map.selected) ? (
                        <CircleCheck size={16} />
                      ) : (
                        <Ban size={16} />
                      )}
                    </button>
                  </TableActions>
                </div>
                {map.labels.length > 100 && (
                  <div className="map-pagination">
                    <button
                      disabled={page === 0}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous 100
                    </button>
                    <span>
                      {page * 100 + 1}–
                      {Math.min((page + 1) * 100, map.labels.length)} /{" "}
                      {map.labels.length}
                    </span>
                    <button
                      disabled={(page + 1) * 100 >= map.labels.length}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next 100
                    </button>
                  </div>
                )}
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
              <MapLayers map={map} ready={ready} run={run} />
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
    </div>
  );
}
