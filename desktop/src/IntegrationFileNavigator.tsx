import { Button, Select } from "./ui";
import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { NavigationStep } from "./NavigationStep";

/** Shared file browser for Image and Pattern; task-specific options follow below. */
export function IntegrationFileNavigator({
  kind,
  step,
  onStepChange,
  canNavigate,
  order,
  onOrderChange,
  onLoad,
  onNavigate,
  filenameControl,
  folderControl,
}: {
  kind: "image" | "pattern";
  step: number;
  onStepChange: (value: number) => void;
  canNavigate: boolean;
  order: string;
  onOrderChange: (mode: string) => void;
  onLoad: () => void;
  onNavigate: (direction: number) => void;
  filenameControl: ReactNode;
  folderControl: ReactNode;
}) {
  const title = kind === "image" ? "Image" : "Pattern";
  return (
    <div className="integration-file-browser integration-file-browser-aligned">
      <div className="integration-file-toolbar">
        <Button className="integration-file-load" onClick={onLoad}>
          Load {kind}…
        </Button>
        <div className="integration-file-arrows">
          <Button
            className="integration-browse-arrow"
            aria-label={`Integration previous ${kind}`}
            title={`Previous ${kind} file${kind === "image" ? " · Page Up (Mac: Fn+↑)" : ""}`}
            aria-keyshortcuts={kind === "image" ? "PageUp" : undefined}
            disabled={!canNavigate}
            onClick={() => onNavigate(-1)}
          >
            <ChevronLeft size={18} aria-hidden="true" />
          </Button>
          <Button
            className="integration-browse-arrow"
            aria-label={`Integration next ${kind}`}
            title={`Next ${kind} file${kind === "image" ? " · Page Down (Mac: Fn+↓)" : ""}`}
            aria-keyshortcuts={kind === "image" ? "PageDown" : undefined}
            disabled={!canNavigate}
            onClick={() => onNavigate(1)}
          >
            <ChevronRight size={18} aria-hidden="true" />
          </Button>
        </div>
        <NavigationStep
          label={kind === "image" ? "File step" : "Pattern file step"}
          value={step}
          onChange={onStepChange}
        />
        <label className="integration-file-order">
          <span>Browse by</span>
          <Select
            aria-label={`${title} file order`}
            title="Browse files by filename number or creation time"
            value={order}
            onChange={(event) => onOrderChange(event.target.value)}
          >
            <option value="number">Name</option>
            <option value="time">Time</option>
          </Select>
        </label>
      </div>
      <div
        className="integration-browse-row"
        role="group"
        aria-label={`${title} file navigation`}
      >
        <span className="integration-browse-label">File</span>
        {filenameControl}
        {folderControl}
      </div>
    </div>
  );
}
