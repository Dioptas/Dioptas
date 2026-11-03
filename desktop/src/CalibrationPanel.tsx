import { TableScroll, TableActions } from "./DataTable";
import { FolderOpen, ListX, Save, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import type { State } from "./types";
import { number } from "./types";

export function CalibrationPanel({
  state,
  ready,
  ring,
  automatic,
  setAutomatic,
  run,
  selected,
  onSelected,
  onRingChange,
}: {
  state: State | null;
  selected: number[];
  onSelected: (value: number[]) => void;
  onRingChange: (value: number) => void;
  ready: boolean;
  ring: number;
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
  const groupCount = c?.picks.length ?? 0;
  const selectedCount =
    c?.picks.filter((_, index) => selected.includes(index)).length ?? 0;
  const allSelected = groupCount > 0 && selectedCount === groupCount;
  const selectAll = useRef<HTMLInputElement>(null);
  const clearDialog = useRef<HTMLDialogElement>(null);
  const clearButton = useRef<HTMLButtonElement>(null);
  const positionClearDialog = useCallback(() => {
    const dialog = clearDialog.current;
    const button = clearButton.current;
    if (!dialog?.open || !button) return;
    const anchor = button.getBoundingClientRect();
    const gap = 8;
    const left = Math.max(
      gap,
      Math.min(
        anchor.right - dialog.offsetWidth,
        window.innerWidth - dialog.offsetWidth - gap,
      ),
    );
    const below = anchor.bottom + gap;
    const top =
      below + dialog.offsetHeight <= window.innerHeight - gap
        ? below
        : Math.max(gap, anchor.top - dialog.offsetHeight - gap);
    dialog.style.left = `${left}px`;
    dialog.style.top = `${top}px`;
  }, []);
  useEffect(() => {
    window.addEventListener("resize", positionClearDialog);
    return () => window.removeEventListener("resize", positionClearDialog);
  }, [positionClearDialog]);
  const list = useRef<HTMLDivElement>(null);
  const previous = useRef({ count: 0, ring, selected: [] as number[] });
  useEffect(() => {
    if (selectAll.current)
      selectAll.current.indeterminate = selectedCount > 0 && !allSelected;
  }, [selectedCount, allSelected]);
  useEffect(() => {
    const count = c?.picks.length ?? 0;
    const newlySelected = selected.filter(
      (index) => !previous.current.selected.includes(index),
    );
    const index =
      count > previous.current.count
        ? count - 1
        : newlySelected.length === 1
          ? newlySelected[0]
          : ring !== previous.current.ring
            ? (c?.picks.findIndex((pick) => pick.ring === ring) ?? -1)
            : -1;
    previous.current = { count, ring, selected };
    const container = list.current;
    const row = container?.querySelectorAll<HTMLElement>(".peak-row")[index];
    if (!container || !row) return;
    const bounds = container.getBoundingClientRect();
    const headerBottom =
      container.querySelector(".peak-table-headers")?.getBoundingClientRect()
        .bottom ?? bounds.top;
    const rect = row.getBoundingClientRect();
    // Scroll only the rows, without moving the task panel or detector view.
    if (rect.bottom > bounds.bottom)
      container.scrollTop += rect.bottom - bounds.bottom;
    else if (rect.top < headerBottom)
      container.scrollTop -= headerBottom - rect.top;
  }, [c?.picks.length, ring, selected]);
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
          <TableActions
            className="peak-table-actions"
            role="group"
            aria-label="Peak selection actions"
          >
            <button
              className="icon-button"
              aria-label="Load picked peaks"
              title="Load picked peaks (replaces current groups; Undo restores them)"
              disabled={!ready || !state?.hasImage}
              onClick={() => run("load_peaks", {}, "Loading picked peaks…")}
            >
              <FolderOpen size={17} aria-hidden="true" />
            </button>
            <button
              className="icon-button"
              aria-label="Save picked peaks"
              title="Save all picked peak groups"
              disabled={!ready || !groupCount}
              onClick={() => run("save_peaks", {}, "Saving picked peaks…")}
            >
              <Save size={17} aria-hidden="true" />
            </button>
            <button
              className="icon-button peak-delete-selected"
              aria-label="Delete selected"
              title="Delete selected groups"
              disabled={!ready || !selectedCount}
              onClick={() => {
                void run("remove_picks", { indices: selected });
                onSelected([]);
              }}
            >
              <Trash2 size={17} aria-hidden="true" />
            </button>
            <button
              ref={clearButton}
              className="icon-button peak-clear-all"
              aria-label="Clear calibration peaks"
              title="Clear all groups"
              disabled={!ready || !groupCount}
              onClick={() => {
                clearDialog.current?.showModal();
                positionClearDialog();
              }}
            >
              <ListX size={18} aria-hidden="true" />
            </button>
          </TableActions>
        </div>
        <TableScroll
          className="peak-list data-table-grid"
          ref={list}
          role="region"
          aria-label="Picked peak groups"
        >
          <div className="peak-table-headers data-table-header">
            <input
              ref={selectAll}
              type="checkbox"
              aria-label="Select all peak groups"
              title="Select or deselect all groups"
              disabled={!ready || !groupCount}
              checked={allSelected}
              onChange={(e) =>
                onSelected(
                  e.target.checked ? (c?.picks.map((_, i) => i) ?? []) : [],
                )
              }
            />
            <span>Ring</span>
            <span>Peaks</span>
            <span>Position</span>
            <span />
          </div>
          {c?.picks.length ? (
            c.picks.map((pick, index) => (
              <div
                className="peak-row data-table-row"
                key={index}
                role="group"
                aria-label={`Peak group ${index + 1}, ring ${pick.ring}`}
                tabIndex={ready ? 0 : -1}
                data-selected={selected.includes(index)}
                onClick={(event) => {
                  if (
                    !ready ||
                    (event.target as HTMLElement).closest(
                      'button, input[type="checkbox"]',
                    )
                  )
                    return;
                  onSelected([index]);
                  onRingChange(pick.ring);
                }}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget || !ready) return;
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    onSelected([index]);
                    onRingChange(pick.ring);
                  }
                }}
              >
                <input
                  type="checkbox"
                  aria-label={`Select peak group ${index + 1}`}
                  disabled={!ready}
                  checked={selected.includes(index)}
                  onChange={(e) => {
                    onSelected(
                      e.target.checked
                        ? [...selected, index]
                        : selected.filter((i) => i !== index),
                    );
                    if (e.target.checked) onRingChange(pick.ring);
                  }}
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
        </TableScroll>
      </div>
      <dialog
        ref={clearDialog}
        className="clear-peaks-dialog"
        aria-labelledby="clear-peaks-title"
        aria-describedby="clear-peaks-description"
        onClick={(event) => {
          if (event.target !== event.currentTarget) return;
          const bounds = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            event.currentTarget.close();
        }}
      >
        <h2 id="clear-peaks-title">Clear all peaks?</h2>
        <p id="clear-peaks-description">
          This will remove all picked peak groups.
        </p>
        <div className="clear-peaks-dialog-actions">
          <button
            type="button"
            autoFocus
            onClick={() => clearDialog.current?.close()}
          >
            Cancel
          </button>
          <button
            type="button"
            className="clear-peaks-confirm"
            disabled={!ready || !groupCount}
            onClick={() => {
              clearDialog.current?.close();
              void run("clear_peaks");
            }}
          >
            Clear all
          </button>
        </div>
      </dialog>
    </section>
  );
}
