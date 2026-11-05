import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { mapWindowChannel, type MapWindowStatus } from "./mapWindowChannel";
import type { IntegrationRun } from "./integration";
import type { Response } from "./types";

export interface BatchWindowStatus extends MapWindowStatus {
  progress?: {
    running: boolean;
    current: number;
    total: number;
    label?: string;
  };
}
const reads = new Set(["batch_snapshot", "batch_levels"]);
const edits = new Set([
  "batch_load",
  "batch_load_data",
  "batch_folder_step",
  "batch_unit",
  "batch_normalization_settings",
  "batch_folder",
  "batch_open",
  "batch_select",
  "batch_normalize",
  "integration_save_batch",
]);
export function useBatchWindow({
  run,
  request,
  status,
  onDock,
  onOpen,
  onError,
  cancel,
}: {
  run: IntegrationRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  status: BatchWindowStatus;
  onDock: () => void;
  onOpen: () => void;
  onError: (error: string) => void;
  cancel: () => Promise<unknown> | undefined;
}) {
  const [detached, setDetached] = useState(false);
  const [session] = useState(() => crypto.randomUUID());
  const latest = useRef({
    run,
    request,
    status,
    onDock,
    onOpen,
    onError,
    cancel,
  });
  latest.current = { run, request, status, onDock, onOpen, onError, cancel };
  const transport = useRef<ReturnType<typeof mapWindowChannel> | null>(null);
  const popup = useRef<Window | null>(null),
    opening = useRef(false);
  const hide = async () => {
    if (isTauri()) await invoke("close_batch_window");
    else popup.current?.close();
    setDetached(false);
  };
  const dock = async () => {
    await hide();
    latest.current.onDock();
  };
  useEffect(() => {
    const channel = mapWindowChannel(false, session, "batch");
    transport.current = channel;
    const subscription = channel.listen(async (message) => {
      if (message.type === "ready") {
        setDetached(true);
        channel.send({ type: "refresh", status: latest.current.status });
      } else if (message.type === "closed") setDetached(false);
      else if (message.type === "dock") {
        try {
          await dock();
        } catch (e) {
          latest.current.onError(String(e));
        }
      } else if (message.type === "request") {
        const { id, command, args, read } = message;
        let result: Response = {
          ok: false,
          error: "The main window is busy. Try again when processing finishes.",
        };
        try {
          if (read && reads.has(command))
            result = (await latest.current.request(command, args)) ?? result;
          else if (!read && command === "cancel_refinement") {
            await latest.current.cancel();
            result = { ok: true };
          } else if (!read && command === "batch_hide") {
            await hide();
            result = { ok: true };
          } else if (!read && edits.has(command)) {
            await latest.current.run(
              command,
              args,
              command === "batch_select"
                ? "Loading batch frame…"
                : "Processing batch…",
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
              error: "This command is unavailable in the Batch window.",
            };
        } catch (e) {
          result = { ok: false, error: String(e) };
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
      if (isTauri()) await invoke("open_batch_window");
      else {
        if (!popup.current || popup.current.closed) {
          const url = new URL(location.href);
          url.searchParams.set("batch_window", session);
          popup.current = window.open(
            url,
            `dioptas-batch-${session}`,
            "popup,width=900,height=600",
          );
          if (!popup.current)
            throw Error(
              "Allow pop-up windows to open Batch, or use the dock below the image.",
            );
        } else popup.current.focus();
      }
      setDetached(true);
      latest.current.onOpen();
    } catch (e) {
      latest.current.onDock();
      latest.current.onError(String(e));
    } finally {
      opening.current = false;
    }
  };
  return { detached, open: () => void open(), dock: () => void dock() };
}
