import { FolderOpen } from "lucide-react";

export function LoadCalibrationButton({
  ready,
  onLoad,
  label,
}: {
  ready: boolean;
  onLoad: () => void;
  label: string;
}) {
  return (
    <button
      className="plot-tool-button"
      aria-label={label}
      disabled={!ready}
      onClick={onLoad}
    >
      <FolderOpen size={15} /> Load calibration…
    </button>
  );
}
