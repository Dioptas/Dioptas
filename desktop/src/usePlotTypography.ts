import { useLayoutEffect, useState, type RefObject } from "react";

/** Canvas text follows the same readable control size as DOM plot labels. */
export function usePlotTypography(target: RefObject<HTMLElement | null>) {
  const [size, setSize] = useState(14);
  const [muted, setMuted] = useState("#a6b1bc");
  useLayoutEffect(() => {
    const read = () => {
      const element = target.current;
      if (!element) return;
      const style = getComputedStyle(element);
      const value = parseFloat(style.getPropertyValue("--text-small"));
      const color = style.getPropertyValue("--ui-muted").trim();
      if (color) setMuted((current) => (current === color ? current : color));
      if (Number.isFinite(value))
        setSize((current) => (current === value ? current : value));
    };
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, {
      subtree: true,
      attributes: true,
      attributeFilter: ["data-text-size"],
    });
    read();
    return () => observer.disconnect();
  }, [target]);
  return {
    size,
    muted,
    scale: size / 13,
    mono: `${size}px ui-monospace, SFMono-Regular, monospace`,
    text: `${size}px -apple-system, sans-serif`,
  };
}
