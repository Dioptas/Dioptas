import { Button } from "./ui";
import { StatusMessage } from "./StatusMessage";
import { processingProgressText } from "./processingProgress";
import { useCallback, useEffect, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { connect } from "./bridge";
import { mapWindowChannel } from "./mapWindowChannel";
import type { BatchWindowStatus } from "./batchWindow";
import { BatchView } from "./BatchView";
import { usePlotReadout } from "./plotReadout";
import type { BatchData, BatchRun } from "./batchDomain";
import type { Invoke, Response } from "./types";
import { BatchWindowSync, batchWindowError } from "./batchWindowState";
import { ReadingFields } from "./PlotStatus";

export function DetachedBatchWindow() {
  const [batch, setBatch] = useState<BatchData | null>(null);
  const [status, setStatus] = useState<BatchWindowStatus>({
    ready: false,
    calibrated: false,
    largeText: false,
    error: null,
  });
  const [error, setError] = useState<string | null>(null);
  const readout = usePlotReadout();
  const bridge = useRef<Invoke | null>(null);
  const channel = useRef<ReturnType<typeof mapWindowChannel> | null>(null);
  const pending = useRef(
    new Map<
      string,
      { resolve: (r: Response) => void; timer: ReturnType<typeof setTimeout> }
    >(),
  );
  const rpc = useCallback(
    (
      command: string,
      args: Record<string, unknown> = {},
      read = false,
    ): Promise<Response> =>
      new Promise((resolve) => {
        const id = crypto.randomUUID();
        const timer = setTimeout(() => {
          pending.current.delete(id);
          resolve({ ok: false, error: "The main window did not respond." });
        }, 120000);
        pending.current.set(id, { resolve, timer });
        channel.current?.send({ type: "request", id, command, args, read });
      }),
    [],
  );
  const request = useCallback(
    async (command: string, args: Record<string, unknown> = {}) => {
      try {
        const r = bridge.current
          ? await bridge.current(command, args)
          : await rpc(command, args, true);
        if (!r.ok) setError(r.error ?? "Could not refresh Batch.");
        return r;
      } catch (e) {
        setError(String(e));
        return { ok: false, error: String(e) };
      }
    },
    [rpc],
  );
  useEffect(() => {
    let disposed = false;
    const transport = mapWindowChannel(
      true,
      new URLSearchParams(location.search).get("batch_window") ?? "native",
      "batch",
    );
    channel.current = transport;
    const sync = new BatchWindowSync(async () => {
      const r = await request("batch_snapshot");
      return r.ok && "batch" in r ? (r.batch ?? null) : undefined;
    }, setBatch);
    const subscription = transport.listen((message) => {
      if (message.type === "refresh") {
        if (
          !message.batchUpdate ||
          sync.receive(message.batchUpdate, message.status.ready)
        )
          setStatus(message.status);
      } else if (message.type === "response") {
        const task = pending.current.get(message.id);
        if (task) {
          clearTimeout(task.timer);
          pending.current.delete(message.id);
          task.resolve(message.result);
        }
      }
    });
    void subscription
      .then(async () => {
        if (isTauri()) bridge.current = await connect();
        if (!disposed) transport.send({ type: "ready" });
      })
      .catch((e) => setError(String(e)));
    const closing = () => transport.send({ type: "closed" });
    window.addEventListener("beforeunload", closing);
    return () => {
      disposed = true;
      sync.dispose();
      window.removeEventListener("beforeunload", closing);
      void subscription.then((stop) => stop());
      transport.close();
      for (const task of pending.current.values()) {
        clearTimeout(task.timer);
        task.resolve({ ok: false, cancelled: true });
      }
      pending.current.clear();
    };
  }, [request]);
  const run = useCallback<BatchRun>(
    async (command, args = {}) => {
      setError(null);
      const r = await rpc(command, args);
      if (!r.ok) setError(r.error ?? "Batch command failed.");
    },
    [rpc],
  );
  return (
    <div
      className="app detached-batch-app"
      data-text-size={status.largeText ? "large" : "normal"}
    >
      <BatchView
        position={status.position}
        batch={batch}
        calibrated={status.calibrated}
        ready={status.ready}
        run={run}
        request={request}
        reportPlot={readout.report}
        onDock={() => channel.current?.send({ type: "dock" })}
        onHide={() => void run("batch_hide")}
      />
      <footer className="detached-batch-footer">
        <span className="batch-reading" data-testid="batch-readout">
          {readout.reading ? (
            <ReadingFields reading={readout.reading} />
          ) : batch ? (
            `Frame ${batch.selected + 1} of ${batch.entries.length} · ${batch.entries[batch.selected]?.name}`
          ) : (
            "Load a series to inspect it in Integration."
          )}
        </span>
        {status.clicked && (
          <span
            className="batch-click-reading"
            data-testid="batch-click-readout"
          >
            Click <ReadingFields reading={status.clicked} />
          </span>
        )}
        <StatusMessage
          error={batchWindowError(error, status.error)}
          message={
            status.progress?.running
              ? processingProgressText(status.progress)
              : !status.ready
                ? "Processing…"
                : ""
          }
        />
        {status.progress?.running && (
          <Button onClick={() => run("cancel_refinement")}>
            Cancel processing
          </Button>
        )}
        {error && (
          <Button
            aria-label="Dismiss batch error"
            onClick={() => setError(null)}
          >
            ×
          </Button>
        )}
      </footer>
    </div>
  );
}
