import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Save } from "lucide-react";
import { RasterView } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import { useMapDisplay, useMapPreference } from "./mapPreferences";
import { number, type Raster, type Response } from "./types";
import type { MapData, MapRun } from "./mapDomain";
import type { ReportPlot } from "./plotReadout";
export function ScanMapPanel({
  map,
  progressPreview,
  calibrated,
  ready,
  run,
  request,
  reintegrate,
  reportPlot,
  actions,
  allowLoad = true,
}: {
  map: MapData | null;
  progressPreview?: NonNullable<Response["progress"]>["mapPreview"];
  calibrated: boolean;
  ready: boolean;
  run: MapRun;
  request: (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<Response | undefined>;
  reintegrate: boolean;
  reportPlot: ReportPlot;
  actions?: ReactNode;
  allowLoad?: boolean;
}) {
  const mapExporter = useRef<{ png: () => string } | null>(null);
  const [smooth, setSmooth] = useMapPreference<boolean>("smooth", false),
    [smoothFactor, setSmoothFactor] = useMapPreference<number>(
      "smooth-factor",
      5,
    );
  const [showContours, setShowContours] = useMapPreference<boolean>(
      "contours",
      false,
    ),
    [contourCount, setContourCount] = useMapPreference<number>(
      "contour-count",
      5,
    );
  const [preview, setPreview] = useState<Raster | null>(null),
    [contours, setContours] = useState<number[][][]>([]);
  const requestRef = useRef(request);
  requestRef.current = request;
  // A point selection resends map metadata without changing the scan pixels.
  // Keep its preview and contours instead of clearing/recomputing them.
  useEffect(() => {
    let current = true;
    setPreview(null);
    setContours([]);
    if (map && ready && (smooth || showContours))
      void requestRef
        .current("map_display", {
          smooth: smooth ? smoothFactor : 1,
          contours: showContours ? contourCount : 0,
        })
        .then((result) => {
          if (current && result?.ok) {
            setPreview(result.mapPreview ?? null);
            setContours(result.mapContours ?? []);
          }
        });
    return () => {
      current = false;
    };
  }, [
    map?.raster.data,
    map?.raster.width,
    map?.raster.height,
    ready,
    smooth,
    smoothFactor,
    showContours,
    contourCount,
  ]);
  const scanHistogramKey = JSON.stringify(map?.raster.histogram);
  const scanRaster = useMemo(
    () => map?.raster ?? null,
    [
      map?.raster.data,
      map?.raster.dtype,
      map?.raster.width,
      map?.raster.height,
      map?.raster.fullWidth,
      map?.raster.fullHeight,
      map?.raster.limits[0],
      map?.raster.limits[1],
      scanHistogramKey,
    ],
  );
  const scanPeaks = useMemo(
    () =>
      map?.selectedCell && scanRaster
        ? [
            {
              x: map.selectedCell[1],
              y: scanRaster.height - map.selectedCell[0] - 1,
              ring: 1,
              selected: true,
            },
          ]
        : [],
    [map?.selectedCell?.[0], map?.selectedCell?.[1], scanRaster?.height],
  );
  const display = useMapDisplay(scanRaster, "map");
  if (progressPreview)
    return (
      <section className="map-scan-panel" aria-label="Scan map">
        <div
          className="detector-workspace map-raster"
          data-testid="scan-map-progress"
        >
          <RasterView
            raster={progressPreview.raster}
            limits={progressPreview.raster.limits}
            log={display.log}
            palette={display.palette}
            zoomMode="rectangle"
            tool="pan"
            busy
          />
        </div>
        <div className="integration-image-tools" role="status">
          Integrating {progressPreview.completed} / {progressPreview.total} ·
          Preview of layer {progressPreview.active} · Unfinished cells are blank
        </div>
      </section>
    );
  return (
    <section className="map-scan-panel" aria-label="Scan map">
      {map && scanRaster ? (
        <div className="detector-workspace map-raster" data-testid="scan-map">
          <RasterView
            raster={preview ?? scanRaster}
            contours={contours}
            limits={display.limits}
            log={display.log}
            palette={display.palette}
            zoomMode="rectangle"
            tool="pan"
            busy={!ready}
            exportRef={mapExporter}
            peaks={scanPeaks}
            onInspect={(point) =>
              run(
                "map_select",
                {
                  row: map.raster.height - 1 - Math.floor(point.y),
                  column: Math.floor(point.x),
                  reintegrate,
                },
                "Loading scan point…",
              )
            }
            onHover={(point) => {
              if (!point) {
                reportPlot("map", null);
                return;
              }
              const row = map.raster.height - 1 - Math.floor(point.y),
                col = Math.floor(point.x),
                value = map.values[row]?.[col],
                index = map.indices[row]?.[col];
              reportPlot("map", {
                text: `Row ${row} · column ${col} · ${value == null ? "no value" : `I ${number(value, 5)}`} · ${index == null || index < 0 ? "blank" : `point ${index}`}`,
                hint: "Click a map cell to inspect its detector image and pattern.",
              });
            }}
          />
          <ImageIntensity
            raster={scanRaster}
            limits={display.limits}
            onLimits={display.setLimits}
            log={display.log}
            onLog={display.setLog}
            palette={display.palette}
            onPalette={display.setPalette}
            preferences={display.prefs}
            onPreferences={display.setPrefs}
            display="map"
            ready={ready}
            initialLevelsReady={display.initialLevelsReady}
            initialAutoActive={display.initialAutoActive}
            onAuto={async (settings) => {
              const result = await request("map_levels", { ...settings });
              if (result?.mapLevels) display.setAutoLimits(result.mapLevels);
            }}
          />
        </div>
      ) : (
        <div className="empty-view">
          <h3>{allowLoad ? "Load a scan" : "No map loaded"}</h3>
          <p>
            {allowLoad
              ? "Integrate detector images or open a processed batch."
              : "Load a scan from Map mode in the main window."}
          </p>
          {allowLoad && (
            <button
              disabled={!ready || !calibrated}
              className="primary"
              onClick={() => run("map_load", {}, "Integrating map…")}
            >
              Load images…
            </button>
          )}
        </div>
      )}
      <div className="integration-image-tools map-display-controls">
        <label>
          <input
            aria-label="Smooth map"
            type="checkbox"
            checked={smooth}
            disabled={!map}
            onChange={(e) => setSmooth(e.target.checked)}
          />
          Smooth
        </label>
        <input
          aria-label="Map smoothing factor"
          title={`Smoothing factor: ${smoothFactor}×`}
          type="range"
          min="2"
          max="10"
          value={smoothFactor}
          disabled={!smooth || !map}
          onChange={(e) => setSmoothFactor(+e.target.value)}
        />
        <label>
          <input
            aria-label="Map contours"
            type="checkbox"
            checked={showContours}
            disabled={!map}
            onChange={(e) => setShowContours(e.target.checked)}
          />
          Contours
        </label>
        <input
          aria-label="Map contour count"
          title={`${contourCount} contour levels`}
          type="range"
          min="1"
          max="20"
          value={contourCount}
          disabled={!showContours || !map}
          onChange={(e) => setContourCount(+e.target.value)}
        />
      </div>
      <div className="integration-image-tools map-toolbar">
        <button
          className="plot-tool-button map-icon-button"
          aria-label="Save map data…"
          title="Save map data as text or TIFF"
          disabled={!ready || !map}
          onClick={() => run("map_export")}
        >
          <Save size={16} />
        </button>
        <label className="map-layer-select">
          Layer
          <select
            aria-label="Map layer"
            disabled={!ready || !map}
            value={map?.active ?? ""}
            onChange={(e) => run("map_layer", { name: e.target.value })}
          >
            {map ? (
              [
                ...map.rois.map((r) => r.name),
                ...Object.keys(map.expressions),
              ].map((n) => <option key={n}>{n}</option>)
            ) : (
              <option>No map loaded</option>
            )}
          </select>
        </label>
        <button
          className="plot-tool-button map-icon-button"
          aria-label="Save PNG…"
          title="Save map viewport as PNG"
          disabled={!ready || !map}
          onClick={() => {
            const png = mapExporter.current?.png();
            if (png) void run("map_export", { png_data: png });
          }}
        >
          PNG
        </button>
        {actions}
      </div>
    </section>
  );
}
