import { TabList } from "./TabList";
const sections = [
  ["Image", "Image & setup"],
  ["Peaks", "Pick rings"],
  ["Fit", "Calibrate"],
  ["Validate", "Validate"],
] as const;

export function CalibrationWorkflowTabs({
  active,
  disabled,
  onChange,
}: {
  active: number;
  disabled: readonly boolean[];
  onChange: (index: number) => void;
}) {
  return (
    <TabList
      className="calibration-workflow-tabs"
      label="Calibration sections"
      value={active}
      onChange={onChange}
      options={sections.map(([label, description], index) => ({
        value: index,
        label,
        name: `Step ${index + 1}: ${description}`,
        id: `calibration-section-${index}`,
        panelId: "calibration-task-content",
        title: description,
        disabled: disabled[index],
      }))}
    />
  );
}
