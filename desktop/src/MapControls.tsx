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
  Radio,
  Crosshair,
} from "lucide-react";
import { MapLayers } from "./MapLayers";
import {
  useEffect,
  useState,
  useRef,
  type ReactNode,
  type KeyboardEvent,
} from "react";
import type { State, Unit } from "./types";
import { unitLabel } from "./types";
import type { MapData, MapRun } from "./mapDomain";

export function MapControls({
  map,
  state,
  ready,
  run,
  reintegrate,
  onReintegrate,
  live,
  onLive,
  follow,
  onFollow,
  imageTab,
  windowUnit,
}: {
  imageTab?: ReactNode;
  windowUnit?: Unit;
  map: MapData | null;
  state: State | null;
  ready: boolean;
  run: MapRun;
  reintegrate: boolean;
  onReintegrate: (v: boolean) => void;
  live: boolean;
  onLive: (v: boolean) => void;
  follow: boolean;
  onFollow: (v: boolean) => void;
}) {
  const [tab, setTab] = useState("Points");
  const [rows, setRows] = useState(() => String(map?.dimension[0] ?? 1)),
    [columns, setColumns] = useState(() => String(map?.dimension[1] ?? 1));
  const gridPending = useRef<string | null>(null);
  const submittedGrid = useRef<{ rows: string; columns: string } | null>(null);
  const [start, setStart] = useState(0),
    [stop, setStop] = useState(100),
    [reference, setReference] = useState(0);
  const [page, setPage] = useState(0);
  useEffect(() => {
    setPage(map?.selectedSlot == null ? 0 : Math.floor(map.selectedSlot / 100));
  }, [map?.selectedSlot, map?.points]);
  useEffect(() => {
    if (map) {
      const submitted = submittedGrid.current;
      setRows((current) =>
        !submitted || current === submitted.rows
          ? String(map.dimension[0])
          : current,
      );
      setColumns((current) =>
        !submitted || current === submitted.columns
          ? String(map.dimension[1])
          : current,
      );
      submittedGrid.current = null;
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
  const gridRows = Number(rows),
    gridColumns = Number(columns);
  const gridNumbersValid =
    rows.trim() !== "" &&
    columns.trim() !== "" &&
    Number.isInteger(gridRows) &&
    Number.isInteger(gridColumns) &&
    gridRows > 0 &&
    gridColumns > 0;
  const gridCells = gridNumbersValid ? gridRows * gridColumns : null;
  const gridValid =
    gridCells !== null &&
    gridCells >= (map?.points ?? 0) &&
    gridCells <= 4_000_000;
  const applyGrid = async () => {
    if (
      !ready ||
      !map ||
      !gridValid ||
      (gridRows === map.dimension[0] && gridColumns === map.dimension[1])
    )
      return;
    const key = `${gridRows}:${gridColumns}`;
    if (gridPending.current === key) return;
    gridPending.current = key;
    submittedGrid.current = { rows, columns };
    try {
      await run("map_grid", { rows: gridRows, columns: gridColumns });
    } finally {
      if (gridPending.current === key) gridPending.current = null;
    }
  };
  const gridKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void applyGrid();
    }
    if (event.key === "Escape" && map) {
      event.preventDefault();
      setRows(String(map.dimension[0]));
      setColumns(String(map.dimension[1]));
    }
  };
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
      <TableScroll
        id="map-tab-content"
        className={`map-tab-content ${tab === "Image" ? "map-image-tab" : tab === "Points" ? "map-points-tab" : ""}`}
        role="tabpanel"
        aria-labelledby={`map-tab-${tab}`}
      >
        {tab === "Image" && imageTab}
        {tab === "Points" && (
          <section className="sidebar-section map-source-section">
            <div
              className="integration-image-tools map-source-actions"
              role="group"
              aria-label="Map scan controls"
            >
              <button
                className="plot-tool-button"
                aria-label="Load images…"
                title="Load detector images"
                disabled={!ready || !state?.calibrated}
                onClick={() => run("map_load", {}, "Integrating map images…")}
              >
                <FolderOpen size={15} /> Load…
              </button>
              <button
                className="plot-tool-button"
                title="Integrate detector images from a folder"
                disabled={!ready || !state?.calibrated}
                onClick={() =>
                  run("map_folder", {}, "Integrating scan folder…")
                }
              >
                Folder…
              </button>
              <button
                className="plot-tool-button map-live-button"
                aria-label="Live map"
                aria-pressed={live}
                title="Append new completed scan files from this map’s folder"
                disabled={
                  !ready ||
                  !map?.canRebuild ||
                  !state?.calibrated ||
                  !!map?.normalized
                }
                onClick={() => onLive(!live)}
              >
                <Radio size={15} /> Live
              </button>
              <label
                className="check-row map-follow"
                title="Select the newest point as scan images arrive"
              >
                <input
                  type="checkbox"
                  aria-label="Follow newest map point"
                  checked={follow}
                  disabled={!live || !ready}
                  onChange={(e) => onFollow(e.target.checked)}
                />
                Follow
              </label>
              <span className="map-source-spacer" />
              <button
                className="plot-tool-button map-source-icon"
                aria-label="Load map calibration"
                title={`Load calibration…${state?.calibrationName ? ` · ${state.calibrationName}` : ""}`}
                disabled={!ready}
                onClick={() => run("open_calibration")}
              >
                <Crosshair size={16} />
              </button>
              <button
                className="plot-tool-button map-source-icon"
                aria-label="Reintegrate map"
                title="Reintegrate all map images with the current settings"
                disabled={!ready || !map?.canRebuild || !state?.calibrated}
                onClick={() =>
                  run("map_load", { reintegrate: true }, "Reintegrating map…")
                }
              >
                <RefreshCw size={15} />
              </button>
            </div>
            {!state?.calibrated && (
              <p className="map-note">
                Load a calibration to integrate images.
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
              <MapLayers
                map={map}
                ready={ready}
                run={run}
                unit={windowUnit ?? map.unit}
                wavelength={
                  state?.calibrated ? state.geometry.wavelength : undefined
                }
              />
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
                      onChange={(e) => setRows(e.target.value)}
                      onBlur={() => void applyGrid()}
                      onKeyDown={gridKeyDown}
                      aria-invalid={
                        (rows !== "" &&
                          (!Number.isInteger(gridRows) || gridRows < 1)) ||
                        undefined
                      }
                    />
                  </label>
                  <label className="field-label">
                    Columns
                    <input
                      aria-label="Map columns"
                      type="number"
                      min="1"
                      value={columns}
                      onChange={(e) => setColumns(e.target.value)}
                      onBlur={() => void applyGrid()}
                      onKeyDown={gridKeyDown}
                      aria-invalid={
                        (columns !== "" &&
                          (!Number.isInteger(gridColumns) ||
                            gridColumns < 1)) ||
                        undefined
                      }
                    />
                  </label>
                </div>
                <p className="map-note" aria-live="polite">
                  {gridCells === null
                    ? "Enter positive whole numbers for both dimensions."
                    : gridCells < map.points
                      ? `${gridCells} cells — at least ${map.points} are needed.`
                      : gridCells > 4_000_000
                        ? "Use no more than 4 million cells."
                        : `${gridCells} cells for ${map.points} points.`}
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
      </TableScroll>
    </div>
  );
}
