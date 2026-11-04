import { isTauri } from "@tauri-apps/api/core";
import { emit, listen } from "@tauri-apps/api/event";
import type { Response } from "./types";

export type MapWindowStatus = {
  ready: boolean;
  calibrated: boolean;
  largeText: boolean;
  error: string | null;
  revision?: number;
};
export type MapWindowMessage =
  | { type: "ready" | "closed" | "dock" }
  | { type: "refresh"; status: MapWindowStatus }
  | {
      type: "request";
      id: string;
      command: string;
      args: Record<string, unknown>;
      read: boolean;
    }
  | { type: "response"; id: string; result: Response };

/** Native notifications contain no pixels; browser popups share their opener's bridge. */
export function mapWindowChannel(child: boolean, session: string) {
  const incoming = child ? "map-window-child" : "map-window-main";
  const outgoing = child ? "map-window-main" : "map-window-child";
  const native = isTauri();
  let partner: Window | null = child ? window.opener : null;
  return {
    send: (message: MapWindowMessage) => {
      if (native) void emit(outgoing, message);
      else
        partner?.postMessage(
          { mapWindowSession: session, target: outgoing, message },
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
          event.data?.mapWindowSession !== session ||
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
