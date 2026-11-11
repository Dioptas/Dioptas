import { Button, Input, Portal, Popover } from "./ui";
import { Dialog } from "./Dialog";
import { PatternBackgroundIcon, WaterfallIcon } from "./DiffractionActionIcons";
import {
  DataTable,
  TableBodyScroll,
  TableScroll,
  TableActions,
} from "./DataTable";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { KeyboardEvent as RowKeyEvent } from "react";
import { ORIGINAL_PATTERN_UID } from "./integration";
import {
  ArrowDown,
  ArrowUp,
  FolderOpen,
  ListX,
  RotateCcw,
  Trash2,
} from "lucide-react";
import type { IntegrationRun, IntegrationState } from "./integration";
import "./integrationOverlayControls.css";
import { OverlayColorScalePicker } from "./OverlayColorScalePicker";

// Qt keeps this widget alive when changing modes. Retain its local view state
// for this window's JS lifetime when React temporarily unmounts Integration.
const retained = {
  selectedUid: null as string | null,
  scaleStep: 0.01,
  offsetStep: 100,
};

/** The Qt OverlayWidget's action rail, editable table and parameter rail. */
export function IntegrationOverlayControls({
  source,
  run,
  onSelectionChange,
  showOriginal,
  onShowOriginalChange,
  originalColor,
  onOriginalColorChange,
}: {
  source: IntegrationState;
  run: IntegrationRun;
  onSelectionChange: (uid: string | null) => void;
  showOriginal: boolean;
  onShowOriginalChange: (show: boolean) => void;
  originalColor: string;
  onOriginalColorChange: (color: string) => void;
}) {
  const controlsRef = useRef<HTMLDivElement>(null);
  const [toolbarLayout, setToolbarLayout] = useState("single");
  useLayoutEffect(() => {
    const node = controlsRef.current;
    if (!node) return;
    const parameters = node.querySelector<HTMLElement>(
      ".qt-overlay-parameters",
    )!;
    const steps = node.querySelector<HTMLElement>(".qt-overlay-step-controls")!;
    const waterfall = node.querySelector<HTMLElement>(
      ".qt-overlay-waterfall-actions",
    )!;
    const background = node.querySelector<HTMLElement>(
      ".qt-overlay-background-action",
    )!;
    const measure = () => {
      if (!node.clientWidth) return;
      if (node.clientWidth > 600) {
        setToolbarLayout("single");
        return;
      }
      const style = getComputedStyle(parameters);
      const gap = parseFloat(style.columnGap) || 0;
      const available =
        parameters.clientWidth -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight);
      const spacing = node.querySelector<HTMLInputElement>(
        '[aria-label="Waterfall separation"]',
      )!;
      const spacingWidth =
        parseFloat(getComputedStyle(spacing).width) +
        parseFloat(getComputedStyle(waterfall).columnGap);
      const hidden = node.dataset.toolbarLayout?.endsWith("reduced");
      const fullWaterfall =
        waterfall.getBoundingClientRect().width + (hidden ? spacingWidth : 0);
      const backgroundWidth = background.getBoundingClientRect().width;
      const full =
        steps.getBoundingClientRect().width +
        fullWaterfall +
        backgroundWidth +
        2 * gap;
      // Prefer hiding the optional spacing box to wrapping any action. Once a
      // second row is necessary, restore it if the complete action row fits.
      setToolbarLayout(
        available + 0.5 >= full
          ? "single"
          : available + 0.5 >= full - spacingWidth
            ? "reduced"
            : available + 0.5 >= fullWaterfall + backgroundWidth + gap
              ? "two-rows"
              : "two-rows-reduced",
      );
    };
    const observer = new ResizeObserver(measure);
    for (const element of [node, parameters, steps, waterfall, background])
      observer.observe(element);
    measure();
    return () => observer.disconnect();
  }, []);
  const [selectedUid, select] = useState<string | null>(retained.selectedUid);
  useEffect(
    () => onSelectionChange(selectedUid),
    [selectedUid, onSelectionChange],
  );
  const [scaleStep, setScaleStep] = useState(retained.scaleStep);
  const [offsetStep, setOffsetStep] = useState(retained.offsetStep);
  const menuTrigger = useRef<HTMLTableRowElement | null>(null);
  const [menu, setMenu] = useState<{
    uid: string;
    x: number;
    y: number;
  } | null>(null);
  useEffect(() => {
    Object.assign(retained, { selectedUid, scaleStep, offsetStep });
  }, [selectedUid, scaleStep, offsetStep]);
  const clearDialog = useRef<HTMLDialogElement>(null);
  const clearButton = useRef<HTMLButtonElement>(null);
  const positionClearDialog = useCallback(() => {
    const dialog = clearDialog.current,
      button = clearButton.current;
    if (!dialog?.open || !button) return;
    const anchor = button.getBoundingClientRect(),
      gap = 8;
    dialog.style.left = `${Math.max(gap, Math.min(anchor.right - dialog.offsetWidth, window.innerWidth - dialog.offsetWidth - gap))}px`;
    const below = anchor.bottom + gap;
    dialog.style.top = `${below + dialog.offsetHeight <= window.innerHeight - gap ? below : Math.max(gap, anchor.top - dialog.offsetHeight - gap)}px`;
  }, []);
  useEffect(() => {
    window.addEventListener("resize", positionClearDialog);
    return () => window.removeEventListener("resize", positionClearDialog);
  }, [positionClearDialog]);
  const tableScroll = useRef<HTMLTableSectionElement>(null);
  const tableHead = useRef<HTMLTableSectionElement>(null);
  const originalGroup = useRef<HTMLTableSectionElement>(null);
  const synchronizeHeader = useCallback(() => {
    const body = tableScroll.current,
      head = tableHead.current;
    if (!body || !head) return;
    for (const group of [head, originalGroup.current]) {
      if (!group) continue;
      group.style.paddingRight = `${body.offsetWidth - body.clientWidth}px`;
      const row = group.firstElementChild as HTMLElement | null;
      if (row) row.style.transform = `translateX(${-body.scrollLeft}px)`;
    }
  }, []);
  useEffect(() => {
    const body = tableScroll.current;
    if (!body) return;
    const observer = new ResizeObserver(synchronizeHeader);
    observer.observe(body);
    synchronizeHeader();
    return () => observer.disconnect();
  }, [synchronizeHeader]);
  const previous = useRef<string[]>([]);
  const overlays = source.overlays;
  const index = overlays.findIndex((o) => o.uid === selectedUid);
  const selected = overlays[index];
  useEffect(() => {
    const added = overlays.filter((o) => !previous.current.includes(o.uid));
    if (
      added.length &&
      (previous.current.length || !overlays.some((o) => o.uid === selectedUid))
    )
      select(added[added.length - 1].uid);
    else if (
      !overlays.some((o) => o.uid === selectedUid) &&
      !(selectedUid === ORIGINAL_PATTERN_UID && source.patternName)
    ) {
      const oldIndex = previous.current.indexOf(selectedUid ?? "");
      select(
        overlays[Math.max(0, Math.min(oldIndex, overlays.length - 1))]?.uid ??
          (source.patternName ? ORIGINAL_PATTERN_UID : null),
      );
    }
    previous.current = overlays.map((o) => o.uid);
  }, [overlays, selectedUid, source.patternName]);
  useEffect(() => {
    const scroll = tableScroll.current;
    const row = scroll?.querySelector('tr[aria-selected="true"]');
    if (!scroll || !row) return;
    const bounds = scroll.getBoundingClientRect(),
      selectedBounds = row.getBoundingClientRect();
    if (selectedBounds.top < bounds.top)
      scroll.scrollTop += selectedBounds.top - bounds.top;
    else if (selectedBounds.bottom > bounds.top + scroll.clientHeight)
      scroll.scrollTop +=
        selectedBounds.bottom - bounds.top - scroll.clientHeight;
  }, [selectedUid, overlays.length]);
  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "Tab") {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
        }
        close();
        menuTrigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", key);
    };
  }, [menu]);
  const action = (operation: string, args: Record<string, unknown> = {}) =>
    void run(
      "integration_overlay",
      { operation, ...args },
      "Updating overlays…",
    );
  const move = (direction: number) => action("move", { index, direction });
  const navigateRows = (event: RowKeyEvent<HTMLTableRowElement>) => {
    if (
      event.target !== event.currentTarget ||
      !["ArrowUp", "ArrowDown"].includes(event.key)
    )
      return false;
    event.preventDefault();
    const rows = [
      ...(event.currentTarget
        .closest("table")
        ?.querySelectorAll<HTMLTableRowElement>("tbody tr") ?? []),
    ];
    const current = rows.indexOf(event.currentTarget);
    rows[
      Math.max(
        0,
        Math.min(rows.length - 1, current + (event.key === "ArrowUp" ? -1 : 1)),
      )
    ]?.focus();
    return true;
  };

  return (
    <div
      ref={controlsRef}
      className="qt-overlay-controls"
      data-toolbar-layout={toolbarLayout}
    >
      <TableActions
        orientation="vertical"
        className="qt-overlay-actions"
        role="group"
        aria-label="Overlay actions"
      >
        <div className="qt-overlay-action-pair">
          <Button
            title="Loads Overlay(s) from file(s)"
            aria-label="Add overlay files"
            onClick={() =>
              action("load", { directory: source.overlayDirectory })
            }
          >
            <FolderOpen size={17} />
          </Button>
          <Button
            title="Removes currently selected overlay"
            aria-label="Delete selected overlay"
            disabled={!selected}
            onClick={() => action("remove", { index })}
          >
            <Trash2 size={16} />
          </Button>
        </div>
        <div className="qt-overlay-clear-group">
          <div className="qt-overlay-spacer" />
          <hr />
          <div className="qt-overlay-spacer" />
          <Button
            ref={clearButton}
            title="Clear all overlays"
            aria-label="Clear overlays"
            className="danger"
            disabled={!overlays.length}
            onClick={() => {
              clearDialog.current?.showModal();
              positionClearDialog();
            }}
          >
            <ListX size={18} aria-hidden="true" />
          </Button>
          <div className="qt-overlay-spacer" />
          <hr />
          <div className="qt-overlay-spacer" />
        </div>
        <div className="qt-overlay-action-pair">
          <Button
            title="Move selected overlay up"
            aria-label="Move overlay up"
            disabled={index < 1}
            onClick={() => move(-1)}
          >
            <ArrowUp size={17} />
          </Button>
          <Button
            title="Move selected overlay down"
            aria-label="Move overlay down"
            disabled={index < 0 || index >= overlays.length - 1}
            onClick={() => move(1)}
          >
            <ArrowDown size={17} />
          </Button>
        </div>
      </TableActions>
      <div className="qt-overlay-table-region">
        <DataTable
          layout="grid"
          className="qt-overlay-table"
          role="table"
          aria-label="Overlays"
        >
          <thead ref={tableHead}>
            <tr>
              <th>
                <Button
                  className="qt-overlay-show-all"
                  aria-label="Toggle all overlays"
                  title="Show or hide all overlays"
                  disabled={!overlays.length}
                  onClick={() =>
                    action("visibility", {
                      visible: !overlays.some((o) => o.visible),
                    })
                  }
                >
                  ✓
                </Button>
              </th>
              <th aria-label="Color">
                <OverlayColorScalePicker
                  count={overlays.length}
                  onApply={(colors) => action("color_scale", { colors })}
                />
              </th>
              <th>Name</th>
              <th>Scale</th>
              <th>Offset</th>
            </tr>
          </thead>
          <tbody className="qt-overlay-original-group" ref={originalGroup}>
            {Boolean(source.patternName) && (
              <tr
                className="qt-overlay-original-row"
                aria-label="Original pattern row"
                aria-selected={selectedUid === ORIGINAL_PATTERN_UID}
                tabIndex={selectedUid === ORIGINAL_PATTERN_UID ? 0 : -1}
                onClick={() => select(ORIGINAL_PATTERN_UID)}
                onFocus={() => select(ORIGINAL_PATTERN_UID)}
                onKeyDown={navigateRows}
              >
                <td>
                  <Input
                    type="checkbox"
                    aria-label="Original pattern"
                    checked={showOriginal}
                    onChange={(event) =>
                      onShowOriginalChange(event.target.checked)
                    }
                  />
                </td>
                <td>
                  <Input
                    type="color"
                    aria-label="Original pattern color"
                    title="Original pattern color"
                    value={originalColor}
                    onChange={(event) =>
                      onOriginalColorChange(event.target.value)
                    }
                  />
                </td>
                <td className="qt-overlay-name-cell">
                  <span
                    className="qt-overlay-original-name"
                    title={source.patternPath || source.patternName}
                  >
                    Original · {source.patternName}
                  </span>
                </td>
                <td>
                  <span
                    className="qt-overlay-fixed-value"
                    role="group"
                    aria-label="Original pattern scale"
                    title="Original scale is fixed"
                  >
                    1
                  </span>
                </td>
                <td>
                  <span
                    className="qt-overlay-fixed-value"
                    role="group"
                    aria-label="Original pattern offset"
                    title="Original offset is fixed"
                  >
                    0
                  </span>
                </td>
              </tr>
            )}
          </tbody>
          <TableBodyScroll
            className="qt-overlay-table-scroll"
            ref={tableScroll}
            onScroll={synchronizeHeader}
          >
            {overlays.map((overlay, row) => (
              <tr
                key={overlay.uid}
                aria-selected={overlay.uid === selectedUid}
                onClick={() => select(overlay.uid)}
                onFocus={() => select(overlay.uid)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  select(overlay.uid);
                  menuTrigger.current = e.currentTarget;
                  setMenu({ uid: overlay.uid, x: e.clientX, y: e.clientY });
                }}
                onKeyDown={(e) => {
                  if (navigateRows(e)) return;
                  if (
                    (e.key === "F10" && e.shiftKey) ||
                    e.key === "ContextMenu"
                  ) {
                    e.preventDefault();
                    const box = e.currentTarget.getBoundingClientRect();
                    select(overlay.uid);
                    menuTrigger.current = e.currentTarget;
                    setMenu({
                      uid: overlay.uid,
                      x: box.left + 30,
                      y: box.bottom,
                    });
                  }
                }}
                tabIndex={overlay.uid === selectedUid ? 0 : -1}
              >
                <td>
                  <Input
                    type="checkbox"
                    aria-label={`Show overlay ${row + 1}`}
                    checked={overlay.visible}
                    onChange={(e) =>
                      action("update", {
                        index: row,
                        visible: e.target.checked,
                      })
                    }
                  />
                </td>
                <td>
                  <Input
                    type="color"
                    aria-label={`Overlay ${row + 1} color`}
                    value={overlay.color}
                    onChange={(e) =>
                      action("update", { index: row, color: e.target.value })
                    }
                  />
                </td>
                <td className="qt-overlay-name-cell">
                  <OverlayName
                    name={overlay.name}
                    label={`Overlay ${row + 1} name`}
                    onCommit={(name) => action("update", { index: row, name })}
                  />
                </td>
                <td>
                  <OverlayNumber
                    label={`Overlay ${row + 1} scale`}
                    value={overlay.scale}
                    step={scaleStep}
                    min={-9999999}
                    max={9999999}
                    onCommit={(scale) =>
                      action("update", { index: row, scale })
                    }
                  />
                </td>
                <td>
                  <OverlayNumber
                    label={`Overlay ${row + 1} offset`}
                    value={overlay.offset}
                    step={offsetStep}
                    min={-9999999}
                    max={9999999}
                    onCommit={(offset) =>
                      action("update", { index: row, offset })
                    }
                  />
                </td>
              </tr>
            ))}
          </TableBodyScroll>
        </DataTable>
        {!overlays.length && (
          <p className="qt-overlay-empty">
            Load overlay files or use As Overlay below the pattern.
          </p>
        )}
      </div>
      <div
        className="qt-overlay-parameters"
        role="group"
        aria-label="Overlay parameters"
      >
        <TableScroll className="qt-overlay-parameter-scroll">
          <div className="qt-overlay-step-controls">
            <label title="Scale step">
              <span>Scale</span>
              <OverlayNumber
                label="Scale Step"
                value={scaleStep}
                min={0.0001}
                max={10}
                multiply
                onCommit={setScaleStep}
              />
            </label>
            <label title="Offset step">
              <span>Offset</span>
              <OverlayNumber
                label="Offset Step"
                value={offsetStep}
                min={0.0001}
                max={100000}
                multiply
                onCommit={setOffsetStep}
              />
            </label>
          </div>
          <hr />
          <div className="qt-overlay-waterfall-actions">
            <Button
              aria-label="Waterfall"
              title={`Apply waterfall separation (${source.waterfallSeparation} intensity units)`}
              disabled={!overlays.length}
              onClick={() => action("waterfall")}
            >
              <WaterfallIcon
                className="qt-overlay-waterfall-icon"
                size={16}
                aria-hidden="true"
              />
              <span className="qt-overlay-waterfall-label">Waterfall</span>
            </Button>
            <label
              className="qt-overlay-spacing-field"
              title="Waterfall separation"
            >
              <span>Spacing</span>
              <OverlayNumber
                label="Waterfall separation"
                value={source.waterfallSeparation}
                min={-100000}
                step={0.01}
                max={100000}
                multiply
                onCommit={(separation) =>
                  action("waterfall_separation", { separation })
                }
              />
            </label>
            <Button
              aria-label="Auto waterfall spacing"
              title="Auto spacing: 10% of mean scaled intensity above each pattern’s minimum, averaged across patterns and rounded up; existing offsets are ignored"
              disabled={!overlays.length}
              onClick={() => action("waterfall_auto")}
            >
              A
            </Button>
            <Button
              aria-label="Reset"
              title="Reset waterfall separation"
              disabled={!overlays.length}
              onClick={() => action("reset_offsets")}
            >
              <RotateCcw size={16} aria-hidden="true" />
            </Button>
          </div>
        </TableScroll>
        <div className="qt-overlay-background-action">
          <Button
            aria-label="As Bkg"
            title="Set selected overlay as background"
            aria-pressed={selected?.background ?? false}
            disabled={!selected}
            onClick={() => action("background", { index })}
          >
            <PatternBackgroundIcon size={16} aria-hidden="true" />
          </Button>
        </div>
      </div>
      <Dialog
        autoOpen={false}
        dialogRef={clearDialog}
        returnFocusRef={clearButton}
        className="clear-peaks-dialog"
        aria-labelledby="clear-overlays-title"
        aria-describedby="clear-overlays-description"
      >
        <h2 id="clear-overlays-title">Clear all overlays?</h2>
        <p id="clear-overlays-description">
          This will remove all loaded overlays.
        </p>
        <div className="clear-peaks-dialog-actions">
          <Button
            type="button"
            autoFocus
            onClick={() => clearDialog.current?.close()}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="clear-peaks-confirm"
            disabled={!overlays.length}
            onClick={() => {
              clearDialog.current?.close();
              action("clear");
            }}
          >
            Clear all
          </Button>
        </div>
      </Dialog>
      {menu && (
        <Portal>
          {
            <Popover
              className="qt-overlay-menu"
              role="menu"
              style={{
                left: Math.max(0, Math.min(menu.x, window.innerWidth - 180)),
                top: Math.max(0, Math.min(menu.y, window.innerHeight - 45)),
              }}
              onPointerDown={(e) => e.stopPropagation()}
            >
              <Button
                role="menuitem"
                autoFocus
                onClick={() => {
                  const row = overlays.findIndex((o) => o.uid === menu.uid);
                  setMenu(null);
                  menuTrigger.current?.focus();
                  if (row >= 0) action("match_intensity", { index: row });
                }}
              >
                Match intensity
              </Button>
            </Popover>
          }
        </Portal>
      )}
    </div>
  );
}

function OverlayName({
  name,
  label,
  onCommit,
}: {
  name: string;
  label: string;
  onCommit: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  useEffect(() => setDraft(name), [name]);
  return (
    <Input
      aria-label={label}
      title={name}
      value={draft}
      readOnly={!editing}
      onDoubleClick={(e) => {
        setEditing(true);
        e.currentTarget.select();
      }}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setEditing(false);
        if (draft !== name) onCommit(draft);
      }}
      onKeyDown={(e) => {
        if (e.key === "F2") setEditing(true);
        if (e.key === "Enter") {
          if (editing) e.currentTarget.blur();
          else {
            setEditing(true);
            e.currentTarget.select();
          }
        }
        if (e.key === "Escape") {
          setDraft(name);
          setEditing(false);
        }
      }}
    />
  );
}

// Same 1–2–5 progression as Qt DoubleMultiplySpinBoxAlignRight.
function nextStep(value: number, up: boolean) {
  const base = 10 ** Math.floor(Math.log10(Math.max(value, 0.0001)));
  const ratio = value / base;
  return up
    ? base * (ratio < 1.9 ? 2 : ratio < 4.9 ? 5 : 10)
    : base * (ratio < 1.1 ? 0.5 : ratio < 2.1 ? 1 : ratio < 5.1 ? 2 : 5);
}

function OverlayNumber({
  label,
  value,
  onCommit,
  min,
  max,
  step = 1,
  multiply = false,
}: {
  label: string;
  value: number;
  onCommit: (v: number) => void;
  min: number;
  max: number;
  step?: number | "any";
  multiply?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState(String(value));
  const submitted = useRef<number | undefined>(undefined);
  useEffect(() => {
    setDraft(String(value));
    submitted.current = undefined;
  }, [value]);
  const send = (v: number) => {
    if (v !== value && v !== submitted.current) {
      submitted.current = v;
      onCommit(v);
    }
  };
  const advance = (up: boolean) => {
    const current = Number(draft);
    if (!draft.trim() || !Number.isFinite(current)) return;
    let next: number;
    if (multiply && min < 0) {
      const quantum = step === "any" ? 0.01 : step;
      if (current === 0) next = up ? quantum : -quantum;
      else if (
        ((current > 0 && !up) || (current < 0 && up)) &&
        Math.abs(current) <= quantum
      )
        next = 0;
      else
        next = current > 0 ? nextStep(current, up) : -nextStep(-current, !up);
    } else
      next = multiply
        ? nextStep(current, up)
        : current + (up ? 1 : -1) * (step === "any" ? 1 : step);
    const stepped = Math.min(max, Math.max(min, Number(next.toPrecision(12))));
    setDraft(String(stepped));
    send(stepped);
  };
  const wheelStep = useRef(advance);
  wheelStep.current = advance;
  useEffect(() => {
    const element = input.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      if (!event.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY))
        return;
      event.preventDefault();
      if (!element.matches(":disabled")) wheelStep.current(event.deltaY < 0);
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);
  const commit = () => {
    const v = Number(draft);
    if (draft.trim() && Number.isFinite(v) && v >= min && v <= max) send(v);
    else setDraft(String(value));
  };
  return (
    <Input
      ref={input}
      className="numeric-stepper"
      type="number"
      aria-label={label}
      value={draft}
      min={min > 0 ? 0 : min}
      max={max}
      step={multiply && min > 0 ? min : step}
      onChange={(e) => {
        const next = e.target.value;
        // Native spin arrows emit an Event; typing/paste emits an InputEvent.
        // Keep the native control and replace only its stepping calculation.
        const current = Number(draft);
        if (
          multiply &&
          !(e.nativeEvent instanceof InputEvent) &&
          draft.trim() &&
          next.trim() &&
          Number.isFinite(current) &&
          Number(next) !== current
        ) {
          advance(Number(next) > current);
        } else setDraft(next);
      }}
      onBlur={commit}
      onPointerUp={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        else if (e.key === "Escape") setDraft(String(value));
      }}
      onKeyUp={(e) => {
        if (e.key === "ArrowUp" || e.key === "ArrowDown") commit();
      }}
    />
  );
}
