import type { Pattern } from "./types";
import { PlotLegend, type LegendBounds } from "./PlotLegend";

/** Qt's separate, color-coded phase legend in the upper-left plot corner. */
export function IntegrationPhaseLegend({
  lines,
  left,
  top = 10,
  bounds,
}: {
  lines: NonNullable<Pattern["phaseLines"]>;
  left: number;
  top?: number;
  bounds: LegendBounds;
}) {
  const phases = new Map<string | number, (typeof lines)[number]>();
  for (const line of lines)
    phases.set(line.phaseIndex ?? `${line.name}:${line.color}`, line);
  if (!phases.size) return null;
  return (
    <PlotLegend
      label="Phase legend"
      className="integration-phase-legend"
      entries={[...phases.values()].map((phase) => ({
        name: phase.name,
        color: phase.color,
      }))}
      left={left + 15}
      top={top}
      bounds={bounds}
      align="left"
      width={bounds.width * 0.35}
      height={bounds.height * 0.45}
    />
  );
}
