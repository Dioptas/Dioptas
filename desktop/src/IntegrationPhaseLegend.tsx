import type { Pattern } from "./types";
import "./integrationPhaseLegend.css";

/** Qt's separate, color-coded phase legend in the upper-left plot corner. */
export function IntegrationPhaseLegend({
  lines,
  left,
}: {
  lines: NonNullable<Pattern["phaseLines"]>;
  left: number;
}) {
  const phases = new Map<string | number, (typeof lines)[number]>();
  for (const line of lines)
    phases.set(line.phaseIndex ?? `${line.name}:${line.color}`, line);
  if (!phases.size) return null;
  return (
    <div
      className="integration-phase-legend"
      style={{ left: left + 15 }}
      aria-label="Phase legend"
    >
      {[...phases.entries()].map(([key, phase]) => (
        <div key={key} style={{ color: phase.color }} title={phase.name}>
          {phase.name}
        </div>
      ))}
    </div>
  );
}
