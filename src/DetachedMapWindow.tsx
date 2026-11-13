import { DockWindowIcon } from "./WindowIcons";
import { Button } from "./ui";
import { StatusMessage } from "./StatusMessage";
import { ReadingFields } from "./PlotStatus";
import { processingProgressText } from "./processingProgress";
import { useCallback, useEffect, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { connect } from "./bridge";
import { mapWindowChannel, type MapWindowStatus } from "./mapWindowChannel";
import { ScanMapPanel } from "./ScanMapPanel";
import { useMapPreference } from "./mapPreferences";
import { usePlotReadout } from "./plotReadout";
import type { Invoke, Response } from "./types";
import type {
  CommandInvocation,
  CheckedInvocation,
  CommandRequestReader,
} from "./commandContracts";
import { forwardInvoke } from "./commandDispatch";
import { WindowCommandRpc, type WindowRunInvocation } from "./windowCommandRpc";
import type { MapData, MapRun } from "./mapDomain";
import "./map.css";

export function DetachedMapWindow() {
  const [map, setMap] = useState<MapData | null>(null);
  const [progressPreview, setProgressPreview] =
    useState<NonNullable<Response["progress"]>["mapPreview"]>();
  const [status, setStatus] = useState<MapWindowStatus>({
    ready: false,
    calibrated: false,
    largeText: false,
    error: null,
  });
  const [error, setError] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [reintegrate] = useMapPreference("reintegrate-selected", true);
  const readout = usePlotReadout();
  const bridge = useRef<Invoke | null>(null);
  const channel = useRef<ReturnType<typeof mapWindowChannel> | null>(null);
  const [rpc] = useState(
    () => new WindowCommandRpc((message) => channel.current?.send(message)),
  );
  const request = useCallback<CommandRequestReader>(
    async <const A extends CommandInvocation>(
      ...call: CheckedInvocation<A>
    ) => {
      try {
        const response = bridge.current
          ? await forwardInvoke(bridge.current, call)
          : await forwardInvoke(rpc.read, call);
        setReadError(
          response.ok ? null : (response.error ?? "Could not update the map."),
        );
        return response;
      } catch (error) {
        setReadError(String(error));
        return undefined;
      }
    },
    [rpc],
  );
  useEffect(() => {
    let disposed = false,
      refreshing = false,
      queued = false;
    const transport = mapWindowChannel(
      true,
      new URLSearchParams(location.search).get("map_window") ?? "native",
    );
    channel.current = transport;
    const refresh = async () => {
      queued = true;
      if (refreshing) return;
      refreshing = true;
      try {
        while (queued && !disposed) {
          queued = false;
          const result = await request("map_snapshot");
          if (!disposed && result?.ok && "map" in result)
            setMap(result.map ?? null);
        }
      } catch (error) {
        if (!disposed) setError(String(error));
      } finally {
        refreshing = false;
      }
    };
    const subscription = transport.listen((message) => {
      if (message.type === "refresh") {
        setStatus(message.status);
        if (message.status.ready) {
          void refresh();
        }
      } else if (message.type === "response") {
        rpc.receive(message.id, message.result);
      }
    });
    void subscription
      .then(async () => {
        if (isTauri()) bridge.current = await connect();
        if (!disposed) transport.send({ type: "ready" });
      })
      .catch((error) => setError(String(error)));
    const closing = () => transport.send({ type: "closed" });
    window.addEventListener("beforeunload", closing);
    return () => {
      disposed = true;
      window.removeEventListener("beforeunload", closing);
      void subscription.then((stop) => stop());
      transport.close();
      rpc.close();
    };
  }, [request]);
  const run = useCallback<MapRun>(
    async <const A extends WindowRunInvocation>(...call: A) => {
      setError(null);
      const response = await rpc.editInvocation(call);
      if (!response.ok) setError(response.error ?? "Map command failed.");
    },
    [rpc],
  );
  useEffect(() => {
    setProgressPreview(undefined);
    if (status.ready) return;
    let active = true;
    let polling = false;
    const timer = setInterval(() => {
      if (polling) return;
      polling = true;
      void request("progress")
        .then((result) => {
          if (active && result?.ok)
            setProgressPreview(result.progress?.mapPreview);
        })
        .finally(() => {
          polling = false;
        });
    }, 150);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [status.ready, request]);
  return (
    <div
      className="app detached-map-app"
      data-text-size={status.largeText ? "large" : "normal"}
    >
      <div className="detached-map-content">
        <ScanMapPanel
          map={map}
          progressPreview={progressPreview}
          allowLoad={false}
          calibrated={status.calibrated}
          ready={status.ready}
          run={run}
          request={request}
          reintegrate={reintegrate && status.calibrated && !map?.normalized}
          reportPlot={readout.report}
          actions={
            <Button
              className="plot-tool-button map-icon-button"
              aria-label="Dock map"
              onClick={() => channel.current?.send({ type: "dock" })}
              title="Return the map to Map mode in the main window"
            >
              <DockWindowIcon size={16} />
            </Button>
          }
        />
      </div>
      <footer className="detached-map-footer">
        <span data-testid="map-readout">
          {readout.reading?.text ??
            "Select a map cell to inspect it in the main window."}
        </span>
        {status.clicked && (
          <span className="map-click-reading" data-testid="map-click-readout">
            Click <ReadingFields reading={status.clicked} />
          </span>
        )}
        <StatusMessage
          error={error || readError || status.error || null}
          message={
            status.progress?.running
              ? processingProgressText(status.progress)
              : !status.ready
                ? "Processing…"
                : ""
          }
        />
      </footer>
    </div>
  );
}
