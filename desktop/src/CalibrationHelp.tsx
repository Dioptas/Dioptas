import { useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CircleHelp } from "lucide-react";

// Text follows the refinement options in docs/source/calibration.rst.
// Search thresholds are checked against CalibrationModel.search_peaks_on_ring.
export const calibrationHelp = {
  deltaTth:
    "How far to search on either side of each predicted ring, in degrees of 2θ. A wider search may find more peaks, but can include neighbouring rings.",
  meanFactor:
    "How bright peaks must be compared with the surrounding area. Lower values find weaker peaks but may include noise. Try 3 for spotty rings or 1–1.5 for smooth rings.",
  intensityLimit:
    "Pixels brighter than this value are ignored during the peak search. Use it to exclude saturated or unusually bright pixels.",
  numberOfRings:
    "How many calibrant rings to search, starting with the first ring. Choose enough to include the visible rings.",
} as const;

export function CalibrationHelp({
  label,
  text,
}: {
  label: string;
  text: string;
}) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const show = () => {
    clearTimeout(closeTimer.current);
    setOpen(true);
  };
  const hide = () => {
    closeTimer.current = setTimeout(() => setOpen(false), 120);
  };

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = button.current?.getBoundingClientRect();
      const box = tooltip.current?.getBoundingClientRect();
      if (!anchor || !box) return;
      setPosition({
        left: Math.max(12, Math.min(anchor.left, innerWidth - box.width - 12)),
        top: Math.max(
          12,
          anchor.bottom + box.height + 8 < innerHeight - 12
            ? anchor.bottom + 8
            : anchor.top - box.height - 8,
        ),
      });
    };
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    window.addEventListener("keydown", dismiss);
    return () => {
      clearTimeout(closeTimer.current);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("keydown", dismiss);
    };
  }, [open]);

  return (
    <>
      <button
        ref={button}
        type="button"
        className="icon-button calibration-help-button"
        aria-label={`Help: ${label}`}
        aria-describedby={open ? id : undefined}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={() => setOpen(false)}
        onClick={show}
      >
        <CircleHelp size={15} aria-hidden="true" />
      </button>
      {open &&
        createPortal(
          <div
            ref={tooltip}
            id={id}
            role="tooltip"
            className="calibration-help-tooltip"
            style={position}
            onMouseEnter={show}
            onMouseLeave={hide}
          >
            {text}
          </div>,
          document.querySelector(".app") ?? document.body,
        )}
    </>
  );
}
