import { isTauri } from "@tauri-apps/api/core";
import { emitTo, listen } from "@tauri-apps/api/event";
import type { DetectorPresentation } from "./detectorSnapshot";
import type { PlotReading } from "./plotReadout";

export type DetectorWindowStatus = {
  largeText: boolean;
  reading: PlotReading | null;
  clicked: PlotReading | null;
  message: string;
  error: string | null;
};
export type DetectorWindowMessage =
  | { type: "ready" | "dock" | "closed" | "snapshot" | "owner" }
  | { type: "refresh"; status: DetectorWindowStatus }
  | {
      type: "presentation";
      presentation: DetectorPresentation | null;
      buffers: Map<string, unknown>;
    }
  | {
      type: "event";
      identity: string;
      callback: string;
      args: unknown[];
      id: string;
    }
  | { type: "response"; id: string; error?: string }
  | { type: "key"; identity: string; key: string }
  | { type: "export"; id: string; identity: string }
  | { type: "exported"; id: string; png?: string; error?: string };

/** Live native snapshots contain no pixels in events. The explicit PNG save
 * response uses the existing data-URL export format. Browser tests use structured clone. */
export function detectorWindowChannel(child: boolean, session: string) {
  const incoming = child ? "detector-window-child" : "detector-window-main";
  const outgoing = child ? "detector-window-main" : "detector-window-child";
  let partner: Window | null = child ? window.opener : null;
  return {
    send(message: DetectorWindowMessage) {
      if (isTauri())
        void emitTo(child ? "main" : "detector-window", outgoing, message);
      else
        partner?.postMessage(
          { detectorWindowSession: session, target: outgoing, message },
          location.protocol === "file:" ? "*" : location.origin,
        );
    },
    async listen(callback: (message: DetectorWindowMessage) => void) {
      if (isTauri())
        return listen<DetectorWindowMessage>(incoming, (e) =>
          callback(e.payload),
        );
      const handler = (event: MessageEvent) => {
        if (
          event.data?.detectorWindowSession !== session ||
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
    close() {
      partner = null;
    },
  };
}
