import { Button, Input, Select } from "./ui";
import { TabList } from "./TabList";
import { TableScroll, TableActions } from "./DataTable";
import {
  ArrowUp,
  ArrowDown,
  PlusSquare,
  MinusSquare,
  Ban,
  CircleCheck,
  RefreshCw,
  Radio,
  FolderOpen,
  ListOrdered,
  Settings,
} from "lucide-react";
import { MapLayers } from "./MapLayers";
import { MapLoadActions } from "./MapLoadActions";
import { MapSettingsDialog } from "./MapSettingsDialog";
import {
  useEffect,
  useState,
  useRef,
  type ReactNode,
  type KeyboardEvent,
  type CSSProperties,
} from "react";
import type { State, Unit } from "./types";
import type { MapData, MapRun } from "./mapDomain";

export function MapControls({
  map,
  state,
  ready,
  run,
  live,
  onLive,
  follow,
  onFollow,
  imageTab,
  windowUnit,
  reintegrateSelected,
  onReintegrateSelected,
}: {
  reintegrateSelected: boolean;
  onReintegrateSelected: (enabled: boolean) => void;
  imageTab?: ReactNode;
  windowUnit?: Unit;
  map: MapData | null;
  state: State | null;
  ready: boolean;
  run: MapRun;
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsTrigger = useRef<HTMLButtonElement>(null);
  const reintegrate =
    reintegrateSelected && !!state?.calibrated && !map?.normalized;
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
      <TabList
        className="map-tabs"
        label="Map controls"
        value={tab}
        onChange={setTab}
        options={[
          ...(imageTab ? ["Image"] : []),
          "Points",
          "Layers",
          "Grid",
        ].map((t) => ({
          value: t,
          label: t,
          id: `map-tab-${t}`,
          panelId: "map-tab-content",
        }))}
      />
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
              <MapLoadActions
                ready={ready}
                calibrated={!!state?.calibrated}
                run={run}
              />
              <Button
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
              </Button>
              <label
                className="check-row map-follow"
                title="Select the newest point as scan images arrive"
              >
                <Input
                  type="checkbox"
                  aria-label="Follow newest map point"
                  checked={follow}
                  disabled={!live || !ready}
                  onChange={(e) => onFollow(e.target.checked)}
                />
                Follow
              </label>
              <span className="map-source-spacer" />
              <Button
                className="plot-tool-button map-source-icon"
                aria-label="Load map calibration"
                title={`Load calibration…${state?.calibrationName ? ` · ${state.calibrationName}` : ""}`}
                disabled={!ready}
                onClick={() => run("open_calibration")}
              >
                <FolderOpen size={16} />
              </Button>
              <Button
                className="plot-tool-button map-source-icon"
                aria-label="Reintegrate map"
                title="Reintegrate all map images with the current settings"
                disabled={!ready || !map?.canRebuild || !state?.calibrated}
                onClick={() =>
                  run("map_load", { reintegrate: true }, "Reintegrating map…")
                }
              >
                <RefreshCw size={15} />
              </Button>
            </div>
          </section>
        )}
        {map && (
          <>
            {tab === "Points" && (
              <section className="sidebar-section map-points-section">
                <div className="map-points-tools" ref={list}>
                  <TableActions
                    orientation="horizontal"
                    aria-label="Point arrangement actions"
                  >
                    <div
                      className="map-point-action-group"
                      role="group"
                      aria-label="Move points"
                    >
                      <Button
                        aria-label="Move up"
                        title="Move up · Alt+↑"
                        disabled={!ready || selected == null || selected === 0}
                        onClick={() => arrange("move", { offset: -1 })}
                      >
                        <ArrowUp size={16} />
                      </Button>
                      <Button
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
                      </Button>
                    </div>
                    <div
                      className="map-point-action-group"
                      role="group"
                      aria-label="Blank cells and filename numbering"
                    >
                      <Button
                        aria-label="Insert blank"
                        title="Insert blank cell before selection"
                        disabled={!ready || selected == null}
                        onClick={() => arrange("insert")}
                      >
                        <PlusSquare size={16} />
                      </Button>
                      <Button
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
                      </Button>
                      <Button
                        aria-label="Check filename numbering"
                        title="Check filename numbering and insert blank cells for missing scan numbers"
                        disabled={!ready}
                        onClick={() => run("map_arrange", { op: "gaps" })}
                      >
                        <ListOrdered size={16} />
                      </Button>
                    </div>
                    <div
                      className="map-point-action-group map-point-exclusion"
                      role="group"
                      aria-label="Point inclusion"
                    >
                      <Button
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
                      </Button>
                    </div>
                    <Button
                      className="map-point-settings"
                      ref={settingsTrigger}
                      aria-label="Map settings"
                      title="Map folder settings"
                      aria-haspopup="dialog"
                      disabled={!ready}
                      onClick={() => setSettingsOpen(true)}
                    >
                      <Settings size={16} />
                    </Button>
                  </TableActions>
                  <TableScroll
                    className="map-file-list data-list"
                    style={
                      {
                        "--map-point-index-width": `${Math.max(3, String(map.slots.length).length)}ch`,
                      } as CSSProperties
                    }
                    role="listbox"
                    aria-label="Scan arrangement"
                  >
                    {map.labels
                      .slice(page * 100, page * 100 + 100)
                      .map((label, offset) => {
                        const slot = page * 100 + offset,
                          point = map.slots[slot];
                        return (
                          <Button
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
                          </Button>
                        );
                      })}
                  </TableScroll>
                </div>
                {map.labels.length > 100 && (
                  <div className="map-pagination">
                    <Button
                      disabled={page === 0}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous 100
                    </Button>
                    <span>
                      {page * 100 + 1}–
                      {Math.min((page + 1) * 100, map.labels.length)} /{" "}
                      {map.labels.length}
                    </span>
                    <Button
                      disabled={(page + 1) * 100 >= map.labels.length}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next 100
                    </Button>
                  </div>
                )}
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
                  <Select
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
                  </Select>
                </label>
                <div className="map-field-pair">
                  <label className="field-label">
                    Rows
                    <Input
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
                    <Input
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
                    <Input
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
              </section>
            )}
          </>
        )}
      </TableScroll>
      {map && settingsOpen && (
        <MapSettingsDialog
          map={map}
          ready={ready}
          run={run}
          anchor={settingsTrigger.current}
          reintegrateSelected={reintegrateSelected}
          onReintegrateSelected={onReintegrateSelected}
          displayUnit={windowUnit ?? map.unit}
          wavelength={state?.calibrated ? state.geometry.wavelength : undefined}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
}
