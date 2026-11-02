import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { Calibration } from "./types";

export function CalibrationRingControls({
  calibration,
  ring,
  onRingChange,
  picking,
  onPickingChange,
  onAutoAdvanceChange,
  ready,
  canPick,
}: {
  calibration?: Calibration;
  ring: number;
  onRingChange: (ring: number) => void;
  picking: boolean;
  onPickingChange: (picking: boolean) => void;
  onAutoAdvanceChange: (automatic: boolean) => void;
  ready: boolean;
  canPick: boolean;
}) {
  const id = useId();
  const picker = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const autoAdvance = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const typed = useRef({ text: "", time: 0 });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(ring);
  const rings = calibration?.rings ?? [];
  const previousRing = [...rings]
    .reverse()
    .find((entry) => entry.ring < ring)?.ring;
  const nextRing = rings.find((entry) => entry.ring > ring)?.ring;
  const enabled = ready && rings.length > 0;
  const counts = new Map<number, number>();
  for (const pick of calibration?.picks ?? [])
    counts.set(pick.ring, (counts.get(pick.ring) ?? 0) + pick.points.length);

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) trigger.current?.focus({ preventScroll: true });
  };
  const choose = (value: number) => {
    onRingChange(value);
    close(true);
  };
  const show = () => {
    setActive(
      rings.find((entry) => entry.ring === ring)?.ring ?? rings[0].ring,
    );
    typed.current = { text: "", time: 0 };
    setOpen(true);
  };
  useEffect(() => {
    if (!open) return;
    if (!enabled) {
      setOpen(false);
      return;
    }
    const outside = (event: PointerEvent) => {
      if (!picker.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open, enabled]);
  useEffect(() => {
    if (!open || !enabled) return;
    list.current?.focus({ preventScroll: true });
    list.current
      ?.querySelector(`[data-ring="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [open, enabled, active]);
  const keyboard = (event: KeyboardEvent) => {
    // Keep list navigation and number entry away from application shortcuts.
    event.stopPropagation();
    if (event.key === "Tab") {
      event.preventDefault();
      close();
      (event.shiftKey ? trigger : autoAdvance).current?.focus({
        preventScroll: true,
      });
      return;
    }
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    const index = rings.findIndex((entry) => entry.ring === active);
    if (event.key === "Escape") close(true);
    else if (event.key === "Enter" || event.key === " ") choose(active);
    else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      typed.current.text = "";
      setActive(
        rings[
          Math.max(
            0,
            Math.min(
              rings.length - 1,
              index + (event.key === "ArrowDown" ? 1 : -1),
            ),
          )
        ].ring,
      );
    } else if (event.key === "Home" || event.key === "End")
      setActive(rings[event.key === "Home" ? 0 : rings.length - 1].ring);
    else if (/^\d$/.test(event.key)) {
      const now = performance.now();
      typed.current = {
        text:
          (now - typed.current.time < 800 ? typed.current.text : "") +
          event.key,
        time: now,
      };
      const match = rings.find(
        (entry) => entry.ring === Number(typed.current.text),
      );
      if (match) setActive(match.ring);
    } else if (event.key === "Backspace") typed.current.text = "";
  };
  return (
    <div
      className="calibration-ring-controls"
      role="group"
      aria-label="Ring picking"
    >
      <div
        className="calibration-ring-picker"
        ref={picker}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) close();
        }}
      >
        <div
          className="calibration-ring-navigation"
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ")
              event.stopPropagation();
          }}
        >
          <button
            type="button"
            aria-label="Previous calibrant ring"
            title="Previous ring"
            disabled={!enabled || previousRing === undefined}
            onClick={() => onRingChange(previousRing!)}
          >
            <ChevronLeft size={16} aria-hidden="true" />
          </button>
          <button
            ref={trigger}
            type="button"
            className="calibration-ring-trigger"
            aria-label="Current calibrant ring"
            aria-haspopup="listbox"
            aria-expanded={open && enabled}
            aria-controls={open && enabled ? id : undefined}
            data-ring={ring}
            disabled={!enabled}
            onClick={() => (open ? close() : show())}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                event.stopPropagation();
                show();
              }
            }}
          >
            <span>Ring {ring}</span>
            <ChevronDown size={12} aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Next calibrant ring"
            title="Next ring"
            disabled={!enabled || nextRing === undefined}
            onClick={() => onRingChange(nextRing!)}
          >
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </div>
        {open && enabled && (
          <div className="calibration-ring-menu">
            <div className="calibration-ring-menu-heading" aria-hidden="true">
              <span>Ring</span>
              <span>Picked points</span>
            </div>
            <div
              ref={list}
              id={id}
              role="listbox"
              aria-label="Calibrant rings"
              aria-activedescendant={`${id}-${active}`}
              tabIndex={-1}
              className="calibration-ring-options"
              onKeyDown={keyboard}
            >
              {rings.map((entry) => {
                const count = counts.get(entry.ring) ?? 0;
                return (
                  <div
                    id={`${id}-${entry.ring}`}
                    key={entry.ring}
                    role="option"
                    aria-selected={entry.ring === ring}
                    aria-label={`Ring ${entry.ring}, ${count} picked ${count === 1 ? "point" : "points"}`}
                    data-ring={entry.ring}
                    data-active={entry.ring === active}
                    onClick={() => choose(entry.ring)}
                  >
                    <span>Ring {entry.ring}</span>
                    <span className="calibration-ring-point-count">
                      {count}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
      <div className="calibration-picking-options">
        <label
          className="calibration-picking-switch"
          title="Advance to the next ring after each pick"
        >
          <input
            ref={autoAdvance}
            type="checkbox"
            aria-label="Automatically advance ring number"
            checked={calibration?.workflow.autoIncrement ?? true}
            disabled={!ready}
            onChange={(event) => onAutoAdvanceChange(event.target.checked)}
          />
          Auto advance
        </label>
        <label className="calibration-picking-switch">
          <input
            type="checkbox"
            aria-label="Pick peaks"
            checked={picking}
            disabled={!ready || !canPick}
            onChange={(event) => onPickingChange(event.target.checked)}
          />
          Pick peaks
        </label>
      </div>
    </div>
  );
}
