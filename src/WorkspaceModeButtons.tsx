import { Button } from "./ui";
import { Crosshair, ScanLine } from "lucide-react";
import { IntegrationModeIcon, MapModeIcon, MaskModeIcon } from "./ModeIcons";
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
    name: "Single Crystal XRD",
    label: "SCXRD",
    icon: <ScanLine size={20} />,
  },
] as const;

/**
 * Single Crystal XRD is being reworked on `feature/scxrd-rebuild` and is not
 * part of the next release. Its code stays in place; only the mode button is
 * withheld so users cannot enter it. Set to true to bring the mode back.
 */
export const SINGLE_CRYSTAL_MODE_ENABLED = false;

const visibleModes = modes.filter(
  (item) => SINGLE_CRYSTAL_MODE_ENABLED || item.value !== "scxrd",
);

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
      {visibleModes.map((item) => (
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
