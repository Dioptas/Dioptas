import { useLayoutEffect, type RefObject } from "react";

/** Position an open native dialog from its measured size, including text scaling. */
export function useAnchoredDialog(
  dialog: RefObject<HTMLDialogElement | null>,
  anchor: HTMLElement | null,
  open = true,
  align: "start" | "end" = "end",
  preferAbove = false,
) {
  useLayoutEffect(() => {
    const popup = dialog.current;
    if (!open || !popup || !anchor) return;
    const place = () => {
      const target = anchor.getBoundingClientRect();
      const inset = 8,
        gap = 6;
      const width = popup.offsetWidth,
        height = popup.offsetHeight;
      const below = target.bottom + gap,
        above = target.top - gap - height;
      const top =
        preferAbove && above >= inset
          ? above
          : below + height <= innerHeight - inset
            ? below
            : above >= inset
              ? above
              : Math.max(inset, innerHeight - height - inset);
      const left = align === "end" ? target.right - width : target.left;
      popup.style.left = `${Math.max(inset, Math.min(left, innerWidth - width - inset))}px`;
      popup.style.top = `${top}px`;
    };
    const observer = new ResizeObserver(place);
    observer.observe(popup);
    observer.observe(anchor);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    place();
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [dialog, anchor, open, align, preferAbove]);
}
