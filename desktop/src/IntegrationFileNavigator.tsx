import { Button, Input, Select } from "./ui";
import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { NavigationStep } from "./NavigationStep";

/** Qt BrowseFileWidget's shared load/checkbox, step and file-order rows. */
export function IntegrationFileNavigator({
  kind,
  step,
  onStepChange,
  canNavigate,
  order,
  onOrderChange,
  checkboxLabel,
  checked,
  onCheckedChange,
  onLoad,
  onNavigate,
  filenameControl,
  aligned = false,
  folderControl,
}: {
  kind: "image" | "pattern";
  step: number;
  onStepChange: (value: number) => void;
  canNavigate: boolean;
  order: string;
  onOrderChange: (mode: string) => void;
  checkboxLabel: string;
  checked: boolean;
  onCheckedChange: (value: boolean) => void;
  onLoad: () => void;
  onNavigate: (direction: number) => void;
  filenameControl: ReactNode;
  aligned?: boolean;
  folderControl?: ReactNode;
}) {
  const title = kind === "image" ? "Image" : "Pattern";
  return (
    <div
      className={`integration-file-browser${aligned ? " integration-file-browser-aligned" : ""}`}
    >
      <div className="integration-file-toolbar">
        <Button
          variant="secondary"
          className="integration-file-load"
          onClick={onLoad}
        >
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
        {!aligned && (
          <label className="check-row">
            <Input
              type="checkbox"
              checked={checked}
              onChange={(event) => onCheckedChange(event.target.checked)}
            />
            {checkboxLabel}
          </label>
        )}
        {aligned && (
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
        )}
      </div>
      <div
        className="integration-browse-row"
        role="group"
        aria-label={`${title} file navigation`}
      >
        <span className="integration-browse-label">File</span>
        {filenameControl}
        {aligned ? (
          folderControl
        ) : (
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
        )}
      </div>
    </div>
  );
}
