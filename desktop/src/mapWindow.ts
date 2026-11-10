import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import type { IntegrationRun } from "./integration";
import type { Response } from "./types";
import { mapWindowChannel, type MapWindowStatus } from "./mapWindowChannel";

const reads = new Set([
  "map_snapshot",
  "map_display",
  "map_levels",
  "progress",
]);
const edits = new Set(["map_select", "map_layer", "map_export"]);

export function useMapWindow({
  run,
  request,
  status,
  onOpen,
  onDock,
  onError,
}: {
  run: IntegrationRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  status: MapWindowStatus;
  onOpen: () => void;
  onDock: () => void;
  onError: (error: string) => void;
}) {
  const [detached, setDetached] = useState(false);
  const [session] = useState(() => crypto.randomUUID());
  const latest = useRef({ run, request, status, onOpen, onDock, onError });
  latest.current = { run, request, status, onOpen, onDock, onError };
  const transport = useRef<ReturnType<typeof mapWindowChannel> | null>(null);
  const popup = useRef<Window | null>(null);
  const opening = useRef(false);
  const dock = async () => {
    try {
      if (isTauri()) await invoke("close_map_window");
      else popup.current?.close();
      setDetached(false);
      latest.current.onDock();
    } catch (error) {
      latest.current.onError(String(error));
    }
  };
  useEffect(() => {
    const channel = mapWindowChannel(false, session);
    transport.current = channel;
    const subscription = channel.listen(async (message) => {
      if (message.type === "ready") {
        setDetached(true);
        channel.send({ type: "refresh", status: latest.current.status });
      } else if (message.type === "closed") {
        setDetached(false);
      } else if (message.type === "dock") {
        void dock();
      } else if (message.type === "request") {
        const { id, command, args, read } = message;
        let result: Response = {
          ok: false,
          error: "The main window is busy. Try again when processing finishes.",
        };
        try {
          if (read && reads.has(command)) {
            result = (await latest.current.request(command, args)) ?? result;
          } else if (!read && edits.has(command)) {
            // All changes go through the main window's existing ordered queue.
            await latest.current.run(
              command,
              args,
              command === "map_select" ? "" : "Processing map…",
              (response) => {
                result = {
                  ok: response.ok,
                  error: response.error,
                  cancelled: response.cancelled,
                };
              },
            );
          } else
            result = {
              ok: false,
              error: "This command is unavailable in the map window.",
            };
        } catch (error) {
          result = { ok: false, error: String(error) };
        }
        channel.send({ type: "response", id, result });
        if (!read)
          channel.send({ type: "refresh", status: latest.current.status });
      }
    });
    const timer = isTauri()
      ? undefined
      : setInterval(() => {
          if (popup.current?.closed) {
            popup.current = null;
            setDetached(false);
          }
        }, 400);
    const closing = () => popup.current?.close();
    window.addEventListener("beforeunload", closing);
    return () => {
      clearInterval(timer);
      void subscription.then((stop) => stop());
      channel.close();
      transport.current = null;
      window.removeEventListener("beforeunload", closing);
    };
  }, [session]);
  useEffect(() => {
    if (detached) transport.current?.send({ type: "refresh", status });
  }, [
    detached,
    status.ready,
    status.calibrated,
    status.largeText,
    status.error,
    status.revision,
    status.progress,
  ]);
  const open = async () => {
    if (opening.current) return;
    opening.current = true;
    try {
      if (isTauri()) await invoke("open_map_window");
      else {
        if (!popup.current || popup.current.closed) {
          const url = new URL(location.href);
          url.searchParams.set("map_window", session);
          popup.current = window.open(
            url,
            `dioptas-map-${session}`,
            "popup,width=800,height=760",
          );
          if (!popup.current)
            throw Error("Allow pop-up windows to detach the map.");
        } else popup.current.focus();
      }
      setDetached(true);
      latest.current.onOpen();
    } catch (error) {
      latest.current.onError(String(error));
    } finally {
      opening.current = false;
    }
  };
  return { detached, open: () => void open(), dock: () => void dock() };
}
