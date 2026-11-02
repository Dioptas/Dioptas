import { useCallback, useEffect, useRef, useState } from "react";
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
export type MaskRun = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => Promise<void>;

export function MaskView({
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
  const [limits, setLimits] = useState<[number, number]>(
    image?.limits ?? [0, 100],
  );
  const [log, setLog] = useState(false),
    [palette, setPalette] = useState("grey");
  const [points, setPoints] = useState<MaskPoint[]>([]),
    [hover, setHover] = useState<MaskPoint | null>(null);
  const [pending, setPending] = useState(0);
  const [pendingOverlay, setPendingOverlay] = useState<MaskOverlay | null>(
    null,
  );
  const drawingSequence = useRef(0);
  const [preferences, setPreferences] = useImageDisplayPreferences(
    "mask-detector",
    "vertical",
  );
  useEffect(() => {
    if (image) setLimits(image.limits);
    setPoints([]);
    setPendingOverlay(null);
    drawingSequence.current++;
  }, [image]);
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
    command: string,
    args: Record<string, unknown>,
    preview: MaskOverlay | null,
  ) => {
    const sequence = ++drawingSequence.current;
    setPending((count) => count + 1);
    setPendingOverlay(preview);
    try {
      await run(command, args, "Applying mask…");
    } finally {
      setPending((count) => count - 1);
      if (sequence === drawingSequence.current) setPendingOverlay(null);
    }
  };
  const commitShape = (vertices: MaskPoint[]) => {
    void submitDrawing(
      "mask_edit",
      { operation: tools.shape, points: vertices, erase: tools.erase },
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
      if (
        (event.target as HTMLElement).closest(
          'input,select,textarea,[role="dialog"]',
        ) ||
        event.ctrlKey ||
        event.metaKey
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
        <div className="detector-workspace">
          <RasterView
            raster={image}
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
                "mask_stroke",
                { points, radius: tools.diameter / 2, erase },
                null,
              )
            }
          />
          <ImageIntensity
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
        </div>
      ) : (
        <div className="empty-view">
          <h3>Open a detector image</h3>
          <button disabled={!ready} onClick={() => void run("open_image")}>
            Open detector image
          </button>
        </div>
      )}
    </section>
  );
}
