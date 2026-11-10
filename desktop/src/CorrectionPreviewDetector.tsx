import { DetectorSurface } from "./DetectorWindow";
import { detectorViewport, type ViewportMemory } from "./plotViewport";
import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
import { RasterView } from "./RasterView";
import { ImageIntensity } from "./ImageIntensity";
import {
  useCorrectionPreviewReadout,
  type PreviewGeometrySample,
} from "./useCorrectionPreviewReadout";
import type { CorrectionPreview } from "./correctionPreview";
import type { AutoLevels, ImageDisplayPreferences, Palette } from "./types";
import type { ReportPlot } from "./plotReadout";
import "./correctionPreview.css";

/** An independent display surface. The source renderer and all its view state
 * stay mounted behind it. No mask, ROI, processing or source export is attached. */
export function CorrectionPreviewDetector({
  map,
  ready,
  onBack,
  onAuto,
  reportPlot,
  sampleGeometry,
  wavelength,
}: {
  map: CorrectionPreview;
  ready: boolean;
  onBack: () => void;
  onAuto: (settings: AutoLevels) => Promise<void>;
  reportPlot: ReportPlot;
  sampleGeometry: PreviewGeometrySample;
  wavelength?: number;
}) {
  const viewport = useRef<ViewportMemory>({ current: null });
  const [limits, setLimits] = useState(map.raster.limits);
  useEffect(() => setLimits(map.raster.limits), [map.raster]);
  const [log, setLog] = useState(false);
  const [palette, setPalette] = useState<Palette>("grey");
  const [preferences, setPreferences] = useState<ImageDisplayPreferences>({
    orientation: "vertical",
    auto: { mode: "percentile", percentile: 2.5, filter_gaps: false },
  });
  const [clicked, setClicked] = useState<{ x: number; y: number } | null>(null);
  const reading = useCorrectionPreviewReadout(
    map,
    wavelength,
    reportPlot,
    sampleGeometry,
  );
  return (
    <div
      className="correction-preview"
      role="region"
      aria-label="Correction map preview"
      data-kind={map.kind}
    >
      <div className="correction-preview-heading">
        <span title="The scientific image is divided by this map">
          {map.label} · {map.units}
        </span>
        <Button onClick={onBack}>Back</Button>
      </div>
      <DetectorSurface
        priority={1}
        interactionKey={`correction-${map.kind}`}
        label={`${map.label} · ${map.units} · divisor`}
        onBack={onBack}
      >
        <RasterView
          raster={map.raster}
          viewport={detectorViewport(
            viewport.current,
            `correction-${map.kind}`,
          )}
          limits={limits}
          log={log}
          palette={palette}
          onHover={reading}
          clickedPoint={clicked}
          onInspect={(point) => {
            setClicked(point);
            reading(point);
          }}
        />
        <ImageIntensity
          raster={map.raster}
          limits={limits}
          onLimits={setLimits}
          log={log}
          onLog={setLog}
          palette={palette}
          onPalette={setPalette}
          ready={ready}
          preferences={preferences}
          onPreferences={setPreferences}
          gapFiltering={false}
          initialLevelsReady
          onAuto={async (settings) => {
            await onAuto({ ...settings, filter_gaps: false });
          }}
        />
      </DetectorSurface>
    </div>
  );
}
