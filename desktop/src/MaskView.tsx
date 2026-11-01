import { useEffect, useState } from "react";
import { RasterView } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import type { Raster, State, ImageDisplayPreferences } from "./types";
import { number } from "./types";
import {
  previewMask,
  shapeHelp,
  type MaskTools,
  type MaskPoint,
} from "./maskDomain";
import "./mask.css";
export type MaskRun = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => Promise<void>;

export function MaskView({
  image,
  mask,
  state,
  ready,
  busy,
  run,
  tools,
  resetKey,
  onHover,
  pixel,
}: {
  image: Raster | null;
  mask: Raster | null;
  state: State | null;
  ready: boolean;
  busy: boolean;
  run: MaskRun;
  tools: MaskTools;
  resetKey: number;
  onHover: (point: { x: number; y: number } | null) => void;
  pixel: { x: number; y: number; value: number | null } | null;
}) {
  const [limits, setLimits] = useState<[number, number]>(
    image?.limits ?? [0, 100],
  );
  const [log, setLog] = useState(false),
    [palette, setPalette] = useState("grey"),
    [show, setShow] = useState(true);
  const [fit, setFit] = useState(0),
    [points, setPoints] = useState<MaskPoint[]>([]),
    [hover, setHover] = useState<MaskPoint | null>(null);
  const [preferences, setPreferences] = useState<ImageDisplayPreferences>({
    size: "compact",
    orientation: "vertical",
    auto: { mode: "percentile", percentile: 0.4, filter_gaps: true },
  });
  useEffect(() => {
    if (image) setLimits(image.limits);
    setPoints([]);
  }, [image]);
  useEffect(() => setPoints([]), [tools.shape, tools.erase, resetKey]);
  const finish = (vertices = points) => {
    if (vertices.length < 3 || busy) return;
    void run(
      "mask_edit",
      { operation: tools.shape, points: vertices, erase: tools.erase },
      "Applying selection…",
    );
    setPoints([]);
  };
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (
        (event.target as HTMLElement).closest("input,select,textarea") ||
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
  }, [points, tools, busy]);
  const pick = ({ x, y }: { x: number; y: number }) => {
    if (tools.shape === "navigate" || tools.shape === "point") return;
    const next: MaskPoint[] = [...points, [x, y]];
    if (
      ((tools.shape === "rectangle" || tools.shape === "circle") &&
        next.length === 2) ||
      (tools.shape === "arc" && next.length === 4)
    ) {
      void run(
        "mask_edit",
        { operation: tools.shape, points: next, erase: tools.erase },
        "Applying selection…",
      );
      setPoints([]);
    } else setPoints(next);
  };
  return (
    <section
      className="panel detector-panel mask-view"
      aria-label="Mask detector workspace"
    >
      <div className="panel-heading">
        <div>
          <span className="panel-dot amber" />
          <h2>Detector image</h2>
          {state?.shape && (
            <span className="panel-meta">
              {state.shape[1]} × {state.shape[0]}
            </span>
          )}
        </div>
        <div>
          <button
            onClick={() => {
              setFit(fit + 1);
              setPoints([]);
            }}
            aria-label="Fit mask detector"
          >
            Fit
          </button>
          <label className="check-line">
            <input
              type="checkbox"
              checked={show}
              onChange={(e) => setShow(e.target.checked)}
            />
            Display mask
          </label>
        </div>
      </div>
      {image ? (
        <div className="detector-workspace">
          <RasterView
            raster={image}
            mask={show ? (mask ?? undefined) : undefined}
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
            resetKey={resetKey + fit}
            onPick={pick}
            overlay={previewMask(tools.shape, points, hover, tools.erase)}
            onImageDoubleClick={() => {
              if (tools.shape === "polygon") finish();
            }}
            onHover={(p) => {
              setHover(p ? [p.x, p.y] : null);
              onHover(p);
            }}
            onStroke={(points, erase) =>
              void run(
                "mask_stroke",
                { points, radius: tools.diameter / 2, erase },
                "Applying mask…",
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
      <div className="panel-footer detector-readout">
        <span data-testid="mask-mouse-readout">
          {pixel && image
            ? `x ${pixel.x} · y ${image.fullHeight - 1 - pixel.y} · I ${pixel.value === null ? "—" : number(pixel.value, 3)}`
            : shapeHelp[tools.shape]}
        </span>
        <span>{number(state?.maskedPixels ?? 0, 0)} masked</span>
      </div>
      {points.length > 0 && (
        <div className="mask-selection-status" role="status">
          {points.length} point{points.length > 1 ? "s" : ""} selected ·{" "}
          {shapeHelp[tools.shape]}{" "}
          <button onClick={() => setPoints([])}>Cancel selection</button>
        </div>
      )}
    </section>
  );
}
