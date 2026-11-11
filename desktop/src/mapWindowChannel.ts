import { isTauri } from "@tauri-apps/api/core";
import { emit, listen } from "@tauri-apps/api/event";
import type { Response } from "./types";

export type MapWindowStatus = {
  ready: boolean;
  calibrated: boolean;
  largeText: boolean;
  error: string | null;
  clicked?: import("./plotReadout").PlotReading | null;
  revision?: number;
  progress?: {
    running: boolean;
    current: number;
    total: number;
    label?: string;
    fps?: number;
    elapsedSeconds?: number;
  };
};
export type MapWindowMessage =
  | { type: "ready" | "dock" }
  | { type: "closed"; shuttingDown?: boolean }
  | {
      type: "refresh";
      status: MapWindowStatus;
      batchUpdate?: import("./batchWindowState").BatchWindowUpdate;
    }
  | {
      type: "request";
      id: string;
      command: string;
      args: Record<string, unknown>;
      read: boolean;
    }
  | { type: "response"; id: string; result: Response };

/** Native notifications contain no pixels; browser popups share their opener's bridge. */
export function mapWindowChannel(
  child: boolean,
  session: string,
  kind: "map" | "batch" = "map",
) {
  const incoming = child ? `${kind}-window-child` : `${kind}-window-main`;
  const outgoing = child ? `${kind}-window-main` : `${kind}-window-child`;
  const native = isTauri();
  let partner: Window | null = child ? window.opener : null;
  return {
    send: (message: MapWindowMessage) => {
      if (native) void emit(outgoing, message);
      else
        partner?.postMessage(
          { [`${kind}WindowSession`]: session, target: outgoing, message },
          location.protocol === "file:" ? "*" : location.origin,
        );
    },
    listen: async (callback: (message: MapWindowMessage) => void) => {
      if (native)
        return listen<MapWindowMessage>(incoming, (event) =>
          callback(event.payload),
        );
      const handler = (event: MessageEvent) => {
        if (
          event.data?.[`${kind}WindowSession`] !== session ||
          event.data?.target !== incoming ||
          !event.source
        )
          return;
        if (partner && !partner.closed && event.source !== partner) return;
        partner = event.source as Window;
        callback(event.data.message);
      };
      window.addEventListener("message", handler);
      return () => window.removeEventListener("message", handler);
    },
    close: () => {
      partner = null;
    },
  };
}
