import { useEffect, useRef, type RefObject } from "react";

function direction(event: WheelEvent) {
  if (
    event.ctrlKey ||
    event.metaKey ||
    !event.deltaY ||
    Math.abs(event.deltaX) > Math.abs(event.deltaY)
  )
    return 0;
  return event.deltaY < 0 ? 1 : -1;
}

function consume(event: WheelEvent) {
  event.preventDefault();
  event.stopPropagation();
}

/** Custom numeric controls keep their own validation and stepping calculation. */
export function useSpinBoxWheel(
  input: RefObject<HTMLInputElement | null>,
  onStep: (direction: number) => void,
  enabled = true,
) {
  const latest = useRef(onStep);
  latest.current = onStep;
  useEffect(() => {
    const element = input.current;
    if (!element || !enabled) return;
    const surface =
      element.closest<HTMLElement>(".pe-number-stepped") ?? element;
    const wheel = (event: WheelEvent) => {
      const step = direction(event);
      if (!step || element.matches(":disabled")) return;
      consume(event);
      latest.current(step);
    };
    surface.addEventListener("wheel", wheel, { passive: false });
    return () => surface.removeEventListener("wheel", wheel);
  }, [input, enabled]);
}

/** Cover native number inputs in every workspace and detached window. */
export function installSpinBoxWheel() {
  document.addEventListener(
    "wheel",
    (event) => {
      if (event.defaultPrevented) return;
      const step = direction(event);
      const input = event.target;
      if (
        !step ||
        !(input instanceof HTMLInputElement) ||
        input.type !== "number" ||
        !input.closest(".app") ||
        input.matches(":disabled") ||
        input.readOnly
      )
        return;
      const current = input.valueAsNumber;
      if (!Number.isFinite(current)) return;
      consume(event);
      const quantum = Number(input.step) > 0 ? Number(input.step) : 1;
      const min = input.min ? Number(input.min) : -Infinity;
      const max = input.max ? Number(input.max) : Infinity;
      const next = Math.min(
        max,
        Math.max(min, Number((current + step * quantum).toPrecision(12))),
      );
      if (next === current) return;
      input.focus({ preventScroll: true });
      // Use the native setter so React's value tracker observes the input event.
      Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )!.set!.call(input, String(next));
      input.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertReplacementText",
          data: String(next),
        }),
      );
    },
    { passive: false },
  );
}
