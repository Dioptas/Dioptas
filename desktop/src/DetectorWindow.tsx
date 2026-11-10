import {
  Children,
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { ExternalLink } from "lucide-react";
import { Button } from "./ui";
import {
  detectorBufferId,
  detectorPacket,
  detectorPresentation,
  detectorTools,
} from "./detectorSnapshot";
import {
  detectorWindowChannel,
  type DetectorWindowStatus,
} from "./detectorWindowChannel";
import type { Raster, Response } from "./types";
import "./detector_window.css";

type Surface = ReturnType<typeof detectorPresentation>;
type Owner = ReturnType<typeof useDetectorWindow>;
const DetectorWindowContext = createContext<Owner | null>(null);
export const DetectorWindowProvider = DetectorWindowContext.Provider;
export const useDetectorDetached = () =>
  useContext(DetectorWindowContext)?.detached ?? false;

export function useDetectorWindow(
  status: DetectorWindowStatus,
  context: string,
  onError: (error: string) => void,
  displayKey = context,
) {
  const [detached, setDetached] = useState(false);
  const [session] = useState(() => crypto.randomUUID());
  const channel = useRef<ReturnType<typeof detectorWindowChannel> | null>(null);
  const popup = useRef<Window | null>(null);
  const opening = useRef(false);
  const latest = useRef({ status, context, onError });
  latest.current = { status, context, onError };
  const surface = useRef<Surface | null>(null);
  const surfaces = useRef(
    new Map<object, { value: Surface; priority: number }>(),
  );
  const published = useRef("");
  const accessories = useRef<ReturnType<typeof detectorTools> | null>(null);
  const active = useRef(false);
  active.current = detached;
  const publishing = useRef(false),
    queued = useRef(false);
  const known = useRef(new Set<string>());
  const exports = useRef(
    new Map<
      string,
      {
        resolve: (png: string) => void;
        reject: (e: Error) => void;
        timer: ReturnType<typeof setTimeout>;
        identity: string;
      }
    >(),
  );
  const publish = async () => {
    queued.current = true;
    if (publishing.current || !active.current) return;
    publishing.current = true;
    try {
      while (queued.current && active.current) {
        queued.current = false;
        const value = surface.current;
        if (isTauri()) {
          const retained = await invoke<string[]>(
            "publish_detector_snapshot",
            detectorPacket(
              { ok: true, presentation: value?.presentation ?? null },
              value?.buffers ?? new Map(),
              known.current,
            ),
          );
          known.current = active.current ? new Set(retained) : new Set();
          if (active.current) channel.current?.send({ type: "snapshot" });
        } else
          channel.current?.send({
            type: "presentation",
            presentation: value?.presentation ?? null,
            buffers: value?.buffers ?? new Map(),
          });
      }
    } catch (error) {
      latest.current.onError(String(error));
    } finally {
      publishing.current = false;
    }
  };
  const compose = () => {
    const selected =
      [...surfaces.current.values()]
        .sort((a, b) => a.priority - b.priority)
        .at(-1)?.value ?? null;
    const tools = accessories.current;
    surface.current = selected
      ? {
          ...selected,
          presentation: {
            ...selected.presentation,
            controls: tools?.controls,
            profile: tools?.profile,
          },
          callbacks: new Map([
            ...selected.callbacks,
            ...(tools?.callbacks ?? []),
          ]),
        }
      : null;
    const signature = JSON.stringify(surface.current?.presentation ?? null);
    if (signature !== published.current) {
      published.current = signature;
      void publish();
    }
  };
  // The surface remains owned by its original mode (including mask drafts).
  const present = (token: object, value: Surface | null, priority = 0) => {
    if (value) surfaces.current.set(token, { value, priority });
    else surfaces.current.delete(token);
    compose();
  };
  const dock = async () => {
    try {
      if (isTauri()) await invoke("close_detector_window");
      else popup.current?.close();
      setDetached(false);
    } catch (error) {
      latest.current.onError(String(error));
    }
  };
  useEffect(() => {
    const transport = detectorWindowChannel(false, session);
    channel.current = transport;
    const subscription = transport.listen(async (message) => {
      if (message.type === "ready") {
        setDetached(true);
        active.current = true;
        transport.send({ type: "refresh", status: latest.current.status });
        void publish();
      } else if (message.type === "closed") {
        active.current = false;
        known.current.clear();
        setDetached(false);
        for (const task of exports.current.values()) {
          clearTimeout(task.timer);
          task.reject(
            Error("The detector window closed before its image was exported."),
          );
        }
        exports.current.clear();
      } else if (message.type === "dock") void dock();
      else if (message.type === "exported") {
        const pending = exports.current.get(message.id);
        if (pending) {
          clearTimeout(pending.timer);
          exports.current.delete(message.id);
          if (pending.identity !== surface.current?.presentation.identity)
            pending.reject(
              Error(
                "The detector changed before its image was exported. Try again with the current image.",
              ),
            );
          else if (message.png) pending.resolve(message.png);
          else
            pending.reject(
              Error(message.error ?? "Could not export the detector image."),
            );
        }
      } else if (message.type === "event" || message.type === "key") {
        // Reject actions captured against another source/configuration/geometry,
        // mode or tool. Never apply an old detached click to new scientific state.
        if (
          !surface.current ||
          surface.current.presentation.identity !== message.identity
        ) {
          if (message.type === "event")
            transport.send({
              type: "response",
              id: message.id,
              error: "The detector changed. Try again with the current image.",
            });
          return;
        }
        if (message.type === "key") {
          if (["Escape", "Enter", "q", "w"].includes(message.key))
            window.dispatchEvent(
              new KeyboardEvent("keydown", {
                key: message.key,
                bubbles: true,
                cancelable: true,
              }),
            );
        } else {
          try {
            const callback = surface.current.callbacks.get(message.callback);
            if (!callback)
              throw Error("This detector interaction is no longer available.");
            const result = await callback(...message.args);
            transport.send({ type: "response", id: message.id, result });
          } catch (error) {
            transport.send({
              type: "response",
              id: message.id,
              error: String(error),
            });
          }
        }
      }
    });
    // A live frontend reload reconnects an already existing native companion.
    void subscription
      .then(() => transport.send({ type: "owner" }))
      .catch((error) => latest.current.onError(String(error)));
    const poll = isTauri()
      ? undefined
      : setInterval(() => {
          if (popup.current?.closed) {
            popup.current = null;
            setDetached(false);
          }
        }, 250);
    const closing = () => popup.current?.close();
    window.addEventListener("beforeunload", closing);
    return () => {
      clearInterval(poll);
      void subscription.then((stop) => stop());
      transport.close();
      window.removeEventListener("beforeunload", closing);
      for (const task of exports.current.values()) {
        clearTimeout(task.timer);
        task.reject(Error("The detector window closed."));
      }
      exports.current.clear();
    };
  }, [session]);
  useEffect(() => {
    if (detached) channel.current?.send({ type: "refresh", status });
  }, [detached, status]);
  useEffect(() => {
    if (detached) void publish();
  }, [detached]);
  const open = async () => {
    if (opening.current) return;
    opening.current = true;
    try {
      if (isTauri()) await invoke("open_detector_window");
      else {
        if (!popup.current || popup.current.closed) {
          const url = new URL(location.href);
          url.searchParams.set("detector_window", session);
          popup.current = window.open(
            url,
            `dioptas-detector-${session}`,
            "popup,width=900,height=760",
          );
          if (!popup.current)
            throw Error("Allow pop-up windows to detach the detector.");
        } else popup.current.focus();
      }
      setDetached(true);
    } catch (error) {
      latest.current.onError(String(error));
    } finally {
      opening.current = false;
    }
  };
  const png = () =>
    new Promise<string>((resolve, reject) => {
      const identity = surface.current?.presentation.identity;
      if (!identity) {
        reject(Error("No detector image is available."));
        return;
      }
      const id = crypto.randomUUID();
      const timer = setTimeout(() => {
        exports.current.delete(id);
        reject(Error("The detector window did not respond."));
      }, 15000);
      exports.current.set(id, { resolve, reject, timer, identity });
      channel.current?.send({ type: "export", id, identity });
    });
  return {
    detached,
    context,
    displayKey,
    present,
    tools: (value: ReturnType<typeof detectorTools> | null) => {
      accessories.current = value;
      compose();
    },
    open: () => void open(),
    dock: () => void dock(),
    png,
  };
}

/** The original RasterView/ImageIntensity props and callbacks remain with each
 * workspace. Only their presentation moves, preserving all existing tools.
 */
export function DetectorSurface({
  children,
  interactionKey = "",
  priority = 0,
  label,
  onBack,
  active = true,
  enabled = true,
  showUndock = true,
  cakeWavelength,
}: {
  children: ReactNode;
  interactionKey?: string;
  priority?: number;
  label?: string;
  onBack?: () => void;
  active?: boolean;
  enabled?: boolean;
  showUndock?: boolean;
  cakeWavelength?: number;
}) {
  const owner = useContext(DetectorWindowContext);
  const elements = Children.toArray(children) as ReactElement<
    Record<string, unknown>
  >[];
  const raster = elements[0]?.props;
  const intensity = elements[1]?.props;
  const value =
    raster && intensity && owner && enabled && active
      ? detectorPresentation(
          JSON.stringify([
            owner.context,
            interactionKey,
            detectorBufferId(raster.raster as Raster),
            raster.tool,
            raster.radius,
            raster.activeRing,
            raster.currentPeakRing,
            raster.busy,
          ]),
          raster,
          intensity,
        )
      : null;
  if (value && owner) {
    value.presentation.intensityKey = `${owner.displayKey}:${interactionKey}`;
    if (raster.radialAxis)
      value.presentation.cakeAxis = {
        requested: (raster.radialAxis as { requested: "2th_deg" | "q_A^-1" })
          .requested,
        wavelength: cakeWavelength,
      };
    if (label) value.presentation.label = label;
    if (onBack) {
      value.callbacks.set("back", onBack);
      value.presentation.back = true;
    }
  }
  const token = useRef({});
  const current = useRef(owner);
  current.current = owner;
  useLayoutEffect(() => {
    current.current?.present(token.current, value, priority);
  });
  useLayoutEffect(
    () => () => current.current?.present(token.current, null),
    [],
  );
  return (
    <div
      className="detector-surface"
      data-detached={(enabled && owner?.detached) || undefined}
    >
      {enabled && owner?.detached ? (
        <div className="detector-detached-placeholder">
          <p>Detector image is in its own window.</p>
          <Button onClick={owner.open}>Show detector window</Button>
          <Button onClick={owner.dock}>Dock detector image</Button>
        </div>
      ) : (
        <>
          <div className="detector-workspace">{children}</div>
          {owner && enabled && showUndock && (
            <Button
              className="plot-tool-button detector-window-action"
              aria-label="Undock detector image"
              title="Undock detector image"
              onClick={owner.open}
            >
              <ExternalLink size={16} />
            </Button>
          )}
        </>
      )}
    </div>
  );
}

/** Move the existing toolbar/profile with the selected image surface. */
export function DetectorWindowTools({
  controls,
  profile,
}: {
  controls: ReactElement | null;
  profile: ReactElement | null;
}) {
  const owner = useContext(DetectorWindowContext);
  const latest = useRef(owner);
  latest.current = owner;
  const controlProps = controls?.props as Record<string, unknown> | undefined;
  const profileProps = profile?.props as Record<string, unknown> | undefined;
  const value = detectorTools(
    controlProps
      ? {
          ...controlProps,
          run: async (command: string, args: Record<string, unknown> = {}) => {
            if (
              command !== "settings" ||
              !Object.keys(args).length ||
              Object.entries(args).some(
                ([key, value]) =>
                  !["use_mask", "transparent_mask"].includes(key) ||
                  typeof value !== "boolean",
              )
            )
              throw Error("This image control is unavailable.");
            await (controlProps.run as import("./integration").IntegrationRun)(
              command,
              args,
            );
          },
        }
      : null,
    profileProps
      ? {
          ...profileProps,
          run: async (
            command: string,
            args: Record<string, unknown> = {},
            message = "",
          ) => {
            if (!["cake_profile", "save_cake_profile"].includes(command))
              throw Error("This profile command is unavailable.");
            let result: Response = { ok: false, cancelled: true };
            await (profileProps.run as import("./integration").IntegrationRun)(
              command,
              args,
              message,
              (reply) => {
                result = {
                  ok: reply.ok,
                  error: reply.error,
                  cakeProfile: reply.cakeProfile,
                };
              },
            );
            return result;
          },
        }
      : null,
  );
  useLayoutEffect(() => {
    latest.current?.tools(value);
  });
  useLayoutEffect(() => () => latest.current?.tools(null), []);
  return owner?.detached ? null : (
    <>
      {profile}
      {controls}
    </>
  );
}
