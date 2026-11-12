import { Input } from "./ui";
import { useModelExplanationPreference } from "./modelExplanationPreference";

export function ModelExplanationToggle() {
  const [enabled, setEnabled] = useModelExplanationPreference();
  return (
    <label className="pe-model-help-toggle">
      <Input
        type="checkbox"
        aria-label="Show model explanations"
        checked={enabled}
        onChange={(event) => setEnabled(event.target.checked)}
      />
      Show model explanations
    </label>
  );
}
