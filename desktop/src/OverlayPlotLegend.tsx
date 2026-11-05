import { PlotLegend, type LegendEntry, type LegendBounds } from "./PlotLegend";
/** Qt PatternWidget's compact names float inside the scientific data area. */
export function OverlayPlotLegend(props: {
  entries: LegendEntry[];
  left: number;
  top: number;
  width: number;
  height: number;
  bounds: LegendBounds;
}) {
  return (
    <PlotLegend
      {...props}
      label="Pattern legend"
      className="overlay-plot-legend"
    />
  );
}
