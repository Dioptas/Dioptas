import { useCallback, useEffect, useRef, useState } from "react";
import { PanelLeftClose } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { connect } from "./bridge";
import { mapWindowChannel, type MapWindowStatus } from "./mapWindowChannel";
import { ScanMapPanel } from "./ScanMapPanel";
import { useMapPreference } from "./mapPreferences";
import { usePlotReadout } from "./plotReadout";
import type { Invoke, Response } from "./types";
import type { MapData, MapRun } from "./mapDomain";
import "./map.css";

export function DetachedMapWindow() {
  const [map, setMap] = useState<MapData | null>(null);
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
  const pending = useRef(
    new Map<
      string,
      {
        resolve: (response: Response) => void;
        timer: ReturnType<typeof setTimeout>;
      }
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
        const response = bridge.current
          ? await bridge.current(command, args)
          : await rpc(command, args, true);
        setReadError(
          response.ok ? null : (response.error ?? "Could not update the map."),
        );
        return response;
      } catch (error) {
        setReadError(String(error));
        return { ok: false, error: String(error) };
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
          if (!disposed && result.ok && "map" in result)
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
      .catch((error) => setError(String(error)));
    const closing = () => transport.send({ type: "closed" });
    window.addEventListener("beforeunload", closing);
    return () => {
      disposed = true;
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
  const run = useCallback<MapRun>(
    async (command, args = {}) => {
      setError(null);
      const response = await rpc(command, args);
      if (!response.ok) setError(response.error ?? "Map command failed.");
    },
    [rpc],
  );
  return (
    <div
      className="app detached-map-app"
      data-text-size={status.largeText ? "large" : "normal"}
    >
      <div className="detached-map-content">
        <ScanMapPanel
          map={map}
          allowLoad={false}
          calibrated={status.calibrated}
          ready={status.ready}
          run={run}
          request={request}
          reintegrate={reintegrate && status.calibrated && !map?.normalized}
          reportPlot={readout.report}
          actions={
            <button
              className="plot-tool-button map-icon-button"
              aria-label="Dock map"
              onClick={() => channel.current?.send({ type: "dock" })}
              title="Return the map to Map mode in the main window"
            >
              <PanelLeftClose size={16} />
            </button>
          }
        />
      </div>
      <footer className="detached-map-footer">
        <span>
          {readout.reading?.text ??
            "Select a map cell to inspect it in the main window."}
        </span>
        <span role={error || readError || status.error ? "alert" : undefined}>
          {error ||
            readError ||
            status.error ||
            (!status.ready ? "Processing…" : "")}
        </span>
      </footer>
    </div>
  );
}
