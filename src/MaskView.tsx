import { runCommand } from "./commandDispatch";
import type { CommandRequest } from "./commandContracts";
import { DetectorSurface } from "./DetectorWindow";
import { Button } from "./ui";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  detectorViewport,
  plotViewContext,
  type SharedPlotViews,
} from "./plotViewport";
import { RasterView } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import type { Raster, State } from "./types";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import {
  previewMask,
  shapeHelp,
  type MaskTools,
  type MaskPoint,
  type MaskOverlay,
} from "./maskDomain";
import "./mask.css";
export type MaskRun = import("./commandContracts").Run;

export function MaskView({
  contrast,
  plotViews,
  active = true,
  image,
  mask,
  state,
  ready,
  busy,
  run,
  tools,
  resetKey,
  onHover,
  onSelectionStatus,
}: {
  contrast: {
    limits: [number, number];
    setLimits: (limits: [number, number]) => void;
    autoActive: boolean;
    setAutoActive: (active: boolean) => void;
  };
  plotViews?: SharedPlotViews;
  active?: boolean;
  image: Raster | null;
  mask: Raster | null;
  state: State | null;
  ready: boolean;
  busy: boolean;
  run: MaskRun;
  tools: MaskTools;
  resetKey: number;
  onHover: (point: { x: number; y: number } | null) => void;
  onSelectionStatus: (
    status: { text: string; cancel: () => void } | null,
  ) => void;
}) {
  const { limits, setLimits, autoActive, setAutoActive } = contrast;
  const [log, setLog] = useState(false),
    [palette, setPalette] = useState("grey");
  const [points, setPoints] = useState<MaskPoint[]>([]),
    [hover, setHover] = useState<MaskPoint | null>(null);
  const [pending, setPending] = useState(0);
  const [pendingOverlay, setPendingOverlay] = useState<MaskOverlay | null>(
    null,
  );
  const drawingSequence = useRef(0);
  const orientationContext = plotViewContext(state);
  const [preferences, setPreferences] = useImageDisplayPreferences(
    "mask-detector",
    "vertical",
  );
  useEffect(() => {
    setPoints((previous) => (previous.length ? [] : previous));
    setPendingOverlay(null);
    drawingSequence.current++;
  }, [image?.data, orientationContext]);
  useEffect(() => setPoints([]), [tools.shape, tools.erase, resetKey]);
  const cancelSelection = useCallback(() => setPoints([]), []);
  useEffect(() => {
    onSelectionStatus(
      points.length
        ? {
            text: `${points.length} point${points.length > 1 ? "s" : ""} selected · ${shapeHelp[tools.shape]}`,
            cancel: cancelSelection,
          }
        : null,
    );
  }, [points.length, tools.shape, onSelectionStatus, cancelSelection]);
  useEffect(() => () => onSelectionStatus(null), [onSelectionStatus]);
  const submitDrawing = async (
    request: CommandRequest<"mask_edit" | "mask_stroke">,
    preview: MaskOverlay | null,
  ) => {
    const sequence = ++drawingSequence.current;
    setPending((count) => count + 1);
    setPendingOverlay(preview);
    try {
      await runCommand(run, request, "Applying mask…");
    } finally {
      setPending((count) => count - 1);
      if (sequence === drawingSequence.current) setPendingOverlay(null);
    }
  };
  const commitShape = (vertices: MaskPoint[]) => {
    if (tools.shape === "navigate" || tools.shape === "point") return;
    void submitDrawing(
      {
        command: "mask_edit",
        payload: {
          operation: tools.shape,
          points: vertices,
          erase: tools.erase,
        },
      },
      previewMask(tools.shape, vertices, null, tools.erase),
    );
    setPoints([]);
  };
  const finish = (vertices = points) => {
    if (vertices.length < 3 || busy) return;
    commitShape(vertices);
  };
  useEffect(() => {
    if (!active) return;
    const key = (event: KeyboardEvent) => {
      const target =
        event.target instanceof Element ? event.target : document.body;
      if (
        target.closest(
          'input,select,textarea,dialog,[role="dialog"],[role="listbox"],[role="menu"],[contenteditable="true"]',
        ) ||
        event.ctrlKey ||
        event.metaKey
      )
        return;
      if (
        event.defaultPrevented ||
        (["Enter", " "].includes(event.key) &&
          target.closest('button, a, summary, [role="tab"]'))
      )
        return;
      if (event.key === "Escape") setPoints([]);
      if (event.key === "Enter" && tools.shape === "polygon") {
        event.preventDefault();
        event.stopImmediatePropagation();
        finish();
      }
      if (
        tools.shape === "point" &&
        ["q", "w"].includes(event.key.toLowerCase())
      )
        tools.setDiameter(
          Math.max(
            2,
            Math.min(
              600,
              tools.diameter + (event.key.toLowerCase() === "q" ? 1 : -1),
            ),
          ),
        );
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [points, tools, busy, active]);
  const pick = ({ x, y }: { x: number; y: number }) => {
    if (tools.shape === "navigate" || tools.shape === "point") return;
    const next: MaskPoint[] = [...points, [x, y]];
    if (
      ((tools.shape === "rectangle" || tools.shape === "circle") &&
        next.length === 2) ||
      (tools.shape === "arc" && next.length === 4)
    ) {
      commitShape(next);
    } else setPoints(next);
  };
  return (
    <section
      className="panel detector-panel mask-view"
      aria-label="Mask detector workspace"
      aria-busy={pending > 0}
    >
      {image ? (
        <DetectorSurface interactionKey={`${tools.shape}:${tools.erase}`}>
          <RasterView
            raster={image}
            viewport={
              plotViews
                ? detectorViewport(plotViews.detector, plotViewContext(state))
                : undefined
            }
            imagePadding={0}
            mask={mask ?? undefined}
            maskOpacity={state?.transparentMask ? 0.4 : 1}
            limits={limits}
            log={log}
            palette={palette}
            tool={
              tools.shape === "point"
                ? tools.erase
                  ? "erase"
                  : "mask"
                : tools.shape === "navigate"
                  ? "pan"
                  : "pick"
            }
            radius={tools.diameter / 2}
            busy={busy}
            resetKey={resetKey}
            onPick={pick}
            overlay={
              points.length
                ? previewMask(tools.shape, points, hover, tools.erase)
                : (pendingOverlay ?? undefined)
            }
            onImageDoubleClick={() => {
              if (tools.shape === "polygon") finish();
            }}
            onHover={(p) => {
              setHover(p ? [p.x, p.y] : null);
              onHover(p);
            }}
            onStroke={(points, erase) =>
              void submitDrawing(
                {
                  command: "mask_stroke",
                  payload: { points, radius: tools.diameter / 2, erase },
                },
                null,
              )
            }
          />
          <ImageIntensity
            initialAutoActive={autoActive}
            onAutoActiveChange={setAutoActive}
            raster={image}
            preferences={preferences}
            onPreferences={setPreferences}
            ready={ready}
            limits={limits}
            onLimits={setLimits}
            log={log}
            onLog={setLog}
            palette={palette}
            onPalette={setPalette}
            onAuto={async (settings) => {
              // Limits are display-only and independent of the other images.
              const result = await import("./bridge")
                .then(({ connect }) => connect())
                .then((invoke) => invoke("image_levels", { ...settings }));
              if (result.ok && result.levels) setLimits(result.levels);
            }}
          />
        </DetectorSurface>
      ) : (
        <div className="empty-view">
          <h3>Open a detector image</h3>
          <Button disabled={!ready} onClick={() => void run("open_image")}>
            Open detector image
          </Button>
        </div>
      )}
    </section>
  );
}
