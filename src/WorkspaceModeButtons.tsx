import { Button } from "./ui";
import { Crosshair } from "lucide-react";
import {
  IntegrationModeIcon,
  MapModeIcon,
  MaskModeIcon,
  SingleCrystalModeIcon,
} from "./ModeIcons";
export type WorkspaceMode =
  "calibration" | "mask" | "integration" | "map" | "scxrd";
const modes = [
  {
    value: "calibration",
    name: "Calibration",
    label: "Calib",
    icon: <Crosshair size={20} />,
  },
  { value: "mask", name: "Mask", label: "Mask", icon: <MaskModeIcon /> },
  {
    value: "integration",
    name: "Integration",
    label: "Int",
    icon: <IntegrationModeIcon />,
  },
  { value: "map", name: "Map", label: "Map", icon: <MapModeIcon /> },
  {
    value: "scxrd",
    name: "Single Crystal",
    label: "SC",
    icon: <SingleCrystalModeIcon />,
  },
] as const;

/** Mode buttons keep one visual, naming and selection contract. */
export function WorkspaceModeButtons({
  mode,
  onSelect,
}: {
  mode: WorkspaceMode | null;
  onSelect: (mode: WorkspaceMode) => void;
}) {
  return (
    <>
      {modes.map((item) => (
        <Button
          key={item.value}
          className={`workspace-nav ${mode === item.value ? "workspace-active" : ""}`}
          aria-label={item.name}
          aria-pressed={mode === item.value}
          title={item.name}
          onClick={() => onSelect(item.value)}
        >
          {item.icon}
          <span>{item.label}</span>
        </Button>
      ))}
    </>
  );
}
