import { TabList } from "./TabList";
export function CalibrationTabs({
  label,
  tabs,
  active,
  onChange,
}: {
  label: string;
  tabs: readonly string[];
  active: number;
  onChange: (index: number) => void;
}) {
  return (
    <TabList
      className="calibration-section-tabs"
      label={label}
      value={active}
      onChange={onChange}
      options={tabs.map((tab, index) => ({ value: index, label: tab }))}
    />
  );
}
