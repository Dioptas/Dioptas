import type { ModelHelp } from "./phaseModelHelp";
import { PeritheosManualLink } from "./PeritheosManualLink";
import "./phaseModelHelp.css";

export function PhaseModelExplanation({
  help,
  id,
}: {
  help: ModelHelp;
  id?: string;
}) {
  return (
    <div className="pe-model-help" id={id}>
      <p>
        <strong>{help.title}</strong> · {help.description}
      </p>
      {help.equations?.map((equation) => (
        <div
          key={equation.text}
          className="pe-model-equation"
          dangerouslySetInnerHTML={{ __html: equation.math }}
        />
      ))}
      {help.note && <p>{help.note}</p>}
      <PeritheosManualLink
        href={help.url}
        label={`PeriTheos manual: ${help.title}`}
      />
    </div>
  );
}
