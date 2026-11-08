import { Button, Dialog } from "./ui";
import { useLayoutEffect, useRef } from "react";

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
  useLayoutEffect(() => {
    const popup = dialog.current!;
    const place = () => {
      const target = anchor?.getBoundingClientRect();
      if (!target) return;
      const box = popup.getBoundingClientRect();
      const left = Math.max(
        12,
        Math.min(target.left, window.innerWidth - box.width - 12),
      );
      const below = target.bottom + 6;
      const top =
        below + box.height <= window.innerHeight - 12
          ? below
          : target.top - box.height - 6;
      popup.style.left = `${left}px`;
      popup.style.top = `${Math.max(12, top)}px`;
    };
    place();
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("resize", place);
      anchor?.focus({ preventScroll: true });
    };
  }, [anchor]);
  return (
    <Dialog
      backdrop="clear"
      open
      ref={dialog}
      className="phase-dialog pe-confirm-popover"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onCancel();
      }}
      dismissOnBackdrop
      onDismiss={onCancel}
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
