import { Popover, Portal } from "./ui";
import { useEffect, useId, useImperativeHandle, useRef, useState } from "react";
import type { Ref } from "react";

import { colorMaps, colorMapPreview } from "./colorMaps";

type MenuPoint = { clientX: number; clientY: number };
export type ColorMapPickerHandle = {
  open: (trigger: SVGRectElement, point?: MenuPoint) => void;
};

export function ColorMapPicker({
  value,
  onChange,
  label,
  ref,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  ref?: Ref<ColorMapPickerHandle>;
}) {
  const names = Object.keys(colorMaps),
    selected = colorMaps[value] ? value : "grey",
    id = useId();
  const trigger = useRef<SVGRectElement | null>(null),
    list = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{
    left: number;
    top: number;
    height: number;
  } | null>(null);
  const [active, setActive] = useState(names.indexOf(selected));
  const close = () => {
    setPosition(null);
    trigger.current?.focus({ preventScroll: true });
  };
  const choose = (name: string) => {
    onChange(name);
    close();
  };
  const open = (element: SVGRectElement, point?: MenuPoint) => {
    trigger.current = element;
    const box = element.getBoundingClientRect(),
      x = point?.clientX ?? box.left + box.width / 2,
      y = Math.max(
        12,
        Math.min(
          point?.clientY ?? box.top + box.height / 2,
          window.innerHeight - 12,
        ),
      ),
      below = window.innerHeight - y - 12,
      above = y - 12,
      openBelow = below >= Math.min(260, above),
      height = Math.min(520, openBelow ? below : above);
    setActive(names.indexOf(selected));
    setPosition({
      left: Math.max(8, Math.min(x + 4, window.innerWidth - 268)),
      top: openBelow ? y + 4 : y - height - 4,
      height,
    });
  };
  useImperativeHandle(ref, () => ({ open }));
  useEffect(() => {
    if (!position) return;
    const option = list.current?.querySelector<HTMLElement>(
      `[data-index="${active}"]`,
    );
    option?.focus({ preventScroll: true });
    option?.scrollIntoView({ block: "nearest" });
  }, [position, active]);
  const keyboard = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (position)
        setActive(
          (index) =>
            (index + (event.key === "ArrowDown" ? 1 : -1) + names.length) %
            names.length,
        );
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      setActive(event.key === "Home" ? 0 : names.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (position) choose(names[active]);
    } else if (event.key === "Tab") setPosition(null);
  };
  return (
    <>
      {position && (
        <Portal>
          <div className="color-map-backdrop" onPointerDown={close}>
            <Popover
              id={id}
              ref={list}
              className="color-map-options"
              role="listbox"
              aria-label={`${label} choices`}
              style={{
                left: position.left,
                top: position.top,
                maxHeight: position.height,
              }}
              onPointerDown={(event) => event.stopPropagation()}
              onKeyDown={keyboard}
            >
              {names.map((name, index) => (
                <div
                  key={name}
                  role="option"
                  aria-selected={name === selected}
                  aria-label={colorMaps[name].label}
                  tabIndex={-1}
                  data-color-map={name}
                  data-index={index}
                  className={index === active ? "focused" : ""}
                  onPointerMove={() => setActive(index)}
                  onClick={() => choose(name)}
                >
                  <img
                    src={colorMapPreview(name)}
                    alt={`${colorMaps[name].label} colour scale`}
                  />
                  <span>{colorMaps[name].label}</span>
                </div>
              ))}
            </Popover>
          </div>
        </Portal>
      )}
    </>
  );
}
