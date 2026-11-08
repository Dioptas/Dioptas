import { useAnchoredDialog } from "./useAnchoredDialog";
import { Dialog } from "./Dialog";
import { useRef } from "react";

export function PhaseEditorConfirm({
  anchor,
  title,
  detail,
  action,
  onCancel,
  onConfirm,
}: {
  anchor: HTMLButtonElement | null;
  title: string;
  detail: string;
  action: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useAnchoredDialog(dialog, anchor, true, "start");
  return (
    <Dialog
      dialogRef={dialog}
      returnFocusTarget={anchor}
      className="phase-dialog pe-confirm-popover"
      onDismiss={onCancel}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onCancel();
      }}
    >
      <h3>{title}</h3>
      <p>{detail}</p>
      <footer>
        <Button autoFocus onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" onClick={onConfirm}>
          {action}
        </Button>
      </footer>
    </Dialog>
  );
}
