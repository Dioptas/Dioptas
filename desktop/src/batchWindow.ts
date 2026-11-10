import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { mapWindowChannel, type MapWindowStatus } from "./mapWindowChannel";
import type { IntegrationRun } from "./integration";
import { batchWindowUpdate, BATCH_BUSY_MESSAGE } from "./batchWindowState";
import type { BatchData } from "./batchDomain";
import type { Response } from "./types";

export interface BatchWindowStatus extends MapWindowStatus {
  position?: import("./linkedPosition").PatternPosition;
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
  "batch_waterfall",
  "batch_normalize",
  "batch_background_settings",
  "batch_background_extract",
  "batch_background_display",
  "integration_save_batch",
]);
export function useBatchWindow({
  batch,
  run,
  request,
  status,
  onDock,
  onOpen,
  onClose,
  onError,
  cancel,
}: {
  batch: BatchData | null;
  run: IntegrationRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  status: BatchWindowStatus;
  onDock: () => void;
  onOpen: () => void;
  onClose: () => void;
  onError: (error: string) => void;
  cancel: () => Promise<unknown> | undefined;
}) {
  const [detached, setDetached] = useState(false);
  const [session] = useState(() => crypto.randomUUID());
  const latest = useRef({
    batch,
    run,
    request,
    status,
    onDock,
    onOpen,
    onClose,
    onError,
    cancel,
  });
  latest.current = {
    batch,
    run,
    request,
    status,
    onDock,
    onOpen,
    onClose,
    onError,
    cancel,
  };
  const transport = useRef<ReturnType<typeof mapWindowChannel> | null>(null);
  const published = useRef<{
    batch: BatchData | null | undefined;
    base: number;
    sequence: number;
  }>({ batch: undefined, base: 0, sequence: 0 });
  const publish = (initial = false) => {
    const { batch, status } = latest.current;
    const update = batchWindowUpdate(
      published.current.batch,
      batch,
      published.current,
      initial,
    );
    published.current = { batch, base: update.base, sequence: update.sequence };
    transport.current?.send({ type: "refresh", status, batchUpdate: update });
  };
  const popup = useRef<Window | null>(null),
    opening = useRef(false);
  const shuttingDown = useRef(false),
    internalClose = useRef(false);
  const hide = async (rememberClosed = true) => {
    internalClose.current = true;
    if (isTauri()) await invoke("close_batch_window");
    else popup.current?.close();
    setDetached(false);
    if (rememberClosed) latest.current.onClose();
  };
  const dock = async () => {
    await hide(false);
    latest.current.onDock();
  };
  useEffect(() => {
    const channel = mapWindowChannel(false, session, "batch");
    transport.current = channel;
    const subscription = channel.listen(async (message) => {
      if (message.type === "ready") {
        setDetached(true);
        publish(true);
      } else if (message.type === "closed") {
        setDetached(false);
        if (
          !shuttingDown.current &&
          !internalClose.current &&
          (!isTauri() || message.shuttingDown === false)
        )
          latest.current.onClose();
      } else if (message.type === "dock") {
        try {
          await dock();
        } catch (e) {
          latest.current.onError(String(e));
        }
      } else if (message.type === "request") {
        const { id, command, args, read } = message;
        let result: Response = {
          ok: false,
          error: BATCH_BUSY_MESSAGE,
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
        // The committed status effect publishes edits once React has applied
        // them. Sending here can announce the previous revision and fetch the
        // same snapshot again when the committed revision arrives.
      }
    });
    const timer = isTauri()
      ? undefined
      : setInterval(() => {
          if (popup.current?.closed) {
            popup.current = null;
            setDetached(false);
            if (!shuttingDown.current && !internalClose.current)
              latest.current.onClose();
          }
        }, 400);
    const closing = () => {
      shuttingDown.current = true;
      popup.current?.close();
    };
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
    if (detached) publish();
  }, [
    batch,
    detached,
    status.ready,
    status.calibrated,
    status.largeText,
    status.error,
    status.revision,
    status.position?.x,
    status.position?.unit,
    status.progress,
  ]);
  const open = async () => {
    if (opening.current) return;
    opening.current = true;
    internalClose.current = false;
    // A child can become ready and dock/close before native open returns.
    // Record the transition first so a late completion cannot undo that action.
    setDetached(true);
    latest.current.onOpen();
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
    } catch (e) {
      setDetached(false);
      latest.current.onDock();
      latest.current.onError(String(e));
    } finally {
      opening.current = false;
    }
  };
  return { detached, open: () => void open(), dock: () => void dock() };
}
