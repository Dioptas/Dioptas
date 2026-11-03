import { RasterTransfer } from "./rasterTransfer";
import type { Invoke } from "./types";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

export async function updateWindowTitle(imageName: string | null | undefined) {
  const base = imageName ? `${imageName} — Dioptas` : "Dioptas";
  const previewLabel = import.meta.env.VITE_DIOPTAS_PREVIEW_LABEL;
  const title = previewLabel ? `${base} · ${previewLabel}` : base;
  document.title = title;
  if (isTauri()) await getCurrentWindow().setTitle(title);
}

export async function connect(): Promise<Invoke> {
  if (isTauri()) {
    const transfer = new RasterTransfer((action, payload, cachedBuffers) =>
      invoke<ArrayBuffer>("desktop_invoke", { action, payload, cachedBuffers }),
    );
    return (action, payload = {}) => transfer.call(action, payload);
  }
  if (window.pywebview?.api.invoke) return window.pywebview.api.invoke;
  return new Promise((resolve, reject) => {
    const ready = () => {
      clearTimeout(timeout);
      if (window.pywebview?.api.invoke) resolve(window.pywebview.api.invoke);
      else reject(new Error("The desktop bridge is unavailable."));
    };
    const timeout = setTimeout(() => {
      window.removeEventListener("pywebviewready", ready);
      reject(
        new Error(
          "Open this interface with desktop/launch.command (Tauri), or python -m dioptas.desktop (legacy preview). A plain browser needs the development test bridge.",
        ),
      );
    }, 8000);
    window.addEventListener("pywebviewready", ready, { once: true });
  });
}
