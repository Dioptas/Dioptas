import type { Invoke } from "./types";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

export async function updateWindowTitle(imageName: string | null | undefined) {
  const title = imageName ? `${imageName} — Dioptas` : "Dioptas";
  document.title = title;
  if (isTauri()) await getCurrentWindow().setTitle(title);
}

export async function connect(): Promise<Invoke> {
  if (isTauri())
    return (action, payload = {}) =>
      invoke("desktop_invoke", { action, payload });
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
