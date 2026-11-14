import { useEffect, useRef } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

/** Development swaps the worker without remounting the workspace or its drafts. */
export function useBackendReload(
  onStatus: (message: string, restored: boolean, failed: boolean) => void,
) {
  const callback = useRef(onStatus);
  callback.current = onStatus;
  useEffect(() => {
    if (!import.meta.env.DEV || !isTauri()) return;
    let disposed = false;
    let stop: (() => void) | undefined;
    void listen<{ phase: string; message: string }>(
      "dioptas-backend-update",
      ({ payload }) => {
        if (!disposed)
          callback.current(
            payload.message,
            payload.phase === "ready",
            payload.phase === "error",
          );
      },
    ).then((unlisten) => {
      if (disposed) unlisten();
      else stop = unlisten;
    });
    return () => {
      disposed = true;
      stop?.();
    };
  }, []);
}
