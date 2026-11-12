import { useModelExplanationPreference } from "./modelExplanationPreference";
import { PhaseModelExplanation } from "./PhaseModelExplanation";
import type { ModelHelp } from "./phaseModelHelp";

export function PhaseParameterExplanation({
  help,
  id,
}: {
  help: ModelHelp;
  id: string;
}) {
  const [expanded] = useModelExplanationPreference();
  return <div id={id}>{expanded && <PhaseModelExplanation help={help} />}</div>;
}
