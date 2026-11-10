import { useEffect, useRef, useState, type ComponentProps } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { PanelLeftClose } from "lucide-react";
import { Button } from "./ui";
import { RasterView, type RasterExport } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import { ReadingFields } from "./PlotStatus";
import { StatusMessage } from "./StatusMessage";
import { RasterTransfer } from "./rasterTransfer";
import {
  detectorWindowChannel,
  type DetectorWindowStatus,
} from "./detectorWindowChannel";
import type { DetectorPresentation } from "./detectorSnapshot";
import type { PlotRange } from "./usePlotNavigation";
import "./sharedFooter.css";
import "./detector_window.css";

export function DetachedDetectorWindow() {
  const [presentation, setPresentation] = useState<DetectorPresentation | null>(
    null,
  );
  const [status, setStatus] = useState<DetectorWindowStatus>({
    largeText: false,
    reading: null,
    clicked: null,
    message: "",
    error: null,
  });
  const [error, setError] = useState<string | null>(null);
  const channel = useRef<ReturnType<typeof detectorWindowChannel> | null>(null);
  const current = useRef(presentation);
  current.current = presentation;
  const exporter = useRef<RasterExport>(null);
  const viewport = useRef<{ key: string; range: PlotRange | null }>({
    key: "",
    range: null,
  });
  const pending = useRef(
    new Map<
      string,
      {
        resolve: () => void;
        reject: (e: Error) => void;
        timer: ReturnType<typeof setTimeout>;
      }
    >(),
  );
  const event = (callback: string, args: unknown[]) =>
    new Promise<void>((resolve, reject) => {
      if (!current.current) {
        resolve();
        return;
      }
      const id = crypto.randomUUID();
      const timer = setTimeout(() => {
        pending.current.delete(id);
        reject(Error("The main window did not respond."));
      }, 120000);
      pending.current.set(id, { resolve, reject, timer });
      channel.current?.send({
        type: "event",
        identity: current.current.identity,
        callback,
        args,
        id,
      });
    }).catch((e) => {
      setError(String(e));
    });
  useEffect(() => {
    let disposed = false,
      refreshing = false,
      queued = false;
    const transport = detectorWindowChannel(
      true,
      new URLSearchParams(location.search).get("detector_window") ?? "native",
    );
    channel.current = transport;
    const transfer = new RasterTransfer((_, __, cachedBuffers) =>
      invoke<ArrayBuffer>("detector_snapshot", { cachedBuffers }),
    );
    const accept = (next: DetectorPresentation | null) => {
      if (disposed) return;
      if (next?.viewport && viewport.current.key !== next.viewport.key)
        viewport.current = {
          key: next.viewport.key,
          range: next.viewport.range as PlotRange | null,
        };
      if (current.current?.identity !== next?.identity) setError(null);
      current.current = next;
      setPresentation(next);
    };
    const refresh = async () => {
      queued = true;
      if (refreshing) return;
      refreshing = true;
      try {
        while (queued && !disposed) {
          queued = false;
          const result = await transfer.call("detector_snapshot");
          accept(
            (result as unknown as { presentation: DetectorPresentation | null })
              .presentation,
          );
        }
      } catch (error) {
        if (!disposed) setError(String(error));
      } finally {
        refreshing = false;
      }
    };
    const subscription = transport.listen((message) => {
      if (message.type === "owner") transport.send({ type: "ready" });
      else if (message.type === "refresh") setStatus(message.status);
      else if (message.type === "snapshot") void refresh();
      else if (message.type === "presentation") {
        const hydrate = (value: unknown): unknown => {
          if (Array.isArray(value)) return value.map(hydrate);
          if (!value || typeof value !== "object") return value;
          const obj = value as Record<string, unknown>;
          if (typeof obj.bufferId === "string")
            return { ...obj, data: message.buffers.get(obj.bufferId) };
          return Object.fromEntries(
            Object.entries(obj).map(([k, v]) => [k, hydrate(v)]),
          );
        };
        accept(hydrate(message.presentation) as DetectorPresentation | null);
      } else if (message.type === "response") {
        const task = pending.current.get(message.id);
        if (task) {
          clearTimeout(task.timer);
          pending.current.delete(message.id);
          message.error ? task.reject(Error(message.error)) : task.resolve();
        }
      } else if (message.type === "export") {
        try {
          if (
            !exporter.current ||
            message.identity !== current.current?.identity
          )
            throw Error("The detector changed before its image was exported.");
          transport.send({
            type: "exported",
            id: message.id,
            png: exporter.current.png(),
          });
        } catch (error) {
          transport.send({
            type: "exported",
            id: message.id,
            error: String(error),
          });
        }
      }
    });
    void subscription
      .then(() => {
        if (!disposed) transport.send({ type: "ready" });
      })
      .catch((e) => setError(String(e)));
    const closing = () => transport.send({ type: "closed" });
    window.addEventListener("beforeunload", closing);
    const key = (e: KeyboardEvent) => {
      if (
        e.defaultPrevented ||
        e.ctrlKey ||
        e.metaKey ||
        !(e.target instanceof Element) ||
        e.target.closest(
          'input,textarea,select,button,[role="dialog"],[role="menu"]',
        )
      )
        return;
      if (current.current && ["Escape", "Enter", "q", "w"].includes(e.key)) {
        e.preventDefault();
        transport.send({
          type: "key",
          identity: current.current.identity,
          key: e.key,
        });
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      disposed = true;
      window.removeEventListener("beforeunload", closing);
      window.removeEventListener("keydown", key);
      void subscription.then((stop) => stop());
      transport.close();
      for (const task of pending.current.values()) {
        clearTimeout(task.timer);
        task.resolve();
      }
      pending.current.clear();
    };
  }, []);
  const props = (input: Record<string, unknown>) =>
    Object.fromEntries(
      Object.entries(input).map(([key, value]) => {
        if (value && typeof value === "object" && "callback" in value)
          return [
            key,
            (...args: unknown[]) => event(String(value.callback), args),
          ];
        return [key, value];
      }),
    );
  return (
    <div
      className="app detached-detector-app"
      data-text-size={status.largeText ? "large" : "normal"}
    >
      <div className="detached-detector-content">
        {presentation?.label && (
          <div className="detached-detector-heading">
            <span>{presentation.label}</span>
            {presentation.back && (
              <Button
                aria-label="Back from correction preview"
                onClick={() => void event("back", [])}
              >
                Back
              </Button>
            )}
          </div>
        )}
        {presentation ? (
          <div className="detector-workspace">
            <RasterView
              {...(props(presentation.raster) as ComponentProps<
                typeof RasterView
              >)}
              exportRef={exporter}
              viewport={
                presentation.viewport
                  ? {
                      key: presentation.viewport.key,
                      read: () => viewport.current.range,
                      write: (range) => {
                        viewport.current.range = range;
                        void event("viewport", [range]);
                      },
                    }
                  : undefined
              }
            />
            <ImageIntensity
              key={presentation.intensityKey}
              {...(props(presentation.intensity) as ComponentProps<
                typeof ImageIntensity
              >)}
            />
          </div>
        ) : (
          <div className="empty-view">
            <p>No detector image in the current workspace.</p>
          </div>
        )}
        <Button
          className="plot-tool-button detector-window-action"
          aria-label="Dock detector image"
          title="Return the detector image to the main window"
          onClick={() => channel.current?.send({ type: "dock" })}
        >
          <PanelLeftClose size={16} />
        </Button>
      </div>
      <footer className="detached-detector-footer">
        <span data-testid="detector-readout" title={status.reading?.text}>
          {status.reading ? (
            <ReadingFields reading={status.reading} />
          ) : (
            "Move the pointer to inspect the detector."
          )}
        </span>
        {status.clicked && (
          <span
            className="detector-click-reading"
            data-testid="detector-click-readout"
          >
            Click <ReadingFields reading={status.clicked} />
          </span>
        )}
        <span className="detector-message">
          <StatusMessage
            error={error || status.error}
            message={status.message}
          />
        </span>
      </footer>
    </div>
  );
}
