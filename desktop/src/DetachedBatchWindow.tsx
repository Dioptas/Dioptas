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
import type { BatchData } from "./batchDomain";
import type { Invoke } from "./types";
import type {
  CommandInvocation,
  CommandRequestReader,
} from "./commandContracts";
import { WindowCommandRpc, type WindowRun, type WindowRunInvocation } from "./windowCommandRpc";
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
  const [rpc] = useState(
    () => new WindowCommandRpc((message) => channel.current?.send(message)),
  );
  const request = useCallback<CommandRequestReader>(
    async <const A extends CommandInvocation>(...call: A) => {
      try {
        const r = bridge.current
          ? await bridge.current<A>(...call)
          : await rpc.read<A>(...call);
        if (!r.ok) setError(r.error ?? "Could not refresh Batch.");
        return r;
      } catch (e) {
        setError(String(e));
        return undefined;
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
      return r?.ok && "batch" in r ? (r.batch ?? null) : undefined;
    }, setBatch);
    const subscription = transport.listen((message) => {
      if (message.type === "refresh") {
        if (
          !message.batchUpdate ||
          sync.receive(message.batchUpdate, message.status.ready)
        )
          setStatus(message.status);
      } else if (message.type === "response") {
        rpc.receive(message.id, message.result);
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
      rpc.close();
    };
  }, [request]);
  const run = useCallback<WindowRun>(
    async <const A extends WindowRunInvocation>(...call: A) => {
      setError(null);
      const r = await rpc.edit<A>(...call);
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
