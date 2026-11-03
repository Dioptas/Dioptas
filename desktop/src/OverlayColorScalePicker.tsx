import { Palette, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { colorMaps } from "./colorMaps";
import { overlayScaleColors } from "./overlayColorScales";
import "./overlayColorScalePicker.css";

const scales = ["viridis", "plasma", "magma", "inferno", "cividis", "turbo"];

export function OverlayColorScalePicker({
  count,
  onApply,
}: {
  count: number;
  onApply: (colors: string[]) => void;
}) {
  const button = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [reverse, setReverse] = useState(false);
  useEffect(() => {
    const resize = () => dialog.current?.close();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const open = () => {
    const picker = dialog.current,
      anchor = button.current?.getBoundingClientRect();
    if (!picker || !anchor) return;
    picker.showModal();
    picker.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - picker.offsetWidth - 8))}px`;
    picker.style.top = `${Math.max(8, Math.min(anchor.bottom + 8, innerHeight - picker.offsetHeight - 8))}px`;
  };
  return (
    <>
      <button
        ref={button}
        className="qt-overlay-color-scale-button"
        aria-label="Color overlays by scale"
        title="Assign overlay colors from a color scale"
        disabled={!count}
        onClick={open}
      >
        <Palette size={16} aria-hidden="true" />
      </button>
      <dialog
        ref={dialog}
        className="overlay-color-scale-dialog"
        aria-labelledby="overlay-color-scale-title"
        onClick={(event) => {
          if (event.target !== event.currentTarget) return;
          const box = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < box.left ||
            event.clientX > box.right ||
            event.clientY < box.top ||
            event.clientY > box.bottom
          )
            event.currentTarget.close();
        }}
      >
        <div className="overlay-color-scale-heading">
          <h2 id="overlay-color-scale-title">Overlay color scale</h2>
          <button
            aria-label="Close color scales"
            onClick={() => dialog.current?.close()}
          >
            <X size={16} />
          </button>
        </div>
        <label className="overlay-color-scale-reverse">
          <input
            type="checkbox"
            checked={reverse}
            onChange={(event) => setReverse(event.target.checked)}
          />
          Reverse scale
        </label>
        <div className="overlay-color-scale-options">
          {scales.map((name) => (
            <button
              key={name}
              aria-label={`Apply ${colorMaps[name].label} to overlays`}
              onClick={() => {
                const colors = overlayScaleColors(
                  colorMaps[name].colors,
                  count,
                  reverse,
                );
                dialog.current?.close();
                onApply(colors);
              }}
            >
              <span>{colorMaps[name].label}</span>
              <span
                className="overlay-scale-preview"
                aria-hidden="true"
                style={{
                  background: `linear-gradient(to right, ${overlayScaleColors(colorMaps[name].colors, 32, reverse).join(", ")})`,
                }}
              />
            </button>
          ))}
        </div>
        <p>
          Dark endpoints are trimmed for visibility. Applies in table order;
          Undo restores the previous colors.
        </p>
      </dialog>
    </>
  );
}
