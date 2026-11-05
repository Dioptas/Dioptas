import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ExternalLink,
  FolderOpen,
  PanelBottomClose,
  Save,
  X,
} from "lucide-react";
import { DataTable, TableScroll } from "./DataTable";
import { BatchHeatmap } from "./BatchHeatmap";
import { BatchControls } from "./BatchControls";
import { ImageIntensity } from "./ImageIntensity";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import { useBatchDisplay } from "./batchDisplay";
import type { BatchData, BatchRun } from "./batchDomain";
import type { Response, Unit } from "./types";
import type { ReportPlot } from "./plotReadout";
import "./batch.css";

/** Layout follows Qt BatchWidget: file actions and view tabs, central view,
 * right-hand plot options, then actions and frame/range navigation below. */
export function BatchView({
  batch,
  calibrated,
  ready,
  run,
  request,
  reportPlot,
  collapsed = false,
  onCollapse,
  onDetach,
  onDock,
  onHide,
}: {
  batch: BatchData | null;
  calibrated: boolean;
  ready: boolean;
  run: BatchRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  reportPlot: ReportPlot;
  collapsed?: boolean;
  onCollapse?: () => void;
  onDetach?: () => void;
  onDock?: () => void;
  onHide: () => void;
}) {
  const display = useBatchDisplay(batch);
  const [prefs, setPrefs] = useImageDisplayPreferences(
    "batch-overview",
    "horizontal",
    false,
  );
  const [tab, setTab] = useState<"Files" | "2D">(batch ? "2D" : "Files");
  const rangeRef = useRef<[number, number]>([
    0,
    Math.max(0, (batch?.entries.length ?? 1) - 1),
  ]);
  useEffect(() => {
    if (batch) setTab("2D");
  }, [batch?.id]);
  const select = (index: number) =>
    void run("batch_select", { index }, "Loading batch frame…");
  const folder = batch?.files[0]?.path.replace(/[\\/][^\\/]*$/, "") ?? "";
  const auto = async () => {
    const r = await request("batch_levels", { ...prefs.auto });
    if (r?.batchLevels) display.update({ limits: r.batchLevels, auto: true });
  };
  const onRange = (start: number, stop: number) => {
    if (!batch || start < 0 || stop < start || stop >= batch.entries.length)
      return;
    const old = rangeRef.current;
    rangeRef.current = [start, stop];
    if (old[0] === start && old[1] === stop) return;
    display.update({
      range: {
        xMin: display.range?.xMin ?? 0,
        xMax: display.range?.xMax ?? batch.x.length,
        yMin: batch.entries.length - 1 - stop,
        yMax: batch.entries.length - start,
      },
    });
  };
  return (
    <section
      className={`batch-series-panel ${collapsed ? "batch-collapsed" : ""}`}
      aria-label="Batch series"
    >
      <header className="batch-series-toolbar">
        <div
          className="batch-file-toolbar"
          role="toolbar"
          aria-label="Batch files"
        >
          <button
            aria-label="Load raw/proc data"
            title="Load raw/proc data"
            disabled={!ready}
            onClick={() => run("batch_load_data", {}, "Loading batch data…")}
          >
            <FolderOpen size={16} />
          </button>
          <button
            aria-label="Previous batch folder"
            title="Load files in previous folder"
            disabled={!ready || !batch?.canReintegrate}
            onClick={() =>
              run(
                "batch_folder_step",
                { direction: -1 },
                "Loading previous folder…",
              )
            }
          >
            <ChevronLeft size={15} />
          </button>
          <button
            aria-label="Next batch folder"
            title="Load files in next folder"
            disabled={!ready || !batch?.canReintegrate}
            onClick={() =>
              run("batch_folder_step", { direction: 1 }, "Loading next folder…")
            }
          >
            <ChevronRight size={15} />
          </button>
          <button
            aria-label="Save batch data"
            title="Save data"
            disabled={!ready || !batch}
            onClick={() => run("integration_save_batch", {}, "Saving batch…")}
          >
            <Save size={15} />
          </button>
        </div>
        <span className="batch-folder-label" title={folder}>
          {folder || "Batch"}
        </span>
        <div className="batch-view-tabs" role="tablist" aria-label="Batch view">
          {(["Files", "2D"] as const).map((name) => (
            <button
              role="tab"
              aria-selected={tab === name}
              key={name}
              disabled={name === "2D" && !batch}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="batch-window-actions">
          {onCollapse && (
            <button
              aria-label={
                collapsed ? "Expand batch overview" : "Collapse batch overview"
              }
              title={collapsed ? "Expand" : "Collapse"}
              onClick={onCollapse}
            >
              {collapsed ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
          )}
          {onDetach && (
            <button
              aria-label="Detach batch"
              title="Move Batch to a separate window"
              onClick={onDetach}
            >
              <ExternalLink size={15} />
            </button>
          )}
          {onDock && (
            <button
              aria-label="Dock batch below image"
              title="Dock below the image in Integration"
              onClick={onDock}
            >
              <PanelBottomClose size={15} />
            </button>
          )}
          <button
            aria-label="Hide batch view"
            title="Hide Batch; keep the series"
            onClick={onHide}
          >
            <X size={15} />
          </button>
        </div>
      </header>
      <div className="batch-qt-content" hidden={collapsed}>
        {tab === "Files" ? (
          <div
            className="batch-files-view"
            role="tabpanel"
            aria-label="Batch files"
          >
            <dl className="batch-file-metadata">
              <dt>Calibration File:</dt>
              <dd title={batch?.calibration ?? ""}>
                {batch?.calibration || "none loaded"}
              </dd>
              <dt>Mask File:</dt>
              <dd title={batch?.mask ?? ""}>{batch?.mask || "none loaded"}</dd>
            </dl>
            {batch ? (
              <TableScroll className="batch-file-list">
                <DataTable aria-label="Raw batch files">
                  <thead>
                    <tr>
                      <th>Raw file name</th>
                      <th>N images</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batch.files.map((file, i) => (
                      <tr
                        key={i}
                        aria-selected={
                          file.path === batch.entries[batch.selected]?.path
                        }
                      >
                        <td>
                          <button
                            disabled={!ready || file.first === null}
                            aria-label={`Select batch file ${i}`}
                            title={file.path}
                            onClick={() => select(file.first!)}
                          >
                            {file.path}
                          </button>
                        </td>
                        <td>{file.frames}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              </TableScroll>
            ) : (
              <div className="empty-view">
                <p>
                  Load a series of raw image files to integrate them in one run.
                </p>
                <button
                  disabled={!ready}
                  onClick={() =>
                    run("batch_load_data", {}, "Loading batch data…")
                  }
                >
                  Load raw/proc data
                </button>
                {!calibrated && (
                  <p>
                    Raw images need a calibration. Stored batches can be opened
                    directly.
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          batch && (
            <div
              className="batch-2d-view"
              role="tabpanel"
              aria-label="Batch 2D view"
            >
              <div className="batch-overview-image detector-workspace">
                <BatchHeatmap
                  batch={batch}
                  limits={display.limits}
                  log={display.log}
                  sqrt={display.sqrt}
                  palette={display.palette}
                  viewport={display.viewport}
                  ready={ready}
                  onSelect={select}
                  reportPlot={reportPlot}
                />
                <ImageIntensity
                  raster={batch.raster}
                  limits={display.limits}
                  onLimits={(limits) => display.update({ limits, auto: false })}
                  log={display.log}
                  onLog={(log) =>
                    display.update({ log, sqrt: false, auto: false })
                  }
                  palette={display.palette}
                  onPalette={(palette) => display.update({ palette })}
                  preferences={prefs}
                  onPreferences={setPrefs}
                  ready={ready}
                  display="batch"
                  initialLevelsReady={display.initialized}
                  initialAutoActive={display.auto}
                  onAuto={auto}
                />
              </div>
              <div className="batch-options" aria-label="Batch plot options">
                {(
                  [
                    ["2th_deg", "2θ"],
                    ["q_A^-1", "Q"],
                    ["d_A", "d"],
                  ] as [Unit, string][]
                ).map(([unit, label]) => (
                  <button
                    key={unit}
                    aria-label={`Batch unit ${label}`}
                    aria-pressed={batch.unit === unit}
                    disabled={
                      !ready ||
                      (unit !== batch.sourceUnit &&
                        [unit, batch.sourceUnit].includes("2th_deg") &&
                        !batch.wavelength)
                    }
                    onClick={() =>
                      run("batch_unit", { unit }, "Changing batch unit…")
                    }
                  >
                    {label}
                  </button>
                ))}
                <span className="batch-options-space" />
                <button
                  aria-pressed={!display.log && !display.sqrt}
                  onClick={() => display.update({ log: false, sqrt: false })}
                >
                  lin
                </button>
                <button
                  aria-pressed={display.sqrt}
                  onClick={() => display.update({ log: false, sqrt: true })}
                >
                  √
                </button>
                <button
                  aria-pressed={display.log}
                  onClick={() => display.update({ log: true, sqrt: false })}
                >
                  log
                </button>
              </div>
            </div>
          )
        )}
      </div>
      {!collapsed && (
        <BatchControls
          batch={batch}
          ready={ready}
          calibrated={calibrated}
          filesView={tab === "Files"}
          run={run}
          onAutoScale={auto}
          onRange={onRange}
        />
      )}
    </section>
  );
}
