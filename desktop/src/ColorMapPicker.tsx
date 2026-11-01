import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { colorMaps, colorMapPreview } from "./colorMaps";

export function ColorMapPicker({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  const names = Object.keys(colorMaps),
    selected = colorMaps[value] ? value : "grey",
    id = useId();
  const button = useRef<HTMLButtonElement>(null),
    list = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{
    left: number;
    top: number;
    height: number;
  } | null>(null);
  const [active, setActive] = useState(names.indexOf(selected));
  const close = () => {
    setPosition(null);
    button.current?.focus({ preventScroll: true });
  };
  const choose = (name: string) => {
    onChange(name);
    close();
  };
  const open = () => {
    const box = button.current!.getBoundingClientRect(),
      height = Math.min(520, window.innerHeight - 16);
    setActive(names.indexOf(selected));
    setPosition({
      left: Math.max(8, Math.min(box.left, window.innerWidth - 276)),
      top:
        box.bottom + height + 4 <= window.innerHeight
          ? box.bottom + 4
          : Math.max(8, box.top - height - 4),
      height,
    });
  };
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
      if (!position) open();
      else
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
      else open();
    } else if (event.key === "Tab") setPosition(null);
  };
  return (
    <>
      <button
        type="button"
        ref={button}
        className="color-map-picker"
        role="combobox"
        aria-label={label}
        aria-haspopup="listbox"
        aria-controls={position ? id : undefined}
        aria-expanded={!!position}
        data-color-map={selected}
        title={`${colorMaps[selected].label} colour scale`}
        onClick={() => (position ? close() : open())}
        onKeyDown={keyboard}
      >
        <img
          src={colorMapPreview(selected)}
          alt={`${colorMaps[selected].label} colour scale`}
        />
        <span aria-hidden="true">▾</span>
      </button>
      {position &&
        createPortal(
          <div className="color-map-backdrop" onPointerDown={close}>
            <div
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
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
