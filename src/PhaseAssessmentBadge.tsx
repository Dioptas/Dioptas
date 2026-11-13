import {
  CheckCircle2,
  CircleHelp,
  Info,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import type { PhaseReference } from "./integrationPhase";

/** Colour the recorded outcome without promoting a scoped check to reproduction. */
export function PhaseAssessmentBadge({
  reference,
}: {
  reference?: PhaseReference;
}) {
  const label = reference?.assessment || "Not assessed";
  const tone = ["Reproduced", "Parameter parity", "Curve parity"].includes(
    label,
  )
    ? "success"
    : ["Similar", "Limited check", "Provisional refit"].includes(label)
      ? "warning"
      : ["Not reproduced", "Do not use"].includes(label)
        ? "danger"
        : [
              "Equation reconstruction",
              "Independent refit",
              "Check documented",
            ].includes(label)
          ? "info"
          : "neutral";
  const Icon = {
    success: CheckCircle2,
    warning: TriangleAlert,
    danger: XCircle,
    info: Info,
    neutral: CircleHelp,
  }[tone];
  return (
    <span
      className="pe-assessment"
      data-tone={tone}
      aria-label={`Reproduction assessment: ${label}`}
      title={reference?.detail}
    >
      <Icon aria-hidden="true" />
      {label}
    </span>
  );
}
