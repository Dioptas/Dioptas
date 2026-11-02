import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { State } from "./types";
import { number } from "./types";

export function CalibrationPanel({
  state,
  ready,
  ring,
  setRing,
  automatic,
  setAutomatic,
  run,
  selected,
  onSelected,
}: {
  state: State | null;
  selected: number[];
  onSelected: (value: number[]) => void;
  ready: boolean;
  ring: number;
  setRing: (ring: number) => void;
  automatic: boolean;
  setAutomatic: (value: boolean) => void;
  run: (
    command: string,
    args?: Record<string, unknown>,
    message?: string,
  ) => unknown;
}) {
  const c = state?.calibration,
    points = c?.picks.reduce((sum, pick) => sum + pick.points.length, 0) ?? 0;
  const rings = new Set(c?.picks.map((pick) => pick.ring)).size;
  const list = useRef<HTMLDivElement>(null);
  const [rows, setRows] = useState(4);
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil((c?.picks.length ?? 0) / rows));
  useEffect(() => {
    if (!list.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setRows(Math.max(1, Math.floor(entry.contentRect.height / 36))),
    );
    observer.observe(list.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    setPage((value) => Math.min(value, pageCount - 1));
  }, [pageCount]);
  useEffect(() => {
    const index = c?.picks.findIndex((pick) => pick.ring === ring) ?? -1;
    if (index >= 0) setPage(Math.floor(index / rows));
  }, [ring]);
  return (
    <section className="panel calibration-panel">
      <div className="panel-heading">
        <div>
          <span className="panel-dot teal" />
          <h2>Peak selection</h2>
        </div>
        <span className="panel-meta">
          {points} peaks · {rings} rings
        </span>
      </div>
      <div className="calibration-panel-body">
        <div className="current-ring-control">
          <label htmlFor="ring-number">Current ring number</label>
          <input
            id="ring-number"
            className="numeric-stepper"
            aria-label="Current calibrant ring"
            type="number"
            min="1"
            max={c?.rings.length || 999}
            step="1"
            value={ring}
            disabled={!ready}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (
                Number.isInteger(n) &&
                n >= 1 &&
                n <= (c?.rings.length || 999)
              )
                setRing(n);
            }}
          />
        </div>
        <p className="current-ring-angle">
          <span data-testid="active-ring">Picking ring {ring}</span> ·{" "}
          {number(c?.rings.find((r) => r.ring === ring)?.twoTheta ?? 0, 3)}° ·
          2θ
        </p>
        <label className="check-row">
          <input
            aria-label="Automatically advance ring number"
            type="checkbox"
            disabled={!ready}
            checked={c?.workflow.autoIncrement ?? true}
            onChange={(e) =>
              run("workflow_settings", { autoIncrement: e.target.checked })
            }
          />
          Automatic increase
        </label>
        <fieldset className="peak-search-options">
          <label className="check-row">
            <input
              type="radio"
              name="peak-search"
              disabled={!ready}
              aria-label="Automatic peak search"
              checked={automatic}
              onChange={() => setAutomatic(true)}
            />
            Automatic peak search
          </label>
          <label className="check-row">
            <input
              type="radio"
              name="peak-search"
              disabled={!ready}
              aria-label="Single peak search"
              checked={!automatic}
              onChange={() => setAutomatic(false)}
            />
            Single peak search
          </label>
          <label className="search-size">
            Search size
            <input
              aria-label="Single-peak search size"
              className="numeric-stepper"
              type="number"
              min="1"
              max="1000"
              disabled={automatic || !ready}
              key={c?.workflow.searchSize}
              defaultValue={c?.workflow.searchSize ?? 10}
              onBlur={(e) => {
                if (Number(e.target.value) !== c?.workflow.searchSize)
                  run("workflow_settings", {
                    searchSize: Number(e.target.value),
                  });
              }}
            />
            <span>px</span>
          </label>
        </fieldset>
        <div className="peak-table-heading">
          <span>RING SELECTIONS</span>
        </div>
        <div className="peak-table-headers" aria-hidden="true">
          <span />
          <span />
          <span>Ring</span>
          <span>Peaks</span>
          <span>Position</span>
          <span />
        </div>
        <div className="peak-list" ref={list}>
          {c?.picks.length ? (
            c.picks
              .map((pick, index) => ({ pick, index }))
              .slice(page * rows, (page + 1) * rows)
              .map(({ pick, index }) => (
                <div className="peak-row" key={index}>
                  <span
                    className={`ring-color${pick.ring === ring ? " current-ring" : ""}${selected.includes(index) ? " selected-peak" : ""}`}
                  />
                  <input
                    type="checkbox"
                    aria-label={`Select peak group ${index + 1}`}
                    checked={selected.includes(index)}
                    onChange={(e) =>
                      onSelected(
                        e.target.checked
                          ? [...selected, index]
                          : selected.filter((i) => i !== index),
                      )
                    }
                  />
                  <input
                    className="ring-input"
                    aria-label={`Ring assignment ${index + 1}`}
                    type="number"
                    min="1"
                    max={c.rings.length}
                    key={`ring-${index}-${pick.ring}`}
                    defaultValue={pick.ring}
                    disabled={!ready}
                    onBlur={(e) => {
                      if (Number(e.target.value) !== pick.ring)
                        void run("reassign_pick", {
                          index,
                          ring: Number(e.target.value),
                        });
                    }}
                  />
                  <span className="peak-count">{pick.points.length}</span>
                  <span
                    className="pick-position"
                    title="Mean image position (column, row from top)"
                  >
                    {number(
                      pick.points.reduce((sum, p) => sum + p[1], 0) /
                        pick.points.length,
                      0,
                    )}
                    ,{" "}
                    {number(
                      (state?.shape?.[0] ?? 1) -
                        1 -
                        pick.points.reduce((sum, p) => sum + p[0], 0) /
                          pick.points.length,
                      0,
                    )}
                  </span>
                  <button
                    className="icon-button"
                    disabled={!ready}
                    aria-label={`Remove selection ${index + 1}`}
                    onClick={() => run("remove_pick", { index })}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))
          ) : (
            <div className="no-peaks">
              No peaks selected yet.
              <br />
              Picking is active in Pick rings. Click bright positions on the
              current ring.
            </div>
          )}
        </div>
        <div className="peak-pagination" aria-label="Peak selection pages">
          <button
            type="button"
            aria-label="Previous peak page"
            disabled={page === 0}
            onClick={() => setPage((value) => value - 1)}
          >
            ‹
          </button>
          <span>
            {c?.picks.length
              ? `${page * rows + 1}–${Math.min((page + 1) * rows, c.picks.length)} of ${c.picks.length} groups`
              : "No groups"}
          </span>
          <button
            type="button"
            aria-label="Next peak page"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((value) => value + 1)}
          >
            ›
          </button>
        </div>
        <div
          className="file-actions compact-actions"
          role="group"
          aria-label="Peak selection actions"
        >
          <button
            aria-label="Delete selected"
            disabled={!ready || !selected.length}
            onClick={() => {
              void run("remove_picks", { indices: selected });
              onSelected([]);
            }}
          >
            Delete
          </button>
          <button
            aria-label="Clear calibration peaks"
            disabled={!ready || !points}
            onClick={() => run("clear_peaks")}
          >
            Clear all
          </button>
          <button
            disabled={!ready || !points}
            onClick={() => onSelected(c?.picks.map((_, i) => i) ?? [])}
          >
            Select all
          </button>
        </div>
      </div>
    </section>
  );
}
