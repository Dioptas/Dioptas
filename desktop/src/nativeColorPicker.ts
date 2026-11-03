import { invoke, isTauri } from "@tauri-apps/api/core";

/** Remember the swatch for WebKit's separate native More Colors window. */
export function installNativeColorPickerAnchors() {
  if (!isTauri()) return;
  let lastInput: HTMLInputElement | null = null;
  let lastPrepared = -Infinity;
  const prepare = (event: Event) => {
    const input = event.target;
    if (
      !(input instanceof HTMLInputElement) ||
      input.type !== "color" ||
      input.matches(":disabled")
    )
      return;
    if (event instanceof KeyboardEvent && !["Enter", " "].includes(event.key))
      return;
    const now = performance.now();
    if (input === lastInput && now - lastPrepared < 100) return;
    lastInput = input;
    lastPrepared = now;
    const box = input.getBoundingClientRect();
    void invoke("prepare_color_picker", {
      anchor: {
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom,
      },
    }).catch((error) =>
      console.error("Could not position the native color picker", error),
    );
  };
  document.addEventListener("pointerdown", prepare, true);
  document.addEventListener("focusin", prepare, true);
  document.addEventListener("click", prepare, true);
  document.addEventListener("keydown", prepare, true);
}
