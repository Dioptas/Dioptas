import { useEffect, useState } from "react";
import { detectorPlotSetup, patternPlotSetup } from "./diffractionPlotSetup";
import {
  patternViewport,
  plotViewContext,
  type SharedPlotViews,
} from "./plotViewport";
import { patternReading } from "./PlotStatus";
import { BatchHeatmap } from "./BatchHeatmap";
import { ImageIntensity } from "./ImageIntensity";
import { RasterView } from "./RasterView";
import { PatternView } from "./PatternView";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import type { BatchData, BatchRun } from "./batchDomain";
import type { Raster, Response, State } from "./types";
import type { ReportPlot } from "./plotReadout";
import type { ZoomMode } from "./usePlotNavigation";
import "./batch.css";

function useDisplay(raster: Raster | null, id: string) {
  const [limits, setLimits] = useState<[number, number]>([0, 1]);
  const [log, setLog] = useState(false),
    [palette, setPalette] = useState("grey");
  const [preferences, onPreferences] = useImageDisplayPreferences(
    id,
    "horizontal",
    false,
  );
  useEffect(() => {
    if (raster) setLimits(raster.limits);
  }, [raster?.data]);
  return {
    limits,
    onLimits: setLimits,
    log,
    onLog: setLog,
    palette,
    onPalette: setPalette,
    preferences,
    onPreferences,
  };
}
export function BatchView({
  plotViews,
  batch,
  image,
  mask,
  state,
  ready,
  run,
  request,
  reportPlot,
  onDetectorHover,
  patternZoom,
  onPatternZoom,
}: {
  plotViews: SharedPlotViews;
  batch: BatchData | null;
  image: Raster | null;
  mask: Raster | null;
  state: State | null;
  ready: boolean;
  run: BatchRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  reportPlot: ReportPlot;
  onDetectorHover: (point: { x: number; y: number } | null) => void;
  patternZoom: ZoomMode;
  onPatternZoom: (mode: ZoomMode) => void;
}) {
  const overview = useDisplay(batch?.raster ?? null, "batch-overview"),
    detector = useDisplay(image, "batch-detector");
  const [expanded, setExpanded] = useState(false),
    [logPattern, setLogPattern] = useState(false);
  const patternPlot = batch
    ? patternPlotSetup({
        pattern: batch.pattern,
        viewport: patternViewport(
          plotViews.pattern,
          plotViewContext(state),
          batch.unit,
          logPattern ? "log" : "linear",
          batch.wavelength ?? undefined,
        ),
        patternColor: state?.integration.originalPatternColor,
        showLegend: false,
      })
    : null;
  const select = (index: number) =>
    void run("batch_select", { index }, "Loading batch frame…");
  return (
    <div className={`batch-layout ${expanded ? "batch-expanded" : ""}`}>
      <section
        className="panel batch-overview-panel"
        aria-label="Batch overview"
      >
        <div className="panel-heading">
          <span>
            {batch
              ? `${batch.entries.length} integrated patterns`
              : "Batch processing"}
          </span>
          <button
            disabled={!batch}
            aria-pressed={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Show detector / pattern" : "Expand overview"}
          </button>
        </div>
        {batch ? (
          <div className="batch-overview-image detector-workspace">
            <BatchHeatmap
              batch={batch}
              {...overview}
              ready={ready}
              onSelect={select}
              reportPlot={reportPlot}
            />
            <ImageIntensity
              raster={batch.raster}
              {...overview}
              ready={ready}
              display="batch"
              onAuto={async (settings) => {
                const r = await request("batch_levels", { ...settings });
                if (r?.batchLevels) overview.onLimits(r.batchLevels);
              }}
            />
          </div>
        ) : (
          <div className="empty-view">
            <h3>Explore an image series</h3>
            <p>
              Integrate detector images with your current calibration,
              <br />
              mask and corrections. Select a row to inspect its pattern.
            </p>
            <button
              className="primary"
              disabled={!ready || !state?.calibrated}
              onClick={() => run("batch_load", {}, "Integrating batch…")}
            >
              Load images…
            </button>
            <button
              disabled={!ready}
              onClick={() => run("batch_open", {}, "Opening processed batch…")}
            >
              Open processed batch…
            </button>
          </div>
        )}
      </section>
      {!expanded && (
        <>
          <section
            className="batch-detector-panel"
            aria-label="Batch detector image"
          >
            {state?.hasImage && image ? (
              <div className="detector-workspace">
                <RasterView
                  raster={image}
                  {...detectorPlotSetup({ state, viewports: plotViews, mask })}
                  limits={detector.limits}
                  log={detector.log}
                  palette={detector.palette}
                  busy={!ready}
                  onHover={onDetectorHover}
                />
                <ImageIntensity
                  raster={image}
                  {...detector}
                  ready={ready}
                  onAuto={async (settings) => {
                    const r = await request("image_levels", { ...settings });
                    if (r?.levels) detector.onLimits(r.levels);
                  }}
                />
              </div>
            ) : (
              <div className="empty-view">
                <p>
                  {batch
                    ? "Raw detector image unavailable"
                    : "The selected detector image appears here"}
                </p>
              </div>
            )}
          </section>
          <section
            className="panel batch-pattern-panel"
            aria-label="Batch selected pattern"
          >
            <div className="panel-heading">
              <span>
                {batch
                  ? `Pattern ${batch.selected + 1} · ${batch.entries[batch.selected]?.name}`
                  : "Selected pattern"}
              </span>
              <label>
                <input
                  type="checkbox"
                  checked={logPattern}
                  onChange={(e) => setLogPattern(e.target.checked)}
                />
                Log I
              </label>
            </div>
            {batch && patternPlot ? (
              <PatternView
                {...patternPlot.props}
                log={logPattern}
                onHover={(point) =>
                  reportPlot(
                    "pattern",
                    point
                      ? patternReading(point, batch.wavelength ?? undefined)
                      : null,
                  )
                }
                zoomMode={patternZoom}
                onZoomMode={onPatternZoom}
              />
            ) : (
              <div className="empty-view">
                <p>Select an integrated pattern</p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
