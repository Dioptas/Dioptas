import { withErrorReporting, reportFailure } from "./errorReporting";
import { RasterTransfer } from "./rasterTransfer";
import type { Invoke } from "./commandContracts";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import { applicationWindowTitle } from "./windowTitle";
import { getCurrentWindow } from "@tauri-apps/api/window";

let nativeVersion: Promise<string> | undefined;
export async function updateWindowTitle(context?: string | null) {
  const version = isTauri()
    ? await (nativeVersion ??= getVersion())
    : import.meta.env.VITE_DIOPTAS_VERSION;
  const title = applicationWindowTitle(
    version,
    context,
    import.meta.env.VITE_DIOPTAS_PREVIEW_LABEL,
  );
  document.title = title;
  if (isTauri()) await getCurrentWindow().setTitle(title);
}

export async function connect(): Promise<Invoke> {
  try {
    return withErrorReporting(await rawConnect());
  } catch (error) {
    reportFailure("Connecting to the processor", error);
    throw error;
  }
}
async function rawConnect(): Promise<Invoke> {
  if (isTauri()) {
    const transfer = new RasterTransfer(
      (action, payload, cachedBuffers, cachedProducts) =>
        invoke<ArrayBuffer>("desktop_invoke", {
          action,
          payload,
          cachedBuffers,
          cachedProducts,
        }),
    );
    return transfer.call.bind(transfer);
  }
  // Historical adapter name retained for headless tests that inject a native
  // processor client. Production processing is available only through Tauri.
  if (window.pywebview?.api.invoke) return window.pywebview.api.invoke;
  throw new Error(
    "Open this interface with desktop/launch.command (Tauri). Headless browser checks require the injected native test bridge.",
  );
}
