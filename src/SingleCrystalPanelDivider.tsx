import { useLayoutEffect, useRef, useState } from "react";
import { LayoutDivider } from "./LayoutDivider";
import {
  layoutKeys,
  readLayoutNumber,
  saveLayoutValue,
} from "./layoutPreferences";

const MIN_WIDTH = 300;
const MAX_WIDTH = 640;

/** Image / task panel divider. The width is a local layout preference applied
 * as --sc-panel-width on the workspace; without one the CSS default applies.
 * A display: contents anchor finds the workspace before parent refs attach. */
export function SingleCrystalPanelDivider() {
  const anchor = useRef<HTMLDivElement>(null);
  const [stored, setStored] = useState(() =>
    readLayoutNumber(layoutKeys.scxrdPanelWidth, 0, 0, MAX_WIDTH),
  );
  const [box, setBox] = useState({ width: 1200, large: false });
  useLayoutEffect(() => {
    const node = anchor.current?.parentElement;
    if (!node) return;
    const measure = () => {
      const width = node.clientWidth;
      const large =
        node.closest(".app")?.getAttribute("data-text-size") === "large";
      setBox((old) =>
        old.width === width && old.large === large ? old : { width, large },
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    const style = anchor.current?.parentElement?.style;
    if (!style) return;
    if (stored) style.setProperty("--sc-panel-width", `${stored}px`);
    else style.removeProperty("--sc-panel-width");
  }, [stored]);
  const defaultWidth = box.large ? 410 : 380;
  // The detector image keeps at least half of the workspace.
  const max = Math.max(MIN_WIDTH + 20, Math.min(MAX_WIDTH, box.width / 2));
  const value = Math.min(max, stored || defaultWidth);
  return (
    <div ref={anchor} className="sc-panel-divider-anchor">
      <LayoutDivider
        className="integration-divider integration-divider-image sc-panel-divider"
        label="Image and task panel divider"
        orientation="vertical"
        unit="px"
        value={value}
        min={MIN_WIDTH}
        max={max}
        defaultValue={defaultWidth}
        step={10}
        reverse
        onChange={(next) => {
          const width =
            Math.round(next) === defaultWidth ? 0 : Math.round(next);
          setStored(width);
          saveLayoutValue(layoutKeys.scxrdPanelWidth, width);
        }}
        pointerValue={(event) => {
          const rect = anchor.current?.parentElement?.getBoundingClientRect();
          return rect ? rect.right - event.clientX : null;
        }}
      />
    </div>
  );
}
