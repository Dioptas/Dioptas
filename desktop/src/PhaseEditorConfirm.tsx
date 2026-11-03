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
    popup.showModal();
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
      popup.close();
      anchor?.focus({ preventScroll: true });
    };
  }, [anchor]);
  return (
    <dialog
      ref={dialog}
      className="phase-dialog pe-confirm-popover"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onCancel();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const box = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < box.left ||
          event.clientX > box.right ||
          event.clientY < box.top ||
          event.clientY > box.bottom
        )
          onCancel();
      }}
    >
      <h3>{title}</h3>
      <p>{detail}</p>
      <footer>
        <button autoFocus onClick={onCancel}>
          Cancel
        </button>
        <button className="primary" onClick={onConfirm}>
          {action}
        </button>
      </footer>
    </dialog>
  );
}
