import { scientificValue } from "./ScientificNumberInput";
import { TabList } from "./TabList";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ExternalLink,
  FolderOpen,
  ChartNoAxesColumn,
  Unlink,
  PanelBottomClose,
  Save,
  Settings2,
  X,
} from "lucide-react";
import { DataTable, TableScroll } from "./DataTable";
import { BatchHeatmap } from "./BatchHeatmap";
import { BatchControls } from "./BatchControls";
import { PlotToggle } from "./IntegrationPlotControls";
import { ImageIntensity } from "./ImageIntensity";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
import { batchDisplayInUnit, useBatchDisplay } from "./batchDisplay";
import type { BatchData, BatchRun } from "./batchDomain";
import type { Response, Unit } from "./types";
import type { ReportPlot } from "./plotReadout";
import "./batch.css";

/** Layout follows Qt BatchWidget: file actions and view tabs, central view,
 * right-hand plot options, then actions and frame/range navigation below. */
export function BatchView({
  batch,
  position,
  calibrated,
  ready,
  run,
  request,
  reportPlot,
  collapsed = false,
  docked = false,
  linkedDisplay,
  onCollapse,
  onDetach,
  onDock,
  onHide,
  activeImagePath,
}: {
  batch: BatchData | null;
  activeImagePath?: string | null;
  position?: import("./linkedPosition").PatternPosition;
  calibrated: boolean;
  ready: boolean;
  run: BatchRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  reportPlot: ReportPlot;
  collapsed?: boolean;
  docked?: boolean;
  linkedDisplay?: {
    unit: Unit;
    log: boolean;
    sqrt: boolean;
    onScale: (scale: "linear" | "log" | "sqrt") => void;
  };
  onCollapse?: () => void;
  onDetach?: () => void;
  onDock?: () => void;
  onHide: () => void;
}) {
  const display = useBatchDisplay(batch);
  const shownBatch = useMemo(
    () =>
      batch && linkedDisplay
        ? batchDisplayInUnit(batch, linkedDisplay.unit)
        : batch,
    [batch, linkedDisplay?.unit],
  );
  const shownLog = linkedDisplay?.log ?? display.log;
  const shownSqrt = linkedDisplay?.sqrt ?? display.sqrt;
  const [prefs, setPrefs] = useImageDisplayPreferences(
    "batch-overview",
    "vertical",
    false,
  );
  const [tab, setTab] = useState<"Files" | "2D" | "Options">(
    batch ? "2D" : "Files",
  );
  const rangeRef = useRef<[number, number]>([
    0,
    Math.max(0, (batch?.entries.length ?? 1) - 1),
  ]);
  useEffect(() => {
    if (batch) setTab((tab) => (tab === "Options" ? tab : "2D"));
  }, [batch?.id]);
  const select = (
    index: number,
    position?: import("./linkedPosition").PatternPosition,
  ) =>
    void run(
      "batch_select",
      { index, ...(position ? { position } : {}) },
      "Loading batch frame…",
    );
  const folder = batch?.files[0]?.path.replace(/[\\/][^\\/]*$/, "") ?? "";
  const folderLabel = folder
    ? `…/${folder
        .split(/[\\/]+/)
        .filter(Boolean)
        .at(-1)}`
    : "Batch";
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
        yMin: start,
        yMax: stop + 1,
      },
    });
  };
  const plotOptions = batch ? (
    <div
      className="integration-pattern-tools batch-options"
      role="group"
      aria-label="Batch plot options"
    >
      <div
        className="plot-tool-group"
        role="group"
        aria-label="Batch radial unit"
      >
        {(
          [
            ["2th_deg", "2θ", "Two theta (degrees)"],
            ["q_A^-1", "Q", "Scattering vector (Å⁻¹)"],
            ["d_A", "d", "d spacing (Å)"],
          ] as [Unit, string, string][]
        ).map(([unit, label, title]) => (
          <PlotToggle
            key={unit}
            label={`Batch unit ${label}`}
            title={title}
            pressed={batch.unit === unit}
            disabled={
              !ready ||
              (unit !== batch.sourceUnit &&
                [unit, batch.sourceUnit].includes("2th_deg") &&
                !batch.wavelength)
            }
            onClick={() => run("batch_unit", { unit }, "Changing batch unit…")}
          >
            {label}
          </PlotToggle>
        ))}
      </div>
      <div
        className="plot-tool-group"
        role="group"
        aria-label="Batch intensity scale"
      >
        <PlotToggle
          label="Logarithmic batch intensity"
          title="Logarithmic intensity scale; turn off for linear"
          pressed={display.log}
          onClick={() => display.update({ log: !display.log, sqrt: false })}
        >
          Log
        </PlotToggle>
        <PlotToggle
          label="Square root batch intensity"
          title="Square-root intensity scale; turn off for linear"
          pressed={display.sqrt}
          onClick={() => display.update({ log: false, sqrt: !display.sqrt })}
        >
          √
        </PlotToggle>
      </div>
    </div>
  ) : null;
  return (
    <section
      className={`batch-series-panel ${collapsed ? "batch-collapsed" : ""} ${docked ? "batch-docked" : ""}`}
      data-selected-frame={batch?.selected ?? ""}
      aria-busy={!ready}
      aria-label="Batch series"
      aria-description={
        batch
          ? `Intensity display limits ${scientificValue(display.limits[0])} to ${scientificValue(display.limits[1])}, ${shownLog ? "logarithmic" : shownSqrt ? "square root" : "linear"}.`
          : undefined
      }
    >
      <header className="batch-series-toolbar plot-toolbar">
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
          <span>{folderLabel}</span>
        </span>
        {activeImagePath &&
          batch &&
          batch.entries[batch.selected]?.path !== activeImagePath && (
            <span
              className="batch-source-note"
              title="This series differs from the detector image currently displayed. Select a batch frame to inspect its source."
            >
              <Unlink size={14} aria-hidden="true" />
              <span className="plot-toolbar-label">Separate series</span>
            </span>
          )}
        {docked && batch && (
          <span
            className="batch-position"
            role="group"
            aria-label="Selected batch frame"
            title={`Frame ${batch.selected + 1} of ${batch.entries.length} · ${batch.entries[batch.selected]?.name}`}
          >
            <span className="plot-toolbar-label">
              Frame {batch.selected + 1} of {batch.entries.length}
            </span>
            <span className="batch-position-compact" aria-hidden="true">
              {batch.selected + 1}/{batch.entries.length}
            </span>
          </span>
        )}
        <TabList
          className="batch-view-tabs calibration-workflow-tabs"
          label="Batch view"
          value={tab}
          onChange={setTab}
          options={(["Files", "2D", "Options"] as const).map((name) => ({
            value: name,
            name,
            label: name === "Options" ? <Settings2 size={15} /> : name,
            title: name === "Options" ? "Options" : undefined,
            disabled: name !== "Files" && !batch,
          }))}
        />
        <PlotToggle
          label="Show batch phases"
          title="Show phase lines on the batch overview"
          pressed={display.phases}
          disabled={!batch?.phaseLines?.length}
          onClick={() => display.update({ phases: !display.phases })}
        >
          <ChartNoAxesColumn size={15} aria-hidden="true" />
          <span className="plot-toolbar-label">Phases</span>
        </PlotToggle>
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
          {docked && (
            <button
              aria-label="Hide batch view"
              title="Hide Batch; keep the series"
              onClick={onHide}
            >
              <X size={15} />
            </button>
          )}
        </div>
      </header>
      <div className="batch-qt-content" hidden={collapsed || tab === "Options"}>
        {tab === "Files" ? (
          <div
            className="batch-files-view"
            role="tabpanel"
            aria-label="Batch files"
          >
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
                            aria-label={`Select batch file ${i + 1}`}
                            title={file.path}
                            onClick={() => select(file.first!)}
                          >
                            <span>{file.name}</span>
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
              <div className="batch-overview-column">
                <div className="batch-overview-image detector-workspace">
                  <ImageIntensity
                    raster={batch.raster}
                    limits={display.limits}
                    onLimits={(limits) =>
                      display.update({ limits, auto: false })
                    }
                    log={shownLog}
                    mirrored
                    onLog={(log) =>
                      linkedDisplay
                        ? linkedDisplay.onScale(log ? "log" : "linear")
                        : display.update({ log, sqrt: false, auto: false })
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
                  <BatchHeatmap
                    position={position ?? batch?.position ?? undefined}
                    phaseLines={display.phases ? batch?.phaseLines : undefined}
                    batch={shownBatch!}
                    limits={display.limits}
                    log={shownLog}
                    sqrt={shownSqrt}
                    palette={display.palette}
                    viewport={display.viewport}
                    zoomMode={display.zoomMode}
                    onZoomMode={(zoomMode) => display.update({ zoomMode })}
                    ready={ready}
                    onSelect={select}
                    onNormalize={() =>
                      run(
                        "batch_normalize",
                        { enabled: !batch.normalized },
                        "Updating normalization…",
                      )
                    }
                    reportPlot={reportPlot}
                  />
                </div>
              </div>
              {!linkedDisplay && plotOptions}
            </div>
          )
        )}
      </div>
      {!collapsed && (
        <BatchControls
          docked={docked}
          optionsVisible={tab === "Options"}
          batch={shownBatch}
          ready={ready}
          calibrated={calibrated}
          filesView={tab === "Files"}
          run={run}
          onRange={onRange}
        />
      )}
    </section>
  );
}
