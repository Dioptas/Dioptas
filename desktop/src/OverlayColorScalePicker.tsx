import { Dialog, DialogHeader } from "./Dialog";
import { Palette } from "lucide-react";
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
      <Button
        ref={button}
        className="qt-overlay-color-scale-button"
        aria-label="Color overlays by scale"
        title="Assign overlay colors from a color scale"
        disabled={!count}
        onClick={open}
      >
        <Palette size={16} aria-hidden="true" />
      </button>
      <Dialog
        autoOpen={false}
        dialogRef={dialog}
        returnFocusRef={button}
        className="overlay-color-scale-dialog"
        aria-labelledby="overlay-color-scale-title"
      >
        <DialogHeader
          title="Overlay color scale"
          titleId="overlay-color-scale-title"
          closeLabel="Close color scales"
          onClose={() => dialog.current?.close()}
        />
        <label className="overlay-color-scale-reverse">
          <Input
            type="checkbox"
            checked={reverse}
            onChange={(event) => setReverse(event.target.checked)}
          />
          Reverse scale
        </label>
        <div className="overlay-color-scale-options">
          {scales.map((name) => (
            <Button
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
            </Button>
          ))}
        </div>
        <p>
          Dark endpoints are trimmed for visibility. Applies in table order;
          Undo restores the previous colors.
        </p>
      </Dialog>
    </>
  );
}
