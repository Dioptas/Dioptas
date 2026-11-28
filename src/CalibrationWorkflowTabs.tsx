import { TabList } from "./TabList";
const sections = [
  ["Calibrate", "Calibrate"],
  ["Validate", "Validate"],
  ["Manual", "Manual picking & constraints"],
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
        name: label,
        id: `calibration-section-${index}`,
        panelId: "calibration-task-content",
        title: description,
        disabled: disabled[index],
      }))}
    />
  );
}
